from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from boi_api.app.v2.openkb_compat import OpenKBCompatibilityGateway


def test_openkb_gateway_transforms_json_object_repairs_once_and_forbids_model_management():
    requests: list[dict] = []

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def do_POST(self):  # noqa: N802
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            requests.append(payload)
            content = "not json" if len(requests) == 1 else json.dumps({"title": "Alarm 판단"})
            body = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = upstream.server_address[:2]
        with OpenKBCompatibilityGateway(f"http://{host}:{port}/v1") as gateway:
            request = Request(
                f"{gateway.base_url}/chat/completions",
                data=json.dumps({
                    "model": "google/gemma-local",
                    "messages": [{"role": "user", "content": "Summarize"}],
                    "response_format": {"type": "json_object"},
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            payload = json.load(urlopen(request, timeout=5))
            assert json.loads(payload["choices"][0]["message"]["content"]) == {"title": "Alarm 판단"}
            assert requests[0]["response_format"]["type"] == "json_schema"
            assert requests[0]["messages"][0]["role"] == "system"
            assert gateway.metrics["json_object_transforms"] == 1
            assert gateway.metrics["repair_attempts"] == 1

            blocked = Request(f"{gateway.base_url}/models/load", data=b"{}", method="POST")
            try:
                urlopen(blocked, timeout=5)
            except HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("model load must be blocked")
            assert gateway.metrics["load_requests"] == 1
            assert gateway.metrics["unload_requests"] == 0
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=2)
