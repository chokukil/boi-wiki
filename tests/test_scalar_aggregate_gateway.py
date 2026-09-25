"""Synthetic Gateway execution regressions; no real Wiki authority is claimed."""
import sqlite3
import pytest
from pydantic import ValidationError
from boi_api.app.governed_runtime.multi_result_query_gateway import (
    MultiResultSetPlan, MultiResultSqliteGateway, MultiResultExploratoryExecutionRequest,
    AuthorizedPhysicalMapping, capture_multi_result_sqlite_schema,
    create_multi_result_logical_plan, validate_multi_result_plan_authority,
    NativeQueryAuthority, ReviewedQueryAccess,
)
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest

SHA = "sha256:" + "a" * 64


def native_authority(snapshot):
    ref=dict(ref="fixture:definition", revision_digest=SHA)
    return NativeQueryAuthority(contract_version="boi/native-query-authority@1",
        principal="synthetic-test", purpose="regression", profile_revision=ref,
        definition_authority=dict(principal="synthetic-test", purpose="regression",
            definition_revisions=(ref,), review_revision=ref, knowledge_reading_ref=ref,
            definition_context_digest=SHA, source_manifest_digest=SHA, acl_policy_digest=SHA),
        planning_outcome_digest=SHA, source_snapshot_digest=snapshot,
        parameter_digest=semantic_digest({}), request_authorization_digest=SHA)


def scalar(**overrides):
    values = dict(result_set_id="result:global", role="SCALAR", object_ref="object:records",
        source_id="source:test", table="records", projections=(),
        aggregations=tuple(dict(reducer=r, mapping_ref="mapping:id", column="id", output_name=n)
            for r,n in [("count_rows", "rows"), ("count", "nonnull"), ("count_distinct", "unique_values")]),
        exact_grain=(), filters=(), parent_link=None, ordering=(),
        completeness_policy="PROVISIONAL_SNAPSHOT", result_row_limit=1)
    values.update(overrides)
    return MultiResultSetPlan.model_validate(values)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("rows,expected", [([], dict(rows=0, nonnull=0, unique_values=0)),
    ([(None,), ("x",), ("x",)], dict(rows=3, nonnull=2, unique_values=1))])
def test_protected_gateway_executes_one_global_row_without_group_by(tmp_path, rows, expected, native):
    path=tmp_path / "input.sqlite"
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE records (id TEXT)')
        db.executemany('INSERT INTO records VALUES (?)', rows)
    schema=capture_multi_result_sqlite_schema(path, allowed_tables=("records",))
    authority=native_authority(schema.source_snapshot_digest) if native else None
    plan=create_multi_result_logical_plan(shape_solver_outcome_digest=SHA,
        profile_contract_binding_digest=SHA, active_release_digest=None if native else SHA,
        candidate_authority=authority,
        domain_profile_digest=SHA, mapping_profile_digest=SHA, query_profile_digest=SHA,
        schema_digest=schema.schema_digest, result_sets=(scalar(),),
        parameter_specs=(), quality_receipt_digests=())
    mappings=(AuthorizedPhysicalMapping(mapping_ref="mapping:id", source_id="source:test",
        table="records", column="id", revision_digest=SHA),)
    validation=validate_multi_result_plan_authority(plan, physical_mappings=mappings, selected_relationship_ids=())
    request=MultiResultExploratoryExecutionRequest(lane="exploratory", logical_plan=plan,
        validation_receipt=validation, physical_mappings=mappings, selected_relationship_ids=(),
        quality_receipts=(), parameters={}, principal="synthetic-test", purpose="regression",
        idempotency_key="global", inline_row_limit=1, timeout_seconds=10)
    gateway=MultiResultSqliteGateway(path, schema=schema, result_artifact_root=tmp_path / "results")
    if native:
        with pytest.raises(ValueError, match="REVIEWED_QUERY_EXECUTION_NOT_AUTHORIZED"):
            gateway.create(request)
        def resolve(access):
            assert access.logical_plan_digest == plan.plan_digest
            assert access.parameter_digest == semantic_digest({})
            return authority
        with gateway.reviewed_access_scope(resolve):
            result=gateway.create(request).result.result_sets[0]
    else:
        result=gateway.create(request).result.result_sets[0]
    assert result.role == "SCALAR"
    assert result.rows == (expected,)


def test_native_access_rejects_changed_parameters_before_resolver():
    with pytest.raises(ValidationError, match="NATIVE_QUERY_PARAMETERS_CHANGED"):
        ReviewedQueryAccess(authority=native_authority(SHA), logical_plan_digest=SHA,
            parameter_digest=semantic_digest({"changed": 1}))


@pytest.mark.parametrize("overrides", [dict(exact_grain=("id",)), dict(result_row_limit=2),
    dict(aggregations=()), dict(row_limit_policy="TRUNCATE"),
    dict(projections=(dict(mapping_ref="mapping:id", column="id", output_name="id"),))])
def test_scalar_rejects_grouping_raw_projections_and_truncation(overrides):
    with pytest.raises(ValidationError):
        scalar(**overrides)
