"""Synthetic helper closure for focused MCP release validation."""
import sqlite3


from boi_api.app.governed_runtime.multi_result_query_gateway import (
    AuthorizedPhysicalMapping, MultiResultExploratoryExecutionRequest, MultiResultSqliteGateway,
    capture_multi_result_sqlite_schema, create_multi_result_logical_plan, validate_multi_result_plan_authority,
)


from tests.test_scalar_aggregate_gateway import scalar, native_authority, SHA


def setup(tmp_path):
    path=tmp_path/'source.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE records (id TEXT)')
        db.executemany('INSERT INTO records VALUES (?)',[(None,),('x',),('x',)])
    schema=capture_multi_result_sqlite_schema(path,allowed_tables=('records',))
    authority=native_authority(schema.source_snapshot_digest)
    mappings=(AuthorizedPhysicalMapping(mapping_ref='mapping:id',source_id='source:test',table='records',column='id',revision_digest=SHA),)
    def request(reducer):
        result=scalar(aggregations=({'reducer':reducer,'mapping_ref':'mapping:id','column':'id','output_name':'answer'},))
        plan=create_multi_result_logical_plan(shape_solver_outcome_digest=SHA,profile_contract_binding_digest=SHA,
            active_release_digest=None,candidate_authority=authority,domain_profile_digest=SHA,mapping_profile_digest=SHA,
            query_profile_digest=SHA,schema_digest=schema.schema_digest,result_sets=(result,),parameter_specs=(),quality_receipt_digests=())
        validation=validate_multi_result_plan_authority(plan,physical_mappings=mappings,selected_relationship_ids=())
        return MultiResultExploratoryExecutionRequest(lane='exploratory',logical_plan=plan,validation_receipt=validation,
            physical_mappings=mappings,selected_relationship_ids=(),quality_receipts=(),parameters={},
            principal=authority.principal,purpose=authority.purpose,idempotency_key=reducer,inline_row_limit=1,timeout_seconds=10)
    current={'allowed':True,'calls':0}
    def resolve(access):
        current['calls']+=1
        if not current['allowed']:raise ValueError('CURRENT_SCOPE_REVOKED')
        return authority
    gateway=MultiResultSqliteGateway(path,schema=schema,result_artifact_root=tmp_path/'results',reviewed_authority_resolver=resolve)
    return gateway,request,current
