from __future__ import annotations

import hashlib
import hmac
import json
import os
from urllib.parse import quote

import httpx
import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse


app = FastAPI(title="BoI Mock Corporate SSO Gateway", version="1.0.0")
UPSTREAM = str(os.getenv("MOCK_GATEWAY_UPSTREAM") or "http://boi-api-trusted:8000").rstrip("/")
SESSION_SECRET = str(os.getenv("MOCK_GATEWAY_SESSION_SECRET") or "")
PROXY_SECRET = str(os.getenv("MOCK_GATEWAY_PROXY_SHARED_SECRET") or "")
BRIDGE_URL = str(os.getenv("MOCK_GATEWAY_BRIDGE_URL") or "http://sso-token-bridge:8080").rstrip("/")
ALLOWED_EMPLOYEES = {
    item.strip()
    for item in str(os.getenv("MOCK_GATEWAY_ALLOWED_EMPLOYEES") or "").split(",")
    if item.strip()
}
INJECT_BRIDGE_JWT = str(
    os.getenv("MOCK_GATEWAY_INJECT_BRIDGE_JWT") or ""
).strip().lower() in {"1", "true", "yes", "on"}
COOKIE_NAME = "boi_mock_corporate_session"
IDENTITY_HEADERS = {
    "x-boi-employee-id",
    "x-boi-name",
    "x-boi-email",
    "x-boi-teams",
    "x-boi-roles",
    "x-hynix-employee-id",
    "x-hynix-name",
    "x-hynix-email",
    "x-hynix-teams",
    "x-hynix-roles",
    "x-boi-proxy-secret",
}
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
}


def _signature(employee_id: str) -> str:
    if not SESSION_SECRET:
        raise RuntimeError("MOCK_GATEWAY_SESSION_SECRET is required")
    return hmac.new(
        SESSION_SECRET.encode("utf-8"),
        employee_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _session(request: Request) -> str:
    raw = str(request.cookies.get(COOKIE_NAME) or "")
    employee_id, separator, signature = raw.partition(".")
    if not separator or not employee_id:
        return ""
    if not hmac.compare_digest(signature, _signature(employee_id)):
        return ""
    return employee_id


def _identity(employee_id: str) -> dict[str, str]:
    names = {
        "100001": "BoI Administrator",
        "100002": "BoI Developer",
        "100003": "BoI Viewer",
    }
    return {
        "employee_id": employee_id,
        "name": names.get(employee_id, employee_id),
        "email": f"{employee_id}@boi.validation",
        "teams": "aix-tf",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/mock-login/{employee_id}")
def login(employee_id: str, next_path: str = "/playground") -> Response:
    if employee_id not in {"100001", "100002", "100003"}:
        return Response(status_code=404)
    response = RedirectResponse(next_path if next_path.startswith("/") else "/playground")
    response.set_cookie(
        COOKIE_NAME,
        f"{employee_id}.{_signature(employee_id)}",
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response


@app.get("/mock-logout")
def logout() -> Response:
    response = RedirectResponse("/")
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/mock-bridge-proof", response_model=None)
async def bridge_proof(request: Request) -> dict[str, object] | Response:
    employee_id = _session(request)
    if not employee_id:
        return Response(status_code=401)
    identity = _identity(employee_id)
    async with httpx.AsyncClient(timeout=10) as client:
        token_response = await client.get(
            f"{BRIDGE_URL}/auth",
            headers={
                "x-boi-proxy-secret": PROXY_SECRET,
                "x-boi-employee-id": identity["employee_id"],
                "x-boi-name": identity["name"],
                "x-boi-email": identity["email"],
            },
        )
        token_response.raise_for_status()
        token = str(token_response.headers.get("x-forwarded-access-token") or "")
        jwks_response = await client.get(f"{BRIDGE_URL}/.well-known/jwks.json")
        jwks_response.raise_for_status()
    header = jwt.get_unverified_header(token)
    jwk = next(
        item
        for item in jwks_response.json().get("keys") or []
        if item.get("kid") == header.get("kid")
    )
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience="langflow-browser",
        issuer="boi-validation-sso-bridge",
    )
    return {
        "ok": True,
        "employee_id": claims["empno"],
        "algorithm": header["alg"],
        "issuer": claims["iss"],
        "audience": claims["aud"],
        "ttl_seconds": claims["exp"] - claims["iat"],
        "token_exposed": False,
    }


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request) -> Response:
    employee_id = _session(request)
    if not employee_id:
        if path.startswith("api/"):
            return Response(status_code=401)
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'>"
            "<title>Mock corporate SSO</title>"
            "<a href='/mock-login/100002?next_path=/playground'>"
            "100002로 회사 SSO 로그인</a>",
            status_code=401,
        )
    if ALLOWED_EMPLOYEES and employee_id not in ALLOWED_EMPLOYEES:
        return Response(status_code=403)
    identity = _identity(employee_id)
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in IDENTITY_HEADERS | HOP_BY_HOP
    }
    headers.update(
        {
            "x-boi-employee-id": identity["employee_id"],
            "x-boi-name": identity["name"],
            "x-boi-email": identity["email"],
            "x-boi-teams": identity["teams"],
            "x-boi-proxy-secret": PROXY_SECRET,
        }
    )
    if INJECT_BRIDGE_JWT:
        async with httpx.AsyncClient(timeout=10) as client:
            bridge_response = await client.get(
                f"{BRIDGE_URL}/auth",
                headers={
                    "x-boi-proxy-secret": PROXY_SECRET,
                    "x-boi-employee-id": identity["employee_id"],
                    "x-boi-name": identity["name"],
                    "x-boi-email": identity["email"],
                },
            )
        if bridge_response.status_code != 204:
            return Response(status_code=502)
        access_token = str(
            bridge_response.headers.get("x-forwarded-access-token") or ""
        )
        if not access_token:
            return Response(status_code=502)
        headers["x-forwarded-access-token"] = access_token
    target = f"{UPSTREAM}/{quote(path, safe='/:%')}"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        upstream = await client.request(
            request.method,
            target,
            headers=headers,
            content=await request.body(),
        )
    response = Response(
        content=upstream.content,
        status_code=upstream.status_code,
    )
    for key, value in upstream.headers.multi_items():
        if key.lower() not in HOP_BY_HOP:
            response.headers.append(key, value)
    return response
