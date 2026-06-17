from __future__ import annotations

import json
import subprocess
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


def test_okf_lint_module_accepts_checked_in_boi_docs():
    from boi_api.app.okf import lint_data_root

    result = lint_data_root(Path("data"), include_logs=True)

    assert result.ok, result.errors[:5]
    assert result.checked_markdown_count >= 1


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
