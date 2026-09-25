"""Deterministic DDL/catalog/SQL observations for candidate-only mappings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlglot import exp, parse_one
from sqlglot.optimizer.scope import Scope, traverse_scope

from .declarative_profile_candidates import (
    DeclarativeProfileCandidatePackage,
    ProfileCandidateDocument,
)
from .semantic_query_planner import PlannerCatalogSnapshot
from .sql_lineage import SourceColumn, analyze_sql_lineage


def _digest(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class UsageObservedBootstrapError(RuntimeError):
    pass


class ObservedPhysicalJoin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    observation_digest: str


class UsageObservedRelationshipCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    domain_ref: str
    authority_basis: str
    physically_validated: bool
    observed_in_sql: bool
    observed_join_digest: str
    candidate_revision_digest: str


class UsageObservedBootstrapReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    contract_schema: str = Field(alias="schema", serialization_alias="schema")
    status: str
    package_digest: str
    sql_resource: str
    sql_content_digest: str
    sql_ast_digest: str
    lineage_unresolved_count: int
    catalog_snapshot_digest: str
    catalog_content_digest: str
    schema_digest: str
    capability_digest: str
    physical_tables: tuple[str, ...]
    observed_joins: tuple[ObservedPhysicalJoin, ...]
    filter_clause_count: int
    ordering_count: int
    aggregation_count: int
    relationship_candidates: tuple[UsageObservedRelationshipCandidate, ...]
    source_roles: tuple[str, ...]
    auto_promoted: bool
    qualification_receipt_id: None
    release_id: None
    active_pointer_transition: bool
    canonical_projection_eligible: bool
    receipt_digest: str


class PhysicalRelationshipCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    status: str
    reason_codes: tuple[str, ...]
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    left_row_count: int
    right_row_count: int
    distinct_right_key_count: int
    join_row_count: int
    orphan_count: int
    fanout_ratio: float
    inputs_digest: str
    evidence_digest: str


class DerivedValidatedMappingCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_id: str
    base_revision_digest: str
    derived_revision_digest: str
    payload_digest: str
    authority_basis: str
    physically_validated: bool
    payload: dict[str, Any]


class PhysicalMappingQualificationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    contract_schema: str = Field(alias="schema", serialization_alias="schema")
    status: str
    base_package_digest: str
    bootstrap_receipt_digest: str
    catalog_snapshot_digest: str
    catalog_content_digest: str
    schema_digest: str
    source_content_digest: str
    checks: tuple[PhysicalRelationshipCheck, ...]
    validation_evidence_digest: str
    derived_candidates: tuple[DerivedValidatedMappingCandidate, ...]
    auto_promoted: bool
    qualification_receipt_id: None
    release_id: None
    active_pointer_transition: bool
    canonical_projection_eligible: bool
    receipt_digest: str


def _projection_for(scope: Scope, name: str) -> exp.Expression | None:
    selections = getattr(scope.expression, "selects", ())
    for selection in selections:
        if selection.alias_or_name == name:
            return selection.this if isinstance(selection, exp.Alias) else selection
    if any(isinstance(selection, exp.Star) for selection in selections):
        return exp.column(name)
    return None


def _resolve_column(
    scope: Scope,
    column: exp.Column,
    *,
    visited: frozenset[tuple[int, str, str]] = frozenset(),
) -> tuple[SourceColumn, ...]:
    qualifier = column.table
    key = (id(scope), qualifier, column.name)
    if key in visited:
        return ()
    visited = visited | {key}
    if qualifier:
        source = scope.sources.get(qualifier)
    elif len(scope.sources) == 1:
        source = next(iter(scope.sources.values()))
    else:
        source = None
    if isinstance(source, exp.Table):
        return (
            SourceColumn(
                catalog=source.catalog or None,
                database=source.db or None,
                table=source.name,
                column=column.name,
            ),
        )
    if not isinstance(source, Scope):
        return ()
    projected = _projection_for(source, column.name)
    if projected is None:
        return ()
    if isinstance(projected, exp.Column):
        if not projected.table and len(source.sources) == 1:
            alias = next(iter(source.sources))
            projected = exp.column(projected.name, table=alias)
        return _resolve_column(source, projected, visited=visited)
    columns = tuple(projected.find_all(exp.Column))
    resolved = {
        item
        for nested in columns
        for item in _resolve_column(source, nested, visited=visited)
    }
    return tuple(sorted(resolved))


def _observed_joins(statement: exp.Expression) -> tuple[ObservedPhysicalJoin, ...]:
    observations: dict[tuple[str, str, str, str], ObservedPhysicalJoin] = {}
    for scope in traverse_scope(statement):
        for join in scope.expression.args.get("joins") or ():
            condition = join.args.get("on")
            if not isinstance(condition, exp.EQ):
                continue
            left_expression = condition.this
            right_expression = condition.expression
            if not isinstance(left_expression, exp.Column) or not isinstance(right_expression, exp.Column):
                continue
            left = _resolve_column(scope, left_expression)
            right = _resolve_column(scope, right_expression)
            if len(left) != 1 or len(right) != 1:
                continue
            key = (left[0].table, left[0].column, right[0].table, right[0].column)
            values = {
                "left_table": key[0],
                "left_column": key[1],
                "right_table": key[2],
                "right_column": key[3],
            }
            observations[key] = ObservedPhysicalJoin(
                **values,
                observation_digest=_digest(values),
            )
    return tuple(observations[key] for key in sorted(observations))


def _physical_endpoint(
    mapping_by_id: dict[str, ProfileCandidateDocument], mapping_id: str
) -> tuple[str, str] | None:
    mapping = mapping_by_id.get(mapping_id)
    if mapping is None:
        return None
    physical = mapping.payload.get("physical")
    if not isinstance(physical, dict):
        return None
    table = str(physical.get("table") or "")
    column = str(physical.get("column") or "")
    return (table, column) if table and column else None


def _catalog_content_digest(catalog: PlannerCatalogSnapshot) -> str:
    return _digest(catalog.model_dump(mode="json", exclude={"snapshot_digest"}))


def _verify_bootstrap_receipt(receipt: UsageObservedBootstrapReceipt) -> str | None:
    expected = _digest(
        receipt.model_dump(mode="json", by_alias=True, exclude={"receipt_digest"})
    )
    if expected != receipt.receipt_digest:
        return "USAGE_OBSERVED_BOOTSTRAP_RECEIPT_DIGEST_INVALID"
    return None


def bootstrap_usage_observed_candidates(
    package: DeclarativeProfileCandidatePackage,
    *,
    sql_resource: str,
    catalog: PlannerCatalogSnapshot,
) -> UsageObservedBootstrapReceipt:
    """Extract observations without granting physical validation or promotion."""

    required_roles = {"sql", "ddl", "catalog_snapshot", "query_history"}
    source_roles = {item.role for item in package.source_receipts}
    if not required_roles <= source_roles:
        raise UsageObservedBootstrapError("BOOTSTRAP_REQUIRED_SOURCE_ROLE_MISSING")
    source = next(
        (item for item in package.source_receipts if item.resource == sql_resource), None
    )
    if source is None or source.role != "sql" or not source.verified:
        raise UsageObservedBootstrapError("BOOTSTRAP_SQL_SOURCE_NOT_VERIFIED")
    if _catalog_content_digest(catalog) != catalog.snapshot_digest:
        raise UsageObservedBootstrapError("CATALOG_SNAPSHOT_CONTENT_DIGEST_INVALID")

    mappings = [item for item in package.documents if item.category == "mapping"]
    schema_digests = {str(item.payload.get("schema_snapshot_digest") or "") for item in mappings}
    if schema_digests != {catalog.schema_digest}:
        raise UsageObservedBootstrapError("PROFILE_CATALOG_SCHEMA_MISMATCH")
    relationship_documents = [
        item
        for item in mappings
        if item.payload.get("relationship_binding") is not None
        and sql_resource in item.evidence_resources
    ]
    for relationship in relationship_documents:
        contract = relationship.payload["relationship_binding"]
        if contract.get("authority_basis") != "usage_observed":
            raise UsageObservedBootstrapError("BOOTSTRAP_RELATION_AUTHORITY_NOT_USAGE_OBSERVED")
        if contract.get("physically_validated") is not False:
            raise UsageObservedBootstrapError("BOOTSTRAP_CANNOT_ACCEPT_PREVALIDATED_RELATION")

    sql = Path(source.local_path).read_text(encoding="utf-8")
    catalog_schema = {
        table.name: {column.name: column.data_type for column in table.columns}
        for catalog_source in catalog.sources
        for table in catalog_source.tables
    }
    lineage = analyze_sql_lineage(sql, dialect="sqlite", schema=catalog_schema)
    statement = parse_one(sql, read="sqlite")
    observed_joins = _observed_joins(statement)
    observed_pairs = {
        frozenset({(item.left_table, item.left_column), (item.right_table, item.right_column)}): item
        for item in observed_joins
    }
    mapping_by_id = {item.entry_id: item for item in mappings}
    candidates: list[UsageObservedRelationshipCandidate] = []
    for relationship in relationship_documents:
        contract = relationship.payload["relationship_binding"]
        left = _physical_endpoint(mapping_by_id, str(contract["left_mapping_ref"]))
        right = _physical_endpoint(mapping_by_id, str(contract["right_mapping_ref"]))
        observed = observed_pairs.get(frozenset({left, right})) if left and right else None
        candidates.append(UsageObservedRelationshipCandidate(
            mapping_id=relationship.entry_id,
            domain_ref=str(relationship.payload["domain_ref"]),
            authority_basis="usage_observed",
            physically_validated=False,
            observed_in_sql=observed is not None,
            observed_join_digest=(observed.observation_digest if observed else _digest({"missing": relationship.entry_id})),
            candidate_revision_digest=relationship.revision_digest,
        ))
    candidates.sort(key=lambda item: item.mapping_id)
    values = {
        "schema": "boi-usage-observed-bootstrap/v1",
        "status": "candidate_only",
        "package_digest": package.package_digest,
        "sql_resource": sql_resource,
        "sql_content_digest": source.content_digest,
        "sql_ast_digest": lineage.ast_digest,
        "lineage_unresolved_count": lineage.unresolved_count,
        "catalog_snapshot_digest": catalog.snapshot_digest,
        "catalog_content_digest": _catalog_content_digest(catalog),
        "schema_digest": catalog.schema_digest,
        "capability_digest": catalog.capability_digest,
        "physical_tables": tuple(sorted(catalog_schema)),
        "observed_joins": observed_joins,
        "filter_clause_count": len(list(statement.find_all(exp.Where))),
        "ordering_count": len(list(statement.find_all(exp.Ordered))),
        "aggregation_count": len(list(statement.find_all(exp.AggFunc))),
        "relationship_candidates": tuple(candidates),
        "source_roles": tuple(sorted(source_roles)),
        "auto_promoted": False,
        "qualification_receipt_id": None,
        "release_id": None,
        "active_pointer_transition": False,
        "canonical_projection_eligible": False,
    }
    serializable = {
        key: [item.model_dump(mode="json") for item in value]
        if key in {"observed_joins", "relationship_candidates"}
        else value
        for key, value in values.items()
    }
    return UsageObservedBootstrapReceipt(
        **values,
        receipt_digest=_digest(serializable),
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _file_content_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _qualification_receipt_digest(
    receipt: PhysicalMappingQualificationReceipt,
) -> str:
    return _digest(
        receipt.model_dump(mode="json", by_alias=True, exclude={"receipt_digest"})
    )


def verify_physical_mapping_qualification(
    receipt: PhysicalMappingQualificationReceipt,
) -> str | None:
    if _qualification_receipt_digest(receipt) != receipt.receipt_digest:
        return "PHYSICAL_QUALIFICATION_RECEIPT_DIGEST_INVALID"
    expected_status = "PASS" if receipt.checks and all(
        item.status == "PASS" for item in receipt.checks
    ) else "BLOCKED"
    if receipt.status != expected_status:
        return "PHYSICAL_QUALIFICATION_STATUS_INVALID"
    if receipt.status != "PASS" and receipt.derived_candidates:
        return "BLOCKED_QUALIFICATION_HAS_DERIVED_CANDIDATES"
    if receipt.status == "PASS" and len(receipt.derived_candidates) != len(receipt.checks):
        return "PHYSICAL_QUALIFICATION_DERIVED_COUNT_INVALID"
    for candidate in receipt.derived_candidates:
        if (
            candidate.payload_digest != _digest(candidate.payload)
            or candidate.derived_revision_digest != _digest({
                "mapping_id": candidate.mapping_id,
                "base_revision_digest": candidate.base_revision_digest,
                "payload_digest": candidate.payload_digest,
                "validation_evidence_digest": receipt.validation_evidence_digest,
                "status": "candidate",
            })
        ):
            return "DERIVED_MAPPING_CANDIDATE_DIGEST_INVALID"
        relationship = candidate.payload.get("relationship_binding")
        if not isinstance(relationship, dict) or (
            relationship.get("authority_basis") != "usage_observed"
            or relationship.get("physically_validated") is not True
            or relationship.get("physical_validation_receipt_digest")
            != receipt.validation_evidence_digest
        ):
            return "DERIVED_MAPPING_CANDIDATE_AUTHORITY_INVALID"
    return None


def qualify_usage_observed_relationships(
    package: DeclarativeProfileCandidatePackage,
    *,
    bootstrap: UsageObservedBootstrapReceipt,
    catalog: PlannerCatalogSnapshot,
    sqlite_path: Path,
) -> PhysicalMappingQualificationReceipt:
    """Measure relationship safety and emit new candidates, never promotion."""

    bootstrap_error = _verify_bootstrap_receipt(bootstrap)
    if bootstrap_error:
        raise UsageObservedBootstrapError(bootstrap_error)
    if bootstrap.package_digest != package.package_digest:
        raise UsageObservedBootstrapError("BOOTSTRAP_PACKAGE_DIGEST_MISMATCH")
    if (
        bootstrap.catalog_snapshot_digest != catalog.snapshot_digest
        or bootstrap.catalog_content_digest != _catalog_content_digest(catalog)
    ):
        raise UsageObservedBootstrapError("BOOTSTRAP_CATALOG_CONTENT_MISMATCH")
    catalog_source_receipt = next(
        (item for item in package.source_receipts if item.role == "catalog_snapshot"),
        None,
    )
    resolved_path = sqlite_path.resolve()
    if (
        catalog_source_receipt is None
        or Path(catalog_source_receipt.local_path).resolve() != resolved_path
        or _file_content_digest(resolved_path) != catalog_source_receipt.content_digest
    ):
        raise UsageObservedBootstrapError("PHYSICAL_SOURCE_SNAPSHOT_MISMATCH")

    mapping_documents = {
        item.entry_id: item for item in package.documents if item.category == "mapping"
    }
    checks: list[PhysicalRelationshipCheck] = []
    connection = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
    try:
        for observed in bootstrap.relationship_candidates:
            document = mapping_documents.get(observed.mapping_id)
            if document is None:
                raise UsageObservedBootstrapError("RELATIONSHIP_CANDIDATE_NOT_IN_PACKAGE")
            relationship = document.payload.get("relationship_binding")
            if not isinstance(relationship, dict):
                raise UsageObservedBootstrapError("RELATIONSHIP_BINDING_NOT_IN_PACKAGE")
            left_document = mapping_documents.get(str(relationship.get("left_mapping_ref")))
            right_document = mapping_documents.get(str(relationship.get("right_mapping_ref")))
            if left_document is None or right_document is None:
                raise UsageObservedBootstrapError("RELATIONSHIP_ENDPOINT_MAPPING_MISSING")
            left = _physical_endpoint(mapping_documents, left_document.entry_id)
            right = _physical_endpoint(mapping_documents, right_document.entry_id)
            if left is None or right is None:
                raise UsageObservedBootstrapError("RELATIONSHIP_ENDPOINT_PHYSICAL_MISSING")
            left_table, left_column = left
            right_table, right_column = right
            left_catalog = next((
                column
                for source in catalog.sources
                for table in source.tables if table.name == left_table
                for column in table.columns if column.name == left_column
            ), None)
            right_catalog = next((
                column
                for source in catalog.sources
                for table in source.tables if table.name == right_table
                for column in table.columns if column.name == right_column
            ), None)
            reasons: list[str] = []
            if not observed.observed_in_sql:
                reasons.append("RELATIONSHIP_NOT_OBSERVED_IN_SQL")
            if left_catalog is None:
                reasons.append("LEFT_KEY_NOT_IN_CATALOG")
            if right_catalog is None:
                reasons.append("RIGHT_KEY_NOT_IN_CATALOG")
            if right_catalog is not None and not (
                right_catalog.primary_key or right_catalog.unique
            ):
                reasons.append("RIGHT_KEY_NOT_UNIQUE_IN_CATALOG")
            quoted = tuple(
                _quote_identifier(value)
                for value in (left_table, left_column, right_table, right_column)
            )
            lt, lc, rt, rc = quoted
            left_count = int(connection.execute(
                f"SELECT COUNT(*) FROM {lt}"
            ).fetchone()[0])
            right_count = int(connection.execute(
                f"SELECT COUNT(*) FROM {rt}"
            ).fetchone()[0])
            distinct_right = int(connection.execute(
                f"SELECT COUNT(DISTINCT {rc}) FROM {rt}"
            ).fetchone()[0])
            nonnull_right = int(connection.execute(
                f"SELECT COUNT({rc}) FROM {rt}"
            ).fetchone()[0])
            join_count = int(connection.execute(
                f"SELECT COUNT(*) FROM {lt} AS l JOIN {rt} AS r ON l.{lc} = r.{rc}"
            ).fetchone()[0])
            orphan_count = int(connection.execute(
                f"SELECT COUNT(*) FROM {lt} AS l LEFT JOIN {rt} AS r "
                f"ON l.{lc} = r.{rc} WHERE l.{lc} IS NOT NULL AND r.{rc} IS NULL"
            ).fetchone()[0])
            fanout = join_count / left_count if left_count else 0.0
            if distinct_right != nonnull_right:
                reasons.append("RIGHT_KEY_DUPLICATE_IN_SOURCE")
            if fanout > 1.0:
                reasons.append("UNSAFE_CARDINALITY")
            if orphan_count:
                reasons.append("ORPHAN_KEYS_PRESENT")
            inputs = {
                "mapping_id": observed.mapping_id,
                "bootstrap_receipt_digest": bootstrap.receipt_digest,
                "catalog_snapshot_digest": catalog.snapshot_digest,
                "source_content_digest": catalog_source_receipt.content_digest,
                "left": left,
                "right": right,
            }
            evidence = {
                **inputs,
                "left_row_count": left_count,
                "right_row_count": right_count,
                "distinct_right_key_count": distinct_right,
                "nonnull_right_key_count": nonnull_right,
                "join_row_count": join_count,
                "orphan_count": orphan_count,
                "fanout_ratio": fanout,
                "reason_codes": reasons,
            }
            checks.append(PhysicalRelationshipCheck(
                mapping_id=observed.mapping_id,
                status="PASS" if not reasons else "FAIL",
                reason_codes=tuple(reasons),
                left_table=left_table,
                left_column=left_column,
                right_table=right_table,
                right_column=right_column,
                left_row_count=left_count,
                right_row_count=right_count,
                distinct_right_key_count=distinct_right,
                join_row_count=join_count,
                orphan_count=orphan_count,
                fanout_ratio=fanout,
                inputs_digest=_digest(inputs),
                evidence_digest=_digest(evidence),
            ))
    finally:
        connection.close()
    checks.sort(key=lambda item: item.mapping_id)
    status = "PASS" if checks and all(item.status == "PASS" for item in checks) else "BLOCKED"
    validation_evidence_digest = _digest({
        "bootstrap_receipt_digest": bootstrap.receipt_digest,
        "catalog_snapshot_digest": catalog.snapshot_digest,
        "catalog_content_digest": _catalog_content_digest(catalog),
        "source_content_digest": catalog_source_receipt.content_digest,
        "checks": [item.model_dump(mode="json") for item in checks],
    })
    derived: list[DerivedValidatedMappingCandidate] = []
    if status == "PASS":
        for check in checks:
            document = mapping_documents[check.mapping_id]
            relationship = {
                **document.payload["relationship_binding"],
                "physically_validated": True,
                "physical_validation_receipt_digest": validation_evidence_digest,
            }
            payload = {**document.payload, "relationship_binding": relationship}
            payload_digest = _digest(payload)
            derived_revision_digest = _digest({
                "mapping_id": document.entry_id,
                "base_revision_digest": document.revision_digest,
                "payload_digest": payload_digest,
                "validation_evidence_digest": validation_evidence_digest,
                "status": "candidate",
            })
            derived.append(DerivedValidatedMappingCandidate(
                mapping_id=document.entry_id,
                base_revision_digest=document.revision_digest,
                derived_revision_digest=derived_revision_digest,
                payload_digest=payload_digest,
                authority_basis="usage_observed",
                physically_validated=True,
                payload=payload,
            ))
    values = {
        "schema": "boi-physical-mapping-qualification/v1",
        "status": status,
        "base_package_digest": package.package_digest,
        "bootstrap_receipt_digest": bootstrap.receipt_digest,
        "catalog_snapshot_digest": catalog.snapshot_digest,
        "catalog_content_digest": _catalog_content_digest(catalog),
        "schema_digest": catalog.schema_digest,
        "source_content_digest": catalog_source_receipt.content_digest,
        "checks": tuple(checks),
        "validation_evidence_digest": validation_evidence_digest,
        "derived_candidates": tuple(derived),
        "auto_promoted": False,
        "qualification_receipt_id": None,
        "release_id": None,
        "active_pointer_transition": False,
        "canonical_projection_eligible": False,
    }
    serializable = {
        key: [item.model_dump(mode="json") for item in value]
        if key in {"checks", "derived_candidates"}
        else value
        for key, value in values.items()
    }
    return PhysicalMappingQualificationReceipt(
        **values,
        receipt_digest=_digest(serializable),
    )
