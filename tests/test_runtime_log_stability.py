from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient


def _today_action_log_name(boi_app_module) -> str:
    return f"actions-{boi_app_module.datetime.now(boi_app_module.KST).strftime('%Y%m%d')}.jsonl"


def _today_event_log_name(boi_app_module) -> str:
    return f"events-{boi_app_module.datetime.now(boi_app_module.KST).strftime('%Y%m%d')}.jsonl"


def test_action_append_rotates_to_segment_and_writes_index(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_LOG_MAX_BYTES", 120, raising=False)
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_INDEX_ENABLED", True, raising=False)
    boi_app_module.ensure_dirs()
    base = boi_app_module.ACTION_LOG_ROOT / _today_action_log_name(boi_app_module)
    base.write_text(json.dumps({"existing": "x" * 180}) + "\n", encoding="utf-8")

    row = boi_app_module.append_action_log_row(
        {
            "action_key": "sop.equipment.request_raw_data",
            "request_id": "act-runtime-rotation",
            "event_type": "maintenance.guide.requested.v1",
            "trace_id": "trace-runtime-rotation",
            "status": "invoked",
            "employee_id": "100001",
        }
    )

    assert row["_log_ref"].startswith("action:actions-")
    assert "-0002.jsonl:" in row["_log_ref"]
    segment_name = row["_log_ref"].split(":")[1]
    segment_path = boi_app_module.ACTION_LOG_ROOT / segment_name
    assert segment_path.exists()
    index_path = boi_app_module.runtime_log_index_path(segment_path)
    assert index_path.exists()
    indexed = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert indexed[-1]["request_id"] == "act-runtime-rotation"
    assert indexed[-1]["log_ref"] == row["_log_ref"]
    assert boi_app_module.find_action_log_row_by_ref(row["_log_ref"], "100001")["request_id"] == "act-runtime-rotation"


def test_event_append_rotates_to_segment_and_writes_index(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_LOG_MAX_BYTES", 120, raising=False)
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_INDEX_ENABLED", True, raising=False)
    boi_app_module.ensure_dirs()
    base = boi_app_module.EVENTS_ROOT / _today_event_log_name(boi_app_module)
    base.write_text(json.dumps({"existing": "x" * 180}) + "\n", encoding="utf-8")

    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-runtime-rotation",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": "trace-runtime-rotation",
            "producer": "pytest",
            "actor": {"employee_id": "100001"},
            "payload": {"title": "rotation smoke"},
        },
    )

    segments = sorted(boi_app_module.EVENTS_ROOT.glob("events-*-0002.jsonl"))
    assert len(segments) == 1
    index_path = boi_app_module.runtime_log_index_path(segments[0])
    assert index_path.exists()
    indexed = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert indexed[-1]["event_id"] == "evt-runtime-rotation"
    assert boi_app_module.find_event_log_row_by_ref(indexed[-1]["log_ref"])["event_id"] == "evt-runtime-rotation"


def test_action_history_filter_uses_index_before_full_scan(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_LOG_MAX_BYTES", 10_000, raising=False)
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_INDEX_ENABLED", True, raising=False)
    appended = boi_app_module.append_action_log_row(
        {
            "action_key": "sop.equipment.request_raw_data",
            "request_id": "act-index-filter",
            "event_type": "maintenance.guide.requested.v1",
            "trace_id": "trace-index-filter",
            "status": "failed",
            "employee_id": "100001",
            "connector_kind": "api",
        }
    )
    assert appended["_log_ref"]

    def fail_full_scan():
        raise AssertionError("full action log scan should not be required for indexed filters")

    monkeypatch.setattr(boi_app_module, "cached_action_log_rows", fail_full_scan)
    payload = boi_app_module.filter_action_logs_payload(
        employee_id="100001",
        action_key="sop.equipment.request_raw_data",
        status="failed",
        limit=10,
    )

    assert payload["total"] == 1
    assert payload["items"][0]["request_id"] == "act-index-filter"


def test_source_edit_candidate_lint_does_not_copy_runtime_logs(boi_app_module, monkeypatch):
    copied: list[Path] = []
    original_copy = boi_app_module.copy_optional_tree

    def record_copy(source: Path, target: Path) -> None:
        copied.append(source)
        original_copy(source, target)

    monkeypatch.setattr(boi_app_module, "copy_optional_tree", record_copy)
    source_path = boi_app_module.DATA_ROOT / "public" / "index.md"
    content = source_path.read_text(encoding="utf-8")

    report = boi_app_module.candidate_okf_lint_report(source_path, content)

    assert report is not None
    assert boi_app_module.DATA_ROOT in copied
    assert boi_app_module.EVENTS_ROOT not in copied
    assert boi_app_module.ACTION_LOG_ROOT not in copied


def test_runtime_log_health_api_reports_largest_files(boi_app_module, monkeypatch):
    monkeypatch.setattr(boi_app_module, "BOI_RUNTIME_LOG_MAX_BYTES", 120, raising=False)
    boi_app_module.ensure_dirs()
    (boi_app_module.ACTION_LOG_ROOT / "actions-20990101.jsonl").write_text("{}\n", encoding="utf-8")
    (boi_app_module.EVENTS_ROOT / "events-20990101.jsonl").write_text(json.dumps({"x": "y" * 180}) + "\n", encoding="utf-8")
    client = TestClient(boi_app_module.app)

    response = client.get("/api/runtime/log-health?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["summary"]["largest_file_bytes"] >= 120
    assert body["summary"]["warning_count"] >= 1
    assert any(item["kind"] == "event" for item in body["files"])


def test_runtime_git_guardrail_blocks_staged_runtime_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("ok\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    runtime_file = repo / "data" / "actions" / "actions-20990101.jsonl"
    runtime_file.parent.mkdir(parents=True)
    runtime_file.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", str(runtime_file.relative_to(repo))], cwd=repo, check=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_git_guardrails.py"
    result = subprocess.run(["python", str(script), "--root", str(repo)], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    assert result.returncode == 1
    assert "data/actions/actions-20990101.jsonl" in result.stdout


def test_runtime_git_guardrail_blocks_nested_generated_private_boi(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    generated = repo / "data" / "boi" / "private" / "100001" / "data-context" / "boi-private-100001-generated.md"
    generated.parent.mkdir(parents=True)
    generated.write_text("---\ntitle: generated\n---\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", str(generated.relative_to(repo))], cwd=repo, check=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_git_guardrails.py"
    result = subprocess.run(["python", str(script), "--root", str(repo)], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    assert result.returncode == 1
    assert "data/boi/private/100001/data-context/boi-private-100001-generated.md" in result.stdout


def test_runtime_git_guardrail_blocks_private_trash(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    trash = repo / "data" / "private-trash" / "100001" / "cleanup-test" / "manifest.json"
    trash.parent.mkdir(parents=True)
    trash.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", str(trash.relative_to(repo))], cwd=repo, check=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_git_guardrails.py"
    result = subprocess.run(["python", str(script), "--root", str(repo)], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    assert result.returncode == 1
    assert "data/private-trash/100001/cleanup-test/manifest.json" in result.stdout


def test_runtime_git_guardrail_allows_curated_catalog(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    curated = repo / "data" / "event_catalog" / "event_types.yaml"
    curated.parent.mkdir(parents=True)
    curated.write_text("event_types: []\n", encoding="utf-8")
    subprocess.run(["git", "add", str(curated.relative_to(repo))], cwd=repo, check=True)

    script = Path(__file__).resolve().parents[1] / "scripts" / "check_runtime_git_guardrails.py"
    result = subprocess.run(["python", str(script), "--root", str(repo)], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    assert result.returncode == 0
