from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import ScienceAuthorization
from boi_api.app.science.anchors import SpanAnchorError, resolve_anchor
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.llm import (
    ScienceInterpretationPayload,
    ScienceInterpretationUnavailable,
    ScienceLLMClient,
    ScienceLLMConfig,
    ScienceLLMResult,
)
from boi_api.app.science.models import (
    PrimaryVerdict,
    ReleaseSelection,
    ResolvedComponent,
    ResolvedRelease,
    ResolvedReleaseSet,
    SourceSpan,
)
from boi_api.app.science.operational import _issue_operational_verification
from boi_api.app.science.rules import ReleasedRule, ResolvedRuleSet, VerificationRule
from boi_api.app.science.service import (
    ScienceConfirmationRequired,
    ScienceIdempotencyConflict,
    ScienceService,
)
from boi_api.app.science.storage import (
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
            "process_stage": "final_spin",
            "material_state": "liquid_film",
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
    assert body["temperature"] == 0.0
    assert result.payload.claims[0].ontology_refs == [
        "sci:binding:rpm",
        "sci:binding:increases",
        "sci:binding:film-thickness",
    ]
    assert result.response_digest.startswith("sha256:")
    assert "secret-token" not in repr(result)
    assert "science-llm.test" not in repr(result)


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
        content_hash=f"sha256:{release_id}",
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

    def evidence(self, evidence_id):
        assert evidence_id == "sci:evidence:spin-direction"
        original_text = "Increasing angular speed decreases film thickness."
        return SimpleNamespace(
            object_id=evidence_id,
            digest=self.evidence_digest,
            source_id="sci:source:spin-paper",
            locator={"section": "3.2", "equation": "7"},
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
        clock=lambda: datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )
    return service, catalog, store, llm


def _real_service(tmp_path: Path, content: dict[str, object] | None = None):
    catalog = _Catalog()
    store = ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=lambda _identity: ["science.admin"],
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
    return service.confirm_interpretation(
        proposal.interpretation_id,
        claim_ids=[proposal.candidate_claims[0].claim_id],
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

    with pytest.raises(ValueError, match="credential or endpoint"):
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

    with pytest.raises(ValueError, match="credential or endpoint"):
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

    with pytest.raises(ValueError, match="model_id"):
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
        )

    confirmed = service.confirm_interpretation(
        proposal.interpretation_id,
        claim_ids=[proposal.candidate_claims[0].claim_id],
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
    assert event.source_interpretation_id == proposal.interpretation_id
    verdict = service.verify_claim(
        confirmed.interpretation_id,
        confirmed.candidate_claims[0].claim_id,
        ReleaseSelection(foundation=catalog.release.release_id),
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
    assert link.locator == {"section": "3.2", "equation": "7"}
    assert link.source_lookup.versioned_path == ("public/science/sources/spin-paper.md")
    assert link.source_lookup.acl_policy == "acl:public"
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


@pytest.mark.parametrize(
    "source_url",
    [
        "https://user:password@example.test/spin-paper",
        "https://example.test/spin-paper?accessToken=hidden-value",
    ],
)
def test_verify_document_rejects_credential_bearing_source_urls(
    science_identity: AuthIdentity,
    source_url: str,
):
    service, catalog, store, _llm = _service()
    record = _confirmed_interpretation(service, science_identity)
    catalog.source_url = source_url

    with pytest.raises(ScienceOperationalError, match="approved source link"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
            idempotency_key=REPORT_KEY,
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
    with pytest.raises(ScienceIdempotencyConflict):
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
