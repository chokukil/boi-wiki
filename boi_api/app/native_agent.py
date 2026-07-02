from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

try:  # LangGraph is installed in the runtime image; tests can still run without it.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback is exercised when dependency is absent.
    END = "__end__"
    START = "__start__"
    StateGraph = None

LANGGRAPH_AVAILABLE = StateGraph is not None


class NativeAgentRuntimeUnavailable(RuntimeError):
    """Raised when the required Native Agent orchestration runtime is unavailable."""


JsonDict = dict[str, Any]

ALLOWED_AGENT_ROUTES = {"fast", "deep", "inbox", "manual_handoff", "approval_required"}
ALLOWED_AGENT_INTENTS = {
    "search",
    "page_qa",
    "summarize",
    "diagram",
    "workflow_explain",
    "gap_check",
    "trace_reasoning",
    "inbox",
    "manual_complete",
    "approval",
    "event_publish",
    "action_invoke",
    "workflow_start",
    "event_type_draft",
    "access_denied",
}
DEEP_AGENT_INTENTS = {"diagram", "workflow_explain", "gap_check", "trace_reasoning"}
MUTATION_AGENT_INTENTS = {"manual_complete", "approval", "event_publish", "action_invoke", "workflow_start", "event_type_draft"}


def infer_agent_page_kind(current_url: str, page_context: JsonDict | None = None) -> str:
    context_kind = str((page_context or {}).get("page_kind") or "").strip()
    if context_kind:
        return context_kind
    url = str(current_url or "")
    if "/workflows/" in url and "/status" in url:
        return "workflow_status"
    if "/docs/" in url:
        return "doc"
    if "/events" in url:
        return "events"
    if "/event-types" in url:
        return "event_type"
    if "/actions/raw" in url:
        return "action_raw"
    return "home" if url in {"", "/"} else "unknown"


def normalize_profile_terms(values: Any) -> list[str]:
    if isinstance(values, str):
        return [values]
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item or "").strip()]


def score_agent_goal_profile(question: str, current_url: str, page_context: JsonDict | None, profile: JsonDict) -> int:
    match = profile.get("match") if isinstance(profile.get("match"), dict) else {}
    text = f"{question} {(page_context or {}).get('title') or ''}".lower()
    url = str(current_url or "").lower()
    page_kind = infer_agent_page_kind(current_url, page_context)
    score = int(profile.get("priority") or 0)
    page_kinds = normalize_profile_terms(match.get("page_kinds"))
    if page_kinds:
        if page_kind not in page_kinds:
            return -1
        score += 4
    url_contains = normalize_profile_terms(match.get("url_contains"))
    if url_contains:
        matched_url_terms = [term for term in url_contains if term.lower() in url]
        if not matched_url_terms:
            return -1
        score += 10 * len(matched_url_terms)
    required_keywords = normalize_profile_terms(match.get("required_keywords"))
    if required_keywords and not all(term.lower() in text for term in required_keywords):
        return -1
    score += 15 * len(required_keywords)
    keywords = normalize_profile_terms(match.get("keywords"))
    matched_keywords = [term for term in keywords if term.lower() in text]
    if keywords and not matched_keywords:
        return -1
    score += 8 * len(matched_keywords)
    any_keyword_groups = match.get("any_keyword_groups") if isinstance(match.get("any_keyword_groups"), list) else []
    for group in any_keyword_groups:
        group_terms = normalize_profile_terms(group)
        if group_terms and not any(term.lower() in text for term in group_terms):
            return -1
        if group_terms:
            score += 12
    negative_keywords = normalize_profile_terms(match.get("negative_keywords"))
    if any(term.lower() in text for term in negative_keywords):
        return -1
    if not page_kinds and not url_contains and not required_keywords and not keywords and not any_keyword_groups:
        score = max(score, 1)
    return score


def select_agent_goal_profile(
    question: str,
    current_url: str,
    page_context: JsonDict | None,
    profiles: list[JsonDict] | None,
) -> JsonDict | None:
    best: tuple[int, int, JsonDict] | None = None
    for index, profile in enumerate(profiles or []):
        if not isinstance(profile, dict) or not profile.get("goal_type"):
            continue
        score = score_agent_goal_profile(question, current_url, page_context, profile)
        if score < 0:
            continue
        candidate = (score, -index, profile)
        if best is None or candidate > best:
            best = candidate
    if not best:
        return None
    selected = dict(best[2])
    selected["_match_score"] = best[0]
    return selected


def route_candidate_from_goal_profile(profile: JsonDict | None) -> JsonDict | None:
    if not profile:
        return None
    intent = normalize_native_intent(str(profile.get("intent") or ""), fallback="page_qa")
    route = normalize_native_route(str(profile.get("route") or route_for_native_intent(intent)))
    response_profile = str(profile.get("response_profile") or intent)
    return {
        "route": route,
        "intent": intent,
        "response_profile": response_profile,
        "goal_model": {
            "goal_type": str(profile.get("goal_type") or intent),
            "intent": intent,
            "response_profile": response_profile,
            "route": route,
            "source": "agent_goal_registry",
            "description": str(profile.get("description") or ""),
            "match_score": int(profile.get("_match_score") or 0),
        },
        "confidence": float(profile.get("confidence") or 0.82),
        "reason": f"agent goal profile: {profile.get('goal_type')}",
        "router_backend": "agent_goal_registry",
    }


def is_strong_agent_goal_profile(profile: JsonDict | None) -> bool:
    if not isinstance(profile, dict):
        return False
    if str(profile.get("goal_type") or "") == "page_question_answer":
        return False
    try:
        score = int(profile.get("_match_score") or 0)
    except (TypeError, ValueError):
        score = 0
    return score >= 20


def semantic_route_should_override_profile(semantic: JsonDict | None, profile: JsonDict | None, question: str) -> bool:
    if not semantic:
        return False
    if not is_strong_agent_goal_profile(profile):
        return True
    goal_type = str((profile or {}).get("goal_type") or "")
    if goal_type != "workflow_relationship_summary":
        return False
    text = semantic_route_text(question)
    lookup_terms = ("뭐", "무엇", "어떤", "목록", "보여", "찾", "링크", "있")
    flow_terms = ("흐름", "관계", "발생하면", "요약", "정리", "표", "플로우")
    return any(term in text for term in lookup_terms) and not any(term in text for term in flow_terms)


RELATED_AFFORDANCE_TERMS: dict[str, tuple[str, ...]] = {
    "related_sop": ("sop", "절차", "표준", "수행 이력", "수행이력"),
    "related_event": ("event", "이벤트", "발생 이력", "발생이력"),
    "related_action": ("action", "액션", "조치", "실행 이력", "실행이력"),
    "related_boi": ("boi", "근거 문서", "참고 문서", "boi 문서"),
}
RELATED_AFFORDANCE_LABELS: dict[str, str] = {
    "related_sop": "관련 SOP",
    "related_event": "관련 Event",
    "related_action": "관련 Action",
    "related_boi": "관련 BoI 문서",
}
RELATED_AFFORDANCE_RELATION_TERMS = (
    "관련",
    "연결",
    "있",
    "뭐",
    "무엇",
    "어떤",
    "목록",
    "보여",
    "찾",
    "링크",
)
DIALOG_CONTINUATION_TERMS = (
    "전체",
    "리스트",
    "목록",
    "더",
    "다른",
    "나머지",
    "이어",
    "계속",
    "보여",
    "알려",
)
CURRENT_PAGE_QA_TERMS = ("보고서", "문서", "본문", "현재 페이지", "현재 화면", "이 페이지", "이 화면", "여기")
CURRENT_PAGE_ANSWER_TERMS = ("뭐", "무엇", "어떤", "왜", "어떻게", "요약", "정리", "설명", "확인")
ARTIFACT_ROUTE_TERMS = ("mermaid", "머메이드", "flowchart", "다이어그램", "도식", "프로세스 플로우", "프로세스플로우", "그려", "그려줘")
RELATED_AFFORDANCE_PAGE_KINDS = {"doc", "workflow_status", "events", "event_type", "action_raw", "actions", "action_history"}
SOP_SCOPE_ALL_TERMS = ("전체", "전부", "모든", "목록", "리스트", "카탈로그")
SOP_SCOPE_CURRENT_TERMS = ("현재", "이 페이지", "이 화면", "보고서", "문서", "연결된", "직접 연결")
SOP_QUERY_STOPWORDS = (
    "sop",
    "전체",
    "전부",
    "모든",
    "목록",
    "리스트",
    "카탈로그",
    "관련",
    "연결",
    "연결된",
    "현재",
    "페이지",
    "화면",
    "보고서",
    "문서",
    "보여",
    "보여줘",
    "알려",
    "알려줘",
    "찾",
    "찾아",
    "찾아줘",
    "있는",
    "있니",
    "뭐",
    "무엇",
)


def dialog_context_from_conversation(
    conversation: Any,
    *,
    current_url: str = "",
    page_context: JsonDict | None = None,
) -> JsonDict:
    if not isinstance(conversation, list):
        return {}
    previous_user_question = ""
    previous_assistant_summary = ""
    previous_related_target = ""
    previous_related_scope = ""
    previous_links: list[JsonDict] = []
    for turn in reversed(conversation[-8:]):
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").lower()
        if role == "user" and not previous_user_question:
            previous_user_question = str(turn.get("content") or turn.get("text") or "").strip()[:300]
        if role != "assistant":
            continue
        if not previous_assistant_summary:
            previous_assistant_summary = str(turn.get("content") or turn.get("text") or "").strip()[:500]
        related_context = turn.get("related_item_context") if isinstance(turn.get("related_item_context"), dict) else {}
        semantic_context = turn.get("semantic_route") if isinstance(turn.get("semantic_route"), dict) else {}
        target = str(related_context.get("target_kind") or semantic_context.get("target_kind") or "").strip()
        scope = str(related_context.get("scope") or semantic_context.get("scope") or "").strip()
        if not target and str(turn.get("response_profile") or "") == "related_items":
            links = turn.get("links") if isinstance(turn.get("links"), list) else []
            link_kinds = {str(item.get("kind") or "") for item in links if isinstance(item, dict)}
            if "sop" in link_kinds or "related_sop" in link_kinds:
                target = "related_sop"
            elif "event" in link_kinds or "event_type" in link_kinds or "related_event" in link_kinds:
                target = "related_event"
            elif "action" in link_kinds or "related_action" in link_kinds:
                target = "related_action"
            elif "boi" in link_kinds or "related_boi" in link_kinds:
                target = "related_boi"
        if target.startswith("related_") and not previous_related_target:
            previous_related_target = target
            previous_related_scope = scope
            previous_links = [item for item in (turn.get("links") if isinstance(turn.get("links"), list) else []) if isinstance(item, dict)][:8]
    if not previous_user_question and not previous_related_target:
        return {}
    return {
        "previous_user_question": previous_user_question,
        "previous_assistant_summary": previous_assistant_summary,
        "previous_related_target": previous_related_target,
        "previous_related_scope": previous_related_scope,
        "previous_links": previous_links,
        "current_page_fingerprint": str((page_context or {}).get("boi_id") or current_url or ""),
    }


def sop_catalog_query_from_question(question: str) -> str:
    text = re.sub(r"[?？!！,.，。]+", " ", str(question or "").strip(), flags=re.UNICODE)
    tokens = [token for token in re.split(r"\s+", text) if token]
    kept: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in SOP_QUERY_STOPWORDS:
            continue
        reduced = lowered
        for suffix in ("를", "을", "이", "가", "은", "는", "와", "과", "의", "으로", "로", "에", "에서"):
            if len(reduced) > len(suffix) + 1 and reduced.endswith(suffix):
                reduced = reduced[: -len(suffix)]
                break
        if reduced and reduced not in SOP_QUERY_STOPWORDS:
            kept.append(reduced)
    return " ".join(kept).strip()


def sop_scope_from_question(question: str, dialog_context: JsonDict | None = None) -> JsonDict:
    text = semantic_route_text(question)
    previous_scope = str((dialog_context or {}).get("previous_related_scope") or "")
    continuation_terms = [term for term in DIALOG_CONTINUATION_TERMS if term.lower() in text]
    if previous_scope in {"catalog_all", "catalog_search", "current_page_related"} and continuation_terms:
        return {"scope": previous_scope, "query": sop_catalog_query_from_question(question)}
    query = sop_catalog_query_from_question(question)
    current_terms = [term for term in SOP_SCOPE_CURRENT_TERMS if term.lower() in text]
    if current_terms:
        return {"scope": "current_page_related", "query": query}
    all_terms = [term for term in SOP_SCOPE_ALL_TERMS if term.lower() in text]
    if all_terms and not query:
        return {"scope": "catalog_all", "query": ""}
    if query:
        return {"scope": "catalog_search", "query": query}
    return {"scope": "current_page_related", "query": ""}


def semantic_route_candidate(
    question: str,
    current_url: str = "",
    page_context: JsonDict | None = None,
    dialog_context: JsonDict | None = None,
) -> JsonDict | None:
    page_kind = infer_agent_page_kind(current_url, page_context or {})
    text = semantic_route_text(question)
    if page_kind not in RELATED_AFFORDANCE_PAGE_KINDS:
        return None
    if any(term.lower() in text for term in ARTIFACT_ROUTE_TERMS):
        return None
    candidates = semantic_route_candidates(question, current_url, page_context, dialog_context)
    if not candidates:
        return None
    best = candidates[0]
    if not str(best.get("target_kind") or "").startswith("related_"):
        return None
    score = float(best.get("score") or 0.0)
    if score < 0.56:
        return None
    target_kind = str(best.get("target_kind") or "")
    sop_scope = best.get("scope") if target_kind == "related_sop" else ""
    sop_query = best.get("query") if target_kind == "related_sop" else ""
    return {
        "route": "fast",
        "intent": "search",
        "response_profile": "related_items",
        "confidence": round(min(0.95, max(0.55, score)), 2),
        "router_backend": "semantic_hybrid_router",
        "reason": f"semantic affordance route: {target_kind}",
        "requires_mutation": False,
        "requires_deep_reasoning": False,
        "requires_langflow": False,
        "llm_reranker_used": False,
        "semantic_route": {
            "target_kind": target_kind,
            "confidence": round(min(0.95, max(0.55, score)), 2),
            "matched_affordance": target_kind,
            "scope": sop_scope,
            "query": sop_query,
            "continuation_of": str(best.get("continuation_of") or ""),
            "resolved_from_turn": str(best.get("resolved_from_turn") or ""),
        },
        "matched_affordance": target_kind,
        "route_candidates": candidates[:5],
    }


def semantic_route_candidates(
    question: str,
    current_url: str = "",
    page_context: JsonDict | None = None,
    dialog_context: JsonDict | None = None,
) -> list[JsonDict]:
    text = semantic_route_text(question)
    page_kind = infer_agent_page_kind(current_url, page_context or {})
    candidates: list[JsonDict] = []
    relation_score = 0.18 if any(term.lower() in text for term in RELATED_AFFORDANCE_RELATION_TERMS) else 0.0
    for target_kind, terms in RELATED_AFFORDANCE_TERMS.items():
        matched_terms = [term for term in terms if term.lower() in text]
        if not matched_terms:
            continue
        score = 0.45 + relation_score + min(0.26, 0.08 * len(matched_terms))
        if page_kind in {"doc", "workflow_status", "events", "event_type", "action_raw"}:
            score += 0.06
        candidate = {
                "target_kind": target_kind,
                "score": round(min(score, 0.95), 2),
                "reason": f"{RELATED_AFFORDANCE_LABELS.get(target_kind, target_kind)} affordance matched",
                "matched_terms": matched_terms[:5],
            }
        if target_kind == "related_sop":
            candidate.update(sop_scope_from_question(question, dialog_context))
        candidates.append(candidate)
    has_related_candidate = any(str(item.get("target_kind") or "").startswith("related_") for item in candidates)
    previous_target = str((dialog_context or {}).get("previous_related_target") or "")
    continuation_terms = [term for term in DIALOG_CONTINUATION_TERMS if term.lower() in text]
    if previous_target.startswith("related_") and continuation_terms and not has_related_candidate:
        candidate = {
                "target_kind": previous_target,
                "score": 0.74,
                "reason": "continued previous related-item request",
                "matched_terms": continuation_terms[:5],
                "continuation_of": previous_target,
                "resolved_from_turn": "previous_assistant",
            }
        if previous_target == "related_sop":
            candidate.update(sop_scope_from_question(question, dialog_context))
        candidates.append(candidate)
    page_terms = [term for term in CURRENT_PAGE_QA_TERMS if term.lower() in text]
    answer_terms = [term for term in CURRENT_PAGE_ANSWER_TERMS if term.lower() in text]
    if page_terms and answer_terms:
        candidates.append(
            {
                "target_kind": "current_page_answer",
                "score": round(0.5 + min(0.25, 0.05 * (len(page_terms) + len(answer_terms))), 2),
                "reason": "current page question terms matched",
                "matched_terms": (page_terms + answer_terms)[:5],
            }
        )
    candidates.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return candidates


def semantic_route_text(question: str) -> str:
    return re.sub(r"\s+", " ", str(question or "").strip().lower())


def normalize_native_route(value: str, fallback: str = "fast") -> str:
    route = str(value or "").strip().lower().replace("-", "_")
    return route if route in ALLOWED_AGENT_ROUTES else fallback


def normalize_native_intent(value: str, *, fallback: str = "search") -> str:
    intent = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "lookup": "search",
        "page_summary": "summarize",
        "summary": "summarize",
        "workflow_reasoning": "trace_reasoning",
        "reasoning": "trace_reasoning",
        "manual_handoff": "manual_complete",
        "approval_required": "approval",
        "publish_event": "event_publish",
        "event": "event_publish",
        "invoke_action": "action_invoke",
        "action": "action_invoke",
        "start_workflow": "workflow_start",
    }
    intent = aliases.get(intent, intent)
    return intent if intent in ALLOWED_AGENT_INTENTS else fallback


def safety_route_override(question: str) -> str | None:
    q = str(question or "").lower()
    manual_action_terms = ("handoff 완료", "핸드오프 완료", "조치 완료", "완료 처리", "조치내용", "조치 내용", "완료 기록", "완료로 기록")
    approval_terms = ("승인", "approve", "실행해", "실행해줘", "invoke", "publish", "게시", "배포", "반영", "적용", "source_apply", "doc_body_apply")
    if any(term in q for term in manual_action_terms):
        return "manual_handoff"
    if any(term in q for term in approval_terms):
        return "approval_required"
    return None


def deterministic_native_intent(
    question: str,
    current_url: str = "",
    page_context: JsonDict | None = None,
    dialog_context: JsonDict | None = None,
) -> str:
    q = str(question or "").lower()
    if looks_like_unregistered_event_workflow_request(question):
        return "event_type_draft"
    if (
        any(term in q for term in ("event type", "event-type", "이벤트 타입", "이벤트 유형", "이벤트 정의", "신규 이벤트"))
        and any(term in q for term in ("초안", "만들", "생성", "정의", "추가", "draft", "create"))
    ):
        return "event_type_draft"
    if event_type_from_text(question) and any(term in q for term in ("이벤트 발행", "event 발행", "publish event", "이벤트를 발행", "이벤트 발생", "발행해", "발행해줘")):
        return "event_publish"
    if any(term in q for term in ("workflow 시작", "workflow 실행", "워크플로우 시작", "워크플로우 실행", "workflow start", "start workflow")):
        return "workflow_start"
    if action_key_from_text(question) and any(term in q for term in ("action 실행", "액션 실행", "action 요청", "액션 요청", "invoke", "호출", "실행해", "실행해줘")):
        return "action_invoke"
    if safety := safety_route_override(q):
        return "manual_complete" if safety == "manual_handoff" else "approval"
    if semantic_route_candidate(question, current_url, page_context, dialog_context):
        return "search"
    return "page_qa" if current_url else "search"


def route_for_native_intent(intent: str) -> str:
    if intent in DEEP_AGENT_INTENTS:
        return "deep"
    if intent == "inbox":
        return "inbox"
    if intent == "manual_complete":
        return "manual_handoff"
    if intent == "approval":
        return "approval_required"
    if intent in {"event_publish", "action_invoke", "workflow_start"}:
        return "approval_required"
    if intent == "event_type_draft":
        return "approval_required"
    return "fast"


def native_rule_route(request: JsonDict, reason: str = "native_rules") -> JsonDict:
    deterministic = deterministic_native_intent(
        str(request.get("question") or ""),
        str(request.get("current_url") or ""),
        request.get("page_context") if isinstance(request.get("page_context"), dict) else {},
        request.get("dialog_context") if isinstance(request.get("dialog_context"), dict) else {},
    )
    requested_intent = normalize_native_intent(str(request.get("intent") or ""), fallback=deterministic) if request.get("intent") else deterministic
    requested_mode = str(request.get("mode") or "auto")
    route = route_for_native_intent(requested_intent)
    if requested_mode == "fast" and route not in {"manual_handoff", "approval_required"}:
        route = "fast"
    elif requested_mode == "deep":
        route = "deep"
    return finalize_native_route(request, {"route": route, "intent": requested_intent, "reason": reason, "router_backend": "native_rules"})


def finalize_native_route(request: JsonDict, candidate: JsonDict | None) -> JsonDict:
    question = str(request.get("question") or "")
    current_url = str(request.get("current_url") or "")
    deterministic = deterministic_native_intent(
        question,
        current_url,
        request.get("page_context") if isinstance(request.get("page_context"), dict) else {},
        request.get("dialog_context") if isinstance(request.get("dialog_context"), dict) else {},
    )
    route = normalize_native_route(str((candidate or {}).get("route") or ""), fallback=route_for_native_intent(deterministic))
    intent = normalize_native_intent(str((candidate or {}).get("intent") or ""), fallback=deterministic)
    if looks_like_unregistered_event_workflow_request(question) and intent in {"approval", "action_invoke", "event_publish", "workflow_start"}:
        intent = "event_type_draft"
    profile_selected = bool((candidate or {}).get("goal_model") or (candidate or {}).get("response_profile"))
    if not profile_selected and deterministic in DEEP_AGENT_INTENTS and (route != "deep" or intent != deterministic):
        route = "deep"
        intent = deterministic
    if intent in {"event_publish", "action_invoke", "workflow_start", "event_type_draft"}:
        route = "approval_required"
    elif override := safety_route_override(question):
        route = override
        intent = "manual_complete" if override == "manual_handoff" else "approval"
    elif intent in MUTATION_AGENT_INTENTS:
        route = route_for_native_intent(intent)
    elif (candidate or {}).get("requires_mutation") and route not in {"manual_handoff", "approval_required"}:
        route = "approval_required"
        intent = "approval"
    confidence = (candidate or {}).get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else (1.0 if (candidate or {}).get("router_backend") == "request_hint" else 0.82)
    except (TypeError, ValueError):
        confidence_value = 0.82
    final_route = {
        "route": route,
        "intent": intent,
        "confidence": confidence_value,
        "reason": str((candidate or {}).get("reason") or "native classification"),
        "requires_mutation": route in {"manual_handoff", "approval_required"},
        "requires_deep_reasoning": route == "deep",
        # Compatibility field for older clients. Deep is native reasoning now, not Langflow.
        "requires_langflow": False,
        "router_backend": str((candidate or {}).get("router_backend") or "native_rules"),
    }
    if isinstance((candidate or {}).get("component_errors"), list):
        final_route["component_errors"] = list((candidate or {}).get("component_errors") or [])
    if (candidate or {}).get("response_profile"):
        final_route["response_profile"] = str((candidate or {}).get("response_profile") or "")
    if isinstance((candidate or {}).get("goal_model"), dict):
        final_route["goal_model"] = dict((candidate or {}).get("goal_model") or {})
    if isinstance((candidate or {}).get("semantic_route"), dict):
        final_route["semantic_route"] = dict((candidate or {}).get("semantic_route") or {})
    if isinstance((candidate or {}).get("route_candidates"), list):
        final_route["route_candidates"] = list((candidate or {}).get("route_candidates") or [])[:5]
    if (candidate or {}).get("llm_reranker_used") is not None:
        final_route["llm_reranker_used"] = bool((candidate or {}).get("llm_reranker_used"))
    if (candidate or {}).get("matched_affordance"):
        final_route["matched_affordance"] = str((candidate or {}).get("matched_affordance") or "")
    return final_route


def agent_artifact(
    artifact_type: str,
    *,
    title: str = "",
    data: Any = None,
    source: str = "",
    role: str = "primary",
    display_mode: str = "inline",
    priority: int = 10,
    reason: str = "",
    user_requested: bool = True,
) -> JsonDict:
    artifact: JsonDict = {
        "type": artifact_type,
        "role": role,
        "display_mode": display_mode,
        "priority": priority,
        "reason": reason or ("요청에 맞춰 바로 확인할 산출물" if role == "primary" else "답변을 뒷받침하는 참고 자료"),
        "user_requested": user_requested,
        "default_collapsed": role in {"evidence", "diagnostic"} or display_mode in {"collapsed", "viewer_only", "hidden_diagnostic"},
    }
    if title:
        artifact["title"] = title
    if data is not None:
        artifact["data"] = data
    if source:
        artifact["source"] = source
    return artifact


@dataclass
class NativeAgentConfig:
    max_tool_loops: int = 5
    tool_timeout_seconds: float = 8.0
    build_revision: str = "unknown"
    llm_enabled: bool = False
    require_langgraph: bool = True
    composer_enabled: bool = False
    composer_required: bool = False
    progress_callback: Callable[[JsonDict], None] | None = None


@dataclass
class NativeAgentTools:
    ontology_search: Callable[[str, str, int], JsonDict]
    boi_get: Callable[[str], JsonDict | None]
    event_type_lookup: Callable[[str], JsonDict | None]
    action_spec_lookup: Callable[[str], JsonDict | None]
    workflow_status: Callable[[str, str], JsonDict | None]
    trace_context_lookup: Callable[[str], JsonDict]
    dictionary_resolve: Callable[[str], JsonDict]
    memory_recall: Callable[[str, int], JsonDict]
    agent_inbox: Callable[[int], JsonDict]
    sop_catalog_search: Callable[[str, str, int], JsonDict] | None = None
    llm_json: Callable[[str, JsonDict], JsonDict | None] | None = None


@dataclass
class ToolTraceItem:
    tool: str
    status: str
    elapsed_ms: int
    summary: str = ""
    args: JsonDict = field(default_factory=dict)
    result: JsonDict | list[Any] | None = None


class NativeBoiAgent:
    """Native BoI Agent runtime.

    The graph is intentionally deterministic around tool execution. The LLM can
    influence planning/composition through JSON, but all tool dispatch and safety
    boundaries are controlled in Python.
    """

    def __init__(self, tools: NativeAgentTools, config: NativeAgentConfig | None = None) -> None:
        self.tools = tools
        self.config = config or NativeAgentConfig()

    def run(self, request: JsonDict, route: JsonDict, context_pack: JsonDict) -> JsonDict:
        state: JsonDict = {
            "run_id": f"boi-agent-run-{uuid.uuid4().hex[:12]}",
            "request": request,
            "route": route,
            "context_pack": context_pack,
            "page_context": context_pack.get("page_context") or {},
            "event_context": context_pack.get("event_context") or {},
            "workflow_definition_context": context_pack.get("workflow_definition_context") or {},
            "search": context_pack.get("ontology_search_seed") or {},
            "tool_trace": [],
            "tool_results": {},
            "artifacts": [],
            "links": [],
            "citations": [],
            "coverage_report": {},
            "answer_markdown": "",
            "status_updates": [],
            "access_summary": context_pack.get("access_summary") or {},
            "guardrails_applied": [],
            "component_errors": route.get("component_errors") if isinstance(route.get("component_errors"), list) else [],
        }
        if StateGraph is not None:
            return self._run_langgraph(state)
        if self.config.require_langgraph:
            raise NativeAgentRuntimeUnavailable("LangGraph runtime is required but unavailable")
        return self._run_sequential(state)

    def _run_sequential(self, state: JsonDict) -> JsonDict:
        for node in (
            self._classify_intent,
            self._resolve_page_context,
            self._access_policy_gate,
            self._retrieve_ontology,
            self._plan_tools,
            self._execute_tools_loop,
            self._evaluate_coverage,
            self._compose_answer,
            self._verify_acl_and_artifacts,
            self._safety_gate,
        ):
            state = node(state)
        return self._response(state)

    def _run_langgraph(self, state: JsonDict) -> JsonDict:
        try:
            graph = StateGraph(dict)
            graph.add_node("classify_intent", self._classify_intent)
            graph.add_node("resolve_page_context", self._resolve_page_context)
            graph.add_node("access_policy_gate", self._access_policy_gate)
            graph.add_node("retrieve_ontology", self._retrieve_ontology)
            graph.add_node("plan_tools", self._plan_tools)
            graph.add_node("execute_tools_loop", self._execute_tools_loop)
            graph.add_node("evaluate_coverage", self._evaluate_coverage)
            graph.add_node("compose_answer", self._compose_answer)
            graph.add_node("verify_acl_and_artifacts", self._verify_acl_and_artifacts)
            graph.add_node("safety_gate", self._safety_gate)
            graph.add_edge(START, "classify_intent")
            graph.add_edge("classify_intent", "resolve_page_context")
            graph.add_edge("resolve_page_context", "access_policy_gate")
            graph.add_edge("access_policy_gate", "retrieve_ontology")
            graph.add_edge("retrieve_ontology", "plan_tools")
            graph.add_edge("plan_tools", "execute_tools_loop")
            graph.add_edge("execute_tools_loop", "evaluate_coverage")
            graph.add_edge("evaluate_coverage", "compose_answer")
            graph.add_edge("compose_answer", "verify_acl_and_artifacts")
            graph.add_edge("verify_acl_and_artifacts", "safety_gate")
            graph.add_edge("safety_gate", END)
            compiled = graph.compile()
            final_state = compiled.invoke(state)
            final_state["langgraph_available"] = True
            return self._response(final_state)
        except Exception as exc:  # pragma: no cover - depends on installed LangGraph version.
            if self.config.require_langgraph:
                raise NativeAgentRuntimeUnavailable(f"LangGraph runtime failed: {exc}") from exc
            state["langgraph_available"] = False
            state["langgraph_error"] = repr(exc)
            return self._run_sequential(state)

    def _classify_intent(self, state: JsonDict) -> JsonDict:
        request = state.get("request") or {}
        route = state.get("route") or {}
        if not route.get("route"):
            route = self._classify_route_inside_graph(request, state)
        else:
            route = finalize_native_route(request, route)
        state["route"] = route
        state["intent"] = str(route.get("intent") or "search")
        state["route_name"] = str(route.get("route") or "fast")
        state["response_profile"] = str(route.get("response_profile") or "")
        if isinstance(route.get("goal_model"), dict):
            state["goal_model"] = dict(route.get("goal_model") or {})
        state["question"] = str(request.get("question") or "")
        return state

    def _classify_route_inside_graph(self, request: JsonDict, state: JsonDict) -> JsonDict:
        profile = select_agent_goal_profile(
            str(request.get("question") or ""),
            str(request.get("current_url") or ""),
            state.get("page_context") if isinstance(state.get("page_context"), dict) else {},
            (state.get("context_pack") or {}).get("agent_goal_profiles") if isinstance(state.get("context_pack"), dict) else [],
        )
        semantic = semantic_route_candidate(
            str(request.get("question") or ""),
            str(request.get("current_url") or ""),
            state.get("page_context") if isinstance(state.get("page_context"), dict) else {},
            request.get("dialog_context")
            if isinstance(request.get("dialog_context"), dict)
            else ((state.get("context_pack") or {}).get("dialog_context") if isinstance(state.get("context_pack"), dict) else {}),
        )
        if semantic_route_should_override_profile(semantic, profile, str(request.get("question") or "")):
            return finalize_native_route(request, semantic)
        if is_strong_agent_goal_profile(profile):
            return finalize_native_route(request, route_candidate_from_goal_profile(profile))
        if profile:
            return finalize_native_route(request, route_candidate_from_goal_profile(profile))
        if self.config.llm_enabled and self.tools.llm_json and str(request.get("mode") or "auto") == "auto":
            payload = {
                "request": request,
                "deterministic_intent": deterministic_native_intent(
                    str(request.get("question") or ""),
                    str(request.get("current_url") or ""),
                    state.get("page_context") if isinstance(state.get("page_context"), dict) else {},
                    request.get("dialog_context")
                    if isinstance(request.get("dialog_context"), dict)
                    else ((state.get("context_pack") or {}).get("dialog_context") if isinstance(state.get("context_pack"), dict) else {}),
                ),
                "allowed_routes": sorted(ALLOWED_AGENT_ROUTES),
                "allowed_intents": sorted(ALLOWED_AGENT_INTENTS),
            }
            routed = self._call_tool(
                "route_classifier",
                {"backend": "llm_first"},
                lambda: self.tools.llm_json("route", payload) if self.tools.llm_json else None,
                state,
            )
            if isinstance(routed, dict) and routed.get("route"):
                return finalize_native_route(request, routed)
            raise NativeAgentRuntimeUnavailable("Native Agent route classifier did not return a route")
        if str(request.get("mode") or "auto") == "auto":
            raise NativeAgentRuntimeUnavailable("Native Agent route classifier is required but not configured")
        return native_rule_route(request)

    def _resolve_page_context(self, state: JsonDict) -> JsonDict:
        page_context = state.get("page_context") or {}
        boi_id = str(page_context.get("boi_id") or page_context.get("sop_ref") or "")
        if boi_id and "current_doc" not in state.get("tool_results", {}):
            doc = self._call_tool("boi_get", {"boi_id": boi_id}, lambda: self.tools.boi_get(boi_id), state)
            if doc:
                state.setdefault("tool_results", {})["current_doc"] = doc
        return state

    def _access_policy_gate(self, state: JsonDict) -> JsonDict:
        state.setdefault("guardrails_applied", []).append("acl_policy")
        access = state.get("access_summary") if isinstance(state.get("access_summary"), dict) else {}
        if access and access.get("can_read") is False:
            state["route_name"] = "approval_required"
            state["intent"] = "access_denied"
            state["answer_markdown"] = "현재 권한으로 이 BoI를 Agent 컨텍스트에 사용할 수 없습니다."
            state["stop_reason"] = "access_denied"
        if access and access.get("can_use_in_agent_context") is False:
            state.setdefault("guardrails_applied", []).append("classification_redaction")
            state["answer_markdown"] = (
                "이 BoI는 보안 등급 정책 때문에 Agent 답변 컨텍스트로 사용할 수 없습니다. "
                "문서 존재와 접근 정책은 확인할 수 있지만, 본문이나 연결 항목을 바탕으로 한 요약·도식·외부 전달은 제한됩니다."
            )
            state["stop_reason"] = "context_restricted"
        return state

    def _retrieve_ontology(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            return state
        search = state.get("search") or {}
        if not search.get("ok"):
            query = state.get("question") or ""
            search = self._call_tool("ontology_search", {"query": query, "scope": "all"}, lambda: self.tools.ontology_search(query, "all", 8), state) or {}
        state["search"] = search
        state.setdefault("tool_results", {})["ontology_search"] = search
        return state

    def _plan_tools(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            state["planned_tools"] = []
            return state
        intent = state.get("intent")
        response_profile = state.get("response_profile") or response_profile_for_state(state)
        page_context = state.get("page_context") or {}
        planned: list[JsonDict] = []
        if intent in {"diagram", "workflow_explain", "gap_check"} or response_profile == "action_requirements" or is_action_requirement_question(str(state.get("question") or "")):
            target_boi_id = str(page_context.get("boi_id") or "")
            if not target_boi_id:
                target_boi_id = best_boi_ref_from_search(state.get("search") or {}, prefer_sop=True)
            if not target_boi_id:
                workflow_definition_context = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
                sop_refs = workflow_definition_context.get("sop_refs") if isinstance(workflow_definition_context.get("sop_refs"), list) else []
                target_boi_id = str((sop_refs or [""])[0] or "")
            if target_boi_id:
                planned.append({"tool": "boi_get", "args": {"boi_id": target_boi_id}})
        if intent == "trace_reasoning" and page_context.get("trace_id"):
            planned.append({"tool": "trace_context_lookup", "args": {"trace_id": page_context["trace_id"]}})
            if page_context.get("workflow_key"):
                planned.append({"tool": "workflow_status", "args": {"workflow_key": page_context["workflow_key"], "trace_id": page_context["trace_id"]}})
        if response_profile == "workflow_manual_summary" and page_context.get("workflow_key") and page_context.get("trace_id"):
            planned.append({"tool": "trace_context_lookup", "args": {"trace_id": page_context["trace_id"]}})
            planned.append({"tool": "workflow_status", "args": {"workflow_key": page_context["workflow_key"], "trace_id": page_context["trace_id"]}})
        if intent == "inbox":
            planned.append({"tool": "agent_inbox", "args": {"limit": 10}})
        if state.get("question"):
            planned.append({"tool": "dictionary_resolve", "args": {"query": state["question"]}})
            planned.append({"tool": "memory_recall", "args": {"query": state["question"], "limit": 5}})
        state["planned_tools"] = planned[: self.config.max_tool_loops]
        return state

    def _execute_tools_loop(self, state: JsonDict) -> JsonDict:
        results = state.setdefault("tool_results", {})
        for item in state.get("planned_tools") or []:
            tool = item.get("tool")
            args = item.get("args") or {}
            if tool == "boi_get":
                boi_id = str(args.get("boi_id") or "")
                result = self._call_tool(tool, args, lambda boi_id=boi_id: self.tools.boi_get(boi_id), state)
                if result:
                    results["current_doc"] = result
            elif tool == "trace_context_lookup":
                trace_id = str(args.get("trace_id") or "")
                results["trace_context"] = self._call_tool(tool, args, lambda trace_id=trace_id: self.tools.trace_context_lookup(trace_id), state)
            elif tool == "workflow_status":
                workflow_key = str(args.get("workflow_key") or "")
                trace_id = str(args.get("trace_id") or "")
                results["workflow_status"] = self._call_tool(tool, args, lambda workflow_key=workflow_key, trace_id=trace_id: self.tools.workflow_status(workflow_key, trace_id), state)
            elif tool == "agent_inbox":
                limit = int(args.get("limit") or 10)
                results["agent_inbox"] = self._call_tool(tool, args, lambda limit=limit: self.tools.agent_inbox(limit), state)
            elif tool == "dictionary_resolve":
                query = str(args.get("query") or "")
                results["dictionary"] = self._call_tool(tool, args, lambda query=query: self.tools.dictionary_resolve(query), state)
            elif tool == "memory_recall":
                query = str(args.get("query") or "")
                limit = int(args.get("limit") or 5)
                results["memory"] = self._call_tool(tool, args, lambda query=query, limit=limit: self.tools.memory_recall(query, limit), state)
        self._expand_action_specs_from_doc(state)
        self._expand_action_specs_from_workflow_definition(state)
        self._expand_action_specs_from_event_context(state)
        return state

    def _expand_action_specs_from_doc(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc")
        metadata = doc.get("metadata") if isinstance(doc, dict) else {}
        workflow = metadata.get("workflow") if isinstance(metadata, dict) else {}
        actions: list[str] = []
        for stage in (workflow or {}).get("stages") or []:
            for key in stage.get("automated_actions") or []:
                if key not in actions:
                    actions.append(str(key))
            for key in stage.get("manual_actions") or []:
                if key not in actions:
                    actions.append(str(key))
        looked_up: list[JsonDict] = []
        for action_key in actions[:12]:
            result = self._call_tool("action_spec_lookup", {"action_key": action_key}, lambda action_key=action_key: self.tools.action_spec_lookup(action_key), state)
            if result:
                looked_up.append(result)
        if looked_up:
            state.setdefault("tool_results", {})["action_specs"] = looked_up

    def _expand_action_specs_from_workflow_definition(self, state: JsonDict) -> None:
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        actions = []
        for key in definition.get("action_refs") or []:
            key = str(key or "")
            if key and key not in actions:
                actions.append(key)
        if not actions:
            return
        existing = (state.get("tool_results") or {}).get("action_specs") or []
        seen = {
            str(((item.get("item") if isinstance(item, dict) else {}) or item or {}).get("action_key") or "")
            for item in existing
            if isinstance(item, dict)
        }
        looked_up = list(existing) if isinstance(existing, list) else []
        for action_key in actions[:12]:
            if action_key in seen:
                continue
            result = self._call_tool("action_spec_lookup", {"action_key": action_key}, lambda action_key=action_key: self.tools.action_spec_lookup(action_key), state)
            if result:
                looked_up.append(result)
                seen.add(action_key)
        if looked_up:
            state.setdefault("tool_results", {})["action_specs"] = looked_up

    def _expand_action_specs_from_event_context(self, state: JsonDict) -> None:
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        actions: list[str] = []
        for source_key in ("recommended_actions", "recommended_manual_actions"):
            for key in event_context.get(source_key) or []:
                key = str(key or "")
                if key and key not in actions:
                    actions.append(key)
        if not actions:
            return
        existing = (state.get("tool_results") or {}).get("action_specs") or []
        seen = {
            str(((item.get("item") if isinstance(item, dict) else {}) or item or {}).get("action_key") or "")
            for item in existing
            if isinstance(item, dict)
        }
        looked_up = list(existing) if isinstance(existing, list) else []
        for action_key in actions[:12]:
            if action_key in seen:
                continue
            result = self._call_tool("action_spec_lookup", {"action_key": action_key}, lambda action_key=action_key: self.tools.action_spec_lookup(action_key), state)
            if result:
                looked_up.append(result)
                seen.add(action_key)
        if looked_up:
            state.setdefault("tool_results", {})["action_specs"] = looked_up

    def _evaluate_coverage(self, state: JsonDict) -> JsonDict:
        intent = state.get("intent")
        response_profile = state.get("response_profile") or response_profile_for_state(state)
        results = state.get("tool_results") or {}
        checks = {
            "page_context": bool((state.get("page_context") or {}).get("resolved")),
            "ontology_search": bool((state.get("search") or {}).get("best_matches")),
            "current_doc": bool(results.get("current_doc")),
            "workflow_definition_context": bool((state.get("workflow_definition_context") or {}).get("workflow_definition_key")),
            "action_specs": bool(results.get("action_specs")),
            "trace_context": bool(results.get("trace_context") or results.get("workflow_status")),
        }
        required = ["ontology_search"]
        if intent in {"diagram", "workflow_explain", "gap_check"}:
            required.append("current_doc" if checks.get("current_doc") or not checks.get("workflow_definition_context") else "workflow_definition_context")
        if intent == "gap_check":
            required.append("action_specs")
        if intent == "trace_reasoning":
            required.append("trace_context")
        if response_profile == "workflow_manual_summary":
            required.append("trace_context")
        covered = [key for key in required if checks.get(key)]
        state["coverage_report"] = {
            "required": required,
            "covered": covered,
            "missing": [key for key in required if key not in covered],
            "coverage_score": round(len(covered) / len(required), 2) if required else 1.0,
        }
        return state

    def _compose_answer(self, state: JsonDict) -> JsonDict:
        if state.get("stop_reason"):
            return state
        intent = state.get("intent")
        response_profile = state.get("response_profile") or response_profile_for_state(state)
        if intent == "diagram":
            self._compose_diagram_answer(state)
        elif intent == "gap_check":
            self._compose_gap_answer(state)
        elif response_profile == "workflow_manual_summary":
            self._compose_workflow_manual_answer(state)
        elif response_profile == "related_items":
            self._compose_related_items_answer(state)
        elif intent == "workflow_explain":
            self._compose_workflow_answer(state)
        elif intent == "trace_reasoning":
            self._compose_trace_answer(state)
        elif intent == "inbox":
            self._compose_inbox_answer(state)
        else:
            self._compose_search_answer(state)
        self._compose_with_llm_if_enabled(state)
        return state

    def _compose_with_llm_if_enabled(self, state: JsonDict) -> None:
        if state.get("stop_reason") or state.get("route_name") in {"manual_handoff", "approval_required"}:
            return
        if state.get("authoritative_answer_contract"):
            state["composer_backend"] = "native_structured"
            state["composer_error"] = ""
            return
        if not self.config.composer_enabled:
            if self.config.composer_required and not str(state.get("answer_markdown") or "").strip():
                raise NativeAgentRuntimeUnavailable("LLM answer composer is required but not configured")
            state["composer_backend"] = "native_structured"
            if self.config.composer_required:
                state["composer_error"] = "composer_not_configured"
                state.setdefault("component_errors", []).append(
                    {
                        "component": "answer_composer",
                        "status": "not_configured",
                        "message": "LLM answer composer is required but not configured; native structured answer was preserved.",
                    }
                )
            return
        if not self.tools.llm_json:
            if self.config.composer_required and not str(state.get("answer_markdown") or "").strip():
                raise NativeAgentRuntimeUnavailable("LLM answer composer is required but not configured")
            state["composer_backend"] = "native_structured"
            state["composer_error"] = "llm_json_not_configured"
            if self.config.composer_required:
                state.setdefault("component_errors", []).append(
                    {
                        "component": "answer_composer",
                        "status": "not_configured",
                        "message": "LLM JSON adapter is unavailable; native structured answer was preserved.",
                    }
                )
            return
        payload = llm_compose_payload(state)
        result = self._call_tool(
            "answer_composer",
            {"intent": state.get("intent"), "route": state.get("route_name")},
            lambda: self.tools.llm_json("compose", payload) if self.tools.llm_json else None,
            state,
        )
        if isinstance(result, dict) and str(result.get("answer_markdown") or "").strip() and not result.get("error"):
            composer_answer = str(result.get("answer_markdown") or "").strip()
            state["answer_markdown"] = merge_composer_answer_with_structured_details(
                str(state.get("intent") or ""),
                composer_answer,
                str(state.get("answer_markdown") or ""),
            )
            if result.get("quality_repair_used"):
                state["composer_quality_repair_used"] = True
            suggestions = result.get("suggested_questions")
            if isinstance(suggestions, list):
                normalized_suggestions = [str(item).strip() for item in suggestions if str(item).strip()][:4]
                if normalized_suggestions:
                    state["suggested_questions"] = normalized_suggestions
                    state["suggested_questions_source"] = "llm_composer"
            state["composer_backend"] = "llm"
            return
        state["composer_backend"] = "deterministic"
        state["composer_error"] = str((result or {}).get("error") if isinstance(result, dict) else "empty_llm_compose_result")
        error_status = "failed" if isinstance(result, dict) and result.get("error") else "invalid_output"
        state.setdefault("component_errors", []).append(
            {
                "component": "answer_composer",
                "status": error_status,
                "message": state["composer_error"],
                "recoverable": True,
                "user_visible": False,
            }
        )
        if self.config.composer_required and not str(state.get("answer_markdown") or "").strip():
            raise NativeAgentRuntimeUnavailable("LLM answer composer did not return answer_markdown")

    def _compose_diagram_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        mermaid = workflow_mermaid(doc) if doc else workflow_definition_mermaid(definition, event_context)
        mapping_rows = workflow_summary_rows(doc) if doc else workflow_definition_summary_rows(definition, event_context)
        state["artifacts"] = [
            agent_artifact(
                "mermaid",
                title="업무 흐름",
                source=mermaid,
                reason="사용자가 요청한 업무 흐름 프로세스 플로우",
            ),
            agent_artifact(
                "workflow_summary",
                title="원본 매핑",
                data=mapping_rows,
                role="evidence",
                display_mode="collapsed",
                priority=70,
                reason="Mermaid 도식의 단계별 원본 근거",
                user_requested=False,
            ),
        ]
        title = doc_title(doc, str(definition.get("title") or "현재 Workflow 정의"))
        state["answer_markdown"] = (
            f"## {title} 프로세스 플로우\n\n"
            "요청한 업무 목적에 맞춰 업무 흐름을 다이어그램으로 정리했습니다. "
            "SOP가 있는 경우에는 SOP 단계를 기준으로, SOP가 없는 경우에는 필요한 업무 BoI와 근거, 다음 행동 기준으로 구체 항목 이름을 표시했습니다. "
            "단계별 원본 매핑은 근거 자료에서 확인할 수 있습니다."
        )
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {}) if doc else workflow_definition_links(definition, event_context)
        state["citations"] = state["links"][:5]

    def _compose_gap_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        specs = (state.get("tool_results") or {}).get("action_specs") or []
        rows = action_gap_rows(doc, specs)
        state["artifacts"] = [agent_artifact("gap_table", title="Action 명세 점검", data=rows)]
        missing = [row for row in rows if str(row.get("status") or "") != "ready"]
        state["answer_markdown"] = (
            f"## {doc_title(doc, '현재 SOP')} Action 명세 점검\n\n"
            f"연결된 Action {len(rows)}건을 확인했습니다. "
            f"보강이 필요한 항목은 {len(missing)}건입니다. "
            "아래 점검 표에서 각 Action의 준비 상태와 근거를 확인할 수 있습니다."
        )
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {})
        state["citations"] = state["links"][:5]

    def _compose_workflow_answer(self, state: JsonDict) -> None:
        doc = (state.get("tool_results") or {}).get("current_doc") or {}
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        rows = workflow_summary_rows(doc) if doc else []
        if not rows:
            rows = workflow_definition_summary_rows(definition, event_context)
        state["artifacts"] = [agent_artifact("workflow_summary", title="업무 흐름 요약", data=rows)]
        title = doc_title(doc, str(definition.get("title") or "BoI 업무 흐름"))
        lines = [f"## {title} 관계 요약", ""]
        process_model = str(definition.get("process_model") or "")
        process_label = {
            "sop_based": "SOP 기반 업무",
            "pattern_based": "반복 업무",
            "ad_hoc": "비정형 업무",
            "external_orchestrator": "외부 실행 시스템 연계 업무",
        }.get(process_model, "SOP 기반 업무" if _registry_list(definition.get("sop_refs")) else "비정형 업무")
        work_boi_outputs = _registry_list(definition.get("work_boi_outputs"))
        if event_context.get("event_type") or definition.get("workflow_definition_key"):
            lines.append(
                f"Event `{event_context.get('event_type') or '-'}` 기준으로 연결된 업무 흐름과 필요한 업무 BoI를 확인했습니다. "
                f"업무 유형은 {process_label}이며 실행 방식은 {definition.get('workflow_engine') or 'event_native'}입니다."
            )
            if work_boi_outputs:
                lines.append(f"채워야 할 업무 BoI는 {', '.join(work_boi_outputs[:4])}입니다.")
            lines.append("")
        if rows:
            action_count = sum(len(row.get("actions") or []) if isinstance(row.get("actions"), list) else bool(row.get("actions")) for row in rows)
            manual_count = sum(len(row.get("manual_actions") or []) if isinstance(row.get("manual_actions"), list) else bool(row.get("manual_actions")) for row in rows)
            lines.append(
                f"총 {len(rows)}개 단계와 {action_count}개 Action, {manual_count}개 수동 조치 후보를 표로 정리했습니다. "
                "아래 업무 흐름 요약 표에서 단계별 연결 관계를 확인하세요."
            )
        if not rows:
            lines.append("현재 문서에서 업무 흐름 metadata를 찾지 못했습니다. 연결된 SOP/이벤트/Action 문서를 더 확인해야 합니다.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = links_from_doc_and_search(doc, state.get("search") or {}) if doc else workflow_definition_links(definition, event_context)
        state["citations"] = state["links"][:5]
        state["authoritative_answer_contract"] = "workflow_summary"

    def _compose_related_items_answer(self, state: JsonDict) -> None:
        route = state.get("route") if isinstance(state.get("route"), dict) else {}
        semantic = route.get("semantic_route") if isinstance(route.get("semantic_route"), dict) else {}
        target_kind = str(semantic.get("target_kind") or route.get("matched_affordance") or "related_boi")
        scope = str(semantic.get("scope") or "current_page_related") if target_kind == "related_sop" else "current_page_related"
        query = str(semantic.get("query") or "")
        items, overflow = self._related_items_for_target(state, target_kind, scope=scope, query=query)
        label = RELATED_AFFORDANCE_LABELS.get(target_kind, "관련 항목")
        item_label_text = label.removeprefix("관련 ")
        continuation_of = str(semantic.get("continuation_of") or route.get("continuation_of") or "")
        resolved_from_turn = str(semantic.get("resolved_from_turn") or route.get("resolved_from_turn") or "")
        page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
        page_title = str(page.get("title") or page.get("page_kind") or "현재 화면")
        if items:
            lines = [f"## {label}", ""]
            if target_kind == "related_sop" and scope == "catalog_all":
                lines.append(f"SOP 카탈로그 전체에서 접근 가능한 SOP를 **{len(items)}건** 찾았습니다.")
                if overflow.get("has_more"):
                    lines.append(f"아래에는 먼저 볼 {len(items)}건만 표시합니다. 전체 결과는 SOP 카탈로그에서 필터로 이어서 볼 수 있습니다.")
            elif target_kind == "related_sop" and scope == "catalog_search":
                shown_query = query or "요청한 조건"
                lines.append(f"`{shown_query}` 조건에 맞는 SOP를 **{len(items)}건** 찾았습니다.")
                if overflow.get("has_more"):
                    lines.append("결과가 더 있습니다. 조건을 좁히거나 SOP 카탈로그에서 이어서 확인하세요.")
            elif continuation_of == target_kind:
                lines.append(f"방금 요청한 {item_label_text} 목록 기준으로 이어서 보면, 현재 페이지와 직접 연결된 {item_label_text}는 **{len(items)}건**입니다.")
            else:
                lines.append(f"현재 페이지와 직접 연결된 {item_label_text}는 **{len(items)}건**입니다.")
            for item in items[:5]:
                title = str(item.get("title") or item.get("ref") or label)
                reason = str(item.get("reason") or "현재 페이지의 Event/Action 연결에서 확인했습니다.")
                url = str(item.get("url") or "")
                if url:
                    lines.append(f"- [{title}]({url}) - {reason}")
                else:
                    lines.append(f"- **{title}** - {reason}")
        else:
            if target_kind == "related_sop" and scope == "catalog_search":
                empty_message = f"`{query or '요청한 조건'}` 조건에 맞는 SOP를 찾지 못했습니다."
            elif target_kind == "related_sop" and scope == "catalog_all":
                empty_message = "접근 가능한 SOP 카탈로그 항목을 찾지 못했습니다."
            else:
                empty_message = f"현재 페이지 **{page_title}**에서 바로 연결된 {label}을 찾지 못했습니다."
            lines = [
                f"## {label}",
                "",
                empty_message,
                "관련 Event, Action, SOP 링크가 있는지 BoI Wiki 검색으로 한 번 더 확인하세요.",
            ]
        state["answer_markdown"] = "\n".join(lines).strip()
        state["links"] = [
            {"label": str(item.get("title") or item.get("ref") or label), "url": str(item.get("url") or ""), "kind": str(item.get("kind") or target_kind)}
            for item in items
            if item.get("url")
        ]
        state["citations"] = state["links"][:5]
        state["related_item_context"] = {
            "target_kind": target_kind,
            "items": items,
            "direct_count": len(items),
            "scope": scope,
            "query": query,
            "continuation_of": continuation_of,
            "resolved_from_turn": resolved_from_turn,
            "overflow": overflow,
        }
        state["authoritative_answer_contract"] = "related_items_lookup"

    def _related_items_for_target(self, state: JsonDict, target_kind: str, *, scope: str = "current_page_related", query: str = "") -> tuple[list[JsonDict], JsonDict]:
        if target_kind == "related_sop":
            return self._related_sop_items(state, scope=scope, query=query)
        if target_kind == "related_event":
            return self._related_event_items(state), {"has_more": False, "omitted_count": 0}
        if target_kind == "related_action":
            return self._related_action_items(state), {"has_more": False, "omitted_count": 0}
        return self._related_boi_items(state), {"has_more": False, "omitted_count": 0}

    def _related_sop_items(self, state: JsonDict, *, scope: str = "current_page_related", query: str = "") -> tuple[list[JsonDict], JsonDict]:
        if scope in {"catalog_all", "catalog_search"} and self.tools.sop_catalog_search is not None:
            result = self._call_tool(
                "sop_catalog_search",
                {"query": query, "scope": scope, "limit": 12},
                lambda: self.tools.sop_catalog_search(query, scope, 12),
                state,
            )
            raw_items = result.get("items") if isinstance(result, dict) else []
            items = [
                {
                    "kind": "sop",
                    "ref": str(item.get("boi_id") or item.get("ref") or ""),
                    "title": str(item.get("title") or item.get("boi_id") or "SOP"),
                    "url": str(item.get("url") or ""),
                    "reason": str(item.get("reason") or ("SOP 카탈로그에서 찾았습니다." if scope == "catalog_all" else "검색 조건과 일치합니다.")),
                }
                for item in (raw_items or [])
                if isinstance(item, dict)
            ]
            total = int(result.get("total") or len(items)) if isinstance(result, dict) else len(items)
            return dedupe_related_items(items), {"has_more": total > len(items), "omitted_count": max(0, total - len(items))}
        refs: list[tuple[str, str]] = []
        page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        add_related_ref(refs, str(page.get("sop_ref") or ""), "현재 화면에 연결된 SOP입니다.")
        add_related_ref(refs, str(event_context.get("sop_ref") or ""), "현재 Event가 이 SOP 단계에 연결됩니다.")
        for ref in _registry_list(definition.get("sop_refs")):
            add_related_ref(refs, ref, "현재 보고서의 Event/Action이 이 SOP 실행 흐름에 포함됩니다.")
        items: list[JsonDict] = []
        for ref, reason in refs[:8]:
            doc = self._call_tool("boi_get", {"boi_id": ref}, lambda ref=ref: self.tools.boi_get(ref), state)
            title = doc_title(doc if isinstance(doc, dict) else {}, readable_ref_label(ref))
            url = str((doc or {}).get("url") or f"/docs/{ref}")
            items.append({"kind": "sop", "ref": ref, "title": title, "url": url, "reason": reason})
        return dedupe_related_items(items), {"has_more": False, "omitted_count": 0}

    def _related_event_items(self, state: JsonDict) -> list[JsonDict]:
        page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        refs: list[tuple[str, str]] = []
        add_related_ref(refs, str(page.get("event_type") or ""), "현재 화면에 연결된 Event입니다.")
        add_related_ref(refs, str(event_context.get("event_type") or ""), "현재 업무 맥락의 기준 Event입니다.")
        for ref in _registry_list(definition.get("entry_events")) + _registry_list(definition.get("emitted_events")):
            add_related_ref(refs, ref, "현재 SOP 실행 흐름에서 쓰이는 Event입니다.")
        for contract in definition.get("event_contracts") or []:
            if isinstance(contract, dict):
                add_related_ref(refs, str(contract.get("event_type") or ""), "현재 SOP 실행 흐름의 Event 계약입니다.")
        items: list[JsonDict] = []
        for ref, reason in refs[:8]:
            event = self._call_tool("event_type_lookup", {"event_type": ref}, lambda ref=ref: self.tools.event_type_lookup(ref), state) or {}
            title = str(event.get("name_ko") or ref)
            items.append({"kind": "event", "ref": ref, "title": title, "url": f"/event-types/{ref}", "reason": reason})
        return dedupe_related_items(items)

    def _related_action_items(self, state: JsonDict) -> list[JsonDict]:
        page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
        event_context = state.get("event_context") if isinstance(state.get("event_context"), dict) else {}
        definition = state.get("workflow_definition_context") if isinstance(state.get("workflow_definition_context"), dict) else {}
        refs: list[tuple[str, str]] = []
        add_related_ref(refs, str(page.get("action_key") or ""), "현재 화면에 연결된 Action입니다.")
        for ref in _registry_list(page.get("workflow_actions")):
            add_related_ref(refs, ref, "현재 화면의 SOP 실행 흐름에 포함된 Action입니다.")
        for ref in _registry_list(definition.get("action_refs")):
            add_related_ref(refs, ref, "현재 보고서의 업무 흐름에서 재사용하는 Action입니다.")
        for ref in _registry_list(event_context.get("recommended_actions")) + _registry_list(event_context.get("recommended_manual_actions")):
            add_related_ref(refs, ref, "현재 Event가 권장하는 Action입니다.")
        items: list[JsonDict] = []
        for ref, reason in refs[:8]:
            spec = self._call_tool("action_spec_lookup", {"action_key": ref}, lambda ref=ref: self.tools.action_spec_lookup(ref), state) or {}
            item = spec.get("item") if isinstance(spec.get("item"), dict) else {}
            title = str(item.get("name_ko") or item.get("name") or ref)
            items.append({"kind": "action", "ref": ref, "title": title, "url": str(spec.get("url") or ""), "reason": reason})
        return dedupe_related_items(items)

    def _related_boi_items(self, state: JsonDict) -> list[JsonDict]:
        search = state.get("search") if isinstance(state.get("search"), dict) else {}
        items: list[JsonDict] = []
        for item in search.get("best_matches") or []:
            url = str(item.get("url") or "")
            if not url:
                continue
            items.append(
                {
                    "kind": str(item.get("kind") or "boi"),
                    "ref": str(item.get("boi_id") or item.get("uri") or item.get("ref") or ""),
                    "title": item_label(item),
                    "url": url,
                    "reason": compact_text(str(item.get("match_reason") or item.get("description") or "BoI Wiki 검색에서 연결 후보로 확인했습니다."), 140),
                }
            )
        return dedupe_related_items(items[:8])

    def _compose_trace_answer(self, state: JsonDict) -> None:
        workflow = (state.get("tool_results") or {}).get("workflow_status") or {}
        trace = (state.get("tool_results") or {}).get("trace_context") or {}
        lines = ["## Trace 실행 상태 요약", ""]
        if workflow:
            lines.append(f"- 업무 흐름: `{workflow.get('workflow_key') or workflow.get('workflow') or '-'}`")
            lines.append(f"- 이벤트 수: {len(workflow.get('events') or [])}")
            lines.append(f"- Action 수: {len(workflow.get('actions') or [])}")
            lines.append(f"- 수동 조치 수: {len(workflow.get('manual_handoffs') or [])}")
        elif trace:
            lines.append(f"- Trace 이벤트 수: {len(trace.get('events') or [])}")
            lines.append(f"- Trace Action 수: {len(trace.get('actions') or [])}")
        else:
            lines.append("현재 trace context를 찾지 못했습니다. 업무 흐름 상태나 Event Stream 링크로 trace를 확인해야 합니다.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = trace_links(workflow, trace)
        state["citations"] = state["links"][:5]

    def _compose_workflow_manual_answer(self, state: JsonDict) -> None:
        workflow = (state.get("tool_results") or {}).get("workflow_status") or {}
        page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
        if not workflow:
            workflow = {
                "workflow_key": page.get("workflow_key") or "",
                "trace_id": page.get("trace_id") or "",
                "manual_handoffs": page.get("manual_handoffs") or page.get("expected_manual_actions") or [],
                "expected_manual_actions": page.get("expected_manual_actions") or page.get("manual_handoffs") or [],
                "manual_action_details": page.get("manual_action_details") or {},
                "approval_required_actions": page.get("approval_required_actions") or [],
                "events": page.get("events") or [],
                "actions": page.get("actions") or [],
                "generated_docs": page.get("generated_docs") or [],
                "status_page_url": page.get("url") or "",
            }
        rows = workflow_manual_summary_rows(workflow)
        expected_count = len(rows)
        action_count = len(workflow.get("actions") or [])
        event_count = len(workflow.get("events") or [])
        generated_count = len(workflow.get("generated_docs") or [])
        previous_answer_wrong = conversation_mentions_no_manual_handoffs(state.get("request") or {})
        if expected_count:
            prefix = "현재 기준으로 다시 확인하면" if previous_answer_wrong else "현재 Workflow Status 기준으로"
            answer = (
                f"## 남은 수동 조치 정리\n\n"
                f"{prefix} 수동 조치로 확인해야 할 항목은 **{expected_count}건**입니다. "
                f"같은 trace에서 이벤트 {event_count}건, Action {action_count}건, 생성 BoI {generated_count}건을 함께 확인했습니다.\n\n"
                "아래 카드/표는 담당자가 업무 관점에서 확인할 항목입니다. 실제 완료 기록은 별도 확인 카드와 권한 검사를 거쳐야 합니다."
            )
        else:
            answer = (
                "## 남은 수동 조치 정리\n\n"
                "현재 Workflow Status와 SOP 정의에서 담당자가 처리해야 할 수동 조치 항목을 찾지 못했습니다. "
                "단, trace 로그가 아직 수집되지 않았을 수 있으므로 Event Stream과 원본 workflow 상태를 함께 확인하세요."
            )
        state["answer_markdown"] = answer
        state["artifacts"] = [agent_artifact("manual_handoff_summary", title="남은 수동 조치", data=rows)]
        state["links"] = trace_links(workflow, (state.get("tool_results") or {}).get("trace_context") or {})
        status_page_url = str(workflow.get("status_page_url") or page.get("url") or "")
        if status_page_url:
            state["links"].insert(0, {"label": "Workflow Status", "url": status_page_url, "kind": "workflow_status"})
        state["citations"] = state["links"][:5]
        state["suggested_questions"] = workflow_manual_followup_questions(rows)
        state["suggested_questions_source"] = "workflow_manual_affordance"
        state["authoritative_answer_contract"] = "workflow_manual_summary"

    def _compose_inbox_answer(self, state: JsonDict) -> None:
        inbox = (state.get("tool_results") or {}).get("agent_inbox") or {}
        items = inbox.get("items") or []
        lines = [f"현재 처리할 업무는 {len(items)}건입니다."]
        cards = []
        for item in items[:10]:
            display = item.get("display") if isinstance(item.get("display"), dict) else {}
            title = display.get("title") or item.get("action_key") or "업무 확인"
            status = display.get("status_label") or item.get("status") or "확인 필요"
            next_action = display.get("next_action") or "실행 현황이나 원본 기록을 확인하세요."
            context = item.get("context_preview") if isinstance(item.get("context_preview"), dict) else {}
            narrative = item.get("work_context_narrative") if isinstance(item.get("work_context_narrative"), dict) else {}
            if not narrative:
                narrative = context.get("work_context_narrative") if isinstance(context.get("work_context_narrative"), dict) else {}
            context_lines = []
            if narrative.get("summary_state") == "ready":
                stage_narrative = narrative.get("stage_history_narrative") if isinstance(narrative.get("stage_history_narrative"), list) else []
                stage_text = "; ".join(str(row.get("text") or "") for row in stage_narrative[:3] if isinstance(row, dict) and row.get("text"))
                if stage_text:
                    context_lines.append(f"지금까지 처리된 내용: {stage_text}")
                similar = narrative.get("similar_case_narrative") if isinstance(narrative.get("similar_case_narrative"), dict) else {}
                if similar.get("text"):
                    context_lines.append(f"비슷한 과거 처리: {similar.get('text')}")
                draft_note = narrative.get("recommended_draft_note") if isinstance(narrative.get("recommended_draft_note"), dict) else {}
                if draft_note.get("text"):
                    context_lines.append(f"추천 조치 초안: {draft_note.get('text')}")
            elif context:
                context_lines.append("업무 맥락 요약은 준비 중입니다. 원본 실행 현황과 기록을 확인해 판단하세요.")
            if len(lines) == 1:
                lines.append(f"가장 먼저 볼 업무는 {status} 상태의 '{title}'입니다. 다음 행동은 '{next_action}'입니다.")
                lines.extend(line for line in context_lines[:3] if line)
            cards.append(display or item)
        state["answer_markdown"] = "\n".join(lines).strip()
        state["artifacts"] = [agent_artifact("task_cards", title="처리할 업무", data=cards)]
        state["links"] = [
            {"label": str(link.get("label") or item.get("action_key") or item.get("request_id") or "Inbox"), "url": str(link.get("url") or ""), "kind": str(link.get("kind") or "inbox")}
            for item in items
            for link in (item.get("user_links") or [])
            if link.get("url")
        ]
        state["citations"] = []

    def _compose_search_answer(self, state: JsonDict) -> None:
        search = state.get("search") or {}
        page = state.get("page_context") or {}
        if compose_action_requirement_answer(state):
            return
        if state.get("intent") in {"summarize", "page_qa"} and page.get("resolved"):
            report_answer = compose_current_doc_report_answer(state)
            if report_answer:
                state["answer_markdown"] = report_answer
                doc = (state.get("tool_results") or {}).get("current_doc") or {}
                state["links"] = links_from_doc_and_search(doc, search)
                state["citations"] = state["links"][:5]
                state["authoritative_answer_contract"] = "page_context_report_qa"
                return
            title = str(page.get("title") or page.get("page_kind") or "현재 화면")
            excerpt = compact_plain_markdown_text(str(page.get("body_excerpt") or ""), 300)
            lines = [f"현재 화면 **{title}** 기준으로 요약합니다."]
            if excerpt:
                lines.append(excerpt)
            if page.get("workflow_key"):
                lines.append(
                    f"workflow `{page.get('workflow_key')}` 기준으로 Event {len(page.get('workflow_event_types') or [])}개, "
                    f"Action {page.get('workflow_action_count') or 0}개, Manual Handoff {page.get('workflow_manual_action_count') or 0}개가 연결되어 있습니다."
                )
            state["answer_markdown"] = "\n".join(lines)
            doc = (state.get("tool_results") or {}).get("current_doc") or {}
            state["links"] = links_from_doc_and_search(doc, search)
            state["citations"] = state["links"][:5]
            state["authoritative_answer_contract"] = "page_context_summary"
            return
        lines = []
        if page.get("resolved"):
            lines.append(f"현재 화면 **{page.get('title') or page.get('page_kind')}** 기준으로 관련 지식을 찾았습니다.")
        else:
            lines.append("BoI Wiki ontology search 기준으로 관련 지식을 찾았습니다.")
        expansion = search.get("query_expansion") or []
        if expansion:
            lines.append("해석한 업무 용어: " + ", ".join(f"`{term}`" for term in expansion[:6]))
        matches = search.get("best_matches") or []
        for item in matches[:5]:
            label = item_label(item)
            url = str(item.get("url") or "")
            desc = compact_text(str(item.get("description") or item.get("match_reason") or ""), 140)
            lines.append(f"- [{label}]({url}) - {desc}" if url else f"- **{label}** - {desc}")
        if not matches:
            lines.append("직접 연결된 결과를 찾지 못했습니다. 더 구체적인 SOP, Event, Action 이름으로 다시 물어보세요.")
        state["answer_markdown"] = "\n".join(lines)
        state["links"] = links_from_search(search)
        state["citations"] = state["links"][:5]
        state["authoritative_answer_contract"] = "ontology_search"

    def _verify_acl_and_artifacts(self, state: JsonDict) -> JsonDict:
        seen: set[str] = set()
        links = []
        for link in state.get("links") or []:
            url = str(link.get("url") or link.get("href") or "")
            label = str(link.get("label") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({"label": label or url, "url": url, "kind": str(link.get("kind") or "reference")})
        state["links"] = links[:12]
        state["citations"] = [item for item in state.get("citations") or [] if item.get("url") or item.get("ref")][:8]
        state.setdefault("guardrails_applied", []).append("artifact_link_acl")
        return state

    def _safety_gate(self, state: JsonDict) -> JsonDict:
        route_name = state.get("route_name")
        if route_name in {"manual_handoff", "approval_required"}:
            confirmation = confirmation_payload_for_state(state)
            state["answer_markdown"] = (
                confirmation["answer_markdown"]
            )
            state["artifacts"] = [
                agent_artifact(
                    "confirmation_required",
                    title=confirmation["title"],
                    data=confirmation["data"],
                    reason="상태 변경 전 사용자 확인이 필요한 요청",
                )
            ]
        return state

    def _response(self, state: JsonDict) -> JsonDict:
        route = state.get("route") or {}
        return {
            "ok": True,
            "run_id": state.get("run_id"),
            "answer_markdown": state.get("answer_markdown") or "",
            "links": state.get("links") or [],
            "citations": state.get("citations") or [],
            "suggested_questions": state.get("suggested_questions") or [],
            "suggested_questions_source": state.get("suggested_questions_source") or "suggestions_endpoint_required",
            "artifacts": state.get("artifacts") or [],
            "goal_model": state.get("goal_model") or goal_model_for_state(state),
            "response_profile": state.get("response_profile") or response_profile_for_state(state),
            "component_errors": state.get("component_errors") or [],
            "context_summary": {
                "route": state.get("route_name"),
                "intent": state.get("intent"),
                "router_backend": route.get("router_backend"),
                "router_confidence": route.get("confidence"),
                "used_backend": "native_langgraph",
                "page_context": state.get("page_context") or {},
                "langgraph_available": bool(state.get("langgraph_available")),
                "composer_backend": state.get("composer_backend") or "deterministic",
                "composer_error": state.get("composer_error") or "",
                "composer_quality_repair_used": bool(state.get("composer_quality_repair_used")),
            },
            "ontology_context": compact_ontology_context(state.get("search") if isinstance(state.get("search"), dict) else {}),
            "action_context": compact_action_context((state.get("tool_results") or {}).get("action_specs") or []),
            "event_context": state.get("event_context") or {},
            "workflow_definition_context": state.get("workflow_definition_context") or {},
            "route": state.get("route_name"),
            "intent": state.get("intent"),
            "router_backend": route.get("router_backend"),
            "router_confidence": route.get("confidence"),
            "used_backend": "native_langgraph",
            "tool_trace": [item.__dict__ for item in state.get("tool_trace") or []],
            "status_updates": state.get("status_updates") or [],
            "coverage_report": state.get("coverage_report") or {},
            "semantic_route": route.get("semantic_route") or {},
            "route_candidates": route.get("route_candidates") or [],
            "llm_reranker_used": bool(route.get("llm_reranker_used")),
            "matched_affordance": route.get("matched_affordance") or ((route.get("semantic_route") or {}).get("matched_affordance") if isinstance(route.get("semantic_route"), dict) else ""),
            "related_item_context": state.get("related_item_context") or {},
            "deployment_revision": self.config.build_revision,
            "access_summary": state.get("access_summary") or {},
            "guardrails_applied": state.get("guardrails_applied") or [],
            "redacted_count": len((state.get("access_summary") or {}).get("redactions") or []),
            "answer_quality": {
                "authoritative_contract": state.get("authoritative_answer_contract") or "",
                "component_error_count": len(state.get("component_errors") or []),
            },
        }

    def _call_tool(self, name: str, args: JsonDict, fn: Callable[[], Any], state: JsonDict) -> Any:
        self._emit_progress({"stage": "tool_start", "tool": name, "args": compact_tool_args(args)})
        started = time.perf_counter()
        try:
            result = fn()
            status = "ok" if result else "empty"
            summary = summarize_tool_result(result)
        except Exception as exc:  # pragma: no cover - defensive guard for runtime tools.
            result = {"error": repr(exc)}
            status = "failed"
            summary = repr(exc)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        state.setdefault("tool_trace", []).append(ToolTraceItem(tool=name, status=status, elapsed_ms=elapsed_ms, summary=summary, args=args, result=compact_tool_result(result)))
        self._emit_progress(
            {
                "stage": "tool_done",
                "tool": name,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "summary": summary,
            }
        )
        return result

    def _emit_progress(self, payload: JsonDict) -> None:
        callback = self.config.progress_callback
        if not callback:
            return
        try:
            callback(payload)
        except Exception:
            return


def summarize_tool_result(result: Any) -> str:
    if isinstance(result, dict):
        if result.get("title"):
            return str(result["title"])
        if result.get("count") is not None:
            return f"count={result.get('count')}"
        if result.get("best_matches") is not None:
            return f"best_matches={len(result.get('best_matches') or [])}"
    if isinstance(result, list):
        return f"items={len(result)}"
    return "ok" if result else "empty"


def compact_tool_args(args: JsonDict) -> JsonDict:
    compact: JsonDict = {}
    for key, value in (args or {}).items():
        if key in {"query", "boi_id", "trace_id", "workflow_key", "action_key", "event_type", "scope", "limit"}:
            compact[key] = compact_text(str(value), 120) if isinstance(value, str) else value
    return compact


def compact_tool_result(result: Any) -> Any:
    if isinstance(result, dict):
        keys = ("ok", "title", "boi_id", "event_type", "action_key", "count", "status", "workflow_key", "trace_id")
        compact = {key: result.get(key) for key in keys if key in result}
        if result.get("best_matches") is not None:
            compact["best_matches"] = [item_label(item) for item in (result.get("best_matches") or [])[:5]]
        return compact or {"keys": sorted(result.keys())[:12]}
    if isinstance(result, list):
        return {"items": len(result)}
    return result


def llm_compose_payload(state: JsonDict) -> JsonDict:
    search = state.get("search") if isinstance(state.get("search"), dict) else {}
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    action_specs = tool_results.get("action_specs") if isinstance(tool_results.get("action_specs"), list) else []
    intent = str(state.get("intent") or "")
    draft = str(state.get("answer_markdown") or "")
    if intent == "diagram":
        draft = strip_mermaid_fences(draft)
    return {
        "task": "compose_final_boi_agent_answer",
        "language": "ko",
        "style": {
            "audience": "일반 구성원과 업무 담당자가 이해할 수 있는 간결한 업무 문장",
            "format": "GitHub-flavored Markdown",
            "language_contract": "한국어 업무 문장을 기본으로 쓰고, 영어는 BoI/SOP/Event/Action/API/MCP/URL/code identifier 같은 공식 용어에만 사용",
            "avoid": [
                "내부 stack trace",
                "근거 없는 단정",
                "권한 없는 private 내용",
                "dry-run",
                "fallback",
                "stub",
                "중국어/한자 장식어",
                "아랍어/키릴/그리스 문자",
                "영어-only 섹션 제목",
            ],
        },
        "question": state.get("question") or "",
        "route": state.get("route_name") or "",
        "intent": intent,
        "artifact_policy": {
            "mermaid": "If intent is diagram, Mermaid is rendered from structured artifacts. Do not include Mermaid code fences in answer_markdown.",
        },
        "page_context": {
            key: page_context.get(key)
            for key in (
                "page_kind",
                "resolved",
                "title",
                "boi_id",
                "type",
                "event_type",
                "workflow_key",
                "trace_id",
                "workflow_event_types",
                "workflow_action_count",
                "workflow_manual_action_count",
                "body_excerpt",
            )
            if page_context.get(key) not in (None, "", [])
        },
        "current_doc": {
            "title": doc_title(current_doc, "") if current_doc else "",
            "boi_id": current_doc.get("boi_id") if isinstance(current_doc, dict) else "",
            "body_excerpt": compact_text(str(current_doc.get("body_excerpt") or ""), 900) if isinstance(current_doc, dict) else "",
        },
        "search_matches": [
            {
                "label": item_label(item),
                "kind": item.get("kind"),
                "type": item.get("type"),
                "url": item.get("url"),
                "description": compact_text(str(item.get("description") or item.get("match_reason") or ""), 180),
            }
            for item in (search.get("best_matches") or [])[:6]
            if isinstance(item, dict)
        ],
        "action_specs": [
            {
                "action_key": ((spec.get("item") if isinstance(spec.get("item"), dict) else spec) or {}).get("action_key"),
                "doc_ref": ((spec.get("item") if isinstance(spec.get("item"), dict) else spec) or {}).get("doc_ref"),
            }
            for spec in action_specs[:12]
            if isinstance(spec, dict)
        ],
        "coverage_report": state.get("coverage_report") or {},
        "tool_trace": [
            {
                "tool": item.tool,
                "status": item.status,
                "summary": item.summary,
            }
            for item in (state.get("tool_trace") or [])[-10:]
            if isinstance(item, ToolTraceItem) and item.tool != "answer_composer"
        ],
        "structured_draft": compact_text(draft, 3200),
        "required_json_schema": {
            "flat_answer_plan": {
                "title": "short Korean title without Markdown syntax",
                "summary": "concise Korean synthesis based only on supplied evidence",
                "suggested_question_1": "optional short Korean follow-up question",
                "suggested_question_2": "optional short Korean follow-up question",
            },
            "server_rendering": "The LLM must not write final Markdown, arrays, nested objects, links, tables, or Mermaid. BoI API renders Markdown and artifacts from this flat plan plus verified evidence.",
        },
    }


def strip_mermaid_fences(value: str) -> str:
    return re.sub(
        r"```[^\S\r\n]*mermaid[^\S\r\n]*(?:\r?\n).*?(?:\r?\n)?```",
        "[Mermaid diagram is provided as a separate structured artifact.]",
        str(value or ""),
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()


def remove_mermaid_fences(value: str) -> str:
    return re.sub(
        r"```[^\S\r\n]*mermaid[^\S\r\n]*(?:\r?\n).*?(?:\r?\n)?```",
        "",
        str(value or ""),
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()


def structured_details_for_composer_merge(intent: str, structured_answer: str) -> str:
    draft = str(structured_answer or "").strip()
    if not draft:
        return ""
    if intent in {"diagram", "gap_check", "workflow_explain"}:
        return ""
    return draft


def merge_composer_answer_with_structured_details(intent: str, composer_answer: str, structured_answer: str) -> str:
    answer = str(composer_answer or "").strip()
    details = structured_details_for_composer_merge(intent, structured_answer)
    if not answer:
        return details
    if not details or details in answer:
        return answer
    return f"{answer}\n\n{details}".strip()


def compact_text(value: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def compact_plain_markdown_text(value: str, limit: int = 360) -> str:
    text = str(value or "")
    text = re.split(r"\s+#\s+", text, maxsplit=1)[0]
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"[#|*_>`]+", " ", text)
    return compact_text(text, limit)


def compose_current_doc_report_answer(state: JsonDict) -> str:
    question = str((state.get("request") or {}).get("question") or state.get("question") or "")
    body = current_doc_report_text(state)
    if not body:
        return ""
    if is_missing_evidence_question(question):
        return compose_missing_evidence_answer(body)
    if is_decision_evidence_question(question):
        return compose_decision_evidence_answer(body)
    return ""


def current_doc_report_text(state: JsonDict) -> str:
    page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    doc = (state.get("tool_results") or {}).get("current_doc")
    parts: list[str] = []
    if isinstance(doc, dict):
        for key in ("body", "body_excerpt", "description"):
            value = str(doc.get(key) or "").strip()
            if value:
                parts.append(value)
    for key in ("body", "body_excerpt", "summary", "description"):
        value = str(page.get(key) or "").strip()
        if value:
            parts.append(value)
    text = "\n".join(parts)
    text = re.sub(r"\bsource_ids?\s*:\s*\S*", "", text, flags=re.IGNORECASE)
    return text.strip()


def is_missing_evidence_question(question: str) -> bool:
    text = str(question or "").lower()
    return any(term in text for term in ("부족", "누락", "보강", "빠진", "missing")) and any(
        term in text for term in ("근거", "자료", "데이터", "확인", "evidence", "raw")
    )


def is_decision_evidence_question(question: str) -> bool:
    text = str(question or "").lower()
    return any(term in text for term in ("판단", "승인", "반려", "결정", "검토")) and any(
        term in text for term in ("근거", "자료", "데이터", "확인", "보고서")
    )


def compose_missing_evidence_answer(body: str) -> str:
    lines = report_body_lines(body)
    missing = select_report_lines(
        lines,
        required_any=("부족 근거", "부족한 근거", "누락", "확인 필요", "먼저 확인", "보강"),
        fallback_any=("Raw Data", "endpoint", "원본 데이터", "Data Lake"),
    )
    decision_basis = select_report_lines(
        lines,
        required_any=("판단 근거", "근거", "Trend", "Raw Data", "승인 리스크"),
        fallback_any=("확인됨", "확보", "필요"),
    )
    next_checks = select_report_lines(
        lines,
        required_any=("먼저 확인", "확인할 일", "확인하세요", "권장 확인", "해당 근거"),
        fallback_any=(),
    )
    if not missing and not any("Raw Data" in line or "endpoint" in line for line in lines):
        return ""
    direct = strongest_missing_evidence_sentence(missing or lines)
    answer_lines = ["## 부족한 근거", "", direct]
    if missing:
        answer_lines.extend(["", "확인해야 할 항목:"])
        answer_lines.extend(f"- {display_report_line(line)}" for line in missing[:4] if line and line not in {direct})
    if decision_basis:
        answer_lines.extend(["", "현재 보고서에서 이미 잡힌 판단 근거:"])
        answer_lines.extend(f"- {display_report_line(line)}" for line in decision_basis[:4])
    if next_checks:
        missing_keys = {report_line_dedupe_key(line) for line in missing}
        next_checks = [
            line
            for line in next_checks
            if report_line_dedupe_key(line) not in missing_keys
        ]
    if next_checks:
        answer_lines.extend(["", "다음 확인:"])
        answer_lines.extend(f"- {display_report_line(line)}" for line in next_checks[:3])
    return "\n".join(dedupe_adjacent_report_lines(answer_lines)).strip()


def compose_decision_evidence_answer(body: str) -> str:
    lines = report_body_lines(body)
    evidence = select_report_lines(
        lines,
        required_any=("판단 근거", "Trend", "Raw Data", "원인 후보", "승인 리스크", "이전 단계"),
        fallback_any=("확인됨", "확보", "확인 필요"),
    )
    next_checks = select_report_lines(
        lines,
        required_any=("부족 근거", "먼저 확인", "권장 판단", "확인할 일", "조치"),
        fallback_any=("승인", "반려", "보류", "추가 근거"),
    )
    if not evidence and not next_checks:
        return ""
    answer_lines = ["## 판단에 필요한 근거", ""]
    if evidence:
        answer_lines.append("보고서에서 확인된 근거:")
        answer_lines.extend(f"- {display_report_line(line)}" for line in evidence[:5])
    if next_checks:
        answer_lines.extend(["", "결정 전에 확인할 항목:"])
        answer_lines.extend(f"- {display_report_line(line)}" for line in next_checks[:4])
    return "\n".join(dedupe_adjacent_report_lines(answer_lines)).strip()


def report_body_lines(body: str) -> list[str]:
    text = re.sub(r"```.*?```", " ", str(body or ""), flags=re.DOTALL)
    text = re.sub(r"\s+(#{1,6}\s+)", r"\n\1", text)
    text = re.sub(r"\s+(-\s+)", r"\n\1", text)
    text = re.sub(r"\s+(\*\*[^*]{1,40}:\*\*)", r"\n\1", text)
    candidates: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", raw).strip()
        line = re.sub(r"^\s*[-*]\s*", "", line).strip()
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        line = re.sub(r"\bsource_ids?\s*:\s*\S*", "", line, flags=re.IGNORECASE).strip()
        pieces = re.split(r"(?<=[.!?。])\s+|(?=\*\*[^*]{1,40}:\*\*)", line)
        for piece in pieces:
            piece = re.sub(r"[#*_>`]+", " ", piece).strip()
            if not piece or piece.lower() in {"body", "metadata", "citations", "relationship graph"}:
                continue
            if piece.endswith(":") and len(piece) <= 40:
                continue
            if re.fullmatch(r"[-:| ]+", piece):
                continue
            if "|" in piece and piece.count("|") >= 2:
                continue
            candidates.append(compact_text(piece, 180))
    return dedupe_report_lines(candidates)


def select_report_lines(lines: list[str], *, required_any: tuple[str, ...], fallback_any: tuple[str, ...]) -> list[str]:
    selected = [
        line
        for line in lines
        if not is_low_signal_report_line(line)
        and any(term.lower() in line.lower() for term in required_any)
        and (not fallback_any or any(term.lower() in line.lower() for term in fallback_any))
    ]
    if selected:
        return dedupe_report_lines(selected)
    return dedupe_report_lines([line for line in lines if not is_low_signal_report_line(line) and any(term.lower() in line.lower() for term in fallback_any)])


def is_low_signal_report_line(line: str) -> bool:
    text = str(line or "")
    if "부족 근거" in text or "확인할 일" in text or "권장 확인" in text:
        return False
    return any(term in text for term in ("판단 대상입니다", "이 문서는 BoI Inbox", "검증된 보고서 BoI"))


def display_report_line(line: str) -> str:
    value = str(line or "").strip()
    value = re.sub(r"^(권장 확인 순서|판단 메모)\s*:\s*", "", value)
    value = re.sub(r"^부족 근거\s*:\s*", "", value)
    value = re.sub(r"^확인할 일\s*:\s*", "", value)
    return value.strip()


def strongest_missing_evidence_sentence(lines: list[str]) -> str:
    joined = " ".join(lines)
    if "Raw Data" in joined and "endpoint" in joined:
        return (
            "부족한 근거는 **Raw Data endpoint 확인**입니다. "
            "Trend나 조치 요청은 잡혀 있지만, 승인 또는 반려 전에 원본 Raw Data 접근 경로와 실제 데이터를 먼저 보강해야 합니다."
        )
    if "Raw Data" in joined:
        return "부족한 근거는 **Raw Data 확인**입니다. 승인 또는 반려 전에 원본 데이터와 현재 판단 근거를 대조해야 합니다."
    first = lines[0] if lines else "보고서에서 부족 근거를 확인해야 합니다."
    return f"부족한 근거는 **{first}**입니다."


def dedupe_report_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        value = str(line or "").strip()
        if not value:
            continue
        key = report_line_dedupe_key(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def report_line_dedupe_key(line: str) -> str:
    value = re.sub(r"\s+", " ", str(line or "")).strip()
    low = value.lower()
    if "raw data endpoint" in low:
        if "부족 근거" in value or "추가 근거" in value:
            return "missing:raw-data-endpoint"
        if "확인할 일" in value or "해당 근거" in value or "권장 확인" in value:
            return "next:raw-data-endpoint"
    return low


def dedupe_adjacent_report_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    last = ""
    for line in lines:
        key = re.sub(r"\s+", " ", str(line or "")).strip().lower()
        if key and key == last:
            continue
        out.append(line)
        last = key
    return out


def item_label(item: JsonDict) -> str:
    return str(item.get("title") or item.get("term") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or item.get("uri") or "결과")


def best_boi_ref_from_search(search: JsonDict, *, prefer_sop: bool = False) -> str:
    matches = [
        item
        for item in (search.get("best_matches") or [])
        if isinstance(item, dict) and str(item.get("kind") or "") == "boi" and (item.get("boi_id") or item.get("uri"))
    ]
    if prefer_sop:
        for item in matches:
            if str(item.get("type") or "") == "boi/sop":
                return str(item.get("boi_id") or item.get("uri") or "")
    return str((matches[0] or {}).get("boi_id") or (matches[0] or {}).get("uri") or "") if matches else ""


def doc_title(doc: JsonDict, fallback: str) -> str:
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    return str((metadata or {}).get("title") or doc.get("title") or fallback)


def add_related_ref(refs: list[tuple[str, str]], ref: str, reason: str) -> None:
    value = str(ref or "").strip()
    if not value:
        return
    if any(existing == value for existing, _ in refs):
        return
    refs.append((value, reason))


def dedupe_related_items(items: list[JsonDict]) -> list[JsonDict]:
    seen: set[str] = set()
    out: list[JsonDict] = []
    for item in items:
        key = str(item.get("url") or item.get("ref") or item.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def readable_ref_label(ref: str) -> str:
    value = str(ref or "").strip()
    if not value:
        return "연결 항목"
    return value.rsplit(":", 1)[-1].replace("-", " ").replace("_", " ")


def workflow_stages(doc: JsonDict) -> list[JsonDict]:
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    workflow = ((metadata or {}).get("workflow") or {}) if isinstance(metadata, dict) else {}
    stages = (workflow.get("stages") if isinstance(workflow, dict) else []) or []
    return [stage for stage in stages if isinstance(stage, dict)]


def workflow_item_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith(".v1"):
        text = text[:-3]
    parts = [part for part in re.split(r"[.:/]+", text) if part]
    if not parts:
        return text
    first = parts[0].lower()
    if first in {"sop", "langflow", "api", "webhook", "mcp", "manual"}:
        return parts[-1]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return text


def append_workflow_item_nodes(
    lines: list[str],
    *,
    stage_node: str,
    prefix: str,
    stage_index: int,
    items: Any,
    direction: str,
    max_items: int = 3,
) -> None:
    if not isinstance(items, list):
        items = [items] if items else []
    labels = []
    for item in items:
        label = workflow_item_label(item)
        if label:
            labels.append(label)
    for item_index, label in enumerate(labels[:max_items], start=1):
        item_node = f"{prefix}{stage_index}_{item_index}"
        if direction == "to_stage":
            lines.append(f'  {item_node}["{mermaid_label(label, 30)}"] --> {stage_node}')
        else:
            lines.append(f'  {stage_node} --> {item_node}["{mermaid_label(label, 30)}"]')
    if len(labels) > max_items:
        more_node = f"{prefix}{stage_index}_more"
        more_label = f"+{len(labels) - max_items}개"
        if direction == "to_stage":
            lines.append(f'  {more_node}["{more_label}"] --> {stage_node}')
        else:
            lines.append(f'  {stage_node} --> {more_node}["{more_label}"]')


def workflow_mermaid(doc: JsonDict) -> str:
    stages = workflow_stages(doc)
    if not stages:
        return 'flowchart TD\n  current["현재 문서"] --> missing["workflow metadata 확인 필요"]'
    lines = ["flowchart TD"]
    for index, stage in enumerate(stages, start=1):
        node = f"s{index}"
        label = mermaid_label(str(stage.get("name") or stage.get("id") or f"Stage {index}"))
        lines.append(f'  {node}["{label}"]')
        events = stage.get("event_types") or ([stage.get("entry_event")] if stage.get("entry_event") else [])
        automated_actions = stage.get("automated_actions") or []
        manual_actions = stage.get("manual_actions") or []
        append_workflow_item_nodes(lines, stage_node=node, prefix="e", stage_index=index, items=events, direction="to_stage")
        append_workflow_item_nodes(
            lines,
            stage_node=node,
            prefix="a",
            stage_index=index,
            items=automated_actions,
            direction="from_stage",
        )
        append_workflow_item_nodes(
            lines,
            stage_node=node,
            prefix="m",
            stage_index=index,
            items=manual_actions,
            direction="from_stage",
        )
        if index < len(stages):
            lines.append(f"  {node} --> s{index + 1}")
    return "\n".join(lines)


def mermaid_label(value: str, limit: int = 34) -> str:
    text = re.sub(r"[\r\n\t]+", " ", value or "").strip().replace('"', "'")
    return text[: limit - 1] + "…" if len(text) > limit else text


def workflow_summary_rows(doc: JsonDict) -> list[JsonDict]:
    rows = []
    for stage in workflow_stages(doc):
        events = stage.get("event_types") or ([stage.get("entry_event")] if stage.get("entry_event") else [])
        rows.append(
            {
                "stage": str(stage.get("name") or stage.get("id") or ""),
                "events": ", ".join(str(item) for item in events if item),
                "actions": ", ".join(str(item) for item in stage.get("automated_actions") or []),
                "manual_actions": ", ".join(str(item) for item in stage.get("manual_actions") or []),
                "next_stage": str(stage.get("next_stage") or stage.get("emits_event") or "완료"),
            }
        )
    return rows


def _registry_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value:
        return [str(value)]
    return []


def workflow_definition_summary_rows(definition: JsonDict, event_context: JsonDict | None = None) -> list[JsonDict]:
    if not isinstance(definition, dict) or not definition.get("workflow_definition_key"):
        return []
    event_context = event_context if isinstance(event_context, dict) else {}
    stage_display = definition.get("stage_display") if isinstance(definition.get("stage_display"), list) else []
    if stage_display:
        rows: list[JsonDict] = []
        entry_events = _registry_list(definition.get("entry_events"))
        emitted_events = _registry_list(definition.get("emitted_events"))
        actions = _registry_list(definition.get("action_refs"))
        manual = [item for item in actions if item.startswith("manual.")]
        automated = [item for item in actions if not item.startswith("manual.")]
        for index, stage in enumerate(stage_display):
            if not isinstance(stage, dict):
                continue
            rows.append(
                {
                    "stage": str(stage.get("label") or stage.get("stage_id") or f"단계 {index + 1}"),
                    "events": ", ".join(entry_events if index == 0 else emitted_events[:1]),
                    "actions": ", ".join(automated[:4]),
                    "manual_actions": ", ".join(manual[:3]),
                    "next_stage": str(stage.get("work_boi") or stage.get("evidence") or "업무 BoI 보강"),
                }
            )
        if rows:
            return rows
    entry_events = _registry_list(definition.get("entry_events"))
    emitted_events = _registry_list(definition.get("emitted_events"))
    actions = _registry_list(definition.get("action_refs"))
    event_actions = _registry_list(event_context.get("recommended_actions"))
    event_manual_actions = _registry_list(event_context.get("recommended_manual_actions"))
    for action_key in event_actions:
        if action_key not in actions:
            actions.append(action_key)
    for action_key in event_manual_actions:
        if action_key not in actions:
            actions.append(action_key)
    automated = [item for item in actions if not item.startswith("manual.")]
    manual = [item for item in actions if item.startswith("manual.")]
    stage = str(event_context.get("sop_stage_id") or definition.get("workflow_key") or definition.get("workflow_definition_key") or "")
    primary_event = str(event_context.get("event_type") or "")
    events = [primary_event] if primary_event else entry_events
    next_events = [item for item in emitted_events if item not in set(events)]
    return [
        {
            "stage": stage,
            "events": ", ".join(events or entry_events),
            "actions": ", ".join(automated),
            "manual_actions": ", ".join(manual),
            "next_stage": ", ".join(next_events[:4]) if next_events else "완료",
        }
    ]


def workflow_definition_mermaid(definition: JsonDict, event_context: JsonDict | None = None) -> str:
    rows = workflow_definition_summary_rows(definition, event_context)
    if not rows:
        return 'flowchart TD\n  current["현재 질문"] --> missing["Workflow 정의 연결 필요"]'
    row = rows[0]
    lines = ["flowchart TD"]
    lines.append(f'  e1["{mermaid_label(row.get("events") or "Event", 30)}"] --> s1["{mermaid_label(row.get("stage") or "SOP Stage", 30)}"]')
    actions = [item.strip() for item in str(row.get("actions") or "").split(",") if item.strip()]
    manuals = [item.strip() for item in str(row.get("manual_actions") or "").split(",") if item.strip()]
    next_events = [item.strip() for item in str(row.get("next_stage") or "").split(",") if item.strip() and item.strip() != "완료"]
    for index, action in enumerate(actions[:4], start=1):
        lines.append(f'  s1 --> a{index}["{mermaid_label(action, 30)}"]')
    for index, action in enumerate(manuals[:3], start=1):
        lines.append(f'  s1 --> m{index}["{mermaid_label(action, 30)}"]')
    for index, event_type in enumerate(next_events[:3], start=1):
        lines.append(f'  s1 --> ne{index}["{mermaid_label(event_type, 30)}"]')
    return "\n".join(lines)


def workflow_definition_links(definition: JsonDict, event_context: JsonDict | None = None) -> list[JsonDict]:
    if not isinstance(definition, dict):
        return []
    links: list[JsonDict] = []
    for sop_ref in _registry_list(definition.get("sop_refs"))[:3]:
        links.append({"label": sop_ref, "url": f"/docs/{sop_ref}", "kind": "sop"})
    event_context = event_context if isinstance(event_context, dict) else {}
    event_type = str(event_context.get("event_type") or "")
    if event_type:
        links.append({"label": event_type, "url": f"/event-types/{event_type}", "kind": "event_type"})
    for action_key in _registry_list(definition.get("action_refs"))[:5]:
        links.append({"label": action_key, "url": f"/actions/{action_key}", "kind": "action"})
    return links


def markdown_table(rows: list[JsonDict], columns: list[str]) -> str:
    if not rows:
        return "_No workflow mapping available._\n"
    labels = {
        "stage": "단계",
        "events": "이벤트",
        "actions": "Action",
        "manual_actions": "수동 조치",
        "next_stage": "다음",
    }
    header = "| " + " | ".join(labels.get(column, column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        values = []
        for column in columns:
            values.append(markdown_cell(str(row.get(column) or "-")))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body]) + "\n"


def markdown_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", "\\|")).strip() or "-"


def action_gap_rows(doc: JsonDict, specs: list[JsonDict]) -> list[JsonDict]:
    found: dict[str, JsonDict] = {}
    for spec in specs:
        item = spec.get("item") if isinstance(spec.get("item"), dict) else spec
        key = str((item or {}).get("action_key") or "")
        if key:
            found[key] = spec
    keys: list[str] = []
    for stage in workflow_stages(doc):
        for key in (stage.get("automated_actions") or []) + (stage.get("manual_actions") or []):
            if str(key) not in keys:
                keys.append(str(key))
    rows = []
    for key in keys:
        spec = found.get(key)
        doc_ref = str(((spec or {}).get("item") or spec or {}).get("doc_ref") or "")
        rows.append(
            {
                "action_key": key,
                "status_label": "명세 있음" if spec and doc_ref else "보강 필요",
                "evidence": doc_ref or "catalog/doc_ref 또는 executable spec 확인 필요",
            }
        )
    return rows or [{"action_key": "-", "status_label": "workflow action 없음", "evidence": "SOP workflow metadata 보강 필요"}]


ACTION_REQUIREMENT_QUESTION_TERMS = (
    "필요",
    "필수",
    "어떤 데이터",
    "무슨 데이터",
    "입력",
    "필드",
    "payload",
    "schema",
    "스키마",
    "근거",
    "확인",
    "결과",
    "출력",
    "contract",
)

ACTION_REQUIREMENT_STOP_TERMS = {
    "어떤",
    "무슨",
    "데이터",
    "필요",
    "필수",
    "위해",
    "위한",
    "알려줘",
    "보여줘",
    "정리해줘",
    "확인",
    "결과",
    "입력",
    "필드",
    "현재",
    "이",
    "그",
    "때",
    "시",
}


def action_spec_item(spec: JsonDict) -> JsonDict:
    if not isinstance(spec, dict):
        return {}
    item = spec.get("item") if isinstance(spec.get("item"), dict) else spec
    return item if isinstance(item, dict) else {}


def action_spec_doc_metadata(spec: JsonDict) -> JsonDict:
    doc = spec.get("doc") if isinstance(spec, dict) and isinstance(spec.get("doc"), dict) else {}
    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    return metadata


def action_spec_search_text(spec: JsonDict) -> str:
    item = action_spec_item(spec)
    metadata = action_spec_doc_metadata(spec)
    doc = spec.get("doc") if isinstance(spec, dict) and isinstance(spec.get("doc"), dict) else {}
    parts = [
        item.get("action_key"),
        item.get("name_ko"),
        item.get("description"),
        item.get("doc_ref"),
        metadata.get("title"),
        metadata.get("description"),
        metadata.get("action_key"),
        " ".join(str(field) for field in (metadata.get("tags") or []) if field),
        " ".join(str(field) for field in ((metadata.get("payload_contract") or {}).get("required") or []) if field),
        " ".join(str(field) for field in ((metadata.get("payload_contract") or {}).get("optional") or []) if field),
        " ".join(str(field) for field in ((metadata.get("result_contract") or {}).get("fields") or []) if field),
        " ".join(
            str(field)
            for requirement in (metadata.get("evidence_requirements") or [])
            if isinstance(requirement, dict)
            for field in (requirement.get("required_fields") or [])
            if field
        ),
        " ".join(
            str(requirement.get("evidence_key") or "")
            for requirement in (metadata.get("evidence_requirements") or [])
            if isinstance(requirement, dict)
        ),
        doc.get("body_excerpt"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def action_question_terms(question: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z0-9_:.가-힣]+", str(question or "").lower())
    terms: list[str] = []
    for raw in raw_terms:
        for term in re.split(r"[_:./-]+", raw):
            term = term.strip()
            if len(term) < 2 or term in ACTION_REQUIREMENT_STOP_TERMS:
                continue
            if term not in terms:
                terms.append(term)
    return terms


def is_action_requirement_question(question: str) -> bool:
    q = str(question or "").lower()
    return any(term in q for term in ACTION_REQUIREMENT_QUESTION_TERMS)


def action_spec_relevance_score(question: str, spec: JsonDict) -> int:
    item = action_spec_item(spec)
    text = action_spec_search_text(spec)
    action_key = str(item.get("action_key") or "").lower()
    if not text:
        return 0
    score = 0
    q = str(question or "").lower()
    if action_key and action_key in q:
        score += 120
    for term in action_question_terms(question):
        if term in text:
            score += 18 if term in {"trend", "트렌드", "response"} else 8
        if term and term in action_key:
            score += 14
    if "trend" in q and ("trend" in text or "트렌드" in text):
        score += 40
    if "품질" in q and "품질" in text:
        score += 14
    return score


def select_relevant_action_specs_for_question(question: str, specs: list[JsonDict]) -> list[JsonDict]:
    scored = [
        (action_spec_relevance_score(question, spec), spec)
        for spec in specs
        if isinstance(spec, dict)
    ]
    scored = [(score, spec) for score, spec in scored if score > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [spec for _, spec in scored[:3]]


def action_contract_rows(specs: list[JsonDict]) -> list[JsonDict]:
    rows: list[JsonDict] = []
    for spec in specs:
        item = action_spec_item(spec)
        metadata = action_spec_doc_metadata(spec)
        payload_contract = metadata.get("payload_contract") if isinstance(metadata.get("payload_contract"), dict) else {}
        result_contract = metadata.get("result_contract") if isinstance(metadata.get("result_contract"), dict) else {}
        required = payload_contract.get("required") if isinstance(payload_contract.get("required"), list) else []
        optional = payload_contract.get("optional") if isinstance(payload_contract.get("optional"), list) else []
        result_fields = result_contract.get("fields") if isinstance(result_contract.get("fields"), list) else []
        example_request = metadata.get("example_request") if isinstance(metadata.get("example_request"), dict) else {}
        example_payload = example_request.get("payload") if isinstance(example_request.get("payload"), dict) else {}
        evidence_requirements = metadata.get("evidence_requirements") if isinstance(metadata.get("evidence_requirements"), list) else []
        evidence_labels: list[str] = []
        evidence_fields: list[str] = []
        evidence_sources: list[str] = []
        simulated_policies: list[str] = []
        for requirement in evidence_requirements:
            if not isinstance(requirement, dict):
                continue
            evidence_key = str(requirement.get("evidence_key") or "").strip()
            if evidence_key:
                evidence_labels.append(evidence_key)
            source_action = str(requirement.get("source_action") or "").strip()
            if source_action:
                evidence_sources.append(source_action)
            for field in requirement.get("required_fields") or []:
                field = str(field or "").strip()
                if field and field not in evidence_fields:
                    evidence_fields.append(field)
            if requirement.get("simulated_allowed") is True:
                simulated_policies.append(f"{evidence_key or source_action}: simulated_prerequisite 허용")
        rows.append(
            {
                "Action": item.get("name_ko") or item.get("action_key") or metadata.get("title") or "-",
                "필수 입력": ", ".join(str(field) for field in required) or "명시 없음",
                "있으면 좋은 입력": ", ".join(str(field) for field in optional) or "명시 없음",
                "확인 결과": ", ".join(str(field) for field in result_fields) or "명시 없음",
                "필수 근거": ", ".join(evidence_labels) or "명시 없음",
                "근거 필드": ", ".join(evidence_fields) or "명시 없음",
                "근거 Source Action": ", ".join(evidence_sources) or "명시 없음",
                "시뮬레이션 정책": "; ".join(simulated_policies) or "명시 없음",
                "예시 입력": ", ".join(f"{key}={value}" for key, value in list(example_payload.items())[:4]) or "명시 없음",
            }
        )
    return rows


def action_spec_links(specs: list[JsonDict]) -> list[JsonDict]:
    links = []
    for spec in specs:
        item = action_spec_item(spec)
        metadata = action_spec_doc_metadata(spec)
        url = str(spec.get("url") or ((spec.get("doc") or {}).get("url") if isinstance(spec.get("doc"), dict) else "") or "")
        if not url:
            continue
        links.append(
            {
                "label": str(item.get("name_ko") or metadata.get("title") or item.get("action_key") or "Action Spec"),
                "url": url,
                "kind": "action_spec",
            }
        )
    return links


def action_requirement_followup_questions(primary: JsonDict, specs: list[JsonDict]) -> list[str]:
    item = action_spec_item(primary)
    metadata = action_spec_doc_metadata(primary)
    title = str(item.get("name_ko") or metadata.get("title") or item.get("action_key") or "이 Action")
    questions = [
        f"{title} 상세 내용을 보여줘",
        f"{title} 입력값을 체크리스트로 정리해줘",
        "이 결과를 다음 SOP 단계에서 어떻게 활용하는지 설명해줘",
    ]
    for spec in specs[1:]:
        related = action_spec_item(spec)
        related_title = str(related.get("name_ko") or related.get("action_key") or "").strip()
        if related_title:
            questions.append(f"{related_title}에 필요한 데이터도 알려줘")
            break
    deduped: list[str] = []
    for question in questions:
        question = question.strip()
        if question and question not in deduped:
            deduped.append(question)
    return deduped[:4]


def compose_action_requirement_answer(state: JsonDict) -> bool:
    question = str(state.get("question") or "")
    if not is_action_requirement_question(question):
        return False
    specs = (state.get("tool_results") or {}).get("action_specs") or []
    if not isinstance(specs, list) or not specs:
        return False
    relevant = select_relevant_action_specs_for_question(question, specs)
    if not relevant:
        return False
    primary_item = action_spec_item(relevant[0])
    primary_meta = action_spec_doc_metadata(relevant[0])
    title = str(primary_item.get("name_ko") or primary_meta.get("title") or primary_item.get("action_key") or "관련 Action")
    rows = action_contract_rows(relevant)
    first = rows[0] if rows else {}
    simulated_system = str(primary_meta.get("simulated_system") or primary_item.get("simulated_system") or "")
    real_status = str(primary_meta.get("real_system_status") or primary_item.get("real_system_status") or "")
    lines = [
        f"## {title}에 필요한 데이터",
        "",
        f"결론부터 말하면, 현재 SOP에서 이 질문은 `{primary_item.get('action_key') or primary_meta.get('action_key') or '-'}` Action의 Action Spec을 기준으로 봐야 합니다.",
        "",
        f"- 반드시 필요한 입력: {first.get('필수 입력') or '명시 없음'}",
        f"- 있으면 판단이 좋아지는 입력: {first.get('있으면 좋은 입력') or '명시 없음'}",
        f"- 확인 결과로 봐야 할 데이터: {first.get('확인 결과') or '명시 없음'}",
    ]
    if simulated_system or real_status:
        lines.append(
            f"- 운영 경계: 현재 `{simulated_system or '연결 시스템'}` 연결 상태는 `{real_status or 'unknown'}`이며, 실제 연결 전까지는 BoI Action Spec 근거의 시뮬레이션 evidence로 다룹니다."
        )
    lines.extend(
        [
            "",
            "아래 표에 관련 Action별 입력·출력 계약을 함께 정리했습니다. 실제 조치나 자동 실행은 별도 확인 카드와 권한 검사를 거쳐야 합니다.",
        ]
    )
    state["answer_markdown"] = "\n".join(lines)
    state["artifacts"] = [agent_artifact("action_requirements", title="필요 데이터와 결과 계약", data=rows)]
    state["links"] = action_spec_links(relevant) + links_from_search(state.get("search") or {})
    state["citations"] = state["links"][:6]
    state["suggested_questions"] = action_requirement_followup_questions(relevant[0], relevant)
    state["suggested_questions_source"] = "action_spec_affordance"
    state["authoritative_answer_contract"] = "action_requirements"
    return True


def links_from_search(search: JsonDict) -> list[JsonDict]:
    links = []
    for item in search.get("best_matches") or []:
        access = item.get("access") if isinstance(item.get("access"), dict) else {}
        if access.get("can_cite") is False:
            continue
        url = str(item.get("url") or "")
        if url:
            links.append({"label": item_label(item), "url": url, "kind": str(item.get("kind") or "search")})
    return links


def links_from_doc_and_search(doc: JsonDict, search: JsonDict) -> list[JsonDict]:
    links = []
    metadata = doc.get("metadata") if isinstance(doc, dict) else {}
    access = doc.get("access") if isinstance(doc.get("access"), dict) else {}
    if metadata and metadata.get("boi_id") and access.get("can_cite") is not False:
        links.append({"label": str(metadata.get("title") or metadata.get("boi_id")), "url": str(doc.get("url") or ""), "kind": "current_doc"})
    links.extend(links_from_search(search))
    return links


def trace_links(workflow: JsonDict, trace: JsonDict) -> list[JsonDict]:
    links = []
    for doc in (workflow.get("generated_docs") if isinstance(workflow, dict) else []) or []:
        url = str(doc.get("url") or "")
        if url:
            links.append({"label": str(doc.get("title") or doc.get("boi_id") or "Generated BoI"), "url": url, "kind": "generated_boi"})
    for row in (trace.get("actions") if isinstance(trace, dict) else []) or []:
        url = str(row.get("raw_url") or "")
        if url:
            links.append({"label": str(row.get("action_key") or row.get("request_id") or "Action Raw"), "url": url, "kind": "action_raw"})
    return links


def compact_ontology_context(search: JsonDict) -> JsonDict:
    if not isinstance(search, dict):
        return {}
    dictionary_terms = []
    for item in (search.get("used_dictionary_terms") or [])[:6]:
        if not isinstance(item, dict):
            continue
        dictionary_terms.append(
            {
                "term": item.get("term") or "",
                "aliases": _registry_list(item.get("aliases"))[:6],
                "related_terms": _registry_list(item.get("related_terms"))[:6],
                "maps_to_event_type": item.get("maps_to_event_type") or "",
                "maps_to_action_key": item.get("maps_to_action_key") or "",
                "maps_to_sop": item.get("maps_to_sop") or "",
            }
        )
    matches = []
    for item in (search.get("best_matches") or [])[:8]:
        if not isinstance(item, dict):
            continue
        matches.append(
            {
                "kind": item.get("kind") or "",
                "label": item_label(item),
                "url": item.get("url") or "",
                "event_type": item.get("event_type") or "",
                "action_key": item.get("action_key") or "",
                "workflow_definition_key": item.get("workflow_definition_key") or "",
                "sop_ref": item.get("sop_ref") or "",
            }
        )
    return {
        "query_expansion": _registry_list(search.get("query_expansion"))[:16],
        "used_dictionary_terms": dictionary_terms,
        "best_matches": matches,
    }


def compact_action_context(specs: Any) -> list[JsonDict]:
    if not isinstance(specs, list):
        return []
    items: list[JsonDict] = []
    for spec in specs[:12]:
        if not isinstance(spec, dict):
            continue
        item = action_spec_item(spec)
        metadata = action_spec_doc_metadata(spec)
        action_key = str(item.get("action_key") or metadata.get("action_key") or "").strip()
        if not action_key:
            continue
        result_contract = metadata.get("result_contract") if isinstance(metadata.get("result_contract"), dict) else {}
        items.append(
            {
                "action_key": action_key,
                "title": item.get("name_ko") or metadata.get("title") or action_key,
                "event_types": _registry_list(metadata.get("event_types") or item.get("event_types")),
                "connector_kind": item.get("connector_kind") or metadata.get("connector_kind") or "",
                "result_fields": _registry_list(result_contract.get("fields")),
                "simulation": bool(item.get("simulation") or metadata.get("simulation")),
            }
        )
    return items


def normalize_detail_map(value: Any) -> dict[str, JsonDict]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if isinstance(item, dict)}
    if isinstance(value, list):
        result: dict[str, JsonDict] = {}
        for item in value:
            if isinstance(item, dict) and item.get("action_key"):
                result[str(item.get("action_key"))] = item
        return result
    return {}


def workflow_manual_summary_rows(workflow: JsonDict) -> list[JsonDict]:
    manual_keys = [
        str(item)
        for item in (workflow.get("expected_manual_actions") or workflow.get("manual_handoffs") or [])
        if str(item or "").strip()
    ]
    details = normalize_detail_map(workflow.get("manual_action_details"))
    approval_rows = [
        row
        for row in (workflow.get("approval_required_actions") or [])
        if isinstance(row, dict)
    ]
    approval_keys = {str(row.get("action_key") or "") for row in approval_rows}
    rows: list[JsonDict] = []
    for index, action_key in enumerate(dict.fromkeys(manual_keys), start=1):
        detail = details.get(action_key, {})
        title = str(detail.get("name_ko") or detail.get("title") or action_key)
        source = "SOP/Workflow 정의"
        status_label = "조치 필요"
        if action_key in approval_keys:
            status_label = "승인 필요"
            source = "Workflow 실행 로그"
        if detail.get("missing"):
            status_label = "명세 확인 필요"
        rows.append(
            {
                "no": index,
                "title": title,
                "action_key": action_key,
                "status_label": status_label,
                "why_it_matters": manual_action_business_reason(action_key, detail),
                "required_evidence": manual_action_required_evidence(action_key, detail),
                "next_action": manual_action_next_step(action_key, detail),
                "source": source,
                "doc_ref": str(detail.get("doc_ref") or ""),
                "doc_uri": str(detail.get("doc_uri") or ""),
                "risk_label": "수동 조치",
            }
        )
    return rows


def manual_action_business_reason(action_key: str, detail: JsonDict) -> str:
    lowered = action_key.lower()
    if "confirm_alarm_context" in lowered:
        return "Alarm이 실제 이상 상황인지, 설비/공정/LOT 맥락과 맞는지 사람이 확인해야 합니다."
    if "review_root_cause" in lowered:
        return "자동 분석 결과만으로 원인을 확정하지 않고 담당자가 원인 후보와 근거를 검토해야 합니다."
    if "approve_process_hold" in lowered:
        return "공정 진행 금지는 영향이 크기 때문에 근거와 범위를 확인한 뒤 승인해야 합니다."
    if "approve_spec_rule_change" in lowered:
        return "스펙/룰 변경은 품질과 생산에 영향을 주므로 변경 사유와 예상 영향을 확인해야 합니다."
    if "confirm_maintenance_done" in lowered:
        return "보전 조치가 실제 완료됐는지 확인해야 다음 단계로 진행할 수 있습니다."
    if detail.get("approval_required"):
        return "승인 또는 담당자 판단이 필요한 Action입니다."
    return "자동 처리만으로 완료할 수 없어 담당자 확인과 조치 기록이 필요합니다."


def manual_action_required_evidence(action_key: str, detail: JsonDict) -> str:
    lowered = action_key.lower()
    if "confirm_alarm_context" in lowered:
        return "Alarm 시각, 설비 ID, LOT/Recipe, 최근 Trend, 관련 이벤트"
    if "review_root_cause" in lowered:
        return "Trend 분석 결과, Raw Data, Map View, 설비 이력, 유사 사례"
    if "approve_process_hold" in lowered:
        return "원인 분석 요약, 영향 범위, Hold 대상, 해제 조건"
    if "approve_spec_rule_change" in lowered:
        return "변경 전후 기준, 품질 영향, 승인자 의견"
    if "confirm_maintenance_done" in lowered:
        return "보전 작업 결과, 재발 여부, 후속 확인 결과"
    if detail.get("doc_ref"):
        return "연결된 Action/Manual 명세의 입력 근거"
    return "SOP 단계 근거와 담당자 조치 메모"


def manual_action_next_step(action_key: str, detail: JsonDict) -> str:
    lowered = action_key.lower()
    if "confirm_alarm_context" in lowered:
        return "Alarm 맥락을 확인하고 실제 이상 여부를 조치 메모로 남기세요."
    if "review_root_cause" in lowered:
        return "자동 분석 근거를 확인한 뒤 원인 후보와 불확실성을 정리하세요."
    if "approve_process_hold" in lowered:
        return "Hold 필요 여부와 범위를 확인하고 승인/반려 판단을 남기세요."
    if "approve_spec_rule_change" in lowered:
        return "룰 변경 필요성과 품질 영향을 확인한 뒤 승인 여부를 결정하세요."
    if "confirm_maintenance_done" in lowered:
        return "보전 완료 증빙과 재가동 가능 여부를 확인하세요."
    if detail.get("missing"):
        return "먼저 이 manual action 명세를 보강하세요."
    return "필요 근거를 확인하고 담당자 조치 내용을 입력하세요."


def workflow_manual_followup_questions(rows: list[JsonDict]) -> list[str]:
    if not rows:
        return ["이 Workflow에서 예상되는 수동 조치 정의를 다시 확인해줘."]
    questions = [
        "가장 먼저 처리해야 할 수동 조치를 골라줘.",
        "각 조치에 필요한 근거 데이터를 체크리스트로 정리해줘.",
        "승인 필요한 항목만 따로 보여줘.",
    ]
    first_title = str(rows[0].get("title") or rows[0].get("action_key") or "").strip()
    if first_title:
        questions.insert(0, f"{first_title} 조치 메모 초안을 만들어줘.")
    deduped: list[str] = []
    for question in questions:
        if question and question not in deduped:
            deduped.append(question)
    return deduped[:4]


def conversation_mentions_no_manual_handoffs(request: JsonDict) -> bool:
    haystack = " ".join(
        str(item.get("content") or item.get("text") or "")
        for item in request.get("conversation") or []
        if isinstance(item, dict) and str(item.get("role") or "") == "assistant"
    )
    return "수동 조치" in haystack and any(term in haystack for term in ("없습니다", "없다", "없음", "0건"))


def goal_model_for_state(state: JsonDict) -> JsonDict:
    intent = str(state.get("intent") or "")
    page = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    return {
        "goal_type": response_profile_for_state(state),
        "intent": intent,
        "route": state.get("route_name") or "",
        "page_kind": page.get("page_kind") or "",
        "requires_mutation": intent in MUTATION_AGENT_INTENTS,
    }


def response_profile_for_state(state: JsonDict) -> str:
    intent = str(state.get("intent") or "")
    if intent in {"page_qa", "summarize"}:
        return "doc_summary" if (state.get("page_context") or {}).get("page_kind") == "doc" else "qa"
    if intent == "workflow_explain":
        return "event_to_action"
    if intent == "trace_reasoning":
        return "trace_reasoning"
    if intent in {"diagram", "gap_check"}:
        return "artifact_generation"
    if intent in MUTATION_AGENT_INTENTS:
        return "mutation_request"
    if intent == "search":
        return "search"
    return intent or "qa"


def suggested_questions_for_state(state: JsonDict) -> list[str]:
    intent = state.get("intent")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    current_doc = (state.get("tool_results") or {}).get("current_doc") or {}
    title = suggested_subject_title(state)
    stage_count, action_count, manual_count = suggested_workflow_counts(page_context, current_doc)
    if intent == "diagram":
        return [
            f"{title}의 Action {action_count}개와 수동 조치 {manual_count}개 중 부족한 명세를 점검해줘.",
            "이 Event가 발생하면 뭘 해야 해?",
        ]
    if intent == "gap_check":
        return ["누락된 Action 명세 초안을 만들어줘.", f"{title}를 Mermaid로 다시 보여줘."]
    if intent == "inbox":
        return ["가장 먼저 처리할 일을 알려줘.", "승인 대기 건만 보여줘."]
    if stage_count:
        return [
            f"{title}를 Mermaid 프로세스 플로우로 보여줘.",
            f"{title}의 이벤트, Action, 수동 조치 관계를 요약해줘.",
            "부족한 Action 명세가 있는지 찾아줘.",
        ]
    return ["이 내용을 Mermaid로 보여줘.", "관련 Action과 이벤트를 요약해줘.", "부족한 명세가 있는지 찾아줘."]


def suggested_subject_title(state: JsonDict) -> str:
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    doc_title_value = doc_title(current_doc or {}, "")
    if doc_title_value:
        return doc_title_value
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    page_title = str(page_context.get("title") or page_context.get("page_title") or "").strip()
    if page_title:
        return page_title
    search = state.get("search") if isinstance(state.get("search"), dict) else {}
    for item in search.get("best_matches") or []:
        if isinstance(item, dict) and str(item.get("kind") or "") in {"boi", "event_type", "action", "dictionary"}:
            label = item_label(item)
            if label and label != "결과":
                return label
    return "현재 문서"


def suggested_workflow_counts(page_context: JsonDict, current_doc: JsonDict) -> tuple[int, int, int]:
    stage_count = int(page_context.get("stage_count") or 0)
    action_count = int(page_context.get("workflow_action_count") or 0)
    manual_count = int(page_context.get("workflow_manual_action_count") or 0)
    if stage_count or action_count or manual_count:
        return stage_count, action_count, manual_count
    stages = workflow_stages(current_doc)
    automated: set[str] = set()
    manual: set[str] = set()
    for stage in stages:
        automated.update(str(item) for item in stage.get("automated_actions") or [] if item)
        manual.update(str(item) for item in stage.get("manual_actions") or [] if item)
    return len(stages), len(automated), len(manual)


def confirmation_payload_for_state(state: JsonDict) -> JsonDict:
    intent = str(state.get("intent") or "")
    route_name = str(state.get("route_name") or "")
    question = str(state.get("question") or "")
    if intent == "event_type_draft":
        payload = event_type_draft_payload_from_state(state)
        if payload:
            return {
                "title": "신규 Event Type 초안 확인",
                "answer_markdown": "신규 Event Type은 바로 운영 목록에 반영하지 않고 초안으로 만든 뒤 검증합니다. 아래 카드에서 이름, 남길 정보, 연결 SOP/Action 후보를 확인하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "event_type_draft",
                    "payload": payload,
                    "title": "신규 Event Type 초안 확인",
                    "message": "Event Type 초안을 만들고 검증 결과를 확인합니다. 운영 목록 반영은 별도 검토와 승인 후 진행됩니다.",
                    "primary_label": "이벤트 유형 초안 만들기",
                },
            }
        return {
            "title": "신규 Event Type 초안 확인",
            "answer_markdown": "Event Type 초안을 만들려면 `domain.event.requested.v1` 같은 versioned event_type 이름이 필요합니다.",
            "data": {
                "route": route_name,
                "intent": intent,
                "title": "Event Type 이름 필요",
                "message": "예: `quality.forecast.requested.v1` 신규 이벤트 유형 초안 만들어줘.",
                "primary_label": "이벤트 유형 이름을 포함해 다시 요청",
            },
        }
    if intent == "event_publish":
        payload = event_publish_payload_from_state(state)
        if payload:
            return {
                "title": "업무 이벤트 발행 확인",
                "answer_markdown": "업무 이벤트를 발행하려면 먼저 내용을 확인해야 합니다. 아래 카드에서 이벤트 유형과 입력값을 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "event_publish",
                    "payload": payload,
                    "title": "업무 이벤트 발행 확인",
                    "message": "이벤트 발행은 SOP 업무 흐름을 진행시키고 BoI 생성과 Action으로 이어질 수 있습니다.",
                    "primary_label": "이벤트 발행하기",
                },
            }
        return missing_execution_payload("이벤트 유형 필요", "예: `equipment.alarm.raised.v1` 이벤트를 발행해줘.", route_name, intent)
    if intent == "workflow_start":
        payload = workflow_start_payload_from_state(state)
        if payload:
            workflow_key = str(payload.get("workflow_key") or "")
            return {
                "title": "SOP 업무 흐름 시작 확인",
                "answer_markdown": "SOP 기반 업무 흐름을 시작하려면 먼저 시작 이벤트 입력값을 확인해야 합니다. 아래 카드에서 업무 흐름과 입력값을 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "workflow_start",
                    "payload": payload,
                    "title": "SOP 업무 흐름 시작 확인",
                    "message": f"`{workflow_key}` 업무 흐름의 시작 이벤트를 발행합니다.",
                    "primary_label": "업무 흐름 시작하기",
                },
            }
        return missing_execution_payload("업무 흐름 Key 필요", "예: `equipment-anomaly` workflow를 시작해줘.", route_name, intent)
    if intent == "action_invoke":
        payload = action_invoke_payload_from_state(state)
        if payload:
            action_key = str(payload.get("action_key") or "")
            return {
                "title": "Action 실행 확인",
                "answer_markdown": "Action은 허용 목록과 권한 검증을 거쳐 실행됩니다. 아래 카드에서 요청 종류와 입력값을 확인한 뒤 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": intent,
                    "operation": "action_invoke",
                    "payload": payload,
                    "title": "Action 실행 확인",
                    "message": f"`{action_key}` Action을 실행합니다.",
                    "primary_label": "Action 실행",
                },
            }
        return missing_execution_payload("Action Key 필요", "예: `sop.equipment.request_raw_data` action을 실행해줘.", route_name, intent)
    if route_name == "approval_required":
        payload = action_invoke_payload_from_state(state)
        if payload:
            action_key = str(payload.get("action_key") or "")
            return {
                "title": "Action 실행 확인",
                "answer_markdown": "Action은 Agent가 바로 실행하지 않습니다. 아래 카드에서 요청 종류와 입력값을 확인한 뒤 명시적으로 실행하세요.",
                "data": {
                    "route": route_name,
                    "intent": "action_invoke",
                    "operation": "action_invoke",
                    "payload": payload,
                    "title": "Action 실행 확인",
                    "message": f"`{action_key}` Action을 실행하기 전 확인이 필요합니다.",
                    "primary_label": "Action 실행",
                },
            }
    return {
        "title": "확인 필요",
        "answer_markdown": "이 요청은 상태 변경 또는 승인 절차가 필요합니다. Agent가 바로 실행하지 않고 확인 카드와 승인 API를 통해 처리해야 합니다.",
        "data": {
            "route": route_name,
            "intent": intent,
            "message": "명시 승인 후에만 실행할 수 있습니다.",
        },
    }


def missing_execution_payload(title: str, message: str, route_name: str, intent: str) -> JsonDict:
    return {
        "title": title,
        "answer_markdown": "실행 요청을 만들려면 필수 식별자가 필요합니다. Agent가 임의로 추정해 실행하지 않습니다.",
        "data": {
            "route": route_name,
            "intent": intent,
            "title": title,
            "message": message,
            "primary_label": "필수 정보를 추가해 다시 요청",
        },
    }


def event_type_from_text(value: str) -> str:
    match = re.search(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\.v\d+)\b", str(value or ""))
    return match.group(1) if match else ""


def looks_like_unregistered_event_workflow_request(value: str) -> bool:
    text = str(value or "")
    lowered = text.lower()
    if event_type_from_text(text) or action_key_from_text(text):
        return False
    event_terms = ("event", "이벤트", "업무 발생", "알람", "alarm", "drift", "overlay")
    request_terms = ("자동 처리", "처리해", "처리해줘", "보정", "등록", "연결", "만들", "생성", "초안")
    return any(term in lowered or term in text for term in event_terms) and any(term in lowered or term in text for term in request_terms)


def event_type_candidate_from_question(value: str) -> str:
    text = str(value or "")
    lowered = text.lower()
    tokens: list[str] = []
    if "euv" in lowered or "노광" in text:
        tokens.append("euv")
    if "overlay" in lowered:
        tokens.append("overlay")
    if "drift" in lowered:
        tokens.append("drift")
    if "alarm" in lowered or "알람" in text:
        tokens.append("alarm")
    if "보정" in text or "correct" in lowered:
        tokens.append("correction")
    if "처리" in text or "요청" in text or "request" in lowered:
        tokens.append("requested")
    if not tokens:
        tokens = ["custom", "business_event", "requested"]
    if tokens[-1] != "requested":
        tokens.append("requested")
    deduped: list[str] = []
    for token in tokens:
        token = re.sub(r"[^a-z0-9_]+", "_", token.lower()).strip("_")
        if token and token not in deduped:
            deduped.append(token)
    return ".".join((deduped or ["custom", "business_event", "requested"])[:5]) + ".v1"


def action_key_from_text(value: str) -> str:
    candidates = re.findall(r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,})\b", str(value or ""))
    for candidate in candidates:
        if not re.search(r"\.v\d+$", candidate):
            return candidate
    return ""


def execution_source_refs(state: JsonDict) -> list[JsonDict]:
    current_url = str(state.get("current_url") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    refs: list[JsonDict] = []
    if page_context.get("boi_id"):
        refs.append({"type": "boi", "ref": str(page_context.get("boi_id"))})
    if page_context.get("sop_ref"):
        refs.append({"type": "sop", "ref": str(page_context.get("sop_ref"))})
    if current_url:
        refs.append({"type": "boi-agent-page", "ref": current_url})
    return refs


def event_publish_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    event_type = event_type_from_text(question) or str(page_context.get("event_type") or "")
    if not event_type:
        return {}
    return {
        "event_type": event_type,
        "payload": {
            "title": compact_text(question, 100) or event_type,
            "summary": compact_text(question, 400),
        },
        "source_refs": execution_source_refs(state),
        "trace_id": str(page_context.get("trace_id") or "") or None,
    }


def workflow_start_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    workflow_key = str(page_context.get("workflow_key") or "")
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    metadata = current_doc.get("metadata") if isinstance(current_doc.get("metadata"), dict) else {}
    workflow = metadata.get("workflow") if isinstance(metadata.get("workflow"), dict) else {}
    workflow_key = workflow_key or str(workflow.get("workflow_key") or "")
    if not workflow_key:
        match = re.search(r"`?([a-z][a-z0-9_-]*(?:-[a-z0-9_]+)+)`?\s*(?:workflow|워크플로우)", question, flags=re.IGNORECASE)
        workflow_key = match.group(1) if match else ""
    if not workflow_key:
        return {}
    return {
        "workflow_key": workflow_key,
        "payload": {
            "title": compact_text(question, 100) or workflow_key,
            "summary": compact_text(question, 400),
            "workflow": workflow_key,
        },
        "source_refs": execution_source_refs(state),
    }


def action_invoke_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    action_key = action_key_from_text(question) or str(page_context.get("action_key") or "")
    if not action_key:
        return {}
    event_type = event_type_from_text(question) or str(page_context.get("event_type") or "")
    return {
        "action_key": action_key,
        "event": {
            "event_type": event_type,
            "trace_id": str(page_context.get("trace_id") or ""),
            "payload": {"title": compact_text(question, 100), "summary": compact_text(question, 400)},
            "source_refs": execution_source_refs(state),
        },
        "payload": {"title": compact_text(question, 100), "summary": compact_text(question, 400)},
    }


def event_type_draft_payload_from_state(state: JsonDict) -> JsonDict:
    question = str(state.get("question") or "")
    event_type = event_type_from_text(question) or event_type_candidate_from_question(question)
    if not event_type:
        return {}
    search = state.get("search") if isinstance(state.get("search"), dict) else {}
    page_context = state.get("page_context") if isinstance(state.get("page_context"), dict) else {}
    tool_results = state.get("tool_results") if isinstance(state.get("tool_results"), dict) else {}
    sop_ref = event_type_draft_sop_ref(page_context, tool_results, search)
    related_event = event_type_draft_related_event(search)
    workflow_stage = event_type_draft_workflow_stage(question, related_event)
    action_keys = event_type_draft_recommended_actions(question, search)
    return {
        "event_type": event_type,
        "name_ko": event_type_draft_name(question, event_type),
        "description": compact_text(question, 260),
        "owner": "",
        "topic": event_type_draft_topic(event_type, related_event),
        "workflow_stage": workflow_stage,
        "sop_ref": sop_ref,
        "payload_schema": event_type_draft_payload_schema(question),
        "recommended_actions": action_keys,
    }


def event_type_draft_name(question: str, event_type: str) -> str:
    before = question.split(event_type, 1)[0]
    before = re.sub(
        r"(신규|새로운|event type|이벤트 타입|이벤트 유형|이벤트|유형|초안|만들어줘|만들|생성|정의|추가|자동|처리해줘|처리|연결해줘|등록해줘)",
        " ",
        before,
        flags=re.IGNORECASE,
    )
    before = before.strip(" .,:;/-")
    before = re.sub(r"(?<=\s)(을|를|은|는|이|가|의|에|으로|로)(?=\s|$)", " ", before)
    before = re.sub(r"\s+(을|를|은|는|이|가|의|에|으로|로)\s*$", " ", before)
    before = re.sub(r"\s+", " ", before).strip(" .,:;/-")
    korean_chunks = re.findall(r"[가-힣A-Za-z0-9·\-/ ]+", before)
    name = " ".join(chunk.strip() for chunk in korean_chunks if chunk.strip()).strip()
    if name:
        return compact_text(name, 60)
    parts = event_type.rsplit(".v", 1)[0].split(".")
    return " ".join(part.replace("_", " ").title() for part in parts[-2:])


def event_type_draft_topic(event_type: str, related_event: JsonDict | None = None) -> str:
    if isinstance(related_event, dict) and related_event.get("topic"):
        return str(related_event.get("topic"))
    parts = event_type.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else parts[0]


def event_type_draft_payload_schema(question: str) -> JsonDict:
    properties: JsonDict = {
        "title": {"type": "string", "description": "업무 화면에 표시할 이벤트 제목"},
        "summary": {"type": "string", "description": "이벤트 발생 맥락 요약"},
    }
    if re.search(r"사번|담당|owner|작업자", question, re.IGNORECASE):
        properties["owner_employee_id"] = {"type": "string", "pattern": "^\\d{7}$", "description": "담당자 7자리 사번"}
    if re.search(r"설비|장비|equipment", question, re.IGNORECASE):
        properties["equipment_id"] = {"type": "string", "description": "대상 설비 또는 장비 ID"}
    return {"type": "object", "properties": properties, "required": ["title"]}


def event_type_draft_sop_ref(page_context: JsonDict, tool_results: JsonDict, search: JsonDict) -> str:
    for value in (page_context.get("sop_ref"),):
        if value:
            return str(value)
    current_doc = tool_results.get("current_doc") if isinstance(tool_results.get("current_doc"), dict) else {}
    metadata = current_doc.get("metadata") if isinstance(current_doc.get("metadata"), dict) else {}
    if metadata.get("type") == "boi/sop" and metadata.get("boi_id"):
        return str(metadata.get("boi_id"))
    if page_context.get("page_kind") == "doc" and page_context.get("boi_id") and "sop" in str(page_context.get("boi_id")):
        return str(page_context.get("boi_id"))
    knowledge = search.get("knowledge_panel") if isinstance(search.get("knowledge_panel"), dict) else {}
    for item in knowledge.get("top_sop") or []:
        if isinstance(item, dict) and item.get("boi_id"):
            return str(item.get("boi_id"))
    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    for item in groups.get("sop") or []:
        if isinstance(item, dict) and item.get("boi_id"):
            return str(item.get("boi_id"))
    for item in search.get("best_matches") or []:
        if isinstance(item, dict) and item.get("type") == "boi/sop" and item.get("boi_id"):
            return str(item.get("boi_id"))
    return ""


def event_type_draft_related_event(search: JsonDict) -> JsonDict | None:
    knowledge = search.get("knowledge_panel") if isinstance(search.get("knowledge_panel"), dict) else {}
    for item in knowledge.get("top_event_type") or []:
        if isinstance(item, dict):
            return item
    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    for item in groups.get("event_types") or []:
        if isinstance(item, dict):
            return item
    return None


def event_type_draft_workflow_stage(question: str, related_event: JsonDict | None = None) -> str:
    stage_terms = ("이상 감지", "원인 분석", "보전 가이드", "이상 조치", "Map View 확인", "단면검사", "결과 확인")
    for term in stage_terms:
        if term in question:
            return term
    if isinstance(related_event, dict) and related_event.get("workflow_stage"):
        return str(related_event.get("workflow_stage"))
    if re.search(r"완료|completed|조치", question, re.IGNORECASE):
        return "이상 조치"
    if re.search(r"요청|requested|분석", question, re.IGNORECASE):
        return "원인 분석"
    return ""


def event_type_draft_recommended_actions(question: str, search: JsonDict) -> list[str]:
    """Return high-confidence action suggestions for a new Event Type draft.

    Ontology search often returns SOP-near actions that are useful for reading
    context but too broad for a brand new event contract. For event type drafts,
    irrelevant actions are worse than no suggestion because they can steer the
    catalog toward an unsafe workflow. Keep only candidates that match explicit
    user intent or a narrow domain hint.
    """
    normalized_question = question.lower()
    direct_hints: list[tuple[str, tuple[str, ...]]] = [
        ("mcp.timesfm.forecast", ("timesfm", "forecast", "예측", "시계열")),
        ("boi.materialize_event", ("boi 기록", "boi 생성", "문서화", "materialize")),
        ("sop.equipment.request_maintenance_guide", ("보전 가이드", "정비 가이드", "maintenance guide", "guide")),
    ]
    action_keys: list[str] = []
    for action_key, hints in direct_hints:
        if any(hint.lower() in normalized_question for hint in hints):
            action_keys.append(action_key)

    groups = search.get("groups") if isinstance(search.get("groups"), dict) else {}
    candidates = list(groups.get("actions") or []) + list(search.get("best_matches") or [])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        action_key = str(item.get("action_key") or "")
        if not action_key or action_key in action_keys:
            continue
        if not event_type_draft_action_matches_question(action_key, item, normalized_question):
            continue
        if action_key not in action_keys:
            action_keys.append(action_key)
        if len(action_keys) >= 3:
            break
    return action_keys


def event_type_draft_action_matches_question(action_key: str, item: JsonDict, normalized_question: str) -> bool:
    text = " ".join(
        str(item.get(field) or "")
        for field in (
            "label",
            "title",
            "name",
            "description",
            "summary",
            "wiki_usage",
            "doc_ref",
            "connector_kind",
        )
    ).lower()
    combined = f"{action_key.lower()} {text}"

    if action_key.lower() in normalized_question:
        return True
    if "direct_development" in action_key.lower() and not re.search(r"direct_development|직개발|직접 개발|직접개발", normalized_question):
        return False
    if "stage_analysis" in action_key.lower() and not re.search(r"stage analysis|단계 분석|stage 분석|원인 분석|분석 요청", normalized_question):
        return False
    if re.search(r"spec|rule|규격|룰|규칙", combined) and not re.search(r"spec|rule|규격|룰|규칙|변경", normalized_question):
        return False
    if re.search(r"approve|approval|승인", combined) and not re.search(r"approve|approval|승인|공유|배포|게시|hold|보류", normalized_question):
        return False
    if "timesfm" in combined or "forecast" in combined or "예측" in combined:
        return bool(re.search(r"timesfm|forecast|예측|시계열", normalized_question))
    if "maintenance_guide" in action_key or "보전 가이드" in combined or "정비 가이드" in combined:
        return bool(re.search(r"보전 가이드|정비 가이드|maintenance guide|guide", normalized_question))

    return False
