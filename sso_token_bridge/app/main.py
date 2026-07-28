from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import time
from dataclasses import dataclass
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request, Response


def split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def env_bool(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, str(default))).strip().lower()
    return value in {"1", "true", "yes", "on"}


def b64url_uint(value: int) -> str:
    width = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).rstrip(b"=").decode("ascii")


def source_allowed(source_host: str, configured: str) -> bool:
    for item in split_csv(configured):
        if hmac.compare_digest(item, source_host):
            return True
        try:
            if ipaddress.ip_address(source_host) in ipaddress.ip_network(item, strict=False):
                return True
        except ValueError:
            continue
    return False


def read_header(request: Request, env_name: str, default: str) -> str:
    name = str(os.getenv(env_name) or default).strip()
    return str(request.headers.get(name) or "").strip()


def load_private_key() -> rsa.RSAPrivateKey:
    key_file = str(os.getenv("SSO_BRIDGE_PRIVATE_KEY_FILE") or "").strip()
    key_b64 = str(os.getenv("SSO_BRIDGE_PRIVATE_KEY_B64") or "").strip()
    raw: bytes | None = None
    if key_file:
        raw = Path(key_file).read_bytes()
    elif key_b64:
        try:
            raw = base64.b64decode(key_b64, validate=True)
        except Exception as exc:
            raise RuntimeError("SSO_BRIDGE_PRIVATE_KEY_B64 is not valid base64") from exc
    if raw is not None:
        loaded = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(loaded, rsa.RSAPrivateKey):
            raise RuntimeError("SSO token bridge requires an RSA private key")
        return loaded
    if env_bool("SSO_BRIDGE_ALLOW_EPHEMERAL_KEY"):
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)
    raise RuntimeError(
        "SSO_BRIDGE_PRIVATE_KEY_FILE or SSO_BRIDGE_PRIVATE_KEY_B64 must be configured"
    )


@dataclass(frozen=True)
class BridgeKey:
    private_key: rsa.RSAPrivateKey
    kid: str

    @classmethod
    def load(cls) -> "BridgeKey":
        private_key = load_private_key()
        public_der = private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        kid = hashlib.sha256(public_der).hexdigest()[:16]
        return cls(private_key=private_key, kid=kid)

    def jwk(self) -> dict[str, str]:
        numbers = self.private_key.public_key().public_numbers()
        return {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": self.kid,
            "n": b64url_uint(numbers.n),
            "e": b64url_uint(numbers.e),
        }


BRIDGE_KEY = BridgeKey.load()
app = FastAPI(title="BoI SSO Token Bridge", version="1.0.0")


def verified_identity(request: Request) -> dict[str, str]:
    expected_secret = str(os.getenv("SSO_BRIDGE_PROXY_SHARED_SECRET") or "")
    if not expected_secret:
        raise HTTPException(status_code=503, detail="proxy shared secret is not configured")
    provided_secret = read_header(
        request,
        "SSO_BRIDGE_PROXY_SECRET_HEADER",
        "x-boi-proxy-secret",
    )
    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=401, detail="trusted proxy authentication failed")

    source_host = request.client.host if request.client else ""
    allowed_sources = str(os.getenv("SSO_BRIDGE_TRUSTED_PROXY_CIDRS") or "")
    if not allowed_sources:
        raise HTTPException(status_code=503, detail="trusted proxy sources are not configured")
    if not source_allowed(source_host, allowed_sources):
        raise HTTPException(status_code=403, detail="trusted proxy source is not allowed")

    employee_id = read_header(
        request,
        "SSO_BRIDGE_EMPLOYEE_HEADER",
        "x-boi-employee-id",
    )
    if not employee_id:
        raise HTTPException(status_code=401, detail="authenticated employee id is missing")
    return {
        "employee_id": employee_id,
        "name": read_header(request, "SSO_BRIDGE_NAME_HEADER", "x-boi-name") or employee_id,
        "email": read_header(request, "SSO_BRIDGE_EMAIL_HEADER", "x-boi-email"),
    }


def issue_token(identity: dict[str, str]) -> str:
    now = int(time.time())
    ttl = max(15, min(int(os.getenv("SSO_BRIDGE_TOKEN_TTL_SECONDS", "60")), 300))
    issuer = str(os.getenv("SSO_BRIDGE_ISSUER") or "boi-sso-token-bridge").strip()
    audience = str(os.getenv("SSO_BRIDGE_AUDIENCE") or "langflow-browser").strip()
    payload = {
        "sub": identity["employee_id"],
        "empno": identity["employee_id"],
        "preferred_username": identity["employee_id"],
        "name": identity["name"],
        "email": identity["email"],
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "nbf": now - 2,
        "exp": now + ttl,
        "jti": hashlib.sha256(
            f"{identity['employee_id']}:{time.time_ns()}".encode("utf-8")
        ).hexdigest(),
    }
    return jwt.encode(
        payload,
        BRIDGE_KEY.private_key,
        algorithm="RS256",
        headers={"kid": BRIDGE_KEY.kid, "typ": "JWT"},
    )


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "issuer": str(os.getenv("SSO_BRIDGE_ISSUER") or "boi-sso-token-bridge"),
        "audience": str(os.getenv("SSO_BRIDGE_AUDIENCE") or "langflow-browser"),
        "key_id": BRIDGE_KEY.kid,
    }


@app.get("/.well-known/jwks.json")
@app.get("/jwks.json")
def jwks() -> dict[str, list[dict[str, str]]]:
    return {"keys": [BRIDGE_KEY.jwk()]}


@app.api_route("/auth", methods=["GET", "POST"])
async def authenticate(request: Request) -> Response:
    identity = verified_identity(request)
    token = issue_token(identity)
    return Response(
        status_code=204,
        headers={
            "X-Forwarded-Access-Token": token,
            "X-Authenticated-Employee-ID": identity["employee_id"],
            "Cache-Control": "no-store",
        },
    )
