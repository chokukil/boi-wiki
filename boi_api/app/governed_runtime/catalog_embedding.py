"""Native catalog embeddings using the existing prepared-vector cache.

Only explicitly configured embedding transport is used. No answer model,
profile executor, semantic router, new store, or query-side document indexing.
"""
import json
import os
from functools import lru_cache
from pathlib import Path
from urllib import request
from urllib.parse import urlsplit

from .local_embedding_client import PreparedEmbeddingClient
from .semantic_profile_retrieval import RetrievalDocument

PROJECTION = 'boi/catalog-embedding@1'
CHUNK_CHARACTERS = 2000


@lru_cache(maxsize=8)
def _client(base_url, model, revision, dimensions, api_key, cache_path):
    parsed = urlsplit(base_url)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.hostname.endswith('.example') or not revision):
        raise ValueError('DOMAIN_EMBEDDING_CONFIGURATION_INVALID')

    def transport(url, payload, timeout):
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        call = request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                               headers=headers, method='POST')
        with request.urlopen(call, timeout=timeout) as response:  # noqa: S310
            value = json.loads(response.read().decode())
        if not isinstance(value, dict):
            raise ValueError('DOMAIN_EMBEDDING_RESPONSE_INVALID')
        return value

    return PreparedEmbeddingClient(base_url=base_url, model_id=model,
        model_digest=revision, dimensions=dimensions, transport=transport,
        cache_path=cache_path, timeout_seconds=30, cache_queries=True)


def configured_client():
    if os.getenv('BOI_NATIVE_EMBEDDING_ENABLED', '').lower() not in ('1', 'true'):
        return None
    if os.getenv('BOI_EMBEDDING_PROVIDER') not in ('openai', 'openai_compatible'):
        raise ValueError('DOMAIN_EMBEDDING_PROVIDER_UNSUPPORTED')
    path = os.getenv('BOI_LOCAL_EMBEDDING_CACHE_PATH') or str(
        Path(os.getenv('XDG_CACHE_HOME') or Path.home() / '.cache') /
        'boi-wiki-governed' / 'logical-vectors-v1.sqlite3')
    return _client(os.getenv('BOI_EMBEDDING_BASE_URL', ''), os.getenv('BOI_EMBEDDING_MODEL', ''),
        os.getenv('BOI_NATIVE_EMBEDDING_REVISION', ''), int(os.getenv('BOI_EMBEDDING_DIMENSIONS', '0')),
        os.getenv('BOI_EMBEDDING_API_KEY', ''), path)


def prepare_entry(client, head_key, record, summary):
    """Publication/maintenance only; exact declared owners, with no inference.

    Character chunks preserve every declared value without silent truncation.
    Chunk pointers remain discovery metadata, not evidence or applicability.
    """
    if summary['catalog_purpose'] != 'knowledge':
        return {'state': 'not_applicable', 'chunks': []}
    if client is None:
        return {'state': 'not_connected', 'chunks': []}
    texts = [('', record.payload['title'] + '\n' + record.payload['description'])]
    texts.extend((entry['node']['target_pointer'],
                  json.dumps(entry['node']['value'], ensure_ascii=False, sort_keys=True))
                 for entry in summary['meaning_search'])
    documents, chunks = [], []
    for pointer, text in texts:
        for part, offset in enumerate(range(0, len(text), CHUNK_CHARACTERS)):
            identity = json.dumps([head_key, pointer, part], separators=(',', ':'))
            document = RetrievalDocument(entry_id=identity, kind=PROJECTION,
                revision_digest=record.record_id, search_text=text[offset:offset + CHUNK_CHARACTERS])
            documents.append(document)
            chunks.append({'key': client.prepared_key(document), 'pointer': pointer, 'part': part})
    value = {'contract_version': PROJECTION, 'identity': client.identity_digest,
             'chunks': chunks, 'scope': 'title_description_and_declared_meaning_values'}
    try:
        report = client.index_documents(tuple(documents))
    except Exception:
        # A failed embedding never erases the committed revision/lexical index.
        # Any validated partial vectors stay cached for explicit maintenance.
        return {**value, 'state': 'deferred', 'reason_code': 'DOMAIN_EMBEDDING_PREPARATION_FAILED'}
    return {**value, 'state': 'prepared', 'preparation': report}
