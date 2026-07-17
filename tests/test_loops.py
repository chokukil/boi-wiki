from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from boi_api.app import loops as loops_module
from boi_api.app.okf import split_frontmatter


RICH_HTML = (
    "<!doctype html>\n"
    "<html lang=\"ko\">\n"
    "<head><meta charset=\"utf-8\"><title>Etch 공정 주간 대시보드</title></head>\n"
    "<body>\n"
    "<h1>Etch 공정 요약</h1>\n"
    "<h2>DRAM 라인 지표</h2>\n"
    "<h3>세부 항목</h3>\n"
    "<table><tr><td>1</td></tr></table>\n"
    "<script>console.log('chart');</script>\n"
    "<p>이번 주 Etch 장비와 DRAM 라인 상태를 정리한 대시보드 문서입니다.</p>\n"
    "</body>\n"
    "</html>\n"
)


def make_client(boi_app_module) -> TestClient:
    boi_app_module.BOI_AUTO_COMMIT = False
    return TestClient(boi_app_module.app)


def upload_html(
    client: TestClient,
    employee_id: str,
    *,
    name: str,
    content: str = RICH_HTML,
    visibility: str = "public",
    team_id: str = "",
    title: str = "루프 테스트 공유",
    description: str = "pytest loops",
):
    data = {"title": title, "description": description, "visibility": visibility, "name": name}
    if team_id:
        data["team_id"] = team_id
    return client.post(
        f"/api/share/html?employee_id={employee_id}",
        data=data,
        files={"file": (f"{name}.html", content.encode("utf-8"), "text/html")},
    )


def write_boi_doc(
    boi_app_module,
    relative_path: str,
    *,
    boi_id: str,
    title: str,
    description: str = "루프 테스트 문서",
    visibility: str = "public",
    team_id: str = "",
    boi_type: str = "boi/reference",
    body: str = "# Summary\n\n루프 테스트 본문\n",
    extra: dict | None = None,
) -> Path:
    path = boi_app_module.DATA_ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": boi_type,
        "title": title,
        "description": description,
        "tags": ["LoopTest"],
        "timestamp": "2026-07-01 09:00:00+09:00",
        "boi_id": boi_id,
        "visibility": visibility,
        "classification": "internal",
        "owner": "aix-tf",
        "acl_policy": f"acl:team:{team_id}" if visibility == "team" else "acl:public",
        "status": "reviewed",
        "review": {"reviewer": "tf-lead", "review_status": "reviewed"},
        "source_refs": [{"type": "test", "ref": "tests/test_loops.py"}],
    }
    if team_id:
        metadata["team_id"] = team_id
    if extra:
        metadata.update(extra)
    path.write_text(
        "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body,
        encoding="utf-8",
    )
    boi_app_module.invalidate_doc_caches()
    return path


# --- 자동 분석 (결정적 추출) --------------------------------------------------


def test_analyze_html_content_is_deterministic_and_capped():
    analysis = loops_module.analyze_html_content(RICH_HTML, ["Etch", "DRAM", "CVD"])

    assert analysis["title"] == "Etch 공정 주간 대시보드"
    assert [item["text"] for item in analysis["headings"]][:3] == ["Etch 공정 요약", "DRAM 라인 지표", "세부 항목"]
    assert analysis["table_count"] == 1
    assert analysis["script_count"] == 1
    assert analysis["matched_terms"] == ["Etch", "DRAM"]
    assert 0 < len(analysis["excerpt"]) <= loops_module.ANALYSIS_EXCERPT_CHARS
    assert loops_module.analyze_html_content(RICH_HTML, ["Etch", "DRAM", "CVD"]) == analysis

    tags = loops_module.analysis_tags(analysis)
    assert tags[:2] == ["HTML", "Share"]
    assert {"Etch", "DRAM"} <= set(tags)

    many_terms = [f"용어{index}" for index in range(20)]
    noisy = loops_module.analyze_html_content(
        "<html><body>" + " ".join(many_terms) + "</body></html>", many_terms
    )
    assert len(loops_module.analysis_tags(noisy)) <= loops_module.ANALYSIS_MAX_TAGS

    heavy = "<html><body>" + "".join(f"<h2>목차 {index}</h2>" for index in range(15)) + "</body></html>"
    assert len(loops_module.analyze_html_content(heavy)["headings"]) == loops_module.ANALYSIS_MAX_HEADINGS


def test_upload_builds_card_with_analysis_section_and_dictionary_tags(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100001", name="loop-analysis-share").status_code == 200

    card = boi_app_module.DATA_ROOT / "public" / "html" / "loop-analysis-share.md"
    card_text = card.read_text(encoding="utf-8")
    assert "# 자동 분석" in card_text
    assert "## 추출 목차" in card_text
    assert "## 본문 발췌" in card_text
    metadata, body = split_frontmatter(card_text)
    assert metadata["tags"][:2] == ["HTML", "Share"]
    assert {"Etch", "DRAM"} <= set(metadata["tags"])
    assert len(metadata["tags"]) <= loops_module.ANALYSIS_MAX_TAGS
    # 발췌는 코드 펜스 안에 있어 strict-links lint를 깨지 않는다.
    assert "```text" in body

    from boi_api.app.okf import lint_data_root

    result = lint_data_root(boi_app_module.DATA_ROOT.parent, strict_links=True)
    card_errors = [error for error in result.errors if "loop-analysis-share" in error]
    assert card_errors == []


def test_enrich_endpoint_rewrites_analysis_section_with_owner_acl(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100002", name="loop-enrich-share").status_code == 200
    card = boi_app_module.DATA_ROOT / "public" / "html" / "loop-enrich-share.md"

    # 자동 분석 섹션을 지워 enrich가 재작성하는지 확인한다.
    stripped = loops_module._ANALYSIS_SECTION_RE.sub("", card.read_text(encoding="utf-8"))
    assert "# 자동 분석" not in stripped
    card.write_text(stripped, encoding="utf-8")
    boi_app_module.invalidate_doc_caches()

    forbidden = client.post("/api/share/loop-enrich-share/enrich?employee_id=100003")
    assert forbidden.status_code == 403

    missing = client.post("/api/share/never-registered/enrich?employee_id=100002")
    assert missing.status_code == 404

    enriched = client.post("/api/share/loop-enrich-share/enrich?employee_id=100002")
    assert enriched.status_code == 200
    payload = enriched.json()
    assert payload["ok"] is True
    assert payload["updated"] is True
    assert payload["analysis"]["tags"][:2] == ["HTML", "Share"]
    restored = card.read_text(encoding="utf-8")
    assert "# 자동 분석" in restored
    metadata, _body = split_frontmatter(restored)
    assert {"Etch", "DRAM"} <= set(metadata["tags"])

    # admin(서비스 토큰과 같은 역할 해석)도 enrich할 수 있고, 변경 없으면 updated=False.
    repeat = client.post("/api/share/loop-enrich-share/enrich?employee_id=100001")
    assert repeat.status_code == 200
    assert repeat.json()["updated"] is False


# --- 텔레메트리 루프 ---------------------------------------------------------


def test_viewer_raw_and_doc_views_increment_counters(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100001", name="loop-telemetry-share").status_code == 200

    viewer = client.get("/loop-telemetry-share?employee_id=100002")
    assert viewer.status_code == 200
    assert "조회" in viewer.text
    assert client.get("/r/loop-telemetry-share?employee_id=100002").status_code == 200

    assert (boi_app_module.TELEMETRY_ROOT / "counters.json").exists()
    usage = boi_app_module.USAGE_TELEMETRY.usage_counts()
    assert usage["loop-telemetry-share"]["clicks"] == 2
    # html 단축주소 클릭은 대상 지식 카드 boi_id에도 적립된다.
    assert usage["boi:public:html:loop-telemetry-share"]["clicks"] == 2

    doc_page = client.get("/docs/boi:public:harness:overview?employee_id=100001")
    assert doc_page.status_code == 200
    usage = boi_app_module.USAGE_TELEMETRY.usage_counts()
    assert usage["boi:public:harness:overview"]["views"] == 1

    mine = client.get("/api/share/mine?employee_id=100001")
    item = next(entry for entry in mine.json()["items"] if entry["name"] == "loop-telemetry-share")
    assert item["views"] == 2

    events_files = list(boi_app_module.TELEMETRY_ROOT.glob("events-*.jsonl"))
    assert events_files
    kinds = {json.loads(line)["kind"] for line in events_files[0].read_text(encoding="utf-8").splitlines() if line.strip()}
    assert {"shortlink_click", "doc_view"} <= kinds


def test_usage_api_filters_by_read_access(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100002", name="loop-private-usage", visibility="private").status_code == 200
    assert client.get("/r/loop-private-usage?employee_id=100002").status_code == 200

    owner_usage = client.get("/api/telemetry/usage?employee_id=100002")
    assert owner_usage.status_code == 200
    owner_keys = {item["key"] for item in owner_usage.json()["items"]}
    assert "loop-private-usage" in owner_keys

    other_usage = client.get("/api/telemetry/usage?employee_id=100003")
    assert other_usage.status_code == 200
    other_keys = {item["key"] for item in other_usage.json()["items"]}
    assert "loop-private-usage" not in other_keys
    assert "boi:private:100002:html:loop-private-usage" not in other_keys
    # 집계만 노출한다 — 개인별 로그 필드가 응답에 없어야 한다.
    for item in other_usage.json()["items"]:
        assert "employee_id" not in item


# --- 피드백 루프 -------------------------------------------------------------


def test_doc_and_share_feedback_post_get_and_acl(boi_app_module):
    client = make_client(boi_app_module)

    assert upload_html(client, "100002", name="loop-feedback-share").status_code == 200
    card_boi_id = "boi:public:html:loop-feedback-share"

    helpful = client.post(f"/api/docs/{card_boi_id}/feedback?employee_id=100001", json={"helpful": True})
    assert helpful.status_code == 200
    assert helpful.json()["feedback"] == {"helpful": 1, "needs_fix": 0}

    needs_fix = client.post(
        f"/api/docs/{card_boi_id}/feedback?employee_id=100003",
        json={"helpful": False, "comment": "표가 깨져 보입니다"},
    )
    assert needs_fix.status_code == 200
    assert needs_fix.json()["feedback"] == {"helpful": 1, "needs_fix": 1}

    counts = client.get(f"/api/docs/{card_boi_id}/feedback?employee_id=100003")
    assert counts.status_code == 200
    assert counts.json()["helpful"] == 1
    assert counts.json()["needs_fix"] == 1

    share_feedback = client.post(
        "/api/share/loop-feedback-share/feedback?employee_id=100003", json={"helpful": False}
    )
    assert share_feedback.status_code == 200
    assert share_feedback.json()["feedback"]["needs_fix"] == 1
    # 단축주소 피드백은 대상 지식 카드에도 적립된다.
    assert client.get(f"/api/docs/{card_boi_id}/feedback?employee_id=100001").json()["needs_fix"] == 2

    # 코멘트는 JSONL 이벤트에만 남는다 (카운터 파일에는 없음).
    counters_text = (boi_app_module.TELEMETRY_ROOT / "counters.json").read_text(encoding="utf-8")
    assert "표가 깨져 보입니다" not in counters_text
    events_text = "".join(
        path.read_text(encoding="utf-8") for path in boi_app_module.TELEMETRY_ROOT.glob("events-*.jsonl")
    )
    assert "표가 깨져 보입니다" in events_text

    # ACL: private 공유의 카드에는 타인이 피드백을 남길 수 없다 (404로 존재 은닉).
    assert upload_html(client, "100002", name="loop-feedback-private", visibility="private").status_code == 200
    private_card = "boi:private:100002:html:loop-feedback-private"
    assert client.post(f"/api/docs/{private_card}/feedback?employee_id=100003", json={"helpful": True}).status_code == 404
    assert client.post("/api/share/loop-feedback-private/feedback?employee_id=100003", json={"helpful": True}).status_code == 404

    too_long = client.post(
        f"/api/docs/{card_boi_id}/feedback?employee_id=100001",
        json={"helpful": True, "comment": "글" * 501},
    )
    assert too_long.status_code == 422


# --- Gardening 루프 ----------------------------------------------------------


def seed_gardening_fixtures(boi_app_module) -> dict[str, str]:
    ids = {
        "stale": "boi:public:loop-tests:stale-doc",
        "orphan": "boi:public:loop-tests:orphan-doc",
        "broken": "boi:public:loop-tests:broken-link-doc",
        "dup_a": "boi:public:loop-tests:dup-a",
        "dup_b": "boi:public:loop-tests:dup-b",
        "old_card": "boi:public:loop-tests:old-card",
    }
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/stale-doc.md",
        boi_id=ids["stale"],
        title="리뷰 기한 지난 문서",
        extra={"review_after": "2020-01-01"},
    )
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/orphan-doc.md",
        boi_id=ids["orphan"],
        title="역링크 없는 문서",
    )
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/broken-link-doc.md",
        boi_id=ids["broken"],
        title="깨진 링크 문서",
        body="# Summary\n\n[없는 문서](./missing-target.md)를 참조합니다.\n",
    )
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/dup-a.md",
        boi_id=ids["dup_a"],
        title="중복 후보 리포트",
        description="중복 후보 설명 A",
    )
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/dup-b.md",
        boi_id=ids["dup_b"],
        title="중복! 후보 리포트",
        description="중복 후보 설명 B",
    )
    write_boi_doc(
        boi_app_module,
        "public/loop-tests/old-card.md",
        boi_id=ids["old_card"],
        title="오래된 HTML 지식 카드",
        boi_type="boi/html-document",
        extra={"timestamp": "2020-01-01 09:00:00+09:00"},
    )
    return ids


def test_gardening_run_produces_findings_report_and_deduped_events(boi_app_module):
    client = make_client(boi_app_module)
    ids = seed_gardening_fixtures(boi_app_module)

    # 수정 필요 피드백은 feedback finding으로 이어진다.
    feedback = client.post(
        f"/api/docs/{ids['orphan']}/feedback?employee_id=100001", json={"helpful": False}
    )
    assert feedback.status_code == 200

    forbidden = client.post("/api/gardening/run?employee_id=100003")
    assert forbidden.status_code == 403

    first = client.post("/api/gardening/run?employee_id=100001&limit=1000&max_age_days=30")
    assert first.status_code == 200
    body = first.json()
    assert body["ok"] is True
    report = body["report"]
    findings = report["findings"]
    kinds_by_boi = {(item["kind"], item["boi_id"]) for item in findings}
    assert ("stale", ids["stale"]) in kinds_by_boi
    assert ("stale", ids["old_card"]) in kinds_by_boi
    assert ("orphan", ids["orphan"]) in kinds_by_boi
    assert ("feedback", ids["orphan"]) in kinds_by_boi
    assert any(item["kind"] == "broken_link" and "missing-target" in item["detail"] for item in findings)
    assert any(
        item["kind"] == "duplicate" and ids["dup_a"] in item["boi_id"] and ids["dup_b"] in item["boi_id"]
        for item in findings
    )
    counts = report["counts"]
    for kind in ("stale", "orphan", "broken_link", "duplicate", "feedback"):
        assert counts[kind] >= 1
    assert counts["docs_scanned"] > 0
    assert "promotion_candidates" in report

    # 보고서는 runtime에 저장된다 (latest + dated history + 발행 대장).
    assert (boi_app_module.GARDENING_ROOT / "latest.json").exists()
    assert list(boi_app_module.GARDENING_ROOT.glob("report-*.json"))
    assert (boi_app_module.GARDENING_ROOT / "emitted.json").exists()

    # remediation 이벤트가 event bus(fake)로 발행된다.
    assert body["remediation"]["emitted_count"] >= 5
    remediation_events = [
        item["event"]
        for item in boi_app_module.AIOKafkaProducer.sent_events
        if item["event"].get("event_type") == "wiki.remediation.requested.v1"
    ]
    assert remediation_events
    emitted_fingerprints = {event["payload"]["fingerprint"] for event in remediation_events}
    stale_finding = next(item for item in findings if item["kind"] == "stale" and item["boi_id"] == ids["stale"])
    assert stale_finding["fingerprint"] in emitted_fingerprints

    # 두 번째 실행은 같은 finding을 재발행하지 않는다 (fingerprint 대장 dedup).
    second = client.post("/api/gardening/run?employee_id=100001&limit=1000&max_age_days=30")
    assert second.status_code == 200
    assert second.json()["remediation"]["emitted_count"] == 0

    # 보고서 조회 권한: promoter(100002)는 가능, viewer(100003)는 403.
    assert client.get("/api/gardening/report?employee_id=100002").status_code == 200
    assert client.get("/api/gardening/report?employee_id=100003").status_code == 403
    report_body = client.get("/api/gardening/report?employee_id=100001").json()
    assert report_body["report"]["ran_at"]


# --- Promotion 추천 루프 -----------------------------------------------------


def test_promotion_recommendations_ranked_by_seeded_telemetry(boi_app_module):
    client = make_client(boi_app_module)
    write_boi_doc(
        boi_app_module,
        "team/aix-tf/loop-usage-a.md",
        boi_id="boi:team:aix-tf:loop-usage-a",
        title="많이 본 팀 문서",
        visibility="team",
        team_id="aix-tf",
    )
    write_boi_doc(
        boi_app_module,
        "team/aix-tf/loop-usage-b.md",
        boi_id="boi:team:aix-tf:loop-usage-b",
        title="덜 본 팀 문서",
        visibility="team",
        team_id="aix-tf",
    )
    write_boi_doc(
        boi_app_module,
        "team/aix-tf/loop-usage-deprecated.md",
        boi_id="boi:team:aix-tf:loop-usage-deprecated",
        title="Deprecated 팀 문서",
        visibility="team",
        team_id="aix-tf",
        extra={"status": "deprecated"},
    )

    for _ in range(3):
        assert client.get("/docs/boi:team:aix-tf:loop-usage-a?employee_id=100002").status_code == 200
    assert client.get("/docs/boi:team:aix-tf:loop-usage-b?employee_id=100002").status_code == 200
    for _ in range(2):
        assert client.get("/docs/boi:team:aix-tf:loop-usage-deprecated?employee_id=100002").status_code == 200

    forbidden = client.get("/api/promotions/recommendations?employee_id=100003")
    assert forbidden.status_code == 403

    response = client.get("/api/promotions/recommendations?employee_id=100002")
    assert response.status_code == 200
    items = response.json()["items"]
    boi_ids = [item["boi_id"] for item in items]
    assert "boi:team:aix-tf:loop-usage-a" in boi_ids
    assert "boi:team:aix-tf:loop-usage-b" in boi_ids
    assert "boi:team:aix-tf:loop-usage-deprecated" not in boi_ids
    assert boi_ids.index("boi:team:aix-tf:loop-usage-a") < boi_ids.index("boi:team:aix-tf:loop-usage-b")
    top = next(item for item in items if item["boi_id"] == "boi:team:aix-tf:loop-usage-a")
    assert top["usage"] == 3
    assert top["visibility"] == "team"
    # public 문서는 추천 대상이 아니다.
    assert all(item["visibility"] in {"private", "team"} for item in items)


# --- Agent memory usage_count 실증가 -----------------------------------------


def test_memory_recall_adds_runtime_usage_without_frontmatter_rewrite(boi_app_module):
    client = make_client(boi_app_module)

    created = client.post(
        "/api/agents/boi-wiki/memory?employee_id=100001",
        json={"title": "루프 회상 테스트 메모리", "body": "Mermaid 다이어그램 형태의 답변 선호", "memory_kind": "preference"},
    )
    assert created.status_code == 200

    before = boi_app_module.agent_memory_items("100001", q="루프 회상")
    assert before
    memory = before[0]
    assert memory["usage_count"] == 1
    memory_path = next(
        path
        for path in (boi_app_module.DATA_ROOT / "private" / "100001" / "agent-memory").glob("*.md")
        if "루프 회상 테스트" in path.read_text(encoding="utf-8")
    )
    frontmatter_before = memory_path.read_text(encoding="utf-8")

    for _ in range(2):
        recalled = boi_app_module.native_agent_memory_tool("루프 회상", "100001")
        assert recalled["ok"] is True and recalled["count"] >= 1

    after = boi_app_module.agent_memory_items("100001", q="루프 회상")
    assert after[0]["usage_count"] == 3
    assert after[0]["priority"] > memory["priority"]
    # frontmatter는 다시 쓰지 않는다 — recall 카운트는 runtime 카운터에만 산다.
    assert memory_path.read_text(encoding="utf-8") == frontmatter_before
    assert boi_app_module.USAGE_TELEMETRY.memory_recall_count(str(memory["memory_id"])) == 2
