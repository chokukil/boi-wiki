from __future__ import annotations

import json
import hashlib
import re
from urllib.parse import quote, unquote

from fastapi.testclient import TestClient
import yaml


def tiny_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01"
        b"\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def append_action_log_row(boi_app_module, row: dict, filename: str = "actions-20990101.jsonl") -> str:
    boi_app_module.ensure_dirs()
    path = boi_app_module.ACTION_LOG_ROOT / filename
    line_number = len(path.read_text(encoding="utf-8").splitlines()) + 1 if path.exists() else 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    boi_app_module._FILE_SIGNATURE_CACHE.clear()
    boi_app_module._ACTION_LOG_CACHE["signature"] = None
    boi_app_module._ACTION_LOG_CACHE["rows"] = []
    return f"action:{filename}:{line_number}"


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

    response = client.get("/api/boi?employee_id=100001&q=SOP")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any("SOP" in item["metadata"].get("title", "") for item in body["items"])


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


def test_events_page_uses_pagination_and_lazy_raw_json(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-lazy-events-test"
    large_payload = {"response": {"item": {"metadata": {"boi_id": "boi-large-raw-test"}, "body": "RAW_BODY_SHOULD_BE_LAZY"}}}
    for index in range(55):
        boi_app_module.append_event_log(
            status="handled",
            event={
                "event_id": f"evt-lazy-events-{index:02d}",
                "event_type": "equipment.alarm.raised.v1",
                "actor": "agent",
                "producer": "test",
                "trace_id": trace_id,
                "payload": {"title": f"Lazy 이벤트 {index:02d}"},
            },
            result={
                "routed_by": "event-router",
                "dispatch_result": {
                    "ok": True,
                    "status": "handled",
                    "results": [{"action_key": "boi.materialize_event", "result": large_payload}],
                },
            },
        )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert response.text.count('class="doc-row event-row"') == 50
    assert 'name="limit"' in response.text
    assert "Page 1" in response.text
    assert "Next" in response.text
    assert "Raw JSON 불러오기" in response.text
    assert "/api/events/raw/" in response.text
    assert "RAW_BODY_SHOULD_BE_LAZY" not in response.text


def test_event_raw_api_returns_single_row_payload(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-event-raw-api-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-event-raw-api-test",
            "event_type": "equipment.alarm.raised.v1",
            "actor": "agent",
            "producer": "test",
            "trace_id": trace_id,
            "payload": {"title": "Raw API 테스트"},
        },
        result={"raw_marker": "RAW_API_MARKER", "dispatch_result": {"ok": True, "status": "handled", "results": []}},
    )
    events = client.get(f"/events?employee_id=100001&trace_id={trace_id}").text
    match = re.search(r"/api/events/raw/([^?\"&]+)\?employee_id=100001", events)

    assert match
    response = client.get(f"/api/events/raw/{unquote(match.group(1))}?employee_id=100001")
    missing = client.get("/api/events/raw/no-such-row?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["row"]["result"]["raw_marker"] == "RAW_API_MARKER"
    assert body["row"]["trace_id"] == trace_id
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")


def test_action_raw_api_and_html_show_single_action_result_with_links(boi_app_module):
    client = TestClient(boi_app_module.app)
    log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-18T13:00:00+09:00",
            "action_key": "langflow.equipment.stage_analysis",
            "request_id": "act-action-raw-link",
            "employee_id": "100001",
            "event_id": "evt-action-raw-link",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": "trace-action-raw-link",
            "boi_id": "boi:private:100001:action:raw",
            "status": "langflow_invoked",
            "doc_ref": "boi:public:actions:langflow:stage-analysis",
            "result": {
                "message": "FULL_LANGFLOW_MESSAGE_START " + ("원본 결과 " * 80) + " FULL_LANGFLOW_MESSAGE_END",
                "headers": {"x-service-token": "secret-should-redact"},
            },
        },
    )
    encoded = quote(log_ref, safe="")

    api_response = client.get(f"/api/actions/raw/{encoded}?employee_id=100001")
    html_response = client.get(f"/actions/raw/{encoded}?employee_id=100001")
    missing = client.get("/api/actions/raw/no-such-row?employee_id=100001")

    assert api_response.status_code == 200
    assert api_response.json()["row"]["request_id"] == "act-action-raw-link"
    assert "FULL_LANGFLOW_MESSAGE_END" in api_response.json()["row"]["result"]["message"]
    assert api_response.json()["row"]["result"]["headers"]["x-service-token"] == "[REDACTED]"
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith("application/json")

    assert html_response.status_code == 200
    assert html_response.headers["content-type"].startswith("text/html")
    assert "Action Raw Detail" in html_response.text
    assert "FULL_LANGFLOW_MESSAGE_END" in html_response.text
    assert "/events?employee_id=100001&amp;event_id=evt-action-raw-link" in html_response.text
    assert "/workflows/equipment-anomaly/status?employee_id=100001&amp;trace_id=trace-action-raw-link" in html_response.text
    assert "/docs/boi:public:actions:langflow:stage-analysis?employee_id=100001" in html_response.text
    assert "secret-should-redact" not in html_response.text


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
    assert '<details class="metadata">' in response.text
    assert '<section class="metadata">' not in response.text
    assert response.text.index('<section class="body">') < response.text.index('<details class="metadata">')
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
        "public/event-types": "설비 Alarm 발생",
        "public/actions/api": "Trend / 이력 확인 요청",
        "public/actions/webhook": "외부 Webhook 이벤트 수신",
        "public/actions/mcp": "MCP 기반 BoI 검색 Tool 호출 예시",
        "public/actions/langflow": "Langflow Reference Flow 호출",
        "public/actions/manual": "공정 진행 금지 승인",
    }

    for folder, expected_title in cases.items():
        response = client.get(f"/?employee_id=100001&folder={folder}")
        assert response.status_code == 200
        assert expected_title in response.text


def test_doc_page_rewrites_okf_markdown_links_to_accessible_doc_routes(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert 'href="/docs/boi:public:actions:api:request-trend-history?employee_id=100001">Trend 확인</a>' in response.text
    assert 'href="/docs/boi:public:event-types:equipment.alarm.raised.v1?employee_id=100001">equipment.alarm.raised.v1</a>' in response.text
    assert 'href="/public/actions/api/request-trend-history.md"' not in response.text
    assert 'href="/public/event-types/equipment.alarm.raised.v1.md"' not in response.text
    assert "Relationship Graph" in response.text
    assert "Citations" in response.text


def test_doc_page_defers_relationship_graph_to_lazy_api(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert 'id="relationship-graph-panel"' in response.text
    assert 'data-graph-url="/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001"' in response.text
    assert "Load Relationship Graph" in response.text
    assert "public/sop/equipment-abnormal-response → public/actions/api/request-trend-history" not in response.text


def test_doc_relationship_graph_api_returns_doc_edges(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["concept_id"] == "public/sop/equipment-abnormal-response"
    assert any(edge["target"] == "public/actions/api/request-trend-history" for edge in body["outgoing"])
    assert "nodes" not in body


def test_doc_page_exposes_draft_only_source_edit_guidance(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:sop:equipment-abnormal-response?employee_id=100001")

    assert response.status_code == 200
    assert "Web edits are draft-only" not in response.text
    assert "Source 보기 / Draft 수정" in response.text
    assert "Body 수정" in response.text
    assert "Save Body Draft" in response.text
    assert "/source?employee_id=100001&amp;path=data%2Fboi%2Fpublic%2Fsop%2Fequipment-abnormal-response.md" in response.text
    assert "/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001" in response.text


def test_doc_body_draft_editor_saves_body_without_mutating_source_file(boi_app_module):
    client = TestClient(boi_app_module.app)
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")

    response = client.post(
        "/api/docs/boi:public:sop:equipment-abnormal-response/body-drafts?employee_id=100001",
        json={
            "base_sha256": boi_app_module.hashlib.sha256(before.encode("utf-8")).hexdigest(),
            "proposed_body": "# Edited Body Draft\n\n본문 draft 저장 테스트",
            "author": "100001",
            "note": "inline body editor test",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["draft_only"] is True
    assert body["message"] == "Draft saved only. An agent must apply, test, and commit this change."
    assert source_path.read_text(encoding="utf-8") == before
    draft_files = list((boi_app_module.DRAFT_ROOT / "source_edits").glob("*.json"))
    assert draft_files
    assert any("Edited Body Draft" in path.read_text(encoding="utf-8") for path in draft_files)


def test_action_spec_is_collapsed_by_default_and_source_citation_is_clickable(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/docs/boi:public:actions:api:change-spec-rule?employee_id=100001")

    assert response.status_code == 200
    assert '<details class="executable-spec"' in response.text
    assert '<section class="executable-spec"' not in response.text
    assert "data/action_catalog/actions.yaml" in response.text
    assert "/source?employee_id=100001&amp;path=data%2Faction_catalog%2Factions.yaml" in response.text


def test_action_catalog_source_api_is_valid_with_manual_high_risk_approvals(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/source?employee_id=100001&path=data/action_catalog/actions.yaml")

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "data/action_catalog/actions.yaml"
    assert body["validation"]["ok"] is True
    assert body["validation"]["errors"] == []


def test_source_page_opens_in_read_mode_before_editing(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/source?employee_id=100001&path=data/action_catalog/actions.yaml")

    assert response.status_code == 200
    assert "Source Viewer" in response.text
    assert '<section class="source-viewer" id="source-viewer">' in response.text
    assert '<button id="edit-source" type="button">수정</button>' in response.text
    assert '<section class="source-editor" id="source-editor" hidden>' in response.text
    assert "Save Draft는 원본 파일과 Git commit을 변경하지 않습니다." in response.text
    assert response.text.index('id="source-viewer"') < response.text.index('id="source-editor"')


def test_source_editor_saves_draft_without_mutating_source_file(boi_app_module):
    client = TestClient(boi_app_module.app)
    source_ref = "data/boi/public/sop/equipment-abnormal-response.md"
    source_path = boi_app_module.DATA_ROOT / "public" / "sop" / "equipment-abnormal-response.md"
    before = source_path.read_text(encoding="utf-8")

    source_response = client.get(f"/api/source?employee_id=100001&path={source_ref}")
    assert source_response.status_code == 200
    source = source_response.json()
    assert source["draft_only"] is True
    assert source["validation"]["ok"] is True

    draft_response = client.post(
        "/api/source/drafts?employee_id=100001",
        json={
            "path": source_ref,
            "base_sha256": source["sha256"],
            "proposed_content": before + "\n<!-- draft-only test -->\n",
            "author": "100001",
            "note": "test draft",
        },
    )

    assert draft_response.status_code == 200
    body = draft_response.json()
    assert body["status"] == "pending"
    assert body["message"] == "Draft saved only. An agent must apply, test, and commit this change."
    assert source_path.read_text(encoding="utf-8") == before
    draft_files = list((boi_app_module.DRAFT_ROOT / "source_edits").glob("*.json"))
    assert draft_files


def test_public_harness_docs_are_browsable(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/?employee_id=100001&folder=public/harness")

    assert response.status_code == 200
    assert "BoI Agent Harness Overview" in response.text
    assert "SOP Authoring Harness" in response.text
    assert "Action Authoring Harness" in response.text
    assert "Web Draft Editing Guide" in response.text


def test_doc_page_does_not_rescan_docs_for_each_markdown_link(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    repeated_links = "\n".join(
        "- [Trend 확인](/public/actions/api/request-trend-history.md)" for _ in range(8)
    )
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Repeated Link Rendering Test",
            "description": "Repeated OKF links should use the request doc index",
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi-repeated-link-rendering-test",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "acl_policy": {"agent": "boi-writer-v0.1"},
            "status": "draft",
        },
        "# Summary\n\n" + repeated_links,
    )
    original_find_doc_by_id = boi_app_module.find_doc_by_id
    calls: list[str] = []

    def counted_find_doc_by_id(ref, employee_id=None):
        calls.append(str(ref))
        return original_find_doc_by_id(ref, employee_id)

    monkeypatch.setattr(boi_app_module, "find_doc_by_id", counted_find_doc_by_id)

    response = client.get("/docs/boi-repeated-link-rendering-test?employee_id=100001")

    assert response.status_code == 200
    assert "boi:public:actions:api:request-trend-history" in response.text
    assert len(calls) <= 1


def test_doc_page_renders_okf_media_images_from_media_directory(boi_app_module):
    client = TestClient(boi_app_module.app)
    image_path = boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "_media" / "browser" / "media-render-test.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = tiny_png_bytes()
    image_path.write_bytes(image_bytes)
    digest = hashlib.sha256(image_bytes).hexdigest()
    (boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "_media" / "media-manifest.yaml").write_text(
        "media:\n"
        "  - path: /public/boi-wiki-manual/_media/browser/media-render-test.png\n"
        f"    sha256: {digest}\n"
        "    source_kind: test\n",
        encoding="utf-8",
    )
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/reference",
        "title": "Media Render Test",
        "description": "OKF media render test",
        "tags": ["Media"],
        "timestamp": boi_app_module.now_iso(),
        "boi_id": "boi:public:boi-wiki-manual:media-render-test",
        "visibility": "public",
        "classification": "internal",
        "owner": "AIX 확산 TF",
        "author": {"type": "agent", "agent_id": "test"},
        "acl_policy": "acl:public",
        "status": "reviewed",
        "source_refs": [{"type": "test", "ref": "media-render"}],
        "review": {"reviewer": "test", "review_status": "reviewed"},
    }
    doc_path = boi_app_module.DATA_ROOT / "public" / "boi-wiki-manual" / "media-render-test.md"
    doc_path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False)
        + "---\n\n# Summary\n\n![Workflow Status 화면](/public/boi-wiki-manual/_media/browser/media-render-test.png)\n",
        encoding="utf-8",
    )
    boi_app_module.invalidate_doc_caches()

    response = client.get("/docs/boi:public:boi-wiki-manual:media-render-test?employee_id=100001")
    media_response = client.get("/okf-media/public/boi-wiki-manual/_media/browser/media-render-test.png")
    blocked_response = client.get("/okf-media/public/boi-wiki-manual/media-render-test.md")

    assert response.status_code == 200
    assert '<figure class="okf-image">' in response.text
    assert 'alt="Workflow Status 화면"' in response.text
    assert "/okf-media/public/boi-wiki-manual/_media/browser/media-render-test.png" in response.text
    assert media_response.status_code == 200
    assert blocked_response.status_code == 404


def test_doc_graph_api_reuses_okf_graph_between_employee_requests(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    boi_app_module._OKF_GRAPH_CACHE.clear()
    original_okf_graph_for_docs = boi_app_module.okf_graph_for_docs
    calls = 0

    def counted_okf_graph_for_docs(docs, employee_id):
        nonlocal calls
        calls += 1
        return original_okf_graph_for_docs(docs, employee_id)

    monkeypatch.setattr(boi_app_module, "okf_graph_for_docs", counted_okf_graph_for_docs)

    response_one = client.get("/api/okf/graph/doc/boi:public:sop:equipment-abnormal-response?employee_id=100001")
    response_two = client.get("/api/okf/graph/doc/boi:team:platform:kafka-sop-v0.1?employee_id=100001")

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert calls == 1


def test_api_okf_graph_exposes_markdown_edges_and_backlinks(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.get("/api/okf/graph?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] > 0
    assert body["edge_count"] > 0
    assert any(node["concept_id"] == "public/sop/equipment-abnormal-response" for node in body["nodes"])
    assert any(
        edge["source"] == "public/sop/equipment-abnormal-response"
        and edge["target"] == "public/actions/api/request-trend-history"
        for edge in body["edges"]
    )
    trend_node = next(node for node in body["nodes"] if node["concept_id"] == "public/actions/api/request-trend-history")
    assert "public/sop/equipment-abnormal-response" in trend_node["backlinks"]


def test_okf_doc_graph_dedupes_repeated_markdown_edges(boi_app_module):
    client = TestClient(boi_app_module.app)
    doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Repeated Graph Link Test",
            "description": "Repeated OKF link graph test",
            "tags": ["Graph"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:private:100001:graph-dedupe",
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "test"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_refs": [{"type": "test", "ref": "graph-dedupe"}],
        },
        (
            "# Summary\n\n"
            "[SOP](/public/sop/equipment-abnormal-response.md)\n\n"
            "다시 [SOP](/public/sop/equipment-abnormal-response.md)\n"
        ),
    )

    response = client.get(f"/api/okf/graph/doc/{doc['metadata']['boi_id']}?employee_id=100001")

    assert response.status_code == 200
    body = response.json()
    matching = [
        edge
        for edge in body["outgoing"]
        if edge["target"] == "public/sop/equipment-abnormal-response" and edge["label"] == "SOP"
    ]
    assert len(matching) == 1
    assert matching[0]["occurrence_count"] == 2


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
    metadata = response.json()["item"]["metadata"]
    assert "[설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)" in body
    assert "[공정 진행 금지 요청](/public/actions/api/block-process-progress.md)" in body
    assert "[Spec / Rule 변경 요청](/public/actions/api/change-spec-rule.md)" in body
    assert "[공정 진행 금지 승인](/public/actions/manual/approve-process-hold.md)" in body
    assert "[Spec / Rule 변경 승인](/public/actions/manual/approve-spec-rule-change.md)" in body
    assert "# Citations" in body
    assert any(rel["type"] == "implements_sop" for rel in metadata["relations"])
    assert any(rel["type"] == "uses_action_spec" for rel in metadata["relations"])

    alarm_response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-equipment-langflow-docref-test",
            "event_type": "equipment.alarm.raised.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "Response Chain 이상 Alarm 발생",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "owner": "100001",
            },
            "source_refs": [{"type": "demo-workflow", "ref": "equipment-anomaly"}],
            "trace_id": "trace-equipment-langflow-docref-test",
        },
    )

    assert alarm_response.status_code == 200
    alarm_body = alarm_response.json()["item"]["body"]
    assert "[Langflow Reference Flow 호출](/public/actions/langflow/reference-flow.md)" in alarm_body


def test_root_cause_generated_boi_is_stage_execution_record_without_architecture_boilerplate(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-root-cause-stage-record",
            "event_type": "root_cause.analysis.requested.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {
                "title": "원인 분석 요청 - ETCH-VM-01",
                "equipment_id": "ETCH-VM-01",
                "lot_id": "LOT-POC-001",
                "wafer_id": "WF-POC-001",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
                "owner": "100001",
            },
            "source_refs": [{"type": "event", "ref": "evt-detect-stage"}],
            "trace_id": "trace-root-cause-stage-record",
        },
    )

    assert response.status_code == 200
    body = response.json()["item"]["body"]
    assert "# AI Native Workflow Interpretation" not in body
    assert "Event Broker는 업무 시점" not in body
    assert "첨부 SOP 사례를 AI Native Workflow로 실행하기 위한 Private BoI 인스턴스" not in body
    for section in [
        "# Event Snapshot",
        "# SOP Stage",
        "# Evidence / Inputs",
        "# Action Plan",
        "# Manual Handoff",
        "# Next Stage",
        "# Action Results",
        "# Citations",
    ]:
        assert section in body
    assert "[Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)" in body
    assert "[장비 보전 가이드 요청](/public/actions/api/request-maintenance-guide.md)" in body
    assert "[원인 후보 검토 및 판단](/public/actions/manual/review-root-cause.md)" in body
    assert "[장비 보전 가이드 요청](/public/event-types/maintenance.guide.requested.v1.md)" in body
    assert "pending enrichment" in body


def test_generated_boi_enrichment_adds_dispatch_results_and_langflow_analysis(boi_app_module):
    client = TestClient(boi_app_module.app)
    event = {
        "event_id": "evt-enrich-root-cause",
        "event_type": "root_cause.analysis.requested.v1",
        "actor": {"type": "human", "employee_id": "100001"},
        "trace_id": "trace-enrich-root-cause",
        "payload": {
            "title": "원인 분석 요청 - ETCH-VM-01",
            "equipment_id": "ETCH-VM-01",
            "lot_id": "LOT-POC-001",
            "wafer_id": "WF-POC-001",
            "owner": "100001",
        },
    }
    materialized = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json=event,
    )
    boi_id = materialized.json()["item"]["metadata"]["boi_id"]
    dispatch_result = {
        "ok": True,
        "status": "dispatched",
        "boi_id": boi_id,
        "results": [
            {
                "action_key": "sop.equipment.request_raw_data",
                "type": "api",
                "result": {
                    "status": "invoked",
                    "request_id": "act-raw-enrich",
                    "response": {
                        "result": {
                            "raw_data_ref": "/mock/hyvis/raw-data/ETCH-VM-01/LOT-POC-001",
                            "source_data_ref": "/mock/tas/source-data/ETCH-VM-01",
                            "message": "Raw/Source Data 참조 링크를 생성했습니다.",
                        }
                    },
                },
            },
            {
                "action_key": "langflow.equipment.stage_analysis",
                "type": "langflow_run",
                "result": {
                    "status": "langflow_invoked",
                    "request_id": "act-langflow-enrich",
                    "message": "## 업무 맥락 자산화\nEvent Broker는 업무 시점을 발행합니다.\n\n## 원인 후보\n원인 후보: RF 매칭 구간 이상 가능성이 높습니다.\n\n## Team BoI 승격 기준\n반복되면 승격합니다.",
                },
            },
            {
                "action_key": "manual.equipment.review_root_cause",
                "type": "manual_task",
                "result": {
                    "status": "manual_required",
                    "request_id": "act-manual-enrich",
                    "manual_handoff": {"owner": "AIX 확산 TF / 제조 PoC"},
                },
            },
        ],
    }

    response = client.post(
        "/api/boi/enrich-from-dispatch",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"employee_id": "100001", "event": event, "dispatch_result": dispatch_result},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["boi_id"] == boi_id
    assert body["enriched"] is True
    assert "Action Results" in body["sections_updated"]
    doc = boi_app_module.find_doc_by_id(boi_id, "100001")
    assert doc is not None
    enriched_body = doc["body"]
    assert "# Action Results" in enriched_body
    assert "# Analysis Draft" in enriched_body
    assert "/mock/hyvis/raw-data/ETCH-VM-01/LOT-POC-001" in enriched_body
    assert "원인 후보: RF 매칭 구간 이상 가능성이 높습니다." in enriched_body
    assert "Event Broker는 업무 시점을 발행합니다." not in enriched_body
    assert "Team BoI 승격 기준" not in enriched_body
    assert "manual_required" in enriched_body
    assert "pending enrichment" not in enriched_body


def test_enrichment_skips_non_generated_or_non_private_boi(boi_app_module):
    client = TestClient(boi_app_module.app)
    public_doc = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/reference",
            "title": "Public enrichment target",
            "description": "Should not be enriched",
            "tags": ["Test"],
            "timestamp": "2026-06-18T00:00:00+09:00",
            "boi_id": "boi:public:test:enrichment-skip",
            "visibility": "public",
            "classification": "internal",
            "owner": "AIX",
            "author": {"type": "human", "agent_id": "human"},
            "acl_policy": "acl:public",
            "status": "reviewed",
            "source_event": {"event_id": "evt-public-skip", "event_type": "root_cause.analysis.requested.v1"},
            "source_refs": [{"type": "test", "ref": "enrichment-skip"}],
            "review": {"reviewer": "tf-lead", "review_status": "reviewed"},
        },
        "# Summary\n\nOriginal public content",
    )

    response = client.post(
        "/api/boi/enrich-from-dispatch",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "employee_id": "100001",
            "event": {"event_id": "evt-public-skip", "event_type": "root_cause.analysis.requested.v1", "trace_id": "trace-public-skip"},
            "dispatch_result": {"boi_id": public_doc["metadata"]["boi_id"], "results": []},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["enriched"] is False
    assert body["skipped_reason"] == "not_generated_private_boi"


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
    assert "langflow.boi.reference_flow" in body["expected_actions"]
    assert "manual.equipment.confirm_alarm_context" in body["manual_handoffs"]
    assert "manual.equipment.confirm_alarm_context" in body["expected_manual_actions"]
    assert body["generated_boi_refs"] == body["generated_docs"]
    assert "relation_graph" in body
    assert body["relation_graph"]["node_count"] < 50


def test_generic_workflow_status_uses_sop_stage_registry(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-generic-workflow-registry"

    response = client.get(f"/api/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_key"] == "equipment-anomaly"
    assert body["sop_ref"] == "boi:public:sop:equipment-abnormal-response"
    stages = body["expected_stages"]
    assert [stage["sop_stage_id"] for stage in stages] == ["detect", "analyze", "guide", "correct"]
    assert stages[0]["event_types"] == ["equipment.alarm.raised.v1", "trend.anomaly.detected.v1"]
    assert sum(1 for stage in stages if stage["stage"] == "원인 분석") == 1
    assert "langflow.equipment.stage_analysis" in body["expected_actions"]
    assert "manual.equipment.review_root_cause" in body["expected_manual_actions"]
    assert body["status_page_url"].startswith("/workflows/equipment-anomaly/status?")


def test_generic_workflow_start_publishes_sop_entry_event(boi_app_module):
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/workflows/equipment-anomaly/start?employee_id=100001",
        json={
            "payload": {
                "title": "Generic workflow start",
                "equipment_id": "ETCH-VM-01",
                "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["workflow"]["workflow_key"] == "equipment-anomaly"
    assert body["workflow"]["first_event_type"] == "equipment.alarm.raised.v1"
    assert body["workflow"]["status_page_url"].startswith("/workflows/equipment-anomaly/status?")
    assert body["event"]["event_type"] == "equipment.alarm.raised.v1"
    assert boi_app_module.AIOKafkaProducer.sent_events[-1]["event"]["payload"]["equipment_id"] == "ETCH-VM-01"


def test_generic_workflow_status_page_groups_multiple_events_in_sop_stage(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-sop-stage-grouping"
    for event_id, event_type, title in [
        ("evt-stage-group-alarm", "equipment.alarm.raised.v1", "Alarm 발생"),
        ("evt-stage-group-trend", "trend.anomaly.detected.v1", "Trend 이상"),
        ("evt-stage-group-root", "root_cause.analysis.requested.v1", "원인 분석 요청"),
    ]:
        boi_app_module.append_event_log(
            status="handled",
            event={
                "event_id": event_id,
                "event_type": event_type,
                "trace_id": trace_id,
                "payload": {"title": title},
            },
            result={"dispatch_result": {"ok": True, "status": "handled", "results": []}},
        )

    response = client.get(f"/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert response.text.count('class="workflow-stage-row"') == 4
    assert "equipment.alarm.raised.v1" in response.text
    assert "trend.anomaly.detected.v1" in response.text
    assert response.text.count("<h3>원인 분석</h3>") == 1
    assert response.text.index("trend.anomaly.detected.v1") < response.text.index("<h3>원인 분석</h3>")


def test_custom_sop_event_materializes_workflow_boi_without_equipment_prefix(boi_app_module, tmp_path):
    client = TestClient(boi_app_module.app)
    custom_sop = boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/sop",
            "title": "Custom Ops SOP",
            "description": "Generic workflow registry fixture",
            "tags": ["SOP", "Workflow"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": "boi:public:sop:custom-ops",
            "visibility": "public",
            "classification": "internal",
            "owner": "workflow-team",
            "author": {"type": "human", "agent_id": "test"},
            "acl_policy": "acl:public",
            "status": "reviewed",
            "source_refs": [{"type": "test", "ref": "custom-sop"}],
            "review": {"reviewer": "test", "review_status": "reviewed"},
            "workflow": {
                "workflow_key": "custom-ops",
                "stages": [
                    {
                        "id": "triage",
                        "name": "Triage",
                        "entry_event": "custom.case.opened.v1",
                        "event_types": ["custom.case.opened.v1"],
                        "automated_actions": [],
                        "manual_actions": [],
                        "outputs": ["triage note"],
                    }
                ],
            },
        },
        "# Summary\n\nCustom workflow SOP",
    )
    catalog_root = tmp_path / "event_catalog"
    catalog_root.mkdir()
    (catalog_root / "event_types.yaml").write_text(
        yaml.safe_dump(
            {
                "event_types": [
                    {
                        "event_type": "custom.case.opened.v1",
                        "name_ko": "Custom Case Opened",
                        "default_boi_type": "boi/workflow-instance",
                        "default_flow_key": "custom-flow",
                        "workflow_stage": "Triage",
                        "sop_ref": custom_sop["metadata"]["boi_id"],
                        "sop_stage_id": "triage",
                        "recommended_actions": [],
                        "recommended_manual_actions": [],
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    boi_app_module.EVENT_CATALOG_ROOT = catalog_root
    boi_app_module._EVENT_TYPES_CACHE["signature"] = None
    boi_app_module._EVENT_TYPES_CACHE["items"] = []
    boi_app_module._FILE_SIGNATURE_CACHE.clear()

    response = client.post(
        "/api/events/handle",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={
            "event_id": "evt-custom-case-opened",
            "event_type": "custom.case.opened.v1",
            "actor": {"type": "human", "employee_id": "100001"},
            "payload": {"title": "Custom case opened", "case_id": "CASE-001", "owner": "100001"},
            "trace_id": "trace-custom-case-opened",
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["metadata"]["sop_ref"] == "boi:public:sop:custom-ops"
    assert item["metadata"]["sop_stage_id"] == "triage"
    assert "# SOP Stage" in item["body"]
    assert "Custom workflow SOP" not in item["body"]
    assert f"[Custom Ops SOP]({custom_sop['uri']})" in item["body"]
    assert "CASE-001" in item["body"]


def test_equipment_demo_status_renders_human_readable_html_for_browsers(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-html-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-html-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "HTML 상태 조회 테스트"},
        },
        result={
            "boi_id": "boi:private:100001:status-html-test",
            "boi_uri": "/private/100001/status-html-test.md",
            "dispatch_result": {
                "ok": True,
                "status": "handled",
                "results": [
                    {
                        "action_key": "langflow.boi.reference_flow",
                        "result": {
                            "status": "invoked",
                            "request_id": "act-status-html-test",
                            "doc_ref": "boi:public:actions:langflow:reference-flow",
                            "response": {
                                "item": {
                                    "metadata": {"boi_id": "boi:private:100001:status-html-test"},
                                    "body": "INLINE_RAW_BODY_SHOULD_NOT_RENDER",
                                }
                            },
                        },
                    }
                ],
            },
        },
    )
    html_route = client.get(f"/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")
    api_accept_html = client.get(
        f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}",
        headers={"accept": "text/html,application/xhtml+xml"},
    )
    api_json = client.get(f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}&format=json")

    assert html_route.status_code == 200
    assert html_route.headers["content-type"].startswith("text/html")
    assert api_accept_html.status_code == 200
    assert api_accept_html.headers["content-type"].startswith("text/html")
    assert api_json.status_code == 200
    assert api_json.headers["content-type"].startswith("application/json")
    for text in (html_route.text, api_accept_html.text):
        assert "Workflow Status" in text
        assert "Timeline" in text
        assert "Actions" in text
        assert "Manual Handoffs" in text
        assert "Generated BoIs" in text
        assert "Trace Graph" in text
        assert "Raw JSON 불러오기" in text
        assert "INLINE_RAW_BODY_SHOULD_NOT_RENDER" not in text
        assert '"edges"' not in text


def test_workflow_status_links_action_raw_ids_and_dedupes_generated_bois(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-workflow-raw-links"
    boi_id = "boi:private:100001:workflow:raw-links"
    boi_app_module.write_boi(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/analysis",
            "title": "Workflow Raw Links BoI",
            "description": "Workflow raw link target",
            "tags": ["Workflow"],
            "timestamp": boi_app_module.now_iso(),
            "boi_id": boi_id,
            "visibility": "private",
            "classification": "internal",
            "owner": "100001",
            "author": {"type": "agent", "agent_id": "boi-writer-v0.4"},
            "acl_policy": "acl:private:100001",
            "status": "draft",
            "source_event": {"event_id": "evt-workflow-raw-links", "event_type": "root_cause.analysis.requested.v1", "trace_id": trace_id},
        },
        "# Summary\n\nWorkflow raw link target",
    )
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "Workflow Raw Link 이벤트"},
        },
        result={"boi_id": boi_id, "boi_uri": "/private/100001/workflow-raw-links.md"},
    )
    boi_app_module.append_event_log(
        status="enriched",
        event={
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "payload": {"title": "Workflow Raw Link 이벤트"},
        },
        result={"boi_id": boi_id, "boi_uri": "/private/100001/workflow-raw-links.md"},
    )
    log_ref = append_action_log_row(
        boi_app_module,
        {
            "logged_at": "2026-06-18T13:10:00+09:00",
            "action_key": "langflow.equipment.stage_analysis",
            "request_id": "act-workflow-raw-links",
            "employee_id": "100001",
            "event_id": "evt-workflow-raw-links",
            "event_type": "root_cause.analysis.requested.v1",
            "trace_id": trace_id,
            "boi_id": boi_id,
            "status": "langflow_invoked",
            "connector_kind": "langflow",
            "doc_ref": "boi:public:actions:langflow:stage-analysis",
            "result": {"message": "ROW_LEVEL_RAW_MARKER"},
        },
    )
    encoded = quote(log_ref, safe="")

    response = client.get(f"/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert f"/actions/raw/{encoded}?employee_id=100001" in response.text
    assert f"/api/actions/raw/{encoded}?employee_id=100001" in response.text
    assert "/events?employee_id=100001&amp;event_id=evt-workflow-raw-links" in response.text
    assert f"/events?employee_id=100001&amp;trace_id={trace_id}" in response.text
    assert f"/docs/{boi_id}?employee_id=100001" in response.text
    assert "act-workflow-raw-links" in response.text
    assert response.text.count('<span class="badge private">BoI</span>') == 1
    assert "ROW_LEVEL_RAW_MARKER" not in response.text


def test_workflow_status_raw_endpoint_returns_lazy_sections(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-raw-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-raw-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "Raw status 테스트"},
        },
        result={"raw_status_marker": "STATUS_RAW_MARKER"},
    )

    events = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=events")
    generic_events = client.get(f"/api/workflows/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=events")
    graph = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=graph")
    missing_section = client.get(f"/api/workflows/demo/equipment-anomaly/status/raw?employee_id=100001&trace_id={trace_id}&section=nope")

    assert events.status_code == 200
    assert events.json()["section"] == "events"
    assert events.json()["data"][0]["result"]["raw_status_marker"] == "STATUS_RAW_MARKER"
    assert generic_events.status_code == 200
    assert generic_events.json()["workflow_key"] == "equipment-anomaly"
    assert graph.status_code == 200
    assert graph.json()["section"] == "graph"
    assert "nodes" in graph.json()["data"]
    assert missing_section.status_code == 422


def test_events_page_links_to_workflow_status_html_route(boi_app_module):
    client = TestClient(boi_app_module.app)
    trace_id = "trace-status-link-test"
    boi_app_module.append_event_log(
        status="handled",
        event={
            "event_id": "evt-status-link-test",
            "event_type": "equipment.alarm.raised.v1",
            "trace_id": trace_id,
            "payload": {"title": "Status 링크 테스트"},
        },
        result={"dispatch_result": {"ok": True, "status": "handled", "results": []}},
    )

    response = client.get(f"/events?employee_id=100001&trace_id={trace_id}")

    assert response.status_code == 200
    assert f"/workflows/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}" in response.text
    assert f"/api/workflows/demo/equipment-anomaly/status?employee_id=100001&trace_id={trace_id}" not in response.text


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


def test_events_page_and_api_can_filter_by_event_id(boi_app_module):
    client = TestClient(boi_app_module.app)
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-filter-target", "event_type": "meeting.closed.v1", "trace_id": "trace-filter-target", "payload": {"title": "Target Event"}},
    )
    boi_app_module.append_event_log(
        status="published",
        event={"event_id": "evt-filter-other", "event_type": "meeting.closed.v1", "trace_id": "trace-filter-other", "payload": {"title": "Other Event"}},
    )

    api_response = client.get("/api/events/log?event_id=evt-filter-target")
    html_response = client.get("/events?employee_id=100001&event_id=evt-filter-target")

    assert api_response.status_code == 200
    assert api_response.json()["count"] == 1
    assert api_response.json()["items"][0]["event_id"] == "evt-filter-target"
    assert html_response.status_code == 200
    assert "Target Event" in html_response.text
    assert "Other Event" not in html_response.text
    assert "/events?employee_id=100001&amp;event_id=evt-filter-target" in html_response.text


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
