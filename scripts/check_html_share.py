#!/usr/bin/env python3
"""Smoke check for the HTML share + shortlink flow (Phase 1 + Phase 2).

Runs against a live boi-api server (dev auth mode):
upload -> availability -> viewer -> raw headers (+ BoI HTML Profile JSON-LD)
-> knowledge card -> duplicate policy -> delete/tombstone (+ card removal).
"""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from typing import Any
from urllib import error as urllib_error, request as urllib_request

BOI_PROFILE_SCRIPT_RE = re.compile(r"<script[^>]*id=\"boi-profile\"[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)

SAMPLE_HTML = (
    "<!doctype html>\n"
    "<html lang=\"ko\">\n"
    "<head><meta charset=\"utf-8\"><title>smoke share</title></head>\n"
    "<body><h1>HTML share smoke</h1><script>console.log('ok');</script></body>\n"
    "</html>\n"
)


def multipart_body(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----boi-share-smoke-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for key, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/html\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def http_call(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    content_type: str = "",
    timeout: float = 20.0,
) -> tuple[int, dict[str, str], bytes]:
    req = urllib_request.Request(url, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            headers = {key.lower(): value for key, value in resp.headers.items()}
            return resp.status, headers, resp.read()
    except urllib_error.HTTPError as exc:
        headers = {key.lower(): value for key, value in exc.headers.items()} if exc.headers else {}
        return exc.code, headers, exc.read()


def parse_json(payload: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(payload.decode("utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the HTML share + shortlink flow against a running boi-api.")
    parser.add_argument("--base-url", default="http://localhost:28000", help="boi-api base URL")
    parser.add_argument("--employee-id", default="100001", help="Primary (owner) employee id")
    parser.add_argument("--second-employee-id", default="100003", help="Second employee id for the duplicate-policy check")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    owner = args.employee_id
    other = args.second_employee_id
    name = f"smoke-share-{int(time.time())}"
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, ok, detail))
        print(f"[{'OK' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail and not ok else ""))

    upload_body, upload_ctype = multipart_body(
        {"name": name, "title": "HTML share smoke", "description": "scripts/check_html_share.py", "visibility": "public"},
        f"{name}.html",
        SAMPLE_HTML.encode("utf-8"),
    )
    status, _headers, payload = http_call("POST", f"{base}/api/share/html?employee_id={owner}", body=upload_body, content_type=upload_ctype)
    upload = parse_json(payload)
    check("upload public html", status == 200 and upload.get("ok") is True, f"status={status} body={payload[:200]!r}")
    check("upload response urls", upload.get("url") == f"/{name}" and upload.get("raw_url") == f"/r/{name}", f"body={upload}")

    status, _headers, payload = http_call("GET", f"{base}/api/share/names/{name}/availability?employee_id={owner}")
    check("availability owned_by_me", status == 200 and parse_json(payload).get("status") == "owned_by_me", f"status={status} body={payload[:200]!r}")

    status, _headers, payload = http_call("GET", f"{base}/{name}?employee_id={other}")
    viewer_text = payload.decode("utf-8", errors="ignore")
    check("viewer page 200", status == 200, f"status={status}")
    check("viewer iframe sandbox", 'sandbox="allow-scripts"' in viewer_text, "sandbox attribute missing")
    check("viewer has no allow-same-origin", "allow-same-origin" not in viewer_text, "allow-same-origin leaked into viewer")

    status, headers, payload = http_call("GET", f"{base}/r/{name}?employee_id={other}")
    raw_text = payload.decode("utf-8", errors="ignore")
    check("raw page 200", status == 200, f"status={status}")
    check("raw CSP header", headers.get("content-security-policy") == "sandbox allow-scripts", f"got={headers.get('content-security-policy')!r}")
    check("raw nosniff header", headers.get("x-content-type-options") == "nosniff", f"got={headers.get('x-content-type-options')!r}")
    check("raw CORP header", headers.get("cross-origin-resource-policy") == "same-site", f"got={headers.get('cross-origin-resource-policy')!r}")
    check("raw content-type", headers.get("content-type") == "text/html; charset=utf-8", f"got={headers.get('content-type')!r}")
    check("raw body served", "HTML share smoke" in raw_text, "uploaded body missing")

    # Phase 2: 저장본에는 BoI HTML Profile(JSON-LD)이 주입되고 지식 카드가 함께 생성된다.
    profile_match = BOI_PROFILE_SCRIPT_RE.search(raw_text)
    check("raw contains boi-profile JSON-LD block", bool(profile_match), "id=\"boi-profile\" block missing")
    boi_profile: dict[str, Any] = {}
    if profile_match:
        try:
            parsed_profile = json.loads(profile_match.group(1).strip())
            boi_profile = parsed_profile.get("boiProfile") or {} if isinstance(parsed_profile, dict) else {}
        except json.JSONDecodeError:
            boi_profile = {}
    boi_id = f"boi:public:html:{name}"
    check("boi-profile parses with boiProfile object", bool(boi_profile), "JSON-LD parse failed or boiProfile missing")
    check("boi-profile boi_id", boi_profile.get("boi_id") == boi_id, f"got={boi_profile.get('boi_id')!r}")
    check("boi-profile type", boi_profile.get("type") == "boi/html-document", f"got={boi_profile.get('type')!r}")
    check("boi-profile shortlink", boi_profile.get("shortlink") == f"/{name}", f"got={boi_profile.get('shortlink')!r}")

    status, _headers, payload = http_call("GET", f"{base}/api/docs/{boi_id}/access?employee_id={owner}")
    check("knowledge card doc exists", status == 200, f"status={status} body={payload[:200]!r}")

    status, _headers, payload = http_call("GET", f"{base}/api/boi?employee_id={owner}&q={name}")
    boi_items = parse_json(payload).get("items") or []
    check(
        "knowledge card appears in search",
        any((item.get("metadata") or {}).get("boi_id") == boi_id for item in boi_items),
        f"items={len(boi_items)}",
    )

    # Phase 3: 조회수 텔레메트리 + 피드백 루프 스모크.
    check("viewer shows view count", "조회" in viewer_text, "조회수가 viewer header에 없음")
    status, _headers, payload = http_call(
        "POST",
        f"{base}/api/share/{name}/feedback?employee_id={other}",
        body=json.dumps({"helpful": True}).encode("utf-8"),
        content_type="application/json",
    )
    feedback = parse_json(payload)
    check("share feedback accepted", status == 200 and feedback.get("ok") is True, f"status={status} body={payload[:200]!r}")
    status, _headers, payload = http_call("GET", f"{base}/api/docs/{boi_id}/feedback?employee_id={owner}")
    doc_feedback = parse_json(payload)
    check(
        "doc feedback aggregates include share feedback",
        status == 200 and int(doc_feedback.get("helpful") or 0) >= 1,
        f"status={status} body={payload[:200]!r}",
    )
    status, _headers, payload = http_call("GET", f"{base}/api/share/mine?employee_id={owner}")
    mine_items = parse_json(payload).get("items") or []
    mine_views = next((item.get("views") for item in mine_items if item.get("name") == name), None)
    check("share list carries view counts", isinstance(mine_views, int) and mine_views >= 1, f"views={mine_views!r}")

    dup_body, dup_ctype = multipart_body({"name": name, "visibility": "public"}, f"{name}.html", SAMPLE_HTML.encode("utf-8"))
    status, _headers, payload = http_call("POST", f"{base}/api/share/html?employee_id={other}", body=dup_body, content_type=dup_ctype)
    detail = parse_json(payload).get("detail") or {}
    suggested = detail.get("suggested_names") if isinstance(detail, dict) else None
    check("duplicate by other employee is 409", status == 409, f"status={status} body={payload[:200]!r}")
    check("409 carries suggested_names", bool(suggested), f"detail={detail}")

    status, _headers, payload = http_call("DELETE", f"{base}/api/share/{name}?employee_id={owner}")
    check("owner delete", status == 200 and parse_json(payload).get("status") == "tombstone", f"status={status} body={payload[:200]!r}")

    status, _headers, payload = http_call("GET", f"{base}/{name}?employee_id={owner}")
    check("viewer after delete is 410", status == 410, f"status={status}")

    status, _headers, payload = http_call("GET", f"{base}/api/share/names/{name}/availability?employee_id={owner}")
    check("availability tombstone", parse_json(payload).get("status") == "tombstone", f"body={payload[:200]!r}")

    status, _headers, payload = http_call("GET", f"{base}/api/docs/{boi_id}/access?employee_id={owner}")
    check("knowledge card removed after delete", status == 404, f"status={status}")

    status, _headers, payload = http_call("POST", f"{base}/api/share/html?employee_id={owner}", body=upload_body, content_type=upload_ctype)
    check("tombstoned name cannot be reused", status == 409, f"status={status} body={payload[:200]!r}")

    failed = [item for item in checks if not item[1]]
    print(f"\nHTML share smoke: {len(checks) - len(failed)}/{len(checks)} checks passed (name={name})")
    if failed:
        print("Failed checks:")
        for label, _ok, detail in failed:
            print(f"  - {label}: {detail}")
        return 1
    print("HTML share smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
