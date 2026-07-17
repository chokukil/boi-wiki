from __future__ import annotations

from fastapi.testclient import TestClient

from boi_api.app import share as share_module


SAMPLE_HTML = (
    "<!doctype html>\n"
    "<html lang=\"ko\">\n"
    "<head><meta charset=\"utf-8\"><title>공유 테스트</title></head>\n"
    "<body><h1>사내 HTML 보고서</h1><script>console.log('inline chart ok');</script></body>\n"
    "</html>\n"
)


def make_client(boi_app_module) -> TestClient:
    boi_app_module.BOI_AUTO_COMMIT = False
    return TestClient(boi_app_module.app)


def upload_html(
    client: TestClient,
    employee_id: str,
    *,
    name: str = "",
    content: str = SAMPLE_HTML,
    filename: str = "report.html",
    content_type: str = "text/html",
    visibility: str = "public",
    team_id: str = "",
    title: str = "테스트 공유",
    description: str = "pytest html share",
):
    data = {"title": title, "description": description, "visibility": visibility}
    if name:
        data["name"] = name
    if team_id:
        data["team_id"] = team_id
    return client.post(
        f"/api/share/html?employee_id={employee_id}",
        data=data,
        files={"file": (filename, content.encode("utf-8"), content_type)},
    )


def test_share_name_policy_helpers():
    assert share_module.suggest_share_name("report_2026-07.html") == "report-2026-07"
    assert share_module.suggest_share_name("한글만.html") == "shared-html"
    assert share_module.share_name_error("weekly-report") == ""
    assert share_module.share_name_error("api") != ""
    assert share_module.share_name_error("-bad-start") != ""
    assert share_module.share_name_error("a") != ""
    assert share_module.share_name_error("Bad_Name") != ""


def test_all_root_segments_are_reserved(boi_app_module):
    # 신규 루트 라우트를 추가하면 RESERVED_SHORTLINK_NAMES 갱신을 강제하는 테스트 (계획서 §7 Q1).
    catch_all = boi_app_module.app.routes[-1]
    assert getattr(catch_all, "path", "") == "/{name}", "GET /{name} catch-all must be the last registered route"
    for route in boi_app_module.app.routes:
        path = getattr(route, "path", "")
        if not path or path == "/":
            continue
        first_segment = path.lstrip("/").split("/", 1)[0]
        if first_segment.startswith("{"):
            assert path == "/{name}", f"unexpected parameterized root route: {path}"
            continue
        assert first_segment in share_module.RESERVED_SHORTLINK_NAMES, (
            f"root segment '{first_segment}' (route {path}) is missing from "
            "share.RESERVED_SHORTLINK_NAMES; add it so GET /{name} cannot shadow it"
        )


def test_upload_rejects_reserved_invalid_and_non_html(boi_app_module):
    client = make_client(boi_app_module)

    reserved = upload_html(client, "100001", name="api")
    invalid = upload_html(client, "100001", name="Bad_Name!")
    not_html = upload_html(client, "100001", name="plain-note", content="그냥 텍스트 메모", filename="note.txt", content_type="text/plain")
    secret = upload_html(client, "100001", name="secret-report", content='<html><body>api_key: "abcd1234efgh5678"</body></html>')

    assert reserved.status_code == 400
    assert "예약" in reserved.json()["detail"]
    assert invalid.status_code == 400
    assert not_html.status_code == 400
    assert "HTML" in not_html.json()["detail"]
    assert secret.status_code == 400
    assert "비밀" in secret.json()["detail"]


def test_upload_rejects_oversize_html(boi_app_module, monkeypatch):
    client = make_client(boi_app_module)
    # 상한을 낮춰 capped read(상한+1)와 413 경로를 실제 업로드로 검증한다.
    monkeypatch.setattr(share_module, "HTML_SHARE_MAX_BYTES", 64)
    oversize = upload_html(client, "100001", name="oversize-report")
    assert oversize.status_code == 413


def test_upload_happy_path_viewer_and_raw_headers(boi_app_module):
    client = make_client(boi_app_module)

    created = upload_html(client, "100001", name="weekly-etch-report")
    assert created.status_code == 200
    body = created.json()
    assert body["ok"] is True
    assert body["name"] == "weekly-etch-report"
    assert body["url"] == "/weekly-etch-report"
    assert body["raw_url"] == "/r/weekly-etch-report"
    assert body["owner_employee_id"] == "100001"
    assert body["visibility"] == "public"
    assert boi_app_module.SHORTLINK_REGISTRY_PATH.exists()

    availability = client.get("/api/share/names/weekly-etch-report/availability?employee_id=100001")
    assert availability.status_code == 200
    assert availability.json()["status"] == "owned_by_me"

    other_availability = client.get("/api/share/names/weekly-etch-report/availability?employee_id=100002")
    assert other_availability.json()["status"] == "taken"

    viewer = client.get("/weekly-etch-report?employee_id=100002")
    assert viewer.status_code == 200
    assert 'sandbox="allow-scripts"' in viewer.text
    assert "allow-same-origin" not in viewer.text

    raw = client.get("/r/weekly-etch-report?employee_id=100002")
    assert raw.status_code == 200
    assert raw.headers["content-security-policy"] == "sandbox allow-scripts"
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert raw.headers["cross-origin-resource-policy"] == "same-site"
    assert raw.headers["content-type"] == "text/html; charset=utf-8"
    assert "사내 HTML 보고서" in raw.text

    mine = client.get("/api/share/mine?employee_id=100001")
    assert mine.status_code == 200
    assert any(item["name"] == "weekly-etch-report" for item in mine.json()["items"])

    public_list = client.get("/api/share/list?employee_id=100002")
    assert public_list.status_code == 200
    assert any(item["name"] == "weekly-etch-report" for item in public_list.json()["items"])


def test_duplicate_policy_owner_overwrites_others_conflict(boi_app_module):
    client = make_client(boi_app_module)

    first = upload_html(client, "100002", name="capacity-report")
    assert first.status_code == 200
    assert first.json()["status"] == "created"

    conflict = upload_html(client, "100003", name="capacity-report")
    assert conflict.status_code == 409
    detail = conflict.json()["detail"]
    assert detail["status"] == "taken"
    assert detail["suggested_names"]
    assert detail["suggested_names"][0] == "capacity-report-2"

    updated_html = SAMPLE_HTML.replace("사내 HTML 보고서", "업데이트된 보고서 v2")
    overwrite = upload_html(client, "100002", name="capacity-report", content=updated_html)
    assert overwrite.status_code == 200
    assert overwrite.json()["status"] == "updated"

    raw = client.get("/r/capacity-report?employee_id=100002")
    assert raw.status_code == 200
    assert "업데이트된 보고서 v2" in raw.text


def test_private_share_hidden_from_other_employees(boi_app_module):
    client = make_client(boi_app_module)

    created = upload_html(client, "100002", name="my-private-note", visibility="private")
    assert created.status_code == 200
    stored = boi_app_module.DATA_ROOT / "private" / "100002" / "html" / "my-private-note.html"
    assert stored.exists()

    assert client.get("/r/my-private-note?employee_id=100002").status_code == 200
    assert client.get("/my-private-note?employee_id=100002").status_code == 200
    # 접근 불가는 미등록과 같은 404 (존재 여부 노출 방지)
    assert client.get("/r/my-private-note?employee_id=100003").status_code == 404
    assert client.get("/my-private-note?employee_id=100003").status_code == 404


def test_team_share_visible_to_members_only(boi_app_module):
    client = make_client(boi_app_module)

    created = upload_html(client, "100002", name="aix-team-report", visibility="team", team_id="aix-tf")
    assert created.status_code == 200
    stored = boi_app_module.DATA_ROOT / "team" / "aix-tf" / "html" / "aix-team-report.html"
    assert stored.exists()

    # 100001은 aix-tf 멤버, 100003은 platform만 소속
    assert client.get("/r/aix-team-report?employee_id=100001").status_code == 200
    assert client.get("/aix-team-report?employee_id=100001").status_code == 200
    assert client.get("/r/aix-team-report?employee_id=100003").status_code == 404
    assert client.get("/aix-team-report?employee_id=100003").status_code == 404

    outsider = upload_html(client, "100003", name="platform-into-aix", visibility="team", team_id="aix-tf")
    assert outsider.status_code == 403


def test_delete_tombstones_name_forever(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100002", name="quarterly-summary").status_code == 200

    forbidden = client.delete("/api/share/quarterly-summary?employee_id=100003")
    assert forbidden.status_code == 403

    deleted = client.delete("/api/share/quarterly-summary?employee_id=100002")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "tombstone"
    stored = boi_app_module.DATA_ROOT / "public" / "html" / "quarterly-summary.html"
    assert not stored.exists()

    viewer = client.get("/quarterly-summary?employee_id=100002")
    assert viewer.status_code == 410
    assert "삭제된 공유 주소" in viewer.text

    availability = client.get("/api/share/names/quarterly-summary/availability?employee_id=100001")
    assert availability.json()["status"] == "tombstone"

    reuse_by_owner = upload_html(client, "100002", name="quarterly-summary")
    reuse_by_other = upload_html(client, "100001", name="quarterly-summary")
    assert reuse_by_owner.status_code == 409
    assert reuse_by_other.status_code == 409
    assert reuse_by_owner.json()["detail"]["status"] == "tombstone"


def test_unknown_and_reserved_shortlink_pages(boi_app_module):
    client = make_client(boi_app_module)

    unknown = client.get("/never-registered-name?employee_id=100001")
    assert unknown.status_code == 404
    assert "이 이름으로 공유 등록하기" in unknown.text
    assert "/share" in unknown.text

    availability = client.get("/api/share/names/never-registered-name/availability?employee_id=100001")
    assert availability.json()["status"] == "available"
    reserved = client.get("/api/share/names/share/availability?employee_id=100001")
    assert reserved.json()["status"] == "reserved"
    invalid = client.get("/api/share/names/a/availability?employee_id=100001")
    assert invalid.json()["status"] == "invalid"


def test_share_upload_page_renders(boi_app_module):
    client = make_client(boi_app_module)

    page = client.get("/share?employee_id=100001")
    assert page.status_code == 200
    assert "HTML 업로드" in page.text
    assert "/api/share/html" in page.text
    assert "/api/share/names" in page.text


def test_upload_injects_boi_profile_and_generates_knowledge_card(boi_app_module):
    from boi_api.app.okf import lint_markdown_file, split_frontmatter

    client = make_client(boi_app_module)

    created = upload_html(client, "100001", name="profile-card-share", description="지식 카드 생성 확인")
    assert created.status_code == 200
    body = created.json()
    assert body["boi_id"] == "boi:public:html:profile-card-share"
    assert body["card_uri"] == "/public/html/profile-card-share.md"
    assert body["event"] in {"published", "disabled", "log_only"}
    assert body["commit"]["card"] in {"disabled", "committed", "unchanged"}

    stored = boi_app_module.DATA_ROOT / "public" / "html" / "profile-card-share.html"
    stored_text = stored.read_text(encoding="utf-8")
    assert stored_text.count('id="boi-profile"') == 1
    profile = share_module.extract_html_profile(stored_text)
    assert profile is not None
    assert profile["@type"] == "DigitalDocument"
    boi_profile = profile["boiProfile"]
    assert boi_profile["type"] == "boi/html-document"
    assert boi_profile["boi_id"] == "boi:public:html:profile-card-share"
    assert boi_profile["acl_policy"] == "acl:public"
    assert boi_profile["content_role"] == "html_artifact"
    assert boi_profile["shortlink"] == "/profile-card-share"
    assert boi_profile["source_refs"][0]["uploaded_by"] == "100001"
    # 본문은 그대로 보존된다.
    assert "사내 HTML 보고서" in stored_text

    raw = client.get("/r/profile-card-share?employee_id=100002")
    assert 'id="boi-profile"' in raw.text

    card = stored.with_suffix(".md")
    assert card.exists()
    card_errors, _edges = lint_markdown_file(card, boi_root=boi_app_module.DATA_ROOT)
    assert card_errors == []
    metadata, card_body = split_frontmatter(card.read_text(encoding="utf-8"))
    assert metadata["boi_id"] == "boi:public:html:profile-card-share"
    assert metadata["type"] == "boi/html-document"
    assert metadata["status"] == "reviewed"
    assert metadata["review"]["review_status"] == "user_confirmed"
    source_ref_types = {ref["type"] for ref in metadata["source_refs"]}
    assert source_ref_types == {"html_artifact", "upload"}
    assert "/profile-card-share" in card_body
    assert "/r/profile-card-share" in card_body


def test_upload_publishes_event_and_relint_passes(boi_app_module):
    from boi_api.app.okf import lint_data_root

    client = make_client(boi_app_module)

    assert upload_html(client, "100001", name="event-lint-share").status_code == 200

    published = [
        item
        for item in boi_app_module.AIOKafkaProducer.sent_events
        if item["event"].get("event_type") == "html.share.published.v1"
    ]
    assert published
    payload = published[-1]["event"]["payload"]
    assert payload["name"] == "event-lint-share"
    assert payload["boi_id"] == "boi:public:html:event-lint-share"
    assert payload["owner_employee_id"] == "100001"
    assert payload["action"] == "created"

    # 재업로드 시 프로필 블록이 중복되지 않고 카드가 재생성되며 lint가 계속 통과한다.
    assert upload_html(client, "100001", name="event-lint-share").status_code == 200
    stored = boi_app_module.DATA_ROOT / "public" / "html" / "event-lint-share.html"
    assert stored.read_text(encoding="utf-8").count('id="boi-profile"') == 1
    result = lint_data_root(boi_app_module.DATA_ROOT.parent)
    assert result.ok, result.errors[:5]
    assert result.checked_html_count >= 1


def test_json_upload_branch_accepts_content_base64(boi_app_module):
    import base64

    client = make_client(boi_app_module)

    response = client.post(
        "/api/share/html?employee_id=100001",
        json={
            "content_base64": base64.b64encode(SAMPLE_HTML.encode("utf-8")).decode("ascii"),
            "name": "json-upload-share",
            "title": "JSON 업로드",
            "visibility": "public",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "json-upload-share"
    stored = boi_app_module.DATA_ROOT / "public" / "html" / "json-upload-share.html"
    assert stored.exists()
    assert stored.with_suffix(".md").exists()

    missing = client.post("/api/share/html?employee_id=100001", json={"name": "json-upload-share"})
    assert missing.status_code == 400
    assert "content_base64" in missing.json()["detail"]


def test_delete_removes_knowledge_card_with_html(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100002", name="card-delete-share").status_code == 200
    stored = boi_app_module.DATA_ROOT / "public" / "html" / "card-delete-share.html"
    assert stored.exists() and stored.with_suffix(".md").exists()

    assert client.delete("/api/share/card-delete-share?employee_id=100002").status_code == 200
    assert not stored.exists()
    assert not stored.with_suffix(".md").exists()


def test_share_preview_is_non_mutating(boi_app_module):
    import base64

    client = make_client(boi_app_module)

    preview = client.post(
        "/api/share/preview?employee_id=100001",
        json={
            "content_base64": base64.b64encode(SAMPLE_HTML.encode("utf-8")).decode("ascii"),
            "name": "preview-only-share",
            "title": "미리보기",
            "visibility": "public",
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is True
    assert body["mutating"] is False
    assert body["name_status"] == "available"
    assert body["would_publish"]["action"] == "create"
    assert body["would_publish"]["boi_id"] == "boi:public:html:preview-only-share"
    assert body["would_publish"]["event"] == "html.share.published.v1"
    assert not (boi_app_module.DATA_ROOT / "public" / "html" / "preview-only-share.html").exists()

    # 비밀 값과 타인 이름 충돌은 preview 단계에서 blocker로 보고된다.
    assert upload_html(client, "100002", name="preview-taken-share").status_code == 200
    conflicted = client.post(
        "/api/share/preview?employee_id=100001",
        json={
            "content": '<html><body>api_key: "abcd1234efgh5678"</body></html>',
            "name": "preview-taken-share",
        },
    )
    assert conflicted.status_code == 200
    conflict_body = conflicted.json()
    assert conflict_body["ok"] is False
    assert conflict_body["name_status"] == "taken"
    assert conflict_body["suggested_names"]
    assert any("비밀" in blocker for blocker in conflict_body["blockers"])


def test_doc_shortlink_registration_policy(boi_app_module):
    client = make_client(boi_app_module)

    registered = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-harness", "target_boi_id": "boi:public:harness:overview"},
    )
    assert registered.status_code == 200
    body = registered.json()
    assert body["ok"] is True
    assert body["target_kind"] == "doc"
    assert body["status"] == "created"

    redirect = client.get("/go-harness?employee_id=100002", follow_redirects=False)
    assert redirect.status_code == 302
    assert "boi:public:harness:overview" in redirect.headers["location"]

    missing_target = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-nowhere", "target_boi_id": "boi:public:does-not-exist"},
    )
    assert missing_target.status_code == 404

    reserved = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "api", "target_boi_id": "boi:public:harness:overview"},
    )
    assert reserved.status_code == 400

    taken = client.post(
        "/api/share/links?employee_id=100002",
        json={"name": "go-harness", "target_boi_id": "boi:public:harness:overview"},
    )
    assert taken.status_code == 409
    assert taken.json()["detail"]["suggested_names"]
