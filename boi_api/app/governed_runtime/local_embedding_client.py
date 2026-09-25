"""Bounded OpenAI-compatible local embeddings for logical profile retrieval."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from contextvars import ContextVar
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable
from threading import Lock
from urllib import request
from urllib.parse import urlsplit

from .semantic_profile_retrieval import RetrievalDocument


JsonTransport = Callable[[str, dict[str, Any], float], dict[str, Any]]


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _default_transport(
    url: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    call = request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(call, timeout=timeout) as response:  # noqa: S310
        decoded = json.loads(response.read().decode())
    if not isinstance(decoded, dict):
        raise ValueError("LOCAL_EMBEDDING_RESPONSE_NOT_OBJECT")
    return decoded


class PreparedEmbeddingClient:
    """Score a question only against bounded, ACL-filtered logical documents."""

    MAX_DOCUMENTS_PER_REQUEST = 64
    MAX_INPUT_BYTES = 131_072
    PROVIDER_NAME = 'openai-compatible-configured'

    def __init__(
        self,
        *,
        base_url: str,
        model_id: str,
        model_digest: str,
        dimensions: int,
        timeout_seconds: float = 60.0,
        transport: JsonTransport | None = None,
        cache_path: str | Path | None = None,
        cache_queries: bool = False,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("LOCAL_EMBEDDING_BASE_URL_INVALID")
        if not model_id.strip():
            raise ValueError("LOCAL_EMBEDDING_MODEL_REQUIRED")
        if dimensions < 1:
            raise ValueError("LOCAL_EMBEDDING_DIMENSIONS_INVALID")
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id.strip()
        self.model_digest = model_digest
        self.dimensions = dimensions
        self.cache_queries = cache_queries
        self._query_lock = Lock()
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport
        # Injected transports default to a process-local test cache. The existing
        # production factory automatically shares a private persistent vector cache.
        self.cache_path = Path(cache_path).expanduser() if cache_path is not None else (
            Path(os.environ.get("BOI_LOCAL_EMBEDDING_CACHE_PATH") or
                 str(Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") /
                     "boi-wiki-governed" / "logical-vectors-v1.sqlite3"))
            if transport is None else None
        )
        self._memory_vectors: dict[str, tuple[float, ...]] = {}
        self._diagnostics: ContextVar[dict[str, Any] | None] = ContextVar(
            "local_embedding_diagnostics", default=None)
        self.identity_digest = _digest(
            {
                "provider": self.PROVIDER_NAME,
                "base_origin": f"{parsed.scheme}://{parsed.netloc}",
                "endpoint": self.base_url,
                "model_id": self.model_id,
                "model_digest": self.model_digest,
                "dimensions": self.dimensions,
            }
        )

    @staticmethod
    def _vector(item: object, *, dimensions: int) -> tuple[float, ...]:
        if not isinstance(item, list) or len(item) != dimensions:
            raise ValueError("LOCAL_EMBEDDING_DIMENSION_MISMATCH")
        vector = tuple(float(value) for value in item)
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("LOCAL_EMBEDDING_VALUE_INVALID")
        if math.sqrt(sum(value * value for value in vector)) == 0:
            raise ValueError("LOCAL_EMBEDDING_ZERO_VECTOR")
        return vector

    @staticmethod
    def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return max(0.0, min(1.0, numerator / (left_norm * right_norm)))

    def __call__(
        self, question: str, documents: tuple[RetrievalDocument, ...]
    ) -> dict[str, float]:
        if not question.strip():
            raise ValueError("QUESTION_REQUIRED")
        self._validate_documents(documents)
        keys = {document.entry_id: self._document_key(document) for document in documents}
        return self.score_prepared(question, keys)

    def score_prepared(self, question: str, keys: dict[str, str]) -> dict[str, float]:
        """Consume exact cache keys prepared at publication, never document text.

        The caller supplies only currently authorized revision keys. A single
        invocation spans all namespaces and issues at most one query embedding.
        """
        if not question.strip():
            raise ValueError('QUESTION_REQUIRED')
        cached = self._read_vectors(tuple(keys.values()))
        available = {entry_id: cached[key] for entry_id, key in keys.items() if key in cached}
        missing = tuple(entry_id for entry_id in keys if entry_id not in available)
        self._diagnostics.set({"status": "not_indexed" if not available else "partial_index" if missing else "indexed",
                               "document_embedding_calls": 0, "query_embedding_calls": 0,
                               "indexed_document_count": len(available), "missing_document_ids": missing,
                               "embedding_identity_digest": self.identity_digest})
        if not available:
            # An absent vector is unknown. The caller retains lexical, alias and
            # graph candidates; discovery is never a semantic validation verdict.
            return {}
        query_key = _digest({'schema': 'boi/query-vector@1', 'provider': self.identity_digest,
                             'question': question})
        with self._query_lock if self.cache_queries else nullcontext():
            query_vector = self._read_vectors((query_key,)).get(query_key) if self.cache_queries else None
            if self.cache_queries:
                self._diagnostics.set({**self.last_retrieval_diagnostics, 'query_vector_cache_hit': query_vector is not None})
            if query_vector is None:
                self._diagnostics.set({**self.last_retrieval_diagnostics, "query_embedding_calls": 1})
                query_vector = self._embed([question])[0]
                if self.cache_queries:
                    self._write_vectors({query_key: query_vector})
        return {entry_id: round(self._cosine(query_vector, vector), 12)
                for entry_id, vector in available.items()}

    @property
    def last_retrieval_diagnostics(self) -> dict[str, Any]:
        return dict(self._diagnostics.get() or {})

    @staticmethod
    def _validate_documents(documents: tuple[RetrievalDocument, ...]) -> None:
        if len({document.entry_id for document in documents}) != len(documents):
            raise ValueError("LOCAL_EMBEDDING_DOCUMENT_ID_DUPLICATE")

    def _document_key(self, document: RetrievalDocument) -> str:
        return _digest({"schema": "boi/logical-vector@1", "provider": self.identity_digest,
                        "document": document.model_dump(mode="json")})

    def prepared_key(self, document: RetrievalDocument) -> str:
        return self._document_key(document)

    def _read_vectors(self, keys: tuple[str, ...]) -> dict[str, tuple[float, ...]]:
        if self.cache_path is None:
            return {key: self._memory_vectors[key] for key in keys if key in self._memory_vectors}
        if not keys or not self.cache_path.is_file():
            return {}
        rows = []
        try:
            with sqlite3.connect(self.cache_path.resolve().as_uri() + "?mode=ro", uri=True) as db:
                for offset in range(0, len(keys), 500):
                    batch = keys[offset:offset + 500]
                    rows.extend(db.execute("SELECT cache_key, vector_json, vector_digest FROM logical_vectors_v1 WHERE cache_key IN ("
                                           + ",".join("?" for _ in batch) + ")", batch).fetchall())
        except sqlite3.DatabaseError:
            return {}
        result = {}
        for key, encoded, digest in rows:
            try:
                raw = json.loads(encoded)
                if _digest(raw) == digest:
                    result[key] = self._vector(raw, dimensions=self.dimensions)
            except (TypeError, ValueError, OverflowError):
                continue
        return result

    def _write_vectors(self, vectors: dict[str, tuple[float, ...]]) -> None:
        if self.cache_path is None:
            self._memory_vectors.update(vectors)
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.cache_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        with sqlite3.connect(self.cache_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS logical_vectors_v1 (cache_key TEXT PRIMARY KEY, vector_json TEXT NOT NULL, vector_digest TEXT NOT NULL)")
            db.executemany("INSERT OR REPLACE INTO logical_vectors_v1 VALUES (?, ?, ?)",
                           [(key, json.dumps(vector), _digest(vector)) for key, vector in vectors.items()])

    def index_documents(self, documents: tuple[RetrievalDocument, ...]) -> dict[str, Any]:
        """Explicit ingestion/backfill operation; never invoked by question scoring.

        The producer passes the same ACL-filtered logical projection used by
        retrieval, including revision digests. Only validated vectors are stored;
        source text, questions and candidate sets are not persisted in this cache.
        """
        self._validate_documents(documents)
        keys = {document.entry_id: self._document_key(document) for document in documents}
        cached = self._read_vectors(tuple(keys.values()))
        missing = [document for document in documents if keys[document.entry_id] not in cached]
        calls, indexed = 0, 0
        batch: list[RetrievalDocument] = []

        def publish(items: list[RetrievalDocument]) -> None:
            nonlocal calls, indexed
            if not items:
                return
            vectors = self._embed([item.search_text for item in items])
            self._write_vectors({keys[item.entry_id]: vector for item, vector in zip(items, vectors)})
            calls += 1
            indexed += len(items)

        for document in missing:
            trial = [*batch, document]
            payload = {"model": self.model_id, "input": [item.search_text for item in trial]}
            if batch and (len(trial) > self.MAX_DOCUMENTS_PER_REQUEST or
                          len(json.dumps(payload, ensure_ascii=False).encode()) > self.MAX_INPUT_BYTES):
                publish(batch)
                batch = []
            batch.append(document)
        publish(batch)
        return {"status": "indexed", "indexed_document_count": indexed,
                "cache_hit_count": len(documents) - len(missing),
                "document_embedding_calls": calls, "query_embedding_calls": 0,
                "embedding_identity_digest": self.identity_digest}

    def _embed(self, inputs: list[str]) -> list[tuple[float, ...]]:
        payload = {"model": self.model_id, "input": inputs}
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        if len(encoded) > self.MAX_INPUT_BYTES:
            raise ValueError("LOCAL_EMBEDDING_INPUT_BYTE_LIMIT")
        response = self.transport(
            f"{self.base_url}/embeddings", payload, self.timeout_seconds
        )
        if response.get("model") not in {None, self.model_id}:
            raise ValueError("LOCAL_EMBEDDING_MODEL_MISMATCH")
        raw = response.get("data")
        if not isinstance(raw, list) or len(raw) != len(inputs):
            raise ValueError("LOCAL_EMBEDDING_VECTOR_COUNT_MISMATCH")
        indexed: dict[int, tuple[float, ...]] = {}
        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError("LOCAL_EMBEDDING_ITEM_INVALID")
            index = item.get("index", position)
            if type(index) is not int or index in indexed:
                raise ValueError("LOCAL_EMBEDDING_INDEX_INVALID")
            indexed[index] = self._vector(
                item.get("embedding"), dimensions=self.dimensions
            )
        if set(indexed) != set(range(len(inputs))):
            raise ValueError("LOCAL_EMBEDDING_INDEX_CLOSURE_MISMATCH")
        return [indexed[position] for position in range(len(inputs))]


class LocalEmbeddingClient(PreparedEmbeddingClient):
    """Historical local-profile transport keeps its original loopback boundary."""

    PROVIDER_NAME = 'openai-compatible-local'

    def __init__(self, *, base_url: str, **kwargs):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ValueError('LOCAL_EMBEDDING_BASE_URL_INVALID')
        if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('LOCAL_EMBEDDING_ENDPOINT_NOT_LOOPBACK')
        super().__init__(base_url=base_url, **kwargs)
