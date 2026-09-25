from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException, Request

from ..auth import AuthError, SESSION_COOKIE_NAME, resolve_identity
from .models import Principal, TokenCreateRequest
from .store import AgentV2Store, now_iso


def _bearer(authorization: str) -> str:
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


class PatService:
    def __init__(
        self,
        store: AgentV2Store,
        hash_secret: str,
        identity_provider: Callable[[str], Principal] | None = None,
    ):
        self.store = store
        self.identity_provider = identity_provider
        self._ephemeral_secret = secrets.token_bytes(32)
        self._configured_secret = hash_secret.encode("utf-8") if hash_secret else b""

    @property
    def available(self) -> bool:
        return bool(self._configured_secret) or not self.store.durable

    @property
    def production_ready(self) -> bool:
        return bool(self._configured_secret)

    def _secret(self) -> bytes:
        return self._configured_secret or self._ephemeral_secret

    def _hash(self, token: str) -> str:
        return hmac.new(self._secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _allowed_scopes(principal: Principal) -> set[str]:
        scopes = {"boi.read"}
        if principal.is_admin or "boi.editor" in principal.roles:
            scopes.add("boi.draft")
        if principal.is_admin or any(role in principal.roles for role in ("boi.action_invoker", "boi.workflow_runner")):
            scopes.add("boi.execute.low")
        return scopes

    def create(self, principal: Principal, request: TokenCreateRequest) -> dict[str, Any]:
        if not self.available:
            raise HTTPException(status_code=503, detail="PAT signing secret is not configured")
        allowed = self._allowed_scopes(principal)
        scopes = sorted(set(request.scopes))
        if any(scope not in allowed for scope in scopes):
            raise HTTPException(status_code=403, detail="requested PAT scope exceeds current RBAC permissions")
        token_id = uuid_token_id()
        raw_secret = secrets.token_urlsafe(32)
        raw_token = f"boi_pat_{token_id}_{raw_secret}"
        issued_at = datetime.now(timezone.utc)
        record = {
            "token_id": token_id,
            "employee_id": principal.employee_id,
            "name": request.name,
            "scopes": scopes,
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(days=request.expires_in_days)).isoformat(),
            "last_used_at": "",
            "revoked_at": "",
            "token_hash": self._hash(raw_token),
            "issued_roles": list(principal.roles),
            "issued_teams": list(principal.teams),
            "display_name": principal.display_name,
            "updated_at": now_iso(),
        }
        self.store.put("tokens", token_id, record)
        return {**self.public_record(record), "token": raw_token}

    @staticmethod
    def public_record(record: dict[str, Any]) -> dict[str, Any]:
        hidden = {"token_hash", "issued_roles", "issued_teams", "display_name"}
        return {key: value for key, value in record.items() if key not in hidden}

    def list(self, principal: Principal) -> list[dict[str, Any]]:
        return [self.public_record(item) for item in self.store.list("tokens", employee_id=principal.employee_id, limit=200)]

    def revoke(self, principal: Principal, token_id: str) -> bool:
        record = self.store.get("tokens", token_id)
        if not record:
            return False
        if record.get("employee_id") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="token belongs to another employee")
        record["revoked_at"] = now_iso()
        self.store.put("tokens", token_id, record)
        return True

    def authenticate(self, raw_token: str) -> Principal | None:
        if not raw_token.startswith("boi_pat_"):
            return None
        parts = raw_token.split("_", 3)
        if len(parts) != 4:
            return None
        token_id = parts[2]
        record = self.store.get("tokens", token_id)
        if not record or record.get("revoked_at"):
            return None
        try:
            expires_at = datetime.fromisoformat(str(record.get("expires_at") or ""))
        except ValueError:
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        if not hmac.compare_digest(str(record.get("token_hash") or ""), self._hash(raw_token)):
            return None
        current_principal: Principal | None = None
        if self.identity_provider:
            try:
                current_principal = self.identity_provider(str(record.get("employee_id") or ""))
            except Exception:
                return None
            if current_principal is None:
                return None
        if current_principal is None:
            try:
                identity = resolve_identity(query_employee_id=str(record.get("employee_id") or ""))
                current_principal = Principal(
                    employee_id=identity.employee_id,
                    display_name=identity.display_name,
                    email=identity.email,
                    teams=list(identity.teams),
                    roles=list(identity.roles),
                    auth_source=identity.auth_source,
                )
            except AuthError:
                current_principal = Principal(
                    employee_id=str(record.get("employee_id") or ""),
                    display_name=str(record.get("display_name") or record.get("employee_id") or ""),
                    teams=[str(item) for item in record.get("issued_teams") or []],
                    roles=[str(item) for item in record.get("issued_roles") or []],
                    auth_source="pat_snapshot",
                )
        issued_roles = set(str(item) for item in record.get("issued_roles") or [])
        issued_teams = set(str(item) for item in record.get("issued_teams") or [])
        roles = [role for role in current_principal.roles if role in issued_roles]
        teams = [team for team in current_principal.teams if team in issued_teams]
        display_name = current_principal.display_name
        record["last_used_at"] = now_iso()
        self.store.put("tokens", token_id, record)
        return Principal(
            employee_id=str(record.get("employee_id") or ""),
            display_name=display_name,
            teams=teams,
            roles=roles,
            auth_source="pat",
            token_id=token_id,
            token_scopes=[str(item) for item in record.get("scopes") or []],
        )


def uuid_token_id() -> str:
    return secrets.token_hex(8)


class V2IdentityResolver:
    def __init__(self, pat_service: PatService):
        self.pat_service = pat_service

    async def __call__(self, request: Request) -> Principal:
        authorization = request.headers.get("authorization", "")
        raw_bearer = _bearer(authorization)
        if raw_bearer.startswith("boi_pat_"):
            principal = self.pat_service.authenticate(raw_bearer)
            if principal is None:
                raise HTTPException(status_code=401, detail="invalid or expired BoI personal access token")
            return principal
        try:
            identity = resolve_identity(
                # v2 clients cannot select or impersonate a principal through
                # a resource query parameter. Browser session, PAT/bearer, or
                # trusted/dev identity headers remain the authentication
                # sources; employee_id in page/API URLs is compatibility-only.
                query_employee_id=None,
                x_employee_id=request.headers.get("x-employee-id"),
                authorization=authorization or None,
                session_token=request.cookies.get(SESSION_COOKIE_NAME),
                x_hynix_employee_id=request.headers.get("x-hynix-employee-id"),
                x_hynix_email=request.headers.get("x-hynix-email"),
                x_hynix_name=request.headers.get("x-hynix-name"),
                x_hynix_teams=request.headers.get("x-hynix-teams"),
                x_hynix_roles=request.headers.get("x-hynix-roles"),
            )
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return Principal(
            employee_id=identity.employee_id,
            display_name=identity.display_name,
            email=identity.email,
            teams=list(identity.teams),
            roles=list(identity.roles),
            auth_source=identity.auth_source,
            token_scopes=["boi.read", "boi.draft", "boi.execute.low"],
        )


def require_scope(principal: Principal, scope: str) -> None:
    if principal.auth_source != "pat":
        return
    if scope not in principal.token_scopes:
        raise HTTPException(status_code=403, detail=f"PAT scope missing: {scope}")
