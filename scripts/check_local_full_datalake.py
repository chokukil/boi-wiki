#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import quote
from typing import Any


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


def service_ok(status: dict[str, Any], name: str) -> bool:
    services = status.get("services") if isinstance(status.get("services"), dict) else {}
    service = services.get(name) if isinstance(services.get(name), dict) else {}
    return service.get("configured") is True and service.get("reachable") is True


def check_disabled_contract(base: str, employee: str, timeout: float, query: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    try:
        sources = fetch_json(f"{base}/api/data-lake/sources?employee_id={employee}", timeout)
        plan_code, plan = post_json(f"{base}/api/data-lake/query/plan?employee_id={employee}", query, timeout)
        preview_code, preview = post_json(f"{base}/api/data-lake/query/preview?employee_id={employee}", query, timeout)
        execute_code, execute = post_json(
            f"{base}/api/data-lake/query/execute?employee_id={employee}",
            {**query, "user_confirmed": True},
            timeout,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should report exact disabled-boundary failure.
        return [f"disabled Data Lake contract endpoints must respond without error: {exc}"]

    expected = [
        ("sources", 200, sources),
        ("plan", plan_code, plan),
        ("preview", preview_code, preview),
        ("execute", execute_code, execute),
    ]
    for name, code, payload in expected:
        if code != 200:
            failures.append(f"disabled {name} endpoint must return HTTP 200, got {code}")
        if payload.get("status") != "disabled":
            failures.append(f"disabled {name} endpoint must return status=disabled, got {payload.get('status')!r}")
        if payload.get("core_required") is not False:
            failures.append(f"disabled {name} endpoint must return core_required=false")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check optional BoI Wiki local-full Data Lake profile.")
    parser.add_argument("--base-url", default="http://localhost:28000", help="BoI Wiki base URL.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument("--employee-id", default="100001", help="Employee id for API calls.")
    parser.add_argument("--question", default="ETCH LOT route 근거를 찾아줘", help="Natural language Data Lake query.")
    parser.add_argument("--source", default="etch_process_sequence", help="Optional source hint.")
    parser.add_argument("--limit", type=int, default=5, help="Preview/execute row limit.")
    parser.add_argument(
        "--allow-disabled",
        action="store_true",
        help="Exit 0 when Data Lake is disabled. Useful for core local-full boundary checks.",
    )
    parser.add_argument(
        "--no-require-services",
        action="store_true",
        help="Do not require PostgreSQL and MinIO endpoints to be reachable.",
    )
    parser.add_argument(
        "--import-data-context",
        action="store_true",
        help="Materialize selected Data Lake source profiles as private OKF Data Context BoI documents.",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    employee = quote(args.employee_id)
    failures: list[str] = []

    try:
        status = fetch_json(f"{base}/api/data-lake/status?employee_id={employee}", args.timeout)
    except Exception as exc:  # noqa: BLE001 - CLI should report exact failure.
        print(f"Data Lake check failed: cannot fetch status: {exc}", file=sys.stderr)
        return 2

    query = {"question": args.question, "source": args.source, "limit": args.limit}

    if status.get("core_required") is not False:
        failures.append("data_lake.core_required must be false")
    if status.get("enabled") is not True:
        if args.allow_disabled and status.get("status") == "disabled":
            failures.extend(check_disabled_contract(base, employee, args.timeout, query))
            if failures:
                print("BoI Wiki Data Lake disabled boundary: FAILED")
                for failure in dict.fromkeys(failures):
                    print(f"- {failure}")
                return 1
            print("BoI Wiki Data Lake profile: disabled (allowed)")
            print("- core remains DB-less")
            print("- disabled API contract: OK")
            return 0
        failures.append(f"Data Lake must be enabled for this check, got status={status.get('status')!r}")
    if status.get("enabled") is True:
        available_sources = [source for source in status.get("fixture_sources") or [] if source.get("available")]
        if not available_sources:
            failures.append("at least one ontology fixture source must be available")
        if not args.no_require_services:
            if not service_ok(status, "postgres"):
                failures.append("configured PostgreSQL endpoint must be reachable from BoI API")
            if not service_ok(status, "minio"):
                failures.append("configured MinIO endpoint must be reachable from BoI API")
        if status.get("status") not in {"ready", "service_degraded"}:
            failures.append(f"unexpected Data Lake status {status.get('status')!r}")

    import_result: dict[str, Any] = {}
    try:
        plan_code, plan = post_json(f"{base}/api/data-lake/query/plan?employee_id={employee}", query, args.timeout)
        preview_code, preview = post_json(f"{base}/api/data-lake/query/preview?employee_id={employee}", query, args.timeout)
        unconfirmed_code, _ = post_json(
            f"{base}/api/data-lake/query/execute?employee_id={employee}",
            {**query, "user_confirmed": False},
            args.timeout,
            allow_status={400},
        )
        execute_code, execute = post_json(
            f"{base}/api/data-lake/query/execute?employee_id={employee}",
            {**query, "user_confirmed": True},
            args.timeout,
        )
        if args.import_data_context:
            _, import_result = post_json(
                f"{base}/api/data-lake/import?employee_id={employee}",
                {
                    "source_ids": [str((preview.get("selected_source") or {}).get("source_id") or "")],
                    "user_confirmed": True,
                },
                args.timeout,
            )
    except Exception as exc:  # noqa: BLE001 - CLI should report exact failure.
        print(f"Data Lake check failed: query flow failed: {exc}", file=sys.stderr)
        return 2

    if status.get("enabled") is True:
        if plan_code != 200 or plan.get("status") != "planned":
            failures.append(f"plan must return planned, got {plan.get('status')!r}")
        if preview_code != 200 or preview.get("status") != "preview_ready":
            failures.append(f"preview must return preview_ready, got {preview.get('status')!r}")
        if not preview.get("artifacts"):
            failures.append("preview must return at least one artifact link")
        if unconfirmed_code != 400:
            failures.append("unconfirmed execute must fail with HTTP 400")
        if execute_code != 200 or execute.get("status") != "executed":
            failures.append(f"confirmed execute must return executed, got {execute.get('status')!r}")
        if not execute.get("rows"):
            failures.append("confirmed execute must return rows for the selected fixture")
        artifacts = execute.get("artifacts") or []
        if artifacts:
            artifact_id = quote(str(artifacts[0].get("artifact_id") or ""), safe="")
            artifact = fetch_json(f"{base}/api/data-lake/artifacts/{artifact_id}?employee_id={employee}", args.timeout)
            if artifact.get("status") != "ready":
                failures.append(f"artifact must be ready, got {artifact.get('status')!r}")
        if args.import_data_context:
            if import_result.get("status") != "imported":
                failures.append(f"Data Context import must return imported, got {import_result.get('status')!r}")
            if not import_result.get("items"):
                failures.append("Data Context import must return at least one materialized item")
            else:
                first_item = import_result["items"][0]
                boi = first_item.get("boi") if isinstance(first_item.get("boi"), dict) else {}
                metadata = boi.get("metadata") if isinstance(boi.get("metadata"), dict) else {}
                if metadata.get("type") != "boi/data-context":
                    failures.append(f"imported BoI type must be boi/data-context, got {metadata.get('type')!r}")
                if not first_item.get("url"):
                    failures.append("imported Data Context item must include a BoI URL")

    if failures:
        print("BoI Wiki Data Lake profile: FAILED")
        for failure in dict.fromkeys(failures):
            print(f"- {failure}")
        return 1

    print("BoI Wiki Data Lake profile: OK")
    print(f"- status: {status.get('status')}")
    print(f"- postgres reachable: {service_ok(status, 'postgres')}")
    print(f"- minio reachable: {service_ok(status, 'minio')}")
    print(f"- selected source: {(preview.get('selected_source') or {}).get('source_id')}")
    print(f"- preview rows: {len(preview.get('rows') or [])}")
    print(f"- execute rows: {len(execute.get('rows') or [])}")
    if args.import_data_context:
        print(f"- imported Data Context BoI: {len(import_result.get('items') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
