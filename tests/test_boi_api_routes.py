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
