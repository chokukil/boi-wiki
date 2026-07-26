"""Validation-only Langflow HTTP gate for negative and recovery browser tests.

Modes:

* ``unsupported`` exposes a minimal public API that reports version 1.12.0.
* ``fail_run_once`` proxies a real Langflow endpoint but fails the first
  ``POST /api/v1/run/{flow_id}`` call. All other calls are passed through.

This module is never imported by the product and must only run in an isolated
validation stack.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


MODE = os.getenv("BOI_LANGFLOW_GATE_MODE", "unsupported").strip()
TARGET_URL = os.getenv("BOI_LANGFLOW_GATE_TARGET", "").rstrip("/")
FAIL_RUNS = max(0, int(os.getenv("BOI_LANGFLOW_GATE_FAIL_RUNS", "1")))

app = FastAPI(title="BoI Agent Playground Langflow validation gate")
state: dict[str, Any] = {
    "mode": MODE,
    "run_attempts": 0,
    "injected_failures": 0,
}


@app.get("/__validation/state")
def validation_state() -> dict[str, Any]:
    return dict(state)


@app.post("/__validation/reset")
def reset_validation_state() -> dict[str, Any]:
    state["run_attempts"] = 0
    state["injected_failures"] = 0
    return dict(state)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def gate(path: str, request: Request) -> Response:
    route = f"/{path}"
    if MODE == "unsupported":
        if route == "/health":
            return JSONResponse({"status": "ok"})
        if route == "/api/v1/version":
            return JSONResponse({"version": "1.12.0"})
        if route == "/api/v1/users/whoami":
            return JSONResponse(
                {
                    "id": "unsupported-user-100002",
                    "username": "100002",
                    "is_active": True,
                }
            )
        if route == "/api/v1/projects/":
            return JSONResponse([])
        return JSONResponse({"detail": "unsupported-version validation route"}, status_code=404)

    if MODE != "fail_run_once" or not TARGET_URL:
        return JSONResponse({"detail": "validation gate is misconfigured"}, status_code=503)

    if request.method == "POST" and route.startswith("/api/v1/run/"):
        state["run_attempts"] += 1
        if state["injected_failures"] < FAIL_RUNS:
            state["injected_failures"] += 1
            return JSONResponse(
                {
                    "detail": {
                        "code": "validation_injected_failure",
                        "message": "one-shot smoke failure for idempotent recovery validation",
                    }
                },
                status_code=503,
            )

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower()
        in {
            "accept",
            "authorization",
            "content-type",
            "x-api-key",
        }
    }
    async with httpx.AsyncClient(timeout=180, follow_redirects=False) as client:
        upstream = await client.request(
            request.method,
            f"{TARGET_URL}{route}",
            params=request.query_params,
            headers=headers,
            content=body,
        )
    response_headers = {}
    if upstream.headers.get("content-type"):
        response_headers["content-type"] = upstream.headers["content-type"]
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
