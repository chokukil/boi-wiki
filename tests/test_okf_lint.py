from __future__ import annotations

import json
import subprocess
import hashlib
from pathlib import Path


def valid_private_metadata(boi_id: str = "boi:private:100001:lint:001") -> dict:
    return {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/test",
        "title": "OKF Lint Test",
        "description": "OKF lint fixture",
        "tags": ["OKF", "Test"],
        "timestamp": "2026-06-17T15:00:00+09:00",
        "boi_id": boi_id,
        "visibility": "private",
        "classification": "internal",
        "owner": "100001",
        "author": {"type": "agent", "agent_id": "test"},
        "acl_policy": "acl:private:100001",
        "status": "draft",
    }


def valid_public_metadata(boi_id: str = "boi:public:lint:test") -> dict:
    return {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/test",
        "title": "OKF Lint Test",
        "description": "OKF lint fixture",
        "tags": ["OKF", "Test"],
        "timestamp": "2026-06-17T15:00:00+09:00",
        "boi_id": boi_id,
        "visibility": "public",
        "classification": "internal",
        "owner": "public",
        "author": {"type": "agent", "agent_id": "test"},
        "acl_policy": "acl:public",
        "status": "draft",
        "source_refs": [{"type": "test", "ref": "okf-lint-fixture"}],
        "review": {"reviewer": "test-reviewer", "review_status": "fixture"},
    }


def write_markdown(path: Path, metadata: dict, body: str = "# Summary\n\nOKF body") -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body + "\n", encoding="utf-8")


def tiny_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
        b"\x89\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01"
        b"\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_okf_lint_module_accepts_checked_in_boi_docs():
    from boi_api.app.okf import lint_data_root

    result = lint_data_root(Path("data"), include_logs=True)

    assert result.ok, result.errors[:5]
    assert result.checked_markdown_count >= 1
    assert result.markdown_link_count > 0


def test_okf_core_metadata_accepts_minimal_official_concept():
    from boi_api.app.okf import validate_boi_profile_metadata, validate_okf_core_metadata

    metadata = {"type": "Playbook"}

    assert validate_okf_core_metadata(metadata) == []
    assert "missing required metadata: boi_id" in validate_boi_profile_metadata(metadata)


def test_okf_lint_reports_invalid_metadata():
    from boi_api.app.okf import validate_okf_metadata

    errors = validate_okf_metadata(
        {
            "okf_version": "0.1",
            "boi_profile_version": "0.1",
            "type": "boi/test",
            "title": "Broken",
            "visibility": "org",
            "classification": "secret",
            "status": "unknown",
        }
    )

    assert "missing required metadata: description" in errors
    assert "visibility must be private/team/public" in errors
    assert "classification must be internal/confidential/restricted" in errors
    assert "status must be draft/reviewed/approved/deprecated" in errors


def test_okf_lint_rejects_unknown_classification(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    metadata = valid_public_metadata("boi:public:lint:bad-classification")
    metadata["classification"] = "secret"
    write_markdown(data_root / "boi" / "public" / "bad-classification.md", metadata)

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("classification must be internal/confidential/restricted" in error for error in result.errors)


def test_okf_lint_rejects_private_owner_acl_path_mismatch(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    metadata = valid_private_metadata("boi:private:100001:mismatch")
    metadata["owner"] = "100002"
    metadata["acl_policy"] = "acl:private:100002"
    write_markdown(data_root / "boi" / "private" / "100001" / "bad-private.md", metadata)

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("private BoI owner must match path employee_id" in error for error in result.errors)
    assert any("private BoI acl_policy must match acl:private:{employee_id}" in error for error in result.errors)


def test_okf_lint_rejects_team_acl_path_mismatch(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    metadata = valid_public_metadata("boi:team:platform:mismatch")
    metadata.update(
        {
            "visibility": "team",
            "owner": "platform",
            "team_id": "process",
            "acl_policy": "acl:team:process",
        }
    )
    write_markdown(data_root / "boi" / "team" / "platform" / "bad-team.md", metadata)

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("team BoI team_id must match path team_id" in error for error in result.errors)
    assert any("team BoI acl_policy must match acl:team:{team_id}" in error for error in result.errors)


def test_okf_lint_rejects_reserved_index_used_as_boi_concept(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_markdown(data_root / "boi" / "public" / "actions" / "index.md", valid_public_metadata("boi:public:actions:index"))

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("reserved index.md must be directory listing, not BoI concept frontmatter" in error for error in result.errors)


def test_okf_lint_extracts_bundle_relative_markdown_graph_edges(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_markdown(
        data_root / "boi" / "public" / "sop" / "flow.md",
        valid_public_metadata("boi:public:sop:flow"),
        "# Summary\n\nUse [Trend History](/public/actions/api/request-trend-history.md).",
    )
    write_markdown(
        data_root / "boi" / "public" / "actions" / "api" / "request-trend-history.md",
        valid_public_metadata("boi:public:actions:api:request-trend-history"),
        "# Summary\n\nTrend API.",
    )

    result = lint_data_root(data_root, strict_links=True)

    assert result.ok, result.errors
    assert result.markdown_link_count == 1
    assert result.link_edges == [
        {
            "source": "public/sop/flow",
            "target": "public/actions/api/request-trend-history",
            "href": "/public/actions/api/request-trend-history.md",
            "label": "Trend History",
            "resolved": True,
        }
    ]


def test_okf_lint_validates_local_media_assets_with_manifest(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    image_path = data_root / "boi" / "public" / "manual" / "_media" / "browser" / "sample.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = tiny_png_bytes()
    image_path.write_bytes(image_bytes)
    digest = hashlib.sha256(image_bytes).hexdigest()
    (image_path.parents[1] / "media-manifest.yaml").write_text(
        "media:\n"
        "  - path: /public/manual/_media/browser/sample.png\n"
        f"    sha256: {digest}\n"
        "    source_kind: test\n",
        encoding="utf-8",
    )
    write_markdown(
        data_root / "boi" / "public" / "manual" / "media-test.md",
        valid_public_metadata("boi:public:manual:media-test"),
        "# Summary\n\n![Sample](/public/manual/_media/browser/sample.png)",
    )

    result = lint_data_root(data_root, strict_media=True)

    assert result.ok, result.errors
    assert result.media_link_count == 1


def test_okf_lint_accepts_relative_data_root_with_strict_media():
    from boi_api.app.okf import lint_data_root

    result = lint_data_root(Path("data"), strict_media=True)

    assert result.ok, result.errors[:5]


def test_okf_lint_rejects_media_outside_media_directory(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    image_path = data_root / "boi" / "public" / "manual" / "sample.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(tiny_png_bytes())
    write_markdown(
        data_root / "boi" / "public" / "manual" / "media-test.md",
        valid_public_metadata("boi:public:manual:bad-media-test"),
        "# Summary\n\n![Sample](/public/manual/sample.png)",
    )

    result = lint_data_root(data_root, strict_media=True)

    assert not result.ok
    assert any("image link must target a _media directory" in error for error in result.errors)


def test_okf_lint_includes_materialized_log_payloads(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_markdown(data_root / "boi" / "private" / "100001" / "private-seed-note.md", valid_private_metadata("boi:private:100001:seed"))
    log_path = data_root / "events" / "events-20260617.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(
        json.dumps(
            {
                "result": {
                    "dispatch_result": {
                        "results": [
                            {
                                "action_key": "boi.materialize_event",
                                "result": {
                                    "response": {
                                        "item": {
                                            "metadata": valid_private_metadata("boi:private:100001:from-log"),
                                            "body": "# Summary\n\nRecovered from log",
                                            "uri": "/private/100001/boi-private-100001-from-log.md",
                                        }
                                    }
                                },
                            }
                        ]
                    }
                }
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = lint_data_root(data_root, include_logs=True)

    assert result.ok, result.errors
    assert result.checked_log_item_count == 1


def test_okf_lint_rejects_materialized_log_acl_path_mismatch(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    log_path = data_root / "events" / "events-20260617.jsonl"
    log_path.parent.mkdir(parents=True)
    metadata = valid_private_metadata("boi:private:100001:from-log-mismatch")
    metadata["owner"] = "100002"
    metadata["acl_policy"] = "acl:private:100002"
    log_path.write_text(
        json.dumps(
            {
                "result": {
                    "response": {
                        "item": {
                            "metadata": metadata,
                            "body": "# Summary\n\nRecovered from log",
                            "uri": "/private/100001/boi-private-100001-from-log-mismatch.md",
                        }
                    }
                }
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = lint_data_root(data_root, include_logs=True)

    assert not result.ok
    assert result.checked_log_item_count == 1
    assert any("private BoI owner must match path employee_id" in error for error in result.errors)
    assert any("private BoI acl_policy must match acl:private:{employee_id}" in error for error in result.errors)


def write_html_share_pair(data_root: Path, *, name: str = "lint-share", extra_html: str = "") -> tuple[Path, Path]:
    """공유 HTML + 지식 카드 쌍을 실제 share 빌더로 생성한다."""
    from boi_api.app import share as share_module

    html_path = data_root / "boi" / "public" / "html" / f"{name}.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    original = (
        "<!doctype html>\n"
        f"<html lang=\"ko\">\n<head><meta charset=\"utf-8\"><title>{name}</title>{extra_html}</head>\n"
        "<body><h1>공유 HTML 문서</h1></body>\n</html>\n"
    )
    original_sha = hashlib.sha256(original.encode("utf-8")).hexdigest()
    profile = share_module.build_html_profile_jsonld(
        name=name,
        title="Lint Share",
        description="okf lint fixture",
        visibility="public",
        team_id="",
        owner="테스트 사용자 (100001)",
        owner_employee_id="100001",
        reviewer="테스트 사용자 (100001)",
        timestamp="2026-07-17T12:00:00+09:00",
        original_filename=f"{name}.html",
        original_sha256=original_sha,
    )
    stored = share_module.inject_html_profile(original, profile).encode("utf-8")
    html_path.write_bytes(stored)
    card_path = html_path.with_suffix(".md")
    card_path.write_text(
        share_module.build_knowledge_card_markdown(
            name=name,
            title="Lint Share",
            description="okf lint fixture",
            visibility="public",
            team_id="",
            owner="테스트 사용자 (100001)",
            owner_label="테스트 사용자 (100001)",
            owner_employee_id="100001",
            created_at="2026-07-17T12:00:00+09:00",
            updated_at="2026-07-17T12:00:00+09:00",
            original_filename=f"{name}.html",
            original_sha256=original_sha,
            stored_sha256=hashlib.sha256(stored).hexdigest(),
            html_repo_path=f"data/boi/public/html/{name}.html",
        ),
        encoding="utf-8",
    )
    return html_path, card_path


def test_okf_lint_accepts_html_share_pair(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_html_share_pair(data_root)

    result = lint_data_root(data_root, strict_links=True, strict_media=True)

    assert result.ok, result.errors
    assert result.checked_html_count == 1
    assert result.warnings == []


def test_okf_lint_rejects_html_without_profile_or_card(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    html_path = data_root / "boi" / "public" / "html" / "no-profile.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text("<!doctype html>\n<html><head></head><body>no profile</body></html>\n", encoding="utf-8")

    result = lint_data_root(data_root)

    assert not result.ok
    assert result.checked_html_count == 1
    assert any("missing or unparseable BoI HTML Profile" in error for error in result.errors)
    assert any("sibling knowledge card" in error for error in result.errors)


def test_okf_lint_rejects_html_card_sha256_mismatch(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    html_path, _card_path = write_html_share_pair(data_root, name="lint-mismatch")
    html_path.write_bytes(html_path.read_bytes() + "<!-- tampered after card generation -->".encode("utf-8"))

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("html artifact sha256 mismatch with knowledge card" in error for error in result.errors)


def test_okf_lint_warns_on_external_html_references(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_html_share_pair(
        data_root,
        name="lint-external",
        extra_html='<script src="https://cdn.example.com/chart.js"></script>',
    )

    result = lint_data_root(data_root)

    assert result.ok, result.errors
    assert any("사내망" in warning for warning in result.warnings)


def test_okf_lint_cli_runs_against_repo_data():
    response = subprocess.run(
        ["python", "scripts/okf_lint.py", "--root", "data", "--include-logs"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert response.returncode == 0, response.stdout + response.stderr
    assert "OKF lint passed" in response.stdout
