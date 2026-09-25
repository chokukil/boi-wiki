"""Rebuild disposable Search, Graph, MCP, and download projections from a Release."""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import re
import shutil
import threading
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .ledger import GovernedRuntimeLedger, RecordKind, record_digest
from .immutable_io import publish_immutable
from .okf_v02 import validate_boi_profile_v02
from .qualification_contract import QualificationContractError, validate_qualification_receipt_payload
from .diagnostic_timing import stage_timing


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ReleaseRebuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseProjectionResult:
    release_id: str
    projection_digest: str
    path: Path
    revision_count: int
    search_count: int
    graph_edge_count: int
    mcp_count: int
    download_count: int
    html_report_count: int
    pdf_report_count: int


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_json(value: Any) -> str:
    return _digest_bytes(_canonical_json(value))


class KnowledgeObjectStore:
    """Minimal immutable byte store; canonical authority remains the ledger."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    # Disposable, process-local derived JSON, shared by request-scoped readers.
    # Never stores an ACL decision. Files and the ledger remain authoritative.
    _derived = OrderedDict()
    _derived_lock = threading.RLock()
    _derived_bytes = 0
    _derived_limit = 8 * 1024 * 1024

    def _projection_key(self):
        directory = self.root / '.derived'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        key_path = directory / '.integrity-key'
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(os.urandom(32))
                output.flush()
                os.fsync(output.fileno())
        key = key_path.read_bytes()
        if len(key) != 32:
            raise ValueError('PROJECTION_CACHE_KEY_INVALID')
        return key

    def _projection_path(self, object_id, version):
        digest = _digest_json([object_id, version]).removeprefix('sha256:')
        return self.root / '.derived' / digest[:2] / (digest + '.json')

    def _read_projection(self, object_id, version):
        """Only local authenticated cache bytes; ACL decisions are never stored."""
        path = self._projection_path(object_id, version)
        try:
            if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
                return None
            envelope = json.loads(path.read_bytes())
            payload = envelope['payload']
            if payload['object_id'] != object_id or payload['version'] != version:
                return None
            signature = hmac.new(self._projection_key(), _canonical_json(payload), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, envelope['signature']):
                return None
            return json.dumps(payload['value'], ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _write_projection(self, object_id, version, encoded):
        """Best-effort disposable index, atomically replaced independently of assets."""
        temporary = None
        try:
            if len(encoded) > 32 * 1024 * 1024:
                return
            payload = {'object_id':object_id, 'version':version, 'value':json.loads(encoded)}
            signature = hmac.new(self._projection_key(), _canonical_json(payload), hashlib.sha256).hexdigest()
            path = self._projection_path(object_id, version)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temporary = output.name
                output.write(_canonical_json({'payload':payload, 'signature':signature}))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            temporary = None
        except (OSError, ValueError, TypeError):
            # A disposable projection failure cannot revoke a committed asset.
            pass
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def project_verified(self, object_id: str, *, version: str, derive, persistent=False):
        """Reuse a versioned projection only while the immutable file is unchanged.

        The local filesystem's identity/change token is checked on every call;
        replacement, in-place edits (including restored mtime), or removal force
        a digest-verified read. No source bytes or authority enter this cache.
        Adapters without this integrity capability must use ordinary reads.
        Explicit discovery projections can persist in the same object store.
        Every cold read still verifies original bytes; authorization/validation
        callers retain the default process-local behavior.
        """
        path = self.path_for(object_id)
        def token():
            try:
                s = path.stat()
            except OSError as exc:
                raise ReleaseRebuildError(f"knowledge object is missing: {object_id}") from exc
            return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        signature = token()
        key = (str(path.absolute()), object_id, version)
        cls = KnowledgeObjectStore
        with cls._derived_lock:
            cached = cls._derived.get(key)
            if cached is not None and cached[0] == signature:
                cls._derived.move_to_end(key)
                return json.loads(cached[1])
        original = self.get(object_id)
        encoded = self._read_projection(object_id, version) if persistent else None
        if encoded is None:
            value = derive(original)
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if persistent:
                self._write_projection(object_id, version, encoded)
        if token() != signature:
            raise ReleaseRebuildError(f"knowledge object changed during projection: {object_id}")
        with cls._derived_lock:
            old = cls._derived.pop(key, None)
            if old is not None:
                cls._derived_bytes -= len(old[1])
            if len(encoded) <= cls._derived_limit:
                cls._derived[key] = (signature, encoded)
                cls._derived_bytes += len(encoded)
            while len(cls._derived) > 4096 or cls._derived_bytes > cls._derived_limit:
                _, removed = cls._derived.popitem(last=False)
                cls._derived_bytes -= len(removed[1])
        return json.loads(encoded)

    def path_for(self, object_id: str) -> Path:
        if not SHA256_RE.fullmatch(object_id):
            raise ReleaseRebuildError("knowledge object id must be canonical sha256")
        return self.root / object_id.removeprefix("sha256:")[:2] / object_id.removeprefix("sha256:")

    def put(self, payload: bytes) -> str:
        object_id = _digest_bytes(payload)
        path = self.path_for(object_id)
        if path.exists():
            if path.read_bytes() != payload:
                raise ReleaseRebuildError("immutable knowledge object conflict")
            return object_id
        publish_immutable(path, payload)
        if path.read_bytes() != payload:
            raise ReleaseRebuildError("immutable knowledge object conflict")
        return object_id

    @stage_timing('knowledge_object_get')
    def get(self, object_id: str) -> bytes:
        path = self.path_for(object_id)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ReleaseRebuildError(f"knowledge object is missing: {object_id}") from exc
        if _digest_bytes(payload) != object_id:
            raise ReleaseRebuildError(f"knowledge object digest mismatch: {object_id}")
        return payload


def _document(payload: bytes) -> tuple[dict[str, Any], str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReleaseRebuildError("released document is not UTF-8") from exc
    match = re.match(r"\A---\n(?P<header>.*?)\n---\n(?P<body>.*)\Z", text, flags=re.DOTALL)
    if not match:
        raise ReleaseRebuildError("released document frontmatter is invalid")
    metadata = yaml.safe_load(match.group("header")) or {}
    if not isinstance(metadata, dict):
        raise ReleaseRebuildError("released document frontmatter must be a mapping")
    validation = validate_boi_profile_v02(metadata)
    if not validation.ok:
        raise ReleaseRebuildError("released document fails strict BoI Profile 0.2")
    return metadata, match.group("body")


def _relations(metadata: Mapping[str, Any]) -> list[tuple[str, str]]:
    relations: list[tuple[str, str]] = []
    for field, raw in metadata.items():
        if field.endswith("_ref") and isinstance(raw, str) and raw.strip():
            relations.append((field.removesuffix("_ref"), raw.strip()))
        elif field.endswith("_refs") and isinstance(raw, list):
            relations.extend((field.removesuffix("_refs"), str(item)) for item in raw if str(item).strip())
    return sorted(set(relations))


def _html_report(item: Mapping[str, Any]) -> bytes:
    metadata = item["metadata"]
    source_rows = "".join(
        "<li><code>"
        + html.escape(json.dumps(source, ensure_ascii=False, sort_keys=True))
        + "</code></li>"
        for source in metadata.get("sources", [])
    )
    value = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(str(metadata['title']))}</title></head>
<body data-knowledge-revision="{html.escape(str(item['revision_id']))}">
<main><h1>{html.escape(str(metadata['title']))}</h1>
<dl><dt>KnowledgeRevision</dt><dd><code>{html.escape(str(item['revision_id']))}</code></dd>
<dt>BoI ID</dt><dd><code>{html.escape(str(metadata['boi_id']))}</code></dd>
<dt>Type</dt><dd><code>{html.escape(str(metadata['type']))}</code></dd>
<dt>Visibility</dt><dd>{html.escape(str(metadata['visibility']))}</dd>
<dt>ACL policy</dt><dd><code>{html.escape(str(metadata['acl_policy']))}</code></dd></dl>
<p>{html.escape(str(metadata['description']))}</p><h2>Sources</h2><ul>{source_rows}</ul>
<h2>Content</h2><pre>{html.escape(str(item['body']))}</pre></main></body></html>
"""
    return value.encode("utf-8")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_report(item: Mapping[str, Any], *, release_id: str) -> bytes:
    metadata = item["metadata"]
    fields = (
        f"Release: {release_id}",
        f"KnowledgeRevision: {item['revision_id']}",
        f"Object: {item['object_id']}",
        "BoI ID: " + json.dumps(metadata["boi_id"], ensure_ascii=True),
        "Type: " + json.dumps(metadata["type"], ensure_ascii=True),
        "Title: " + json.dumps(metadata["title"], ensure_ascii=True),
        "Description: " + json.dumps(metadata["description"], ensure_ascii=True),
        f"Body digest: {_digest_bytes(str(item['body']).encode('utf-8'))}",
    )
    commands = ["BT", "/F1 9 Tf", "40 800 Td", "11 TL"]
    for field in fields:
        for offset in range(0, len(field), 92):
            commands.append(f"({_pdf_escape(field[offset:offset + 92])}) Tj")
            commands.append("T*")
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("ascii")
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    )
    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode("ascii"))
        payload.extend(value)
        payload.extend(b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(payload)


class ReleaseProjectionRebuilder:
    def __init__(
        self,
        ledger: GovernedRuntimeLedger,
        object_store: KnowledgeObjectStore,
        output_root: Path | str,
    ):
        self.ledger = ledger
        self.object_store = object_store
        self.output_root = Path(output_root)

    def rebuild_active(self) -> ReleaseProjectionResult:
        pointer = self.ledger.active_pointer()
        if pointer is None or pointer.get("status") != "ACTIVE":
            raise ReleaseRebuildError("active Release pointer is absent")
        release_id = str(pointer.get("release_id") or "")
        if pointer.get("release_manifest_digest") != record_digest(release_id):
            raise ReleaseRebuildError("active pointer manifest digest mismatch")
        if not self.ledger.verify().ok:
            raise ReleaseRebuildError("ledger verification failed")
        release = self.ledger.read(release_id)
        if release.kind is not RecordKind.RELEASE_MANIFEST:
            raise ReleaseRebuildError("active pointer does not target ReleaseManifest")
        receipt = self.ledger.read(str(release.payload.get("qualification_receipt_id") or ""))
        if receipt.kind is not RecordKind.QUALIFICATION_RECEIPT:
            raise ReleaseRebuildError("active Release is not qualified")
        try:
            validate_qualification_receipt_payload(receipt.payload)
        except QualificationContractError as exc:
            raise ReleaseRebuildError("active Release lacks exact QualificationContract") from exc
        revision_ids = list(release.payload.get("revision_ids") or [])
        if revision_ids != list(receipt.payload.get("revision_ids") or []):
            raise ReleaseRebuildError("Release and qualification revisions differ")

        documents: list[dict[str, Any]] = []
        id_to_revision: dict[str, str] = {}
        downloads: dict[str, str] = {}
        for revision_id in revision_ids:
            revision = self.ledger.read(revision_id)
            if revision.kind is not RecordKind.KNOWLEDGE_REVISION:
                raise ReleaseRebuildError("Release contains non-KnowledgeRevision")
            object_id = str(revision.payload.get("document_object_id") or "")
            payload = self.object_store.get(object_id)
            if _digest_bytes(payload) != revision.payload.get("document_digest"):
                raise ReleaseRebuildError("KnowledgeRevision document digest mismatch")
            metadata, body = _document(payload)
            boi_id = str(metadata["boi_id"])
            if boi_id in id_to_revision:
                raise ReleaseRebuildError("Release contains duplicate boi_id")
            id_to_revision[boi_id] = revision_id
            downloads[revision_id] = object_id
            documents.append(
                {
                    "revision_id": revision_id,
                    "object_id": object_id,
                    "metadata": metadata,
                    "body": body,
                }
            )
        search_rows = [
            {
                "knowledge_revision_id": item["revision_id"],
                "release_id": release_id,
                "boi_id": item["metadata"]["boi_id"],
                "type": item["metadata"]["type"],
                "title": item["metadata"]["title"],
                "description": item["metadata"]["description"],
                "visibility": item["metadata"]["visibility"],
                "acl_policy": item["metadata"]["acl_policy"],
                "searchable_text": item["body"],
                "content_digest": item["object_id"],
            }
            for item in documents
        ]
        graph_edges = []
        for item in documents:
            source_id = str(item["metadata"]["boi_id"])
            for relation, target_id in _relations(item["metadata"]):
                graph_edges.append(
                    {
                        "source_revision_id": item["revision_id"],
                        "source_boi_id": source_id,
                        "relation": relation,
                        "target_boi_id": target_id,
                        "target_revision_id": id_to_revision.get(target_id),
                        "resolved": target_id in id_to_revision,
                    }
                )
        graph_edges.sort(key=lambda item: (item["source_revision_id"], item["relation"], item["target_boi_id"]))
        mcp_documents = [
            {
                "knowledge_revision_id": item["revision_id"],
                "release_id": release_id,
                "content_digest": item["object_id"],
                "metadata": item["metadata"],
                "body": item["body"],
            }
            for item in documents
        ]

        report_files: dict[str, bytes] = {}
        reports: dict[str, dict[str, str]] = {}
        for item in documents:
            report_key = record_digest(str(item["revision_id"])).removeprefix("sha256:")
            html_path = f"reports/{report_key}.html"
            pdf_path = f"reports/{report_key}.pdf"
            html_payload = _html_report(item)
            pdf_payload = _pdf_report(item, release_id=release_id)
            report_files[html_path] = html_payload
            report_files[pdf_path] = pdf_payload
            reports[str(item["revision_id"])] = {
                "knowledge_revision_id": str(item["revision_id"]),
                "content_digest": str(item["object_id"]),
                "acl_policy": str(item["metadata"]["acl_policy"]),
                "html_path": html_path,
                "html_digest": _digest_bytes(html_payload),
                "pdf_path": pdf_path,
                "pdf_digest": _digest_bytes(pdf_payload),
            }

        files = {
            "search.jsonl": b"".join(_canonical_json(row) + b"\n" for row in search_rows),
            "graph.json": _canonical_json({"release_id": release_id, "edges": graph_edges}) + b"\n",
            "mcp.json": _canonical_json({"release_id": release_id, "documents": mcp_documents}) + b"\n",
            "download-index.json": _canonical_json({"release_id": release_id, "objects": downloads}) + b"\n",
            "report-index.json": _canonical_json(
                {"release_id": release_id, "reports": reports}
            )
            + b"\n",
            **report_files,
        }
        file_digests = {name: _digest_bytes(payload) for name, payload in sorted(files.items())}
        projection_base = {
            "schema": "boi-release-projection/v1",
            "release_id": release_id,
            "release_manifest_digest": record_digest(release_id),
            "qualification_receipt_id": receipt.record_id,
            "revision_ids": revision_ids,
            "files": file_digests,
            "counts": {
                "revisions": len(revision_ids),
                "search": len(search_rows),
                "graph_edges": len(graph_edges),
                "mcp": len(mcp_documents),
                "download": len(downloads),
                "html_reports": len(reports),
                "pdf_reports": len(reports),
            },
        }
        projection_digest = _digest_json(projection_base)
        manifest = {**projection_base, "projection_digest": projection_digest}
        files["projection-manifest.json"] = _canonical_json(manifest) + b"\n"
        target = self.output_root / projection_digest.removeprefix("sha256:")

        if target.exists():
            self._verify_existing(target, files)
        else:
            temporary = self.output_root / f".{target.name}.staging"
            self.output_root.mkdir(parents=True, exist_ok=True)
            if temporary.exists():
                shutil.rmtree(temporary)
            try:
                temporary.mkdir(parents=True)
                for name, payload in files.items():
                    destination = temporary / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(payload)
                os.replace(temporary, target)
            except Exception:
                if temporary.exists():
                    shutil.rmtree(temporary)
                raise
        return ReleaseProjectionResult(
            release_id=release_id,
            projection_digest=projection_digest,
            path=target,
            revision_count=len(revision_ids),
            search_count=len(search_rows),
            graph_edge_count=len(graph_edges),
            mcp_count=len(mcp_documents),
            download_count=len(downloads),
            html_report_count=len(reports),
            pdf_report_count=len(reports),
        )

    @staticmethod
    def _verify_existing(target: Path, expected: Mapping[str, bytes]) -> None:
        actual = {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }
        if set(actual) != set(expected) or any(actual[name] != payload for name, payload in expected.items()):
            raise ReleaseRebuildError("existing projection conflicts with deterministic rebuild")
