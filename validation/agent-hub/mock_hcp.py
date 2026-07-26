from __future__ import annotations

import copy
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


PRINCIPALS = {
    "100001": {
        "employee_id": "100001",
        "allowed": True,
        "teams": ["aix-tf", "platform"],
        "roles": [
            "boi.viewer",
            "boi.editor",
            "boi.promoter",
            "boi.workflow_runner",
            "boi.action_invoker",
            "boi.admin",
        ],
        "projects": ["boi-100001"],
    },
    "100002": {
        "employee_id": "100002",
        "allowed": True,
        "teams": ["aix-tf"],
        "roles": [
            "boi.viewer",
            "boi.editor",
            "boi.workflow_runner",
            "boi.action_invoker",
        ],
        "projects": ["boi-100002"],
    },
    "100003": {
        "employee_id": "100003",
        "allowed": True,
        "teams": ["platform"],
        "roles": ["boi.viewer"],
        "projects": ["boi-100003"],
    },
}
DEFAULT_PRINCIPALS = copy.deepcopy(PRINCIPALS)
STATE_LOCK = threading.RLock()
OUTAGE = False
CONTROL_TOKEN = os.getenv(
    "BOI_MOCK_HCP_CONTROL_TOKEN",
    "boi-hcp-validation-control",
)


class Handler(BaseHTTPRequestHandler):
    server_version = "BoIMockHCP/1.0"

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized_control(self) -> bool:
        return self.headers.get("x-validation-token", "") == CONTROL_TOKEN

    def _request_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        global OUTAGE
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(
                200,
                {
                    "status": "ok",
                    "service": "boi-mock-hcp",
                    "authorization_outage": OUTAGE,
                },
            )
            return
        if parsed.path != "/permissions":
            self._json(404, {"detail": "not found"})
            return
        if OUTAGE:
            self._json(503, {"detail": "validation HCP outage"})
            return
        employee_id = str(parse_qs(parsed.query).get("employee_id", [""])[0])
        with STATE_LOCK:
            principal = copy.deepcopy(PRINCIPALS.get(employee_id))
        if principal is None:
            self._json(
                200,
                {
                    "employee_id": employee_id,
                    "allowed": False,
                    "teams": [],
                    "roles": [],
                    "projects": [],
                },
            )
            return
        self._json(200, principal)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        global OUTAGE
        if self.path != "/__validation/state":
            self._json(404, {"detail": "not found"})
            return
        if not self._authorized_control():
            self._json(403, {"detail": "validation control token is required"})
            return
        payload = self._request_json()
        employee_id = str(payload.get("employee_id") or "")
        with STATE_LOCK:
            if "outage" in payload:
                OUTAGE = bool(payload["outage"])
            if employee_id:
                current = copy.deepcopy(
                    PRINCIPALS.get(employee_id)
                    or {
                        "employee_id": employee_id,
                        "allowed": False,
                        "teams": [],
                        "roles": [],
                        "projects": [],
                    }
                )
                for key in ("allowed", "teams", "roles", "projects"):
                    if key in payload:
                        current[key] = payload[key]
                PRINCIPALS[employee_id] = current
            principal = copy.deepcopy(PRINCIPALS.get(employee_id)) if employee_id else None
        self._json(
            200,
            {
                "ok": True,
                "employee_id": employee_id,
                "outage": OUTAGE,
                "principal": principal,
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        global OUTAGE
        if self.path != "/__validation/state":
            self._json(404, {"detail": "not found"})
            return
        if not self._authorized_control():
            self._json(403, {"detail": "validation control token is required"})
            return
        with STATE_LOCK:
            PRINCIPALS.clear()
            PRINCIPALS.update(copy.deepcopy(DEFAULT_PRINCIPALS))
            OUTAGE = False
        self._json(200, {"ok": True, "reset": True, "outage": False})

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
