"""Deterministic SQL AST lineage for ontology migration candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping

from sqlglot import exp, parse
from sqlglot.errors import ParseError
from sqlglot.lineage import lineage
from sqlglot.optimizer.qualify import qualify


class LineagePolicyError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class SourceColumn:
    catalog: str | None
    database: str | None
    table: str
    column: str


@dataclass(frozen=True)
class OutputColumnLineage:
    output_column: str
    expression: str
    classification: str
    sources: tuple[SourceColumn, ...]


@dataclass(frozen=True)
class SqlLineageReport:
    input_digest: str
    ast_digest: str
    dialect: str
    columns: tuple[OutputColumnLineage, ...]
    unresolved_count: int
    read_only: bool


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _parse_one_read_only(sql: str, dialect: str) -> exp.Query:
    if not isinstance(sql, str) or not sql.strip():
        raise LineagePolicyError("EMPTY_SQL")
    try:
        statements = [statement for statement in parse(sql, read=dialect) if statement is not None]
    except ParseError as error:
        raise LineagePolicyError(f"SQL_PARSE_ERROR:{error}") from error
    if len(statements) != 1:
        raise LineagePolicyError("EXACTLY_ONE_STATEMENT_REQUIRED")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise LineagePolicyError(f"READ_ONLY_QUERY_REQUIRED:{statement.key.upper()}")
    return statement


def _physical_sources(root: object) -> tuple[SourceColumn, ...]:
    sources: set[SourceColumn] = set()
    for node in root.walk():
        if node.downstream or not isinstance(node.expression, exp.Table):
            continue
        table = node.expression.name
        if not table or table == "?":
            continue
        column = str(node.name).rsplit(".", 1)[-1]
        if not column or column == "*":
            continue
        sources.add(
            SourceColumn(
                catalog=node.expression.catalog or None,
                database=node.expression.db or None,
                table=table,
                column=column,
            )
        )
    return tuple(sorted(sources))


def _root_expression(root: object) -> exp.Expression:
    expression = root.expression
    if isinstance(expression, exp.Alias):
        return expression.this
    return expression


def _classification(root: object, sources: tuple[SourceColumn, ...]) -> str:
    if not sources:
        return "unresolved"
    physical_tables = {
        (source.catalog, source.database, source.table)
        for source in sources
    }
    if len(physical_tables) > 1:
        return "multi_source"
    if isinstance(_root_expression(root), exp.Column) and len(sources) == 1:
        return "direct"
    return "computed"


def analyze_sql_lineage(
    sql: str,
    *,
    dialect: str,
    schema: Mapping[str, Mapping[str, str]] | None = None,
) -> SqlLineageReport:
    """Analyze one read-only query and resolve final output to physical leaves.

    ``schema`` is catalog metadata, not sample rows. It enables deterministic
    star expansion and unqualified-column resolution without sending data to a
    model.
    """

    statement = _parse_one_read_only(sql, dialect)
    qualified = qualify(
        statement,
        dialect=dialect,
        schema=dict(schema or {}),
        validate_qualify_columns=False,
        identify=False,
    )

    columns: list[OutputColumnLineage] = []
    for output_name in qualified.named_selects:
        try:
            root = lineage(
                output_name,
                qualified,
                dialect=dialect,
                schema=dict(schema or {}),
            )
            sources = _physical_sources(root)
            classification = _classification(root, sources)
            expression_sql = root.expression.sql(dialect=dialect)
        except Exception:
            # A failed resolution is evidence, never permission to guess a
            # mapping. Parse/policy failures are handled before this loop.
            sources = ()
            classification = "unresolved"
            expression_sql = output_name
        columns.append(
            OutputColumnLineage(
                output_column=output_name,
                expression=expression_sql,
                classification=classification,
                sources=sources,
            )
        )

    canonical_ast = qualified.sql(dialect=dialect, pretty=False)
    output = tuple(columns)
    return SqlLineageReport(
        input_digest=_digest(sql),
        ast_digest=_digest(canonical_ast),
        dialect=dialect,
        columns=output,
        unresolved_count=sum(column.classification == "unresolved" for column in output),
        read_only=True,
    )
