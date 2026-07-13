from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from boi_api.app.task_execution import TaskExecutionStore
from boi_api.app.v2.a2ui import (
    ALLOWED_COMPONENTS,
    BOI_CATALOG_ID,
    compile_harness_review_surface,
    compile_surface,
    validate_surface,
)
from boi_api.app.v2.models import AgentTurnResponse, AnswerBlock, ArtifactRef, GraphQueryPlan
from boi_api.app.v2.service import AgentV2Service
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


def test_acceptance_fixture_has_decision_complete_50_scenario_matrix():
    payload = yaml.safe_load((ROOT / "tests/fixtures/task_ontology_a2ui_acceptance.yaml").read_text(encoding="utf-8"))
    groups = payload["groups"]
    assert {key: len(value) for key, value in groups.items()} == {
        "task": 10,
        "graph": 10,
        "a2ui": 6,
        "learning": 6,
        "harness_improvement": 6,
        "integration_completion": 12,
    }
    scenario_ids = [item["id"] for items in groups.values() for item in items]
    assert len(scenario_ids) == len(set(scenario_ids)) == 50
    assert all(item.get("handler", "").startswith("tests/") for items in groups.values() for item in items)
    assert len(payload["multiturn"]) >= 6
    assert all(len(item["turns"]) >= 2 for item in payload["multiturn"])
    assert payload["thresholds"]["citation_integrity"] == 1.0
    assert payload["thresholds"]["unauthorized_mutations"] == 0


def test_browser_acceptance_manifest_covers_four_viewports_and_fifteen_real_journeys():
    payload = yaml.safe_load((ROOT / "tests/fixtures/task_ontology_a2ui_browser_scenarios.yaml").read_text(encoding="utf-8"))
    assert {(item["width"], item["height"]) for item in payload["viewports"]} == {
        (1440, 1000),
        (1180, 850),
        (949, 1151),
        (390, 844),
    }
    journey_ids = {item["id"] for item in payload["journeys"]}
    assert journey_ids == {
        "inbox_to_task_work_record",
        "task_assignment_and_revision",
        "task_work_record_persistence",
        "ontology_one_hop_expand",
        "agent_a2ui_and_fallback",
        "inbox_task_snapshot_parity",
        "ontology_path",
        "ontology_impact",
        "ontology_tour",
        "ontology_semantic_queries",
        "agent_table_timeline_mermaid",
        "harness_review_release_rehearsal",
        "adapter_job_status_and_retry",
        "mobile_focus_and_fallback",
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


def test_harness_review_surface_explains_failures_trial_and_non_deployment():
    surface = compile_harness_review_surface(
        {
            "candidate_id": "hcandidate-1",
            "rationale": "반복되는 근거 누락을 줄이기 위한 제한된 검색 정책 시험입니다.",
            "changes": {"retrieval_policy": {"authority_weight": 1.1}},
            "status": "review_required",
            "created_at": "2026-07-13T00:00:00+00:00",
        },
        failure_patterns=[{"summary": "검증된 근거 누락", "occurrence_count": 3, "status": "open"}],
        shadow_run={"status": "preflight_passed"},
        evaluation={"qualified": True},
    )

    validate_surface(surface)
    summaries = [item["props"].get("summary") for item in surface["components"]]
    assert "반복해서 막힌 이유" in summaries
    assert "시험과 운영 경계" in summaries
    assert surface["fallback"]["production_changed"] is False
    assert all(item["component"] in {"Answer", "DecisionSummary"} for item in surface["components"])


def test_harness_candidate_opens_rendered_review_page_instead_of_raw_surface(boi_app_module):
    client = TestClient(boi_app_module.app)
    service = boi_app_module.AGENT_V2_SERVICE
    candidate_id = "hcandidate-browser-review"
    service.store.put(
        "harness_candidates",
        candidate_id,
        {
            "candidate_id": candidate_id,
            "employee_id": "100001",
            "harness_id": "context.work",
            "base_version": "1.1",
            "model_profile": service.learning.model_profile,
            "rationale": "반복되는 근거 누락을 제한된 retrieval 변경으로 시험합니다.",
            "changes": {"retrieval_policy": {"authority_weight": 1.1}},
            "status": "review_required",
            "latest_eval_id": "heval-browser-review",
            "created_at": "2026-07-13T00:00:00+00:00",
        },
    )
    service.store.put(
        "harness_eval_runs",
        "heval-browser-review",
        {"eval_id": "heval-browser-review", "candidate_id": candidate_id, "qualified": True},
    )

    response = client.get(f"/harness-candidates/{candidate_id}?employee_id=100001")

    assert response.status_code == 200
    assert "업무 실행 품질 개선 검토" in response.text
    assert 'data-a2ui-component-id="candidate-summary"' in response.text
    assert "배포 검토 승인" in response.text
    assert "/api/v2/harness-candidates/" not in response.url.path


@pytest.mark.parametrize(
    ("presentation", "component"),
    [("table", "DataTable"), ("timeline", "Timeline"), ("mermaid", "MermaidArtifact"), ("explorer", "OntologyExplorer")],
)
def test_ontology_result_uses_the_requested_dynamic_presentation(presentation, component):
    response = AgentTurnResponse(
        run_id=f"run-{presentation}",
        turn_id=f"turn-{presentation}",
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="업무 관계", markdown="검증된 업무 관계"),
        artifact_refs=[
            ArtifactRef(
                artifact_id="artifact-graph",
                artifact_type="ontology_graph",
                title="업무 관계",
                metadata={"presentation": presentation},
            )
        ],
    )

    surface = compile_surface(response)
    assert component in {item["component"] for item in surface["components"]}


def test_mermaid_graph_is_grounded_connected_and_bounded_around_focal_entity():
    nodes = [
        {"node_id": f"node:{index}", "node_type": "boi", "payload": {"title": f"Node {index}"}}
        for index in range(24)
    ]
    edges = [
        {
            "edge_id": f"edge:{index}",
            "source_id": f"node:{index}",
            "target_id": f"node:{index + 1}",
            "relation": "links_to",
            "payload": {"source_refs": [f"boi:public:source:{index}"]},
        }
        for index in range(23)
    ]
    edges.append(
        {
            "edge_id": "edge:ungrounded",
            "source_id": "node:0",
            "target_id": "node:23",
            "relation": "links_to",
            "payload": {},
        }
    )

    selected_nodes, selected_edges = AgentV2Service._bounded_mermaid_graph(
        GraphQueryPlan(focal_entities=["node:0"], presentation="mermaid", depth=6),
        nodes,
        edges,
    )

    node_ids = {item["node_id"] for item in selected_nodes}
    assert "node:0" in node_ids
    assert len(selected_nodes) <= 14
    assert len(selected_edges) <= 20
    assert all({item["source_id"], item["target_id"]} <= node_ids for item in selected_edges)
    assert all(item["payload"]["source_refs"] for item in selected_edges)
    assert "edge:ungrounded" not in {item["edge_id"] for item in selected_edges}


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


def test_a2ui_validator_rejects_component_props_that_do_not_match_catalog_schema():
    response = AgentTurnResponse(
        run_id="run-props",
        turn_id="turn-props",
        status="completed",
        capability_id="knowledge.search",
        answer=AnswerBlock(summary="요약", markdown="근거 기반 답변"),
    )
    surface = compile_surface(response)
    surface["components"][0]["props"]["summary"] = ["문자열이 아님"]

    with pytest.raises(ValueError, match="invalid_a2ui_component_props"):
        validate_surface(surface)


def test_task_console_is_rendered_from_a_valid_stored_a2ui_work_form(boi_app_module):
    client = TestClient(boi_app_module.app)
    item = _create_task(boi_app_module, "task-a2ui-work-form")

    snapshot = client.get(f"/api/tasks/{item['task_ref']}/execution-snapshot?employee_id=100001")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    surface = validate_surface(payload["a2ui_surface"])
    components = {item["component"]: item for item in surface["components"]}
    assert {"TaskStatus", "WorkRecordForm", "EvidencePicker"} <= set(components)
    field_names = {item["name"] for item in components["WorkRecordForm"]["props"]["fields"]}
    assert {
        "observation", "action_taken", "decision", "outcome",
        "evidence_refs", "blocker", "next_work",
    } <= field_names

    stored = client.get(f"/api/v2/a2ui-surfaces/{surface['surface_id']}?employee_id=100001")
    assert stored.status_code == 200
    assert stored.json()["catalog_id"] == BOI_CATALOG_ID

    page = client.get(f"/tasks/console?employee_id=100001&task_id={item['task_ref']}")
    assert page.status_code == 200
    assert 'data-a2ui-component="WorkRecordForm"' in page.text
    assert 'data-a2ui-component="EvidencePicker"' in page.text
    assert 'name="observation"' in page.text and 'name="decision"' in page.text
    assert "누가 이 업무를 맡나요?" in page.text
    assert page.text.count("data-directory-picker") >= 3
    assert "사번, 이름 또는 부서로 찾기" in page.text
    assert "data-task-assignment-save" in page.text


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
    assert completed.json()["record"]["evidence_refs"] == ["human-note:multi-assignee-1"]
    assert not any(item["request_id"] == request_id for item in boi_app_module.agent_inbox_payload("100001", limit=100)["items"])
    assert not any(item["request_id"] == request_id for item in boi_app_module.agent_inbox_payload("100002", limit=100)["items"])


def test_inbox_batch_and_task_console_share_the_same_trace_workflow_snapshot(boi_app_module):
    client = TestClient(boi_app_module.app)
    item = _create_task(boi_app_module, "snapshot-workflow-parity")

    snapshot = client.get(
        f"/api/tasks/{item['task_ref']}/execution-snapshot?employee_id=100001"
    )
    batch = client.post(
        "/api/inbox/workflow-canvases?employee_id=100001",
        json={"task_refs": [item["task_ref"]]},
    )

    assert snapshot.status_code == batch.status_code == 200
    snapshot_payload = snapshot.json()
    batch_item = batch.json()["items"][0]
    assert snapshot_payload["source_signature"]
    assert batch_item["state"] == "ready"
    assert batch_item["canvas"]["source"] == snapshot_payload["workflow_canvas"]["source"]
    assert batch_item["canvas"]["current_stage_id"] == snapshot_payload["workflow_canvas"]["current_stage_id"]


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
