from __future__ import annotations

from fastapi.testclient import TestClient

from boi_api.app.v2.models import WorkRoutineCreateRequest


def test_business_event_definition_dedupe_and_manual_run(boi_app_module):
    client = TestClient(boi_app_module.app)

    draft_response = client.post(
        "/api/business-event-definitions/drafts?employee_id=100001",
        json={
            "definition_id": "bed-test-alarm-immediate",
            "name": "설비 Alarm 대응 필요",
            "source_kind": "webhook",
            "source_name": "equipment-alarm",
            "target_event_type": "equipment.alarm.raised.v1",
            "occurrence_mode": "immediate",
            "payload_mapping": {"equipment_id": "$.equipment", "alarm_code": "$.alarm"},
            "fingerprint_fields": ["payload.equipment_id", "payload.alarm_code"],
            "dedupe_window_seconds": 600,
            "user_confirmed": True,
        },
    )
    assert draft_response.status_code == 200

    activate_response = client.post(
        "/api/business-event-definitions/bed-test-alarm-immediate/activate?employee_id=100001",
        json={"user_confirmed": True},
    )
    assert activate_response.status_code == 200

    first = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={
            "definition_id": "bed-test-alarm-immediate",
            "source_kind": "webhook",
            "source_name": "equipment-alarm",
            "signal": {"equipment": "ETCH-VM-01", "alarm": "PRESS-01"},
        },
    )
    second = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={
            "definition_id": "bed-test-alarm-immediate",
            "source_kind": "webhook",
            "source_name": "equipment-alarm",
            "signal": {"equipment": "ETCH-VM-01", "alarm": "PRESS-01"},
        },
    )

    assert first.status_code == 200
    assert first.json()["decision"] == "published"
    assert second.status_code == 200
    assert second.json()["decision"] == "suppressed"
    assert len(boi_app_module.AIOKafkaProducer.sent_events) == 1
    assert boi_app_module.AIOKafkaProducer.sent_events[0]["topic"] == boi_app_module.BOI_EVENTS_TOPIC

    run_response = client.post(
        "/api/business-event-definitions/bed-test-alarm-immediate/run?employee_id=100001",
        json={"payload": {"equipment_id": "ETCH-VM-02", "alarm_code": "PRESS-02"}, "user_confirmed": True},
    )
    assert run_response.status_code == 200
    assert run_response.json()["decision"] == "published"


def test_business_event_definition_repeated_transition_and_confirmation(boi_app_module):
    client = TestClient(boi_app_module.app)

    repeated = {
        "definition_id": "bed-test-repeated",
        "name": "반복 Alarm 대응 필요",
        "source_kind": "webhook",
        "source_name": "repeat-alarm",
        "target_event_type": "equipment.alarm.raised.v1",
        "occurrence_mode": "repeated",
        "fingerprint_fields": ["payload.equipment_id", "payload.alarm_code"],
        "threshold_count": 3,
        "dedupe_window_seconds": 600,
        "user_confirmed": True,
    }
    assert client.post("/api/business-event-definitions/drafts?employee_id=100001", json=repeated).status_code == 200
    assert client.post("/api/business-event-definitions/bed-test-repeated/activate?employee_id=100001", json={"user_confirmed": True}).status_code == 200

    decisions = [
        client.post(
            "/api/signals/evaluate?employee_id=100001",
            json={
                "definition_id": "bed-test-repeated",
                "source_kind": "webhook",
                "source_name": "repeat-alarm",
                "payload": {"equipment_id": "ETCH-VM-03", "alarm_code": "TEMP-01"},
            },
        ).json()["decision"]
        for _ in range(3)
    ]
    assert decisions == ["aggregated", "aggregated", "published"]

    transition = {
        "definition_id": "bed-test-transition",
        "name": "상태 전환 감지",
        "source_kind": "webhook",
        "source_name": "state-feed",
        "target_event_type": "equipment.alarm.raised.v1",
        "occurrence_mode": "transition",
        "conditions": {"state_field": "payload.status", "to_values": ["alarm"]},
        "fingerprint_fields": ["payload.equipment_id"],
        "user_confirmed": True,
    }
    assert client.post("/api/business-event-definitions/drafts?employee_id=100001", json=transition).status_code == 200
    assert client.post("/api/business-event-definitions/bed-test-transition/activate?employee_id=100001", json={"user_confirmed": True}).status_code == 200
    normal = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={"definition_id": "bed-test-transition", "payload": {"equipment_id": "ETCH-VM-04", "status": "normal"}},
    ).json()
    alarm = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={"definition_id": "bed-test-transition", "payload": {"equipment_id": "ETCH-VM-04", "status": "alarm"}},
    ).json()
    assert normal["decision"] == "ignored"
    assert alarm["decision"] == "published"

    confirmation = {
        "definition_id": "bed-test-confirm",
        "name": "담당자 확인 후 발생",
        "source_kind": "webhook",
        "source_name": "review-alarm",
        "target_event_type": "equipment.alarm.raised.v1",
        "occurrence_mode": "confirmation",
        "fingerprint_fields": ["payload.equipment_id", "payload.alarm_code"],
        "user_confirmed": True,
    }
    assert client.post("/api/business-event-definitions/drafts?employee_id=100001", json=confirmation).status_code == 200
    assert client.post("/api/business-event-definitions/bed-test-confirm/activate?employee_id=100001", json={"user_confirmed": True}).status_code == 200
    pending = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={"definition_id": "bed-test-confirm", "payload": {"equipment_id": "ETCH-VM-05", "alarm_code": "REVIEW-01"}},
    ).json()
    assert pending["decision"] == "pending_confirmation"
    confirmed = client.post(
        "/api/business-event-definitions/bed-test-confirm/confirm?employee_id=100001",
        json={"confirmation_id": pending["confirmation_id"], "decision": "confirm", "user_confirmed": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["decision"] == "published"


def test_business_event_ui_and_adapter_plan_are_user_facing(boi_app_module):
    client = TestClient(boi_app_module.app)

    page = client.get("/sops/new?employee_id=100001&focus=event")
    assert page.status_code == 200
    assert "업무 이벤트 정의" in page.text
    assert "이 업무 이벤트는 언제 발생하나요?" in page.text
    assert "반복되거나 계속되면 발생" in page.text
    assert "담당자가 확인하면 발생" in page.text
    assert "Adapter 초안 저장" not in page.text

    plan_response = client.post(
        "/api/event-ingestion/adapters/plan?employee_id=100001",
        json={
            "source_kind": "webhook",
            "source_name": "equipment-alarm",
            "target_event_type": "equipment.alarm.raised.v1",
            "occurrence_mode": "repeated",
            "payload_mapping": {"equipment_id": "$.equipment", "alarm_code": "$.alarm"},
            "fingerprint_fields": ["payload.equipment_id", "payload.alarm_code"],
            "threshold_count": 5,
            "sample_payload": {"equipment": "ETCH-VM-01", "alarm": "PRESS-01"},
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()["adapter_plan"]
    assert plan["business_event_definition"]["occurrence_mode"] == "repeated"
    assert plan["business_event_definition"]["threshold_count"] == 5
    assert plan["user_facing_summary"]["question"] == "이 업무 이벤트는 언제 발생하나요?"


def test_published_business_event_queues_the_linked_proactive_work_routine(boi_app_module):
    client = TestClient(boi_app_module.app)
    principal = boi_app_module.agent_v2_identity_for_employee("100001")
    routine = boi_app_module.AGENT_V2_SERVICE.create_work_routine(
        principal,
        WorkRoutineCreateRequest(
            title="Alarm 업무 맥락 확인",
            goal="발생한 Alarm과 관련된 SOP, 근거, 과거 사례를 확인해줘",
            capability_id="knowledge.search",
            trigger="event",
            event_ref="equipment.alarm.raised.v1",
            routine_stop="event_resolved",
        ),
    )
    definition_id = "bed-test-proactive-routine"
    draft = client.post(
        "/api/business-event-definitions/drafts?employee_id=100001",
        json={
            "definition_id": definition_id,
            "name": "Alarm 업무 맥락 확인 시작",
            "source_kind": "webhook",
            "source_name": "proactive-alarm",
            "target_event_type": "equipment.alarm.raised.v1",
            "occurrence_mode": "immediate",
            "fingerprint_fields": ["payload.equipment_id", "payload.alarm_code"],
            "work_routine_id": routine["routine_id"],
            "user_confirmed": True,
        },
    )
    assert draft.status_code == 200
    activated = client.post(
        f"/api/business-event-definitions/{definition_id}/activate?employee_id=100001",
        json={"user_confirmed": True},
    )
    assert activated.status_code == 200

    published = client.post(
        "/api/signals/evaluate?employee_id=100001",
        json={
            "definition_id": definition_id,
            "payload": {"equipment_id": "ETCH-VM-09", "alarm_code": "PRESS-09"},
        },
    )

    assert published.status_code == 200
    payload = published.json()
    assert payload["decision"] == "published"
    assert payload["work_routine"]["status"] == "queued"
    trigger = boi_app_module.AGENT_V2_SERVICE.store.get(
        "routine_triggers",
        payload["work_routine"]["trigger_id"],
    )
    assert trigger and trigger["routine_id"] == routine["routine_id"]
    assert trigger["request"]["source_fingerprint"] == payload["fingerprint"]


def test_scheduler_definition_activation_creates_durable_routine_and_internal_evaluation(boi_app_module):
    client = TestClient(boi_app_module.app)
    definition_id = "bed-test-scheduled-runtime"
    draft = client.post(
        "/api/business-event-definitions/drafts?employee_id=100001",
        json={
            "definition_id": definition_id,
            "name": "주간 설비 점검 시작",
            "source_kind": "scheduler",
            "source_name": "weekly-equipment-check",
            "target_event_type": "equipment.alarm.raised.v1",
            "occurrence_mode": "immediate",
            "schedule_config": {
                "repeat_type": "weekly",
                "time": "09:00",
                "weekdays": ["MON"],
                "timezone": "Asia/Seoul",
            },
            "default_payload": {"equipment_id": "ETCH-VM-SCHEDULED", "alarm_code": "WEEKLY-CHECK"},
            "user_confirmed": True,
        },
    )
    assert draft.status_code == 200

    activated = client.post(
        f"/api/business-event-definitions/{definition_id}/activate?employee_id=100001",
        json={"user_confirmed": True},
    )
    assert activated.status_code == 200
    definition = activated.json()["definition"]
    assert definition["status"] == "active"
    assert definition["scheduler_routine_id"]
    routine = boi_app_module.AGENT_V2_SERVICE.store.get("work_routines", definition["scheduler_routine_id"])
    assert routine["target_kind"] == "business_event"
    assert routine["target_ref"] == definition_id
    assert routine["next_run_at"]

    evaluated = client.post(
        f"/api/internal/business-event-definitions/{definition_id}/scheduled-evaluate",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "routine_id": definition["scheduler_routine_id"],
            "triggered_at": "2026-07-13T09:00:00+09:00",
            "payload": {},
            "employee_id": "100001",
        },
    )
    assert evaluated.status_code == 200
    payload = evaluated.json()
    assert payload["decision"] == "published"
    assert payload["scheduled_trigger"]["routine_id"] == definition["scheduler_routine_id"]
