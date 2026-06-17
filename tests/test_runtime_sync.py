from __future__ import annotations

from pathlib import Path


def test_runtime_sync_script_preserves_logs_and_generated_boi_docs():
    script = Path("scripts/sync_runtime_mirror.sh")

    text = script.read_text(encoding="utf-8")

    assert "--protect=data/events/*.jsonl" in text
    assert "--protect=data/actions/*.jsonl" in text
    assert "--protect=data/boi/private/*/boi-private-*.md" in text
    assert "--protect=data/boi/team/*/boi-team-*.md" in text
    assert "--protect=data/boi/public/boi-public-*.md" in text
    assert "--delete" in text
    assert "rsync" in text
