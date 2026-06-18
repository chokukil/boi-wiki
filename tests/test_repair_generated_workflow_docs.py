from __future__ import annotations

import importlib.util
import json
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


def test_repair_generated_workflow_docs_rewrites_enriched_langflow_sections(tmp_path: Path):
    module = load_repair_module()
    private_doc = tmp_path / "boi" / "private" / "100001" / "boi-private-100001-enriched.md"
    actions = tmp_path / "actions"
    private_doc.parent.mkdir(parents=True)
    actions.mkdir(parents=True)
    doc_text = """---
type: boi/analysis
boi_id: boi:private:100001:enriched
visibility: private
owner: '100001'
author:
  type: agent
  agent_id: boi-writer-v0.4
source_event:
  event_id: evt-enriched
  event_type: corrective_action.requested.v1
  trace_id: trace-enriched
enrichment:
  status: enriched
---

# Summary

Generated doc.

# Action Results

| Action | Status | Request | Summary |
|---|---|---|---|
| `langflow.equipment.stage_analysis` | `langflow_invoked` | `act-enriched` | # Langflow BoI Execution Result ## Analysis Draft **Current Finding** ETCH-VM-01 설비에서 RESPONSE_CHAIN_ABNORMAL 알람이 발생했습니다. **R |

# Analysis Draft

- # Langflow BoI Execution Result

## Analysis Draft
**Current Finding**
partial
"""
    private_doc.write_text(doc_text, encoding="utf-8")
    message = (
        "# Langflow BoI Execution Result\n\n"
        "## Analysis Draft\n"
        "**Current Finding**\n"
        "ETCH-VM-01 설비에서 RESPONSE_CHAIN_ABNORMAL 알람이 발생했습니다.\n\n"
        "**Evidence Used**\n"
        "- Event: corrective_action.requested.v1\n\n"
        "**Recommended Next Check**\n"
        "- 담당자 확인\n\n"
        "**Manual Handoff**\n"
        "- manual.equipment.confirm_maintenance_done\n\n"
        "**Risk/Approval Notes**\n"
        "- 최종 문장 보존\n\n"
        "## BoI Write Result\n"
        "```json\n{\"ok\": true}\n```"
    )
    (actions / "actions-20990101.jsonl").write_text(
        json.dumps(
            {
                "action_key": "langflow.equipment.stage_analysis",
                "request_id": "act-enriched",
                "employee_id": "100001",
                "event_id": "evt-enriched",
                "event_type": "corrective_action.requested.v1",
                "trace_id": "trace-enriched",
                "boi_id": "boi:private:100001:enriched",
                "status": "langflow_invoked",
                "result": {"status": "langflow_invoked", "request_id": "act-enriched", "message": message},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    action_rows = module.read_action_logs(actions)
    matches = module.find_enrichment_repair_candidates(tmp_path / "boi")
    rewritten, action_count = module.rewrite_enriched_text(matches[0], action_rows)

    assert [item.path for item in matches] == [private_doc]
    assert action_count == 1
    assert "# Langflow BoI Execution Result" not in rewritten
    assert "BoI Write Result" not in rewritten
    assert "**R |" not in rewritten
    assert "최종 문장 보존" in rewritten
    assert "/actions/raw/action%3Aactions-20990101.jsonl%3A1?employee_id=100001" in rewritten
