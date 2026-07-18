from __future__ import annotations

import subprocess

import pytest
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
    assert raw.headers["content-security-policy"] == "sandbox allow-scripts; frame-ancestors 'self'"
    assert raw.headers["x-content-type-options"] == "nosniff"
    assert raw.headers["cross-origin-resource-policy"] == "same-site"
    assert raw.headers["referrer-policy"] == "no-referrer"
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


def test_upload_transcodes_non_utf8_encoding_and_rewrites_meta_charset(boi_app_module):
    # 사내 legacy HTML은 EUC-KR/CP949일 가능성이 높다 (§10 P0-3). errors="replace"로
    # 깨진 채 저장하지 않고, 감지된 인코딩으로 정확히 디코딩해 utf-8로 다시 저장해야 한다.
    client = make_client(boi_app_module)

    korean_text = "인코딩 변환 테스트: 한글 레거시 업로드 확인"
    cp949_html = (
        "<!doctype html>\n"
        "<html lang=\"ko\">\n"
        "<head><meta charset=\"euc-kr\"><title>인코딩 테스트</title></head>\n"
        f"<body><h1>{korean_text}</h1></body>\n"
        "</html>\n"
    ).encode("cp949")

    response = client.post(
        "/api/share/html?employee_id=100001",
        data={"name": "encoding-cp949-share", "title": "인코딩 테스트", "visibility": "public"},
        files={"file": ("report.html", cp949_html, "text/html")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["encoding"]["detected"] == "cp949"
    assert body["encoding"]["converted"] is True
    assert body["encoding"]["lossy"] is False

    stored = boi_app_module.DATA_ROOT / "public" / "html" / "encoding-cp949-share.html"
    # 예외 없이 utf-8로 읽히면 변환이 성공했다는 뜻이다 (읽기 실패 시 UnicodeDecodeError).
    stored_text = stored.read_text(encoding="utf-8")
    assert korean_text in stored_text
    assert "euc-kr" not in stored_text.lower()
    assert 'charset="utf-8"' in stored_text.lower()
    assert "�" not in stored_text

    raw = client.get("/r/encoding-cp949-share?employee_id=100002")
    assert raw.status_code == 200
    assert korean_text in raw.text

    card = stored.with_suffix(".md")
    card_text = card.read_text(encoding="utf-8")
    assert "�" not in card_text


def test_upload_utf8_content_is_unaffected_by_encoding_detection(boi_app_module):
    # 정상 UTF-8 업로드는 기존과 동일하게 동작해야 한다 (변환/메타 재작성 없음).
    client = make_client(boi_app_module)

    created = upload_html(client, "100001", name="utf8-unaffected-share")
    assert created.status_code == 200
    body = created.json()
    assert body["encoding"] == {"detected": "utf-8", "converted": False, "lossy": False}

    stored = boi_app_module.DATA_ROOT / "public" / "html" / "utf8-unaffected-share.html"
    assert "사내 HTML 보고서" in stored.read_text(encoding="utf-8")


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


# --- §10 P1-6: PATCH /api/share/{name} (메타데이터만 수정) --------------------


def test_patch_title_only_reinjects_profile_and_regenerates_card(boi_app_module):
    from boi_api.app.okf import lint_data_root, split_frontmatter

    client = make_client(boi_app_module)
    assert upload_html(client, "100001", name="patch-title-share", title="원래 제목", description="원래 설명").status_code == 200

    forbidden = client.patch(
        "/api/share/patch-title-share?employee_id=100003", json={"title": "다른 사람 제목"}
    )
    assert forbidden.status_code == 403

    patched = client.patch(
        "/api/share/patch-title-share?employee_id=100001", json={"title": "새 제목"}
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["ok"] is True
    assert body["title"] == "새 제목"
    assert body["description"] == "원래 설명"
    assert body["visibility"] == "public"
    assert body["status"] == "updated"

    stored = boi_app_module.DATA_ROOT / "public" / "html" / "patch-title-share.html"
    stored_text = stored.read_text(encoding="utf-8")
    assert stored_text.count('id="boi-profile"') == 1
    profile = share_module.extract_html_profile(stored_text)
    assert profile["boiProfile"]["title"] == "새 제목"

    card = stored.with_suffix(".md")
    metadata, _body = split_frontmatter(card.read_text(encoding="utf-8"))
    assert metadata["title"] == "새 제목"

    availability = client.get("/api/share/names/patch-title-share/availability?employee_id=100001")
    assert availability.json()["status"] == "owned_by_me"

    registry = share_module.registry_load(boi_app_module.SHORTLINK_REGISTRY_PATH)
    record = share_module.registry_find(registry, "patch-title-share")
    assert record["title"] == "새 제목"

    result = lint_data_root(boi_app_module.DATA_ROOT.parent, strict_links=True)
    card_errors = [error for error in result.errors if "patch-title-share" in error]
    assert card_errors == []


def test_patch_visibility_move_public_to_team_and_acl_enforced(boi_app_module):
    client = make_client(boi_app_module)
    assert upload_html(client, "100002", name="patch-visibility-share", visibility="public").status_code == 200
    old_path = boi_app_module.DATA_ROOT / "public" / "html" / "patch-visibility-share.html"
    assert old_path.exists()

    patched = client.patch(
        "/api/share/patch-visibility-share?employee_id=100002",
        json={"visibility": "team", "team_id": "aix-tf"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["visibility"] == "team"
    assert body["team_id"] == "aix-tf"
    assert body["boi_id"] == "boi:team:aix-tf:html:patch-visibility-share"

    # 옛 public 경로의 파일/카드는 사라진다.
    assert not old_path.exists()
    assert not old_path.with_suffix(".md").exists()

    new_path = boi_app_module.DATA_ROOT / "team" / "aix-tf" / "html" / "patch-visibility-share.html"
    assert new_path.exists()
    assert new_path.with_suffix(".md").exists()

    # ACL: aix-tf 팀원(100001)은 읽을 수 있고, platform 전용(100003)은 불가.
    assert client.get("/r/patch-visibility-share?employee_id=100001").status_code == 200
    assert client.get("/patch-visibility-share?employee_id=100001").status_code == 200
    assert client.get("/r/patch-visibility-share?employee_id=100003").status_code == 404
    assert client.get("/patch-visibility-share?employee_id=100003").status_code == 404

    # 팀 멤버가 아니면 team으로 변경할 수 없다.
    assert upload_html(client, "100003", name="patch-visibility-other", visibility="public").status_code == 200
    non_member = client.patch(
        "/api/share/patch-visibility-other?employee_id=100003",
        json={"visibility": "team", "team_id": "aix-tf"},
    )
    assert non_member.status_code == 403

    invalid = client.patch(
        "/api/share/patch-visibility-share?employee_id=100002", json={"visibility": "not-a-scope"}
    )
    assert invalid.status_code == 400


def test_patch_rejects_unknown_and_non_html_shares(boi_app_module):
    client = make_client(boi_app_module)

    missing = client.patch("/api/share/never-registered-patch?employee_id=100001", json={"title": "x"})
    assert missing.status_code == 404

    registered = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "patch-doc-kind", "target_boi_id": "boi:public:harness:overview"},
    )
    assert registered.status_code == 200
    non_html = client.patch("/api/share/patch-doc-kind?employee_id=100001", json={"title": "x"})
    assert non_html.status_code == 404


# --- §10 P1-7: 소유권 이전·회수 ------------------------------------------------


def test_transfer_ownership_new_owner_can_manage_old_owner_forbidden(boi_app_module):
    client = make_client(boi_app_module)
    assert upload_html(client, "100002", name="transfer-public-share", visibility="public").status_code == 200

    forbidden = client.post(
        "/api/share/transfer-public-share/transfer?employee_id=100003",
        json={"new_owner_employee_id": "100003"},
    )
    assert forbidden.status_code == 403

    transferred = client.post(
        "/api/share/transfer-public-share/transfer?employee_id=100002",
        json={"new_owner_employee_id": "100003"},
    )
    assert transferred.status_code == 200
    body = transferred.json()
    assert body["ok"] is True
    assert body["owner_employee_id"] == "100003"
    assert len(body["transfers"]) == 1
    transfer_entry = body["transfers"][0]
    assert transfer_entry["from"] == "100002"
    assert transfer_entry["to"] == "100003"
    assert transfer_entry["by"] == "100002"
    assert transfer_entry["at"]

    registry = share_module.registry_load(boi_app_module.SHORTLINK_REGISTRY_PATH)
    record = share_module.registry_find(registry, "transfer-public-share")
    assert record["owner_employee_id"] == "100003"
    assert record["transfers"][0]["from"] == "100002"
    assert record["transfers"][0]["to"] == "100003"

    # 새 소유자는 이제 PATCH/재업로드가 가능하다.
    new_owner_patch = client.patch(
        "/api/share/transfer-public-share?employee_id=100003", json={"title": "새 소유자 제목"}
    )
    assert new_owner_patch.status_code == 200

    reupload = upload_html(client, "100003", name="transfer-public-share", title="재업로드")
    assert reupload.status_code == 200
    assert reupload.json()["status"] == "updated"

    # 옛 소유자는 더 이상 소유자가 아니므로 PATCH/삭제/재이전이 거부된다.
    old_owner_patch = client.patch(
        "/api/share/transfer-public-share?employee_id=100002", json={"title": "옛 소유자 시도"}
    )
    assert old_owner_patch.status_code == 403
    old_owner_delete = client.delete("/api/share/transfer-public-share?employee_id=100002")
    assert old_owner_delete.status_code == 403
    old_owner_reupload = upload_html(client, "100002", name="transfer-public-share")
    assert old_owner_reupload.status_code == 409
    assert old_owner_reupload.json()["detail"]["status"] == "taken"


def test_transfer_admin_reclaim_relocates_private_file(boi_app_module):
    client = make_client(boi_app_module)
    assert upload_html(client, "100002", name="transfer-private-share", visibility="private").status_code == 200
    old_path = boi_app_module.DATA_ROOT / "private" / "100002" / "html" / "transfer-private-share.html"
    assert old_path.exists()

    # 100001은 boi.admin 역할을 가진 서비스/관리자 사번(테스트 fixtures 기준)이다.
    reclaimed = client.post(
        "/api/share/transfer-private-share/transfer?employee_id=100001",
        json={"new_owner_employee_id": "100003"},
    )
    assert reclaimed.status_code == 200
    body = reclaimed.json()
    assert body["owner_employee_id"] == "100003"
    assert body["boi_id"] == "boi:private:100003:html:transfer-private-share"

    assert not old_path.exists()
    new_path = boi_app_module.DATA_ROOT / "private" / "100003" / "html" / "transfer-private-share.html"
    assert new_path.exists()
    assert new_path.with_suffix(".md").exists()

    stored_text = new_path.read_text(encoding="utf-8")
    profile = share_module.extract_html_profile(stored_text)
    assert profile["boiProfile"]["owner"] == "100003"
    assert profile["boiProfile"]["acl_policy"] == "acl:private:100003"

    # 원래 소유자는 더 이상 읽을 수 없다 (private ACL이 새 소유자로 넘어갔다).
    assert client.get("/r/transfer-private-share?employee_id=100002").status_code == 404
    assert client.get("/r/transfer-private-share?employee_id=100003").status_code == 200


def test_transfer_rejects_missing_and_same_owner(boi_app_module):
    client = make_client(boi_app_module)
    assert upload_html(client, "100002", name="transfer-validation-share").status_code == 200

    missing_field = client.post(
        "/api/share/transfer-validation-share/transfer?employee_id=100002", json={"new_owner_employee_id": ""}
    )
    assert missing_field.status_code == 400

    same_owner = client.post(
        "/api/share/transfer-validation-share/transfer?employee_id=100002",
        json={"new_owner_employee_id": "100002"},
    )
    assert same_owner.status_code == 400

    missing_share = client.post(
        "/api/share/never-registered-transfer/transfer?employee_id=100002",
        json={"new_owner_employee_id": "100003"},
    )
    assert missing_share.status_code == 404


# --- §10 P2-13: url-kind go-link 등록 개방 --------------------------------------


def test_url_kind_shortlink_allowed_host_redirects_lists_publicly_and_tombstones(boi_app_module, monkeypatch):
    client = make_client(boi_app_module)
    monkeypatch.setenv("BOI_SHARE_URL_ALLOWED_HOSTS", "wiki-tools.internal")

    disallowed = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-external", "target_kind": "url", "target_url": "https://evil.example.com/phish"},
    )
    assert disallowed.status_code == 400
    assert "허용된" in disallowed.json()["detail"]

    allowed = client.post(
        "/api/share/links?employee_id=100001",
        json={
            "name": "go-internal-tool",
            "target_kind": "url",
            "target_url": "https://wiki-tools.internal/dashboard",
            "title": "내부 대시보드",
        },
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["target_kind"] == "url"
    assert body["visibility"] == "public"

    redirect = client.get("/go-internal-tool?employee_id=100002", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://wiki-tools.internal/dashboard"

    # url-link는 공개 메타데이터라 등록자 외 다른 사용자에게도 공개 목록에 노출된다.
    public_list = client.get("/api/share/list?employee_id=100002")
    assert any(item["name"] == "go-internal-tool" for item in public_list.json()["items"])

    # 같은 이름 정책: 소유자만 갱신 가능, 타인은 409.
    taken = client.post(
        "/api/share/links?employee_id=100002",
        json={"name": "go-internal-tool", "target_kind": "url", "target_url": "https://wiki-tools.internal/other"},
    )
    assert taken.status_code == 409

    # 삭제 = tombstone: 이름 영구 재사용 불가.
    deleted = client.delete("/api/share/go-internal-tool?employee_id=100001")
    assert deleted.status_code == 200
    reuse = client.post(
        "/api/share/links?employee_id=100002",
        json={"name": "go-internal-tool", "target_kind": "url", "target_url": "https://wiki-tools.internal/other"},
    )
    assert reuse.status_code == 409
    assert reuse.json()["detail"]["status"] == "tombstone"


def test_url_kind_shortlink_default_hosts_and_validation(boi_app_module):
    client = make_client(boi_app_module)

    ok = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-local", "target_kind": "url", "target_url": "http://localhost:28000/internal"},
    )
    assert ok.status_code == 200

    bad_scheme = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-ftp", "target_kind": "url", "target_url": "ftp://localhost/file"},
    )
    assert bad_scheme.status_code == 400

    missing_url = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-empty", "target_kind": "url", "target_url": ""},
    )
    assert missing_url.status_code == 400

    bad_kind = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-bad-kind", "target_kind": "not-a-kind"},
    )
    assert bad_kind.status_code == 400

    # doc-kind 등록은 target_kind를 생략해도(기본값 doc) 이전과 동일하게 동작한다.
    doc_default = client.post(
        "/api/share/links?employee_id=100001",
        json={"name": "go-doc-default", "target_boi_id": "boi:public:harness:overview"},
    )
    assert doc_default.status_code == 200
    assert doc_default.json()["target_kind"] == "doc"


# --- §10 P2-16: 업로드 quota (env, monkeypatch로 재정의) -------------------------


def test_upload_quota_per_user_active_share_cap(boi_app_module, monkeypatch):
    client = make_client(boi_app_module)
    monkeypatch.setattr(boi_app_module, "BOI_SHARE_MAX_PER_USER", 1)

    first = upload_html(client, "100002", name="quota-user-first")
    assert first.status_code == 200

    second = upload_html(client, "100002", name="quota-user-second")
    assert second.status_code == 429
    assert "개수" in second.json()["detail"]

    # 재업로드(overwrite)는 활성 공유 개수를 늘리지 않으므로 상한 검사에서 빠진다.
    overwrite = upload_html(client, "100002", name="quota-user-first", title="다시 업로드")
    assert overwrite.status_code == 200

    # 다른 사용자는 자신만의 상한을 갖는다.
    other_user = upload_html(client, "100003", name="quota-user-other")
    assert other_user.status_code == 200


def test_upload_quota_daily_upload_cap(boi_app_module, monkeypatch):
    client = make_client(boi_app_module)
    monkeypatch.setattr(boi_app_module, "BOI_SHARE_MAX_UPLOADS_PER_DAY", 1)

    first = upload_html(client, "100002", name="quota-daily-first")
    assert first.status_code == 200

    # 같은 이름 재업로드도 하루 업로드 상한에 반영된다.
    second = upload_html(client, "100002", name="quota-daily-first", title="다시")
    assert second.status_code == 429
    assert "하루" in second.json()["detail"]

    # 신규 이름 업로드도 동일하게 막힌다.
    third = upload_html(client, "100002", name="quota-daily-second")
    assert third.status_code == 429

    # 다른 사용자는 자신의 하루 카운트를 별도로 갖는다.
    other_user = upload_html(client, "100003", name="quota-daily-other-user")
    assert other_user.status_code == 200


def test_upload_quota_disabled_when_limit_is_zero(boi_app_module, monkeypatch):
    client = make_client(boi_app_module)
    monkeypatch.setattr(boi_app_module, "BOI_SHARE_MAX_PER_USER", 0)
    monkeypatch.setattr(boi_app_module, "BOI_SHARE_MAX_UPLOADS_PER_DAY", 0)
    assert upload_html(client, "100002", name="quota-disabled-a").status_code == 200
    assert upload_html(client, "100002", name="quota-disabled-b").status_code == 200
    assert upload_html(client, "100002", name="quota-disabled-c").status_code == 200


# --- §10 P2-17: 레지스트리 동시성 (inter-process 파일락) -------------------------


def test_registry_upsert_creates_inter_process_lock_file(boi_app_module):
    if share_module.fcntl is None:
        pytest.skip("fcntl is unavailable on this platform (e.g. Windows dev environment)")
    client = make_client(boi_app_module)
    assert upload_html(client, "100001", name="lock-file-share").status_code == 200
    lock_path = boi_app_module.SHORTLINK_REGISTRY_PATH.parent / (boi_app_module.SHORTLINK_REGISTRY_PATH.name + ".lock")
    assert lock_path.exists()

    # tombstone(레지스트리 삭제 경로)도 같은 락 파일을 재사용한다.
    assert client.delete("/api/share/lock-file-share?employee_id=100001").status_code == 200
    assert lock_path.exists()


# --- §10 P2-14: 버전 이력 뷰 -----------------------------------------------------


def test_share_history_gracefully_unavailable_without_git(boi_app_module):
    # 기본 테스트 환경(DATA_ROOT가 git 저장소가 아님)에서는 하드 실패 없이 unavailable로 응답한다.
    client = make_client(boi_app_module)
    assert upload_html(client, "100001", name="history-no-git").status_code == 200

    history = client.get("/api/share/history-no-git/history?employee_id=100001")
    assert history.status_code == 200
    body = history.json()
    assert body["ok"] is True
    assert body["available"] is False
    assert body["entries"] == []

    invalid_commit = client.get("/api/share/history-no-git/history/not-a-hash?employee_id=100001")
    assert invalid_commit.status_code == 400

    missing_version = client.get("/api/share/history-no-git/history/abc1234?employee_id=100001")
    assert missing_version.status_code == 404

    missing_share = client.get("/api/share/never-registered-history/history?employee_id=100001")
    assert missing_share.status_code == 404


def _init_isolated_git_repo(root) -> None:
    """pytest tmp_path 아래 완전히 새 git 저장소를 만든다 — 실제 저장소의 .git과 무관하다."""
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "-c", "user.email=harness-eval@example.com", "-c", "user.name=harness-eval", "add", "-A"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=harness-eval@example.com",
            "-c",
            "user.name=harness-eval",
            "commit",
            "-q",
            "-m",
            "seed",
        ],
        cwd=str(root),
        check=False,  # 이미 커밋된 상태 등으로 "nothing to commit"이면 무시한다.
    )


def test_share_history_lists_and_serves_versions_with_real_git_repo(boi_app_module):
    # §10 P2-14: BOI_AUTO_COMMIT을 켜고 실제(격리된) git 저장소로 전체 라우트를 검증한다.
    client = make_client(boi_app_module)
    _init_isolated_git_repo(boi_app_module.DATA_ROOT)
    boi_app_module.BOI_AUTO_COMMIT = True

    first_content = SAMPLE_HTML.replace("사내 HTML 보고서", "버전 1")
    assert upload_html(client, "100001", name="history-real-git", content=first_content).status_code == 200
    second_content = SAMPLE_HTML.replace("사내 HTML 보고서", "버전 2")
    assert upload_html(client, "100001", name="history-real-git", content=second_content).status_code == 200

    history = client.get("/api/share/history-real-git/history?employee_id=100002")
    assert history.status_code == 200
    body = history.json()
    assert body["available"] is True
    assert len(body["entries"]) >= 2
    commits = [entry["commit"] for entry in body["entries"]]
    assert len(commits) == len(set(commits))
    for entry in body["entries"]:
        assert entry["committed_at"]
        assert entry["message"]

    oldest_commit = body["entries"][-1]["commit"]
    oldest_version = client.get(f"/api/share/history-real-git/history/{oldest_commit}?employee_id=100002")
    assert oldest_version.status_code == 200
    assert oldest_version.headers["content-security-policy"] == "sandbox allow-scripts; frame-ancestors 'self'"
    assert oldest_version.headers["x-content-type-options"] == "nosniff"
    assert oldest_version.headers["cross-origin-resource-policy"] == "same-site"
    assert oldest_version.headers["referrer-policy"] == "no-referrer"
    assert "버전 1" in oldest_version.text

    latest_commit = body["entries"][0]["commit"]
    latest_version = client.get(f"/api/share/history-real-git/history/{latest_commit}?employee_id=100002")
    assert "버전 2" in latest_version.text

    invalid_commit = client.get("/api/share/history-real-git/history/deadbeefzz?employee_id=100002")
    assert invalid_commit.status_code == 400

    unknown_commit = client.get("/api/share/history-real-git/history/0123456?employee_id=100002")
    assert unknown_commit.status_code == 404

    # ACL: private 공유의 이력은 소유자 외에는 볼 수 없다.
    assert upload_html(client, "100002", name="history-private-git", visibility="private").status_code == 200
    private_history = client.get("/api/share/history-private-git/history?employee_id=100003")
    assert private_history.status_code == 404


# --- §10 P2-15: 다중 파일 번들(assets) -------------------------------------------


def upload_bundle(
    client: TestClient,
    employee_id: str,
    *,
    name: str,
    content: str = SAMPLE_HTML,
    assets=None,
    visibility: str = "public",
    team_id: str = "",
    title: str = "번들 테스트",
    description: str = "pytest bundle",
):
    data = {"title": title, "description": description, "visibility": visibility, "name": name}
    if team_id:
        data["team_id"] = team_id
    files = [("file", ("report.html", content.encode("utf-8"), "text/html"))]
    for asset_name, asset_bytes, asset_content_type in assets or []:
        files.append(("assets", (asset_name, asset_bytes, asset_content_type)))
    return client.post(f"/api/share/html?employee_id={employee_id}", data=data, files=files)


def test_bundle_upload_serves_index_and_assets_with_security_headers(boi_app_module):
    from boi_api.app.okf import lint_data_root, split_frontmatter

    client = make_client(boi_app_module)
    css_bytes = b"body{background:#fff}"
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16

    created = upload_bundle(
        client,
        "100001",
        name="bundle-report",
        assets=[("style.css", css_bytes, "text/css"), ("logo.png", png_bytes, "image/png")],
    )
    assert created.status_code == 200
    body = created.json()
    assert body["bundle"] is True
    assert sorted(body["assets"]) == ["logo.png", "style.css"]
    assert body["card_uri"] == "/public/html/bundle-report.md"

    bundle_dir = boi_app_module.DATA_ROOT / "public" / "html" / "bundle-report"
    assert (bundle_dir / "index.html").exists()
    assert (bundle_dir / "style.css").read_bytes() == css_bytes
    assert (bundle_dir / "logo.png").read_bytes() == png_bytes
    card_path = boi_app_module.DATA_ROOT / "public" / "html" / "bundle-report.md"
    assert card_path.exists()

    metadata, card_body = split_frontmatter(card_path.read_text(encoding="utf-8"))
    assert metadata["bundle"] is True
    assert metadata["source_refs"][0]["ref"] == "data/boi/public/html/bundle-report/index.html"
    assert "style.css" in card_body

    index_response = client.get("/r/bundle-report?employee_id=100002")
    assert index_response.status_code == 200

    css_response = client.get("/r/bundle-report/style.css?employee_id=100002")
    assert css_response.status_code == 200
    assert css_response.content == css_bytes
    assert css_response.headers["content-security-policy"] == "sandbox allow-scripts; frame-ancestors 'self'"
    assert css_response.headers["x-content-type-options"] == "nosniff"
    assert css_response.headers["cross-origin-resource-policy"] == "same-site"
    assert css_response.headers["referrer-policy"] == "no-referrer"

    png_response = client.get("/r/bundle-report/logo.png?employee_id=100002")
    assert png_response.status_code == 200
    assert png_response.content == png_bytes

    # private 자산: 다른 스코프였다면 접근 불가 — 여기서는 public이므로 정상 접근.
    result = lint_data_root(boi_app_module.DATA_ROOT.parent, strict_links=True)
    bundle_errors = [error for error in result.errors if "bundle-report" in error]
    assert bundle_errors == []


def test_bundle_asset_traversal_and_bad_extension_are_rejected(boi_app_module):
    client = make_client(boi_app_module)
    assert (
        upload_bundle(client, "100001", name="bundle-guard", assets=[("style.css", b"a{}", "text/css")]).status_code
        == 200
    )

    # 경로 탈출 시도는 어떤 형태든 200(자산 노출)이어서는 안 된다.
    traversal = client.get("/r/bundle-guard/../../../etc/passwd?employee_id=100001")
    assert traversal.status_code != 200
    encoded_traversal = client.get("/r/bundle-guard/..%2f..%2fsecret.css?employee_id=100001")
    assert encoded_traversal.status_code != 200

    bad_extension = upload_bundle(
        client, "100001", name="bundle-bad-ext", assets=[("payload.exe", b"MZ", "application/octet-stream")]
    )
    assert bad_extension.status_code == 400
    assert "확장자" in bad_extension.json()["detail"]

    too_large = upload_bundle(
        client,
        "100001",
        name="bundle-too-large",
        assets=[("huge.css", b"a" * (share_module.HTML_BUNDLE_ASSET_MAX_BYTES + 1), "text/css")],
    )
    assert too_large.status_code == 400
    assert "5MB" in too_large.json()["detail"]

    non_bundle_asset_request = client.get("/r/never-registered-bundle/style.css?employee_id=100001")
    assert non_bundle_asset_request.status_code == 404


def test_bundle_too_many_assets_are_rejected(boi_app_module):
    client = make_client(boi_app_module)
    assets = [(f"asset-{index}.css", b"a{}", "text/css") for index in range(share_module.HTML_BUNDLE_ASSET_MAX_COUNT + 1)]
    response = upload_bundle(client, "100001", name="bundle-too-many", assets=assets)
    assert response.status_code == 400
    assert "20" in response.json()["detail"]


def test_bundle_delete_removes_whole_folder(boi_app_module):
    client = make_client(boi_app_module)
    assert (
        upload_bundle(client, "100002", name="bundle-delete", assets=[("style.css", b"a{}", "text/css")]).status_code
        == 200
    )
    bundle_dir = boi_app_module.DATA_ROOT / "public" / "html" / "bundle-delete"
    assert bundle_dir.exists()

    deleted = client.delete("/api/share/bundle-delete?employee_id=100002")
    assert deleted.status_code == 200
    assert not bundle_dir.exists()
    assert not (boi_app_module.DATA_ROOT / "public" / "html" / "bundle-delete.md").exists()


def test_bundle_patch_visibility_move_relocates_whole_folder(boi_app_module):
    client = make_client(boi_app_module)
    assert (
        upload_bundle(client, "100002", name="bundle-move", assets=[("style.css", b"a{}", "text/css")]).status_code
        == 200
    )
    old_dir = boi_app_module.DATA_ROOT / "public" / "html" / "bundle-move"
    assert old_dir.exists()

    patched = client.patch(
        "/api/share/bundle-move?employee_id=100002", json={"visibility": "team", "team_id": "aix-tf"}
    )
    assert patched.status_code == 200
    assert not old_dir.exists()
    new_dir = boi_app_module.DATA_ROOT / "team" / "aix-tf" / "html" / "bundle-move"
    assert new_dir.exists()
    assert (new_dir / "index.html").exists()
    assert (new_dir / "style.css").read_bytes() == b"a{}"
    assert (boi_app_module.DATA_ROOT / "team" / "aix-tf" / "html" / "bundle-move.md").exists()

    # ACL이 새 스코프로 정상 적용된다.
    assert client.get("/r/bundle-move?employee_id=100001").status_code == 200
    assert client.get("/r/bundle-move?employee_id=100003").status_code == 404


def test_bundle_name_availability_shared_with_single_file_form(boi_app_module):
    client = make_client(boi_app_module)
    assert (
        upload_bundle(
            client, "100002", name="bundle-or-file", assets=[("style.css", b"a{}", "text/css")]
        ).status_code
        == 200
    )
    # 같은 이름은 파일/폴더 형태와 무관하게 여전히 소유자만 갱신할 수 있다.
    conflict = upload_html(client, "100003", name="bundle-or-file")
    assert conflict.status_code == 409

    overwrite_single = upload_html(client, "100002", name="bundle-or-file", title="단일 파일로 전환")
    assert overwrite_single.status_code == 200
    assert overwrite_single.json()["bundle"] is False
    # 번들 폴더는 정리되고 단일 파일만 남는다.
    assert not (boi_app_module.DATA_ROOT / "public" / "html" / "bundle-or-file").exists()
    assert (boi_app_module.DATA_ROOT / "public" / "html" / "bundle-or-file.html").exists()


def test_single_file_uploads_unaffected_by_bundle_support(boi_app_module):
    # §10 P2-15 회귀 가드: assets 필드를 보내지 않으면 기존 단일 파일 동작이 그대로다.
    client = make_client(boi_app_module)
    created = upload_html(client, "100001", name="still-single-file")
    assert created.status_code == 200
    body = created.json()
    assert body["bundle"] is False
    assert body["assets"] == []
    stored = boi_app_module.DATA_ROOT / "public" / "html" / "still-single-file.html"
    assert stored.exists()
    assert stored.with_suffix(".md").exists()
