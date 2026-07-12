from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from boi_api.app.task_execution import TaskExecutionStore
from boi_api.app.v2.a2ui import ALLOWED_COMPONENTS, BOI_CATALOG_ID, compile_surface, validate_surface
from boi_api.app.v2.models import AgentTurnResponse, AnswerBlock
from boi_api.app.v2.store import MemoryAgentV2Store
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def _create_task(boi_app_module, request_id: str, *, employee_id: str = "100001") -> dict:
    boi_app_module.append_action_log_row(
        {
            "request_id": request_id,
            "employee_id": employee_id,
            "trace_id": f"trace-{request_id}",
            "event_id": f"event-{request_id}",
            "event_type": "custom.assignment.requested.v1",
            "action_key": "manual.assignment.review",
            "status": "manual_required",
            "summary": f"{request_id} 확인 업무",
        }
    )
    return next(
        item
        for item in boi_app_module.agent_inbox_payload(employee_id, limit=100)["items"]
        if item["request_id"] == request_id
    )


def test_acceptance_fixture_has_decision_complete_32_scenario_matrix():
    payload = yaml.safe_load((ROOT / "tests/fixtures/task_ontology_a2ui_acceptance.yaml").read_text(encoding="utf-8"))
    groups = payload["groups"]
    assert {key: len(value) for key, value in groups.items()} == {"task": 10, "graph": 10, "a2ui": 6, "learning": 6}
    scenario_ids = [item["id"] for items in groups.values() for item in items]
    assert len(scenario_ids) == len(set(scenario_ids)) == 32
    assert len(payload["multiturn"]) >= 6
    assert all(len(item["turns"]) >= 2 for item in payload["multiturn"])
    assert payload["thresholds"]["citation_integrity"] == 1.0
    assert payload["thresholds"]["unauthorized_mutations"] == 0


def test_browser_acceptance_manifest_covers_three_viewports_and_core_journeys():
    payload = yaml.safe_load((ROOT / "tests/fixtures/task_ontology_a2ui_browser_scenarios.yaml").read_text(encoding="utf-8"))
    assert {(item["width"], item["height"]) for item in payload["viewports"]} == {
        (1440, 1000),
        (1180, 850),
        (390, 844),
    }
    journey_ids = {item["id"] for item in payload["journeys"]}
    assert journey_ids == {
        "inbox_to_task_work_record",
        "task_assignment_and_revision",
        "ontology_one_hop_expand",
        "agent_a2ui_and_fallback",
    }
    assert all(item["actions"] and item["assertions"] for item in payload["journeys"])


def test_task_execution_store_shares_assignment_and_records_between_assignees(tmp_path):
    store = TaskExecutionStore(tmp_path / "task-execution")
    row = {"request_id": "request-1", "employee_id": "100001"}

    assignment = store.update_assignment(
        row,
        actor_employee_id="100001",
        assignee_employee_ids=["100001", "100002", "100002"],
        reviewer_employee_ids=["100003"],
        related_team_ids=["platform"],
        expected_revision=0,
    )
    record = store.append_record(
        row,
        {
            "outcome": "progress",
            "observation": "Trend를 확인했습니다.",
            "evidence_refs": ["boi:public:evidence:trend"],
            "completed_check_ids": ["check-1"],
        },
        "100002",
    )

    assert assignment["completion_policy"] == "any_assignee"
    assert assignment["assignee_employee_ids"] == ["100001", "100002"]
    assert store.assignment(row)["revision"] == 1
    assert store.assignment_history(row)[0]["before"]["revision"] == 0
    assert store.assignment_history(row)[0]["after"]["revision"] == 1
    assert store.records(row)[0]["record_id"] == record["record_id"]
    assert store.records(row)[0]["actor_employee_id"] == "100002"


def test_memory_ontology_incremental_upsert_preserves_unaffected_nodes_and_removes_tombstones():
    store = MemoryAgentV2Store()
    store.upsert_ontology(
        [
            {"node_id": "boi:a", "node_type": "boi", "payload": {"title": "A"}},
            {"node_id": "boi:b", "node_type": "boi", "payload": {"title": "B"}},
        ],
        [{"edge_id": "edge:a-b", "source_id": "boi:a", "target_id": "boi:b", "relation": "related", "payload": {}}],
    )
    store.upsert_ontology(
        [{"node_id": "boi:a", "node_type": "boi", "payload": {"title": "A2"}}],
        [],
    )
    before = store.ontology_neighbors(["boi:a"], depth=1, limit=10, employee_id="100001", include_all=True)
    assert {item["node_id"] for item in before["nodes"]} == {"boi:a", "boi:b"}
    assert next(item for item in before["nodes"] if item["node_id"] == "boi:a")["payload"]["title"] == "A2"

    store.remove_ontology_entries(["boi:b"], ["edge:a-b"])
    after = store.ontology_neighbors(["boi:a"], depth=1, limit=10, employee_id="100001", include_all=True)
    assert {item["node_id"] for item in after["nodes"]} == {"boi:a"}
    assert after["edges"] == []


def test_a2ui_compiler_only_emits_trusted_catalog_components_and_keeps_fallback():
    response = AgentTurnResponse(
        run_id="run-1",
        turn_id="turn-1",
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="요약", markdown="근거 기반 답변"),
    )

    surface = compile_surface(response)

    assert surface["catalog_id"] == BOI_CATALOG_ID
    assert surface["fallback"]["answer"]["markdown"] == "근거 기반 답변"
    assert {item["component"] for item in surface["components"]} <= ALLOWED_COMPONENTS
    assert "createSurface" in surface["jsonl"]
    assert "updateComponents" in surface["jsonl"]


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda surface: surface["components"].append({"id": "x", "component": "RawHtml", "props": {}}), "unsupported_a2ui_component"),
        (lambda surface: surface["components"][0]["props"].update({"displayHtml": '<script>alert(1)</script>'}), "unsafe_a2ui_html"),
        (lambda surface: surface["components"][0]["props"].update({"url": "https://attacker.example"}), "external_a2ui_url"),
        (lambda surface: surface["events"].append({"event": "mutate"}), "unsupported_a2ui_event"),
    ],
)
def test_a2ui_validator_rejects_untrusted_components_html_urls_and_events(mutation, error):
    response = AgentTurnResponse(
        run_id="run-safe",
        turn_id="turn-safe",
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="요약", markdown="근거 기반 답변"),
    )
    surface = compile_surface(response)
    mutation(surface)
    with pytest.raises(ValueError, match=error):
        validate_surface(surface)


def test_multi_assignee_task_is_projected_to_each_inbox_and_completes_once(boi_app_module):
    client = TestClient(boi_app_module.app)
    request_id = "multi-assignee-task-1"
    boi_app_module.append_action_log_row(
        {
            "request_id": request_id,
            "employee_id": "100001",
            "trace_id": "trace-multi-assignee-1",
            "event_id": "event-multi-assignee-1",
            "event_type": "custom.assignment.requested.v1",
            "action_key": "manual.assignment.review",
            "status": "manual_required",
            "summary": "복수 담당자 확인 업무",
        }
    )
    owner_item = next(item for item in boi_app_module.agent_inbox_payload("100001", limit=100)["items"] if item["request_id"] == request_id)
    patch = client.patch(
        f"/api/tasks/{owner_item['task_ref']}/assignment?employee_id=100001",
        json={
            "assignee_employee_ids": ["100001", "100002"],
            "reviewer_employee_ids": [],
            "related_team_ids": ["platform"],
            "completion_policy": "any_assignee",
            "expected_revision": 0,
            "user_confirmed": True,
        },
    )
    assert patch.status_code == 200

    second_item = next(item for item in boi_app_module.agent_inbox_payload("100002", limit=100)["items"] if item["request_id"] == request_id)
    owner_snapshot = client.get(f"/api/tasks/{owner_item['task_ref']}/execution-snapshot?employee_id=100001")
    second_snapshot = client.get(f"/api/tasks/{second_item['task_ref']}/execution-snapshot?employee_id=100002")
    assert owner_snapshot.status_code == second_snapshot.status_code == 200
    assert owner_snapshot.json()["workflow_canvas"]["source"] == second_snapshot.json()["workflow_canvas"]["source"]
    checks = [item["check_id"] for item in second_snapshot.json()["completion"]["checks"]]

    completed = client.post(
        f"/api/tasks/{second_item['task_ref']}/work-records?employee_id=100002",
        json={
            "outcome": "completed",
            "observation": "업무 요청과 현재 상태를 확인했습니다.",
            "action_taken": "담당 기준에 따라 필요한 검토를 수행했습니다.",
            "decision": "요청한 확인이 끝나 공통 Task를 완료합니다.",
            "result": "검토 완료",
            "evidence_refs": ["human-note:multi-assignee-1"],
            "completed_check_ids": checks,
            "user_confirmed": True,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["record"]["actor_employee_id"] == "100002"
    assert not any(item["request_id"] == request_id for item in boi_app_module.agent_inbox_payload("100001", limit=100)["items"])
    assert not any(item["request_id"] == request_id for item in boi_app_module.agent_inbox_payload("100002", limit=100)["items"])


def test_task_work_record_progress_blocker_and_completion_contract(boi_app_module):
    client = TestClient(boi_app_module.app)
    item = _create_task(boi_app_module, "task-record-contract")
    endpoint = f"/api/tasks/{item['task_ref']}/work-records?employee_id=100001"

    progress = client.post(
        endpoint,
        json={
            "outcome": "blocked",
            "observation": "검토할 자료의 현재 상태를 확인했습니다.",
            "blocker": "원본 자료 접근 권한이 없습니다.",
            "next_work": "자료 소유자에게 접근 권한을 요청합니다.",
            "user_confirmed": True,
        },
    )
    assert progress.status_code == 200
    assert progress.json()["record"]["blocker"] == "원본 자료 접근 권한이 없습니다"

    snapshot = client.get(f"/api/tasks/{item['task_ref']}/execution-snapshot?employee_id=100001").json()
    checks = [check["check_id"] for check in snapshot["completion"]["checks"]]
    missing = client.post(
        endpoint,
        json={
            "outcome": "completed",
            "observation": "업무 상태를 확인했습니다.",
            "action_taken": "필요한 검토를 수행했습니다.",
            "decision": "완료로 판단했습니다.",
            "completed_check_ids": checks,
            "user_confirmed": True,
        },
    )
    assert missing.status_code == 400
    assert "확인한 자료" in missing.json()["detail"]

    inaccessible = client.post(
        endpoint,
        json={
            "outcome": "completed",
            "observation": "업무 상태를 확인했습니다.",
            "action_taken": "필요한 검토를 수행했습니다.",
            "decision": "완료로 판단했습니다.",
            "evidence_refs": ["artifact:other-users-private-file"],
            "completed_check_ids": checks,
            "user_confirmed": True,
        },
    )
    assert inaccessible.status_code == 400
    assert "접근" in inaccessible.json()["detail"]


def test_copilot_requires_human_decision_and_autopilot_rejects_human_record(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    copilot = _create_task(boi_app_module, "task-copilot-contract")
    monkeypatch.setattr(boi_app_module, "work_context_task_execution_mode", lambda _context, _requested="": "copilot")
    response = client.post(
        f"/api/tasks/{copilot['task_ref']}/work-records?employee_id=100001",
        json={
            "outcome": "completed",
            "observation": "AI가 근거 요약을 준비했습니다.",
            "action_taken": "요약을 검토했습니다.",
            "decision": "",
            "evidence_refs": ["human-note:copilot-review"],
            "completed_check_ids": ["check-1"],
            "user_confirmed": True,
        },
    )
    assert response.status_code == 400
    assert "판단" in response.json()["detail"]

    autopilot = _create_task(boi_app_module, "task-autopilot-contract")
    monkeypatch.setattr(boi_app_module, "work_context_task_execution_mode", lambda _context, _requested="": "autopilot")
    response = client.post(
        f"/api/tasks/{autopilot['task_ref']}/work-records?employee_id=100001",
        json={
            "outcome": "progress",
            "observation": "사람이 임의로 자동 결과를 기록하려고 했습니다.",
            "user_confirmed": True,
        },
    )
    assert response.status_code == 409
    assert "시스템 결과" in response.json()["detail"]


def test_assignment_revision_reviewer_and_unassigned_access(boi_app_module):
    client = TestClient(boi_app_module.app)
    item = _create_task(boi_app_module, "task-assignment-contract")
    endpoint = f"/api/tasks/{item['task_ref']}/assignment"
    first = client.patch(
        f"{endpoint}?employee_id=100001",
        json={
            "assignee_employee_ids": ["100001"],
            "reviewer_employee_ids": ["100002"],
            "related_team_ids": ["platform"],
            "expected_revision": 0,
            "user_confirmed": True,
        },
    )
    assert first.status_code == 200
    stale = client.patch(
        f"{endpoint}?employee_id=100001",
        json={
            "assignee_employee_ids": ["100001"],
            "reviewer_employee_ids": ["100002"],
            "related_team_ids": [],
            "expected_revision": 0,
            "user_confirmed": True,
        },
    )
    assert stale.status_code == 409

    reviewer = client.patch(
        f"{endpoint}?employee_id=100002",
        json={
            "assignee_employee_ids": ["100001", "100002"],
            "reviewer_employee_ids": ["100002"],
            "related_team_ids": ["platform"],
            "expected_revision": 1,
            "user_confirmed": True,
        },
    )
    assert reviewer.status_code == 200
    assert reviewer.json()["assignment_design"]["revision"] == 2
    forbidden = client.get(f"/api/tasks/{item['task_ref']}/execution-snapshot?employee_id=100003")
    assert forbidden.status_code in {403, 404}
