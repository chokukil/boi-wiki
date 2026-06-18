from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient


DEFAULT_USER_TEAMS: dict[str, list[str]] = {
    "100001": ["aix-tf", "platform"],
    "100002": ["aix-tf"],
    "100003": ["platform"],
}
DEFAULT_USER_NAMES: dict[str, str] = {
    "100001": "AIX TF User 100001",
    "100002": "AIX TF User 100002",
    "100003": "Platform User 100003",
}

DEV_DEFAULT_ROLES = [
    "boi.viewer",
    "boi.editor",
    "boi.promoter",
    "boi.workflow_runner",
    "boi.action_invoker",
]
DEV_ADMIN_ROLES = [*DEV_DEFAULT_ROLES, "boi.admin"]


@dataclass(frozen=True)
class AuthIdentity:
    employee_id: str
    display_name: str
    email: str = ""
    teams: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    auth_source: str = "dev"

    @property
    def is_admin(self) -> bool:
        return "boi.admin" in self.roles


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_JWKS_CLIENTS: dict[str, PyJWKClient] = {}
_HCP_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
SESSION_COOKIE_NAME = "boi_session"
OIDC_STATE_COOKIE_NAME = "boi_oidc_state"


def auth_mode() -> str:
    return os.getenv("BOI_AUTH_MODE", "dev").strip().lower() or "dev"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def dev_user_teams() -> dict[str, list[str]]:
    configured = os.getenv("BOI_DEV_USER_TEAMS_JSON")
    if not configured:
        return DEFAULT_USER_TEAMS
    try:
        parsed = json.loads(configured)
    except json.JSONDecodeError:
        return DEFAULT_USER_TEAMS
    result: dict[str, list[str]] = {}
    for employee_id, teams in parsed.items():
        if isinstance(teams, str):
            result[str(employee_id)] = split_csv(teams)
        elif isinstance(teams, list):
            result[str(employee_id)] = [str(item) for item in teams if item]
    return result or DEFAULT_USER_TEAMS


def dev_user_names() -> dict[str, str]:
    configured = os.getenv("BOI_DEV_USER_NAMES_JSON")
    if not configured:
        return DEFAULT_USER_NAMES
    try:
        parsed = json.loads(configured)
    except json.JSONDecodeError:
        return DEFAULT_USER_NAMES
    result = {str(key): str(value) for key, value in parsed.items() if value}
    return result or DEFAULT_USER_NAMES


def teams_for_employee(employee_id: str) -> list[str]:
    return dev_user_teams().get(employee_id, [])


def name_for_employee(employee_id: str) -> str:
    return dev_user_names().get(employee_id, employee_id)


def dev_identity(employee_id: str | None) -> AuthIdentity:
    resolved = employee_id or os.getenv("DEMO_EMPLOYEE_ID", "100001")
    roles = DEV_ADMIN_ROLES if resolved == os.getenv("BOI_DEV_ADMIN_EMPLOYEE_ID", "100001") else DEV_DEFAULT_ROLES
    return AuthIdentity(
        employee_id=resolved,
        display_name=name_for_employee(resolved),
        email=f"{resolved}@dev.local",
        teams=teams_for_employee(resolved),
        roles=roles,
        auth_source="dev",
    )


def service_identity(employee_id: str | None) -> AuthIdentity:
    base = dev_identity(employee_id)
    permissions = hcp_permissions(base.employee_id)
    teams = unique([*base.teams, *[str(item) for item in permissions.get("teams", [])]])
    roles = unique([*DEV_ADMIN_ROLES, *[str(item) for item in permissions.get("roles", [])]])
    identity = AuthIdentity(
        employee_id=base.employee_id,
        display_name=base.display_name,
        email=base.email,
        teams=teams,
        roles=roles,
        auth_source="service_token",
    )
    allowed_employee_check(identity)
    return identity


def allowed_employee_check(identity: AuthIdentity) -> None:
    allowed = split_csv(os.getenv("BOI_ALLOWED_EMPLOYEE_IDS"))
    if allowed and identity.employee_id not in allowed:
        raise AuthError(403, "employee is not allowed to access this BoI Wiki instance")


def extract_nested_claim(claims: dict[str, Any], path: str) -> Any:
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def claim_values(claims: dict[str, Any], env_name: str, default_path: str) -> list[str]:
    raw = extract_nested_claim(claims, os.getenv(env_name, default_path))
    if isinstance(raw, str):
        return split_csv(raw) if "," in raw else [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []


def keycloak_base_url() -> str:
    internal = os.getenv("KEYCLOAK_INTERNAL_URL") or os.getenv("KEYCLOAK_SERVER_URL") or ""
    realm = os.getenv("KEYCLOAK_REALM", "")
    if not internal or not realm:
        raise AuthError(500, "Keycloak URL and realm must be configured")
    return f"{internal.rstrip('/')}/realms/{realm}"


def keycloak_issuer() -> str:
    public = os.getenv("KEYCLOAK_SERVER_URL") or os.getenv("KEYCLOAK_INTERNAL_URL") or ""
    realm = os.getenv("KEYCLOAK_REALM", "")
    if not public or not realm:
        raise AuthError(500, "Keycloak URL and realm must be configured")
    return f"{public.rstrip('/')}/realms/{realm}"


def keycloak_browser_base_url() -> str:
    public = os.getenv("KEYCLOAK_SERVER_URL") or os.getenv("KEYCLOAK_INTERNAL_URL") or ""
    realm = os.getenv("KEYCLOAK_REALM", "")
    if not public or not realm:
        raise AuthError(500, "Keycloak URL and realm must be configured")
    return f"{public.rstrip('/')}/realms/{realm}"


def keycloak_internal_base_url() -> str:
    return keycloak_base_url()


def boi_external_url() -> str:
    return os.getenv("BOI_EXTERNAL_URL", "http://localhost:8000").rstrip("/")


def keycloak_redirect_uri() -> str:
    return os.getenv("KEYCLOAK_REDIRECT_URI") or f"{boi_external_url()}/auth/callback"


def oidc_client_id() -> str:
    client_id = os.getenv("KEYCLOAK_CLIENT_ID", "")
    if not client_id:
        raise AuthError(500, "KEYCLOAK_CLIENT_ID must be configured")
    return client_id


def oidc_client_secret() -> str:
    return os.getenv("KEYCLOAK_CLIENT_SECRET", "")


def session_secret() -> str:
    secret = os.getenv("BOI_SESSION_SECRET") or os.getenv("LANGFLOW_SECRET_KEY") or os.getenv("SERVICE_TOKEN") or ""
    if not secret:
        raise AuthError(500, "BOI_SESSION_SECRET must be configured")
    return secret


def create_session_token(identity: AuthIdentity) -> str:
    now = int(time.time())
    payload = {
        "sub": identity.employee_id,
        "employee_id": identity.employee_id,
        "name": identity.display_name,
        "email": identity.email,
        "teams": identity.teams,
        "roles": identity.roles,
        "auth_source": identity.auth_source,
        "iat": now,
        "exp": now + int(os.getenv("BOI_SESSION_TTL_SECONDS", "28800")),
    }
    return jwt.encode(payload, session_secret(), algorithm="HS256")


def identity_from_session_token(token: str) -> AuthIdentity:
    try:
        claims = jwt.decode(token, session_secret(), algorithms=["HS256"])
    except Exception as exc:
        raise AuthError(401, f"invalid BoI session: {exc}") from exc
    identity = AuthIdentity(
        employee_id=str(claims.get("employee_id") or claims.get("sub") or ""),
        display_name=str(claims.get("name") or claims.get("employee_id") or ""),
        email=str(claims.get("email") or ""),
        teams=[str(item) for item in claims.get("teams", [])],
        roles=[str(item) for item in claims.get("roles", [])],
        auth_source=str(claims.get("auth_source") or "session"),
    )
    if not identity.employee_id:
        raise AuthError(401, "invalid BoI session: employee id is missing")
    allowed_employee_check(identity)
    return identity


def create_oidc_state(next_url: str = "/") -> tuple[str, str, str]:
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    code_verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    payload = {
        "state": state,
        "nonce": nonce,
        "code_verifier": code_verifier,
        "next": next_url or "/",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    state_token = jwt.encode(payload, session_secret(), algorithm="HS256")
    return state_token, state, challenge


def decode_oidc_state(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, session_secret(), algorithms=["HS256"])
    except Exception as exc:
        raise AuthError(401, f"invalid OIDC state: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthError(401, "invalid OIDC state")
    return payload


def keycloak_authorization_url(*, state: str, code_challenge: str) -> str:
    params = {
        "client_id": oidc_client_id(),
        "redirect_uri": keycloak_redirect_uri(),
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{keycloak_browser_base_url()}/protocol/openid-connect/auth?{urlencode(params)}"


def keycloak_logout_url(redirect_to: str = "/") -> str:
    params = {
        "client_id": oidc_client_id(),
        "post_logout_redirect_uri": f"{boi_external_url()}{redirect_to if redirect_to.startswith('/') else '/'}",
    }
    return f"{keycloak_browser_base_url()}/protocol/openid-connect/logout?{urlencode(params)}"


def exchange_keycloak_code(code: str, state_payload: dict[str, Any]) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "client_id": oidc_client_id(),
        "code": code,
        "redirect_uri": keycloak_redirect_uri(),
        "code_verifier": state_payload.get("code_verifier"),
    }
    secret = oidc_client_secret()
    if secret:
        data["client_secret"] = secret
    response = httpx.post(
        f"{keycloak_internal_base_url()}/protocol/openid-connect/token",
        data=data,
        timeout=float(os.getenv("KEYCLOAK_TOKEN_TIMEOUT_SECONDS", "5")),
    )
    try:
        body = response.json()
    except Exception:
        body = {"text": response.text}
    if response.status_code >= 400:
        raise AuthError(response.status_code, f"Keycloak token exchange failed: {body}")
    if not isinstance(body, dict):
        raise AuthError(502, "Keycloak token exchange returned invalid JSON")
    return body


def jwks_client(jwks_url: str) -> PyJWKClient:
    client = _JWKS_CLIENTS.get(jwks_url)
    if client is None:
        client = PyJWKClient(jwks_url)
        _JWKS_CLIENTS[jwks_url] = client
    return client


def decode_keycloak_bearer(token: str) -> dict[str, Any]:
    issuer = keycloak_issuer()
    jwks_url = f"{keycloak_base_url()}/protocol/openid-connect/certs"
    audience = os.getenv("KEYCLOAK_CLIENT_ID")
    leeway = int(os.getenv("KEYCLOAK_JWT_LEEWAY_SECONDS", "30"))
    try:
        signing_key = jwks_client(jwks_url).get_signing_key_from_jwt(token)
        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=audience,
                issuer=issuer,
                leeway=leeway,
                options={"verify_aud": bool(audience)},
            )
        except (jwt.MissingRequiredClaimError, jwt.InvalidAudienceError):
            if not audience or os.getenv("KEYCLOAK_ALLOW_AZP_AUDIENCE", "true").lower() != "true":
                raise
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=issuer,
                leeway=leeway,
                options={"verify_aud": False},
            )
            if claims.get("azp") != audience:
                raise
            return claims
    except Exception as exc:
        raise AuthError(401, f"invalid Keycloak token: {exc}") from exc


def parse_mock_bearer(token: str) -> dict[str, Any]:
    # Deterministic test/dev escape hatch. Never enable this outside BOI_AUTH_MODE=dev.
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        parsed = json.loads(payload)
    except Exception as exc:
        raise AuthError(401, "invalid mock bearer token") from exc
    if not isinstance(parsed, dict):
        raise AuthError(401, "invalid mock bearer token")
    return parsed


def hcp_permissions(employee_id: str, bearer_token: str | None = None) -> dict[str, Any]:
    url = os.getenv("HCP_AUTHZ_URL", "").strip()
    if not url:
        return {}
    ttl = int(os.getenv("HCP_AUTHZ_CACHE_TTL_SECONDS", "60"))
    now = time.time()
    cached = _HCP_CACHE.get(employee_id)
    if cached and cached[0] > now:
        return cached[1]
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    timeout = float(os.getenv("HCP_AUTHZ_TIMEOUT_SECONDS", "2"))
    try:
        response = httpx.get(url, params={"employee_id": employee_id}, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            data = {}
    except Exception as exc:
        if auth_mode() == "dev" and os.getenv("HCP_AUTHZ_FAIL_OPEN_DEV", "true").lower() == "true":
            return {}
        raise AuthError(503, f"HCP authorization lookup failed: {exc}") from exc
    _HCP_CACHE[employee_id] = (now + ttl, data)
    return data


def identity_from_claims(claims: dict[str, Any], auth_source: str, bearer_token: str | None = None) -> AuthIdentity:
    employee_claim = os.getenv("BOI_EMPLOYEE_CLAIM", "employee_id")
    employee_id = str(
        extract_nested_claim(claims, employee_claim)
        or claims.get("preferred_username")
        or claims.get("sub")
        or ""
    )
    if not employee_id:
        raise AuthError(401, "employee id claim is missing")
    teams = claim_values(claims, "BOI_TEAMS_CLAIM", "groups")
    roles = claim_values(claims, "BOI_ROLES_CLAIM", "realm_access.roles")
    permissions = hcp_permissions(employee_id, bearer_token=bearer_token)
    teams = unique([*teams, *[str(item) for item in permissions.get("teams", [])]])
    roles = unique([*roles, *[str(item) for item in permissions.get("roles", [])]])
    display_name = str(claims.get("name") or claims.get("preferred_username") or employee_id)
    email = str(claims.get("email") or "")
    identity = AuthIdentity(
        employee_id=employee_id,
        display_name=display_name,
        email=email,
        teams=teams,
        roles=roles or ["boi.viewer"],
        auth_source=auth_source,
    )
    allowed_employee_check(identity)
    return identity


def identity_from_trusted_headers(
    *,
    employee_id: str | None,
    email: str | None,
    name: str | None,
    teams: str | None,
    roles: str | None,
) -> AuthIdentity:
    if not employee_id:
        raise AuthError(401, "trusted header employee id is missing")
    identity = AuthIdentity(
        employee_id=employee_id,
        display_name=name or employee_id,
        email=email or "",
        teams=split_csv(teams),
        roles=split_csv(roles) or ["boi.viewer"],
        auth_source="trusted_header",
    )
    allowed_employee_check(identity)
    return identity


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def resolve_identity(
    *,
    query_employee_id: str | None = None,
    x_employee_id: str | None = None,
    authorization: str | None = None,
    session_token: str | None = None,
    x_hynix_employee_id: str | None = None,
    x_hynix_email: str | None = None,
    x_hynix_name: str | None = None,
    x_hynix_teams: str | None = None,
    x_hynix_roles: str | None = None,
) -> AuthIdentity:
    mode = auth_mode()
    if mode == "dev":
        token = bearer_token(authorization)
        if token and token.startswith("mock."):
            return identity_from_claims(parse_mock_bearer(token[5:]), auth_source="dev_bearer", bearer_token=token)
        identity = dev_identity(query_employee_id or x_employee_id or x_hynix_employee_id)
        allowed_employee_check(identity)
        return identity
    if mode == "trusted_header":
        identity = identity_from_trusted_headers(
            employee_id=x_hynix_employee_id or x_employee_id,
            email=x_hynix_email,
            name=x_hynix_name,
            teams=x_hynix_teams,
            roles=x_hynix_roles,
        )
    elif mode == "keycloak":
        token = bearer_token(authorization)
        if token:
            identity = identity_from_claims(decode_keycloak_bearer(token), auth_source="keycloak", bearer_token=token)
        elif session_token:
            identity = identity_from_session_token(session_token)
        else:
            raise AuthError(401, "Bearer token or browser session is required")
    else:
        raise AuthError(500, f"unsupported BOI_AUTH_MODE: {mode}")
    if query_employee_id and query_employee_id != identity.employee_id:
        raise AuthError(403, "employee_id query does not match authenticated identity")
    return identity


def has_role(identity: AuthIdentity, role: str) -> bool:
    return identity.is_admin or role in identity.roles


def require_role(identity: AuthIdentity, role: str) -> None:
    if not has_role(identity, role):
        raise AuthError(403, f"required role missing: {role}")
