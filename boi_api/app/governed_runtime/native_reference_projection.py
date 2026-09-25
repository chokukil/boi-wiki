"""Exact declared native references, prepared with the publication index.

These are dependency/conflict/supersession declarations, not inferred domain
relations or semantic impact verdicts. The ledger remains their authority.
"""
import json

from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest

VERSION = 'boi/native-reference-projection@1'
FINGERPRINT_FUNCTION = 'boi_native_reference_fingerprint_v1'
FINGERPRINT_BODY = """BEGIN
 NEW.native_reference_digest := 'sha256:' || encode(sha256(convert_to(NEW.payload->>'reference_projection_wire','UTF8')),'hex');
 RETURN NEW;
END"""


def install_reference_index(cursor, table):
    # Installed at store schema initialization, before new native publications.
    # Existing legacy rows are not reinterpreted or silently backfilled.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/reference-index@1',0))")
    cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS native_reference_digest TEXT')
    if cursor.execute('SELECT to_regprocedure(%s)',(FINGERPRINT_FUNCTION+'()',)).fetchone()[0] is None:
        cursor.execute(f'CREATE FUNCTION {FINGERPRINT_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$'+FINGERPRINT_BODY+'$$')
    if not cursor.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
            (table,FINGERPRINT_FUNCTION)).fetchone():
        cursor.execute(f'CREATE TRIGGER {FINGERPRINT_FUNCTION} BEFORE INSERT OR UPDATE ON {table} '
            f'FOR EACH ROW EXECUTE FUNCTION {FINGERPRINT_FUNCTION}()')
    cursor.execute(f'''CREATE INDEX IF NOT EXISTS boi_native_reference_targets_v1 ON {table}
 USING gin (((payload->>'reference_projection_wire')::jsonb) jsonb_path_ops)''')
    reference_index_ready(cursor,table)


def reference_index_ready(connection, table):
    row=connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',
        (FINGERPRINT_FUNCTION+'()',)).fetchone()
    trigger=connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgqual IS NULL '
        'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
        (FINGERPRINT_FUNCTION+'()',table,FINGERPRINT_FUNCTION)).fetchone()
    if row!=(FINGERPRINT_BODY,'v',False) or trigger not in (('O',23,True,True),('A',23,True,True)):
        raise ValueError('KNOWLEDGE_REFERENCE_INDEX_UNAVAILABLE')


def reference_projection(record):
    payload = record.payload
    edges = []
    for index, dependency in enumerate(payload['dependencies']):
        edges.append({'kind':'dependency','pointer':f'/dependencies/{index}',
            'target':dependency['revision'],'role':dependency['role'],
            'required':dependency.get('required',True),'reason':dependency['reason'],
            'stages':dependency['stages']})
    for key, kind in (('conflicts_with','declared_conflict'),('supersedes','supersedes')):
        for index, target in enumerate(payload[key]):
            edges.append({'kind':kind,'pointer':f'/{key}/{index}','target':target})
    wire = json.dumps({'contract_version':VERSION,'record_payload_digest':semantic_digest(payload),
        'edges':edges},ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    return {'reference_projection_wire':wire,'reference_projection_digest':byte_digest(wire.encode())}
