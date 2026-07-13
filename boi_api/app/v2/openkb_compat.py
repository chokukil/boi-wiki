from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class OpenKBCompatibilityGateway:
    """Narrow OpenAI-compatible proxy for OpenKB's legacy json_object requests."""

    def __init__(self, upstream_base_url: str, api_key: str = ""):
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self.api_key = api_key
        self.metrics = {
            "requests": 0,
            "json_object_transforms": 0,
            "repair_attempts": 0,
            "load_requests": 0,
            "unload_requests": 0,
        }
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if not self._server:
            return ""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def _upstream_url(self, path: str) -> str:
        normalized = path.split("?", 1)[0]
        if self.upstream_base_url.endswith("/v1") and normalized.startswith("/v1/"):
            normalized = normalized[3:]
        return f"{self.upstream_base_url}{normalized}"

    def _forward(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, bytes, str]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self._upstream_url(path), data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=120) as response:
                return response.status, response.read(), response.headers.get("Content-Type", "application/json")
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers.get("Content-Type", "application/json")

    @staticmethod
    def _json_content(payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None

    def _chat(self, payload: dict[str, Any]) -> tuple[int, bytes, str]:
        request_payload = dict(payload)
        response_format = request_payload.get("response_format")
        if isinstance(response_format, dict) and response_format.get("type") == "json_object":
            self.metrics["json_object_transforms"] += 1
            request_payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "openkb_json_object",
                    "strict": False,
                    "schema": {"type": "object", "additionalProperties": True},
                },
            }
            messages = list(request_payload.get("messages") or [])
            messages.insert(0, {"role": "system", "content": "Return one valid JSON object and no surrounding prose."})
            request_payload["messages"] = messages
        request_payload["stream"] = False
        status, body, content_type = self._forward("POST", "/v1/chat/completions", request_payload)
        if status >= 400:
            return status, body, content_type
        try:
            response_payload = json.loads(body)
        except json.JSONDecodeError:
            return 502, b'{"error":{"message":"openkb_upstream_invalid_json"}}', "application/json"
        if not isinstance(response_format, dict) or response_format.get("type") != "json_object":
            return status, body, content_type
        parsed = self._json_content(response_payload)
        if parsed is None:
            self.metrics["repair_attempts"] += 1
            repair_payload = dict(request_payload)
            repair_payload["messages"] = [
                *(request_payload.get("messages") or []),
                {"role": "user", "content": "The previous answer was not a valid JSON object. Return the corrected JSON object only."},
            ]
            status, body, content_type = self._forward("POST", "/v1/chat/completions", repair_payload)
            if status >= 400:
                return status, body, content_type
            try:
                response_payload = json.loads(body)
            except json.JSONDecodeError:
                response_payload = {}
            parsed = self._json_content(response_payload)
        if parsed is None:
            return 502, b'{"error":{"message":"openkb_json_schema_validation_failed"}}', "application/json"
        response_payload["choices"][0]["message"]["content"] = json.dumps(parsed, ensure_ascii=False)
        return 200, json.dumps(response_payload, ensure_ascii=False).encode("utf-8"), "application/json"

    def start(self) -> "OpenKBCompatibilityGateway":
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def _write(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                gateway.metrics["requests"] += 1
                status, body, content_type = gateway._forward("GET", self.path)
                self._write(status, body, content_type)

            def do_POST(self) -> None:  # noqa: N802
                gateway.metrics["requests"] += 1
                if "/models/load" in self.path:
                    gateway.metrics["load_requests"] += 1
                    self._write(403, b'{"error":{"message":"model_management_forbidden"}}', "application/json")
                    return
                if "/models/unload" in self.path:
                    gateway.metrics["unload_requests"] += 1
                    self._write(403, b'{"error":{"message":"model_management_forbidden"}}', "application/json")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    payload = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    self._write(400, b'{"error":{"message":"invalid_json"}}', "application/json")
                    return
                if self.path.split("?", 1)[0].endswith("/chat/completions"):
                    status, body, content_type = gateway._chat(payload)
                else:
                    status, body, content_type = gateway._forward("POST", self.path, payload)
                self._write(status, body, content_type)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, name="openkb-lmstudio-compat", daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def __enter__(self) -> "OpenKBCompatibilityGateway":
        return self.start()

    def __exit__(self, *_args: Any) -> None:
        self.close()
