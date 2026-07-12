from __future__ import annotations

import hashlib
import json
import re
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
COMPONENT_PROP_SCHEMAS: dict[str, dict[str, type]] = {
    "Answer": {"summary": str, "markdown": str},
    "CitationList": {"items": list},
    "EvidencePicker": {"items": list},
    "WorkRecordForm": {"fields": list},
    "DecisionSummary": {"summary": str, "items": list},
    "TaskStatus": {"title": str, "completion": dict},
    "RelatedQuestions": {"items": list},
    "DataTable": {"artifact_id": str},
    "Timeline": {"artifact_id": str},
    "MermaidArtifact": {"artifact_id": str},
    "OntologyExplorer": {"artifact_id": str},
    "ActionPreview": {"artifact_id": str},
    "Confirmation": {"title": str, "message": str, "plan_ref": str},
}

_UNSAFE_HTML = re.compile(r"<(?:script|iframe|object|embed)\b|\son[a-z]+\s*=", re.IGNORECASE)


def _validate_props(value: Any, *, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            _validate_props(child_value, key=str(child_key))
        return
    if isinstance(value, list):
        for child in value:
            _validate_props(child, key=key)
        return
    if not isinstance(value, str):
        return
    if key in {"displayHtml", "html"} and _UNSAFE_HTML.search(value):
        raise ValueError("unsafe_a2ui_html")
    if key.lower() in {"url", "href", "downloadurl"} and value and not value.startswith(("/", "#")):
        raise ValueError("external_a2ui_url")


def validate_surface(surface: dict[str, Any]) -> dict[str, Any]:
    if surface.get("protocol_version") != A2UI_PROTOCOL_VERSION or surface.get("catalog_id") != BOI_CATALOG_ID:
        raise ValueError("unsupported_a2ui_contract")
    events = surface.get("events") or []
    if events:
        raise ValueError("unsupported_a2ui_event")
    components = surface.get("components") or []
    component_ids: set[str] = set()
    for item in components:
        if not isinstance(item, dict) or item.get("component") not in ALLOWED_COMPONENTS:
            raise ValueError("unsupported_a2ui_component")
        component_id = str(item.get("id") or "")
        if not component_id or component_id in component_ids:
            raise ValueError("invalid_a2ui_component_id")
        component_ids.add(component_id)
        props = item.get("props") or {}
        schema = COMPONENT_PROP_SCHEMAS.get(str(item.get("component") or ""), {})
        for prop_name, expected_type in schema.items():
            if prop_name not in props or not isinstance(props[prop_name], expected_type):
                raise ValueError("invalid_a2ui_component_props")
        _validate_props(props)
    return surface


def presentation_plan(response: AgentTurnResponse) -> dict[str, Any]:
    components = ["Answer"]
    if response.citations:
        components.append("CitationList")
    for artifact in response.artifact_refs[:3]:
        if artifact.artifact_type == "mermaid_diagram":
            components.append("MermaidArtifact")
        elif artifact.artifact_type in {"ontology_graph", "knowledge_graph"}:
            presentation = str((artifact.metadata or {}).get("presentation") or "explorer")
            components.append({"table": "DataTable", "timeline": "Timeline", "mermaid": "MermaidArtifact"}.get(presentation, "OntologyExplorer"))
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
            "action_plan": "ActionPreview",
            "action_preview": "ActionPreview",
        }.get(artifact.artifact_type)
        if artifact.artifact_type in {"ontology_graph", "knowledge_graph"}:
            presentation = str((artifact.metadata or {}).get("presentation") or "explorer")
            component = {"table": "DataTable", "timeline": "Timeline", "mermaid": "MermaidArtifact"}.get(presentation, "OntologyExplorer")
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
    surface = {
        "surface_id": surface_id,
        "protocol_version": A2UI_PROTOCOL_VERSION,
        "catalog_id": BOI_CATALOG_ID,
        "components": components,
        "events": [],
        "fallback": response.model_dump(mode="json", exclude={"presentation_plan", "a2ui_surface_ref"}),
    }
    validate_surface(surface)
    surface["jsonl"] = "\n".join(
        json.dumps(item, ensure_ascii=False)
        for item in [
            {"createSurface": {"surfaceId": surface_id, "catalogId": BOI_CATALOG_ID}},
            {"updateComponents": {"surfaceId": surface_id, "components": components}},
        ]
    )
    return surface


def compile_harness_review_surface(
    candidate: dict[str, Any],
    *,
    failure_patterns: list[dict[str, Any]],
    shadow_run: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile an inspectable, non-mutating review surface for a Harness candidate."""
    candidate_id = str(candidate.get("candidate_id") or "")
    pattern_items = [
        {
            "label": str(item.get("summary") or "반복 실패"),
            "value": f"{int(item.get('occurrence_count') or 0)}회",
            "status": str(item.get("status") or "open"),
        }
        for item in failure_patterns[:10]
    ]
    changes = candidate.get("changes") if isinstance(candidate.get("changes"), dict) else {}
    trial_items = [
        {"label": "서버 사전 점검", "value": str((shadow_run or {}).get("status") or "아직 실행하지 않음")},
        {"label": "회귀·안전 평가", "value": "통과" if (evaluation or {}).get("qualified") else "미통과 또는 대기"},
        {"label": "운영 반영", "value": "반영되지 않음"},
    ]
    components = [
        {
            "id": "candidate-summary",
            "component": "Answer",
            "props": {
                "summary": "업무 실행 품질 개선 후보",
                "markdown": str(candidate.get("rationale") or "반복 실패를 줄이기 위한 제한된 개선 후보입니다."),
            },
        },
        {
            "id": "failure-patterns",
            "component": "DecisionSummary",
            "props": {"summary": "반복해서 막힌 이유", "items": pattern_items},
        },
        {
            "id": "bounded-change",
            "component": "DecisionSummary",
            "props": {
                "summary": "다음 실행에서 시험할 변경",
                "items": [{"label": key, "value": value} for key, value in sorted(changes.items())],
            },
        },
        {
            "id": "trial-result",
            "component": "DecisionSummary",
            "props": {"summary": "시험과 운영 경계", "items": trial_items},
        },
    ]
    surface_id = "surface-harness-" + hashlib.sha256(
        f"{candidate_id}:{candidate.get('updated_at') or candidate.get('created_at')}".encode("utf-8")
    ).hexdigest()[:20]
    surface = {
        "surface_id": surface_id,
        "protocol_version": A2UI_PROTOCOL_VERSION,
        "catalog_id": BOI_CATALOG_ID,
        "components": components,
        "events": [],
        "fallback": {
            "candidate_id": candidate_id,
            "status": candidate.get("status"),
            "production_changed": False,
        },
    }
    validate_surface(surface)
    surface["jsonl"] = "\n".join(
        json.dumps(item, ensure_ascii=False)
        for item in [
            {"createSurface": {"surfaceId": surface_id, "catalogId": BOI_CATALOG_ID}},
            {"updateComponents": {"surfaceId": surface_id, "components": components}},
        ]
    )
    return surface
