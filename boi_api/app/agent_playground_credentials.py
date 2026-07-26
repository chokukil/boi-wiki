from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .auth import AuthIdentity


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class TokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[Literal["boi.read", "boi.draft", "boi.execute.low"]] = Field(
        default_factory=lambda: ["boi.read", "boi.draft"]
    )
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


@dataclass(frozen=True)
class CredentialAuthentication:
    identity: AuthIdentity
    token_id: str
    scopes: tuple[str, ...]
    kind: Literal["pat", "run_token"]
    action_key: str = ""
    flow_id: str = ""
    trace_id: str = ""

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=403, detail=f"credential scope missing: {scope}")


class SQLiteCredentialRepository:
    """Dedicated durable store for Agent Playground PATs and one-run tokens."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS playground_credentials (
                    token_id TEXT PRIMARY KEY,
                    token_kind TEXT NOT NULL CHECK(token_kind IN ('pat', 'run_token')),
                    employee_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    token_hash TEXT NOT NULL,
                    scopes_json TEXT NOT NULL,
                    issued_roles_json TEXT NOT NULL,
                    issued_teams_json TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    action_key TEXT NOT NULL DEFAULT '',
                    flow_id TEXT NOT NULL DEFAULT '',
                    trace_id TEXT NOT NULL DEFAULT '',
                    issued_at TEXT NOT NULL,
                    expires_at TEXT,
                    last_used_at TEXT NOT NULL DEFAULT '',
                    revoked_at TEXT NOT NULL DEFAULT '',
                    consumed_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_playground_credentials_owner
                    ON playground_credentials(employee_id, token_kind, issued_at DESC);
                CREATE INDEX IF NOT EXISTS idx_playground_credentials_expiry
                    ON playground_credentials(token_kind, expires_at);
                """
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, object] | None:
        if row is None:
            return None
        value = dict(row)
        value["scopes"] = json.loads(str(value.pop("scopes_json") or "[]"))
        value["issued_roles"] = json.loads(str(value.pop("issued_roles_json") or "[]"))
        value["issued_teams"] = json.loads(str(value.pop("issued_teams_json") or "[]"))
        return value

    def put(self, collection: str, token_id: str, record: dict[str, object]) -> dict[str, object]:
        token_kind = "run_token" if collection == "run_tokens" else "pat"
        payload = {
            "token_id": token_id,
            "token_kind": token_kind,
            "employee_id": str(record.get("employee_id") or ""),
            "name": str(record.get("name") or ""),
            "token_hash": str(record.get("token_hash") or ""),
            "scopes_json": json.dumps(record.get("scopes") or [], ensure_ascii=False),
            "issued_roles_json": json.dumps(record.get("issued_roles") or [], ensure_ascii=False),
            "issued_teams_json": json.dumps(record.get("issued_teams") or [], ensure_ascii=False),
            "display_name": str(record.get("display_name") or ""),
            "action_key": str(record.get("action_key") or ""),
            "flow_id": str(record.get("flow_id") or ""),
            "trace_id": str(record.get("trace_id") or ""),
            "issued_at": str(record.get("issued_at") or now_iso()),
            "expires_at": record.get("expires_at"),
            "last_used_at": str(record.get("last_used_at") or ""),
            "revoked_at": str(record.get("revoked_at") or ""),
            "consumed_at": str(record.get("consumed_at") or ""),
            "updated_at": str(record.get("updated_at") or now_iso()),
        }
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO playground_credentials (
                    token_id, token_kind, employee_id, name, token_hash,
                    scopes_json, issued_roles_json, issued_teams_json, display_name,
                    action_key, flow_id, trace_id, issued_at, expires_at,
                    last_used_at, revoked_at, consumed_at, updated_at
                ) VALUES (
                    :token_id, :token_kind, :employee_id, :name, :token_hash,
                    :scopes_json, :issued_roles_json, :issued_teams_json, :display_name,
                    :action_key, :flow_id, :trace_id, :issued_at, :expires_at,
                    :last_used_at, :revoked_at, :consumed_at, :updated_at
                )
                ON CONFLICT(token_id) DO UPDATE SET
                    name=excluded.name,
                    token_hash=excluded.token_hash,
                    scopes_json=excluded.scopes_json,
                    issued_roles_json=excluded.issued_roles_json,
                    issued_teams_json=excluded.issued_teams_json,
                    display_name=excluded.display_name,
                    action_key=excluded.action_key,
                    flow_id=excluded.flow_id,
                    trace_id=excluded.trace_id,
                    expires_at=excluded.expires_at,
                    last_used_at=excluded.last_used_at,
                    revoked_at=excluded.revoked_at,
                    consumed_at=excluded.consumed_at,
                    updated_at=excluded.updated_at
                """,
                payload,
            )
            connection.execute("COMMIT")
        return record

    def get(self, collection: str, token_id: str) -> dict[str, object] | None:
        token_kind = "run_token" if collection == "run_tokens" else "pat"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM playground_credentials WHERE token_id=? AND token_kind=?",
                (token_id, token_kind),
            ).fetchone()
        return self._decode(row)

    def list(
        self,
        collection: str,
        *,
        employee_id: str = "",
        limit: int = 200,
    ) -> list[dict[str, object]]:
        token_kind = "run_token" if collection == "run_tokens" else "pat"
        query = "SELECT * FROM playground_credentials WHERE token_kind=?"
        params: list[object] = [token_kind]
        if employee_id:
            query += " AND employee_id=?"
            params.append(employee_id)
        query += " ORDER BY issued_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [value for row in rows if (value := self._decode(row)) is not None]

    def consume_run_token(self, token_id: str) -> bool:
        timestamp = now_iso()
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE playground_credentials
                   SET consumed_at=?, updated_at=?
                 WHERE token_id=?
                   AND token_kind='run_token'
                   AND consumed_at=''
                   AND revoked_at=''
                   AND expires_at>?
                """,
                (timestamp, timestamp, token_id, timestamp),
            )
            connection.execute("COMMIT")
        return cursor.rowcount == 1


class PlaygroundCredentialService:
    def __init__(
        self,
        runtime_root: Path,
        *,
        hash_secret: str = "",
        identity_provider: Callable[[str], AuthIdentity] | None = None,
    ):
        self.store = SQLiteCredentialRepository(
            runtime_root / "agent-playground" / "credentials.sqlite3"
        )
        configured = hash_secret or os.getenv("BOI_AGENT_PLAYGROUND_TOKEN_HASH_SECRET", "")
        if not configured and os.getenv("BOI_AUTH_MODE", "dev").strip().lower() != "dev":
            raise RuntimeError("BOI_AGENT_PLAYGROUND_TOKEN_HASH_SECRET is required outside development")
        self._secret = (configured or "dev-only-agent-playground-token-secret").encode("utf-8")
        self.identity_provider = identity_provider

    @staticmethod
    def _allowed_scopes(identity: AuthIdentity) -> set[str]:
        scopes = {"boi.read"}
        if identity.is_admin or "boi.editor" in identity.roles:
            scopes.add("boi.draft")
        if identity.is_admin or any(
            role in identity.roles for role in ("boi.action_invoker", "boi.workflow_runner")
        ):
            scopes.add("boi.execute.low")
        return scopes

    def _hash(self, raw_token: str) -> str:
        return hmac.new(self._secret, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def public_record(record: dict[str, object]) -> dict[str, object]:
        hidden = {"token_hash", "issued_roles", "issued_teams", "display_name", "token_kind"}
        return {key: value for key, value in record.items() if key not in hidden}

    def create(self, identity: AuthIdentity, request: TokenCreateRequest) -> dict[str, object]:
        scopes = sorted(set(request.scopes))
        if any(scope not in self._allowed_scopes(identity) for scope in scopes):
            raise HTTPException(status_code=403, detail="requested PAT scope exceeds current permissions")
        token_id = secrets.token_hex(8)
        raw_token = f"boi_pat_{token_id}_{secrets.token_urlsafe(32)}"
        issued_at = datetime.now(timezone.utc)
        record: dict[str, object] = {
            "token_id": token_id,
            "employee_id": identity.employee_id,
            "name": request.name,
            "token_hash": self._hash(raw_token),
            "scopes": scopes,
            "issued_roles": list(identity.roles),
            "issued_teams": list(identity.teams),
            "display_name": identity.display_name,
            "issued_at": issued_at.isoformat(),
            "expires_at": (
                (issued_at + timedelta(days=request.expires_in_days)).isoformat()
                if request.expires_in_days is not None
                else None
            ),
            "last_used_at": "",
            "revoked_at": "",
            "consumed_at": "",
            "updated_at": now_iso(),
        }
        self.store.put("tokens", token_id, record)
        return {**self.public_record(record), "token": raw_token}

    def list(self, identity: AuthIdentity) -> list[dict[str, object]]:
        return [
            self.public_record(record)
            for record in self.store.list("tokens", employee_id=identity.employee_id)
        ]

    def revoke(self, identity: AuthIdentity, token_id: str) -> bool:
        record = self.store.get("tokens", token_id)
        if not record:
            return False
        if record.get("employee_id") != identity.employee_id and not identity.is_admin:
            raise HTTPException(status_code=403, detail="token belongs to another employee")
        record["revoked_at"] = now_iso()
        record["updated_at"] = now_iso()
        self.store.put("tokens", token_id, record)
        return True

    def _current_identity(self, record: dict[str, object]) -> AuthIdentity | None:
        if self.identity_provider:
            try:
                return self.identity_provider(str(record.get("employee_id") or ""))
            except Exception:
                return None
        return AuthIdentity(
            employee_id=str(record.get("employee_id") or ""),
            display_name=str(record.get("display_name") or record.get("employee_id") or ""),
            teams=[str(value) for value in record.get("issued_teams") or []],
            roles=[str(value) for value in record.get("issued_roles") or []],
            auth_source="credential_snapshot",
        )

    def _authenticate(
        self,
        raw_token: str,
        *,
        prefix: str,
        collection: str,
        kind: Literal["pat", "run_token"],
    ) -> CredentialAuthentication | None:
        if not raw_token.startswith(prefix):
            return None
        parts = raw_token.split("_", 3)
        if len(parts) != 4:
            return None
        record = self.store.get(collection, parts[2])
        if not record or record.get("revoked_at"):
            return None
        if kind == "run_token" and record.get("consumed_at"):
            return None
        expires_at = parse_timestamp(str(record.get("expires_at") or ""))
        if expires_at and expires_at <= datetime.now(timezone.utc):
            return None
        if not hmac.compare_digest(str(record.get("token_hash") or ""), self._hash(raw_token)):
            return None
        current = self._current_identity(record)
        if current is None or not current.employee_id:
            return None
        issued_roles = {str(value) for value in record.get("issued_roles") or []}
        issued_teams = {str(value) for value in record.get("issued_teams") or []}
        identity = AuthIdentity(
            employee_id=current.employee_id,
            display_name=current.display_name,
            email=current.email,
            teams=[team for team in current.teams if team in issued_teams],
            roles=[role for role in current.roles if role in issued_roles],
            auth_source=kind,
        )
        if kind == "pat":
            record["last_used_at"] = now_iso()
            record["updated_at"] = now_iso()
            self.store.put(collection, str(record["token_id"]), record)
        return CredentialAuthentication(
            identity=identity,
            token_id=str(record["token_id"]),
            scopes=tuple(str(value) for value in record.get("scopes") or []),
            kind=kind,
            action_key=str(record.get("action_key") or ""),
            flow_id=str(record.get("flow_id") or ""),
            trace_id=str(record.get("trace_id") or ""),
        )

    def authenticate(self, raw_token: str) -> CredentialAuthentication | None:
        return self._authenticate(
            raw_token,
            prefix="boi_pat_",
            collection="tokens",
            kind="pat",
        )

    def create_run_token(
        self,
        identity: AuthIdentity,
        *,
        action_key: str,
        flow_id: str,
        trace_id: str,
        scopes: list[str],
        ttl_seconds: int = 180,
    ) -> dict[str, object]:
        resolved_scopes = sorted(set(scopes))
        if not resolved_scopes or any(
            scope not in self._allowed_scopes(identity) for scope in resolved_scopes
        ):
            raise HTTPException(status_code=403, detail="run-token scope exceeds current permissions")
        token_id = secrets.token_hex(8)
        raw_token = f"boi_run_{token_id}_{secrets.token_urlsafe(32)}"
        issued_at = datetime.now(timezone.utc)
        record: dict[str, object] = {
            "token_id": token_id,
            "employee_id": identity.employee_id,
            "name": "Action execution",
            "token_hash": self._hash(raw_token),
            "scopes": resolved_scopes,
            "issued_roles": list(identity.roles),
            "issued_teams": list(identity.teams),
            "display_name": identity.display_name,
            "action_key": str(action_key or ""),
            "flow_id": str(flow_id or ""),
            "trace_id": str(trace_id or ""),
            "issued_at": issued_at.isoformat(),
            "expires_at": (
                issued_at + timedelta(seconds=max(30, min(int(ttl_seconds), 600)))
            ).isoformat(),
            "last_used_at": "",
            "revoked_at": "",
            "consumed_at": "",
            "updated_at": now_iso(),
        }
        self.store.put("run_tokens", token_id, record)
        return {
            "token": raw_token,
            "token_id": token_id,
            "expires_at": record["expires_at"],
            "action_key": record["action_key"],
            "flow_id": record["flow_id"],
            "trace_id": record["trace_id"],
            "scopes": resolved_scopes,
        }

    def authenticate_run_token(self, raw_token: str) -> CredentialAuthentication | None:
        return self._authenticate(
            raw_token,
            prefix="boi_run_",
            collection="run_tokens",
            kind="run_token",
        )

    def consume_run_token(self, token_id: str) -> bool:
        return self.store.consume_run_token(token_id)
