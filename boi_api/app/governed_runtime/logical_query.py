"""Structured logical query contracts and deterministic dialect rendering."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Mapping


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SQLITE_COMPILER_ID = "boi.sqlite-logical-renderer@0.3.0"


class IdentifierPolicyError(ValueError):
    pass


class UnsupportedDialectError(ValueError):
    pass


def _digest_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _canonical(value: Any) -> Any:
    if hasattr(value, "to_canonical"):
        return value.to_canonical()
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in sorted(value.items())}
    return value


class Expr:
    def to_canonical(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Column(Expr):
    source: str | None
    name: str

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "column", "source": self.source, "name": self.name}


@dataclass(frozen=True)
class Literal(Expr):
    value: str | int | float | None

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "literal", "value": self.value}


@dataclass(frozen=True)
class Parameter(Expr):
    name: str

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "parameter", "name": self.name}


@dataclass(frozen=True)
class Equal(Expr):
    left: Expr
    right: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "equal", "left": _canonical(self.left), "right": _canonical(self.right)}


@dataclass(frozen=True)
class InValues(Expr):
    value: Expr
    options: tuple[Literal, ...]

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "in", "value": _canonical(self.value), "options": _canonical(self.options)}


@dataclass(frozen=True)
class Compare(Expr):
    operator: str
    left: Expr
    right: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "compare", "operator": self.operator,
                "left": _canonical(self.left), "right": _canonical(self.right)}


@dataclass(frozen=True)
class Boolean(Expr):
    operator: str
    arguments: tuple[Expr, ...]

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "boolean", "operator": self.operator, "arguments": _canonical(self.arguments)}


@dataclass(frozen=True)
class Not(Expr):
    argument: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "not", "argument": _canonical(self.argument)}


@dataclass(frozen=True)
class IsNull(Expr):
    argument: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "is_null", "argument": _canonical(self.argument)}


@dataclass(frozen=True)
class CaseWhen(Expr):
    condition: Expr
    then_value: Expr
    else_value: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {
            "op": "case_when",
            "condition": _canonical(self.condition),
            "then": _canonical(self.then_value),
            "else": _canonical(self.else_value),
        }


@dataclass(frozen=True)
class Coalesce(Expr):
    value: Expr
    fallback: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "coalesce", "value": _canonical(self.value), "fallback": _canonical(self.fallback)}


@dataclass(frozen=True)
class CastInteger(Expr):
    value: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "cast_integer", "value": _canonical(self.value)}


@dataclass(frozen=True)
class Count(Expr):
    value: Expr | None = None

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "count", "value": _canonical(self.value)}


@dataclass(frozen=True)
class Average(Expr):
    value: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"op": "average", "value": _canonical(self.value)}


@dataclass(frozen=True)
class Source:
    table: str
    alias: str

    def to_canonical(self) -> dict[str, str]:
        return {"table": self.table, "alias": self.alias}


@dataclass(frozen=True)
class Join:
    kind: str
    source: Source
    on: Expr

    def to_canonical(self) -> dict[str, Any]:
        return {"kind": self.kind, "source": _canonical(self.source), "on": _canonical(self.on)}


@dataclass(frozen=True)
class Projection:
    expression: Expr
    alias: str

    def to_canonical(self) -> dict[str, Any]:
        return {"expression": _canonical(self.expression), "alias": self.alias}


@dataclass(frozen=True)
class Order:
    expression: Expr
    direction: str = "ASC"

    def to_canonical(self) -> dict[str, Any]:
        return {"expression": _canonical(self.expression), "direction": self.direction}


@dataclass(frozen=True)
class LatestBy:
    partition_by: tuple[Expr, ...]
    order_by: tuple[Order, ...]

    def to_canonical(self) -> dict[str, Any]:
        return {"partition_by": _canonical(self.partition_by), "order_by": _canonical(self.order_by)}


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    value_type: str
    required: bool = True

    def to_canonical(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.value_type, "required": self.required}


@dataclass(frozen=True)
class LogicalQuerySpec:
    query_spec_id: str
    source: Source
    joins: tuple[Join, ...]
    projections: tuple[Projection, ...]
    filters: tuple[Expr, ...] = ()
    group_by: tuple[Expr, ...] = ()
    order_by: tuple[Order, ...] = ()
    limit: int | None = None
    parameters: tuple[ParameterSpec, ...] = ()
    latest_by: LatestBy | None = None

    def to_canonical(self) -> dict[str, Any]:
        payload = {
            "query_spec_id": self.query_spec_id,
            "source": _canonical(self.source),
            "joins": _canonical(self.joins),
            "projections": _canonical(self.projections),
            "filters": _canonical(self.filters),
            "order_by": _canonical(self.order_by),
            "limit": self.limit,
            "parameters": _canonical(self.parameters),
            "latest_by": _canonical(self.latest_by),
        }
        if self.group_by:
            payload["group_by"] = _canonical(self.group_by)
        return payload

    @property
    def logical_plan_digest(self) -> str:
        payload = json.dumps(self.to_canonical(), sort_keys=True, separators=(",", ":"))
        return _digest_text(payload)

    @property
    def source_objects(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([self.source.table, *(join.source.table for join in self.joins)]))

    def bind_parameters(self, values: Mapping[str, Any]) -> dict[str, Any]:
        expected = tuple(sorted(parameter.name for parameter in self.parameters if parameter.required))
        supplied = tuple(sorted(values))
        if supplied != expected:
            raise ValueError(
                f"PARAMETER_CONTRACT_MISMATCH:required={expected}:supplied={supplied}"
            )
        by_name = {parameter.name: parameter for parameter in self.parameters}
        for name, value in values.items():
            value_type = by_name[name].value_type
            if value_type == "string" and not isinstance(value, str):
                raise TypeError(f"PARAMETER_TYPE_MISMATCH:{name}:expected=string")
            if value_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                raise TypeError(f"PARAMETER_TYPE_MISMATCH:{name}:expected=integer")
        return dict(values)

    def with_source_table(self, table: str) -> "LogicalQuerySpec":
        return replace(self, source=replace(self.source, table=table))


@dataclass(frozen=True)
class CompiledQuery:
    query_spec_id: str
    dialect: str
    sql: str
    logical_plan_digest: str
    compiler_digest: str
    compiled_sql_digest: str


class SqliteLogicalRenderer:
    dialect = "sqlite"

    @staticmethod
    def _identifier(value: str) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise IdentifierPolicyError(f"INVALID_IDENTIFIER:{value}")
        return f'"{value}"'

    def _expr(self, expression: Expr) -> str:
        if isinstance(expression, Column):
            column = self._identifier(expression.name)
            return f"{self._identifier(expression.source)}.{column}" if expression.source else column
        if isinstance(expression, Literal):
            if expression.value is None:
                return "NULL"
            if isinstance(expression.value, str):
                return "'" + expression.value.replace("'", "''") + "'"
            return str(expression.value)
        if isinstance(expression, Parameter):
            return f":{self._identifier(expression.name)[1:-1]}"
        if isinstance(expression, Equal):
            return f"{self._expr(expression.left)} = {self._expr(expression.right)}"
        if isinstance(expression, Compare):
            operators = {'eq': '=', 'ne': '<>', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
            if expression.operator not in operators:
                raise ValueError('INVALID_COMPARISON_OPERATOR')
            return f"({self._expr(expression.left)} {operators[expression.operator]} {self._expr(expression.right)})"
        if isinstance(expression, Boolean):
            if expression.operator not in ('and', 'or') or len(expression.arguments) < 2:
                raise ValueError('INVALID_BOOLEAN_EXPRESSION')
            separator = ' AND ' if expression.operator == 'and' else ' OR '
            return '(' + separator.join(f'({self._expr(v)})' for v in expression.arguments) + ')'
        if isinstance(expression, Not):
            return f"(NOT ({self._expr(expression.argument)}))"
        if isinstance(expression, IsNull):
            return f"(({self._expr(expression.argument)}) IS NULL)"
        if isinstance(expression, InValues):
            options = ", ".join(self._expr(option) for option in expression.options)
            return f"{self._expr(expression.value)} IN ({options})"
        if isinstance(expression, CaseWhen):
            return (
                f"CASE WHEN {self._expr(expression.condition)} "
                f"THEN {self._expr(expression.then_value)} "
                f"ELSE {self._expr(expression.else_value)} END"
            )
        if isinstance(expression, Coalesce):
            return f"COALESCE({self._expr(expression.value)}, {self._expr(expression.fallback)})"
        if isinstance(expression, CastInteger):
            return f"CAST({self._expr(expression.value)} AS INTEGER)"
        if isinstance(expression, Count):
            return "COUNT(*)" if expression.value is None else f"COUNT({self._expr(expression.value)})"
        if isinstance(expression, Average):
            return f"AVG({self._expr(expression.value)})"
        raise TypeError(f"UNSUPPORTED_LOGICAL_EXPRESSION:{type(expression).__name__}")

    def _order(self, order: Order) -> str:
        direction = order.direction.upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError(f"INVALID_ORDER_DIRECTION:{order.direction}")
        return f"{self._expr(order.expression)} {direction}"

    def _base_select(self, spec: LogicalQuerySpec, *, include_rank: bool) -> str:
        projections = [
            f"{self._expr(projection.expression)} AS {self._identifier(projection.alias)}"
            for projection in spec.projections
        ]
        if include_rank and spec.latest_by:
            partition = ", ".join(self._expr(item) for item in spec.latest_by.partition_by)
            order = ", ".join(self._order(item) for item in spec.latest_by.order_by)
            projections.append(
                f"ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order}) "
                f"AS {self._identifier('__revision_rank')}"
            )
        lines = [
            "SELECT",
            "  " + ",\n  ".join(projections),
            f"FROM {self._identifier(spec.source.table)} AS {self._identifier(spec.source.alias)}",
        ]
        for join in spec.joins:
            kind = join.kind.upper()
            if kind not in {"INNER", "LEFT"}:
                raise ValueError(f"UNSUPPORTED_JOIN_KIND:{join.kind}")
            lines.append(
                f"{kind} JOIN {self._identifier(join.source.table)} AS "
                f"{self._identifier(join.source.alias)} ON {self._expr(join.on)}"
            )
        if spec.filters:
            lines.append("WHERE " + "\n  AND ".join(self._expr(item) for item in spec.filters))
        if spec.group_by:
            lines.append("GROUP BY " + ", ".join(self._expr(item) for item in spec.group_by))
        return "\n".join(lines)

    def render(self, spec: LogicalQuerySpec) -> CompiledQuery:
        if spec.latest_by:
            inner = self._base_select(spec, include_rank=True)
            aliases = ", ".join(self._identifier(item.alias) for item in spec.projections)
            sql = (
                f"WITH {self._identifier('ranked')} AS (\n{inner}\n)\n"
                f"SELECT {aliases}\nFROM {self._identifier('ranked')}\n"
                f"WHERE {self._identifier('__revision_rank')} = 1"
            )
        else:
            sql = self._base_select(spec, include_rank=False)
        if spec.order_by:
            sql += "\nORDER BY " + ", ".join(self._order(item) for item in spec.order_by)
        if spec.limit is not None:
            if not isinstance(spec.limit, int) or not 1 <= spec.limit <= 1000:
                raise ValueError(f"INVALID_LIMIT:{spec.limit}")
            sql += f"\nLIMIT {spec.limit}"
        compiler_digest = _digest_text(_SQLITE_COMPILER_ID)
        return CompiledQuery(
            query_spec_id=spec.query_spec_id,
            dialect=self.dialect,
            sql=sql,
            logical_plan_digest=spec.logical_plan_digest,
            compiler_digest=compiler_digest,
            compiled_sql_digest=_digest_text(sql),
        )


def renderer_for(dialect: str) -> SqliteLogicalRenderer:
    if dialect.lower() == "sqlite":
        return SqliteLogicalRenderer()
    raise UnsupportedDialectError(f"UNSUPPORTED_DIALECT:{dialect}")
