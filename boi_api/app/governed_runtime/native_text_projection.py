"""Disposable lexical document index, atomically bound to native publication.

Source files are not read or granted by this index. Document text and metadata
stay distinct from qualified predicates, domain identity and semantic selection.
"""
import json
import unicodedata

from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest

COLLECTION = 'knowledge_text_projections'
VERSION = 'boi/native-text-projection@1'
FUNCTION = 'boi_native_text_fingerprint_v1'
DENY = 'boi_native_text_no_truncate_v1'
BODY = """BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'KNOWLEDGE_TEXT_PROJECTION_IMMUTABLE'; END IF;
 IF TG_OP='UPDATE' AND (OLD.item_key IS DISTINCT FROM NEW.item_key OR
    OLD.employee_id IS DISTINCT FROM NEW.employee_id OR
    OLD.payload->>'wire' IS DISTINCT FROM NEW.payload->>'wire') THEN
   RAISE EXCEPTION 'KNOWLEDGE_TEXT_PROJECTION_IMMUTABLE';
 END IF;
 NEW.text_digest := 'sha256:' || encode(sha256(convert_to(NEW.payload->>'wire','UTF8')),'hex');
 NEW.text_normalized := (NEW.payload->>'wire')::jsonb->>'normalized';
 NEW.text_grams := (NEW.payload->>'wire')::jsonb->'grams';
 RETURN NEW;
END"""
DENY_BODY = "BEGIN RAISE EXCEPTION 'KNOWLEDGE_TEXT_PROJECTION_IMMUTABLE'; END"


def normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def grams(text):
    # All lengths include short Korean and identifier searches. These are
    # character candidates, never acronym expansions or domain routing rules.
    return sorted({text[i:i+n] for n in (1,2,3) for i in range(len(text)-n+1)})


def projection(record, draft):
    content = json.loads(draft.content_json)
    body, representation = '', 'metadata_only'
    if isinstance(content, dict) and content.get('contract_version') == 'boi/knowledge-content@1':
        body = content['document']['body']; representation = 'document_body'
    elif isinstance(content, dict) and content.get('contract_version') == 'boi/knowledge-profile@1':
        body = content['label'] + '\n\n' + content['description']; representation = 'profile_overview'
    text = normalized(draft.title + '\n' + draft.description + '\n' + body)
    value = {'contract_version': VERSION, 'revision': record.record_id,
             'record_payload_digest': semantic_digest(record.payload),
             'content_object_ref': record.payload['content_object_ref'],
             'title': draft.title, 'description': draft.description, 'body': body,
             'normalized': text, 'grams': grams(text), 'representation': representation}
    wire = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return {'employee_id': record.payload['employee_id'], 'wire': wire}, byte_digest(wire.encode())


def install_text_index(cursor, table):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/text-index@1',0))")
    cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS text_digest TEXT')
    cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS text_normalized TEXT')
    cursor.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS text_grams JSONB')
    for name, body in ((FUNCTION,BODY),(DENY,DENY_BODY)):
        if cursor.execute('SELECT to_regprocedure(%s)',(name+'()',)).fetchone()[0] is None:
            cursor.execute(f'CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$'+body+'$$')
    for name, timing in ((FUNCTION,'BEFORE INSERT OR UPDATE OR DELETE'), (DENY,'BEFORE TRUNCATE')):
        if not cursor.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
                              (table,name)).fetchone():
            level='ROW' if name==FUNCTION else 'STATEMENT'
            cursor.execute(f'CREATE TRIGGER {name} {timing} ON {table} FOR EACH {level} EXECUTE FUNCTION {name}()')
    cursor.execute(f"CREATE INDEX IF NOT EXISTS boi_native_text_grams_v1 ON {table} USING gin (text_grams jsonb_path_ops)")
    text_index_ready(cursor,table)


def text_index_ready(connection, table):
    for name,body,kind in ((FUNCTION,BODY,31),(DENY,DENY_BODY,34)):
        row=connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',
                               (name+'()',)).fetchone()
        trigger=connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgqual IS NULL '
            'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(name+'()',table,name)).fetchone()
        if row!=(body,'v',False) or trigger not in (('O',kind,True,True),('A',kind,True,True)):
            raise ValueError('KNOWLEDGE_TEXT_INDEX_UNAVAILABLE')
