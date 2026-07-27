#!/usr/bin/env python3
"""Verify the generated Universal Simulation MCP artifact and Canvas contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.setup_langflow_reference_flows import (
        BOI_UNIVERSAL_MCP_ARTIFACT,
        BOI_UNIVERSAL_MCP_ARTIFACT_SHA256,
        BOI_UNIVERSAL_MCP_FLOW_ENDPOINT,
        BOI_UNIVERSAL_MCP_FLOW_NAME,
        BOI_UNIVERSAL_MCP_FLOW_VERSION,
        BOI_UNIVERSAL_MCP_TOOL_NAME,
        universal_mcp_flow_contract,
        universal_mcp_flow_contract_sha256,
    )
except ModuleNotFoundError:
    from setup_langflow_reference_flows import (  # type: ignore[no-redef]
        BOI_UNIVERSAL_MCP_ARTIFACT,
        BOI_UNIVERSAL_MCP_ARTIFACT_SHA256,
        BOI_UNIVERSAL_MCP_FLOW_ENDPOINT,
        BOI_UNIVERSAL_MCP_FLOW_NAME,
        BOI_UNIVERSAL_MCP_FLOW_VERSION,
        BOI_UNIVERSAL_MCP_TOOL_NAME,
        universal_mcp_flow_contract,
        universal_mcp_flow_contract_sha256,
    )


EXPECTED_EXECUTION = [
    ("ChatInput-boi-universal-simulation-mcp", 80, 420),
    ("BoIWikiKnowledge-boi-universal-simulation-mcp", 500, 420),
    ("BoIUniversalSimulationMCPAgent-boi-universal-simulation-mcp", 940, 420),
    ("BoIWikiSave-boi-universal-simulation-mcp", 1380, 420),
    ("ChatOutput-boi-universal-simulation-mcp", 1820, 420),
]
EXPECTED_NOTES = [
    ("Note-start-boi-universal-simulation-mcp", 60, 20),
    ("Note-context-boi-universal-simulation-mcp", 480, 20),
    ("Note-agent-boi-universal-simulation-mcp", 920, 20),
    ("Note-save-boi-universal-simulation-mcp", 1360, 20),
    ("Note-output-boi-universal-simulation-mcp", 1800, 20),
]
EXPECTED_NOTE_HEADINGS = [
    "여기서 시작하세요",
    "Wiki와 Ontology가 맥락을 준비합니다",
    "이 Agent만 교체할 수 있습니다",
    "저장 전 반드시 확인합니다",
    "두 가지 방법으로 사용할 수 있습니다",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangle(node: dict[str, Any]) -> tuple[float, float, float, float]:
    position = node.get("position") if isinstance(node.get("position"), dict) else {}
    x = float(position.get("x") or 0)
    y = float(position.get("y") or 0)
    width = float(node.get("width") or 0)
    height = float(node.get("height") or 0)
    if width <= 0 or height <= 0:
        raise AssertionError(f"node has no measurable Canvas bounds: {node.get('id')}")
    return x, y, x + width, y + height


def overlaps(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return not (
        left[2] <= right[0]
        or right[2] <= left[0]
        or left[3] <= right[1]
        or right[3] <= left[1]
    )


def verify(path: Path = BOI_UNIVERSAL_MCP_ARTIFACT) -> dict[str, Any]:
    flow = json.loads(path.read_text(encoding="utf-8"))
    actual_sha256 = sha256(path)
    assert actual_sha256 == BOI_UNIVERSAL_MCP_ARTIFACT_SHA256
    assert flow["name"] == BOI_UNIVERSAL_MCP_FLOW_NAME
    assert flow["endpoint_name"] == BOI_UNIVERSAL_MCP_FLOW_ENDPOINT
    assert BOI_UNIVERSAL_MCP_FLOW_VERSION in flow["tags"]
    assert flow["mcp_enabled"] is True
    assert flow["action_name"] == BOI_UNIVERSAL_MCP_TOOL_NAME

    data = flow["data"]
    assert data["boi_contract"] == universal_mcp_flow_contract()
    assert data["boi_contract_sha256"] == universal_mcp_flow_contract_sha256()
    assert data["viewport"] == {"x": 20, "y": 20, "zoom": 0.6}

    nodes = {
        str(item.get("id") or ""): item
        for item in data["nodes"]
        if isinstance(item, dict)
    }
    assert len(nodes) == 10
    for node_id, x, y in [*EXPECTED_EXECUTION, *EXPECTED_NOTES]:
        assert node_id in nodes
        assert nodes[node_id]["position"] == {"x": x, "y": y}

    for group in (EXPECTED_EXECUTION, EXPECTED_NOTES):
        rectangles = [(node_id, rectangle(nodes[node_id])) for node_id, _, _ in group]
        for index, (left_id, left) in enumerate(rectangles):
            for right_id, right in rectangles[index + 1 :]:
                assert not overlaps(left, right), (
                    f"Canvas nodes overlap: {left_id} and {right_id}"
                )

    note_bottom = max(rectangle(nodes[node_id])[3] for node_id, _, _ in EXPECTED_NOTES)
    execution_top = min(rectangle(nodes[node_id])[1] for node_id, _, _ in EXPECTED_EXECUTION)
    assert note_bottom < execution_top, "Canvas Notes overlap the execution path"

    note_text = json.dumps(
        [nodes[node_id] for node_id, _, _ in EXPECTED_NOTES],
        ensure_ascii=False,
    )
    for heading in EXPECTED_NOTE_HEADINGS:
        assert heading in note_text

    agent_code = str(
        nodes["BoIUniversalSimulationMCPAgent-boi-universal-simulation-mcp"]
        ["data"]["node"]["template"]["code"]["value"]
    )
    knowledge_code = str(
        nodes["BoIWikiKnowledge-boi-universal-simulation-mcp"]
        ["data"]["node"]["template"]["code"]["value"]
    )
    save_code = str(
        nodes["BoIWikiSave-boi-universal-simulation-mcp"]
        ["data"]["node"]["template"]["code"]["value"]
    )
    assert '"real_system_called": False' in agent_code
    assert 'getattr(result, "isError", False)' in knowledge_code
    assert '"sop" in combined' not in knowledge_code
    assert "boi.universal-simulation.result.v1" in save_code
    assert "BOI_RESULT_JSON_B64" in save_code
    assert 'getattr(result, "isError", False)' in save_code

    expected_edges = list(
        zip(
            [item[0] for item in EXPECTED_EXECUTION[:-1]],
            [item[0] for item in EXPECTED_EXECUTION[1:]],
            strict=True,
        )
    )
    actual_edges = [
        (str(item.get("source") or ""), str(item.get("target") or ""))
        for item in data["edges"]
        if isinstance(item, dict)
    ]
    assert actual_edges == expected_edges

    return {
        "ok": True,
        "artifact": str(path),
        "artifact_sha256": actual_sha256,
        "source_of_truth_sha256": BOI_UNIVERSAL_MCP_ARTIFACT_SHA256,
        "contract_sha256": data["boi_contract_sha256"],
        "execution_nodes": len(EXPECTED_EXECUTION),
        "notes": len(EXPECTED_NOTES),
        "edges": len(actual_edges),
        "overlaps": [],
        "viewport": data["viewport"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, default=BOI_UNIVERSAL_MCP_ARTIFACT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.artifact)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
