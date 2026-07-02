#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 60) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc


def api_url(base_url: str, path: str, employee_id: str) -> str:
    joiner = "&" if "?" in path else "?"
    return f"{base_url.rstrip('/')}{path}{joiner}{urllib.parse.urlencode({'employee_id': employee_id})}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BoI Agent Builder + GPT-5.5 + sandbox evidence flow.")
    parser.add_argument("--base-url", default="http://localhost:28000")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--strict-openai", action="store_true", help="Require GPT-5.5 Responses and Agents SDK summary to be ready.")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    started = time.monotonic()
    base = args.base_url.rstrip("/")
    employee_id = args.employee_id

    runtime = request_json("GET", f"{base}/api/runtime/config", timeout=30)
    agents_runtime = runtime.get("agents_sdk_runtime") or {}
    openai_runtime = runtime.get("openai_runtime") or {}
    require((agents_runtime.get("sandbox") or {}).get("backend") == "unix_local", "sandbox backend should be unix_local for local-full smoke")
    require(agents_runtime.get("available") is True, f"Agents SDK is not available: {agents_runtime.get('import_error')}")

    checked_openai = request_json("POST", f"{base}/api/runtime/openai-health/check", timeout=60)
    if args.strict_openai:
        require(checked_openai.get("gpt_5_5_available") is True, "gpt-5.5 model is not available")
        require(checked_openai.get("responses_smoke_status") == 200, f"Responses smoke failed: {checked_openai}")
        require(checked_openai.get("quota_state") == "ready", f"OpenAI quota state is not ready: {checked_openai.get('quota_state')}")

    draft = request_json(
        "POST",
        api_url(base, "/api/agents/drafts", employee_id),
        {
            "title": "Sandbox Evidence Analyst",
            "prompt": "Data Lake나 첨부 CSV를 분석해 판단 근거와 시각화 artifact를 만들어주세요.",
            "skills": ["data-analytics:analyze-data-quality", "data-analytics:visualize-data"],
            "mcp_servers": ["boi-wiki-local"],
            "scope": "private",
        },
        timeout=30,
    )["draft"]
    draft_test = request_json("POST", api_url(base, f"/api/agents/drafts/{draft['draft_id']}/test", employee_id), timeout=60)["test"]
    require(draft_test.get("sandbox_supported") is True, "draft test did not advertise sandbox support")
    if args.strict_openai:
        require(draft_test.get("runtime_backend") == "agents_sdk", f"draft test did not use Agents SDK: {draft_test}")
        require((draft_test.get("agents_sdk") or {}).get("ok") is True, f"Agents SDK draft test failed: {draft_test.get('agents_sdk')}")

    scenarios = [
        {
            "title": "Pressure Raw Data Evidence",
            "task": "압력 raw sample을 분석해 승인 판단에 필요한 계산 근거와 artifact를 만든다.",
            "marker": "pressure-sandbox-ok",
            "expected_artifacts": {"analysis.json", "pressure_chart.csv", "pressure_chart.html", "evidence_report.md"},
            "code": r"""
import csv
import json
from pathlib import Path

rows = [
    {"wafer": "WF-01", "pressure": 1.21, "raw_status": "ready"},
    {"wafer": "WF-02", "pressure": 1.18, "raw_status": "ready"},
    {"wafer": "WF-03", "pressure": 1.46, "raw_status": "missing"},
]
avg = sum(row["pressure"] for row in rows) / len(rows)
risk = "review_required" if any(row["raw_status"] == "missing" for row in rows) else "ready"
Path("analysis.json").write_text(json.dumps({"average_pressure": avg, "risk": risk, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
with Path("pressure_chart.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["wafer", "pressure", "raw_status"])
    writer.writeheader()
    writer.writerows(rows)
bars = "\n".join(
    f"<tr><td>{row['wafer']}</td><td><div style='width:{row['pressure'] * 160:.0f}px;background:#0f766e;color:white;padding:2px 6px'>{row['pressure']:.2f}</div></td><td>{row['raw_status']}</td></tr>"
    for row in rows
)
Path("pressure_chart.html").write_text(
    "<!doctype html><meta charset='utf-8'><title>Pressure Evidence</title>"
    "<h1>Pressure Evidence</h1><p>Approval review should check missing raw rows before accepting this evidence.</p>"
    "<table><thead><tr><th>Wafer</th><th>Pressure</th><th>Raw status</th></tr></thead><tbody>"
    + bars
    + "</tbody></table>",
    encoding="utf-8",
)
Path("evidence_report.md").write_text(
    f"# Evidence Report\n\nAverage pressure: {avg:.2f}\n\nRaw data status: {risk}\n",
    encoding="utf-8",
)
print("pressure-sandbox-ok")
""",
        },
        {
            "title": "Lot Yield Evidence",
            "task": "LOT별 yield table을 집계해 특이 LOT와 참고할 표 artifact를 만든다.",
            "marker": "yield-sandbox-ok",
            "expected_artifacts": {"yield_summary.json", "yield_table.csv", "yield_chart.html", "yield_report.md"},
            "code": r"""
import csv
import json
from pathlib import Path

rows = [
    {"lot": "LOT-A", "pass": 94, "fail": 6},
    {"lot": "LOT-B", "pass": 81, "fail": 19},
    {"lot": "LOT-C", "pass": 97, "fail": 3},
]
for row in rows:
    row["yield"] = round(row["pass"] / (row["pass"] + row["fail"]), 4)
lowest = min(rows, key=lambda row: row["yield"])
Path("yield_summary.json").write_text(json.dumps({"lowest_lot": lowest, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
with Path("yield_table.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["lot", "pass", "fail", "yield"])
    writer.writeheader()
    writer.writerows(rows)
bars = "\n".join(
    f"<tr><td>{row['lot']}</td><td><div style='width:{row['yield'] * 220:.0f}px;background:#2563eb;color:white;padding:2px 6px'>{row['yield']:.1%}</div></td><td>{row['fail']}</td></tr>"
    for row in rows
)
Path("yield_chart.html").write_text(
    "<!doctype html><meta charset='utf-8'><title>Yield Evidence</title>"
    "<h1>Yield Evidence</h1><p>LOT-B has the lowest sample yield and should be reviewed before approval.</p>"
    "<table><thead><tr><th>LOT</th><th>Yield</th><th>Fail count</th></tr></thead><tbody>"
    + bars
    + "</tbody></table>",
    encoding="utf-8",
)
Path("yield_report.md").write_text(f"# Yield Evidence\n\nLowest yield lot: {lowest['lot']} ({lowest['yield']:.1%})\n", encoding="utf-8")
print("yield-sandbox-ok")
""",
        },
        {
            "title": "Missing Raw Gate Evidence",
            "task": "필수 raw data 확보 여부를 검사하고 승인 전 추가 근거 요청 여부를 판단한다.",
            "marker": "missing-raw-sandbox-ok",
            "expected_artifacts": {"missing_raw_check.json", "missing_raw_report.md"},
            "code": r"""
import json
from pathlib import Path

required = ["trend_chart", "raw_endpoint", "maintenance_note"]
available = ["trend_chart", "maintenance_note"]
missing = [item for item in required if item not in available]
decision = "request_more_evidence" if missing else "ready_for_decision"
Path("missing_raw_check.json").write_text(json.dumps({"missing": missing, "decision": decision}, ensure_ascii=False, indent=2), encoding="utf-8")
Path("missing_raw_report.md").write_text("# Missing Raw Check\n\nMissing evidence: " + ", ".join(missing) + "\n", encoding="utf-8")
print("missing-raw-sandbox-ok")
""",
        },
    ]
    sandbox_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        sandbox_job = request_json(
            "POST",
            api_url(base, "/api/agents/sandbox/jobs", employee_id),
            {
                "title": scenario["title"],
                "task": scenario["task"],
                "language": "python",
                "code": scenario["code"],
                "evidence_intent": "approval_decision_support",
                "user_confirmed": True,
            },
            timeout=90,
        )["job"]
        require(sandbox_job.get("execution_mode") == "agents_sdk_unix_local", f"sandbox did not execute through Agents SDK unix local: {sandbox_job.get('execution_mode')}")
        require(sandbox_job.get("status") == "completed", f"sandbox job did not complete: {sandbox_job.get('status')}")
        require(str(scenario["marker"]) in str(sandbox_job.get("stdout") or ""), "sandbox stdout does not include scenario marker")
        artifact_paths = {str(item.get("path")) for item in sandbox_job.get("artifacts") or []}
        require(set(scenario["expected_artifacts"]).issubset(artifact_paths), f"missing expected artifacts for {scenario['title']}: {artifact_paths}")
        if args.strict_openai:
            summary = sandbox_job.get("agents_sdk_summary") or {}
            require(summary.get("ok") is True, f"gpt-5.5 sandbox summary failed: {summary}")
            require(summary.get("model") == "gpt-5.5", f"sandbox summary did not use gpt-5.5: {summary}")

        adopted = request_json(
            "POST",
            api_url(base, f"/api/agents/sandbox/jobs/{sandbox_job['job_id']}/adopt-evidence", employee_id),
            {
                "evidence_state": "verified_evidence",
                "validation_note": "source refs, code, runtime output, and artifacts checked by harness",
                "source_refs": [{"type": "sandbox_job", "id": sandbox_job["job_id"]}],
                "user_confirmed": True,
            },
            timeout=30,
        )["job"]
        require(adopted.get("evidence_state") == "verified_evidence", "sandbox evidence was not adopted as verified_evidence")
        sandbox_results.append({"job": sandbox_job, "artifact_paths": sorted(artifact_paths)})

    attachment = request_json(
        "POST",
        api_url(base, "/api/inbox/reports/harness-report/attach-evidence", employee_id),
        {
            "evidence_refs": [
                {"type": "sandbox_job", "id": result["job"]["job_id"], "state": "verified_evidence"}
                for result in sandbox_results
            ],
            "note": "Harness-attached computational evidence",
            "user_confirmed": True,
        },
        timeout=30,
    )["attachment"]
    require(attachment.get("report_id") == "harness-report", "report attachment failed")

    if args.summary:
        print(
            json.dumps(
                {
                    "ok": True,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "openai": {
                        "active_model": openai_runtime.get("active_model"),
                        "checked_quota_state": checked_openai.get("quota_state"),
                        "responses_smoke_status": checked_openai.get("responses_smoke_status"),
                    },
                    "agents_sdk": {
                        "available": agents_runtime.get("available"),
                        "draft_backend": draft_test.get("runtime_backend"),
                    },
                    "sandbox": {
                        "job_count": len(sandbox_results),
                        "jobs": [
                            {
                                "job_id": result["job"]["job_id"],
                                "title": result["job"].get("title"),
                                "artifacts": result["artifact_paths"],
                                "summary_state": (result["job"].get("agents_sdk_summary") or {}).get("state"),
                            }
                            for result in sandbox_results
                        ],
                    },
                    "attachment_id": attachment.get("id"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"check_agent_sandbox failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
