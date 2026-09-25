"""Protected, snapshot-bound paging of *internally compiled* result queries.

This is not a SQL endpoint. Only the deterministic Gateway compiler supplies
CompiledPageQuery. Consumers can use a content-addressed ref and sealed cursor.
Count/identity scans return scalars; each row-bearing request reads <=1000 rows.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer
from .result_canonicalization import normalize_result_rows
from .latest_time_order import register_latest_time_functions, time_function_digest
from .temporal_sql_comparison import temporal_expression, ALLOWED as TIME_ORDER_POLICIES


def _bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_bytes(value)).hexdigest()


def _sha(value: str) -> str:
    if len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
        raise ValueError("PAGING_DIGEST_INVALID")
    return value


def _quote(value: str) -> str:
    if not value or "\x00" in value:
        raise ValueError("PAGING_IDENTIFIER_INVALID")
    return '"' + value.replace('"', '""') + '"'


class SnapshotPagingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract: Literal["boi/snapshot-result-paging@1"] = "boi/snapshot-result-paging@1"
    policy_revision: str = Field(min_length=1)
    approval_digest: str
    page_size: int = Field(ge=1, le=1000)
    ttl_seconds: int = Field(ge=1, le=86400)
    timeout_seconds: int = Field(ge=1, le=30, default=30)
    null_grain_policy: Literal["BLOCK"] = "BLOCK"
    duplicate_grain_policy: Literal["BLOCK"] = "BLOCK"

    _approval = field_validator("approval_digest")(_sha)

    @property
    def policy_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class SnapshotPageAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract: Literal["boi/snapshot-result-paging@1"] = "boi/snapshot-result-paging@1"
    paging_ref: str
    policy_digest: str
    count_receipt_digest: str
    page_receipt_digest: str
    page_result_digest: str
    total_row_count: int = Field(ge=0)
    returned_row_count: int = Field(ge=0, le=1000)
    page_size: int = Field(ge=1, le=1000)
    expires_at: str
    next_cursor: str | None
    result_digest_kind: Literal["SNAPSHOT_BOUND_QUERY"] = "SNAPSHOT_BOUND_QUERY"


class WithSnapshotPageAccess(BaseModel):
    """Additive v2 field, absent in byte-preserved historical v1 payloads."""
    paging: SnapshotPageAccess | None = None

    @model_serializer(mode="wrap")
    def omit_absent_paging(self, handler):
        result = handler(self)
        if self.paging is None:
            result.pop("paging", None)
        return result


@dataclass(frozen=True)
class CompiledPageQuery:
    # Protected compiler-only bytes. Never part of public receipts or prompts.
    sql: str
    parameters: dict[str, Any]
    allowed_tables: tuple[str, ...]
    exact_grain: tuple[str, ...]
    ordering: tuple[str, ...]
    ordering_directions: tuple[str, ...]
    result_schema: tuple[tuple[str, str], ...]
    compiler_digest: str
    temporal_order_policies: tuple[tuple[str, str], ...] = ()


class SnapshotResultPager:
    PREFIX = "protected:snapshot-page:sha256:"

    def __init__(self, root: Path, database: Path, *,
                 authorize: Callable[[str, str, dict], bool],
                 approved_policy_digests: tuple[str, ...],
                 clock: Callable[[], datetime] | None = None) -> None:
        self.root, self.database = root, database.resolve(strict=True)
        self.authorize, self.approved_policy_digests = authorize, approved_policy_digests
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._reviewed_scope = ContextVar(
            "reviewed_snapshot_paging_authority", default=None
        )
        for path in (root, root / "queries", root / "receipts", root / "compiled"):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        key_path = root / "cursor.key"
        try:
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as file:
                file.write(secrets.token_bytes(32))
        self._key = key_path.read_bytes()
        if len(self._key) != 32:
            raise ValueError("PAGING_CURSOR_KEY_INVALID")

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("PAGING_CLOCK_NOT_AWARE")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _immutable(path: Path, value: dict) -> None:
        encoded = _bytes(value)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError("PAGING_IMMUTABLE_CONFLICT")
        else:
            with os.fdopen(fd, "wb") as file:
                file.write(encoded)

    def _snapshot(self, expected: str) -> None:
        from .sqlite_source_snapshot import sealed_sqlite_digest
        if sealed_sqlite_digest(self.database, error_prefix="PAGING_") != expected:
            raise ValueError("PAGING_SOURCE_SNAPSHOT_DRIFT")

    def _connection(self, allowed_tables: list | tuple, timeout: int) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.database}?mode=ro", uri=True, timeout=timeout)
        register_latest_time_functions(connection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        deadline = time.monotonic() + timeout
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 100)
        allowed = set(allowed_tables)

        def authorize(action, arg1, arg2, database, source):
            if action == sqlite3.SQLITE_READ:
                # SQLite's COUNT(*) optimization emits one table-level read
                # with an empty column and no database name for a projection-
                # only subquery. The named column reads still bind to ``main``;
                # admit only that exact optimizer event for an allowlisted table.
                table_level_count = database is None and arg2 == ""
                return sqlite3.SQLITE_OK if (
                    arg1 in allowed and (database == "main" or table_level_count)
                ) else sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION:
                return sqlite3.SQLITE_OK if str(arg2).lower() in {
                    "count", "sum", "avg", "min", "max", "row_number", "coalesce", "nullif", "boi_latest_time_key"
                } else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        return connection

    @contextmanager
    def reviewed_access_scope(self, resolver):
        """Bind a server-owned reviewed-candidate resolver to one request."""
        token = self._reviewed_scope.set(resolver)
        try:
            yield
        finally:
            self._reviewed_scope.reset(token)

    def _check_access(self, binding: dict, principal: str, purpose: str, *,
                      paging_phase: str, total_row_count: int | None = None,
                      page_size: int | None = None) -> None:
        if binding.get("latest_time_function_digest") and binding["latest_time_function_digest"] != time_function_digest():
            raise ValueError("PAGING_TIME_COMPILER_DRIFT")
        if binding["principal"] != principal or binding["purpose"] != purpose:
            raise ValueError("PAGING_ACCESS_DENIED")
        if binding["policy_digest"] not in self.approved_policy_digests:
            raise ValueError("PAGING_POLICY_NOT_APPROVED")
        if binding.get("candidate_authority") is not None:
            resolver = self._reviewed_scope.get()
            if resolver is None:
                raise ValueError("PAGING_REVIEWED_AUTHORITY_REQUIRED")
            scoped = {
                **binding,
                "paging_phase": paging_phase,
                "paging_page_size": (
                    int(page_size) if page_size is not None
                    else int(binding["page_size"])
                ),
                **({"paging_total_row_count": total_row_count}
                   if total_row_count is not None else {}),
            }
            resolver(principal, purpose, scoped)
        elif not self.authorize(principal, purpose, binding):
            raise ValueError("PAGING_ACCESS_DENIED")

    def prepare(self, *, query: CompiledPageQuery, policy: SnapshotPagingPolicy,
                principal: str, purpose: str, run_id: str, result_set_id: str,
                source_snapshot_digest: str, schema_digest: str,
                logical_plan_digest: str, active_release_digest: str | None,
                query_profile_digest: str, authorization_policy_digest: str,
                domain_profile_digest: str = "", mapping_profile_digest: str = "",
                candidate_authority: dict | None = None,
                reviewed_parameter_digest: str | None = None) -> dict:
        policy = SnapshotPagingPolicy.model_validate(policy.model_dump())
        if policy.policy_digest not in self.approved_policy_digests:
            raise ValueError("PAGING_POLICY_NOT_APPROVED")
        fields = {name for name, _ in query.result_schema}
        if not query.exact_grain or not set(query.exact_grain) <= fields:
            raise ValueError("PAGING_GRAIN_REQUIRED")
        if (not set(query.exact_grain) <= set(query.ordering) or not set(query.ordering) <= fields
            or len(set(query.ordering)) != len(query.ordering)
            or len(query.ordering) != len(query.ordering_directions)
            or any(item not in {"ASC", "DESC"} for item in query.ordering_directions)):
            raise ValueError("PAGING_TOTAL_ORDER_REQUIRED")
        if not query.sql.lstrip().upper().startswith("SELECT ") or ";" in query.sql:
            raise ValueError("PAGING_COMPILER_QUERY_INVALID")
        temporal_policies = dict(query.temporal_order_policies)
        if (len(temporal_policies) != len(query.temporal_order_policies)
            or not set(temporal_policies) <= fields
            or any(value not in TIME_ORDER_POLICIES for value in temporal_policies.values())):
            raise ValueError("PAGING_TEMPORAL_ORDER_POLICY_INVALID")
        for value in (source_snapshot_digest, schema_digest, logical_plan_digest,
                      query_profile_digest, authorization_policy_digest, query.compiler_digest):
            _sha(value)
        if candidate_authority is None:
            _sha(active_release_digest)
            if reviewed_parameter_digest is not None:
                raise ValueError("PAGING_REVIEWED_AUTHORITY_BINDING_INVALID")
        else:
            if active_release_digest is not None or not isinstance(candidate_authority, dict):
                raise ValueError("PAGING_REVIEWED_AUTHORITY_BINDING_INVALID")
            _sha(str(reviewed_parameter_digest or ""))
        binding = dict(principal=principal, purpose=purpose, run_id=run_id, result_set_id=result_set_id,
            source_snapshot_digest=source_snapshot_digest, schema_digest=schema_digest,
            logical_plan_digest=logical_plan_digest, active_release_digest=active_release_digest,
            query_profile_digest=query_profile_digest, authorization_policy_digest=authorization_policy_digest,
            domain_profile_digest=domain_profile_digest, mapping_profile_digest=mapping_profile_digest,
            policy_digest=policy.policy_digest, parameter_digest=_digest(query.parameters),
            compiler_digest=query.compiler_digest, compiled_query_digest=_digest(query.sql),
            exact_grain=query.exact_grain, ordering=query.ordering, ordering_directions=query.ordering_directions,
            result_schema=query.result_schema, result_schema_digest=_digest(query.result_schema))
        if candidate_authority is not None:
            binding.update(
                candidate_authority=json.loads(_bytes(candidate_authority)),
                reviewed_parameter_digest=reviewed_parameter_digest,
            )
        if temporal_policies:
            binding["temporal_order_policies"] = temporal_policies
        if "boi_latest_time_key(" in query.sql or temporal_policies:
            binding["latest_time_function_digest"] = time_function_digest()
        self._check_access(
            binding, principal, purpose, paging_phase="COUNT_PRECHECK",
            page_size=policy.page_size,
        )
        self._snapshot(source_snapshot_digest)
        connection = self._connection(query.allowed_tables, policy.timeout_seconds)
        try:
            inner = f"({query.sql}) AS __boi_page_source"
            count = connection.execute(f"SELECT COUNT(*) FROM {inner}", query.parameters).fetchone()[0]
            null_test = " OR ".join(f"{_quote(key)} IS NULL" for key in query.exact_grain)
            if connection.execute(f"SELECT COUNT(*) FROM {inner} WHERE {null_test}", query.parameters).fetchone()[0]:
                raise ValueError("PAGING_NULL_GRAIN")
            grain = ",".join(_quote(key) for key in query.exact_grain)
            if connection.execute(f"SELECT COUNT(*) FROM (SELECT {grain} FROM {inner} GROUP BY {grain} HAVING COUNT(*)>1 LIMIT 1)", query.parameters).fetchone()[0]:
                raise ValueError("PAGING_GRAIN_NOT_UNIQUE")
        except sqlite3.Error as error:
            raise ValueError("PAGING_QUERY_REJECTED_OR_TIMEOUT") from error
        finally:
            connection.close()
        self._snapshot(source_snapshot_digest)
        self._check_access(
            binding, principal, purpose,
            paging_phase="COUNT_RESULT", total_row_count=count,
            page_size=policy.page_size,
        )
        # The same run/plan/policy has one immutable preparation even if retried
        # later. Expiry is never extended by repeating prepare.
        identity = _digest({"binding": binding, "policy": policy.model_dump(mode="json")})
        path = self.root / "queries" / f"{identity[7:]}.json"
        if path.exists():
            stored = self._load(identity)
            if stored["public"]["total_row_count"] != count:
                raise ValueError("PAGING_COUNT_DRIFT")
            return stored["public"]
        count_receipt = {"binding_digest": _digest(binding), "total_row_count": count,
                         "null_grain_count": 0, "duplicate_grain_count": 0}
        public = {"contract": policy.contract, "paging_ref": self.PREFIX + identity[7:], **binding,
                  "total_row_count": count, "count_receipt_digest": _digest(count_receipt),
                  "page_size": policy.page_size,
                  "expires_at": (self._now() + timedelta(seconds=policy.ttl_seconds)).isoformat()}
        result_binding = {
            key: public[key] for key in (
                "source_snapshot_digest", "schema_digest", "compiled_query_digest", "parameter_digest",
                "exact_grain", "ordering", "ordering_directions", "result_schema_digest",
                "total_row_count", "policy_digest", "query_profile_digest", "active_release_digest",
            )
        }
        for key in ("temporal_order_policies", "latest_time_function_digest"):
            if key in public:
                result_binding[key] = public[key]
        public["query_result_digest"] = _digest(result_binding)
        stored = {"public": public, "policy": policy.model_dump(mode="json"),
                  "sql": query.sql, "parameters": query.parameters, "allowed_tables": query.allowed_tables,
                  "identity": identity, "count_receipt": count_receipt}
        self._immutable(path, {**stored, "content_digest": _digest(stored),
                              "record_mac": hmac.new(self._key, _bytes(stored), hashlib.sha256).hexdigest()})
        return json.loads(_bytes(public))

    def _load(self, identity: str) -> dict:
        _sha(identity)
        try:
            stored = json.loads((self.root / "queries" / f"{identity[7:]}.json").read_bytes())
        except (OSError, ValueError) as error:
            raise ValueError("PAGING_REF_UNAVAILABLE") from error
        proof = stored.pop("content_digest", None)
        mac = stored.pop("record_mac", "")
        if (proof != _digest(stored) or stored["identity"] != identity
            or not hmac.compare_digest(mac, hmac.new(self._key, _bytes(stored), hashlib.sha256).hexdigest())):
            raise ValueError("PAGING_RECORD_TAMPERED")
        return stored

    def _cursor(self, values: dict) -> str:
        encoded = base64.urlsafe_b64encode(_bytes(values)).decode().rstrip("=")
        return encoded + "." + hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()

    def read_page(self, paging_ref: str, *, principal: str, purpose: str, cursor: str | None = None) -> dict:
        if not paging_ref.startswith(self.PREFIX):
            raise ValueError("PAGING_REF_INVALID")
        stored = self._load("sha256:" + paging_ref.removeprefix(self.PREFIX))
        public, policy = stored["public"], SnapshotPagingPolicy.model_validate(stored["policy"])
        self._check_access(
            public, principal, purpose, paging_phase="PAGE_READ",
            total_row_count=public["total_row_count"],
        )
        if self._now() >= datetime.fromisoformat(public["expires_at"]):
            raise ValueError("PAGING_EXPIRED")
        offset = 0
        if cursor is not None:
            try:
                encoded, signature = cursor.split(".")
                if not hmac.compare_digest(signature, hmac.new(self._key, encoded.encode(), hashlib.sha256).hexdigest()):
                    raise ValueError()
                value = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                offset = value["offset"]
                if value != {"paging_ref": paging_ref, "offset": offset} or type(offset) is not int or offset < 0 or offset >= public["total_row_count"] or offset % policy.page_size:
                    raise ValueError()
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError("PAGING_CURSOR_INVALID") from error
        self._snapshot(public["source_snapshot_digest"])
        connection = self._connection(stored["allowed_tables"], policy.timeout_seconds)
        try:
            temporal_policies = public.get("temporal_order_policies", {})
            order = ",".join(
                (temporal_expression(_quote(key), temporal_policies[key]) if key in temporal_policies else _quote(key))
                + f" {direction}" for key, direction in zip(public["ordering"], public["ordering_directions"]))
            sql = f"SELECT * FROM ({stored['sql']}) AS __boi_page_source ORDER BY {order} LIMIT {policy.page_size} OFFSET {offset}"
            dry_run = [list(row) for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}", stored["parameters"]).fetchall()]
            rows = list(normalize_result_rows(tuple(dict(row) for row in connection.execute(sql, stored["parameters"]).fetchall())))
        except sqlite3.Error as error:
            raise ValueError("PAGING_QUERY_REJECTED_OR_TIMEOUT") from error
        finally:
            connection.close()
        self._snapshot(public["source_snapshot_digest"])
        if len(rows) != min(policy.page_size, max(public["total_row_count"] - offset, 0)):
            raise ValueError("PAGING_COUNT_DRIFT")
        end = offset + len(rows)
        compiled = {"sql": sql, "parameters": stored["parameters"], "compiler_digest": public["compiler_digest"],
                    "snapshot": public["source_snapshot_digest"], "policy_digest": public["policy_digest"]}
        compiled_digest = _digest(compiled)
        self._immutable(self.root / "compiled" / f"{compiled_digest[7:]}.json", compiled)
        values = {"schema": "boi-snapshot-result-page/v1", "classification": "PROVISIONAL",
                  "paging_ref": paging_ref, "binding_digest": _digest(public),
                  "source_snapshot_digest": public["source_snapshot_digest"],
                  "run_id": public["run_id"], "result_set_id": public["result_set_id"],
                  "logical_plan_digest": public["logical_plan_digest"], "exact_grain": public["exact_grain"],
                  "compiled_page_digest": compiled_digest, "compiled_page_ref": f"protected:page-compilation:{compiled_digest}",
                  "dry_run_digest": _digest(dry_run),
                  "total_row_count": public["total_row_count"], "returned_row_count": len(rows),
                  "offset": offset, "end_offset_exclusive": end, "rows": rows,
                  "page_result_digest": _digest(rows), "complete_delivery": offset == 0 and end == public["total_row_count"],
                  "next_cursor": self._cursor({"paging_ref": paging_ref, "offset": end}) if end < public["total_row_count"] else None}
        receipt = _digest(values)
        self._immutable(self.root / "receipts" / f"{receipt[7:]}.json", {**values, "receipt_digest": receipt})
        return {**values, "receipt_digest": receipt}
