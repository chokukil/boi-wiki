from __future__ import annotations

import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def load_gateway_module(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ACTION_CATALOG_ROOT", str(Path.cwd() / "data" / "action_catalog"))
    monkeypatch.setenv("ACTION_LOG_ROOT", str(tmp_path / "actions"))
    monkeypatch.setenv("SERVICE_TOKEN", "test-service-token")
    sys.modules.pop("action_gateway.app.main", None)
    return importlib.import_module("action_gateway.app.main")


def test_manual_task_invocation_records_human_handoff_without_external_call(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.confirm_alarm_context",
            "employee_id": "100001",
            "event": {"event_id": "evt-manual-test", "event_type": "equipment.alarm.raised.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "manual_required"
    assert body["action_key"] == "manual.equipment.confirm_alarm_context"
    assert body["manual_handoff"]["owner"] == "AIX 확산 TF / 제조 PoC"

    logs = client.get("/api/actions/logs", headers={"x-service-token": "test-service-token"}).json()["items"]
    assert logs[0]["status"] == "manual_required"
    assert logs[0]["action_type"] == "manual_task"


def test_manual_approval_task_requires_approved_by_before_completion(tmp_path, monkeypatch):
    gateway = load_gateway_module(tmp_path, monkeypatch)
    client = TestClient(gateway.app)

    response = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.approve_process_hold",
            "employee_id": "100001",
            "event": {"event_id": "evt-approval-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "approval_required"
    assert body["action"]["type"] == "manual_task"

    approved = client.post(
        "/api/actions/invoke",
        headers={"x-service-token": "test-service-token"},
        json={
            "action_key": "manual.equipment.approve_process_hold",
            "employee_id": "100001",
            "event": {"event_id": "evt-approval-test", "event_type": "corrective_action.requested.v1"},
            "payload": {"equipment_id": "ETCH-VM-01", "owner": "100001"},
            "approved_by": "line-manager-001",
        },
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "manual_required"
    assert approved.json()["manual_handoff"]["approved_by"] == "line-manager-001"
