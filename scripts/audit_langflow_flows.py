#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FLOW_FILE = ROOT / "langflow" / "flows" / "boi_reference_flow.json"
REQUIRED_RUNTIME_FLOWS = {
    "BoI Reference Flow": {"endpoint": "boi-reference-flow", "require_boi_components": True},
    "BoI Equipment Stage Analysis Flow": {"endpoint": "boi-equipment-stage-analysis", "require_boi_components": True},
    "BoI Universal Action Simulator Flow": {"endpoint": "boi-universal-action-simulator", "require_boi_components": True},
}


def flow_graph(flow: dict[str, Any]) -> tuple[set[str], list[tuple[str, str]], dict[str, dict[str, Any]]]:
    data = flow.get("data") or flow
    nodes = data.get("nodes") or []
    edges = data.get("edges") or []
    node_ids = {str(node.get("id")) for node in nodes if node.get("id")}
    node_by_id = {str(node.get("id")): node for node in nodes if node.get("id")}
    edge_pairs = [(str(edge.get("source")), str(edge.get("target"))) for edge in edges]
    return node_ids, edge_pairs, node_by_id


def component_name(node: dict[str, Any]) -> str:
    data = node.get("data") or {}
    return str(data.get("display_name") or data.get("type") or node.get("id") or "")


def boi_nodes(node_by_id: dict[str, dict[str, Any]]) -> set[str]:
    return {
        node_id
        for node_id, node in node_by_id.items()
        if component_name(node).startswith("BoI") or "BoI" in component_name(node)
    }


def connected_components(node_ids: set[str], edges: list[tuple[str, str]]) -> list[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)
    remaining = set(node_ids)
    components = []
    while remaining:
        start = remaining.pop()
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in adjacency[current]:
                if nxt not in seen:
                    seen.add(nxt)
                    remaining.discard(nxt)
                    queue.append(nxt)
        components.append(seen)
    return components


def node_matching(node_by_id: dict[str, dict[str, Any]], label: str) -> str | None:
    for node_id, node in node_by_id.items():
        if label in component_name(node):
            return node_id
    return None


def path_exists(source: str, target: str, edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for start, end in edges:
        adjacency[start].add(end)
    queue = deque([source])
    seen = {source}
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        for nxt in adjacency[current]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def audit_flow(flow: dict[str, Any], *, require_boi_components: bool = False) -> list[str]:
    errors: list[str] = []
    node_ids, edges, node_by_id = flow_graph(flow)
    if not node_ids:
        return ["flow has no nodes"]
    for source, target in edges:
        if source not in node_ids:
            errors.append(f"edge source missing node: {source}")
        if target not in node_ids:
            errors.append(f"edge target missing node: {target}")
    boi = boi_nodes(node_by_id)
    if require_boi_components and not boi:
        errors.append("required BoI custom components are missing")
    if require_boi_components and boi:
        required_labels = [
            "BoI Harness Loader",
            "BoI Wiki Reader",
            "BoI Context Normalizer",
            "BoI Prompt Composer",
            "BoI Metadata Builder",
            "BoI Policy",
            "BoI Wiki Writer",
            "BoI Action Invoker",
            "BoI Result Composer",
        ]
        for label in required_labels:
            if not node_matching(node_by_id, label):
                errors.append(f"required BoI custom component is missing: {label}")
        components = connected_components(node_ids, edges)
        component_by_node = {node_id: index for index, comp in enumerate(components) for node_id in comp}
        connected_boi = [node_id for node_id in boi if any(n in boi and n != node_id for n in components[component_by_node[node_id]])]
        isolated_boi = sorted(boi - set(connected_boi))
        if isolated_boi:
            labels = [component_name(node_by_id[node_id]) for node_id in isolated_boi]
            errors.append(f"BoI custom components are disconnected: {labels}")
        if len(components) > 1:
            labels = [[component_name(node_by_id[node_id]) for node_id in sorted(component)] for component in components]
            errors.append(f"flow has disconnected node groups: {labels}")
        llm = node_matching(node_by_id, "Gemma OpenAI-Compatible LLM")
        output = node_matching(node_by_id, "BoI Draft Output")
        prompt = node_matching(node_by_id, "BoI Prompt Composer")
        writer = node_matching(node_by_id, "BoI Wiki Writer")
        result = node_matching(node_by_id, "BoI Result Composer")
        for label, node_id in {"Gemma LLM": llm, "BoI Draft Output": output, "BoI Prompt Composer": prompt, "BoI Wiki Writer": writer, "BoI Result Composer": result}.items():
            if not node_id:
                errors.append(f"runtime execution node is missing: {label}")
        if prompt and llm and not path_exists(prompt, llm, edges):
            errors.append("BoI Prompt Composer is not connected to the Gemma LLM input path")
        if llm and writer and not path_exists(llm, writer, edges):
            errors.append("Gemma LLM output is not connected to BoI Wiki Writer")
        if writer and result and not path_exists(writer, result, edges):
            errors.append("BoI Wiki Writer result is not connected to final result composer")
        if result and output and not path_exists(result, output, edges):
            errors.append("BoI Result Composer is not connected to ChatOutput")
    return errors


def get_auth_headers(client: httpx.Client, langflow_url: str, api_key: str, auth_mode: str) -> dict[str, str]:
    if auth_mode == "api-key":
        return {"x-api-key": api_key}
    response = client.get(f"{langflow_url}/api/v1/auto_login")
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Langflow auto_login did not return access_token")
    return {"Authorization": f"Bearer {token}"}


def runtime_flows(langflow_url: str, api_key: str, auth_mode: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=30) as client:
        headers = get_auth_headers(client, langflow_url.rstrip("/"), api_key, auth_mode)
        response = client.get(f"{langflow_url.rstrip('/')}/api/v1/flows/", headers=headers)
        response.raise_for_status()
        flows = response.json()
    if not isinstance(flows, list):
        raise RuntimeError("Langflow flows endpoint did not return a list")
    return [flow for flow in flows if isinstance(flow, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit BoI Langflow flow connectivity.")
    parser.add_argument("--flow-file", default=str(DEFAULT_FLOW_FILE), help="Local flow JSON to audit.")
    parser.add_argument("--runtime", action="store_true", help="Also audit flows from Langflow runtime.")
    parser.add_argument("--langflow-url", default=os.getenv("LANGFLOW_URL", "http://localhost:7860"))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me"))
    parser.add_argument("--auth-mode", choices=["auto-login", "api-key"], default=os.getenv("LANGFLOW_AUTH_MODE", "auto-login"))
    args = parser.parse_args()

    errors: list[str] = []
    flow_path = Path(args.flow_file)
    if flow_path.exists():
        local_flow = json.loads(flow_path.read_text(encoding="utf-8"))
        errors.extend(f"local:{error}" for error in audit_flow(local_flow))
    else:
        errors.append(f"local flow file not found: {flow_path}")

    runtime_summary: dict[str, Any] = {}
    if args.runtime:
        flows = runtime_flows(args.langflow_url, args.langflow_api_key, args.auth_mode)
        by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for flow in flows:
            by_name[str(flow.get("name") or "")].append(flow)
        for flow_name, rule in REQUIRED_RUNTIME_FLOWS.items():
            matches = by_name.get(flow_name) or []
            runtime_summary[flow_name] = len(matches)
            if not matches:
                errors.append(f"runtime flow missing: {flow_name}")
                continue
            if len(matches) > 1:
                errors.append(f"runtime flow has duplicates: {flow_name} x{len(matches)}")
            selected = sorted(matches, key=lambda item: str(item.get("updated_at") or ""), reverse=True)[0]
            errors.extend(
                f"runtime:{flow_name}:{error}"
                for error in audit_flow(selected, require_boi_components=bool(rule["require_boi_components"]))
            )

    result = {"ok": not errors, "errors": errors, "runtime_summary": runtime_summary}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
