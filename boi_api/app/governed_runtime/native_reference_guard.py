"""Transactional write guards for reference observations and publication CAS.

Guard rows sort before native writes in the shared CAS lock order. Ordinary
tracked writes update them in the same transaction, including writers which do
not maintain application-level space epochs. This is not a semantic verifier.
"""
from ..v2.atomic_store_contract import AtomicWrite

GUARDS = 'atomic_knowledge_reference_guards'
FUNCTION = 'boi_reference_scope_guard_v1'
TRIGGER = 'boi_reference_scope_guard_v1'
COLLECTIONS = ('domain_asset_heads','domain_knowledge_assets','knowledge_space_heads',
               'knowledge_space_entries','knowledge_publication_receipts')
ENTRY_SUFFIX = len('knowledge-space-entry:sha256:') + 64
ENTRY_PATTERN = '^knowledge-space-entry:sha256:[0-9a-f]{64}$'


def body(store):
    entries,guards=store._table('knowledge_space_entries'),store._table(GUARDS)
    return f'''
DECLARE changed jsonb; records jsonb; entry record; prefix text; guard_key text; partition_key text;
BEGIN
 IF TG_OP='UPDATE' AND OLD.item_key IS NOT DISTINCT FROM NEW.item_key
   AND OLD.employee_id IS NOT DISTINCT FROM NEW.employee_id AND OLD.payload IS NOT DISTINCT FROM NEW.payload THEN
   RETURN NULL;
 END IF;
 records := CASE TG_OP WHEN 'INSERT' THEN jsonb_build_array(to_jsonb(NEW))
   WHEN 'DELETE' THEN jsonb_build_array(to_jsonb(OLD)) ELSE jsonb_build_array(to_jsonb(OLD),to_jsonb(NEW)) END;
 FOR changed IN SELECT value FROM jsonb_array_elements(records) LOOP
   IF TG_ARGV[0]='knowledge_publication_receipts' THEN
     IF right(changed->>'item_key',71) ~ '^sha256:[0-9a-f]{{64}}$' THEN
       guard_key := left(changed->>'item_key',-71)||'reference-guard:receipts';
       INSERT INTO {guards}(item_key,employee_id,payload) VALUES(guard_key,'receipts',
         jsonb_build_object('employee_id','receipts','change_xid',pg_current_xact_id()::text))
       ON CONFLICT(item_key) DO UPDATE SET payload=EXCLUDED.payload,updated_at=NOW();
     END IF;
   ELSIF TG_ARGV[0]='knowledge_space_entries' THEN
     IF right(changed->>'item_key',{ENTRY_SUFFIX}) ~ '{ENTRY_PATTERN}' THEN
       prefix := left(changed->>'item_key',-{ENTRY_SUFFIX}); partition_key := changed->>'employee_id';
       guard_key := prefix||'reference-guard:'||partition_key;
       INSERT INTO {guards}(item_key,employee_id,payload) VALUES(guard_key,partition_key,
         jsonb_build_object('employee_id',partition_key,'change_xid',pg_current_xact_id()::text))
       ON CONFLICT(item_key) DO UPDATE SET payload=EXCLUDED.payload,updated_at=NOW();
     END IF;
   ELSE
     FOR entry IN
       SELECT DISTINCT left(e.item_key,-{ENTRY_SUFFIX}) AS prefix,e.employee_id AS partition_key
       FROM {entries} e WHERE right(e.item_key,{ENTRY_SUFFIX}) ~ '{ENTRY_PATTERN}' AND (
         (TG_ARGV[0] IN ('domain_asset_heads','knowledge_space_heads') AND
           left(e.item_key,-{ENTRY_SUFFIX})||(e.payload->>'stable_id')=changed->>'item_key') OR
         (TG_ARGV[0]='domain_knowledge_assets' AND
           left(e.item_key,-{ENTRY_SUFFIX})||(e.payload->'content_revision'->>'ref')=changed->>'item_key'))
       ORDER BY 1,2
     LOOP
       guard_key := entry.prefix||'reference-guard:'||entry.partition_key;
       INSERT INTO {guards}(item_key,employee_id,payload) VALUES(guard_key,entry.partition_key,
         jsonb_build_object('employee_id',entry.partition_key,'change_xid',pg_current_xact_id()::text))
       ON CONFLICT(item_key) DO UPDATE SET payload=EXCLUDED.payload,updated_at=NOW();
     END LOOP;
   END IF;
 END LOOP;
 RETURN NULL;
END
'''


def install_reference_guard(connection,store):
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/reference-guard@1',0))")
    entries=store._table('knowledge_space_entries')
    for name,expression in (('head',"payload->>'stable_id'"),('revision',"payload->'content_revision'->>'ref'")):
        connection.execute(f'CREATE INDEX IF NOT EXISTS boi_reference_guard_{name}_v1 ON {entries} '
            f"((left(item_key,-{ENTRY_SUFFIX})||({expression}))) WHERE right(item_key,{ENTRY_SUFFIX}) ~ '{ENTRY_PATTERN}'")
    if connection.execute('SELECT to_regprocedure(%s)',(FUNCTION+'()',)).fetchone()[0] is None:
        connection.execute(f'CREATE FUNCTION {FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$'+body(store)+'$$')
    for collection in COLLECTIONS:
        table=store._table(collection)
        if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(table,TRIGGER)).fetchone():
            connection.execute(f'CREATE TRIGGER {TRIGGER} AFTER INSERT OR UPDATE OR DELETE ON {table} '
                f"FOR EACH ROW EXECUTE FUNCTION {FUNCTION}('{collection}')")
    reference_guard_ready(connection,store)


def reference_guard_ready(connection,store):
    row=connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',(FUNCTION+'()',)).fetchone()
    if row!=(body(store),'v',False):
        raise ValueError('KNOWLEDGE_REFERENCE_GUARD_UNAVAILABLE')
    for collection in COLLECTIONS:
        trigger=connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgargs,tgqual IS NULL '
            'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
            (FUNCTION+'()',store._table(collection),TRIGGER)).fetchone()
        if trigger not in ((enabled,29,True,(collection+'\x00').encode(),True) for enabled in ('O','A')):
            raise ValueError('KNOWLEDGE_REFERENCE_GUARD_UNAVAILABLE')


def reference_guard_fences(index,bindings):
    keys={'reference-guard:receipts':'receipts',
        **{'reference-guard:'+b['partition']:b['partition'] for b in bindings}}
    authority=index.backend.authority_store
    with index.store._connection() as connection:
        reference_guard_ready(connection,index.store)
    rows=authority.get_many(GUARDS,tuple(keys))
    missing=[AtomicWrite(GUARDS,key,None,{'employee_id':partition,'change_xid':'0'})
        for key,partition in keys.items() if key not in rows]
    if missing:
        if not authority.atomic_compare_and_write(missing):
            raise ValueError('KNOWLEDGE_REFERENCE_GUARD_CHANGED')
        rows=authority.get_many(GUARDS,tuple(keys))
    return tuple(AtomicWrite(GUARDS,key,rows[key],rows[key]) for key in sorted(keys))
