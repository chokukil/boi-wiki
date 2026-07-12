from __future__ import annotations

import re

from fastapi.testclient import TestClient


def test_event_broker_navigation_opens_catalog_and_advanced_is_diagnostic_only(boi_app_module):
    client = TestClient(boi_app_module.app)

    catalog = client.get("/event-types?employee_id=100001")
    assert catalog.status_code == 200
    assert 'href="/event-types?employee_id=100001"' in catalog.text
    assert "Event 카탈로그" in catalog.text
    assert "업무 발생 이력" in catalog.text

    advanced = client.get("/advanced/api?employee_id=100001")
    assert advanced.status_code == 200
    assert "권한 관리" in advanced.text
    assert "연결 상태" in advanced.text
    subnav = re.search(r'<nav class="section-subnav".*?</nav>', advanced.text, flags=re.DOTALL)
    assert subnav
    assert ">BoI Agent<" not in subnav.group(0)
    assert ">BoI Agent 만들기<" not in subnav.group(0)


def test_business_event_occurrences_group_trace_and_keep_raw_details_out_of_default_ui(
    boi_app_module,
    monkeypatch,
):
    rows = [
        {
            "trace_id": "trace-business-1",
            "event_id": "event-1",
            "event_type": "report.requested.v1",
            "logged_at": "2026-07-12T10:00:00+09:00",
            "status": "received",
            "payload": {"title": "주간 보고서 검토"},
        },
        {
            "trace_id": "trace-smoke-1",
            "event_id": "event-smoke",
            "event_type": "boi.runtime.smoke.requested.v1",
            "logged_at": "2026-07-12T10:03:00+09:00",
            "status": "completed",
            "payload": {"title": "검증용 전체 경로"},
        },
        {
            "trace_id": "trace-business-1",
            "event_id": "event-2",
            "event_type": "report.completed.v1",
            "logged_at": "2026-07-12T10:02:00+09:00",
            "status": "completed",
            "payload": {"title": "주간 보고서 검토"},
        },
    ]
    monkeypatch.setattr(boi_app_module, "cached_action_log_rows", lambda: [])
    monkeypatch.setattr(boi_app_module, "workflow_for_event_type", lambda *_args, **_kwargs: (None, None, None))

    items = boi_app_module.business_event_occurrences(rows, employee_id="100001", doc_lookup={})

    assert len(items) == 1
    assert items[0]["event_count"] == 2
    assert items[0]["state"] == "completed"
    assert items[0]["title"] == "주간 보고서 검토"

    client = TestClient(boi_app_module.app)
    page = client.get("/events?employee_id=100001")
    assert page.status_code == 200
    assert "업무 발생 이력" in page.text
    assert "raw JSON" not in page.text


def test_public_v2_openapi_is_tagged_and_legacy_schema_is_marked(boi_app_module):
    client = TestClient(boi_app_module.app)

    public_schema = client.get("/openapi-v2.json").json()
    assert public_schema["info"]["version"] == "2.0"
    assert public_schema["x-boi-contract"]["profile"] == "external-v2"
    assert public_schema["paths"]
    assert "/api/boi/enrich-from-dispatch" not in public_schema["paths"]
    assert "/api/v2/evaluations/{evaluation_id}" not in public_schema["paths"]
    assert "/api/v2/usage/{usage_id}" not in public_schema["paths"]
    assert "/api/tasks/{task_ref}/execution-snapshot" in public_schema["paths"]
    assert "/api/tasks/{task_ref}/assignment" in public_schema["paths"]
    assert "/api/tasks/{task_ref}/work-records/preview" in public_schema["paths"]
    assert "/api/tasks/{task_ref}/work-records" in public_schema["paths"]
    assert public_schema["paths"]["/api/tasks/{task_ref}/work-records"]["post"]["tags"] == ["Work"]
    operation_ids = []
    for operations in public_schema["paths"].values():
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert operation.get("tags")
            assert operation.get("summary")
            assert operation.get("operationId")
            operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))

    compatibility_schema = client.get("/openapi.json").json()
    legacy = compatibility_schema["paths"].get("/api/agents/capabilities", {})
    if legacy:
        assert all(operation.get("deprecated") for operation in legacy.values() if isinstance(operation, dict))


def test_starter_suggestion_set_is_grounded_and_covers_business_areas(
    boi_app_module,
    monkeypatch,
):
    service = boi_app_module.AGENT_V2_SERVICE
    monkeypatch.setattr(service, "_refine_starter_suggestion_set", lambda *_args, **_kwargs: None)
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/v2/starter-suggestion-sets?employee_id=100001",
        json={"page_ref": "/event-types", "work_session_id": ""},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["set_id"].startswith("starterset_")
    assert payload["items"]
    assert sum(1 for item in payload["items"] if item["featured"]) <= 4
    assert {item["area"] for item in payload["items"]}.issubset(
        {"current_work", "knowledge", "workflow", "event_action", "learning", "automation"}
    )
    assert all(item["subject_ref"] and item["source_refs"] for item in payload["items"])
    assert all("index.md" not in item["subject_ref"] and "log.md" not in item["subject_ref"] for item in payload["items"])
    assert all(item["result_kind"] in {"answer", "table", "timeline", "mermaid", "explorer", "work_form", "confirmation"} for item in payload["items"])
    assert any(item["result_kind"] in {"table", "timeline", "mermaid", "explorer"} for item in payload["items"])


def test_code_evidence_is_an_admin_only_read_only_viewer(boi_app_module):
    client = TestClient(boi_app_module.app)
    path = "boi_api/app/v2/service.py"

    admin = client.get("/source/code", params={"employee_id": "100001", "path": path})
    viewer = client.get("/source/code", params={"employee_id": "100002", "path": path})

    assert admin.status_code == 200
    assert "읽기 전용" in admin.text
    assert "/api/source/apply" not in admin.text
    assert viewer.status_code == 403
