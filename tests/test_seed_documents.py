from __future__ import annotations

from pathlib import Path

import yaml


def active_markdown_text(root: Path) -> str:
    rows: list[str] = []
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            metadata = yaml.safe_load(text.split("---", 2)[1]) or {}
            if metadata.get("status") == "deprecated":
                continue
        rows.append(text)
    return "\n".join(rows)


def test_cascade_roadmap_seed_boi_exists_for_executive_storyline():
    path = Path("data/boi/team/aix-tf/team-aix-tf-cascade-roadmap.md")

    text = path.read_text(encoding="utf-8")

    assert "TM → CEO → AIX 확산 TF" in text
    assert "1인 1 Agent를 조직의 지식으로 축적하는 업무 맥락 자산화 PoC" in text
    assert "2개월 PoC" in text
    assert "2026 H2" in text
    assert "2027" in text
    assert "2028+" in text
    assert "fallback" not in text.lower()


def test_ppt_capture_plan_document_lists_real_poc_screens():
    path = Path("docs/PPT_CAPTURE_PLAN.md")

    text = path.read_text(encoding="utf-8")

    assert "BoI Wiki 홈" in text
    assert "Event Type Catalog" in text
    assert "Event Stream" in text
    assert "Action Catalog" in text
    assert "Langflow" in text
    assert "Kafka UI" in text
    assert "실제 화면 캡처" in text


def test_boi_wiki_manual_and_agent_skill_cover_mcp_actions_langflow_and_media():
    manual_root = Path("data/boi/public/boi-wiki-manual")
    skill = Path("skills/boi-wiki-agent/SKILL.md").read_text(encoding="utf-8")

    assert (manual_root / "overview.md").exists()
    assert (manual_root / "mcp" / "register-and-use-boi-wiki-mcp.md").exists()
    assert (manual_root / "actions" / "multi-action-connector-guide.md").exists()
    assert (manual_root / "langflow" / "connected-flow-guide.md").exists()
    assert (manual_root / "media" / "okf-media-and-screenshots.md").exists()
    assert (manual_root / "security" / "sso-and-permissions.md").exists()
    assert "http://localhost:8200/mcp/v2" in skill
    assert "boi_agent" in skill
    assert "boi_tools_search" in skill
    assert "work_session_id" in skill
    assert "index.md" in skill
    assert "status: deprecated" in skill
    assert "Langflow is one connector kind" in skill
    assert "_media/" in skill


def test_boi_wiki_manual_matches_workflow_task_builder_model():
    manual_root = Path("data/boi/public/boi-wiki-manual")

    required_docs = [
        manual_root / "concepts" / "work-boi-first-model.md",
        manual_root / "sop-workflows" / "workflow-task-builder-step-by-step.md",
        manual_root / "sop-workflows" / "create-and-connect-sop.md",
        manual_root / "data-lake" / "data-lake-artifact-lifecycle.md",
        manual_root / "workflows" / "workflow-definition-registration-guide.md",
        manual_root / "mcp" / "register-and-use-boi-wiki-mcp.md",
        manual_root / "agent" / "work-context-pack.md",
    ]
    for path in required_docs:
        assert path.exists(), path

    concept = (manual_root / "concepts" / "work-boi-first-model.md").read_text(encoding="utf-8")
    for expected in [
        "Workflow / Task",
        "Manual",
        "Copilot",
        "Autopilot",
        "TAT",
        "Data Lake artifact",
    ]:
        assert expected in concept

    overview = (manual_root / "overview.md").read_text(encoding="utf-8")
    index = (manual_root / "index.md").read_text(encoding="utf-8")
    assert "Workflow/Task Builder 따라하기" in overview
    assert "Workflow/Task Builder 따라하기" in index
    assert "자료 보관함과 업무 근거" in overview
    assert "자료 보관함과 업무 근거" in index


def test_boi_wiki_manual_does_not_regress_to_legacy_registration_or_agent_exposure_copy():
    roots = [Path("data/boi/public/boi-wiki-manual"), Path("data/boi/public/harness")]
    text = "\n".join(active_markdown_text(root) for root in roots)

    forbidden = [
        "Event -> SOP -> Action 3단 구조",
        "이번에는 건너뛰기",
        "Pet Agent는 모든 주요 화면에 공통으로 mount",
        "Web shell은 우측 하단 BoI Agent를 제공한다.",
    ]
    for phrase in forbidden:
        assert phrase not in text

    assert "BOI_PET_AGENT_ENABLED=true" in text
    assert "BOI_OPS_CENTER_ENABLED=false" in text
    assert "Workflow/Task Builder 따라하기" in text
    assert "자료 보관함과 업무 근거" in text


def test_boi_wiki_mcp_manual_explains_client_registration_and_browser_troubleshooting():
    text = Path("data/boi/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md").read_text(encoding="utf-8")

    assert "Codex" in text
    assert "Claude Desktop" in text
    assert "Cursor" in text
    assert "http://localhost:8200" in text
    assert "<BOI_MCP_URL>/mcp/v2" in text
    assert "Streamable HTTP" in text
    assert "10개 도구" in text
    assert "boi_agent" in text
    assert "boi_search" in text
    assert "boi_context" in text
    assert "boi_plan" in text
    assert "boi_confirm" in text
    assert "boi_tools_search" in text
    assert "neighbors" in text
    assert "path" in text
    assert "impact" in text
    assert "tour" in text
    assert "BOI_PAT" in text
    assert "401" in text
    assert "406" in text
    assert "python scripts/check_agent_v2_interface_parity.py" in text


def test_readme_links_mcp_status_and_validation_commands():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "BoI Wiki MCP" in text
    assert "http://localhost:8200/" in text
    assert "http://localhost:8200/mcp" in text
    assert "python scripts/check_boi_wiki_mcp.py" in text


def test_shared_docs_do_not_expose_legacy_private_me_or_real_nas_domain():
    roots = [Path("README.md"), Path("data/boi/public/boi-wiki-manual"), Path("data/boi/public/harness")]
    combined = []
    for root in roots:
        if root.is_file():
            combined.append(root.read_text(encoding="utf-8"))
            continue
        for path in root.rglob("*.md"):
            combined.append(path.read_text(encoding="utf-8"))
    text = "\n".join(combined)

    assert "private" + "/me" not in text
    assert "private" + "\\me" not in text
    assert "mangugil" + ".iptime.org" not in text
