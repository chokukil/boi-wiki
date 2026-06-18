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
            "status": "unknown",
        }
    )

    assert "missing required metadata: description" in errors
    assert "visibility must be private/team/public" in errors
    assert "status must be draft/reviewed/approved/deprecated" in errors


def test_okf_lint_rejects_reserved_index_used_as_boi_concept(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_markdown(data_root / "boi" / "public" / "actions" / "index.md", valid_private_metadata("boi:private:100001:index"))

    result = lint_data_root(data_root)

    assert not result.ok
    assert any("reserved index.md must be directory listing, not BoI concept frontmatter" in error for error in result.errors)


def test_okf_lint_extracts_bundle_relative_markdown_graph_edges(tmp_path: Path):
    from boi_api.app.okf import lint_data_root

    data_root = tmp_path / "data"
    write_markdown(
        data_root / "boi" / "public" / "sop" / "flow.md",
        valid_private_metadata("boi:private:100001:flow"),
        "# Summary\n\nUse [Trend History](/public/actions/api/request-trend-history.md).",
    )
    write_markdown(
        data_root / "boi" / "public" / "actions" / "api" / "request-trend-history.md",
        valid_private_metadata("boi:private:100001:trend"),
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
        valid_private_metadata("boi:private:100001:media-test"),
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
        valid_private_metadata("boi:private:100001:bad-media-test"),
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


def test_okf_lint_cli_runs_against_repo_data():
    response = subprocess.run(
        ["python", "scripts/okf_lint.py", "--root", "data", "--include-logs"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert response.returncode == 0, response.stdout + response.stderr
    assert "OKF lint passed" in response.stdout
