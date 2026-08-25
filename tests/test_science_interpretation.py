from __future__ import annotations

import json
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.anchors import SpanAnchorError, resolve_anchor
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
)
from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.llm import (
    LLMClaimCandidate,
    ScienceInterpretationPayload,
    ScienceInterpretationUnavailable,
    ScienceLLMClient,
    ScienceLLMConfig,
    ScienceLLMResult,
)
from boi_api.app.science.models import (
    EvidenceLocator,
    InterpretationRecord,
    PrimaryVerdict,
    ReleaseSelection,
    ResolvedComponent,
    ResolvedRelease,
    ResolvedReleaseSet,
    ReviewedSourceURLProfile,
    SourceSpan,
    VerificationReport,
)
from boi_api.app.science.operational import _issue_operational_verification
from boi_api.app.science.rules import ReleasedRule, ResolvedRuleSet, VerificationRule
from boi_api.app.science.safety import (
    SciencePublicValidationError,
    closed_science_validation_error,
    validate_credential_free_https_url,
)
from boi_api.app.science.service import (
    ScienceConfirmationRequired,
    ScienceIdempotencyConflict,
    ScienceService,
    submitted_root_document_ref,
    submitted_revision_document_ref,
)
from boi_api.app.science.source_identity import (
    ReviewedSourceURLIdentity,
    _build_reviewed_source_url_profile,
    _issue_catalog_reviewed_source_url_identity,
    _issue_reviewed_source_url_identity,
    _open_reviewed_source_url_identity,
)
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
    ScienceRuntimeStore,
    ScienceTransactionPendingError,
)

SOURCE_DIGEST = sha256_digest("fixture-source-component")
EVIDENCE_DIGEST = sha256_digest("fixture-evidence-component")
KNOWLEDGE_DIGEST = sha256_digest("fixture-knowledge-component")
RULE_DIGEST = sha256_digest("fixture-rule-component")
RPM_BINDING_DIGEST = sha256_digest("fixture-rpm-binding")
RELATION_BINDING_DIGEST = sha256_digest("fixture-increases-binding")
THICKNESS_BINDING_DIGEST = sha256_digest("fixture-thickness-binding")


def _span(text: str, exact: str, *, context: int = 4) -> SourceSpan:
    start = text.index(exact)
    end = start + len(exact)
    return SourceSpan(
        start=start,
        end=end,
        exact=exact,
        prefix=text[max(0, start - context) : start],
        suffix=text[end : end + context],
    )


def test_anchor_uses_unicode_code_points_and_accepts_exact_context():
    text = "웨이퍼😀에서 RPM을 높이면 두께가 증가한다."
    anchor = _span(text, "RPM을 높이면 두께가 증가한다")

    resolved = resolve_anchor(text, anchor, document_digest=sha256_digest(text))

    assert resolved.start == 7
    assert resolved.end == 24
    assert text[resolved.start : resolved.end] == resolved.exact


def test_anchor_recalculates_bad_offsets_only_when_context_match_is_unique():
    text = "서론. 웨이퍼에서 RPM은 두께를 바꾼다. 결론."
    actual = _span(text, "RPM은 두께를 바꾼다", context=5)
    stale_offsets = actual.model_copy(
        update={"start": actual.start - 2, "end": actual.end - 2}
    )

    resolved = resolve_anchor(
        text,
        stale_offsets,
        document_digest=sha256_digest(text),
    )

    assert (resolved.start, resolved.end) == (actual.start, actual.end)


_ZERO_MATCH_SPAN = _span(
    "웨이퍼에서 RPM을 높이면 두께가 증가한다.",
    "RPM을 높이면 두께가 증가한다",
    context=4,
)
_MULTIPLE_MATCH_SPAN = _span("A RPM 증가 Z / A RPM 증가 Z", "RPM 증가", context=2)
_MULTIPLE_MATCH_SPAN = _MULTIPLE_MATCH_SPAN.model_copy(
    update={
        "start": _MULTIPLE_MATCH_SPAN.start + 1,
        "end": _MULTIPLE_MATCH_SPAN.end + 1,
    }
)


@pytest.mark.parametrize(
    ("text", "span", "digest"),
    [
        (
            "웨이퍼에서 RPM을 낮추면 두께가 증가한다.",
            _ZERO_MATCH_SPAN,
            None,
        ),
        (
            "A RPM 증가 Z / A RPM 증가 Z",
            _MULTIPLE_MATCH_SPAN,
            None,
        ),
        (
            "웨이퍼에서 RPM을 높이면 두께가 증가한다.",
            _ZERO_MATCH_SPAN,
            "sha256:stale-document",
        ),
    ],
    ids=["zero-matches", "multiple-matches", "digest-mismatch"],
)
def test_anchor_fails_closed_for_stale_ambiguous_or_wrong_digest(
    text: str,
    span: SourceSpan,
    digest: str | None,
):
    with pytest.raises(SpanAnchorError, match="anchor mismatch"):
        resolve_anchor(text, span, document_digest=digest)


def _llm_content(*, extra: dict[str, object] | None = None) -> dict[str, object]:
    exact = "RPM 증가 시 두께 변화"
    claim: dict[str, object] = {
        "source_span": {
            "start": 0,
            "end": len(exact),
            "exact": exact,
            "prefix": "",
            "suffix": "",
        },
        "normalized_claim": {
            "subject_concept_id": "sci:concept:rpm",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [],
            "conditions": [],
            "process_stage": None,
            "material_state": None,
        },
        "ontology_refs": [
            "sci:binding:rpm",
            "sci:binding:increases",
            "sci:binding:film-thickness",
        ],
        "ambiguity_ids": ["ambiguity:spin-stage"],
        "candidate_meanings": [
            {
                "ambiguity_id": "ambiguity:spin-stage",
                "concept_role": "subject",
                "surface_term": "RPM",
                "ontology_ref": "sci:binding:rpm",
                "meaning": "final coat spin speed",
            },
            {
                "ambiguity_id": None,
                "concept_role": "relation",
                "surface_term": "증가",
                "ontology_ref": "sci:binding:increases",
                "meaning": "increases",
            },
            {
                "ambiguity_id": None,
                "concept_role": "object",
                "surface_term": "두께",
                "ontology_ref": "sci:binding:film-thickness",
                "meaning": "final dry film thickness",
            },
        ],
        "decision_impact": [
            {
                "ambiguity_id": "ambiguity:spin-stage",
                "changes_outcome": True,
                "reason": "The process stage changes rule applicability.",
            }
        ],
    }
    if extra:
        claim.update(extra)
    return {"claims": [claim]}


def _candidate_without_external_applicability() -> LLMClaimCandidate:
    return ScienceInterpretationPayload.model_validate(_llm_content()).claims[0]


def _user_candidate_with_applicability() -> LLMClaimCandidate:
    content = _llm_content()
    normalized = content["claims"][0]["normalized_claim"]
    normalized["process_stage"] = "final_spin"
    normalized["material_state"] = "liquid_film"
    return ScienceInterpretationPayload.model_validate(content).claims[0]


def _openai_response(content: object) -> httpx.Response:
    assistant_content = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(
        200,
        json={
            "id": "completion:fixture",
            "object": "chat.completion",
            "created": 1,
            "model": "fixture-model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": assistant_content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def test_llm_config_uses_science_overrides_then_boi_fallback_without_exposing_secrets():
    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1/",
            "BOI_LLM_BASE_URL": "https://fallback.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "science-model",
            "BOI_LLM_MODEL": "fallback-model",
            "BOI_LLM_API_KEY": "fallback-secret",
            "BOI_LLM_TEMPERATURE": "0.2",
            "BOI_SCIENCE_LLM_MAX_TOKENS": "512",
            "BOI_SCIENCE_LLM_CONTEXT_LENGTH": "100096",
            "BOI_LLM_TIMEOUT_SECONDS": "7.5",
        }
    )

    assert config.model_id == "science-model"
    assert config.safe_model_settings().model_dump() == {
        "temperature": 0.2,
        "top_p": None,
        "max_tokens": 512,
        "seed": None,
        "timeout_seconds": 7.5,
        "context_length": 100096,
    }
    assert "science-llm.test" not in repr(config)
    assert "fallback-secret" not in repr(config)
    assert config.safe_metadata() == {
        "model_id": "science-model",
        "model_settings": config.safe_model_settings().model_dump(),
    }


@pytest.mark.parametrize(
    "model_id",
    [
        "https://internal-llm.test:1236/v1",
        "internal-llm.test:1236/model",
        "internal-llm:1236/model",
        "user:password@model-host",
        "sk-secret-token-value",
        "Bearer-private-model-token",
    ],
)
def test_llm_config_rejects_endpoint_or_credential_shaped_model_ids(model_id: str):
    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": model_id,
            }
        )

    assert captured.value.__cause__ is None
    assert captured.value.diagnostic_code == "invalid_configuration"
    assert "science-llm.test" not in str(captured.value)
    assert model_id not in str(captured.value)


def test_llm_client_posts_strict_schema_and_returns_only_validated_interpretation():
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["url"] = str(request.url)
        seen_request["authorization"] = request.headers.get("authorization")
        seen_request["body"] = json.loads(request.content)
        return _openai_response(_llm_content())

    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            "BOI_SCIENCE_LLM_API_KEY": "secret-token",
            "BOI_SCIENCE_LLM_TEMPERATURE": "0",
        }
    )
    client = ScienceLLMClient(config, transport=httpx.MockTransport(handler))

    result = client.interpret(
        "RPM 증가 시 두께 변화",
        ontology_candidates=[
            {
                "ontology_ref": "sci:binding:rpm",
                "meaning": "final coat spin speed",
            }
        ],
    )

    assert seen_request["url"] == "https://science-llm.test/v1/chat/completions"
    assert seen_request["authorization"] == "Bearer secret-token"
    body = seen_request["body"]
    assert isinstance(body, dict)
    assert body["response_format"]["json_schema"]["strict"] is True
    transport_schema = body["response_format"]["json_schema"]["schema"]
    transport_schema_text = json.dumps(transport_schema, sort_keys=True)
    for unsupported_keyword in [
        '"pattern"',
        '"minLength"',
        '"minItems"',
        '"minimum"',
        '"exclusiveMinimum"',
        '"default"',
    ]:
        assert unsupported_keyword not in transport_schema_text
    assert body["temperature"] == 0.0
    assert result.payload.claims[0].ontology_refs == [
        "sci:binding:rpm",
        "sci:binding:increases",
        "sci:binding:film-thickness",
    ]
    assert result.response_digest.startswith("sha256:")
    assert "secret-token" not in repr(result)
    assert "science-llm.test" not in repr(result)


def test_llm_client_can_use_prompt_json_when_server_rejects_response_format():
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["body"] = json.loads(request.content)
        return _openai_response(_llm_content())

    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            "BOI_SCIENCE_LLM_RESPONSE_FORMAT_MODE": "prompt_json",
        }
    )
    result = ScienceLLMClient(config, transport=httpx.MockTransport(handler)).interpret(
        "RPM 증가 시 두께 변화", ontology_candidates=[]
    )

    assert config.response_format_mode == "prompt_json"
    assert "response_format" not in seen_request["body"]
    assert result.payload.claims[0].normalized_claim.predicate == "increases"


def test_llm_client_uses_lmstudio_native_reasoning_off_without_server_storage():
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["url"] = str(request.url)
        seen_request["authorization"] = request.headers.get("authorization")
        seen_request["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model_instance_id": "fixture-instance",
                "output": [
                    {
                        "type": "message",
                        "content": "```json\n"
                        + json.dumps(_llm_content(), ensure_ascii=False)
                        + "\n```",
                    }
                ],
                "stats": {
                    "input_tokens": 120,
                    "total_output_tokens": 80,
                    "reasoning_output_tokens": 0,
                },
            },
        )

    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "qwen/qwen3.8-27b",
            "BOI_SCIENCE_LLM_API_KEY": "secret-token",
            "BOI_SCIENCE_LLM_TRANSPORT_MODE": "lmstudio_native",
            "BOI_SCIENCE_LLM_RESPONSE_FORMAT_MODE": "prompt_json",
            "BOI_SCIENCE_LLM_REASONING_MODE": "disabled",
            "BOI_SCIENCE_LLM_CONTEXT_LENGTH": "100096",
            "BOI_SCIENCE_LLM_MAX_TOKENS": "4096",
            "BOI_SCIENCE_LLM_SEED": "42",
        }
    )

    result = ScienceLLMClient(
        config,
        transport=httpx.MockTransport(handler),
    ).interpret("RPM 증가 시 두께 변화", ontology_candidates=[])

    assert seen_request["url"] == "https://science-llm.test/api/v1/chat"
    assert seen_request["authorization"] == "Bearer secret-token"
    body = seen_request["body"]
    assert body["reasoning"] == "off"
    assert body["store"] is False
    assert body["context_length"] == 100096
    assert body["max_output_tokens"] == 4096
    assert "seed" not in body
    assert "response_format" not in body
    assert result.payload.claims[0].normalized_claim.predicate == "increases"


def test_llm_client_rejects_fenced_json_with_surrounding_prose():
    content = "Result follows.\n```json\n" + json.dumps(_llm_content()) + "\n```"
    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "fixture-model",
        }
    )
    client = ScienceLLMClient(
        config,
        transport=httpx.MockTransport(lambda _request: _openai_response(content)),
    )

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        client.interpret("RPM 증가 시 두께 변화", ontology_candidates=[])

    assert captured.value.diagnostic_code == "invalid_json"


def test_llm_client_can_disable_qwen_thinking_for_bounded_extraction() -> None:
    seen_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request["body"] = json.loads(request.content)
        return _openai_response(_llm_content())

    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "qwen/qwen3.8-27b",
            "BOI_SCIENCE_LLM_REASONING_MODE": "disabled",
        }
    )
    ScienceLLMClient(config, transport=httpx.MockTransport(handler)).interpret(
        "RPM 증가 시 두께 변화", ontology_candidates=[]
    )

    assert config.reasoning_mode == "disabled"
    user_message = seen_request["body"]["messages"][1]["content"]
    assert user_message.endswith("\n/no_think")


def test_llm_client_retries_only_invalid_candidate_and_accepts_valid_schema() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _openai_response("not-json" if calls == 1 else _llm_content())

    config = ScienceLLMConfig.from_env(
        {
            "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
            "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            "BOI_SCIENCE_LLM_MAX_ATTEMPTS": "2",
        }
    )
    result = ScienceLLMClient(config, transport=httpx.MockTransport(handler)).interpret(
        "RPM 증가 시 두께 변화", ontology_candidates=[]
    )

    assert config.max_attempts == 2
    assert calls == 2
    assert result.payload.claims[0].normalized_claim.predicate == "increases"


def test_llm_config_rejects_unknown_response_format_mode() -> None:
    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
                "BOI_SCIENCE_LLM_RESPONSE_FORMAT_MODE": "best_effort",
            }
        )

    assert captured.value.diagnostic_code == "invalid_configuration"


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        {**_llm_content(), "verdict": "VIOLATION"},
        _llm_content(extra={"evidence_id": "sci:evidence:invented"}),
        _llm_content(extra={"sourceLocator": {"page": 3}}),
    ],
    ids=["malformed-json", "verdict", "nested-evidence", "camelcase-locator"],
)
def test_llm_output_with_malformed_or_forbidden_fields_fails_closed(content: object):
    client = ScienceLLMClient(
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            }
        ),
        transport=httpx.MockTransport(lambda _request: _openai_response(content)),
    )

    with pytest.raises(ScienceInterpretationUnavailable):
        client.interpret("RPM 증가 시 두께 변화", ontology_candidates=[])


@pytest.mark.parametrize(
    "envelope",
    [[], {"choices": [7]}],
    ids=["non-object-envelope", "non-object-choice"],
)
def test_llm_malformed_openai_envelope_also_fails_closed(envelope: object):
    client = ScienceLLMClient(
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            }
        ),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=envelope)
        ),
    )

    with pytest.raises(ScienceInterpretationUnavailable):
        client.interpret("RPM 증가 시 두께 변화", ontology_candidates=[])


def test_llm_transport_failure_exposes_only_a_sanitized_diagnostic_code():
    client = ScienceLLMClient(
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://private-host.test:1236/v1",
                "BOI_SCIENCE_LLM_MODEL": "qwen/qwen3.8-27b",
            }
        ),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, text="Bearer private-token")
        ),
    )

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        client.interpret("RPM 증가 시 두께 변화", ontology_candidates=[])

    assert captured.value.diagnostic_code == "http_status_503"
    assert captured.value.__cause__ is None
    rendered = repr(captured.value) + str(captured.value)
    assert "private-host" not in rendered
    assert "private-token" not in rendered


class _StaticLLM:
    def __init__(self, content: dict[str, object]):
        self.result = ScienceLLMResult(
            payload=ScienceInterpretationPayload.model_validate(content),
            response_digest="sha256:" + "a" * 64,
        )
        self.config = ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://must-not-persist.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
                "BOI_SCIENCE_LLM_API_KEY": "must-not-persist-secret",
                "BOI_SCIENCE_LLM_TEMPERATURE": "0",
            }
        )
        self.ontology_candidates: list[dict[str, object]] | None = None
        self.calls = 0

    def interpret(self, document_text: str, *, ontology_candidates):
        self.calls += 1
        self.ontology_candidates = list(ontology_candidates)
        return self.result


class _RecordingStore:
    def __init__(self):
        self.interpretations = {}
        self.reports = {}
        self.interpretation_identity = None
        self.report_identity = None

    def save_interpretation(self, record, *, identity):
        self.interpretations[record.interpretation_id] = record
        self.interpretation_identity = identity
        return record

    def load_interpretation(self, interpretation_id):
        return self.interpretations[interpretation_id]

    def save_report(self, report, *, identity):
        self.reports[report.report_id] = report
        self.report_identity = identity
        return report

    def load_report(self, report_id):
        return self.reports[report_id]


def _release_and_rules(*, release_id: str = "sci-release:foundation-0.1"):
    rule = VerificationRule.model_validate(
        {
            "rule_id": "sci:rule:spin-direction",
            "rule_kind": "directional_relation",
            "subject_concept_id": "sci:concept:rpm",
            "object_concept_id": "sci:concept:film-thickness",
            "relation_kind": "monotonic_direction",
            "expected_predicate": "decreases",
            "contradiction_predicates": ["increases"],
            "knowledge_refs": ["sci:knowledge:spin-direction"],
            "evidence_refs": ["sci:evidence:spin-direction"],
            "evidence_uses": [
                {
                    "evidence_ref": "sci:evidence:spin-direction",
                    "claim_family": "process.spin_coating.direction",
                    "purpose": "directional_verification",
                }
            ],
            "corrected_claim": "동일 조건에서는 RPM을 높이면 막 두께가 감소한다.",
        }
    )
    semantic_digest = sha256_digest(rule)
    components = tuple(
        ResolvedComponent(
            ref=ref,
            kind=kind,
            declared_digest=digest,
            actual_digest=digest,
            semantic_digest=semantic_digest if kind == "rule" else None,
        )
        for ref, kind, digest in [
            ("sci:source:spin-paper", "source", SOURCE_DIGEST),
            ("sci:evidence:spin-direction", "evidence", EVIDENCE_DIGEST),
            ("sci:knowledge:spin-direction", "knowledge", KNOWLEDGE_DIGEST),
            ("sci:rule:spin-direction", "rule", RULE_DIGEST),
        ]
    )
    release = ResolvedRelease(
        release_id=release_id,
        schema_version="sci-profile/0.1",
        content_hash=sha256_digest(release_id),
        status="active",
        components=components,
        component_digests={item.ref: item.actual_digest for item in components},
        known_limitations=["fixture-only"],
    )
    release_set = ResolvedReleaseSet.from_single_foundation(release)
    rule_set = ResolvedRuleSet(
        release_set_digest=release_set.combined_digest,
        rules=(
            ReleasedRule(
                rule=rule,
                component_digest=RULE_DIGEST,
                semantic_digest=semantic_digest,
            ),
        ),
    )
    return release, release_set, rule_set


class _Catalog:
    def __init__(self):
        self.boi_root = Path("/fixture/boi")
        self.release, self.release_set, self.rule_set = _release_and_rules()
        self.resolve_release_calls = 0
        self.resolve_operational_calls = 0
        self.resolve_legacy_calls = 0
        self.operational_override = None
        self.knowledge_statement = (
            "동일한 레지스트와 공정 조건에서 final spin 속도가 증가하면 "
            "최종 막 두께는 감소한다."
        )
        self.evidence_digest = EVIDENCE_DIGEST
        self.evidence_original_text_hash = sha256_digest(
            "Increasing angular speed decreases film thickness."
        )
        self.source_url = "https://example.test/spin-paper"
        self.evidence_locator = {"section": "3.2", "equation": "7"}
        self._review_current_source_identity()
        self.bindings = {
            "sci:binding:rpm": SimpleNamespace(
                object_id="sci:binding:rpm",
                digest=RPM_BINDING_DIGEST,
                ontology_release_id="sci:ontology:0.1",
                concept_id="sci:concept:rpm",
                aliases=["RPM", "회전 속도"],
                meaning="final coat spin speed",
                domain="lithography",
            ),
            "sci:binding:film-thickness": SimpleNamespace(
                object_id="sci:binding:film-thickness",
                digest=THICKNESS_BINDING_DIGEST,
                ontology_release_id="sci:ontology:0.1",
                concept_id="sci:concept:film-thickness",
                aliases=["두께", "막 두께"],
                meaning="final dry film thickness",
                domain="lithography",
            ),
            "sci:binding:increases": SimpleNamespace(
                object_id="sci:binding:increases",
                digest=RELATION_BINDING_DIGEST,
                ontology_release_id="sci:ontology:0.1",
                concept_id="increases",
                aliases=["증가", "높이면"],
                meaning="increases",
                domain="general-science",
            ),
        }

    def resolve_release_set(self, selection):
        self.resolve_release_calls += 1
        return self.release_set

    def resolve_operational_rule_set(self, release_set):
        self.resolve_operational_calls += 1
        assert release_set == self.release_set
        if self.operational_override is not None:
            return self.operational_override
        return _issue_operational_verification(release_set, self.rule_set, [])

    def _review_current_source_identity(self):
        self._reviewed_source_url = self.source_url
        self._reviewed_evidence_locator = json.loads(json.dumps(self.evidence_locator))

    def _active_reviewed_source_url_profile(self, release_set, evidence_id):
        assert release_set == self.release_set
        if (
            evidence_id != "sci:evidence:spin-direction"
            or self.source_url != self._reviewed_source_url
            or self.evidence_locator != self._reviewed_evidence_locator
        ):
            raise ScienceOperationalError(
                "reviewed Source URL identity does not match the fixture release"
            )
        try:
            locator = EvidenceLocator.model_validate(self._reviewed_evidence_locator)
            profile = _build_reviewed_source_url_profile(
                qualification_state="active",
                release_set_digest=release_set.combined_digest,
                source_id="sci:source:spin-paper",
                source_digest=SOURCE_DIGEST,
                evidence_id=evidence_id,
                evidence_digest=EVIDENCE_DIGEST,
                canonical_source_url=self._reviewed_source_url,
                locator=locator,
            )
        except ValueError:
            raise ScienceOperationalError(
                "reviewed Source URL identity failed closed fixture validation"
            ) from None
        return profile

    def resolve_reviewed_source_url_identity(self, release_set, evidence_id):
        # The production issuer accepts only the exact ScienceCatalog type. This
        # narrow patch lets the application service fake exercise the same live
        # revalidation behavior without publishing a test issuer in production.
        with patch(
            "boi_api.app.science.source_identity._is_exact_science_catalog",
            return_value=True,
        ):
            return _issue_catalog_reviewed_source_url_identity(
                self,
                release_set,
                evidence_id,
            )

    def resolve_rule_set(self, release_set):
        self.resolve_legacy_calls += 1
        raise AssertionError("legacy rule-set resolver must not be used")

    def ontology_binding(self, binding_id):
        try:
            return self.bindings[binding_id]
        except KeyError as exc:
            raise ScienceCatalogError(
                f"unknown ontology binding: {binding_id}"
            ) from exc

    def knowledge(self, knowledge_id):
        assert knowledge_id == "sci:knowledge:spin-direction"
        return SimpleNamespace(
            object_id=knowledge_id,
            digest=KNOWLEDGE_DIGEST,
            statement=self.knowledge_statement,
            evidence_refs=["sci:evidence:spin-direction"],
        )

    def rule(self, rule_id):
        assert rule_id == "sci:rule:spin-direction"
        payload = self.rule_set.rules[0].rule.model_dump(mode="python")
        return SimpleNamespace(
            object_id=rule_id,
            digest=RULE_DIGEST,
            **payload,
        )

    def evidence(self, evidence_id):
        assert evidence_id == "sci:evidence:spin-direction"
        original_text = "Increasing angular speed decreases film thickness."
        return SimpleNamespace(
            object_id=evidence_id,
            digest=self.evidence_digest,
            source_id="sci:source:spin-paper",
            locator=self.evidence_locator,
            original_text=original_text,
            original_text_hash=self.evidence_original_text_hash,
            reviewed_translation="회전 속도가 증가하면 막 두께가 감소한다.",
        )

    def source(self, source_id):
        assert source_id == "sci:source:spin-paper"
        return SimpleNamespace(
            object_id=source_id,
            digest=SOURCE_DIGEST,
            original_url=self.source_url,
            boi_id="boi:public:science:source:spin-paper",
            visibility="public",
            classification="internal",
            acl_policy="acl:public",
            path=self.boi_root / "public/science/sources/spin-paper.md",
        )

    def validate_verification_report_authority(self, report):
        if (
            report.release_selection != self.release_set.selection
            or report.release_digests != self.release_set.release_digests
        ):
            raise ScienceOperationalError("report release is not fixture-authoritative")
        for annotation in report.annotations:
            knowledge = self.knowledge(annotation.knowledge_id)
            if (
                annotation.knowledge_digest != knowledge.digest
                or annotation.text != knowledge.statement
            ):
                raise ScienceOperationalError(
                    "report Knowledge is not fixture-authoritative"
                )
            for link in annotation.evidence_links:
                expected = self._active_reviewed_source_url_profile(
                    self.release_set,
                    link.evidence_id,
                )
                if link.reviewed_source != expected:
                    raise ScienceOperationalError(
                        "report Source profile is not fixture-authoritative"
                    )
                evidence = self.evidence(link.evidence_id)
                source = self.source(link.source_id)
                if (
                    link.evidence_digest != evidence.digest
                    or link.source_digest != source.digest
                    or link.original_text_hash != evidence.original_text_hash
                    or link.quote_hash != evidence.original_text_hash
                    or link.url != source.original_url
                    or link.locator.model_dump(mode="json", exclude_none=True)
                    != evidence.locator
                ):
                    raise ScienceOperationalError(
                        "report Evidence is not fixture-authoritative"
                    )


@pytest.fixture
def science_identity() -> AuthIdentity:
    return AuthIdentity(
        employee_id="100002",
        display_name="Science Pilot",
        roles=["boi.viewer", "science.power_user:lithography"],
    )


def _service(content: dict[str, object] | None = None):
    catalog = _Catalog()
    store = _RecordingStore()
    llm = _StaticLLM(content or _llm_content())
    service = ScienceService(
        catalog=catalog,
        runtime_store=store,
        llm_client=llm,
        dictionary_release_id="sci:dictionary:0.1",
        ontology_release_id="sci:ontology:0.1",
        ontology_binding_ids=[
            "sci:binding:rpm",
            "sci:binding:increases",
            "sci:binding:film-thickness",
        ],
        document_access_check=lambda _identity, _document_ref: True,
        clock=lambda: datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )
    return service, catalog, store, llm


def _real_service(tmp_path: Path, content: dict[str, object] | None = None):
    catalog = _Catalog()
    store = ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=lambda _identity: ["science.admin"],
        report_authority_validator=catalog.validate_verification_report_authority,
    )
    llm = _StaticLLM(content or _llm_content())
    service = ScienceService(
        catalog=catalog,
        runtime_store=store,
        llm_client=llm,
        dictionary_release_id="sci:dictionary:0.1",
        ontology_release_id="sci:ontology:0.1",
        ontology_binding_ids=[
            "sci:binding:rpm",
            "sci:binding:increases",
            "sci:binding:film-thickness",
        ],
        document_access_check=lambda _identity, _document_ref: True,
        clock=lambda: datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )
    return service, catalog, store, llm


def _audit_actions(store: ScienceRuntimeStore) -> list[str]:
    rows = [
        json.loads(line)
        for line in (store.root / "audit.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    return [str(row["action"]) for row in rows]


INTERPRET_KEY = "science-request:interpret-fixture"
CONFIRM_KEY = "science-request:confirm-fixture"
REPORT_KEY = "science-request:report-fixture"


def _confirmed_interpretation(
    service: ScienceService,
    identity: AuthIdentity,
):
    proposal = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=identity,
        idempotency_key=INTERPRET_KEY,
    )
    revision = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=identity,
        client_kind="user",
        candidate=_user_candidate_with_applicability(),
        supersedes_claim_id=proposal.candidate_claims[0].claim_id,
        idempotency_key="science-request:user-applicability-fixture",
    )
    return service.confirm_interpretation(
        revision.interpretation_id,
        claim_ids=[revision.candidate_claims[0].claim_id],
        identity=identity,
        idempotency_key=CONFIRM_KEY,
    )


def test_interpret_document_persists_identity_bound_safe_metadata_and_catalog_meanings(
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _service()

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    assert store.interpretation_identity is science_identity
    assert store.interpretations[record.interpretation_id] == record
    assert record.model_id == "fixture-model"
    assert record.model_settings.temperature == 0
    assert record.response_digest == "sha256:" + "a" * 64
    assert record.dictionary_release_id == "sci:dictionary:0.1"
    assert record.ontology_release_id == "sci:ontology:0.1"
    assert record.candidate_claims[0].interpretation.ambiguity_ids == [
        "ambiguity:spin-stage"
    ]
    assert record.candidate_claims[0].interpretation.user_confirmed is False
    assert record.candidate_claims[0].interpretation.ontology_refs == [
        "sci:binding:film-thickness",
        "sci:binding:increases",
        "sci:binding:rpm",
    ]
    assert record.confirmed_claim_packet_digest is None
    assert record.candidate_meanings[0].meaning == "final coat spin speed"
    assert record.candidate_meanings[0].binding_digest == RPM_BINDING_DIGEST
    assert llm.ontology_candidates is not None
    persisted = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert "must-not-persist" not in persisted
    assert "The process stage changes rule applicability" not in persisted


def test_interpret_document_sends_only_exact_alias_matched_ontology_candidates(
    science_identity: AuthIdentity,
):
    service, catalog, _store, llm = _service()
    catalog.bindings["sci:binding:viscosity"] = SimpleNamespace(
        object_id="sci:binding:viscosity",
        digest=sha256_digest("fixture-viscosity-binding"),
        ontology_release_id="sci:ontology:0.1",
        concept_id="sci:concept:viscosity",
        aliases=["점도", "viscosity"],
        meaning="dynamic viscosity",
        domain="general-science",
    )
    service.ontology_binding_ids = (
        *service.ontology_binding_ids,
        "sci:binding:viscosity",
    )

    service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key="science-request:matched-ontology-candidates",
    )

    assert llm.ontology_candidates is not None
    assert {item["ontology_ref"] for item in llm.ontology_candidates} == {
        "sci:binding:rpm",
        "sci:binding:increases",
        "sci:binding:film-thickness",
    }


def test_interpret_document_accepts_non_overlapping_roles_in_natural_text_order(
    science_identity: AuthIdentity,
):
    document = "두께는 RPM을 높이면 증가한다."
    content = _llm_content()
    claim = content["claims"][0]
    claim["source_span"] = {
        "start": 0,
        "end": len(document),
        "exact": document,
        "prefix": "",
        "suffix": "",
    }
    claim["candidate_meanings"] = [
        {
            "ambiguity_id": "ambiguity:spin-stage",
            "concept_role": "subject",
            "surface_term": "RPM",
            "ontology_ref": "sci:binding:rpm",
            "meaning": "final coat spin speed",
        },
        {
            "ambiguity_id": None,
            "concept_role": "relation",
            "surface_term": "높이면",
            "ontology_ref": "sci:binding:increases",
            "meaning": "increases",
        },
        {
            "ambiguity_id": None,
            "concept_role": "object",
            "surface_term": "두께",
            "ontology_ref": "sci:binding:film-thickness",
            "meaning": "final dry film thickness",
        },
    ]
    service, _catalog, _store, _llm = _service(content)

    record = service.interpret_document(
        document,
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key="science-request:natural-role-order",
    )

    assert record.decision_impact[0].issue_codes == ["USER_CONFIRMATION_REQUIRED"]
    assert record.decision_impact[0].status == "requires_user_confirmation"
    assert record.candidate_claims[0].interpretation.ontology_refs == [
        "sci:binding:film-thickness",
        "sci:binding:increases",
        "sci:binding:rpm",
    ]


def test_interpret_document_reanchors_a_selection_to_full_document_offsets(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    document = "검토 전 문장. RPM 증가 시 두께 변화. 검토 후 문장."
    selection = _span(document, "RPM 증가 시 두께 변화", context=4)

    record = service.interpret_document(
        document,
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        selection_anchor=selection,
        idempotency_key=INTERPRET_KEY,
    )

    claim_span = record.candidate_claims[0].source_span
    assert claim_span.start == document.index("RPM 증가")
    assert document[claim_span.start : claim_span.end] == "RPM 증가 시 두께 변화"
    assert record.document_digest == sha256_digest(document)


def test_interpret_document_uses_catalog_meaning_not_llm_meaning_prose(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["candidate_meanings"][0]["meaning"] = (
        "LLM-authored meaning must not become ontology truth"
    )
    service, _catalog, _store, _llm = _service(content)

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    assert record.candidate_meanings[0].meaning == "final coat spin speed"


def test_detect_aliases_returns_exact_catalog_matches_without_a_verdict(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    document = "검토: RPM 증가 시 막 두께 변화"

    result = service.detect_aliases(
        document,
        document_ref="boi:public:science:document:fixture",
    )

    payload = result.model_dump(mode="json")
    assert payload["document_digest"] == sha256_digest(document)
    assert [
        (
            item["surface_term"],
            item["start"],
            item["end"],
            item["ontology_ref"],
        )
        for item in payload["matches"]
    ] == [
        ("RPM", 4, 7, "sci:binding:rpm"),
        ("증가", 8, 10, "sci:binding:increases"),
        ("막 두께", 13, 17, "sci:binding:film-thickness"),
        ("두께", 15, 17, "sci:binding:film-thickness"),
    ]
    assert all(
        match["binding_id"] == match["ontology_ref"]
        and match["binding_digest"].startswith("sha256:")
        and match["meaning"]
        and match["domain"]
        for match in payload["matches"]
    )
    assert "verdict" not in json.dumps(payload).lower()


def test_detect_aliases_requires_ascii_token_boundaries_but_keeps_standalone_r(
    science_identity: AuthIdentity,
):
    """A substring matcher must not interpret the R inside RPM as resistance."""

    service, catalog, _store, _llm = _service()
    catalog.bindings["sci:binding:resistance"] = SimpleNamespace(
        object_id="sci:binding:resistance",
        digest=sha256_digest("fixture-resistance-binding"),
        ontology_release_id="sci:ontology:0.1",
        concept_id="sci:concept:resistance",
        aliases=["R"],
        meaning="electrical resistance",
        domain="circuits",
    )
    service.ontology_binding_ids = sorted(catalog.bindings)
    document = "RPM은 회전 속도이고, R은 저항이다."

    result = service.detect_aliases(
        document,
        document_ref="boi:public:science:document:fixture",
    )

    resistance_matches = [
        match
        for match in result.matches
        if match.ontology_ref == "sci:binding:resistance"
    ]
    assert [
        (match.surface_term, match.start, match.end) for match in resistance_matches
    ] == [("R", document.index(", R") + 2, document.index(", R") + 3)]


def test_external_claim_submission_reuses_server_validation_and_never_calls_llm(
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _service()
    candidate = _candidate_without_external_applicability()

    record = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:codex-submit-fixture",
    )

    assert llm.calls == 0
    assert store.interpretations[record.interpretation_id] == record
    assert record.submission_client_kind == "codex"
    assert record.model_id == "claim-client/codex"
    assert record.prompt_version == "science-claim-submission/0.1.0"
    assert record.operation_binding.operation == "submit_claim_candidate"
    assert record.decision_impact[0].issue_codes == ["USER_CONFIRMATION_REQUIRED"]
    assert record.candidate_claims[0].interpretation.user_confirmed is False


def test_agent_stage_and_state_remain_blocked_even_with_outcome_ambiguity(
    science_identity: AuthIdentity,
):
    """An Agent cannot make applicability context trusted by self-labeling impact."""

    content = _llm_content()
    content["claims"][0]["normalized_claim"]["process_stage"] = "final_spin"
    content["claims"][0]["normalized_claim"]["material_state"] = "liquid_film"
    assert content["claims"][0]["decision_impact"][0]["changes_outcome"] is True
    candidate = ScienceInterpretationPayload.model_validate(content).claims[0]
    service, _catalog, _store, _llm = _service()

    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:agent-stage-state",
    )

    assert submitted.decision_impact[0].status == "blocked_semantic_mismatch"
    assert "EXTERNAL_CONTEXT_REQUIRES_USER_REVISION" in (
        submitted.decision_impact[0].issue_codes
    )
    with pytest.raises(ScienceConfirmationRequired):
        service.confirm_interpretation(
            submitted.interpretation_id,
            claim_ids=[submitted.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:agent-stage-state-confirm",
        )


def test_agent_supplied_condition_cannot_directly_produce_a_verdict_or_report(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["normalized_claim"]["conditions"] = [
        {"condition_id": "spin_time", "value": 60, "unit": "second"}
    ]
    candidate = ScienceInterpretationPayload.model_validate(content).claims[0]
    service, _catalog, _store, _llm = _service()
    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:unconfirmed-agent-condition",
    )
    claim_id = submitted.candidate_claims[0].claim_id
    selection = ReleaseSelection(foundation="sci-release:foundation-0.1")

    assert submitted.decision_impact[0].status == "blocked_semantic_mismatch"
    assert "EXTERNAL_CONTEXT_REQUIRES_USER_REVISION" in (
        submitted.decision_impact[0].issue_codes
    )
    with pytest.raises(ScienceConfirmationRequired):
        service.confirm_interpretation(
            submitted.interpretation_id,
            claim_ids=[claim_id],
            identity=science_identity,
            idempotency_key="science-request:agent-context-confirm",
        )
    with pytest.raises(ScienceConfirmationRequired):
        service.verify_claim(
            submitted.interpretation_id,
            claim_id,
            selection,
            identity=science_identity,
        )
    with pytest.raises(ScienceConfirmationRequired):
        service.verify_document(
            submitted.interpretation_id,
            selection,
            identity=science_identity,
            idempotency_key="science-request:unconfirmed-condition-report",
        )


def test_different_user_cannot_confirm_or_verify_another_users_interpretation(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    other = AuthIdentity(
        employee_id="100003",
        display_name="Other Science User",
        roles=["science.user", "boi.viewer"],
    )
    candidate = _candidate_without_external_applicability()
    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:owner-submit",
    )
    claim_id = submitted.candidate_claims[0].claim_id

    with pytest.raises(ScienceAuthorizationError, match="interpretation owner"):
        service.confirm_interpretation(
            submitted.interpretation_id,
            claim_ids=[claim_id],
            identity=other,
            idempotency_key="science-request:other-confirm",
        )

    confirmed = service.confirm_interpretation(
        submitted.interpretation_id,
        claim_ids=[claim_id],
        identity=science_identity,
        idempotency_key="science-request:owner-confirm",
    )
    selection = ReleaseSelection(foundation="sci-release:foundation-0.1")
    with pytest.raises(ScienceAuthorizationError, match="interpretation owner"):
        service.verify_claim(
            confirmed.interpretation_id,
            claim_id,
            selection,
            identity=other,
        )
    with pytest.raises(ScienceAuthorizationError, match="interpretation owner"):
        service.verify_document(
            confirmed.interpretation_id,
            selection,
            identity=other,
            idempotency_key="science-request:other-report",
        )


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        (
            lambda candidate: candidate["ontology_refs"].append(
                "sci:binding:does-not-exist"
            ),
            "UNKNOWN_ONTOLOGY_REF",
        ),
        (
            lambda candidate: candidate["candidate_meanings"][0].update(
                {"surface_term": "문서에 없는 RPM 별칭"}
            ),
            "COMPLETE_RELATION_SPAN_REQUIRED",
        ),
    ],
    ids=["unknown-ontology-ref", "alias-absent-from-document"],
)
def test_external_claim_submission_blocks_untrusted_semantic_mismatches(
    science_identity: AuthIdentity,
    mutation,
    expected_issue: str,
):
    content = _llm_content()
    mutation(content["claims"][0])
    candidate = ScienceInterpretationPayload.model_validate(content).claims[0]
    service, _catalog, _store, _llm = _service()

    record = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="claude",
        candidate=candidate,
        idempotency_key=f"science-request:blocked-{expected_issue}",
    )

    impact = record.decision_impact[0]
    assert impact.status == "blocked_semantic_mismatch"
    assert expected_issue in impact.issue_codes
    with pytest.raises(ScienceConfirmationRequired):
        service.confirm_interpretation(
            record.interpretation_id,
            claim_ids=[record.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key=f"science-request:blocked-confirm-{expected_issue}",
        )


def test_external_claim_submission_rejects_overlapping_role_spans(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    claim = content["claims"][0]
    claim["candidate_meanings"][1]["surface_term"] = "RPM 증가"
    candidate = ScienceInterpretationPayload.model_validate(content).claims[0]
    service, catalog, _store, _llm = _service()
    catalog.bindings["sci:binding:increases"].aliases.append("RPM 증가")

    record = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="other",
        candidate=candidate,
        idempotency_key="science-request:overlapping-role-spans",
    )

    assert record.decision_impact[0].status == "blocked_semantic_mismatch"
    assert "COMPLETE_RELATION_SPAN_REQUIRED" in (record.decision_impact[0].issue_codes)


def test_external_claim_submission_allows_non_overlapping_roles_in_natural_text_order(
    science_identity: AuthIdentity,
):
    exact = "두께를 높이려면 RPM을 높여야 한다"
    content = _llm_content()
    claim = content["claims"][0]
    claim["source_span"] = {
        "start": 0,
        "end": len(exact),
        "exact": exact,
        "prefix": "",
        "suffix": "",
    }
    claim["candidate_meanings"] = [
        {
            "ambiguity_id": "ambiguity:spin-stage",
            "concept_role": "subject",
            "surface_term": "RPM",
            "ontology_ref": "sci:binding:rpm",
            "meaning": "untrusted",
        },
        {
            "ambiguity_id": None,
            "concept_role": "relation",
            "surface_term": "높여야 한다",
            "ontology_ref": "sci:binding:increases",
            "meaning": "untrusted",
        },
        {
            "ambiguity_id": None,
            "concept_role": "object",
            "surface_term": "두께",
            "ontology_ref": "sci:binding:film-thickness",
            "meaning": "untrusted",
        },
    ]
    candidate = ScienceInterpretationPayload.model_validate(content).claims[0]
    service, catalog, _store, _llm = _service()
    catalog.bindings["sci:binding:increases"].aliases.append("높여야 한다")

    record = service.submit_claim_candidate(
        exact,
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="user",
        candidate=candidate,
        idempotency_key="science-request:natural-role-order",
    )

    assert record.decision_impact[0].status == "requires_user_confirmation"
    assert record.decision_impact[0].issue_codes == ["USER_CONFIRMATION_REQUIRED"]


def test_manual_correction_is_an_immutable_resubmission(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    blocked_content = _llm_content()
    blocked_content["claims"][0]["candidate_meanings"][0]["surface_term"] = (
        "문서에 없는 회전 속도"
    )
    blocked_candidate = ScienceInterpretationPayload.model_validate(
        blocked_content
    ).claims[0]
    original = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=blocked_candidate,
        idempotency_key="science-request:correction-original",
    )

    corrected_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content()
    ).claims[0]

    corrected = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="user",
        candidate=corrected_candidate,
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        idempotency_key="science-request:correction-user",
    )

    assert corrected.interpretation_id != original.interpretation_id
    assert corrected.supersedes_claim_id == original.candidate_claims[0].claim_id
    assert original.decision_impact[0].status == "blocked_semantic_mismatch"
    assert corrected.decision_impact[0].status == "requires_user_confirmation"
    assert store.interpretations[original.interpretation_id] == original


def test_root_submitted_claim_rejects_non_deterministic_destination(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    document = "RPM 증가 시 두께 변화"

    with pytest.raises(ScienceConfirmationRequired, match="actor/digest bound"):
        service.submit_claim_candidate(
            document,
            document_ref="boi:submitted:forged-or-derived-destination",
            identity=science_identity,
            client_kind="user",
            candidate=ScienceInterpretationPayload.model_validate(
                _llm_content()
            ).claims[0],
            idempotency_key="science-request:root-submitted-forged",
        )


def test_raw_submitted_document_revision_accepts_verified_server_lineage(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    original_text = "RPM 증가 시 두께 변화"
    document_ref = submitted_root_document_ref(
        actor_id=science_identity.employee_id,
        initial_document_digest=sha256_digest(original_text),
    )
    original_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content()
    ).claims[0]
    original = service.submit_claim_candidate(
        original_text,
        document_ref=document_ref,
        identity=science_identity,
        client_kind="user",
        candidate=original_candidate,
        idempotency_key="science-request:raw-lineage-original",
    )
    original_claim = original.candidate_claims[0]
    revised_text = f"검토: {original_text}"
    revised_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content(
            extra={
                "source_span": {
                    "start": len("검토: "),
                    "end": len(revised_text),
                    "exact": original_text,
                    "prefix": "검토: ",
                    "suffix": "",
                }
            }
        )
    ).claims[0]

    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=document_ref,
        identity=science_identity,
        client_kind="user",
        candidate=revised_candidate,
        supersedes_claim_id=original_claim.claim_id,
        source_lineage_document_ref=document_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:raw-lineage-revised",
    )

    revised_claim = revised.candidate_claims[0]
    assert revised.supersedes_claim_id == original_claim.claim_id
    assert revised_claim.claim_id != original_claim.claim_id
    assert revised_claim.document_ref == original_claim.document_ref == document_ref
    assert revised.document_digest == sha256_digest(revised_text)
    assert revised.document_digest != original.document_digest
    assert revised.canonical_source_document_ref is None
    assert revised.canonical_source_document_digest is None
    assert store.interpretations[original.interpretation_id] == original

    service._document_access_check = lambda _identity, _document_ref: False
    confirmed = service.confirm_interpretation(
        revised.interpretation_id,
        claim_ids=[revised_claim.claim_id],
        identity=science_identity,
        idempotency_key="science-request:raw-lineage-confirm-owner-only",
    )
    assert confirmed.candidate_claims[0].interpretation.user_confirmed is True


def test_wiki_document_local_revision_transitions_to_verified_submitted_lineage(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    original_text = "RPM 증가 시 두께 변화"
    source_ref = "boi:public:science:document:fixture"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-lineage-original",
    )
    revised_text = f"검토: {original_text}"
    revised_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content(
            extra={
                "source_span": {
                    "start": len("검토: "),
                    "end": len(revised_text),
                    "exact": original_text,
                    "prefix": "검토: ",
                    "suffix": "",
                }
            }
        )
    ).claims[0]
    submitted_ref = (
        "boi:submitted:feb519c18bd0f77b9e26c4bdb0cd85e18f53471f2bf80634c82b733d98fd3030"
    )

    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=revised_candidate,
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-lineage-revised",
    )

    assert revised.supersedes_claim_id == original.candidate_claims[0].claim_id
    assert revised.candidate_claims[0].claim_id != original.candidate_claims[0].claim_id
    assert revised.candidate_claims[0].document_ref == submitted_ref
    assert revised.candidate_claims[0].document_ref != source_ref
    assert revised.document_digest == sha256_digest(revised_text)
    assert store.interpretations[original.interpretation_id] == original


def test_wiki_revision_rechecks_canonical_acl_before_accepting_revision(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-acl-revision-original",
    )
    revised_text = f"검토: {original_text}"
    submitted_ref = submitted_revision_document_ref(
        actor_id=science_identity.employee_id,
        source_document_ref=source_ref,
        source_document_digest=original.document_digest,
    )
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=submitted_ref,
            identity=science_identity,
            client_kind="user",
            candidate=ScienceInterpretationPayload.model_validate(
                _llm_content(
                    extra={
                        "source_span": _span(revised_text, original_text).model_dump()
                    }
                )
            ).claims[0],
            supersedes_claim_id=original.candidate_claims[0].claim_id,
            source_lineage_document_ref=source_ref,
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:wiki-acl-revision-revoked",
        )


def test_wiki_revision_persists_and_propagates_canonical_acl_lineage(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-acl-propagation-original",
    )
    submitted_ref = submitted_revision_document_ref(
        actor_id=science_identity.employee_id,
        source_document_ref=source_ref,
        source_document_digest=original.document_digest,
    )
    first_text = f"검토: {original_text}"
    first = service.submit_claim_candidate(
        first_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(first_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-acl-propagation-first",
    )
    second_text = f"재검토: {original_text}"
    second = service.submit_claim_candidate(
        second_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(second_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=first.candidate_claims[0].claim_id,
        source_lineage_document_ref=submitted_ref,
        source_lineage_document_digest=first.document_digest,
        idempotency_key="science-request:wiki-acl-propagation-second",
    )

    assert first.canonical_source_document_ref == source_ref
    assert first.canonical_source_document_digest == original.document_digest
    assert second.canonical_source_document_ref == source_ref
    assert second.canonical_source_document_digest == original.document_digest


def test_wiki_revision_rechecks_canonical_acl_before_confirm_and_verify(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-acl-confirm-original",
    )
    submitted_ref = submitted_revision_document_ref(
        actor_id=science_identity.employee_id,
        source_document_ref=source_ref,
        source_document_digest=original.document_digest,
    )
    revised_text = f"검토: {original_text}"
    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(revised_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-acl-confirm-revision",
    )
    claim_id = revised.candidate_claims[0].claim_id
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.confirm_interpretation(
            revised.interpretation_id,
            claim_ids=[claim_id],
            identity=science_identity,
            idempotency_key="science-request:wiki-acl-confirm-revoked",
        )

    service._document_access_check = lambda _identity, _document_ref: True
    confirmed = service.confirm_interpretation(
        revised.interpretation_id,
        claim_ids=[claim_id],
        identity=science_identity,
        idempotency_key="science-request:wiki-acl-confirm-allowed",
    )
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.verify_claim(
            confirmed.interpretation_id,
            claim_id,
            ReleaseSelection(foundation="sci-release:foundation-0.1"),
            identity=science_identity,
        )
    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation="sci-release:foundation-0.1"),
            identity=science_identity,
            idempotency_key="science-request:wiki-acl-report-revoked",
        )


def test_wiki_revision_legacy_lineage_is_traversed_and_forgery_fails_closed(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-acl-legacy-original",
    )
    submitted_ref = submitted_revision_document_ref(
        actor_id=science_identity.employee_id,
        source_document_ref=source_ref,
        source_document_digest=original.document_digest,
    )
    revised_text = f"검토: {original_text}"
    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(revised_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-acl-legacy-revision",
    )
    legacy = revised.model_copy(
        update={
            "canonical_source_document_ref": None,
            "canonical_source_document_digest": None,
        },
        deep=True,
    )
    store.interpretations[revised.interpretation_id] = legacy
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.confirm_interpretation(
            revised.interpretation_id,
            claim_ids=[revised.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:wiki-acl-legacy-confirm",
        )

    forged = revised.model_copy(
        update={
            "canonical_source_document_ref": "boi:public:science:document:other",
            "canonical_source_document_digest": sha256_digest("forged origin"),
        },
        deep=True,
    )
    store.interpretations[revised.interpretation_id] = forged
    service._document_access_check = lambda _identity, _document_ref: True

    with pytest.raises(ScienceAuthorizationError, match="source lineage"):
        service.confirm_interpretation(
            revised.interpretation_id,
            claim_ids=[revised.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:wiki-acl-forged-confirm",
        )


def test_wiki_revision_with_all_lineage_fields_stripped_fails_closed_in_memory(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-stripped-memory-original",
    )
    revised_text = f"검토: {original_text}"
    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_revision_document_ref(
            actor_id=science_identity.employee_id,
            source_document_ref=source_ref,
            source_document_digest=original.document_digest,
        ),
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(revised_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-stripped-memory-revision",
    )
    stripped = revised.model_copy(
        update={
            "supersedes_claim_id": None,
            "canonical_source_document_ref": None,
            "canonical_source_document_digest": None,
        },
        deep=True,
    )
    store.interpretations[revised.interpretation_id] = stripped
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="source lineage"):
        service.confirm_interpretation(
            revised.interpretation_id,
            claim_ids=[revised.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:wiki-stripped-memory-confirm",
        )


def test_wiki_revision_with_all_lineage_fields_stripped_fails_after_store_reopen(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-stripped-store-original",
    )
    revised_text = f"검토: {original_text}"
    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_revision_document_ref(
            actor_id=science_identity.employee_id,
            source_document_ref=source_ref,
            source_document_digest=original.document_digest,
        ),
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(revised_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-stripped-store-revision",
    )
    path = store.record_path("interpretations", revised.interpretation_id)
    payload = revised.model_dump(mode="json", exclude_none=False)
    payload.pop("supersedes_claim_id")
    payload.pop("canonical_source_document_ref")
    payload.pop("canonical_source_document_digest")
    stripped = InterpretationRecord.model_validate(payload)
    runtime_root = store.root
    store.close()
    path.write_bytes(canonical_json_bytes(stripped))
    path.chmod(0o600)

    reopened_store = ScienceRuntimeStore(
        runtime_root,
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=lambda _identity: ["science.admin"],
        report_authority_validator=catalog.validate_verification_report_authority,
    )
    reopened_service = ScienceService(
        catalog=catalog,
        runtime_store=reopened_store,
        llm_client=None,
        dictionary_release_id="sci:dictionary:0.1",
        ontology_release_id="sci:ontology:0.1",
        ontology_binding_ids=[
            "sci:binding:rpm",
            "sci:binding:increases",
            "sci:binding:film-thickness",
        ],
        document_access_check=lambda _identity, _document_ref: False,
        clock=lambda: datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )
    try:
        with pytest.raises(ScienceAuthorizationError, match="source lineage"):
            reopened_service.confirm_interpretation(
                revised.interpretation_id,
                claim_ids=[revised.candidate_claims[0].claim_id],
                identity=science_identity,
                idempotency_key="science-request:wiki-stripped-store-confirm",
            )
    finally:
        reopened_store.close()


def test_real_store_persists_wiki_revision_canonical_acl_lineage(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _real_service(tmp_path)
    source_ref = "boi:public:science:document:fixture"
    original_text = "RPM 증가 시 두께 변화"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-acl-store-original",
    )
    revised_text = f"검토: {original_text}"
    submitted_ref = submitted_revision_document_ref(
        actor_id=science_identity.employee_id,
        source_document_ref=source_ref,
        source_document_digest=original.document_digest,
    )
    revised = service.submit_claim_candidate(
        revised_text,
        document_ref=submitted_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(
            _llm_content(
                extra={"source_span": _span(revised_text, original_text).model_dump()}
            )
        ).claims[0],
        supersedes_claim_id=original.candidate_claims[0].claim_id,
        source_lineage_document_ref=source_ref,
        source_lineage_document_digest=original.document_digest,
        idempotency_key="science-request:wiki-acl-store-revision",
    )

    stored = store.load_interpretation(revised.interpretation_id)
    assert stored.canonical_source_document_ref == source_ref
    assert stored.canonical_source_document_digest == original.document_digest
    service._document_access_check = lambda _identity, _document_ref: False
    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.confirm_interpretation(
            stored.interpretation_id,
            claim_ids=[stored.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:wiki-acl-store-confirm-revoked",
        )


def test_wiki_document_revision_rejects_actor_ref_and_digest_attacks(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    original_text = "RPM 증가 시 두께 변화"
    source_ref = "boi:public:science:document:fixture"
    original = service.submit_claim_candidate(
        original_text,
        document_ref=source_ref,
        identity=science_identity,
        client_kind="user",
        candidate=ScienceInterpretationPayload.model_validate(_llm_content()).claims[0],
        idempotency_key="science-request:wiki-lineage-attack-original",
    )
    claim_id = original.candidate_claims[0].claim_id
    revised_text = f"검토: {original_text}"
    revised_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content(
            extra={
                "source_span": {
                    "start": len("검토: "),
                    "end": len(revised_text),
                    "exact": original_text,
                    "prefix": "검토: ",
                    "suffix": "",
                }
            }
        )
    ).claims[0]
    submitted_ref = (
        "boi:submitted:feb519c18bd0f77b9e26c4bdb0cd85e18f53471f2bf80634c82b733d98fd3030"
    )

    other = AuthIdentity(
        employee_id="100003",
        display_name="Other Science User",
        roles=["science.user", "boi.viewer"],
    )
    with pytest.raises(ScienceAuthorizationError, match="Claim owner"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=submitted_ref,
            identity=other,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=source_ref,
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:wiki-lineage-user-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="destination"):
        service.submit_claim_candidate(
            revised_text,
            document_ref="boi:submitted:forged-destination",
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=source_ref,
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:wiki-lineage-ref-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="lineage document"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=submitted_ref,
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref="boi:public:science:document:other",
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:wiki-lineage-source-ref-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="lineage digest"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=submitted_ref,
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=source_ref,
            source_lineage_document_digest=sha256_digest("forged predecessor"),
            idempotency_key="science-request:wiki-lineage-digest-attack",
        )


def test_raw_submitted_document_revision_rejects_ref_digest_and_document_attacks(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    original_text = "RPM 증가 시 두께 변화"
    document_ref = submitted_root_document_ref(
        actor_id=science_identity.employee_id,
        initial_document_digest=sha256_digest(original_text),
    )
    candidate = ScienceInterpretationPayload.model_validate(_llm_content()).claims[0]
    original = service.submit_claim_candidate(
        original_text,
        document_ref=document_ref,
        identity=science_identity,
        client_kind="user",
        candidate=candidate,
        idempotency_key="science-request:raw-lineage-attack-original",
    )
    claim_id = original.candidate_claims[0].claim_id
    revised_text = f"검토: {original_text}"
    revised_candidate = ScienceInterpretationPayload.model_validate(
        _llm_content(
            extra={
                "source_span": {
                    "start": len("검토: "),
                    "end": len(revised_text),
                    "exact": original_text,
                    "prefix": "검토: ",
                    "suffix": "",
                }
            }
        )
    ).claims[0]

    other = AuthIdentity(
        employee_id="100003",
        display_name="Other Science User",
        roles=["science.user", "boi.viewer"],
    )
    with pytest.raises(ScienceAuthorizationError, match="Claim owner"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=document_ref,
            identity=other,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=document_ref,
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:raw-lineage-user-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="lineage document"):
        service.submit_claim_candidate(
            revised_text,
            document_ref="boi:submitted:other-logical-document",
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref="boi:submitted:other-logical-document",
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:raw-lineage-ref-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="destination"):
        service.submit_claim_candidate(
            revised_text,
            document_ref="boi:submitted:forged-destination",
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=document_ref,
            source_lineage_document_digest=original.document_digest,
            idempotency_key="science-request:raw-lineage-destination-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="lineage digest"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=document_ref,
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            source_lineage_document_ref=document_ref,
            source_lineage_document_digest=sha256_digest("forged predecessor"),
            idempotency_key="science-request:raw-lineage-digest-attack",
        )

    with pytest.raises(ScienceConfirmationRequired, match="exact source document"):
        service.submit_claim_candidate(
            revised_text,
            document_ref=document_ref,
            identity=science_identity,
            client_kind="user",
            candidate=revised_candidate,
            supersedes_claim_id=claim_id,
            idempotency_key="science-request:raw-lineage-missing-contract",
        )


def test_manual_correction_rejects_dangling_cross_user_and_cross_document_lineage(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    candidate = ScienceInterpretationPayload.model_validate(_llm_content()).claims[0]
    original = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:lineage-original",
    )
    claim_id = original.candidate_claims[0].claim_id

    with pytest.raises(ScienceConfirmationRequired, match="provenance"):
        service.submit_claim_candidate(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            client_kind="user",
            candidate=candidate,
            supersedes_claim_id="sci-claim:does-not-exist",
            idempotency_key="science-request:lineage-dangling",
        )

    other = AuthIdentity(
        employee_id="100003",
        display_name="Other Science User",
        roles=["science.user", "boi.viewer"],
    )
    with pytest.raises(ScienceAuthorizationError, match="Claim owner"):
        service.submit_claim_candidate(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=other,
            client_kind="user",
            candidate=candidate,
            supersedes_claim_id=claim_id,
            idempotency_key="science-request:lineage-other-user",
        )

    with pytest.raises(ScienceConfirmationRequired, match="source document"):
        service.submit_claim_candidate(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:other",
            identity=science_identity,
            client_kind="user",
            candidate=candidate,
            supersedes_claim_id=claim_id,
            idempotency_key="science-request:lineage-other-document",
        )


def test_interpretation_confirmation_rechecks_current_document_access(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    candidate = ScienceInterpretationPayload.model_validate(_llm_content()).claims[0]
    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="user",
        candidate=candidate,
        idempotency_key="science-request:access-submit",
    )
    service._document_access_check = lambda _identity, _document_ref: False

    with pytest.raises(ScienceAuthorizationError, match="document access"):
        service.confirm_interpretation(
            submitted.interpretation_id,
            claim_ids=[submitted.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:access-confirm",
        )


def test_different_clients_produce_the_same_claim_and_deterministic_verdict(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    candidate = _candidate_without_external_applicability()
    verdicts = []
    claim_ids = []
    for client_kind in ("codex", "claude"):
        submitted = service.submit_claim_candidate(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            client_kind=client_kind,
            candidate=candidate,
            idempotency_key=f"science-request:{client_kind}-parity",
        )
        claim_id = submitted.candidate_claims[0].claim_id
        confirmed = service.confirm_interpretation(
            submitted.interpretation_id,
            claim_ids=[claim_id],
            identity=science_identity,
            idempotency_key=f"science-request:{client_kind}-parity-confirm",
        )
        claim_ids.append(claim_id)
        verdicts.append(
            service.verify_claim(
                confirmed.interpretation_id,
                claim_id,
                ReleaseSelection(foundation="sci-release:foundation-0.1"),
                identity=science_identity,
            )
        )

    assert claim_ids[0] == claim_ids[1]
    assert verdicts[0].model_dump(mode="json") == verdicts[1].model_dump(mode="json")


def test_real_store_preserves_external_submission_confirmation_dependency(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _real_service(tmp_path)
    candidate = _candidate_without_external_applicability()
    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:real-store-submit",
    )
    claim_id = submitted.candidate_claims[0].claim_id

    confirmed = service.confirm_interpretation(
        submitted.interpretation_id,
        claim_ids=[claim_id],
        identity=science_identity,
        idempotency_key="science-request:real-store-confirm",
    )

    assert store.load_interpretation(submitted.interpretation_id) == submitted
    assert store.load_interpretation(confirmed.interpretation_id) == confirmed
    assert (
        service.verify_claim(
            confirmed.interpretation_id,
            claim_id,
            ReleaseSelection(foundation="sci-release:foundation-0.1"),
            identity=science_identity,
        ).verdict
        == PrimaryVerdict.VIOLATION
    )
    correction = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="user",
        candidate=candidate,
        supersedes_claim_id=claim_id,
        idempotency_key="science-request:real-store-correction",
    )
    assert correction.supersedes_claim_id == claim_id


def test_external_claim_submission_cannot_use_an_inactive_release_for_verdict(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    candidate = _candidate_without_external_applicability()
    submitted = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="claude",
        candidate=candidate,
        idempotency_key="science-request:inactive-release-submit",
    )
    claim_id = submitted.candidate_claims[0].claim_id
    confirmed = service.confirm_interpretation(
        submitted.interpretation_id,
        claim_ids=[claim_id],
        identity=science_identity,
        idempotency_key="science-request:inactive-release-confirm",
    )
    catalog.release = catalog.release.model_copy(update={"status": "release_candidate"})
    catalog.release_set = ResolvedReleaseSet.from_single_foundation(catalog.release)
    catalog.rule_set = catalog.rule_set.model_copy(
        update={"release_set_digest": catalog.release_set.combined_digest}
    )

    with pytest.raises(ScienceOperationalError, match="not operational"):
        service.verify_claim(
            confirmed.interpretation_id,
            claim_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )


def test_interpret_document_rejects_a_non_digest_response_identity(
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _service()
    llm.result = ScienceLLMResult(
        payload=llm.result.payload,
        response_digest="not-a-sha256-digest",
    )

    with pytest.raises(ScienceInterpretationUnavailable, match="response digest"):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key=INTERPRET_KEY,
        )

    assert store.interpretations == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("process_stage", "https://private-process.test:1236/v1"),
        ("material_state", "Bearer-secret-state-value"),
        ("ontology_ref", "sk-secret-ontology-token"),
    ],
)
def test_interpretation_rejects_recursive_secret_or_endpoint_scalars_before_save(
    science_identity: AuthIdentity,
    field: str,
    value: str,
):
    content = _llm_content()
    if field == "ontology_ref":
        content["claims"][0]["ontology_refs"].append(value)
    else:
        content["claims"][0]["normalized_claim"][field] = value
    service, _catalog, store, _llm = _service(content)

    with pytest.raises(ScienceInterpretationUnavailable, match="failed closed"):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key=f"science-request:secret-{field}",
        )

    assert store.interpretations == {}


def test_identity_bound_revision_rejects_endpoint_shaped_actor_before_save(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    proposal = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )
    malicious_identity = AuthIdentity(
        employee_id="https://identity.test:1236",
        display_name="untrusted",
        roles=["science.admin"],
    )

    with pytest.raises(ScienceAuthorizationError, match="interpretation owner"):
        service.confirm_interpretation(
            proposal.interpretation_id,
            claim_ids=[proposal.candidate_claims[0].claim_id],
            identity=malicious_identity,
            idempotency_key="science-request:secret-actor",
        )

    assert len(store.interpretations) == 1


def test_record_boundary_rejects_an_unsafe_programmatically_constructed_model_id(
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _service()
    llm.config = ScienceLLMConfig(
        model_id="https://private-model.test:1236/v1",
        settings=llm.config.settings,
        _base_url="https://runtime-only.test/v1",
    )

    with pytest.raises(ScienceInterpretationUnavailable, match="failed closed"):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key="science-request:unsafe-model",
        )

    assert store.interpretations == {}


def test_closed_revision_and_nested_list_fields_cannot_persist_secret_aliases(
    science_identity: AuthIdentity,
):
    service, _catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    revision_payload = confirmed.model_dump(mode="json")
    revision_payload["user_revision_history"][0]["accessToken"] = "hidden-value"
    with pytest.raises(ValueError):
        type(confirmed).model_validate(revision_payload)

    condition_payload = confirmed.model_dump(mode="json")
    condition_payload["candidate_claims"][0]["normalized_claim"]["conditions"] = [
        {
            "condition_id": "fixture",
            "value": "clientSecret=hidden-value",
            "unit": None,
        }
    ]
    with pytest.raises(ValueError, match="credential or endpoint"):
        type(confirmed).model_validate(condition_payload)


def test_llm_false_changes_outcome_is_advisory_and_never_self_confirms(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, _catalog, _store, _llm = _service(content)

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    claim = record.candidate_claims[0]
    assert claim.interpretation.user_confirmed is False
    assert "USER_CONFIRMATION_REQUIRED" in record.decision_impact[0].issue_codes
    assert record.decision_impact[0].outcome_impact == "unresolved"
    assert record.confirmed_claim_packet_digest is None


def test_unknown_ontology_reference_is_persisted_as_a_paused_proposal(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["ontology_refs"] = ["sci:binding:invented"]
    service, _catalog, store, _llm = _service(content)

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    interpretation = record.candidate_claims[0].interpretation
    assert "sci:binding:invented" not in interpretation.ontology_refs
    assert "sci:binding:invented" in interpretation.proposed_ontology_refs
    assert "UNKNOWN_ONTOLOGY_REF" in record.decision_impact[0].issue_codes
    assert store.interpretations[record.interpretation_id] == record


def test_interpretation_converts_missing_pinned_ontology_to_fail_closed_error(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    service.ontology_binding_ids = ("sci:binding:missing",)

    with pytest.raises(ScienceInterpretationUnavailable, match="unavailable"):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key=INTERPRET_KEY,
        )

    assert store.interpretations == {}


def test_experimental_llm_adapter_can_be_disabled_without_creating_a_candidate(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    service.llm_client = None

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key="science-request:experimental-adapter-disabled",
        )

    assert captured.value.diagnostic_code == "adapter_disabled"
    assert store.interpretations == {}


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("unavailable", "http_status_503"),
        ("timeout", "timeout"),
        ("empty", "invalid_json"),
        ("invalid_json", "invalid_json"),
        ("schema_mismatch", "schema_invalid"),
    ],
)
def test_experimental_llm_failures_never_create_interpretation_or_report(
    science_identity: AuthIdentity,
    case: str,
    expected_code: str,
):
    def handler(_request: httpx.Request) -> httpx.Response:
        if case == "unavailable":
            return httpx.Response(503)
        if case == "timeout":
            raise httpx.ReadTimeout("fixture timeout")
        if case == "empty":
            return _openai_response("")
        if case == "invalid_json":
            return _openai_response("not-json")
        return _openai_response({"claims": []})

    service, _catalog, store, _llm = _service()
    service.llm_client = ScienceLLMClient(
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "qwen/qwen3.8-27b",
                "BOI_SCIENCE_LLM_MAX_ATTEMPTS": "1",
            }
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key=f"science-request:experimental-{case}",
        )

    assert captured.value.diagnostic_code == expected_code
    assert store.interpretations == {}
    assert store.reports == {}


@pytest.mark.parametrize(
    ("case", "expected_issue"),
    [
        ("zero_refs", "ONTOLOGY_REFS_REQUIRED"),
        ("missing_subject", "SUBJECT_BINDING_REQUIRED"),
        ("missing_object", "OBJECT_BINDING_REQUIRED"),
        ("subject_binding_mismatch", "BINDING_CONCEPT_MISMATCH"),
        ("missing_relation", "RELATION_BINDING_REQUIRED"),
        ("alias_binding_mismatch", "ALIAS_BINDING_MISMATCH"),
        ("partial_relation_span", "COMPLETE_RELATION_SPAN_REQUIRED"),
    ],
)
def test_semantically_incomplete_llm_proposals_pause_before_confirmation_or_report(
    science_identity: AuthIdentity,
    case: str,
    expected_issue: str,
):
    content = _llm_content()
    claim = content["claims"][0]
    if case == "zero_refs":
        claim["ontology_refs"] = []
        claim["candidate_meanings"] = []
    elif case == "missing_subject":
        claim["ontology_refs"].remove("sci:binding:rpm")
        claim["candidate_meanings"] = [
            item
            for item in claim["candidate_meanings"]
            if item["concept_role"] != "subject"
        ]
    elif case == "subject_binding_mismatch":
        claim["candidate_meanings"][0]["ontology_ref"] = "sci:binding:film-thickness"
    elif case == "missing_object":
        claim["ontology_refs"].remove("sci:binding:film-thickness")
        claim["candidate_meanings"] = [
            item
            for item in claim["candidate_meanings"]
            if item["concept_role"] != "object"
        ]
    elif case == "missing_relation":
        claim["ontology_refs"].remove("sci:binding:increases")
        claim["candidate_meanings"] = [
            item
            for item in claim["candidate_meanings"]
            if item["concept_role"] != "relation"
        ]
    elif case == "alias_binding_mismatch":
        claim["candidate_meanings"][1]["surface_term"] = "시"
    elif case == "partial_relation_span":
        claim["source_span"] = {
            "start": 0,
            "end": len("RPM 증가"),
            "exact": "RPM 증가",
            "prefix": "",
            "suffix": " 시",
        }

    service, catalog, store, _llm = _service(content)
    proposal = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=f"science-request:{case}",
    )

    assert proposal.candidate_claims[0].interpretation.user_confirmed is False
    assert expected_issue in proposal.decision_impact[0].issue_codes
    if case == "alias_binding_mismatch":
        assert (
            "sci:binding:increases"
            not in proposal.candidate_claims[0].interpretation.ontology_refs
        )
    with pytest.raises(ScienceConfirmationRequired):
        service.confirm_interpretation(
            proposal.interpretation_id,
            claim_ids=[proposal.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key=f"science-request:confirm-{case}",
        )
    with pytest.raises(ScienceConfirmationRequired):
        service.verify_document(
            proposal.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=f"science-request:report-{case}",
        )
    assert store.reports == {}


def test_explicit_identity_bound_confirmation_creates_a_typed_revision_before_verdict(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    proposal = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    with pytest.raises(ScienceConfirmationRequired):
        service.verify_claim(
            proposal.interpretation_id,
            proposal.candidate_claims[0].claim_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )

    user_revision = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="user",
        candidate=_user_candidate_with_applicability(),
        supersedes_claim_id=proposal.candidate_claims[0].claim_id,
        idempotency_key="science-request:explicit-user-applicability",
    )
    confirmed = service.confirm_interpretation(
        user_revision.interpretation_id,
        claim_ids=[user_revision.candidate_claims[0].claim_id],
        identity=science_identity,
        idempotency_key=CONFIRM_KEY,
    )
    event = confirmed.user_revision_history[-1]

    assert confirmed.candidate_claims[0].interpretation.user_confirmed is True
    assert confirmed.candidate_claims[0].interpretation.ambiguity_ids == []
    assert confirmed.confirmed_claim_packet_digest == sha256_digest(
        confirmed.candidate_claims[0]
    )
    assert confirmed.operation_binding is not None
    assert (
        confirmed.operation_binding.claim_digest
        == confirmed.confirmed_claim_packet_digest
    )
    assert event.action == "claim_confirmed"
    assert event.actor_id == science_identity.employee_id
    assert event.source_interpretation_id == user_revision.interpretation_id
    verdict = service.verify_claim(
        confirmed.interpretation_id,
        confirmed.candidate_claims[0].claim_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
    )
    assert verdict.verdict is PrimaryVerdict.VIOLATION
    assert store.interpretations[confirmed.interpretation_id] == confirmed


def test_verify_claim_rejects_a_catalog_result_not_matching_the_exact_selection(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    with pytest.raises(ScienceOperationalError, match="exact release selection"):
        service.verify_claim(
            record.interpretation_id,
            record.candidate_claims[0].claim_id,
            ReleaseSelection(foundation="sci-release:different-selection"),
            identity=science_identity,
        )

    assert catalog.resolve_operational_calls == 0
    assert catalog.resolve_legacy_calls == 0


def test_verify_claim_rejects_any_non_catalog_operational_object(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.operational_override = object()

    with pytest.raises(ScienceOperationalError, match="Catalog-issued"):
        service.verify_claim(
            record.interpretation_id,
            record.candidate_claims[0].claim_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )

    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_claim_runs_the_engine_only_with_catalog_operational_capability(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)

    verdict = service.verify_claim(
        record.interpretation_id,
        record.candidate_claims[0].claim_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
    )

    assert verdict.verdict is PrimaryVerdict.VIOLATION
    assert verdict.releases.combined_digest == catalog.release_set.combined_digest
    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_never_persists_an_unresolved_ambiguity_report(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key=INTERPRET_KEY,
    )

    with pytest.raises(ScienceConfirmationRequired):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
        )

    assert store.reports == {}
    assert catalog.resolve_operational_calls == 0
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_uses_only_grounded_knowledge_and_server_evidence_links(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)

    report = service.verify_document(
        record.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key=REPORT_KEY,
    )

    assert report.verdict_packets[0].verdict is PrimaryVerdict.VIOLATION
    assert report.confirmed_claims == record.candidate_claims
    assert report.confirmed_claims[0].interpretation.ontology_refs == [
        "sci:binding:film-thickness",
        "sci:binding:increases",
        "sci:binding:rpm",
    ]
    annotation = report.annotations[0]
    link = annotation.evidence_links[0]
    assert annotation.claim_id == record.candidate_claims[0].claim_id
    assert annotation.fact_id == "fact:sci:rule:spin-direction:contradicts"
    assert annotation.text == catalog.knowledge_statement
    assert annotation.knowledge_id == "sci:knowledge:spin-direction"
    assert annotation.knowledge_digest == KNOWLEDGE_DIGEST
    assert link.evidence_id == "sci:evidence:spin-direction"
    assert link.evidence_digest == EVIDENCE_DIGEST
    assert link.source_id == "sci:source:spin-paper"
    assert link.source_digest == SOURCE_DIGEST
    assert link.original_text_hash == sha256_digest(
        "Increasing angular speed decreases film thickness."
    )
    assert link.quote_hash == link.original_text_hash
    assert link.url == "https://example.test/spin-paper"
    assert link.locator.model_dump(exclude_none=True) == {
        "section": "3.2",
        "equation": "7",
    }
    assert link.source_lookup.versioned_path == ("public/science/sources/spin-paper.md")
    assert link.source_lookup.acl_policy == "acl:public"
    explanation = report.explanations[0]
    assert (explanation.claim_id, explanation.fact_id) == (
        annotation.claim_id,
        annotation.fact_id,
    )
    assert explanation.equation_refs == []
    assert [item.object_id for item in explanation.knowledge_refs] == [
        "sci:knowledge:spin-direction"
    ]
    assert [item.object_id for item in explanation.rule_refs] == [
        "sci:rule:spin-direction"
    ]
    assert [item.block_kind for item in explanation.blocks] == [
        "applied_principle",
        "scientific_consequence",
        "correction",
        "limitation",
        "evidence",
    ]
    assert report.equation_assets == []
    assert report.report_digest == sha256_digest(
        report.model_dump(mode="json", exclude={"report_digest"})
    )
    assert store.reports[report.report_id] == report
    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_fails_if_a_decisive_fact_has_no_approved_statement(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.knowledge_statement = ""

    with pytest.raises(ScienceOperationalError, match="grounded statement"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
        )
    assert store.reports == {}


def test_verify_document_rejects_evidence_not_matching_the_pinned_digest(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.evidence_digest = "sha256:changed-after-release"

    with pytest.raises(ScienceOperationalError, match="release digest"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
        )

    assert store.reports == {}


def test_verify_document_rejects_an_evidence_quote_hash_mismatch(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.evidence_original_text_hash = "sha256:" + "b" * 64

    with pytest.raises(ScienceOperationalError, match="quote hash"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
        )

    assert store.reports == {}


_CREDENTIAL_BEARING_SOURCE_URLS = [
    "https://user:password@example.test/spin-paper",
    "https://example.test/spin-paper?accessToken=hidden-value",
    "https://example.test/private/api_key=hidden-value",
    "https://example.test/private/api%5Fkey%3Dhidden-value",
    "https://example.test/private/api%255Fkey%253Dhidden-value",
    "https://example.test/private/bearer/hidden-value",
    "https://example.test/paper?X-Amz-Signature=abcdef0123456789",
    "https://example.test/paper?X%2DAmz%2DSignature=abcdef0123456789",
    "https://example.test/paper?signature=abcdef0123456789",
    "https://example.test/paper?sig=abcdef0123456789",
    "https://example.test/paper?X-Amz-Credential=hidden-value",
    "https://example.test/paper#token=hidden-value",
]

_CANONICAL_URL_BYPASSES = [
    "https://example.test/private/api／key=hidden-canonical-value",
    "https://example.test/private/％61pi_key=hidden-canonical-value",
    "https://example.test/private/api;key=hidden-canonical-value",
    "https://example.test/private/api:key=hidden-canonical-value",
    "https://example.test/private/%ZZapi_key=hidden-canonical-value",
    "https://example.test/private/api%ZZ_key=hidden-canonical-value",
    "https://example.test/private/X-Goog-Signature=hidden-canonical-value",
    "https://example.test/private/X-Ms-Signature=hidden-canonical-value",
    "https://example.test/private/SharedAccessSignature=hidden-canonical-value",
    "https://example.test/private/SAS=hidden-canonical-value",
    "https://example.test/private/api-key-hidden-canonical-value",
    "https://example.test/private/api/key-hidden-canonical-value",
    "https://example.test/private/token-hidden-canonical-value",
    "https://example.test/private/signature-hidden-canonical-value",
    "https://user%3Ahidden-canonical-value%40example.test/paper",
    "https://user%253Ahidden-canonical-value%2540example.test/paper",
    " https://example.test/paper\n",
    "https://exa\tmple.test/paper",
]

_CREDENTIAL_TOKEN_FAMILIES = {
    "accesskey": "access-key",
    "accesstoken": "access-token",
    "apikey": "api-key",
    "auth": "auth",
    "authorization": "authorization",
    "basicauth": "basic-auth",
    "bearer": "bearer",
    "clientsecret": "client-secret",
    "credential": "credential",
    "password": "password",
    "passwd": "passwd",
    "privatekey": "private-key",
    "secret": "secret",
    "sig": "sig",
    "signature": "signature",
    "token": "token",
    "xamz": "x-amz-signature",
    "xgoog": "x-goog-signature",
    "xms": "x-ms-signature",
    "sharedaccess": "shared-access-signature",
    "sas": "sas",
    "presigned": "presigned",
}
_CREDENTIAL_SEQUENCE_MARKERS = {
    "access-key",
    "access-token",
    "api-key",
    "basic-auth",
    "client-secret",
    "private-key",
    "x-amz-credential",
    "x-amz-signature",
    "x-goog-credential",
    "x-goog-signature",
    "x-ms-credential",
    "x-ms-signature",
    "shared-access-signature",
}

_BOUNDARY_CREDENTIAL_URLS = [
    url
    for marker in sorted(
        {
            *_CREDENTIAL_TOKEN_FAMILIES,
            *_CREDENTIAL_TOKEN_FAMILIES.values(),
            *_CREDENTIAL_SEQUENCE_MARKERS,
        }
    )
    for url in (
        f"https://example.test/private/file-{marker}-hidden-boundary-value",
        f"https://file-{marker}-hidden-boundary-value.example.test/paper",
    )
]
_COMPACT_OPAQUE_VALUE = "9f4c2a7d8e1b6c3a5d0f7e2c4b9a1d6e"
_COMPACT_CREDENTIAL_URLS = [
    url
    for family in _CREDENTIAL_TOKEN_FAMILIES
    for url in (
        f"https://example.test/private/{family}{_COMPACT_OPAQUE_VALUE}",
        f"https://file{family}{_COMPACT_OPAQUE_VALUE}.example.test/paper",
    )
]
_UNSAFE_STABLE_SOURCE_URLS = [
    *_CANONICAL_URL_BYPASSES,
    *_BOUNDARY_CREDENTIAL_URLS,
    *_COMPACT_CREDENTIAL_URLS,
]


def test_task3_closed_validation_factory_drops_real_except_context():
    secret = "hidden-adapter-value"
    raw_rendered = ""
    rejected = False
    try:
        EvidenceLocator(
            section="3.2",
            resource_url=f"https://example.test/private?token={secret}",
        )
    except ValidationError as exc:
        raw_rendered = str(exc)
        rejected = True
    assert rejected
    assert secret not in raw_rendered

    with pytest.raises(SciencePublicValidationError) as captured:
        raise closed_science_validation_error()

    assert captured.value.diagnostic_code == "invalid_science_input"
    assert secret not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize(
    "url",
    [
        "HTTPS://example.test/paper",
        "https://Example.test/paper",
        "https://example.test:443/paper",
        "https://example.test:8443/paper",
        "https://example.test:not-a-port/paper",
        "https://example..test/paper",
        "https://example.test/%70aper",
        "https://example.test/paper?",
        "https://example.test/paper#",
    ],
)
def test_stable_source_url_rejects_noncanonical_authority_and_serialization(url: str):
    with pytest.raises(ValueError):
        validate_credential_free_https_url(url)


def test_stable_source_url_returns_the_exact_checked_ascii_serialization():
    url = "https://example.test/%ED%95%9C%EA%B8%80.pdf?download=true"

    assert validate_credential_free_https_url(url) == url


@pytest.mark.parametrize("url", _BOUNDARY_CREDENTIAL_URLS)
def test_stable_source_url_syntax_does_not_guess_from_scientific_path_text(url: str):
    assert validate_credential_free_https_url(url) == url


def test_stable_source_url_matrix_covers_all_22_reviewed_credential_families():
    assert len(_CREDENTIAL_TOKEN_FAMILIES) == 22
    assert len(_COMPACT_CREDENTIAL_URLS) * 4 == 176


@pytest.mark.parametrize("url", _COMPACT_CREDENTIAL_URLS)
def test_stable_source_url_syntax_does_not_use_entropy_heuristics(url: str):
    assert validate_credential_free_https_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/signals-and-systems/paper",
        "https://example.test/sigma-model/paper",
        "https://example.test/authors/feynman",
        "https://example.test/tokenization/paper",
        "https://example.test/secretory-pathway/paper",
    ],
)
def test_stable_source_url_allows_normal_scientific_tokens(url: str):
    assert validate_credential_free_https_url(url) == url


def test_reviewed_source_identity_cannot_be_constructed_by_a_caller():
    with pytest.raises(TypeError, match="issued only"):
        ReviewedSourceURLIdentity()


def test_candidate_preview_cannot_be_promoted_through_direct_identity_issuer():
    catalog = _Catalog()
    candidate = _build_reviewed_source_url_profile(
        qualification_state="candidate",
        release_set_digest=catalog.release_set.combined_digest,
        source_id="sci:source:spin-paper",
        source_digest=SOURCE_DIGEST,
        evidence_id="sci:evidence:spin-direction",
        evidence_digest=EVIDENCE_DIGEST,
        canonical_source_url=catalog.source_url,
        locator=EvidenceLocator.model_validate(catalog.evidence_locator),
    )
    payload = candidate.model_dump(mode="json")
    payload["qualification_state"] = "active"
    payload["profile_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "profile_digest"}
    )
    promoted = ReviewedSourceURLProfile.model_validate(payload)

    with pytest.raises(TypeError, match="direct Source identity issuance is forbidden"):
        _issue_reviewed_source_url_identity(promoted)


def test_reviewed_source_identity_is_opaque_immutable_and_nonserializable():
    import copy
    import pickle

    catalog = _Catalog()
    identity = catalog.resolve_reviewed_source_url_identity(
        catalog.release_set, "sci:evidence:spin-direction"
    )

    with pytest.raises(AttributeError, match="immutable"):
        identity.profile = "forged"
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(identity)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(identity)


def test_reviewed_source_identity_revalidates_catalog_on_every_open():
    catalog = _Catalog()
    identity = catalog.resolve_reviewed_source_url_identity(
        catalog.release_set, "sci:evidence:spin-direction"
    )
    catalog.source_url = "https://example.test/reviewed-replacement"
    catalog._review_current_source_identity()

    with pytest.raises(TypeError, match="no longer authoritative"):
        _open_reviewed_source_url_identity(identity)


def test_catalog_identity_issuer_rejects_an_arbitrary_catalog_double():
    catalog = _Catalog()

    with pytest.raises(TypeError, match="exact ScienceCatalog"):
        _issue_catalog_reviewed_source_url_identity(
            catalog,
            catalog.release_set,
            "sci:evidence:spin-direction",
        )


def test_service_rejects_a_raw_unsealed_source_profile(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    raw_profile = _build_reviewed_source_url_profile(
        qualification_state="active",
        release_set_digest=catalog.release_set.combined_digest,
        source_id="sci:source:spin-paper",
        source_digest=SOURCE_DIGEST,
        evidence_id="sci:evidence:spin-direction",
        evidence_digest=EVIDENCE_DIGEST,
        canonical_source_url=catalog.source_url,
        locator=EvidenceLocator.model_validate(catalog.evidence_locator),
    )
    catalog.resolve_reviewed_source_url_identity = lambda *_args: raw_profile

    with pytest.raises(ScienceOperationalError, match="Catalog-issued"):
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:raw-source-profile",
        )

    assert store.reports == {}


def test_candidate_source_profile_cannot_become_an_authoritative_report(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:candidate-profile-base",
    )
    payload = report.model_dump(mode="json")
    profile = payload["annotations"][0]["evidence_links"][0]["reviewed_source"]
    profile["qualification_state"] = "candidate"
    profile["profile_digest"] = sha256_digest(
        {key: value for key, value in profile.items() if key != "profile_digest"}
    )
    payload["report_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "report_digest"}
    )

    with pytest.raises(ValidationError, match="active reviewed Source URL"):
        VerificationReport.model_validate(payload)


def _report_with_coordinated_unreviewed_source(
    report: VerificationReport,
    *,
    report_id: str,
    source_url: str,
) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["report_id"] = report_id
    link = payload["annotations"][0]["evidence_links"][0]
    link["url"] = source_url
    profile = link["reviewed_source"]
    profile["canonical_source_url"] = source_url
    profile["canonical_source_url_digest"] = sha256_digest(source_url)
    profile["profile_digest"] = sha256_digest(
        {key: value for key, value in profile.items() if key != "profile_digest"}
    )
    payload["report_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "report_digest"}
    )
    return payload


def _report_with_coordinated_unreleased_provenance(
    report: VerificationReport,
    *,
    report_id: str,
) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    payload["report_id"] = report_id
    selection = {
        "foundation": "sci-release:not-in-catalog",
        "domains": [],
        "applications": [],
    }
    release_content_digest = sha256_digest("unreleased-release-content")
    release_set_digest = sha256_digest("unreleased-release-set")
    payload["release_selection"] = selection
    payload["release_digests"] = {selection["foundation"]: release_content_digest}
    binding = payload["operation_binding"]
    binding["release_digest"] = sha256_digest(selection)
    binding["request_digest"] = sha256_digest(
        {
            "operation": "verify_document",
            "interpretation_id": payload["interpretation_ids"][0],
            "claim_digest": binding["claim_digest"],
            "release_selection": selection,
        }
    )
    forged_source_id = "sci:source:not-in-catalog"
    forged_source_digest = sha256_digest("unreleased-source")
    forged_evidence_id = "sci:evidence:not-in-catalog"
    forged_evidence_digest = sha256_digest("unreleased-evidence")
    forged_knowledge_id = "sci:knowledge:not-in-catalog"
    forged_knowledge_digest = sha256_digest("unreleased-knowledge")
    forged_url = "https://unreviewed.example.test/all-provenance"
    forged_locator = EvidenceLocator(section="fabricated section 999").model_dump(
        mode="json"
    )
    for verdict in payload["verdict_packets"]:
        verdict["releases"] = {
            "selection": selection,
            "digests": payload["release_digests"],
            "combined_digest": release_set_digest,
        }
        verdict["knowledge_refs"] = [forged_knowledge_id]
        verdict["evidence_refs"] = [forged_evidence_id]
        for fact in verdict["explanation_facts"]:
            fact["knowledge_refs"] = [forged_knowledge_id]
            fact["evidence_refs"] = [forged_evidence_id]
    for annotation in payload["annotations"]:
        annotation["knowledge_id"] = forged_knowledge_id
        annotation["knowledge_digest"] = forged_knowledge_digest
        for link in annotation["evidence_links"]:
            link["evidence_id"] = forged_evidence_id
            link["evidence_digest"] = forged_evidence_digest
            link["source_id"] = forged_source_id
            link["source_digest"] = forged_source_digest
            link["url"] = forged_url
            link["locator"] = forged_locator
            lookup = link["source_lookup"]
            lookup.update(
                {
                    "source_id": forged_source_id,
                    "source_digest": forged_source_digest,
                    "boi_id": "boi:public:science:source:not-in-catalog",
                    "versioned_path": "public/science/sources/not-in-catalog.md",
                }
            )
            lookup["lookup_digest"] = sha256_digest(
                {key: value for key, value in lookup.items() if key != "lookup_digest"}
            )
            profile = link["reviewed_source"]
            profile.update(
                {
                    "release_set_digest": release_set_digest,
                    "source_id": forged_source_id,
                    "source_digest": forged_source_digest,
                    "evidence_id": forged_evidence_id,
                    "evidence_digest": forged_evidence_digest,
                    "canonical_source_url": forged_url,
                    "canonical_source_url_digest": sha256_digest(forged_url),
                    "locator": forged_locator,
                    "locator_digest": sha256_digest(forged_locator),
                    "locator_url_digests": {},
                }
            )
            profile["profile_digest"] = sha256_digest(
                {
                    key: value
                    for key, value in profile.items()
                    if key != "profile_digest"
                }
            )
    authoritative_link = payload["annotations"][0]["evidence_links"][0]
    for explanation in payload["explanations"]:
        explanation["knowledge_refs"] = [
            {
                "object_id": forged_knowledge_id,
                "object_digest": forged_knowledge_digest,
            }
        ]
        explanation["evidence_links"] = [json.loads(json.dumps(authoritative_link))]
        for block in explanation["blocks"]:
            block["knowledge_refs"] = [
                {
                    "object_id": forged_knowledge_id,
                    "object_digest": forged_knowledge_digest,
                }
            ]
            block["evidence_refs"] = [
                {
                    "object_id": forged_evidence_id,
                    "object_digest": forged_evidence_digest,
                }
            ]
    payload["report_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "report_digest"}
    )
    return payload


def test_report_annotations_must_exactly_cover_verdict_explanation_facts(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:annotation-fact-binding-base",
    )
    payload = report.model_dump(mode="json")
    payload["annotations"][0]["fact_id"] = "sci:fact:not-in-verdict"
    payload["report_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "report_digest"}
    )

    with pytest.raises(ValidationError, match="explanation fact"):
        VerificationReport.model_validate(payload)


def test_store_direct_save_rejects_self_consistent_unreviewed_source_profile(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:authority-direct-save-base",
    )
    forged = _report_with_coordinated_unreviewed_source(
        report,
        report_id="sci-report:coordinated-unreviewed-save",
        source_url="https://unreviewed.example.test/replacement",
    )
    VerificationReport.model_validate(forged)

    with pytest.raises(ImmutableScienceRecordError, match="Catalog authority"):
        store.save_report(forged, identity=science_identity)

    assert not store.record_path("reports", forged["report_id"]).exists()


def test_store_private_load_rejects_self_consistent_unreviewed_source_profile(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:authority-private-load-base",
    )
    forged = _report_with_coordinated_unreviewed_source(
        report,
        report_id="sci-report:coordinated-unreviewed-load",
        source_url="https://unreviewed.example.test/private-load",
    )
    path = store.record_path("reports", forged["report_id"])
    path.write_bytes(canonical_json_bytes(forged))
    path.chmod(0o600)

    with pytest.raises(ImmutableScienceRecordError, match="Catalog authority"):
        store.load_report(forged["report_id"])


def test_store_rejects_coordinated_unreleased_release_and_provenance(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:authority-all-provenance-base",
    )
    forged = _report_with_coordinated_unreleased_provenance(
        report,
        report_id="sci-report:coordinated-unreleased-provenance",
    )
    VerificationReport.model_validate(forged)

    with pytest.raises(ImmutableScienceRecordError, match="Catalog authority"):
        store.save_report(forged, identity=science_identity)


def test_store_wal_recovery_rejects_self_consistent_unreviewed_source_profile(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    real_append = store._append_audit_event_locked

    def fail_report_audit(event):
        if event.action == "report_saved":
            raise OSError("simulated authority WAL interruption")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_audit)
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:authority-wal-base",
        )
    journal_path = next((store.root / "transactions").glob("*.json"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    forged = _report_with_coordinated_unreviewed_source(
        VerificationReport.model_validate(journal["record"]),
        report_id=pending.value.record_id,
        source_url="https://unreviewed.example.test/from-wal",
    )
    journal["record"] = forged
    journal["audit"]["details"]["report_digest"] = forged["report_digest"]
    journal_path.write_bytes(canonical_json_bytes(journal))
    store.record_path("reports", pending.value.record_id).unlink()
    monkeypatch.setattr(store, "_append_audit_event_locked", real_append)

    with pytest.raises(ImmutableScienceRecordError, match="Catalog authority"):
        store.recover_pending_transactions()

    assert not store.record_path("reports", pending.value.record_id).exists()
    assert journal_path.exists()


def test_store_requires_an_authoritative_report_validator(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, source_store, _llm = _real_service(tmp_path / "source")
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:missing-authority-base",
    )
    proposal = source_store.load_interpretation(
        confirmed.operation_binding.source_interpretation_id
    )
    unbound_store = ScienceRuntimeStore(
        tmp_path / "unbound",
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=lambda _identity: ["science.admin"],
    )
    unbound_store.save_interpretation(proposal, identity=science_identity)
    unbound_store.save_interpretation(confirmed, identity=science_identity)

    with pytest.raises(ImmutableScienceRecordError, match="Catalog authority"):
        unbound_store.save_report(report, identity=science_identity)

    assert not unbound_store.record_path("reports", report.report_id).exists()


def test_store_catalog_validator_failure_discards_sensitive_exception_context(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:closed-authority-base",
    )
    secret = "https://hidden-authority-validator-secret.test/private"

    def fail_authority(_report):
        raise ValueError(secret)

    store._report_authority_validator = fail_authority
    with pytest.raises(ImmutableScienceRecordError) as captured:
        store.save_report(report, identity=science_identity)

    _assert_closed_runtime_validation_error(captured.value, secret=secret)


@pytest.mark.parametrize(
    "field_name",
    [
        "release_set_digest",
        "source_digest",
        "evidence_digest",
        "canonical_source_url_digest",
        "locator_digest",
        "locator_url_digests",
        "profile_digest",
    ],
)
def test_store_revalidates_every_reviewed_source_profile_binding(
    tmp_path: Path,
    science_identity: AuthIdentity,
    field_name: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key=f"science-request:profile-binding-base-{field_name}",
    )
    payload = report.model_dump(mode="json")
    payload["report_id"] = f"sci-report:profile-binding-{field_name}"
    profile = payload["annotations"][0]["evidence_links"][0]["reviewed_source"]
    if field_name == "locator_url_digests":
        profile[field_name] = {"resource_url": sha256_digest("different")}
    else:
        profile[field_name] = sha256_digest(f"different-{field_name}")
    if field_name != "profile_digest":
        profile["profile_digest"] = sha256_digest(
            {key: value for key, value in profile.items() if key != "profile_digest"}
        )
    payload["report_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "report_digest"}
    )

    with pytest.raises(ValueError):
        store.save_report(payload, identity=science_identity)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/authors2026semiconductorcalibration1234/paper",
        "https://example.test/tokenization2026semiconductormodel1234/paper",
        "https://example.test/secretorypathway2026measurement1234/paper",
        "https://example.test/signalsandsystems2026measurement1234/paper",
        "https://example.test/sasakicrystalstructure2026data1234/paper",
    ],
)
def test_catalog_reviewed_scientific_paths_remain_operational(
    science_identity: AuthIdentity,
    url: str,
):
    service, catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.source_url = url
    catalog._review_current_source_identity()

    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key=f"science-request:reviewed-path-{sha256_digest(url)[7:19]}",
    )

    link = report.annotations[0].evidence_links[0]
    assert link.url == url
    assert link.reviewed_source.qualification_state == "active"
    assert (
        link.reviewed_source.release_set_digest == catalog.release_set.combined_digest
    )


@pytest.mark.parametrize("source_url", _CREDENTIAL_BEARING_SOURCE_URLS)
def test_verify_document_rejects_credential_bearing_source_urls(
    science_identity: AuthIdentity,
    source_url: str,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.source_url = source_url

    with pytest.raises(ScienceOperationalError, match="reviewed Source URL"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
        )

    assert store.reports == {}


@pytest.mark.parametrize(
    ("locator_field", "locator_url"),
    [
        (field, value)
        for field in ("resource_url", "requested_url", "resolved_url")
        for value in _CREDENTIAL_BEARING_SOURCE_URLS
    ],
)
def test_service_rejects_every_credential_bearing_locator_url_without_echo(
    science_identity: AuthIdentity,
    locator_field: str,
    locator_url: str,
):
    service, catalog, store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.evidence_locator = {"section": "3.2", locator_field: locator_url}

    with pytest.raises(ScienceOperationalError) as captured:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=f"science-request:unsafe-{locator_field}",
        )

    rendered = str(captured.value)
    assert "hidden-value" not in rendered
    assert "abcdef0123456789" not in rendered
    assert store.reports == {}


@pytest.mark.parametrize(
    ("target_field", "unsafe_url"),
    [
        (field, value)
        for field in (
            "source_url",
            "resource_url",
            "requested_url",
            "resolved_url",
        )
        for value in _UNSAFE_STABLE_SOURCE_URLS
    ],
)
def test_real_service_rejects_every_noncanonical_source_url_before_report_storage(
    tmp_path: Path,
    science_identity: AuthIdentity,
    target_field: str,
    unsafe_url: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    if target_field == "source_url":
        catalog.source_url = unsafe_url
    else:
        catalog.evidence_locator = {"section": "3.2", target_field: unsafe_url}

    with pytest.raises(ScienceOperationalError) as captured:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=f"science-request:canonical-{target_field}",
        )

    assert "hidden-canonical-value" not in str(captured.value)
    assert "hidden-boundary-value" not in str(captured.value)
    assert not list((store.root / "reports").glob("*.json"))


def test_stable_source_url_policy_allows_only_reviewed_download_query(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    stable_url = "https://example.test/reviewed-paper.pdf?download=true"
    catalog.source_url = stable_url
    catalog.evidence_locator = {
        "resource_url": stable_url,
        "requested_url": stable_url,
        "resolved_url": stable_url,
        "section": "3.2",
    }
    catalog._review_current_source_identity()

    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:stable-download-query",
    )

    link = report.annotations[0].evidence_links[0]
    assert link.url == stable_url
    assert link.locator.resource_url == stable_url


@pytest.mark.parametrize(
    "query",
    [
        "utm_source=tracker",
        "download=false",
        "page=7",
        "download=true&download=true",
    ],
)
def test_stable_source_url_policy_rejects_unreviewed_query_keys_and_values(
    science_identity: AuthIdentity,
    query: str,
):
    service, catalog, store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.source_url = f"https://example.test/paper?{query}"

    with pytest.raises(ScienceOperationalError, match="reviewed Source URL"):
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:unreviewed-source-query",
        )

    assert store.reports == {}


def test_saved_report_keeps_exact_grounding_and_acl_snapshot_after_catalog_changes(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    interpretation = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        interpretation.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key=REPORT_KEY,
    )
    before = report.model_dump_json()

    catalog.knowledge_statement = "A later, mutable statement."
    catalog.evidence_digest = "sha256:later-version"
    loaded = store.load_report(report.report_id)

    assert loaded.model_dump_json() == before
    link = loaded.annotations[0].evidence_links[0]
    assert loaded.annotations[0].knowledge_digest == KNOWLEDGE_DIGEST
    assert link.evidence_digest == EVIDENCE_DIGEST
    assert link.source_digest == SOURCE_DIGEST
    assert link.source_lookup.lookup_digest == sha256_digest(
        link.source_lookup.model_dump(mode="json", exclude={"lookup_digest"})
    )
    tampered = loaded.model_dump(mode="json")
    tampered["annotations"][0]["knowledge_digest"] = sha256_digest(
        "different-knowledge-component"
    )
    with pytest.raises(ValueError, match="report digest"):
        type(loaded).model_validate(tampered)


def test_interpretation_idempotency_is_actor_and_request_bound_before_llm_retry(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _real_service(tmp_path)
    kwargs = {
        "document_ref": "boi:public:science:document:fixture",
        "identity": science_identity,
        "idempotency_key": INTERPRET_KEY,
    }

    first = service.interpret_document("RPM 증가 시 두께 변화", **kwargs)
    retried = service.interpret_document("RPM 증가 시 두께 변화", **kwargs)

    assert retried == first
    assert llm.calls == 1
    assert first.operation_binding is not None
    assert first.operation_binding.actor_id == science_identity.employee_id
    assert first.operation_binding.document_digest == sha256_digest(
        "RPM 증가 시 두께 변화"
    )
    assert first.operation_binding.claim_digest is not None
    assert first.operation_binding.prompt_digest.startswith("sha256:")
    assert _audit_actions(store).count("interpretation_saved") == 1
    with pytest.raises(ScienceIdempotencyConflict):
        service.interpret_document("다른 문서", **kwargs)
    other_identity = AuthIdentity(
        employee_id="100099",
        display_name="Other authorized user",
        roles=["science.admin"],
    )
    with pytest.raises(ScienceIdempotencyConflict):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            **{**kwargs, "identity": other_identity},
        )
    llm.config = ScienceLLMConfig(
        model_id="fixture-model-v2",
        settings=llm.config.settings,
        _base_url="https://runtime-only.test/v1",
    )
    with pytest.raises(ScienceIdempotencyConflict):
        service.interpret_document("RPM 증가 시 두께 변화", **kwargs)
    assert llm.calls == 1


def test_concurrent_same_key_interpretations_publish_one_record_and_audit(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _real_service(tmp_path)

    def run():
        return service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
            idempotency_key="science-request:concurrent-interpretation",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(lambda _index: run(), range(4)))

    assert len({record.interpretation_id for record in records}) == 1
    assert len(list((store.root / "interpretations").glob("*.json"))) == 1
    assert _audit_actions(store).count("interpretation_saved") == 1


def test_interpretation_retry_recovers_post_record_pre_audit_transaction(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    service, _catalog, store, llm = _real_service(tmp_path)
    real_append = store._append_audit_event_locked
    failed = False

    def fail_once(event):
        nonlocal failed
        if event.action == "interpretation_saved" and not failed:
            failed = True
            raise OSError("simulated private audit failure")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_once)
    kwargs = {
        "document_ref": "boi:public:science:document:fixture",
        "identity": science_identity,
        "idempotency_key": "science-request:pending-interpretation",
    }
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.interpret_document("RPM 증가 시 두께 변화", **kwargs)
    assert pending.value.record_published is True

    recovered = service.interpret_document("RPM 증가 시 두께 변화", **kwargs)

    assert recovered.interpretation_id.startswith("sci-interpretation:")
    assert llm.calls == 1
    assert _audit_actions(store).count("interpretation_saved") == 1
    assert not list((store.root / "transactions").glob("*.json"))


def test_report_retry_concurrency_and_pending_audit_are_exactly_once(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    interpretation = _confirmed_interpretation(service, science_identity)
    selection = ReleaseSelection(foundation=catalog.release.release_id)

    def run(report_key: str):
        return service.verify_document(
            interpretation.interpretation_id,
            selection,
            identity=science_identity,
            idempotency_key=report_key,
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        reports = list(
            executor.map(
                lambda _index: run("science-request:concurrent-report"), range(4)
            )
        )
    assert len({report.report_id for report in reports}) == 1
    assert _audit_actions(store).count("report_saved") == 1
    assert run("science-request:concurrent-report") == reports[0]

    with pytest.raises(ScienceIdempotencyConflict):
        service.verify_document(
            interpretation.interpretation_id,
            ReleaseSelection(foundation="sci-release:different"),
            identity=science_identity,
            idempotency_key="science-request:concurrent-report",
        )
    second_proposal = service.interpret_document(
        "RPM 증가 시 두께 변화 추가 문맥",
        document_ref="boi:public:science:document:second",
        identity=science_identity,
        idempotency_key="science-request:second-interpretation",
    )
    second_interpretation = service.confirm_interpretation(
        second_proposal.interpretation_id,
        claim_ids=[second_proposal.candidate_claims[0].claim_id],
        identity=science_identity,
        idempotency_key="science-request:second-confirmation",
    )
    with pytest.raises(ScienceIdempotencyConflict):
        service.verify_document(
            second_interpretation.interpretation_id,
            selection,
            identity=science_identity,
            idempotency_key="science-request:concurrent-report",
        )
    other_identity = AuthIdentity(
        employee_id="100099",
        display_name="Other authorized user",
        roles=["science.admin"],
    )
    with pytest.raises(ScienceAuthorizationError, match="interpretation owner"):
        service.verify_document(
            interpretation.interpretation_id,
            selection,
            identity=other_identity,
            idempotency_key="science-request:concurrent-report",
        )
    assert reports[0].operation_binding is not None
    assert reports[0].operation_binding.claim_digest == (
        interpretation.confirmed_claim_packet_digest
    )
    assert reports[0].operation_binding.release_digest == sha256_digest(selection)

    real_append = store._append_audit_event_locked
    failed = False

    def fail_report_once(event):
        nonlocal failed
        if event.action == "report_saved" and not failed:
            failed = True
            raise OSError("simulated private report audit failure")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_once)
    pending_key = "science-request:pending-report"
    with pytest.raises(ScienceTransactionPendingError) as pending:
        run(pending_key)
    assert pending.value.record_published is True
    recovered = run(pending_key)
    assert recovered.report_id.endswith(
        sha256_digest(pending_key).removeprefix("sha256:")
    )
    assert _audit_actions(store).count("report_saved") == 2
    assert not list((store.root / "transactions").glob("*.json"))


def test_real_store_rejects_unbound_confirmed_interpretation_and_report(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:valid-report-before-forgery",
    )

    unbound_interpretation = confirmed.model_dump(mode="json")
    unbound_interpretation["interpretation_id"] = "sci-interpretation:unbound"
    unbound_interpretation["operation_binding"] = None
    unbound_interpretation["user_revision_history"] = []
    with pytest.raises(ValueError):
        store.save_interpretation(
            unbound_interpretation,
            identity=science_identity,
        )
    stale_model = confirmed.model_copy(
        update={
            "interpretation_id": "sci-interpretation:stale-model-copy",
            "operation_binding": confirmed.operation_binding.model_copy(
                update={"operation": "interpret_document"}
            ),
        },
        deep=True,
    )
    with pytest.raises(ValueError):
        store.save_interpretation(stale_model, identity=science_identity)

    unbound_report = report.model_dump(mode="json")
    unbound_report.update(
        {
            "report_id": "sci-report:unbound",
            "operation_binding": None,
            "confirmed_claims": [],
            "interpretation_ids": ["sci-interpretation:nonexistent"],
            "release_digests": {"forged": "not-a-digest"},
            "report_digest": "sha256:" + "0" * 64,
        }
    )
    with pytest.raises(ValueError):
        store.save_report(unbound_report, identity=science_identity)
    forged_model = report.model_copy(
        update={
            "report_id": "sci-report:unbound-model-copy",
            "operation_binding": None,
        },
        deep=True,
    )
    with pytest.raises(ValueError):
        store.save_report(forged_model, identity=science_identity)


def test_service_rejects_stale_interpret_binding_before_engine_or_report(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    proposal = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        idempotency_key="science-request:stale-binding-proposal",
    )
    claim = proposal.candidate_claims[0].model_copy(
        update={
            "interpretation": proposal.candidate_claims[0].interpretation.model_copy(
                update={"ambiguity_ids": [], "user_confirmed": True}
            )
        },
        deep=True,
    )
    stale = proposal.model_copy(
        update={
            "candidate_claims": [claim],
            "confirmed_claim_packet_digest": sha256_digest(claim),
        },
        deep=True,
    )
    store.interpretations[proposal.interpretation_id] = stale

    with pytest.raises(ScienceConfirmationRequired):
        service.verify_claim(
            proposal.interpretation_id,
            claim.claim_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )
    with pytest.raises(ScienceConfirmationRequired):
        service.verify_document(
            proposal.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:stale-binding-report",
        )
    assert catalog.resolve_operational_calls == 0
    assert store.reports == {}


def test_real_store_rejects_bound_report_with_missing_interpretation_dependency(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _real_service(tmp_path / "source")
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:orphan-report",
    )
    empty_store = ScienceRuntimeStore(
        tmp_path / "empty-runtime",
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=lambda _identity: ["science.admin"],
    )

    with pytest.raises((KeyError, ValueError)):
        empty_store.save_report(report, identity=science_identity)

    source_path = _store.record_path("reports", report.report_id)
    orphan_path = empty_store.record_path("reports", report.report_id)
    shutil.copyfile(source_path, orphan_path)
    orphan_path.chmod(0o600)
    with pytest.raises((KeyError, ValueError)):
        empty_store.load_report(report.report_id)


def test_service_rejects_secret_bearing_evidence_locator_without_echo(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.evidence_locator = {
        "section": "3.2",
        "api_key": "hidden-locator-secret",
        "resource_url": "https://user:password@internal.test/private",
    }

    with pytest.raises(ScienceOperationalError) as captured:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:unsafe-locator",
        )

    diagnostic = str(captured.value)
    assert "hidden-locator-secret" not in diagnostic
    assert "user:password" not in diagnostic
    assert store.reports == {}


def test_real_store_rejects_secret_locator_even_with_recomputed_report_digest(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:locator-base-report",
    )
    malicious = report.model_dump(mode="json")
    malicious["report_id"] = "sci-report:malicious-locator"
    malicious["annotations"][0]["evidence_links"][0]["locator"] = {
        "section": "3.2",
        "api_key": "hidden-locator-secret",
        "resource_url": "https://user:password@internal.test/private",
    }
    malicious["report_digest"] = sha256_digest(
        {key: value for key, value in malicious.items() if key != "report_digest"}
    )
    persisted_before = list((store.root / "reports").glob("*.json"))

    with pytest.raises(ValueError) as captured:
        store.save_report(malicious, identity=science_identity)

    diagnostic = str(captured.value)
    assert "hidden-locator-secret" not in diagnostic
    assert "user:password" not in diagnostic
    assert list((store.root / "reports").glob("*.json")) == persisted_before


@pytest.mark.parametrize(
    ("target_field", "unsafe_value"),
    [
        ("source_url", "https://example.test/private/api_key=hidden-store-value"),
        (
            "resource_url",
            "https://example.test/paper?X-Amz-Signature=hidden-store-value",
        ),
        (
            "requested_url",
            "https://example.test/private/api%5Fkey%3Dhidden-store-value",
        ),
        ("resolved_url", "https://example.test/private/bearer/hidden-store-value"),
        ("section", "api_key=hidden-store-value"),
    ],
)
def test_real_store_rejects_source_and_locator_credentials_with_valid_outer_digest(
    tmp_path: Path,
    science_identity: AuthIdentity,
    target_field: str,
    unsafe_value: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:store-url-base",
    )
    malicious = report.model_dump(mode="json")
    malicious["report_id"] = f"sci-report:unsafe-{target_field}"
    link = malicious["annotations"][0]["evidence_links"][0]
    if target_field == "source_url":
        link["url"] = unsafe_value
    else:
        link["locator"][target_field] = unsafe_value
    malicious["report_digest"] = sha256_digest(
        {key: value for key, value in malicious.items() if key != "report_digest"}
    )
    before = list((store.root / "reports").glob("*.json"))

    with pytest.raises(ValueError) as captured:
        store.save_report(malicious, identity=science_identity)

    assert "hidden-store-value" not in str(captured.value)
    assert list((store.root / "reports").glob("*.json")) == before


def test_real_store_load_rejects_canonical_report_with_credential_source_url(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:load-url-base",
    )
    injected = report.model_dump(mode="json")
    injected["report_id"] = "sci-report:credential-source-file"
    injected["annotations"][0]["evidence_links"][0]["url"] = (
        "https://example.test/private/api%5Fkey%3Dhidden-load-value"
    )
    injected["report_digest"] = sha256_digest(
        {key: value for key, value in injected.items() if key != "report_digest"}
    )
    path = store.record_path("reports", injected["report_id"])
    path.write_bytes(canonical_json_bytes(injected))
    path.chmod(0o600)

    with pytest.raises(ValueError) as captured:
        store.load_report(injected["report_id"])

    assert "hidden-load-value" not in str(captured.value)


def _serialized_exception_graph(error: BaseException) -> str:
    graph: list[dict[str, object]] = []
    pending: list[BaseException] = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        node: dict[str, object] = {
            "type": type(current).__name__,
            "args": repr(current.args),
            "dict": repr(current.__dict__),
            "traceback": "".join(traceback.format_exception(current)),
        }
        if isinstance(current, ValidationError):
            node["validation_errors"] = current.errors(include_url=False)
        graph.append(node)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return json.dumps(graph, ensure_ascii=True, default=str, sort_keys=True)


def _assert_closed_runtime_validation_error(
    error: BaseException, *, secret: str
) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert secret not in str(error)
    assert secret not in repr(error.args)
    assert secret not in repr(error.__dict__)
    assert secret not in "".join(traceback.format_exception(error))
    serialized = _serialized_exception_graph(error)
    assert "ValidationError" not in serialized
    assert secret not in serialized


def test_llm_numeric_settings_drop_input_bearing_validation_context():
    secret = "hidden-llm-validation-secret"

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
                "BOI_SCIENCE_LLM_TEMPERATURE": secret,
            }
        )

    _assert_closed_runtime_validation_error(captured.value, secret=secret)


def test_llm_response_schema_drops_input_bearing_validation_context():
    secret = "hidden-response-validation-secret"
    content = _llm_content()
    content["claims"][0]["candidate_meanings"][0]["concept_role"] = secret
    client = ScienceLLMClient(
        ScienceLLMConfig.from_env(
            {
                "BOI_SCIENCE_LLM_BASE_URL": "https://science-llm.test/v1",
                "BOI_SCIENCE_LLM_MODEL": "fixture-model",
            }
        ),
        transport=httpx.MockTransport(lambda _request: _openai_response(content)),
    )

    with pytest.raises(ScienceInterpretationUnavailable) as captured:
        client.interpret("RPM 증가 시 두께 변화", ontology_candidates=[])

    _assert_closed_runtime_validation_error(captured.value, secret=secret)


def test_authoritative_confirmation_drops_invalid_stored_record_context(
    science_identity: AuthIdentity,
):
    service, _catalog, store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    secret = "https://hidden-confirmation-validation-secret.test/v1"
    payload = confirmed.model_dump(mode="json")
    payload["prompt_version"] = secret
    malformed = SimpleNamespace(model_dump=lambda **_kwargs: payload)
    store.load_interpretation = lambda _record_id: malformed

    with pytest.raises(ScienceConfirmationRequired) as captured:
        service._authoritative_confirmation(
            confirmed.interpretation_id,
            identity=science_identity,
        )

    _assert_closed_runtime_validation_error(captured.value, secret=secret)


def test_top_level_wal_envelope_drops_input_bearing_validation_context(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    real_append = store._append_audit_event_locked

    def fail_report_audit(event):
        if event.action == "report_saved":
            raise OSError("simulated top-level WAL interruption")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_audit)
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:closed-top-level-wal",
        )
    journal_path = next((store.root / "transactions").glob("*.json"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    secret = "hidden-wal-envelope-validation-secret"
    journal["prepared_at"] = secret
    journal_path.write_bytes(canonical_json_bytes(journal))
    store.record_path("reports", pending.value.record_id).unlink()
    monkeypatch.setattr(store, "_append_audit_event_locked", real_append)

    with pytest.raises(ImmutableScienceRecordError) as captured:
        store.recover_pending_transactions()

    _assert_closed_runtime_validation_error(captured.value, secret=secret)


def _report_with_compact_locator_secret(report, *, report_id: str) -> dict[str, object]:
    injected = report.model_dump(mode="json")
    injected["report_id"] = report_id
    injected["annotations"][0]["evidence_links"][0]["locator"]["resource_url"] = (
        f"https://example.test/private/apikey{_COMPACT_OPAQUE_VALUE}"
    )
    injected["report_digest"] = sha256_digest(
        {key: value for key, value in injected.items() if key != "report_digest"}
    )
    return injected


def test_real_service_discards_pydantic_context_for_rejected_locator(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.evidence_locator = {
        "section": "3.2",
        "resource_url": (f"https://example.test/private/apikey{_COMPACT_OPAQUE_VALUE}"),
    }

    with pytest.raises(ScienceOperationalError) as captured:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:closed-service-validation",
        )

    _assert_closed_runtime_validation_error(
        captured.value, secret=_COMPACT_OPAQUE_VALUE
    )


def test_real_store_save_discards_pydantic_context_for_rejected_report(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:closed-save-base",
    )
    injected = _report_with_compact_locator_secret(
        report, report_id="sci-report:closed-save"
    )

    with pytest.raises(ValueError) as captured:
        store.save_report(injected, identity=science_identity)

    _assert_closed_runtime_validation_error(
        captured.value, secret=_COMPACT_OPAQUE_VALUE
    )


def test_real_store_load_discards_pydantic_context_for_rejected_report(
    tmp_path: Path,
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:closed-load-base",
    )
    injected = _report_with_compact_locator_secret(
        report, report_id="sci-report:closed-load"
    )
    path = store.record_path("reports", injected["report_id"])
    path.write_bytes(canonical_json_bytes(injected))
    path.chmod(0o600)

    with pytest.raises(ValueError) as captured:
        store.load_report(injected["report_id"])

    _assert_closed_runtime_validation_error(
        captured.value, secret=_COMPACT_OPAQUE_VALUE
    )


def test_wal_recovery_discards_pydantic_context_for_rejected_report(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    real_append = store._append_audit_event_locked

    def fail_report_audit(event):
        if event.action == "report_saved":
            raise OSError("simulated closed-validation audit interruption")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_audit)
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key="science-request:closed-wal-base",
        )
    journal_path = next((store.root / "transactions").glob("*.json"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    record = journal["record"]
    record["annotations"][0]["evidence_links"][0]["locator"]["resource_url"] = (
        f"https://example.test/private/apikey{_COMPACT_OPAQUE_VALUE}"
    )
    record["report_digest"] = sha256_digest(
        {key: value for key, value in record.items() if key != "report_digest"}
    )
    journal["audit"]["details"]["report_digest"] = record["report_digest"]
    journal_path.write_bytes(canonical_json_bytes(journal))
    store.record_path("reports", pending.value.record_id).unlink()
    monkeypatch.setattr(store, "_append_audit_event_locked", real_append)

    with pytest.raises(ValueError) as captured:
        store.recover_pending_transactions()

    _assert_closed_runtime_validation_error(
        captured.value, secret=_COMPACT_OPAQUE_VALUE
    )


@pytest.mark.parametrize(
    "target_field",
    ["source_url", "resource_url", "requested_url", "resolved_url"],
)
def test_real_store_direct_save_rejects_all_noncanonical_url_bypass_classes(
    tmp_path: Path,
    science_identity: AuthIdentity,
    target_field: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:direct-save-bypass-base",
    )
    before = list((store.root / "reports").glob("*.json"))

    for index, unsafe_url in enumerate(_UNSAFE_STABLE_SOURCE_URLS):
        injected = report.model_dump(mode="json")
        injected["report_id"] = f"sci-report:direct-{target_field}-{index}"
        link = injected["annotations"][0]["evidence_links"][0]
        if target_field == "source_url":
            link["url"] = unsafe_url
        else:
            link["locator"][target_field] = unsafe_url
        injected["report_digest"] = sha256_digest(
            {key: value for key, value in injected.items() if key != "report_digest"}
        )

        with pytest.raises(ValueError) as captured:
            store.save_report(injected, identity=science_identity)
        assert "hidden-canonical-value" not in str(captured.value)
        assert "hidden-boundary-value" not in str(captured.value)

    assert list((store.root / "reports").glob("*.json")) == before


@pytest.mark.parametrize(
    "target_field",
    ["source_url", "resource_url", "requested_url", "resolved_url"],
)
def test_real_store_private_load_rejects_all_noncanonical_url_bypass_classes(
    tmp_path: Path,
    science_identity: AuthIdentity,
    target_field: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:private-load-bypass-base",
    )

    for index, unsafe_url in enumerate(_UNSAFE_STABLE_SOURCE_URLS):
        injected = report.model_dump(mode="json")
        injected["report_id"] = f"sci-report:load-{target_field}-{index}"
        link = injected["annotations"][0]["evidence_links"][0]
        if target_field == "source_url":
            link["url"] = unsafe_url
        else:
            link["locator"][target_field] = unsafe_url
        injected["report_digest"] = sha256_digest(
            {key: value for key, value in injected.items() if key != "report_digest"}
        )
        path = store.record_path("reports", injected["report_id"])
        path.write_bytes(canonical_json_bytes(injected))
        path.chmod(0o600)

        with pytest.raises(ValueError) as captured:
            store.load_report(injected["report_id"])
        assert "hidden-canonical-value" not in str(captured.value)
        assert "hidden-boundary-value" not in str(captured.value)
        path.unlink()


@pytest.mark.parametrize(
    ("target_field", "unsafe_value"),
    [
        ("source_url", "https://example.test/private/api_key=hidden-wal-value"),
        (
            "resource_url",
            "https://example.test/paper?signature=hidden-wal-value",
        ),
        ("requested_url", "https://example.test/private/bearer/hidden-wal-value"),
        ("resolved_url", "https://user:hidden-wal-value@example.test/paper"),
        ("section", "token=hidden-wal-value"),
    ],
)
def test_wal_recovery_rejects_source_and_nested_locator_credentials(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    target_field: str,
    unsafe_value: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    real_append = store._append_audit_event_locked

    def fail_report_audit(event):
        if event.action == "report_saved":
            raise OSError("simulated report audit interruption")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_audit)
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=f"science-request:wal-{target_field}",
        )
    report_id = pending.value.record_id
    journal_paths = list((store.root / "transactions").glob("*.json"))
    assert len(journal_paths) == 1
    journal = json.loads(journal_paths[0].read_text(encoding="utf-8"))
    record = journal["record"]
    link = record["annotations"][0]["evidence_links"][0]
    if target_field == "source_url":
        link["url"] = unsafe_value
    else:
        link["locator"][target_field] = unsafe_value
    record["report_digest"] = sha256_digest(
        {key: value for key, value in record.items() if key != "report_digest"}
    )
    journal["audit"]["details"]["report_digest"] = record["report_digest"]
    journal_paths[0].write_bytes(canonical_json_bytes(journal))
    store.record_path("reports", report_id).unlink()
    monkeypatch.setattr(store, "_append_audit_event_locked", real_append)

    with pytest.raises(ValueError) as captured:
        store.recover_pending_transactions()

    assert "hidden-wal-value" not in str(captured.value)
    assert not store.record_path("reports", report_id).exists()


@pytest.mark.parametrize(
    "target_field",
    ["source_url", "resource_url", "requested_url", "resolved_url"],
)
def test_wal_recovery_rejects_all_noncanonical_url_bypass_classes(
    tmp_path: Path,
    science_identity: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    target_field: str,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    confirmed = _confirmed_interpretation(service, science_identity)
    real_append = store._append_audit_event_locked

    def fail_report_audit(event):
        if event.action == "report_saved":
            raise OSError("simulated canonical URL audit interruption")
        return real_append(event)

    monkeypatch.setattr(store, "_append_audit_event_locked", fail_report_audit)
    with pytest.raises(ScienceTransactionPendingError) as pending:
        service.verify_document(
            confirmed.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=f"science-request:wal-canonical-{target_field}",
        )
    report_id = pending.value.record_id
    journal_paths = list((store.root / "transactions").glob("*.json"))
    assert len(journal_paths) == 1
    original_journal = json.loads(journal_paths[0].read_text(encoding="utf-8"))
    store.record_path("reports", report_id).unlink()
    monkeypatch.setattr(store, "_append_audit_event_locked", real_append)

    for unsafe_url in _UNSAFE_STABLE_SOURCE_URLS:
        journal = json.loads(json.dumps(original_journal))
        record = journal["record"]
        link = record["annotations"][0]["evidence_links"][0]
        if target_field == "source_url":
            link["url"] = unsafe_url
        else:
            link["locator"][target_field] = unsafe_url
        record["report_digest"] = sha256_digest(
            {key: value for key, value in record.items() if key != "report_digest"}
        )
        journal["audit"]["details"]["report_digest"] = record["report_digest"]
        journal_paths[0].write_bytes(canonical_json_bytes(journal))

        with pytest.raises(ValueError) as captured:
            store.recover_pending_transactions()
        assert "hidden-canonical-value" not in str(captured.value)
        assert "hidden-boundary-value" not in str(captured.value)
        assert not store.record_path("reports", report_id).exists()


def test_closed_locator_accepts_reviewed_scientific_location_fields(
    science_identity: AuthIdentity,
):
    service, catalog, _store, _llm = _service()
    confirmed = _confirmed_interpretation(service, science_identity)
    catalog.evidence_locator = {
        "medium": "pdf",
        "resource_url": "https://example.test/reviewed-paper.pdf",
        "content_hash": sha256_digest("reviewed-paper-bytes"),
        "section": "3.2",
        "equation": "7",
        "pdf_page_index": 4,
        "exact": True,
    }
    catalog._review_current_source_identity()

    report = service.verify_document(
        confirmed.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
        idempotency_key="science-request:reviewed-locator",
    )

    assert (
        report.annotations[0].evidence_links[0].locator.model_dump(exclude_none=True)
        == catalog.evidence_locator
    )
