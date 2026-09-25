"""Exact content/meaning contract metadata prepared at native publication.

The outer envelope and its declared inner meaning are separate identifiers.
This disposable projection grants neither source access nor use qualification.
"""
import json

from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest

VERSION = 'boi/native-contract-catalog@1'
FUNCTION = 'boi_native_contract_fingerprint_v1'
INDEXES = {
    'boi_native_content_contract_v1': 'native_content_contract_key',
    'boi_native_meaning_contract_v1': 'native_meaning_contract_key',
}
BODY = f"""DECLARE wire jsonb;
BEGIN
 NEW.native_contract_digest := NULL;
 NEW.native_content_contract := NULL;
 NEW.native_meaning_contract := NULL;
 NEW.native_content_contract_key := NULL;
 NEW.native_meaning_contract_key := NULL;
 IF NEW.payload->>'contract_projection_wire' IS NULL THEN RETURN NEW; END IF;
 wire := (NEW.payload->>'contract_projection_wire')::jsonb;
 IF wire->>'contract_version' IS DISTINCT FROM '{VERSION}'
    OR wire->'revision' IS DISTINCT FROM NEW.payload->'revision'
    OR wire->>'record_payload_digest' IS DISTINCT FROM NEW.payload->>'record_payload_digest'
    OR jsonb_typeof(wire->'content_contract') NOT IN ('string','null')
    OR jsonb_typeof(wire->'meaning_contract') NOT IN ('string','null')
    OR NOT (wire ? 'content_contract' AND wire ? 'meaning_contract') THEN
   RAISE EXCEPTION 'KNOWLEDGE_CONTRACT_PROJECTION_WIRE_INVALID';
 END IF;
 NEW.native_contract_digest := 'sha256:' || encode(sha256(convert_to(NEW.payload->>'contract_projection_wire','UTF8')),'hex');
 IF NEW.native_contract_digest IS DISTINCT FROM NEW.payload->>'contract_projection_digest' THEN
   RAISE EXCEPTION 'KNOWLEDGE_CONTRACT_PROJECTION_DIGEST_CHANGED';
 END IF;
 NEW.native_content_contract := wire->>'content_contract';
 NEW.native_meaning_contract := wire->>'meaning_contract';
 NEW.native_content_contract_key := sha256(convert_to(NEW.native_content_contract,'UTF8'));
 NEW.native_meaning_contract_key := sha256(convert_to(NEW.native_meaning_contract,'UTF8'));
 RETURN NEW;
END"""


def declared_contracts(content):
    """Recognize only the exact OKF wrapper; never infer a domain from text."""
    outer = content.get('contract_version') if isinstance(content, dict) else None
    outer = outer if isinstance(outer, str) else None
    meaning = content.get('meaning') if outer == 'boi/knowledge-content@1' else None
    inner = meaning.get('contract_version') if isinstance(meaning, dict) else None
    return {'content_contract': outer, 'meaning_contract': inner if isinstance(inner, str) else None}


def contract_projection(record, draft):
    revision = {'ref': record.record_id,
                'revision_digest': record.record_id.removeprefix('KnowledgeRevision:')}
    value = {'contract_version': VERSION, 'revision': revision,
             'record_payload_digest': semantic_digest(record.payload),
             'content_object_ref': record.payload['content_object_ref'],
             **declared_contracts(json.loads(draft.content_json))}
    wire = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return {'contract_projection_wire': wire, 'contract_projection_digest': byte_digest(wire.encode())}


def preserve_contract_preparation(row, prior):
    """Reusing a native revision cannot implicitly prepare just its new head."""
    result = dict(row)
    for key in ('contract_projection_wire', 'contract_projection_digest'):
        result.pop(key, None)
        if key in prior:
            result[key] = prior[key]
    return result


def install_contract_catalog(connection, table):
    """Add derived columns/indexes without rewriting old publication payloads."""
    database = getattr(connection, 'connection', connection)
    with database.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/contract-catalog@1',0))")
        for column in ('native_contract_digest', 'native_content_contract', 'native_meaning_contract'):
            connection.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} TEXT')
        for column in INDEXES.values():
            connection.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} BYTEA')
        if connection.execute('SELECT to_regprocedure(%s)', (FUNCTION + '()',)).fetchone()[0] is None:
            connection.execute(f'CREATE FUNCTION {FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$' + BODY + '$$')
        if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
                                  (table, FUNCTION)).fetchone():
            connection.execute(f'CREATE TRIGGER {FUNCTION} BEFORE INSERT OR UPDATE ON {table} '
                               f'FOR EACH ROW EXECUTE FUNCTION {FUNCTION}()')
        for name, column in INDEXES.items():
            connection.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({column},item_key)')
        contract_catalog_ready(connection, table)


def contract_catalog_ready(connection, table):
    function = connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc '
                                  'WHERE oid=to_regprocedure(%s)', (FUNCTION + '()',)).fetchone()
    trigger = connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgqual IS NULL,tgargs '
        'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s', (FUNCTION + '()', table, FUNCTION)).fetchone()
    if function != (BODY, 'v', False) or trigger not in (('O', 23, True, True, b''), ('A', 23, True, True, b'')):
        raise ValueError('KNOWLEDGE_CONTRACT_CATALOG_UNAVAILABLE')
    for name, column in INDEXES.items():
        row = connection.execute('''SELECT i.indisvalid,i.indisready,i.indisunique,
 i.indpred IS NULL,i.indexprs IS NULL,i.indnkeyatts,
 ARRAY(SELECT a.attname::text FROM unnest(i.indkey) WITH ORDINALITY k(n,p)
       JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.n ORDER BY k.p)
 FROM pg_index i WHERE i.indexrelid=to_regclass(%s) AND i.indrelid=%s::regclass''', (name, table)).fetchone()
        if row != (True, True, False, True, True, 2, [column, 'item_key']):
            raise ValueError('KNOWLEDGE_CONTRACT_CATALOG_INDEX_UNAVAILABLE')
