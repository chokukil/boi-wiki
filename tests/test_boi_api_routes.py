from __future__ import annotations

import re
from urllib.parse import unquote

from fastapi.testclient import TestClient


def test_sops_page_lists_seed_sops(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/sops?employee_id=100001")

    assert response.status_code == 200
    assert "Agent Harness SOP v0.1" in response.text
    assert "BoI Wiki SOP v0.1" in response.text


def test_runtime_config_exposes_sanitized_gemma_settings(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/runtime/config")

    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["base_url"] == "http://mangugil.iptime.org:1236/v1"
    assert body["llm"]["model"] == "google/gemma-4-26b-a4b-qat"
    assert body["llm"]["api_key_configured"] is True
    assert "api_key" not in body["llm"]


def test_boi_api_lists_accessible_docs_with_yaml_timestamps(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/boi?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any("AIX 확산 TF" in item["metadata"].get("title", "") for item in body["items"])


def test_equipment_anomaly_demo_route_publishes_first_event(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/workflows/demo/equipment-anomaly/start?employee_id=100001",
        json={
            "equipment_id": "ETCH-VM-01",
            "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            "title": "Response Chain 이상 Alarm 발생",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["workflow"]["name"] == "equipment-anomaly"
    assert body["workflow"]["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert body["workflow"]["sop_uri"] == "/public/sop/equipment-abnormal-response.md"
    assert body["workflow"]["status_url"].startswith("/api/workflows/demo/equipment-anomaly/status?trace_id=")
    assert "manual.equipment.confirm_alarm_context" in body["workflow"]["expected_manual_actions"]
    assert body["event"]["event_type"] == "equipment.alarm.raised.v1"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["topic"] == "boi.events"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["event"]["payload"]["equipment_id"] == "ETCH-VM-01"


def test_events_page_renders_structured_result_instead_of_raw_dict(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-rendering-test",
            "event_type": "corrective_action.requested.v1",
            "actor": "agent",
            "producer": "test",
            "trace_id": "trace-rendering-test",
            "payload": {"title": "렌더링 테스트"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {"ok": True, "status": "dispatched"},
            "body": '# Summary\n\n- 첫 번째 조치\n\n```json\n{"risk": "high", "approval_required": true}\n```',
        },
    )

    response = client.get("/events?employee_id=100001")

    assert response.status_code == 200
    assert "structured-data" in response.text
    assert '<div class="kv-key">routed_by</div>' in response.text
    assert "<h3>Summary</h3>" in response.text
    assert "<li>첫 번째 조치</li>" in response.text
    assert '<div class="kv-key">approval_required</div>' in response.text
    assert "{&#x27;routed_by&#x27;" not in response.text


def test_doc_page_renders_markdown_body(boi_app_module):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Markdown Rendering Test",
            "description": "Markdown 렌더링 확인",
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi-rendering-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "acl_policy": {"agent": "boi-writer-v0.1"},
            "status": "draft",
        },
        "# Summary\n\n본문이 **굵게** 보이고 `inline code`도 보입니다.\n\n| 항목 | 상태 |\n|---|---|\n| Markdown | OK |",
    )

    response = client.get("/docs/boi-rendering-test?employee_id=100001")
    uri_response = client.get(f"/docs{doc['uri']}?employee_id=100001")

    assert response.status_code == 200
    assert uri_response.status_code == 200
    assert '<div class="markdown-body rendered-content">' in response.text
    assert "<h3>Summary</h3>" in response.text
    assert "<strong>굵게</strong>" in response.text
    assert "<code>inline code</code>" in response.text
    assert '<table class="markdown-table">' in response.text
    assert "<pre class=\"markdown-body\">" not in response.text


def test_index_renders_okf_folder_tree_for_accessible_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001")

    assert response.status_code == 200
    assert 'class="library-layout"' in response.text
    assert "All Accessible" in response.text
    assert "public" in response.text
    assert "team/aix-tf" in response.text
    assert "team/platform" in response.text
    assert "private/100001" in response.text


def test_index_folder_filter_limits_documents_by_uri_prefix(boi_app_module):
    client = TestClient(boi_app_module.app)

    platform_response = client.get("/?employee_id=100001&folder=team/platform")
    private_response = client.get("/?employee_id=100001&folder=private/100001")

    assert platform_response.status_code == 200
    assert "Platform Team Kafka Event Broker SOP" in platform_response.text
    assert "AIX 확산 TF 업무 맥락 자산화 PoC 계획" not in platform_response.text
    assert "개인 Private BoI 예시" not in platform_response.text
    assert 'class="breadcrumb"' in platform_response.text

    assert private_response.status_code == 200
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" in private_response.text
    assert "Platform Team Kafka Event Broker SOP" not in private_response.text


def test_index_does_not_leak_inaccessible_folder_documents(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100002&folder=private/100001")

    assert response.status_code == 200
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" not in response.text
    assert "Platform Team Kafka Event Broker SOP" not in response.text
    assert 'class="empty-state"' in response.text


def test_boi_api_filters_by_okf_folder_and_returns_tree_context(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/boi?employee_id=100001&folder=team/platform")

    assert response.status_code == 200
    body = response.json()
    assert body["folder"] == "team/platform"
    assert body["count"] >= 1
    assert all(item["uri"].startswith("/team/platform/") for item in body["items"])
    assert any(item["label"] == "team" for item in body["breadcrumbs"])
    assert body["folder_tree"]["path"] == ""
    assert any(child["path"] == "team" for child in body["folder_tree"]["children"])


def test_doc_page_renders_metadata_as_readable_key_value_grid(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:team:platform:kafka-sop-v0.1?employee_id=100001")

    assert response.status_code == 200
    assert 'class="metadata-grid"' in response.text
    assert '<dt class="metadata-key">okf_version</dt>' in response.text
    assert '<dd class="metadata-value"><span class="scalar string">0.1</span></dd>' in response.text
    assert '<dt class="metadata-key">visibility</dt>' in response.text
    assert '<dd class="metadata-value"><span class="scalar string">team</span></dd>' in response.text
    assert '<dt class="metadata-key">acl_policy</dt>' in response.text
    assert '<dd class="metadata-value"><span class="scalar string">acl:team:platform</span></dd>' in response.text


def test_index_loads_library_script_and_prioritizes_library_surface(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=team/platform")

    assert response.status_code == 200
    assert '<script src="/static/library.js" defer></script>' in response.text
    assert response.text.index('id="boi-library"') < response.text.index('class="poc-guide"')
    assert 'href="/?employee_id=100001&amp;folder=team%2Fplatform"' in response.text
    assert 'aria-current="page"' in response.text


def test_index_partial_returns_only_library_fragment(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=team/platform&partial=library")

    assert response.status_code == 200
    assert 'id="boi-library"' in response.text
    assert 'class="library-layout"' in response.text
    assert "<header>" not in response.text
    assert "보이는 범위" not in response.text
    assert "Platform Team Kafka Event Broker SOP" in response.text
    assert "AIX 확산 TF 업무 맥락 자산화 PoC 계획" not in response.text


def test_index_partial_does_not_leak_inaccessible_documents(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100002&folder=private/100001&partial=library")

    assert response.status_code == 200
    assert 'id="boi-library"' in response.text
    assert 'class="empty-state"' in response.text
    assert "개인 Private BoI 예시: Langflow 컴포넌트 확인" not in response.text
    assert "Platform Team Kafka Event Broker SOP" not in response.text


def test_library_static_js_supports_partial_navigation(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/static/library.js")

    assert response.status_code == 200
    assert "history.pushState" in response.text
    assert "popstate" in response.text
    assert "partial" in response.text
    assert "scrollTo" in response.text


def test_public_sop_and_action_folders_are_browsable(boi_app_module):
    client = TestClient(boi_app_module.app)

    cases = {
        "public/sop": "설비 이상 감지·원인 분석·이상 조치 SOP",
        "public/actions": "Public Action Library",
        "public/actions/api": "Trend / 이력 확인 요청",
        "public/actions/webhook": "외부 Webhook 이벤트 수신",
        "public/actions/mcp": "MCP 기반 BoI 검색 Tool 호출 예시",
        "public/actions/langflow": "Langflow Reference Flow 호출 예시",
        "public/actions/manual": "공정 진행 금지 승인",
    }

    for folder, expected_title in cases.items():
        response = client.get(f"/?employee_id=100001&folder={folder}")
        assert response.status_code == 200
        assert expected_title in response.text


def test_action_catalog_page_links_public_action_specs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/actions?employee_id=100001&event_type=corrective_action.requested.v1")

    assert response.status_code == 200
    assert "manual.equipment.approve_process_hold" in response.text
    assert "manual handoff" in response.text
    assert "/docs/boi:public:actions:manual:approve-process-hold" in response.text
    assert "/docs/boi:public:actions:api:block-process-progress" in response.text


def test_materialized_equipment_boi_links_sop_and_action_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-equipment-docref-test",
            "event_type": "corrective_action.requested.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "이상 조치 요청 - ETCH-VM-01",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "owner": "100001",
            },
            "source_refs": [{"type": "event", "ref": "evt-source"}],
            "trace_id": "trace-equipment-docref-test",
        },
    )

    assert response.status_code == 200
    body = response.json()["item"]["body"]
    assert "SOP URI: `/public/sop/equipment-abnormal-response.md`" in body
    assert "boi:public:actions:api:block-process-progress" in body
    assert "boi:public:actions:api:change-spec-rule" in body
    assert "boi:public:actions:manual:approve-process-hold" in body
    assert "boi:public:actions:manual:approve-spec-rule-change" in body


def test_equipment_demo_status_summarizes_trace_context(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-test"

    boi_app_module.append_event_log(
        status="published",
        event={
            "event_id": "evt-status-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "상태 조회 테스트"},
        },
    )
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "상태 조회 테스트"},
        },
        result={"boi_id": "boi-status-test", "boi_uri": "/private/100001/boi-status-test.md"},
    )

    response = client.get(f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == trace_id
    assert body["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    assert body["sop_uri"] == "/public/sop/equipment-abnormal-response.md"
    assert any(item["event_type"] == "equipment.alarm.raised.v1" for item in body["events"])
    assert "manual.equipment.confirm_alarm_context" in body["manual_handoffs"]


def test_poc_equipment_api_endpoints_are_service_token_protected_and_callable(boi_app_module):
    client = TestClient(boi_app_module.app)

    unauthorized = client.post(
        "/api/poc/equipment/trend-history",
        json={"payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"}},
    )
    assert unauthorized.status_code == 401

    response = client.post(
        "/api/poc/equipment/trend-history",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01", "lot_id": "LOT-001", "wafer_id": "WF-001"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "invoked"
    assert body["result"]["trend_status"] == "anomaly_detected"
    assert body["result"]["lot_history_ref"].endswith("/LOT-001")


def test_poc_high_risk_api_requires_human_approval_even_if_called_directly(boi_app_module):
    client = TestClient(boi_app_module.app)

    rejected = client.post(
        "/api/poc/equipment/process-hold",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01"}, "dry_run": False},
    )
    assert rejected.status_code == 403
    assert rejected.json()["detail"]["status"] == "approval_required"

    approved = client.post(
        "/api/poc/equipment/process-hold",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"payload": {"equipment_id": "ETCH-VM-01"}, "dry_run": False, "approved_by": "line-manager-001"},
    )

    assert approved.status_code == 200
    assert approved.json()["status"] == "invoked"
    assert approved.json()["result"]["approved_by"] == "line-manager-001"


def test_poc_mcp_call_searches_accessible_boi_docs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/poc/mcp/call",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "server": {"name": "boi-wiki-mcp"},
            "tool": "boi.search",
            "arguments": {"query": "Kafka", "employee_id": "100001", "allowed_visibility": ["public", "team", "private"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "mcp_invoked"
    assert body["tool"] == "boi.search"
    assert any("Kafka" in item["title"] for item in body["results"])


def test_event_type_detail_page_explains_empty_boi_state_and_links_specs(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/event-types/meeting.closed.v1?employee_id=100001")

    assert response.status_code == 200
    assert "회의 종료" in response.text
    assert "meeting.closed.v1" in response.text
    assert "아직 이 Event Type으로 생성된 BoI가 없습니다" in response.text
    assert "/events?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "/actions?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "python scripts/publish_event.py meeting.closed.v1 --employee 100001" in response.text
    assert "boi:public:actions:boi-writer:materialize-event" in response.text


def test_event_type_catalog_uses_detail_route_as_primary_cta(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/event-types?employee_id=100001")

    assert response.status_code == 200
    assert 'href="/event-types/meeting.closed.v1?employee_id=100001"' in response.text
    assert "Event Type 상세" in response.text


def test_index_event_type_filter_has_context_bar_and_specific_empty_state(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&event_type=meeting.closed.v1")

    assert response.status_code == 200
    assert 'class="event-context-bar"' in response.text
    assert "회의 종료" in response.text
    assert "/event-types/meeting.closed.v1?employee_id=100001" in response.text
    assert "/events?employee_id=100001&amp;event_type=meeting.closed.v1" in response.text
    assert "아직 이 Event Type으로 생성된 BoI가 없습니다" in response.text


def test_events_page_summarizes_dispatch_results_and_keeps_raw_json_collapsed(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-compact-render-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-compact-render-test",
            "event_type": "maintenance.guide.requested.v1",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "컴팩트 렌더링 테스트"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {
                "ok": True,
                "status": "dispatched",
                "boi_id": "boi:private:100001:compact:test",
                "results": [
                    {
                        "action_key": "boi.materialize_event",
                        "type": "boi_materialize",
                        "result": {
                            "status": "materialized",
                            "request_id": "act-1",
                            "response": {
                                "item": {
                                    "metadata": recovered_metadata("boi:private:100001:compact:test"),
                                    "uri": "/private/100001/compact-test.md",
                                    "body": "# Should stay inside raw JSON only",
                                }
                            },
                        },
                    },
                    {
                        "action_key": "sop.equipment.block_process_progress",
                        "type": "api",
                        "result": {"status": "approval_required", "request_id": "act-2", "doc_ref": "boi:public:actions:api:block-process-progress"},
                    },
                ],
            },
        },
    )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert 'class="action-summary-table"' in response.text
    assert "boi.materialize_event" in response.text
    assert "approval_required" in response.text
    assert "/docs/boi:private:100001:compact:test?employee_id=100001" in response.text
    assert 'class="raw-event-json"' in response.text
    assert "Should stay inside raw JSON only" not in response.text.split('class="raw-event-json"')[0]


def test_api_event_logs_can_filter_by_trace_id(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-trace-a", "event_type": "meeting.closed.v1", "trace_id": "trace-a", "payload": {"title": "A"}},
    )
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-trace-b", "event_type": "meeting.closed.v1", "trace_id": "trace-b", "payload": {"title": "B"}},
    )

    response = client.get("/api/events/log?trace_id=trace-a")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["event_id"] == "evt-trace-a"


def recovered_metadata(boi_id: str = "boi:private:100001:recovered:001") -> dict:
    return {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/action",
        "title": "Recovered Generated BoI",
        "description": "Recovered from materialized event log",
        "tags": ["SOP", "Recovery"],
        "timestamp": "2026-06-17T15:00:00+09:00",
        "boi_id": boi_id,
        "visibility": "private",
        "classification": "internal",
        "owner": "100001",
        "author": {"type": "agent", "agent_id": "boi-writer-v0.4"},
        "acl_policy": "acl:private:100001",
        "status": "draft",
        "source_event": {"event_id": "evt-recovered", "event_type": "corrective_action.requested.v1"},
        "event_type": "corrective_action.requested.v1",
    }


def append_materialized_log(boi_app_module, *, trace_id: str, boi_id: str, include_item: bool = True) -> None:
    action_result = {"status": "materialized", "request_id": "act-recovered"}
    if include_item:
        action_result["response"] = {
            "item": {
                "metadata": recovered_metadata(boi_id),
                "uri": "/private/100001/boi-private-100001-recovered-001.md",
                "body": "# Summary\n\nRecovered generated body",
            }
        }
    boi_app_module.append_event_log(
        status="processed",
        event={
            "event_id": "evt-recovered",
            "event_type": "corrective_action.requested.v1",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "Recovered Generated BoI"},
        },
        result={
            "routed_by": "event-router",
            "dispatch_result": {
                "ok": True,
                "status": "dispatched",
                "boi_id": boi_id,
                "results": [
                    {"action_key": "boi.materialize_event", "type": "boi_materialize", "result": action_result}
                ],
            },
        },
    )


def test_doc_page_recovers_generated_boi_from_materialized_event_log(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100001:recovered:001"
    append_materialized_log(boi_app_module, trace_id="trace-recovered-doc", boi_id=boi_id)

    response = client.get(f"/docs/{boi_id}?employee_id=100001")

    assert response.status_code == 200
    assert "Recovered Generated BoI" in response.text
    assert "Recovered generated body" in response.text
    assert "Recovered from event/action log" in response.text


def test_recovered_private_boi_is_not_visible_to_other_employee(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_id = "boi:private:100001:recovered:secret"
    append_materialized_log(boi_app_module, trace_id="trace-recovered-secret", boi_id=boi_id)

    response = client.get(f"/docs/{boi_id}?employee_id=100002")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Recovered Generated BoI" not in response.text
    assert "BoI not found or not accessible" in response.text


def test_missing_boi_returns_html_missing_page_instead_of_json_detail(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:private:100001:missing:no-log?employee_id=100001")

    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert response.text.lstrip().startswith("<!doctype html>")
    assert '{"detail"' not in response.text
    assert "BoI not found or not accessible" in response.text


def test_events_page_links_recoverable_generated_boi_and_marks_unrecoverable_boi(boi_app_module):
    client = TestClient(boi_app_module.app)
    recoverable_id = "boi:private:100001:recoverable:event"
    missing_id = "boi:private:100001:missing:event"
    append_materialized_log(boi_app_module, trace_id="trace-event-links", boi_id=recoverable_id)
    append_materialized_log(boi_app_module, trace_id="trace-event-links", boi_id=missing_id, include_item=False)

    response = client.get("/events?employee_id=100001&trace_id=trace-event-links")

    assert response.status_code == 200
    assert f"/docs/{recoverable_id}?employee_id=100001" in response.text
    assert "Generated BoI" in response.text
    assert "BoI missing" in response.text
    assert missing_id in response.text
    assert f'href="/docs/{missing_id}?employee_id=100001"' not in response.text


def test_events_page_does_not_render_doc_links_that_return_404(boi_app_module):
    client = TestClient(boi_app_module.app)
    recoverable_id = "boi:private:100001:crawl:ok"
    missing_id = "boi:private:100001:crawl:missing"
    append_materialized_log(boi_app_module, trace_id="trace-crawl-links", boi_id=recoverable_id)
    append_materialized_log(boi_app_module, trace_id="trace-crawl-links", boi_id=missing_id, include_item=False)

    response = client.get("/events?employee_id=100001&trace_id=trace-crawl-links")
    hrefs = [
        unquote(match)
        for match in re.findall(r'href="(/docs/[^"]+)"', response.text)
        if "employee_id=100001" in match
    ]

    assert hrefs
    for href in hrefs:
        linked = client.get(href)
        assert linked.status_code != 404, href
