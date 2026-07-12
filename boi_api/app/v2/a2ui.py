from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import AgentTurnResponse


A2UI_PROTOCOL_VERSION = "0.9.1"
BOI_CATALOG_ID = "boi-a2ui/v1"
ALLOWED_COMPONENTS = {
    "Answer",
    "CitationList",
    "EvidencePicker",
    "WorkRecordForm",
    "DecisionSummary",
    "TaskStatus",
    "Timeline",
    "DataTable",
    "MermaidArtifact",
    "OntologyExplorer",
    "ActionPreview",
    "Confirmation",
    "RelatedQuestions",
}


def presentation_plan(response: AgentTurnResponse) -> dict[str, Any]:
    components = ["Answer"]
    if response.citations:
        components.append("CitationList")
    for artifact in response.artifact_refs[:3]:
        if artifact.artifact_type == "mermaid_diagram":
            components.append("MermaidArtifact")
        elif artifact.artifact_type in {"ontology_graph", "knowledge_graph"}:
            components.append("OntologyExplorer")
        elif artifact.artifact_type in {"action_plan", "action_preview"}:
            components.append("ActionPreview")
    if response.related_questions:
        components.append("RelatedQuestions")
    components = list(dict.fromkeys(item for item in components if item in ALLOWED_COMPONENTS))
    return {
        "catalog_id": BOI_CATALOG_ID,
        "protocol_version": A2UI_PROTOCOL_VERSION,
        "components": components,
        "fallback": "agent_turn_response",
    }


def compile_surface(response: AgentTurnResponse) -> dict[str, Any]:
    plan = presentation_plan(response)
    surface_id = "surface-" + hashlib.sha256(
        f"{response.run_id}:{response.turn_id}:{','.join(plan['components'])}".encode("utf-8")
    ).hexdigest()[:20]
    components: list[dict[str, Any]] = [
        {
            "id": "answer",
            "component": "Answer",
            "props": {
                "summary": response.answer.summary,
                "displayHtml": response.answer.display_html,
                "markdown": response.answer.markdown,
                "groundingStatus": response.grounding_status,
            },
        }
    ]
    if response.citations:
        components.append(
            {
                "id": "citations",
                "component": "CitationList",
                "props": {"items": [item.model_dump(mode="json") for item in response.citations]},
            }
        )
    for index, artifact in enumerate(response.artifact_refs[:3]):
        component = {
            "mermaid_diagram": "MermaidArtifact",
            "ontology_graph": "OntologyExplorer",
            "knowledge_graph": "OntologyExplorer",
            "action_plan": "ActionPreview",
            "action_preview": "ActionPreview",
        }.get(artifact.artifact_type)
        if component:
            components.append(
                {
                    "id": f"artifact-{index + 1}",
                    "component": component,
                    "props": artifact.model_dump(mode="json"),
                }
            )
    if response.related_questions:
        components.append(
            {
                "id": "related-questions",
                "component": "RelatedQuestions",
                "props": {"items": [item.model_dump(mode="json") for item in response.related_questions]},
            }
        )
    invalid = [item for item in components if item.get("component") not in ALLOWED_COMPONENTS]
    if invalid:
        raise ValueError("unsupported_a2ui_component")
    surface = {
        "surface_id": surface_id,
        "protocol_version": A2UI_PROTOCOL_VERSION,
        "catalog_id": BOI_CATALOG_ID,
        "components": components,
        "events": [],
        "fallback": response.model_dump(mode="json", exclude={"presentation_plan", "a2ui_surface_ref"}),
    }
    surface["jsonl"] = "\n".join(
        json.dumps(item, ensure_ascii=False)
        for item in [
            {"createSurface": {"surfaceId": surface_id, "catalogId": BOI_CATALOG_ID}},
            {"updateComponents": {"surfaceId": surface_id, "components": components}},
        ]
    )
    return surface
