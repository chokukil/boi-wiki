from __future__ import annotations

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
