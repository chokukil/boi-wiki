from __future__ import annotations

from boi_api.app.task_execution import TaskExecutionStore
from boi_api.app.v2.a2ui import ALLOWED_COMPONENTS, BOI_CATALOG_ID, compile_surface
from boi_api.app.v2.models import AgentTurnResponse, AnswerBlock
from boi_api.app.v2.store import MemoryAgentV2Store
from fastapi.testclient import TestClient


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
