"""Append-only PostgreSQL preparation from native checks and use assessments.

These rows are a disposable preparation, not publication or current authority.
Visibility must join current native/space heads and the current qualification
entry. A seal prevents ordinary SQL from changing or appending to a completed
preparation. No source truth, population coverage or source access is granted.
"""
import json

from ..v2.store import PostgresAgentV2Store
from .knowledge_assertion_set_sql import prepare_assertion
from .knowledge_projection_contract import ProjectionObject,definition_key
from .semantic_binding_contract import semantic_digest


VERSION='boi/prepared-knowledge-postgres@2'
STATEMENT_EXTENSION='boi/prepared-source-statements@1'
PREFIX='boi_prepared_k_'
TABLES=('objects','facts','clauses','atoms','steps','uses','use_facts','dependencies','identity_targets',
        'statement_contexts','statement_grants','seals')


def wire(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


DDL='''
CREATE TABLE IF NOT EXISTS boi_prepared_k_objects(
 store_scope TEXT NOT NULL, preparation TEXT NOT NULL, stable_id TEXT NOT NULL,
 revision TEXT NOT NULL, object_type TEXT NOT NULL, native_payload_digest TEXT NOT NULL,
 content_digest TEXT NOT NULL, source_manifest_digest TEXT NOT NULL, source_policy_digest TEXT NOT NULL,
 adapter_revision TEXT NOT NULL, profile_digest TEXT NOT NULL, preparation_digest TEXT NOT NULL,
 object_wire TEXT NOT NULL, profiles_wire TEXT NOT NULL, PRIMARY KEY(store_scope,preparation));
CREATE INDEX IF NOT EXISTS boi_prepared_k_object_revision ON boi_prepared_k_objects(store_scope,revision,adapter_revision);
CREATE INDEX IF NOT EXISTS boi_prepared_k_object_type ON boi_prepared_k_objects(store_scope,object_type,stable_id,revision);
CREATE TABLE IF NOT EXISTS boi_prepared_k_facts(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,fact_key TEXT NOT NULL,id TEXT NOT NULL,revision TEXT NOT NULL,
 object_type TEXT NOT NULL,predicate TEXT NOT NULL,kind TEXT NOT NULL,text_value TEXT,decimal_value NUMERIC,boolean_value BOOLEAN,
 polarity TEXT NOT NULL,modality TEXT NOT NULL,time_state TEXT NOT NULL,start_at TIMESTAMPTZ,end_at TIMESTAMPTZ,
 time_scope TEXT NOT NULL,unresolved BOOLEAN NOT NULL,adapter_valid BOOLEAN NOT NULL,fact_digest TEXT NOT NULL,meaning_pointer TEXT NOT NULL,
 PRIMARY KEY(store_scope,preparation,fact_key),
 FOREIGN KEY(store_scope,preparation) REFERENCES boi_prepared_k_objects(store_scope,preparation));
CREATE INDEX IF NOT EXISTS boi_prepared_k_fact_decimal ON boi_prepared_k_facts(store_scope,predicate,kind,decimal_value,id);
CREATE INDEX IF NOT EXISTS boi_prepared_k_fact_text ON boi_prepared_k_facts(store_scope,predicate,kind,text_value,id);
CREATE INDEX IF NOT EXISTS boi_prepared_k_fact_boolean ON boi_prepared_k_facts(store_scope,predicate,kind,boolean_value,id);
CREATE INDEX IF NOT EXISTS boi_prepared_k_fact_time ON boi_prepared_k_facts(store_scope,predicate,start_at,end_at,id);
CREATE TABLE IF NOT EXISTS boi_prepared_k_clauses(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,fact_key TEXT NOT NULL,clause_index INT NOT NULL,
 group_kind TEXT NOT NULL,program_length INT NOT NULL,PRIMARY KEY(store_scope,preparation,fact_key,clause_index),
 FOREIGN KEY(store_scope,preparation,fact_key) REFERENCES boi_prepared_k_facts(store_scope,preparation,fact_key));
CREATE TABLE IF NOT EXISTS boi_prepared_k_atoms(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,fact_key TEXT NOT NULL,clause_index INT NOT NULL,atom_index INT NOT NULL,
 subject_ref TEXT NOT NULL,predicate TEXT NOT NULL,op TEXT NOT NULL,kind TEXT NOT NULL,
 text_value TEXT,decimal_value NUMERIC,boolean_value BOOLEAN,known BOOLEAN NOT NULL,
 PRIMARY KEY(store_scope,preparation,fact_key,clause_index,atom_index),
 FOREIGN KEY(store_scope,preparation,fact_key,clause_index) REFERENCES boi_prepared_k_clauses(store_scope,preparation,fact_key,clause_index));
CREATE INDEX IF NOT EXISTS boi_prepared_k_atom_predicate ON boi_prepared_k_atoms(store_scope,subject_ref,predicate,kind);
CREATE TABLE IF NOT EXISTS boi_prepared_k_steps(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,fact_key TEXT NOT NULL,clause_index INT NOT NULL,step INT NOT NULL,
 op TEXT NOT NULL,arity INT NOT NULL,atom_index INT,PRIMARY KEY(store_scope,preparation,fact_key,clause_index,step),
 FOREIGN KEY(store_scope,preparation,fact_key,clause_index) REFERENCES boi_prepared_k_clauses(store_scope,preparation,fact_key,clause_index));
CREATE TABLE IF NOT EXISTS boi_prepared_k_uses(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,purpose TEXT NOT NULL,qualification_key TEXT NOT NULL,
 qualification_ref TEXT NOT NULL,qualification_digest TEXT NOT NULL,payload_digest TEXT NOT NULL,status TEXT NOT NULL,
 policy_digest TEXT NOT NULL,checker_release_digest TEXT NOT NULL,check_key TEXT NOT NULL,check_ref TEXT NOT NULL,
 check_payload_digest TEXT NOT NULL,entry_wire TEXT NOT NULL,qualification_wire TEXT NOT NULL,check_entry_wire TEXT NOT NULL,
 PRIMARY KEY(store_scope,preparation,purpose),
 FOREIGN KEY(store_scope,preparation) REFERENCES boi_prepared_k_objects(store_scope,preparation));
CREATE INDEX IF NOT EXISTS boi_prepared_k_use_key ON boi_prepared_k_uses(store_scope,qualification_key,qualification_ref,purpose);
CREATE TABLE IF NOT EXISTS boi_prepared_k_use_facts(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,purpose TEXT NOT NULL,fact_key TEXT NOT NULL,
 fact_digest TEXT NOT NULL,meaning_pointer TEXT NOT NULL,PRIMARY KEY(store_scope,preparation,purpose,fact_key),
 FOREIGN KEY(store_scope,preparation,purpose) REFERENCES boi_prepared_k_uses(store_scope,preparation,purpose),
 FOREIGN KEY(store_scope,preparation,fact_key) REFERENCES boi_prepared_k_facts(store_scope,preparation,fact_key));
CREATE TABLE IF NOT EXISTS boi_prepared_k_dependencies(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,revision TEXT NOT NULL,stable_id TEXT NOT NULL,
 native_payload_digest TEXT NOT NULL,content_digest TEXT NOT NULL,source_manifest_digest TEXT NOT NULL,policy_digest TEXT NOT NULL,
 PRIMARY KEY(store_scope,preparation,revision),
 FOREIGN KEY(store_scope,preparation) REFERENCES boi_prepared_k_objects(store_scope,preparation));
CREATE INDEX IF NOT EXISTS boi_prepared_k_dependency_revision ON boi_prepared_k_dependencies(store_scope,revision,preparation);
CREATE TABLE IF NOT EXISTS boi_prepared_k_identity_targets(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,stable_id TEXT NOT NULL,revision TEXT NOT NULL,
 revision_digest TEXT NOT NULL,PRIMARY KEY(store_scope,preparation,stable_id),
 FOREIGN KEY(store_scope,preparation,revision) REFERENCES boi_prepared_k_dependencies(store_scope,preparation,revision));
CREATE INDEX IF NOT EXISTS boi_prepared_k_identity_target ON boi_prepared_k_identity_targets(store_scope,stable_id,revision,preparation);
CREATE TABLE IF NOT EXISTS boi_prepared_k_statement_contexts(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,fact_key TEXT NOT NULL,revision TEXT NOT NULL,
 fact_digest TEXT NOT NULL,context_digest TEXT NOT NULL,owner_scope_digest TEXT NOT NULL,
 time_scope TEXT NOT NULL,unconditional BOOLEAN NOT NULL,context_wire TEXT NOT NULL,
 PRIMARY KEY(store_scope,preparation,fact_key),
 FOREIGN KEY(store_scope,preparation,fact_key) REFERENCES boi_prepared_k_facts(store_scope,preparation,fact_key));
CREATE INDEX IF NOT EXISTS boi_prepared_k_statement_owner ON boi_prepared_k_statement_contexts(
 store_scope,revision,owner_scope_digest,time_scope,context_digest);
CREATE TABLE IF NOT EXISTS boi_prepared_k_statement_grants(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,purpose TEXT NOT NULL,fact_key TEXT NOT NULL,
 fact_digest TEXT NOT NULL,meaning_pointer TEXT NOT NULL,scope_digest TEXT NOT NULL,
 PRIMARY KEY(store_scope,preparation,purpose,fact_key),
 FOREIGN KEY(store_scope,preparation,purpose) REFERENCES boi_prepared_k_uses(store_scope,preparation,purpose),
 FOREIGN KEY(store_scope,preparation,fact_key) REFERENCES boi_prepared_k_statement_contexts(store_scope,preparation,fact_key));
CREATE TABLE IF NOT EXISTS boi_prepared_k_seals(
 store_scope TEXT NOT NULL,preparation TEXT NOT NULL,contract_version TEXT NOT NULL,
 receipt_wire TEXT NOT NULL,receipt_digest TEXT NOT NULL,PRIMARY KEY(store_scope,preparation),
 FOREIGN KEY(store_scope,preparation) REFERENCES boi_prepared_k_objects(store_scope,preparation));
'''


def prepare_statement_rows(*, facts, qualification_records, revision):
    """Add only explicitly bound statement grants; leave old preparations intact.

    Root/qualifier evidence owners are exact source-revision/field pairs. No
    field-coordinate parsing or same-name inference establishes a common owner.
    The context helper preserves native text and dependency order. Rows remain
    ordinary sealed preparation and still require the current-use SQL fence.
    """
    from .knowledge_statement_evidence import reported_statement_context, statement_fact_grants
    contexts, grants = {}, []
    declared = False
    for record, _ in qualification_records:
        payload = record.payload
        declared = declared or 'statement_scope' in payload
        bindings, scope_digest = statement_fact_grants(payload)
        if scope_digest is None:
            continue
        for pointer, digest in bindings.items():
            if pointer not in facts:
                raise ValueError('KNOWLEDGE_PREPARED_STATEMENT_FACT_MISSING')
            fact, row = facts[pointer]
            if digest != semantic_digest(fact):
                raise ValueError('KNOWLEDGE_PREPARED_STATEMENT_FACT_CHANGED')
            context = reported_statement_context(fact)
            fact_key = row.fact[0]
            contexts[fact_key] = (fact_key, revision.ref, digest, context['context_digest'],
                context['owner_scope_digest'], context['time_scope'], context['unconditional'],
                wire(context['context']))
            grants.append((payload['purpose'], fact_key, digest, pointer, scope_digest))
    return declared, [contexts[key] for key in sorted(contexts)], grants


class PostgresKnowledgePreparedStore:
    def __init__(self,store,*,key_prefix='',authority_store=None):
        if not isinstance(store,PostgresAgentV2Store) or not isinstance(key_prefix,str):
            raise ValueError('KNOWLEDGE_PREPARED_POSTGRES_REQUIRED')
        self.store,self.prefix=store,key_prefix
        self.authority_store=store if authority_store is None else authority_store
        self._initialize()

    def _initialize(self):
        with self.store._connection() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('boi/prepared-knowledge-schema@1',0))")
            connection.execute(DDL)
            # A schema-specific function is installed once. Reopening the store
            # never replaces a live trigger or changes already sealed records.
            exists=connection.execute("SELECT to_regprocedure('boi_prepared_k_immutable()')").fetchone()[0]
            if exists is None:
                connection.execute('''CREATE FUNCTION boi_prepared_k_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                  IF TG_OP <> 'INSERT' THEN
                    RAISE EXCEPTION 'KNOWLEDGE_PREPARED_IMMUTABLE';
                  END IF;
                  IF EXISTS (SELECT 1 FROM boi_prepared_k_seals s
                    WHERE s.store_scope=NEW.store_scope AND s.preparation=NEW.preparation) THEN
                    RAISE EXCEPTION 'KNOWLEDGE_PREPARED_SEALED';
                  END IF;
                  RETURN NEW;
                END $$''')
            for name in TABLES:
                table=PREFIX+name
                if not connection.execute('SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',
                    (table,table+'_immutable')).fetchone():
                    connection.execute(f'CREATE TRIGGER {table}_immutable BEFORE INSERT OR UPDATE OR DELETE ON {table} '
                        'FOR EACH ROW EXECUTE FUNCTION boi_prepared_k_immutable()')

    def stage(self,*,projection,registry,native_record,mechanical,qualification_records,read_revision):
        """Called only by the server qualifier after actual source/check validation.

        Commit of the current qualification entry remains the qualifier's atomic
        operation. An interrupted stage or failed later admission grants no use.
        """
        from .knowledge_profile_projector import native_identity
        from .local_knowledge_qualification import qualification_key
        qualification_records = tuple(qualification_records)
        projection=ProjectionObject.model_validate(projection.model_dump(mode='json'))
        if (registry is None or projection.knowledge_revision.ref!=native_record.record_id
                or projection.stable_id!=native_identity(native_record)
                or projection.content_digest!=native_record.payload['content_digest']):
            raise ValueError('KNOWLEDGE_PREPARED_NATIVE_BINDING_MISMATCH')
        profiles=[{'revision':ref.model_dump(mode='json'),'declaration':value.model_dump(mode='json')}
            for ref,value in sorted(registry.profiles.items(),key=lambda item:item[0].ref)]
        prepared=[prepare_assertion(stable_id=projection.stable_id,revision=projection.knowledge_revision,
            object_type=projection.object_type,fact=fact,registry=registry) for fact in projection.facts]
        facts={fact.meaning_pointer:(fact,row) for fact,row in zip(projection.facts,prepared)}
        if len(facts)!=len(projection.facts):raise ValueError('KNOWLEDGE_PREPARED_POINTER_DUPLICATE')
        dependencies=[]
        report=mechanical['report']
        for expected in report['native_inputs']:
            from .semantic_binding_contract import RevisionRef
            record,_=read_revision(RevisionRef.model_validate(expected['revision']))
            value=record.payload
            if (record.record_id!=expected['revision']['ref'] or value['content_digest']!=expected['content_digest']
                    or value['source_manifest_digest']!=expected['source_manifest_digest']):
                raise ValueError('KNOWLEDGE_PREPARED_DEPENDENCY_CHANGED')
            dependencies.append((record.record_id,native_identity(record),semantic_digest(value),
                value['content_digest'],value['source_manifest_digest'],value['policy_digest']))
        if len({d[0] for d in dependencies})!=len(dependencies):
            raise ValueError('KNOWLEDGE_PREPARED_DEPENDENCY_DUPLICATE')
        # Stable-identity references select the current target. Exact revision
        # dependencies may intentionally refer to readable history; these may not.
        from .native_mechanical_records import checked_identity_reference
        identity_targets=[]
        for item in report.get('identity_inputs',[]):
            ref=checked_identity_reference(read_revision,item['stable_id'])
            if (ref.model_dump(mode='json')!=item['revision']
                    or not any(d[0]==ref.ref and d[1]==item['stable_id'] for d in dependencies)):
                raise ValueError('KNOWLEDGE_PREPARED_IDENTITY_TARGET_CHANGED')
            identity_targets.append((item['stable_id'],ref.ref,ref.revision_digest))
        if len({item[0] for item in identity_targets})!=len(identity_targets):
            raise ValueError('KNOWLEDGE_PREPARED_IDENTITY_TARGET_DUPLICATE')
        uses,use_facts=[],[]
        for record,entry in qualification_records:
            entry={key:value for key,value in entry.items() if key!='updated_at'}
            value=record.payload;purpose=value['purpose']
            if (entry['revision']!=projection.knowledge_revision.model_dump(mode='json')
                    or value['knowledge_revision']!=entry['revision'] or value['stable_id']!=projection.stable_id
                    or entry['payload_digest']!=semantic_digest(value) or entry['qualification_ref']['ref']!=record.record_id
                    or value['mechanical_check_ref']!=mechanical['saved']['check_ref']):
                raise ValueError('KNOWLEDGE_PREPARED_QUALIFICATION_BINDING_MISMATCH')
            uses.append((purpose,qualification_key(projection.knowledge_revision,purpose),record.record_id,
                entry['qualification_ref']['revision_digest'],semantic_digest(value),value['status'],
                value['qualification_policy_digest'],value['checker_release_digest'],
                'native-mechanical-execution:'+semantic_digest(mechanical['saved']['input']),
                mechanical['saved']['check_ref']['ref'],mechanical['saved']['payload_digest'],
                wire(entry),wire(value),wire(mechanical['saved'])))
            if value['status']=='usable_with_limits':
                for binding in value['fact_bindings']:
                    fact,row=facts[binding['meaning_pointer']]
                    if binding['meaning_pointer'] not in value['roots'] or binding['fact_digest']!=semantic_digest(fact):
                        raise ValueError('KNOWLEDGE_PREPARED_QUALIFIED_FACT_MISMATCH')
                    use_facts.append((purpose,row.fact[0],binding['fact_digest'],binding['meaning_pointer']))
        content={'contract_version':VERSION,'object':projection.model_dump(mode='json'),'profiles':profiles,
            'native_payload_digest':semantic_digest(native_record.payload),'dependencies':dependencies,
            'identity_targets':identity_targets,
            'uses':uses,'use_facts':use_facts}
        declared, statement_contexts, statement_grants = prepare_statement_rows(
            facts=facts, qualification_records=qualification_records, revision=projection.knowledge_revision)
        if declared:
            # The extension is part of the preparation hash. We never append to
            # an old @2 seal, including a seal made before statement support.
            content['statement_extension'] = {'contract_version':STATEMENT_EXTENSION,
                'contexts':statement_contexts, 'grants':statement_grants}
        preparation=semantic_digest(content)
        rows={'facts':[row.fact for row in prepared],
              'clauses':[x for row in prepared for x in row.clauses],
              'atoms':[x for row in prepared for x in row.atoms],
              'steps':[x for row in prepared for x in row.steps],
              'uses':uses,'use_facts':use_facts,'dependencies':dependencies,'identity_targets':identity_targets}
        if declared:
            rows.update(statement_contexts=statement_contexts, statement_grants=statement_grants)
        receipt={'contract_version':VERSION,'preparation_ref':preparation,
            'native_revision':projection.knowledge_revision.model_dump(mode='json'),
            'counts':{name:len(items) for name,items in rows.items()},'publication_granted':False,
            'current_use_granted':False,'source_access_granted':False}
        if declared:
            receipt['statement_extension'] = STATEMENT_EXTENSION
        native=native_record.payload
        metadata=(projection.stable_id,projection.knowledge_revision.ref,definition_key(projection.object_type),
            semantic_digest(native),projection.content_digest,native['source_manifest_digest'],native['policy_digest'],
            projection.adapter_revision,semantic_digest(profiles),preparation,wire(projection.model_dump(mode='json')),wire(profiles))
        with self.store._connection() as connection,connection.transaction():
            connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(self.prefix+preparation,))
            existing=connection.execute('SELECT receipt_wire,receipt_digest FROM boi_prepared_k_seals WHERE store_scope=%s AND preparation=%s',
                (self.prefix,preparation)).fetchone()
            if existing:
                if existing!=(wire(receipt),semantic_digest(receipt)):
                    raise ValueError('KNOWLEDGE_PREPARED_RECEIPT_CONFLICT')
                return receipt
            connection.execute('INSERT INTO boi_prepared_k_objects VALUES('+','.join(['%s']*14)+')',
                (self.prefix,preparation,*metadata))
            with connection.cursor() as cursor:
                for name,items in rows.items():
                    if items:cursor.executemany('INSERT INTO '+PREFIX+name+' VALUES('+','.join(['%s']*(len(items[0])+2))+')',
                        [(self.prefix,preparation,*item) for item in items])
            connection.execute('INSERT INTO boi_prepared_k_seals VALUES(%s,%s,%s,%s,%s)',
                (self.prefix,preparation,VERSION,wire(receipt),semantic_digest(receipt)))
        return receipt
