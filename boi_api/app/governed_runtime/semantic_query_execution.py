"""Protected SQLite execution contracts for the generic semantic planner."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, computed_field, ConfigDict, Field, model_validator
from .filter_expression import compose_filter_sql

from .semantic_query_planner import (
    BindingResolutionOutcome,
    PlannerCatalogColumn,
    PlannerCatalogSnapshot,
    PlannerCatalogSource,
    PlannerCatalogTable,
    RelationalAst,
    SemanticPlanValidationReceipt,
    SemanticPlanValidator,
    SemanticPlanningContext,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


_SUPPORTED_OPERATORS = (
    "scan", "join", "filter", "aggregate", "distinct", "group", "latest",
    "project", "order", "limit",
)


def _sqlite_type(value: str) -> str:
    folded = value.casefold()
    if "int" in folded:
        return "integer"
    if any(token in folded for token in ("char", "clob", "text")):
        return "string"
    if any(token in folded for token in ("real", "floa", "doub", "dec", "num")):
        return "number"
    if "bool" in folded:
        return "boolean"
    if any(token in folded for token in ("date", "time")):
        return "datetime"
    return folded or "blob"


def capture_sqlite_planner_catalog(
    path: Path, *, source_id: str, allowed_tables: tuple[str, ...],
    captured_at: str,
) -> PlannerCatalogSnapshot:
    """Capture only the authorized metadata needed by the semantic planner."""

    if not allowed_tables or len(set(allowed_tables)) != len(allowed_tables):
        raise ValueError("AUTHORIZED_TABLE_SET_INVALID")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        available = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        if not set(allowed_tables) <= available:
            raise ValueError("AUTHORIZED_TABLE_NOT_FOUND")
        tables: list[PlannerCatalogTable] = []
        for table_name in sorted(allowed_tables):
            quoted = table_name.replace('"', '""')
            column_rows = connection.execute(
                f'PRAGMA table_info("{quoted}")'
            ).fetchall()
            primary_columns = tuple(row for row in column_rows if int(row[5]) > 0)
            # Membership in a composite key does not make each column unique.
            unique_columns = {str(primary_columns[0][1])} if len(primary_columns) == 1 else set()
            indexes = connection.execute(
                f'PRAGMA index_list("{quoted}")'
            ).fetchall()
            table_flags = next((row for row in connection.execute('PRAGMA table_list')
                                if row[0] == 'main' and row[1] == table_name), None)
            strict_or_without_rowid = bool(table_flags and (table_flags[4] or table_flags[5]))
            # INTEGER PRIMARY KEY DESC has a PK index and is not a rowid alias.
            rowid_alias = (str(primary_columns[0][1]) if len(primary_columns) == 1
                           and str(primary_columns[0][2]).upper() == 'INTEGER'
                           and not any(row[3] == 'pk' for row in indexes)
                           else None)
            for index_row in indexes:
                if not bool(index_row[2]) or bool(index_row[4]):
                    continue
                index_name = str(index_row[1]).replace('"', '""')
                indexed = connection.execute(
                    f'PRAGMA index_info("{index_name}")'
                ).fetchall()
                if len(indexed) == 1 and indexed[0][2] is not None:
                    unique_columns.add(str(indexed[0][2]))
            columns = tuple(
                PlannerCatalogColumn(
                    name=str(row[1]),
                    data_type=_sqlite_type(str(row[2])),
                    nullable=not (bool(row[3]) or str(row[1]) == rowid_alias
                                  or bool(row[5]) and strict_or_without_rowid),
                    primary_key=bool(row[5]),
                    unique=str(row[1]) in unique_columns,
                )
                for row in column_rows
            )
            estimated_rows = int(
                connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
            )
            tables.append(PlannerCatalogTable(
                name=table_name,
                estimated_rows=estimated_rows,
                columns=columns,
            ))
    finally:
        connection.close()
    schema_payload = {
        "source_id": source_id,
        "tables": [
            {
                "name": table.name,
                "columns": [column.model_dump(mode="json") for column in table.columns],
            }
            for table in tables
        ],
    }
    capability_payload = {
        "backend": "sqlite",
        "dialects": ["sqlite"],
        "operators": list(_SUPPORTED_OPERATORS),
        "read_only": True,
    }
    source = PlannerCatalogSource(
        source_id=source_id,
        backend="sqlite",
        read_only=True,
        tables=tuple(tables),
    )
    values = {
        "schema_digest": _digest(schema_payload),
        "capability_digest": _digest(capability_payload),
        "captured_at": captured_at,
        "freshness_status": "CURRENT",
        "supported_dialects": ("sqlite",),
        "supported_operators": _SUPPORTED_OPERATORS,
        "sources": (source,),
    }
    return PlannerCatalogSnapshot(
        snapshot_digest=_digest({
            **values,
            "sources": [source.model_dump(mode="json")],
        }),
        **values,
    )


class SemanticPlanReuseReceipt(BaseModel):
    """Content-addressed proof that an exact qualified plan was reused."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-qualified-semantic-plan-reuse/v1"] = (
        "boi-qualified-semantic-plan-reuse/v1"
    )
    status: Literal["HIT"] = "HIT"
    cache_id: str
    cache_key: str
    cache_entry_ref: str
    cache_entry_digest: str
    qualification_receipt_digest: str
    semantic_context_digest: str
    intent_digest: str
    binding_digest: str
    plan_digest: str
    validation_receipt_digest: str
    receipt_digest: str


class SemanticExploratoryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["exploratory"]
    semantic_context: SemanticPlanningContext
    binding_receipt: BindingResolutionOutcome
    logical_plan: RelationalAst
    validation_receipt: SemanticPlanValidationReceipt
    logical_plan_ref: str
    plan_reuse_receipt: SemanticPlanReuseReceipt | None = None
    parameters: dict[str, Any]
    principal: str
    purpose: str
    idempotency_key: str
    timeout_seconds: int = Field(default=30, ge=1, le=30)
    row_limit: int = Field(default=1000, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_chain(self) -> "SemanticExploratoryExecutionRequest":
        context = self.semantic_context
        if self.principal != context.principal_id:
            raise ValueError("SEMANTIC_PRINCIPAL_MISMATCH")
        if self.purpose != context.purpose:
            raise ValueError("SEMANTIC_PURPOSE_MISMATCH")
        if self.binding_receipt.status != "READY":
            raise ValueError("SEMANTIC_BINDING_NOT_READY")
        if self.validation_receipt.status != "PASS":
            raise ValueError("SEMANTIC_VALIDATION_NOT_PASSING")
        if (
            self.binding_receipt.semantic_context_digest != context.context_digest
            or self.logical_plan.semantic_context_digest != context.context_digest
            or self.logical_plan.binding_digest != self.binding_receipt.binding_digest
            or self.validation_receipt.semantic_context_digest != context.context_digest
            or self.validation_receipt.plan_digest != self.logical_plan.plan_digest
        ):
            raise ValueError("SEMANTIC_RECEIPT_CHAIN_MISMATCH")
        expected_validation = _digest(
            self.validation_receipt.model_dump(mode="json", exclude={"receipt_digest"})
        )
        if expected_validation != self.validation_receipt.receipt_digest:
            raise ValueError("SEMANTIC_VALIDATION_RECEIPT_DIGEST_INVALID")
        if SemanticPlanValidator._binding_content_digest(
            self.binding_receipt
        ) != self.binding_receipt.binding_digest:
            raise ValueError("SEMANTIC_BINDING_DIGEST_INVALID")
        if SemanticPlanValidator._plan_content_digest(
            self.logical_plan
        ) != self.logical_plan.plan_digest:
            raise ValueError("SEMANTIC_PLAN_DIGEST_INVALID")
        if self.logical_plan_ref != f"runtime-plan:{self.logical_plan.plan_digest}":
            raise ValueError("SEMANTIC_PLAN_REF_MISMATCH")
        if self.plan_reuse_receipt is not None:
            reuse = self.plan_reuse_receipt
            expected_reuse_digest = _digest(
                reuse.model_dump(mode="json", exclude={"receipt_digest"})
            )
            if reuse.receipt_digest != expected_reuse_digest:
                raise ValueError("SEMANTIC_PLAN_REUSE_RECEIPT_DIGEST_INVALID")
            if (
                reuse.semantic_context_digest != context.context_digest
                or reuse.intent_digest != self.logical_plan.intent_digest
                or reuse.binding_digest != self.binding_receipt.binding_digest
                or reuse.plan_digest != self.logical_plan.plan_digest
                or reuse.validation_receipt_digest
                != self.validation_receipt.receipt_digest
            ):
                raise ValueError("SEMANTIC_PLAN_REUSE_RECEIPT_CHAIN_MISMATCH")
        if self.logical_plan.limit > self.row_limit:
            raise ValueError("SEMANTIC_PLAN_LIMIT_EXCEEDS_REQUEST")
        return self


@dataclass(frozen=True)
class ProtectedSemanticCompilation:
    sql: str
    parameter_bindings: dict[str, Any]
    compiler_digest: str
    compiled_sql_digest: str


class SemanticSqliteCompiler:
    COMPILER_ID = "boi.semantic-sqlite-compiler@0.1.0"

    @staticmethod
    def _identifier(value: str) -> str:
        if not value or "\x00" in value:
            raise ValueError("SQLITE_IDENTIFIER_INVALID")
        return '"' + value.replace('"', '""') + '"'

    def compile(
        self, plan: RelationalAst, *, context: SemanticPlanningContext,
        binding: BindingResolutionOutcome,
    ) -> ProtectedSemanticCompilation:
        if context.policy.required_dialect != "sqlite":
            raise ValueError("SEMANTIC_DIALECT_UNSUPPORTED")
        aliases = {scan.alias: scan for scan in plan.scans}
        if not aliases or len(aliases) != len(plan.scans):
            raise ValueError("SEMANTIC_SCAN_SET_INVALID")
        first = plan.scans[0]
        from_sql = (
            f"{self._identifier(first.table)} AS {self._identifier(first.alias)}"
        )
        join_sql: list[str] = []
        for join in plan.joins:
            right = aliases.get(join.right_alias)
            if right is None:
                raise ValueError("SEMANTIC_JOIN_ALIAS_INVALID")
            kind = {"inner": "INNER", "left": "LEFT"}.get(join.join_kind)
            if kind is None:
                raise ValueError("SEMANTIC_JOIN_KIND_UNSUPPORTED")
            join_sql.append(
                f"{kind} JOIN {self._identifier(right.table)} AS {self._identifier(right.alias)} "
                f"ON {self._identifier(join.left_alias)}.{self._identifier(join.left_column)} = "
                f"{self._identifier(join.right_alias)}.{self._identifier(join.right_column)}"
            )

        parameter_bindings: dict[str, Any] = {}
        filter_sql: list[str] = []
        comparison = {
            "eq": "=", "neq": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=",
        }
        for index, item in enumerate(plan.filters):
            column = (
                f"{self._identifier(item.source_alias)}.{self._identifier(item.column)}"
            )
            instant_comparison=(plan.time_range is not None and item.logical_id==plan.time_range.property_id
                and item.operator not in {'is_null','is_not_null','not_null'})
            if instant_comparison:column=f'boi_instant_key({column})'
            if item.operator in {"is_null", "is_not_null", "not_null"}:
                filter_sql.append(
                    f"{column} IS {'NOT ' if item.operator in {'is_not_null', 'not_null'} else ''}NULL"
                )
            elif item.operator == "in":
                if not isinstance(item.value, tuple) or not item.value:
                    raise ValueError("SEMANTIC_IN_PARAMETER_INVALID")
                names = []
                for value_index, value in enumerate(item.value):
                    name = f"p{index}_{value_index}"
                    parameter_bindings[name] = value
                    names.append(f'boi_instant_key(:{name})' if instant_comparison else f":{name}")
                filter_sql.append(f"{column} IN ({', '.join(names)})")
            elif item.operator in comparison:
                name = f"p{index}"
                parameter_bindings[name] = item.value
                parameter_sql=f'boi_instant_key(:{name})' if instant_comparison else f':{name}'
                filter_sql.append(f"{column} {comparison[item.operator]} {parameter_sql}")
            else:
                raise ValueError("SEMANTIC_FILTER_OPERATOR_UNSUPPORTED")

        if plan.filter_expression is not None:
            filter_sql=[compose_filter_sql(plan.filter_expression,filter_sql)]
        projections = [
            f"{self._identifier(item.source_alias)}.{self._identifier(item.column)} "
            f"AS {self._identifier(item.output_alias)}"
            for item in plan.projection_bindings
        ]
        for aggregate in plan.aggregates:
            column = (
                f"{self._identifier(aggregate.source_alias)}."
                f"{self._identifier(aggregate.column)}"
            )
            if aggregate.operator in {"count", "distinct_count"}:
                distinct = "DISTINCT " if aggregate.distinct or aggregate.operator == "distinct_count" else ""
                expression = f"COUNT({distinct}{column})"
            elif aggregate.operator == "average":
                expression = f"AVG({column})"
            else:
                raise ValueError("SEMANTIC_AGGREGATE_UNSUPPORTED")
            projections.append(f"{expression} AS {self._identifier(aggregate.output_alias)}")
        if not projections:
            raise ValueError("SEMANTIC_PROJECTION_REQUIRED")

        field_by_id = {item.logical_id: item for item in binding.field_bindings}
        group_sql: list[str] = []
        for logical_id in plan.group_by:
            field = field_by_id.get(logical_id)
            if field is None:
                raise ValueError("SEMANTIC_GROUP_BINDING_MISSING")
            alias = next(
                scan.alias for scan in plan.scans
                if scan.source_id == field.source_id and scan.table == field.table
            )
            group_sql.append(
                f"{self._identifier(alias)}.{self._identifier(field.column)}"
            )
        order_sql = [
            f"{self._identifier(item.source_alias)}.{self._identifier(item.column)} {item.direction}"
            for item in plan.ordering
        ]
        source_sql = " FROM " + from_sql
        if join_sql:
            source_sql += " " + " ".join(join_sql)
        if filter_sql:
            source_sql += " WHERE " + " AND ".join(filter_sql)
        if plan.latest is not None:
            if plan.aggregates or plan.group_by:
                raise ValueError("SEMANTIC_LATEST_AGGREGATE_COMBINATION_UNSUPPORTED")
            partition_sql: list[str] = []
            for logical_id in plan.latest.partition_by:
                field = field_by_id.get(logical_id)
                if field is None:
                    raise ValueError("SEMANTIC_LATEST_PARTITION_BINDING_MISSING")
                alias = next(
                    scan.alias for scan in plan.scans
                    if scan.source_id == field.source_id and scan.table == field.table
                )
                partition_sql.append(
                    f"{self._identifier(alias)}.{self._identifier(field.column)}"
                )
            window_order = []
            for item in plan.latest.ordering:
                column = (
                    f"{self._identifier(item.source_alias)}."
                    f"{self._identifier(item.column)}"
                )
                if item.logical_id == plan.latest.target_id:
                    column = f"boi_instant_key({column})"
                window_order.append(f"{column} {item.direction}")
            if not partition_sql or not window_order:
                raise ValueError("SEMANTIC_LATEST_WINDOW_INCOMPLETE")
            rank_alias = "__boi_rank"
            ranked = (
                "SELECT " + ", ".join(projections)
                + ", ROW_NUMBER() OVER (PARTITION BY "
                + ", ".join(partition_sql)
                + " ORDER BY " + ", ".join(window_order)
                + f") AS {self._identifier(rank_alias)}"
                + source_sql
            )
            output_aliases = [item.output_alias for item in plan.projection_bindings]
            projection_alias_by_id = {
                item.logical_id: item.output_alias for item in plan.projection_bindings
            }
            stable_partition_order = [
                projection_alias_by_id[item]
                for item in plan.latest.partition_by
                if item in projection_alias_by_id
            ]
            if len(stable_partition_order) != len(plan.latest.partition_by):
                raise ValueError("SEMANTIC_LATEST_PARTITION_NOT_PROJECTED")
            sql = (
                f"WITH {self._identifier('__boi_ranked')} AS ({ranked}) SELECT "
                + ", ".join(self._identifier(item) for item in output_aliases)
                + f" FROM {self._identifier('__boi_ranked')}"
                + f" WHERE {self._identifier(rank_alias)} = 1"
                + " ORDER BY "
                + ", ".join(self._identifier(item) for item in stable_partition_order)
                + f" LIMIT {plan.limit}"
            )
        else:
            sql = "SELECT " + ", ".join(projections) + source_sql
            if group_sql:
                sql += " GROUP BY " + ", ".join(group_sql)
            if order_sql:
                sql += " ORDER BY " + ", ".join(order_sql)
            sql += f" LIMIT {plan.limit}"
        compiler_digest = _digest({
            "compiler_id": 'boi.semantic-sqlite-compiler@0.4.0' if plan.latest is not None else
                'boi.semantic-sqlite-compiler@0.3.0' if plan.time_range is not None else
                'boi.semantic-sqlite-compiler@0.2.0' if plan.filter_expression is not None else self.COMPILER_ID,
            "capability_digest": context.capability_digest,
            "policy_digest": context.planning_policy_digest,
        })
        return ProtectedSemanticCompilation(
            sql=sql,
            parameter_bindings=parameter_bindings,
            compiler_digest=compiler_digest,
            compiled_sql_digest=_digest(sql),
        )


class SemanticColdPathTrace(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True, serialize_by_alias=True,
    )

    contract_schema: Literal["boi-generic-cold-path-trace/v1"] = Field(
        default="boi-generic-cold-path-trace/v1",
        alias="schema",
        serialization_alias="schema",
    )
    registered_query_spec_ids: tuple[str, ...] = ()
    attested_computation_ids: tuple[str, ...] = ()
    promotion_candidate_ids: tuple[str, ...] = ()
    cache_hit_ids: tuple[str, ...] = ()
    golden_retrieval_ids: tuple[str, ...] = ()
    example_retrieval_ids: tuple[str, ...] = ()
    template_ids: tuple[str, ...] = ()
    family_dispatch_ids: tuple[str, ...] = ()
    raw_sql_count: Literal[0] = 0
    llm_sql_repair_count: Literal[0] = 0


class SemanticExplorationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_context_digest: str
    question_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    semantic_bundle_content_digest: str
    retrieval_receipt_digest: str
    semantic_resolution_receipt_digest: str
    intent_synthesis_receipt_digest: str = ""
    intent_model_id: str = ""
    intent_model_digest: str = ""
    intent_role_digest: str = ""
    intent_prompt_digest: str = ""
    binding_digest: str
    validation_receipt_digest: str
    validation_run_id: str
    validation_check_ids: tuple[str, ...]
    intent_digest: str
    logical_plan_digest: str
    active_release_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    compiler_digest: str
    policy_digest: str
    parameter_digest: str
    execution_artifact_ref: str
    execution_artifact_digest: str
    executed_sql: None = None
    backend_execution_id: str
    source_snapshot: str
    result_schema_digest: str
    row_count: int
    result_digest: str
    authorization_policy_digest: str
    cold_path_trace: SemanticColdPathTrace
    result_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    dry_run_status: Literal["PASS"] = "PASS"
    dry_run_digest: str
    started_at: str
    completed_at: str

    @computed_field
    @property
    def receipt_digest(self) -> str:
        return _digest(self.model_dump(mode="json", exclude={"receipt_digest"}))
