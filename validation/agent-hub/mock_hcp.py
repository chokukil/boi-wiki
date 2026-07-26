from __future__ import annotations

import json
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


class Handler(BaseHTTPRequestHandler):
    server_version = "BoIMockHCP/1.0"

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"status": "ok", "service": "boi-mock-hcp"})
            return
        if parsed.path != "/permissions":
            self._json(404, {"detail": "not found"})
            return
        employee_id = str(parse_qs(parsed.query).get("employee_id", [""])[0])
        principal = PRINCIPALS.get(employee_id)
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

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
