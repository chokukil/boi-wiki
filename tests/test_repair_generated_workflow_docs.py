from __future__ import annotations

import importlib.util
from pathlib import Path


def load_repair_module():
    path = Path.cwd() / "scripts" / "repair_generated_workflow_docs.py"
    spec = importlib.util.spec_from_file_location("repair_generated_workflow_docs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repair_generated_workflow_docs_targets_only_private_generated_boilerplate(tmp_path: Path):
    module = load_repair_module()
    private_doc = tmp_path / "boi" / "private" / "100001" / "boi-private-100001-legacy.md"
    public_doc = tmp_path / "boi" / "public" / "legacy.md"
    private_doc.parent.mkdir(parents=True)
    public_doc.parent.mkdir(parents=True)
    legacy_text = """---
type: boi/analysis
boi_id: boi:private:100001:legacy
visibility: private
owner: '100001'
author:
  type: agent
  agent_id: boi-writer-v0.4
event_type: root_cause.analysis.requested.v1
---

# Summary

Legacy generated doc

# AI Native Workflow Interpretation

1. Event Broker는 업무 시점, 예: 설비 Alarm 발생 또는 Trend 이상 감지를 발행합니다.
"""
    private_doc.write_text(legacy_text, encoding="utf-8")
    public_doc.write_text(legacy_text.replace("visibility: private", "visibility: public"), encoding="utf-8")

    matches = module.find_repair_candidates(tmp_path / "boi")
    preview = module.rewrite_legacy_text(legacy_text)

    assert [item.path for item in matches] == [private_doc]
    assert "# AI Native Workflow Interpretation" not in preview
    assert "# Legacy Notes" in preview
