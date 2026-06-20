#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "langflow" / "flows" / "boi_reference_flow.manifest.json"
DEFAULT_ENDPOINT_NAME = "boi-reference-flow"
BOI_COMPONENT_KEYS = {
    "harness": "ext:boi:BoIHarnessLoader@extra",
    "reader": "ext:boi:BoIWikiReader@extra",
    "context": "ext:boi:BoIContextNormalizer@extra",
    "prompt": "ext:boi:BoIPromptComposer@extra",
    "metadata": "ext:boi:BoIMetadataBuilder@extra",
    "policy": "ext:boi:BoIPolicyGuard@extra",
    "writer": "ext:boi:BoIWikiWriter@extra",
    "action": "ext:boi:BoIActionInvoker@extra",
    "result": "ext:boi:BoIResultComposer@extra",
}


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    flow_file = ROOT / manifest["flow_file"]
    if not flow_file.exists():
        raise FileNotFoundError(f"flow file not found: {flow_file}")
    manifest["_flow_file_path"] = str(flow_file)
    return manifest


def env(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/") if name.endswith("URL") else os.getenv(name, default)


def get_auth_headers(client: httpx.Client, langflow_url: str, api_key: str, auth_mode: str) -> dict[str, str]:
    if auth_mode == "api-key":
        return {"x-api-key": api_key}

    response = client.get(f"{langflow_url}/api/v1/auto_login")
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Langflow auto_login response did not include access_token")
    return {"Authorization": f"Bearer {token}"}


def upload_flow(client: httpx.Client, langflow_url: str, headers: dict[str, str], flow_file: Path) -> dict[str, Any]:
    url = f"{langflow_url}/api/v1/flows/upload/"
    with flow_file.open("rb") as handle:
        response = client.post(url, headers=headers, files={"file": (flow_file.name, handle, "application/json")})
    response.raise_for_status()
    return response.json()


def compact_handle(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace('"', "\u0153")


def first_uploaded_flow(upload_result: Any) -> dict[str, Any]:
    if isinstance(upload_result, list) and upload_result and isinstance(upload_result[0], dict):
        return upload_result[0]
    if isinstance(upload_result, dict):
        return upload_result
    raise RuntimeError("Langflow upload did not return a flow object")


def get_components(client: httpx.Client, langflow_url: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(f"{langflow_url}/api/v1/all", headers=headers)
    response.raise_for_status()
    components = response.json()
    boi_components = components.get("boi") or {}
    missing = [key for key in BOI_COMPONENT_KEYS.values() if key not in boi_components]
    if missing:
        raise RuntimeError(f"BoI Langflow custom components are not loaded: {missing}")
    return components


def list_flows(client: httpx.Client, langflow_url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = client.get(f"{langflow_url}/api/v1/flows/", headers=headers)
    response.raise_for_status()
    flows = response.json()
    if not isinstance(flows, list):
        raise RuntimeError("Langflow flows API did not return a list")
    return [flow for flow in flows if isinstance(flow, dict)]


def delete_flows_by_name(client: httpx.Client, langflow_url: str, headers: dict[str, str], names: set[str]) -> list[str]:
    deleted: list[str] = []
    for flow in list_flows(client, langflow_url, headers):
        if str(flow.get("name") or "") not in names:
            continue
        flow_id = flow.get("id")
        if not flow_id:
            continue
        response = client.delete(f"{langflow_url}/api/v1/flows/{flow_id}", headers=headers)
        if response.status_code not in {200, 202, 204, 404}:
            response.raise_for_status()
        deleted.append(str(flow_id))
    return deleted


def create_custom_node(
    components: dict[str, Any],
    key: str,
    node_id: str,
    x: int,
    y: int,
    values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    component = json.loads(json.dumps(components["boi"][key], ensure_ascii=False))
    component["id"] = node_id
    for field, value in (values or {}).items():
        if field in component.get("template", {}):
            component["template"][field]["value"] = value
    output_name = (component.get("outputs") or [{}])[0].get("name")
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "dragging": False,
        "selected": False,
        "measured": {"width": 320, "height": 260},
        "width": 320,
        "height": 260,
        "data": {
            "id": node_id,
            "type": key,
            "node": component,
            "display_name": component.get("display_name"),
            "description": component.get("description", ""),
            "selected_output": output_name,
            "showNode": True,
        },
    }


def first_output(node: dict[str, Any]) -> dict[str, Any]:
    return (node["data"]["node"].get("outputs") or [{}])[0]


def template_field(node: dict[str, Any], field_name: str) -> dict[str, Any]:
    return node["data"]["node"]["template"][field_name]


def create_edge(
    source: dict[str, Any],
    target: dict[str, Any],
    target_field_name: str,
) -> dict[str, Any]:
    output = first_output(source)
    field = template_field(target, target_field_name)
    source_handle = {
        "dataType": source["data"]["type"],
        "id": source["id"],
        "name": output["name"],
        "output_types": output.get("types") or output.get("output_types") or ["Data"],
    }
    target_handle = {
        "fieldName": target_field_name,
        "id": target["id"],
        "inputTypes": field.get("input_types") or ["Data"],
        "type": field.get("type") or "other",
    }
    source_handle_text = compact_handle(source_handle)
    target_handle_text = compact_handle(target_handle)
    return {
        "animated": False,
        "className": "",
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
        "id": f"reactflow__edge-{source['id']}{source_handle_text}-{target['id']}{target_handle_text}",
        "selected": False,
        "source": source["id"],
        "sourceHandle": source_handle_text,
        "target": target["id"],
        "targetHandle": target_handle_text,
    }


def node_label(node: dict[str, Any]) -> str:
    data = node.get("data") or {}
    return str(data.get("display_name") or data.get("type") or node.get("id") or "")


def find_node(data: dict[str, Any], label_contains: str) -> dict[str, Any]:
    for node in data.get("nodes") or []:
        if label_contains in node_label(node):
            return node
    raise RuntimeError(f"base flow node not found: {label_contains}")


def compact_base_flow(base_flow: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(json.dumps(base_flow.get("data") or {}, ensure_ascii=False))
    nodes = []
    for node in data.get("nodes") or []:
        label = node_label(node)
        node_type = str((node.get("data") or {}).get("type") or "")
        if not node_type or node_type in {"note"}:
            continue
        nodes.append(node)
    kept = {node["id"] for node in nodes if node.get("id")}
    data["nodes"] = nodes
    data["edges"] = [edge for edge in data.get("edges") or [] if edge.get("source") in kept and edge.get("target") in kept]
    return data


def remove_edges_to_fields(data: dict[str, Any], targets: set[tuple[str, str]]) -> None:
    kept_edges = []
    for edge in data.get("edges") or []:
        target_handle = ((edge.get("data") or {}).get("targetHandle") or {})
        field_name = str(target_handle.get("fieldName") or "")
        if (str(edge.get("target") or ""), field_name) in targets:
            continue
        kept_edges.append(edge)
    data["edges"] = kept_edges


def set_prompt_template(data: dict[str, Any], template: str) -> None:
    prompt_node = find_node(data, "BoI Workflow Prompt")
    node = (prompt_node.get("data") or {}).get("node") or {}
    field = (node.get("template") or {}).get("template")
    if isinstance(field, dict):
        field["value"] = template


def create_component_reference_flow(
    client: httpx.Client,
    langflow_url: str,
    headers: dict[str, str],
    base_flow: dict[str, Any],
    *,
    flow_name: str = "BoI Reference Flow",
    endpoint_name: str = "boi-reference-flow",
    context_input: str = "equipment.alarm.raised.v1 trace input from Event Broker",
    action_key: str = "manual.equipment.confirm_alarm_context",
    wiki_query: str = "equipment abnormal response SOP action",
    prompt_instruction: str = (
        "Write a Korean BoI workflow execution draft. Use linked SOP/action context, "
        "avoid PoC architecture boilerplate, and clearly mark manual handoff and approval needs."
    ),
    description: str = (
        "BoI custom component reference flow: Event context, metadata, policy guard, "
        "wiki writer, action invoker, and Gemma LLM smoke path."
    ),
) -> dict[str, Any]:
    components = get_components(client, langflow_url, headers)
    data = compact_base_flow(base_flow)
    data.setdefault("nodes", [])
    data.setdefault("edges", [])

    for node in data["nodes"]:
        node.setdefault("position", {})
        node["position"]["y"] = node["position"].get("y", 0) - 520
        if "positionAbsolute" in node:
            node["positionAbsolute"]["y"] = node["positionAbsolute"].get("y", 0) - 520

    chat_input = find_node(data, "BoI Event Input")
    llm = find_node(data, "Gemma OpenAI-Compatible LLM")
    chat_output = find_node(data, "BoI Draft Output")
    set_prompt_template(
        data,
        (
            "You are a concise Korean enterprise workflow analyst. Use the BoI Wiki context and SOP/action evidence. "
            "Write only trace-specific execution content. Do not include YAML frontmatter, do not wrap the full answer "
            "in a code fence, and do not explain PoC architecture, Event Broker, Action Gateway, or promotion policy "
            "unless they are directly present as evidence in an action result."
        ),
    )
    remove_edges_to_fields(
        data,
        {
            (llm["id"], "input_value"),
            (chat_output["id"], "input_value"),
        },
    )

    nodes_by_name = {
        "harness": create_custom_node(components, BOI_COMPONENT_KEYS["harness"], "BoIHarnessLoader-boi", 120, 440),
        "reader": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["reader"],
            "BoIWikiReader-boi",
            520,
            440,
            {"query": wiki_query, "employee_id": "100001", "boi_api_url": "http://boi-api:8000"},
        ),
        "context": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["context"],
            "BoIContextNormalizer-boi",
            120,
            760,
            {"manual_input": context_input},
        ),
        "prompt": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["prompt"],
            "BoIPromptComposer-boi",
            920,
            440,
            {"instruction": prompt_instruction},
        ),
        "metadata": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["metadata"],
            "BoIMetadataBuilder-boi",
            520,
            760,
            {
                "title": "Langflow SOP 실행 결과 BoI",
                "boi_description": "Generated by BoI custom component reference flow",
                "visibility": "private",
                "owner": "100001",
            },
        ),
        "policy": create_custom_node(components, BOI_COMPONENT_KEYS["policy"], "BoIPolicyGuard-boi", 920, 760),
        "writer": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["writer"],
            "BoIWikiWriter-boi",
            1320,
            760,
            {"boi_api_url": "http://boi-api:8000", "employee_id": "100001"},
        ),
        "action": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["action"],
            "BoIActionInvoker-boi",
            1720,
            760,
            {
                "action_key": action_key,
                "dry_run": True,
                "action_gateway_url": "http://action-gateway:8100",
                "service_token": "dev-service-token-change-me",
            },
        ),
        "result": create_custom_node(
            components,
            BOI_COMPONENT_KEYS["result"],
            "BoIResultComposer-boi",
            2120,
            760,
        ),
    }
    data["nodes"].extend(nodes_by_name.values())
    data["edges"].extend(
        [
            create_edge(chat_input, nodes_by_name["context"], "message"),
            create_edge(nodes_by_name["harness"], nodes_by_name["prompt"], "harness"),
            create_edge(nodes_by_name["reader"], nodes_by_name["prompt"], "documents"),
            create_edge(nodes_by_name["context"], nodes_by_name["prompt"], "work_context"),
            create_edge(nodes_by_name["prompt"], llm, "input_value"),
            create_edge(nodes_by_name["context"], nodes_by_name["metadata"], "work_context"),
            create_edge(llm, nodes_by_name["policy"], "body_message"),
            create_edge(nodes_by_name["metadata"], nodes_by_name["policy"], "metadata"),
            create_edge(llm, nodes_by_name["writer"], "body_message"),
            create_edge(nodes_by_name["metadata"], nodes_by_name["writer"], "metadata"),
            create_edge(nodes_by_name["policy"], nodes_by_name["action"], "payload"),
            create_edge(nodes_by_name["context"], nodes_by_name["action"], "event"),
            create_edge(llm, nodes_by_name["result"], "analysis"),
            create_edge(nodes_by_name["policy"], nodes_by_name["result"], "validation"),
            create_edge(nodes_by_name["writer"], nodes_by_name["result"], "write_result"),
            create_edge(nodes_by_name["action"], nodes_by_name["result"], "action_result"),
            create_edge(nodes_by_name["result"], chat_output, "input_value"),
        ]
    )
    data["viewport"] = {"x": -220, "y": -120, "zoom": 0.55}

    response = client.post(
        f"{langflow_url}/api/v1/flows/",
        headers=headers,
        json={
            "name": flow_name,
            "description": description,
            "endpoint_name": endpoint_name,
            "data": data,
            "webhook": False,
            "access_type": "PRIVATE",
            "tags": ["boi", "sop", "custom-components", "gemma"],
        },
    )
    response.raise_for_status()
    return response.json()


def smoke_run(client: httpx.Client, langflow_url: str, headers: dict[str, str], endpoint_name: str) -> dict[str, Any]:
    url = f"{langflow_url}/api/v1/run/{endpoint_name}"
    request_headers = {**headers, "Content-Type": "application/json"}
    payload = {
        "input_value": "BoI Wiki PoC Langflow smoke test. Respond with one short Korean sentence.",
        "input_type": "chat",
        "output_type": "chat",
    }
    response = client.post(url, headers=request_headers, json=payload)
    response.raise_for_status()
    return response.json()


def first_message(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("text", "message"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return item
            found = first_message(item)
            if found:
                return found
        for item in value.values():
            found = first_message(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = first_message(item)
            if found:
                return found
    return ""


def summarize_run(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    message = first_message(value)
    return {
        "session_id": value.get("session_id"),
        "message_excerpt": message[:800],
        "contains_boi_write_result": "BoI Write Result" in message,
        "contains_manual_required": "manual_required" in message,
    }


def resolve_smoke_target(upload_result: Any, fallback_endpoint_name: str) -> str:
    uploaded_flow = upload_result[0] if isinstance(upload_result, list) and upload_result else upload_result
    if isinstance(uploaded_flow, dict):
        return uploaded_flow.get("id") or uploaded_flow.get("endpoint_name") or fallback_endpoint_name
    return fallback_endpoint_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and smoke-test BoI reference Langflow flows.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--langflow-url", default=env("LANGFLOW_URL", "http://localhost:7860"))
    parser.add_argument("--langflow-api-key", default=os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me"))
    parser.add_argument("--auth-mode", choices=["auto-login", "api-key"], default=os.getenv("LANGFLOW_AUTH_MODE", "auto-login"))
    parser.add_argument("--skip-custom-components", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(Path(args.manifest))
    flow_file = Path(manifest["_flow_file_path"])
    langflow_url = args.langflow_url.rstrip("/")
    endpoint_name = manifest.get("endpoint_name") or DEFAULT_ENDPOINT_NAME

    with httpx.Client(timeout=60) as client:
        headers = get_auth_headers(client, langflow_url, args.langflow_api_key, args.auth_mode)
        base_flow = json.loads(flow_file.read_text(encoding="utf-8"))
        deleted = delete_flows_by_name(
            client,
            langflow_url,
            headers,
            {"BoI Reference Flow", "BoI Equipment Stage Analysis Flow", "BoI Universal Action Simulator Flow"},
        )
        smoke_target = endpoint_name
        custom_flow = None
        stage_flow = None
        simulator_flow = None
        if not args.skip_custom_components:
            custom_flow = create_component_reference_flow(
                client,
                langflow_url,
                headers,
                base_flow,
                endpoint_name=endpoint_name,
                wiki_query="BoI Wiki SOP harness action Langflow",
            )
            stage_flow = create_component_reference_flow(
                client,
                langflow_url,
                headers,
                base_flow,
                flow_name="BoI Equipment Stage Analysis Flow",
                endpoint_name="boi-equipment-stage-analysis",
                context_input=(
                    "root_cause.analysis.requested.v1 trace input. Include prior action results, "
                    "SOP stage, manual handoff requirements, and generated BoI enrichment output."
                ),
                action_key="manual.equipment.review_root_cause",
                wiki_query="equipment abnormal response SOP root cause maintenance guide",
                prompt_instruction=(
                    "Write only a stage-specific Korean analysis draft for the equipment SOP. "
                    "Use Event, SOP stage, prior action results, BoI Wiki context, and manual approval requirements. "
                    "Do not explain Event Broker, Action Gateway, promotion policy, or PoC architecture."
                ),
                description=(
                    "BoI Wiki Writer stage-analysis flow for equipment SOP: context normalizer, "
                    "harness/wiki reader, Gemma LLM, metadata/policy guard, writer, and action invoker."
                ),
            )
            simulator_flow = create_component_reference_flow(
                client,
                langflow_url,
                headers,
                base_flow,
                flow_name="BoI Universal Action Simulator Flow",
                endpoint_name="boi-universal-action-simulator",
                context_input=(
                    "Universal simulation input. Read event payload, SOP stage, action_key, source_refs, "
                    "expected result contract, prior action results, and simulation reason."
                ),
                action_key="manual.direct_development.decide_cross_section",
                wiki_query="direct development reporting SOP universal simulator action contract",
                prompt_instruction=(
                    "You are the official BoI Universal Action Simulator. Generate a Korean PoC simulation result "
                    "for the requested action. Make it unmistakable that this is SIMULATED and not a real system call. "
                    "Use BoI Wiki context, SOP stage, prior action results, source_refs, and the expected result contract. "
                    "Return concise sections plus a JSON block with: status=simulated, simulation=true, simulated_system, "
                    "simulated_action_key, input_evidence_refs, generated_result, confidence, limitations, "
                    "recommended_next_event, human_review_required."
                ),
                description=(
                    "Official BoI universal simulator flow: reads BoI context and generates marked SIMULATED "
                    "action results for unavailable systems or human-step simulations."
                ),
            )
            smoke_target = custom_flow.get("id") or custom_flow.get("endpoint_name") or smoke_target
        else:
            upload_result = upload_flow(client, langflow_url, headers, flow_file)
            smoke_target = resolve_smoke_target(upload_result, endpoint_name)
        result: dict[str, Any] = {
            "ok": True,
            "langflow_url": langflow_url,
            "endpoint_name": endpoint_name,
            "smoke_target": smoke_target,
            "flow_file": str(flow_file),
            "auth_mode": args.auth_mode,
            "deleted_flow_ids": deleted,
            "custom_component_flow": {
                "id": custom_flow.get("id"),
                "name": custom_flow.get("name"),
                "endpoint_name": custom_flow.get("endpoint_name"),
                "nodes": len((custom_flow.get("data") or {}).get("nodes") or []),
                "edges": len((custom_flow.get("data") or {}).get("edges") or []),
            }
            if custom_flow
            else None,
            "equipment_stage_flow": {
                "id": stage_flow.get("id"),
                "name": stage_flow.get("name"),
                "endpoint_name": stage_flow.get("endpoint_name"),
                "nodes": len((stage_flow.get("data") or {}).get("nodes") or []),
                "edges": len((stage_flow.get("data") or {}).get("edges") or []),
            }
            if stage_flow
            else None,
            "universal_simulator_flow": {
                "id": simulator_flow.get("id"),
                "name": simulator_flow.get("name"),
                "endpoint_name": simulator_flow.get("endpoint_name"),
                "nodes": len((simulator_flow.get("data") or {}).get("nodes") or []),
                "edges": len((simulator_flow.get("data") or {}).get("edges") or []),
            }
            if simulator_flow
            else None,
        }
        if not args.skip_smoke:
            result["smoke"] = smoke_run(client, langflow_url, headers, smoke_target)
            if stage_flow:
                result["stage_smoke"] = smoke_run(
                    client,
                    langflow_url,
                    headers,
                    stage_flow.get("id") or stage_flow.get("endpoint_name") or "boi-equipment-stage-analysis",
                )
            if simulator_flow:
                result["simulator_smoke"] = smoke_run(
                    client,
                    langflow_url,
                    headers,
                    simulator_flow.get("id") or simulator_flow.get("endpoint_name") or "boi-universal-action-simulator",
                )
        if args.summary:
            result = {
                "ok": result["ok"],
                "langflow_url": result["langflow_url"],
                "deleted_flow_ids": result["deleted_flow_ids"],
                "custom_component_flow": result["custom_component_flow"],
                "equipment_stage_flow": result["equipment_stage_flow"],
                "universal_simulator_flow": result["universal_simulator_flow"],
                "smoke": summarize_run(result.get("smoke")),
                "stage_smoke": summarize_run(result.get("stage_smoke")),
                "simulator_smoke": summarize_run(result.get("simulator_smoke")),
            }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
