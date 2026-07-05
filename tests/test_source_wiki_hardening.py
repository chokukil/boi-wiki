from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_source_wiki_plan_job_refresh_and_markdown_export(boi_app_module, tmp_path, monkeypatch):
    source_root = tmp_path / "local-source"
    source_root.mkdir()
    (source_root / "README.md").write_text("# Local Source\n\nUse local private notes safely.", encoding="utf-8")
    (source_root / "AGENTS.md").write_text(
        "# Agent Rules\n\nDo not submit raw local notes remotely.\n\n[docs](missing.md)\n\n![sample](evidence/sample.png)",
        encoding="utf-8",
    )
    scripts = source_root / "scripts"
    scripts.mkdir()
    (scripts / "check.sh").write_text("#!/usr/bin/env sh\nprintf 'ok\\n'\n", encoding="utf-8")
    monkeypatch.setenv("SOURCE_WIKI_ALLOWED_ROOTS", str(source_root))
    boi_app_module.SOURCE_WIKI_ROOT = tmp_path / "source-wikis"

    client = TestClient(boi_app_module.app)
    payload = {
        "source_path": str(source_root),
        "wiki_id": "local-source",
        "title": "Local Source",
        "max_files": 10,
        "target_visibility": "public",
    }

    plan = client.post("/api/source-wikis/plan?employee_id=100001", json=payload)
    assert plan.status_code == 200
    plan_body = plan.json()
    assert plan_body["ok"] is True
    assert plan_body["inventory"]["selected_count"] >= 2
    assert plan_body["mutating"] is False

    unconfirmed = client.post("/api/source-wikis/jobs?employee_id=100001", json=payload)
    assert unconfirmed.status_code == 400

    job = client.post("/api/source-wikis/jobs?employee_id=100001", json={**payload, "user_confirmed": True})
    assert job.status_code == 200
    manifest = job.json()
    assert manifest["status"] == "generated"
    assert manifest["pages"]
    assert (boi_app_module.SOURCE_WIKI_ROOT / "local-source" / "latest.json").exists()

    refresh = client.post("/api/source-wikis/local-source/refresh-preview?employee_id=100001", json={"source_path": str(source_root)})
    assert refresh.status_code == 200
    assert refresh.json()["status"] == "fresh"

    markdown = client.get("/api/source-wikis/local-source/markdown?employee_id=100001")
    assert markdown.status_code == 200
    assert "Source Snapshot" in markdown.json()["markdown"]
    assert "[docs](missing.md)" not in markdown.json()["markdown"]
    assert "[link: docs -> missing.md]" in markdown.json()["markdown"]
    assert "![sample]" not in markdown.json()["markdown"]
    assert "[image: sample -> evidence/sample.png]" in markdown.json()["markdown"]


def test_source_wiki_plan_maps_allowlisted_internal_repo_url_to_runtime_outline(boi_app_module, monkeypatch):
    client = TestClient(boi_app_module.app)
    repo_url = "https://git.internal.example/boi/boi-wiki"
    monkeypatch.setenv("SOURCE_WIKI_ALLOWED_REPOS", repo_url)
    payload = {
        "repo_url": repo_url,
        "wiki_id": "boi-wiki-platform-source",
        "title": "BoI Wiki Platform Source",
        "max_files": 1,
        "include_globs": ["README.md"],
    }

    response = client.post("/api/source-wikis/plan?employee_id=100001", json=payload)

    assert response.status_code == 200
    body = response.json()
    selected = {item["path"]: item["role"] for item in body["inventory"]["selected"]}
    assert selected["README.md"] == "entrypoint"
    assert body["source"]["repo_url"] == repo_url

    inventory = {
        "selected": [
            {"path": "README.md", "role": "entrypoint"},
            {"path": "boi_api/app/routes.py", "role": boi_app_module.source_wiki_role_for_path("boi_api/app/routes.py")},
            {"path": "boi_wiki_mcp/app/main.py", "role": boi_app_module.source_wiki_role_for_path("boi_wiki_mcp/app/main.py")},
            {
                "path": "data/boi/public/boi-wiki-manual/guide/final-operator-guide.md",
                "role": boi_app_module.source_wiki_role_for_path("data/boi/public/boi-wiki-manual/guide/final-operator-guide.md"),
            },
            {"path": "tests/test_source_wiki_hardening.py", "role": boi_app_module.source_wiki_role_for_path("tests/test_source_wiki_hardening.py")},
        ],
        "role_counts": {},
    }
    outline_slugs = {item["slug"] for item in boi_app_module.source_wiki_outline("boi-wiki-platform-source", "BoI Wiki Platform Source", inventory)}
    assert {"runtime-surfaces", "knowledge-harness-catalogs", "automation-and-verification", "source-map"}.issubset(outline_slugs)


def test_promotion_preview_is_non_mutating_and_submit_still_requires_confirmation(boi_app_module):
    client = TestClient(boi_app_module.app)
    public_before = sorted(Path(boi_app_module.DATA_ROOT / "public").rglob("*.md"))
    payload = {
        "target_visibility": "public",
        "title": "Preview Candidate",
        "description": "Promotion preview test",
        "body": "# Summary\n\nPreview body.",
        "source_refs": [{"type": "local-private", "ref": "local-note"}],
        "source_local_id": "local-note",
        "source_sha256": "abc123",
    }

    preview = client.post("/api/promotions/preview?employee_id=100001", json=payload)
    assert preview.status_code == 200
    body = preview.json()
    assert body["ok"] is True
    assert body["mutating"] is False
    assert body["approval"]["requires_user_confirmed"] is True
    assert sorted(Path(boi_app_module.DATA_ROOT / "public").rglob("*.md")) == public_before

    submit = client.post("/api/promotions/submit?employee_id=100001", json=payload)
    assert submit.status_code == 422
    assert sorted(Path(boi_app_module.DATA_ROOT / "public").rglob("*.md")) == public_before


def test_agent_memory_review_and_harness_acceptance(boi_app_module):
    client = TestClient(boi_app_module.app)

    review = client.get("/api/agents/boi-wiki/memory/review?employee_id=100001")
    assert review.status_code == 200
    assert review.json()["ok"] is True
    assert "cleanup_preview" in review.json()

    acceptance = client.get("/api/harness/acceptance?employee_id=100001")
    assert acceptance.status_code == 200
    body = acceptance.json()
    assert set(body["matrix"]) == {"Observation", "Context", "Control", "Action", "State", "Verification"}
    assert body["summary"]["total"] >= 6
