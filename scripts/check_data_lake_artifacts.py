#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any
from urllib.parse import quote


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: float, *, allow_status: set[int] | None = None) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"accept": "application/json", "content-type": "application/json"},
        method="POST",
    )
    allowed = allow_status or {200}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in allowed:
            raw = exc.read().decode("utf-8")
            return exc.code, json.loads(raw) if raw else {}
        raise


def post_multipart_upload(base: str, employee: str, filename: str, content: bytes, timeout: float) -> tuple[int, dict[str, Any]]:
    boundary = f"----boi-artifact-{uuid.uuid4().hex}"
    source_context = json.dumps({"source": "artifact_harness", "stage_id": "raw_data_check"})
    parts: list[bytes] = []
    for name, value in [("visibility", "private"), ("source_context", source_context)]:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode("utf-8")
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    request = urllib.request.Request(
        f"{base}/api/data-lake/artifacts/upload?employee_id={employee}",
        data=body,
        headers={"accept": "application/json", "content-type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return response.status, json.loads(response.read().decode("utf-8"))


def fetch_bytes(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied local URL
        return response.status, response.read()


def disabled_payload_ok(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "disabled" and payload.get("enabled") is False and payload.get("core_required") is False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BoI Data Lake artifact upload/profile/download/attach contract.")
    parser.add_argument("--base-url", default="http://localhost:28000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--strict", action="store_true", help="Require every enabled artifact operation to pass; disabled contract is still valid.")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    employee = quote(args.employee_id)
    content = b"timestamp,equipment_id,lot_id,value\n1,ETCH-VM-01,LOT-A,10.2\n"
    failures: list[str] = []

    try:
        status = fetch_json(f"{base}/api/data-lake/status?employee_id={employee}", args.timeout)
    except Exception as exc:  # noqa: BLE001 - CLI should report exact failure.
        print(f"Data Lake artifact check failed: cannot fetch status: {exc}", file=sys.stderr)
        return 2

    try:
        upload_code, upload = post_multipart_upload(base, employee, "artifact-harness.csv", content, args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"Data Lake artifact check failed: upload request failed: {exc}", file=sys.stderr)
        return 2

    if status.get("enabled") is not True:
        if upload_code != 200 or not disabled_payload_ok(upload):
            failures.append("disabled artifact upload must return HTTP 200 with status=disabled/core_required=false")
        _, profile = post_json(f"{base}/api/data-lake/artifacts/missing-artifact/profile?employee_id={employee}", {}, args.timeout)
        _, attach = post_json(
            f"{base}/api/data-lake/artifacts/missing-artifact/attach?employee_id={employee}",
            {"target_type": "inbox_report", "target_id": "report-001", "user_confirmed": True},
            args.timeout,
        )
        if not disabled_payload_ok(profile):
            failures.append("disabled artifact profile must return disabled contract")
        if not disabled_payload_ok(attach):
            failures.append("disabled artifact attach must return disabled contract")
        if failures:
            print("BoI Data Lake artifact contract: FAILED")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("BoI Data Lake artifact contract: disabled (allowed)")
        print("- upload/profile/attach disabled contract: OK")
        return 0

    if upload_code != 200 or upload.get("status") != "uploaded":
        failures.append(f"artifact upload must return uploaded, got {upload.get('status')!r}")
    artifact = upload.get("artifact") if isinstance(upload.get("artifact"), dict) else {}
    artifact_id = str(artifact.get("artifact_id") or "")
    if not artifact_id:
        failures.append("artifact upload must return artifact_id")
    if not artifact.get("download_url"):
        failures.append("artifact upload must return stable download_url")

    if artifact_id:
        encoded_id = quote(artifact_id, safe="")
        get_artifact = fetch_json(f"{base}/api/data-lake/artifacts/{encoded_id}?employee_id={employee}", args.timeout)
        _, profile = post_json(f"{base}/api/data-lake/artifacts/{encoded_id}/profile?employee_id={employee}", {}, args.timeout)
        download_code, download = fetch_bytes(f"{base}/api/data-lake/artifacts/{encoded_id}/download?employee_id={employee}", args.timeout)
        _, attach = post_json(
            f"{base}/api/data-lake/artifacts/{encoded_id}/attach?employee_id={employee}",
            {
                "target_type": "inbox_report",
                "target_id": "artifact-harness-report",
                "note": "artifact harness evidence attach",
                "user_confirmed": True,
            },
            args.timeout,
        )
        if get_artifact.get("status") != "ready":
            failures.append(f"artifact get must return ready, got {get_artifact.get('status')!r}")
        if profile.get("status") != "profiled":
            failures.append(f"artifact profile must return profiled, got {profile.get('status')!r}")
        if (profile.get("profile") or {}).get("kind") != "table":
            failures.append("CSV artifact profile must be table")
        if download_code != 200 or download != content:
            failures.append("artifact download must return the original file content")
        if attach.get("status") != "attached":
            failures.append(f"artifact attach must return attached, got {attach.get('status')!r}")

    if failures:
        print("BoI Data Lake artifact contract: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("BoI Data Lake artifact contract: OK")
    print(f"- artifact_id: {artifact_id}")
    print(f"- download_url: {artifact.get('download_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
