from __future__ import annotations

from pathlib import Path


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
    assert "http://localhost:8200/mcp" in skill
    assert "Langflow is one connector kind" in skill
    assert "_media/" in skill
