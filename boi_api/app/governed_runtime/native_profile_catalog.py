"""Data-declared Profile candidates prepared at native publication.

Token overlap retrieves candidates only. Role, units and identity are never
inferred from words, and this index grants no fact/use qualification.
"""
import json
import re
import unicodedata

from .knowledge_profile import KnowledgeProfileDeclaration, ObjectTypeDeclaration, PredicateDeclaration, LocalType
from .knowledge_projection_contract import ProjectionComponent, ProjectionRevision
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest

VERSION='boi/native-profile-catalog@1'
META='boi_native_profile_catalog_v1'
COMPONENTS='boi_native_profile_components_v1'
FINGERPRINT='boi_native_profile_fingerprint_v1'
LEGACY_DERIVE='boi_native_profile_derive_v1'
DERIVE='boi_native_profile_derive_v2'
GUARD='boi_native_profile_guard_v1'
FINGERPRINT_BODY="""BEGIN
 NEW.native_profile_digest := 'sha256:' || encode(sha256(convert_to(NEW.payload->>'profile_components_wire','UTF8')),'hex');
 RETURN NEW;
END"""
GUARD_BODY="""BEGIN
 IF TG_OP='TRUNCATE' OR pg_trigger_depth()<2 THEN
   RAISE EXCEPTION 'KNOWLEDGE_PROFILE_DERIVED_WRITE_DENIED';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END"""
LEGACY_DERIVE_BODY=f"""DECLARE wire jsonb;
BEGIN
 IF TG_OP='UPDATE' AND OLD.item_key=NEW.item_key
   AND OLD.payload->>'profile_components_wire' IS NOT DISTINCT FROM NEW.payload->>'profile_components_wire' THEN
   RETURN NULL;
 END IF;
 IF TG_OP IN ('UPDATE','DELETE') THEN DELETE FROM {META} WHERE asset_key=OLD.item_key; END IF;
 IF TG_OP='DELETE' THEN RETURN NULL; END IF;
 wire := (NEW.payload->>'profile_components_wire')::jsonb;
 IF wire IS NULL THEN RETURN NULL; END IF;
 IF wire->>'contract_version'<>'{VERSION}' OR jsonb_typeof(wire->'components')<>'array'
    OR jsonb_array_length(wire->'components') NOT BETWEEN 1 AND 1000 THEN
   RAISE EXCEPTION 'KNOWLEDGE_PROFILE_CATALOG_WIRE_INVALID';
 END IF;
 INSERT INTO {META}(asset_key,digest,revision,payload_digest,info,component_count)
 VALUES(NEW.item_key,NEW.native_profile_digest,wire->'revision',wire->>'record_payload_digest',
        wire->'profile',jsonb_array_length(wire->'components'));
 INSERT INTO {COMPONENTS}(asset_key,position,kind,role,value_kind,subject_type,component,tokens)
 SELECT NEW.item_key,(n-1)::int,c->'declaration'->>'kind',c->'declaration'->>'role',
   c->'declaration'->>'value_kind',c->'subject_type',c-'tokens',
   ARRAY(SELECT jsonb_array_elements_text(c->'tokens'))
 FROM jsonb_array_elements(wire->'components') WITH ORDINALITY AS parts(c,n);
 RETURN NULL;
END"""
DERIVE_BODY=LEGACY_DERIVE_BODY.replace(
    "NEW.payload->>'profile_components_wire' THEN",
    "NEW.payload->>'profile_components_wire'\n"
    "   AND OLD.payload->>'profile_repair_ref' IS NOT DISTINCT FROM NEW.payload->>'profile_repair_ref' THEN")


def tokens(text):
    # Unicode normalization and lexical boundaries only, no domain routing or
    # synonym/role/unit inference. Korean morphology and typo recall need eval.
    return sorted(set(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold())))


def profile_projection(record,draft):
    if draft.kind!='profile':
        return {}
    content=json.loads(draft.content_json)
    if not isinstance(content,dict) or content.get('contract_version')!='boi/knowledge-profile@1':
        return {'profile_component_state':'unsupported_contract'}
    profile=KnowledgeProfileDeclaration.model_validate(content)
    revision=ProjectionRevision(ref=record.record_id,revision_digest=record.record_id.removeprefix('KnowledgeRevision:'))
    local={c.id:ProjectionComponent(revision=revision,pointer=f'/components/{i}')
        for i,c in enumerate(profile.components) if isinstance(c,ObjectTypeDeclaration)}
    def resolve(link):
        if isinstance(link,LocalType):
            if link.component_id not in local:raise ValueError('KNOWLEDGE_PROFILE_LOCAL_TYPE_MISSING')
            link=local[link.component_id]
        return link.model_dump(mode='json') if link is not None else None
    components=[]
    for i,declaration in enumerate(profile.components):
        predicate=isinstance(declaration,PredicateDeclaration)
        components.append({'reference':ProjectionComponent(revision=revision,pointer=f'/components/{i}').model_dump(mode='json'),
            'declaration':declaration.model_dump(mode='json'),
            'subject_type':resolve(declaration.subject_type) if predicate else None,
            'target_type':resolve(declaration.target_type) if predicate else None,
            'tokens':tokens(' '.join([declaration.id,declaration.label,declaration.description,
                declaration.role if predicate else '',profile.profile_id,profile.label]))})
    value={'contract_version':VERSION,'revision':revision.model_dump(mode='json'),
        'record_payload_digest':semantic_digest(record.payload),
        'profile':profile.model_dump(mode='json',exclude={'components'}),'components':components}
    wire=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(wire.encode())>16*1024*1024:raise ValueError('KNOWLEDGE_PROFILE_CATALOG_BYTE_LIMIT')
    return {'profile_component_state':'prepared','profile_components_wire':wire,
        'profile_components_digest':byte_digest(wire.encode())}


def catalog_triggers(table):
    return ((table,FINGERPRINT,FINGERPRINT,23),(table,DERIVE,DERIVE,29),
        *((target,target+'_guard',GUARD,31) for target in (META,COMPONENTS)),
        *((target,target+'_no_truncate',GUARD,34) for target in (META,COMPONENTS)))


def install_profile_catalog(connection,table):
    # Store initialization passes a cursor; maintenance may pass a connection.
    # Keep version migration and schema checks in one transaction in both cases.
    database=getattr(connection,'connection',connection)
    with database.transaction():
        _install_profile_catalog(connection,table)


def _install_profile_catalog(connection,table):
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/profile-catalog@1',0))")
    connection.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS native_profile_digest TEXT')
    connection.execute(f'''CREATE TABLE IF NOT EXISTS {META}(
 asset_key TEXT PRIMARY KEY,digest TEXT NOT NULL,revision JSONB NOT NULL,payload_digest TEXT NOT NULL,
 info JSONB NOT NULL,component_count INTEGER NOT NULL CHECK(component_count BETWEEN 1 AND 1000));
 CREATE TABLE IF NOT EXISTS {COMPONENTS}(
 asset_key TEXT NOT NULL REFERENCES {META}(asset_key) ON DELETE CASCADE,position INTEGER NOT NULL,
 kind TEXT NOT NULL,role TEXT,value_kind TEXT,subject_type JSONB,component JSONB NOT NULL,tokens TEXT[] NOT NULL,
 PRIMARY KEY(asset_key,position));
 CREATE INDEX IF NOT EXISTS boi_profile_tokens_v1 ON {COMPONENTS} USING gin(tokens);
 CREATE INDEX IF NOT EXISTS boi_profile_kind_v1 ON {COMPONENTS}(kind,asset_key,position);
 CREATE INDEX IF NOT EXISTS boi_profile_role_v1 ON {COMPONENTS}(role,asset_key,position);
 CREATE INDEX IF NOT EXISTS boi_profile_subject_v1 ON {COMPONENTS}(subject_type,asset_key,position);''')
    for name,body in ((FINGERPRINT,FINGERPRINT_BODY),(DERIVE,DERIVE_BODY),(GUARD,GUARD_BODY)):
        if connection.execute('SELECT to_regprocedure(%s)',(name+'()',)).fetchone()[0] is None:
            connection.execute(f'CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$'+body+'$$')
    legacy=connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgqual IS NULL,tgargs '
        'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
        (LEGACY_DERIVE+'()',table,LEGACY_DERIVE)).fetchone() if connection.execute(
            'SELECT to_regprocedure(%s)',(LEGACY_DERIVE+'()',)).fetchone()[0] else None
    if legacy is not None:
        old_function=connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc '
            'WHERE oid=to_regprocedure(%s)',(LEGACY_DERIVE+'()',)).fetchone()
        if old_function!=(LEGACY_DERIVE_BODY,'v',False) or legacy not in (
                ('O',29,True,True,b''),('A',29,True,True,b'')):
            raise ValueError('KNOWLEDGE_PROFILE_CATALOG_LEGACY_CHANGED')
        # The old function and source remain available; only its verified
        # attachment is replaced atomically by the new trigger below.
        connection.execute(f'DROP TRIGGER {LEGACY_DERIVE} ON {table}')
    for target,name,function,kind in catalog_triggers(table):
        if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(target,name)).fetchone():
            timing={23:'BEFORE INSERT OR UPDATE',29:'AFTER INSERT OR UPDATE OR DELETE',
                31:'BEFORE INSERT OR UPDATE OR DELETE',34:'BEFORE TRUNCATE'}[kind]
            mode='STATEMENT' if kind==34 else 'ROW'
            connection.execute(f'CREATE TRIGGER {name} {timing} ON {target} FOR EACH {mode} EXECUTE FUNCTION {function}()')
    profile_catalog_ready(connection,table)


def profile_catalog_ready(connection,table):
    if connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
            (table,LEGACY_DERIVE)).fetchone():
        raise ValueError('KNOWLEDGE_PROFILE_CATALOG_LEGACY_ATTACHED')
    for name,body in ((FINGERPRINT,FINGERPRINT_BODY),(DERIVE,DERIVE_BODY),(GUARD,GUARD_BODY)):
        if connection.execute('SELECT prosrc,provolatile,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',
                (name+'()',)).fetchone()!=(body,'v',False):
            raise ValueError('KNOWLEDGE_PROFILE_CATALOG_UNAVAILABLE')
    for target,name,function,kind in catalog_triggers(table):
        row=connection.execute('SELECT tgenabled,tgtype,tgfoid=%s::regprocedure,tgqual IS NULL,tgargs '
            'FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(function+'()',target,name)).fetchone()
        if row not in tuple((enabled,kind,True,True,b'') for enabled in ('O','A')):
            raise ValueError('KNOWLEDGE_PROFILE_CATALOG_UNAVAILABLE')
