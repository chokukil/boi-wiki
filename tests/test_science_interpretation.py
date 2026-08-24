from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from boi_api.app.auth import AuthIdentity
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
from boi_api.app.science.service import ScienceService


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
    claim: dict[str, object] = {
        "source_span": {
            "start": 0,
            "end": 6,
            "exact": "RPM 증가",
            "prefix": "",
            "suffix": " 시",
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
        "ontology_refs": ["sci:binding:rpm"],
        "ambiguity_ids": ["ambiguity:spin-stage"],
        "candidate_meanings": [
            {
                "ambiguity_id": "ambiguity:spin-stage",
                "surface_term": "RPM",
                "ontology_ref": "sci:binding:rpm",
                "meaning": "final coat spin speed",
            }
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
    assert result.payload.claims[0].ontology_refs == ["sci:binding:rpm"]
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

    def interpret(self, document_text: str, *, ontology_candidates):
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
            ("sci:source:spin-paper", "source", "sha256:source"),
            ("sci:evidence:spin-direction", "evidence", "sha256:evidence"),
            ("sci:knowledge:spin-direction", "knowledge", "sha256:knowledge"),
            ("sci:rule:spin-direction", "rule", "sha256:rule"),
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
                component_digest="sha256:rule",
                semantic_digest=semantic_digest,
            ),
        ),
    )
    return release, release_set, rule_set


class _Catalog:
    def __init__(self):
        self.release, self.release_set, self.rule_set = _release_and_rules()
        self.resolve_release_calls = 0
        self.resolve_operational_calls = 0
        self.resolve_legacy_calls = 0
        self.operational_override = None
        self.knowledge_statement = (
            "동일한 레지스트와 공정 조건에서 final spin 속도가 증가하면 "
            "최종 막 두께는 감소한다."
        )
        self.evidence_digest = "sha256:evidence"
        self.bindings = {
            "sci:binding:rpm": SimpleNamespace(
                object_id="sci:binding:rpm",
                ontology_release_id="sci:ontology:0.1",
                concept_id="sci:concept:rpm",
                aliases=["RPM", "회전 속도"],
                meaning="final coat spin speed",
                domain="lithography",
            ),
            "sci:binding:film-thickness": SimpleNamespace(
                object_id="sci:binding:film-thickness",
                ontology_release_id="sci:ontology:0.1",
                concept_id="sci:concept:film-thickness",
                aliases=["두께", "막 두께"],
                meaning="final dry film thickness",
                domain="lithography",
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
            digest="sha256:knowledge",
            statement=self.knowledge_statement,
            evidence_refs=["sci:evidence:spin-direction"],
        )

    def evidence(self, evidence_id):
        assert evidence_id == "sci:evidence:spin-direction"
        return SimpleNamespace(
            object_id=evidence_id,
            digest=self.evidence_digest,
            source_id="sci:source:spin-paper",
            locator={"section": "3.2", "equation": "7"},
            original_text="Increasing angular speed decreases film thickness.",
            reviewed_translation="회전 속도가 증가하면 막 두께가 감소한다.",
        )

    def source(self, source_id):
        assert source_id == "sci:source:spin-paper"
        return SimpleNamespace(
            object_id=source_id,
            digest="sha256:source",
            original_url="https://example.test/spin-paper",
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
            "sci:binding:film-thickness",
        ],
        clock=lambda: datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )
    return service, catalog, store, llm


def test_interpret_document_persists_identity_bound_safe_metadata_and_catalog_meanings(
    science_identity: AuthIdentity,
):
    service, _catalog, store, llm = _service()

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        user_revision_history=[
            {"action": "selected_text", "actor_id": science_identity.employee_id}
        ],
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
    assert record.confirmed_claim_packet_digest is None
    assert record.candidate_meanings[0]["meaning"] == "final coat spin speed"
    assert llm.ontology_candidates is not None
    persisted = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
    assert "must-not-persist" not in persisted


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
    )

    claim_span = record.candidate_claims[0].source_span
    assert claim_span.start == document.index("RPM 증가")
    assert document[claim_span.start : claim_span.end] == "RPM 증가"
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
    )

    assert record.candidate_meanings[0]["meaning"] == "final coat spin speed"


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
        )

    assert store.interpretations == {}


def test_non_decisive_term_difference_is_recorded_without_pausing_verification(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, _catalog, _store, _llm = _service(content)

    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )

    claim = record.candidate_claims[0]
    assert claim.interpretation.ambiguity_ids == []
    assert claim.interpretation.user_confirmed is True
    assert record.confirmed_claim_packet_digest == sha256_digest(claim)
    assert record.decision_impact[0]["changes_outcome"] is False


def test_interpretation_rejects_an_ontology_reference_not_in_the_pinned_index(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["ontology_refs"] = ["sci:binding:invented"]
    service, _catalog, store, _llm = _service(content)

    with pytest.raises(ScienceInterpretationUnavailable, match="ontology"):
        service.interpret_document(
            "RPM 증가 시 두께 변화",
            document_ref="boi:public:science:document:fixture",
            identity=science_identity,
        )

    assert store.interpretations == {}


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
        )

    assert store.interpretations == {}


def test_verify_claim_rejects_a_catalog_result_not_matching_the_exact_selection(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, _store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )
    with pytest.raises(ScienceOperationalError, match="exact release selection"):
        service.verify_claim(
            record.candidate_claims[0],
            ReleaseSelection(foundation="sci-release:different-selection"),
        )

    assert catalog.resolve_operational_calls == 0
    assert catalog.resolve_legacy_calls == 0


def test_verify_claim_rejects_any_non_catalog_operational_object(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, _store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )
    catalog.operational_override = object()

    with pytest.raises(ScienceOperationalError, match="Catalog-issued"):
        service.verify_claim(
            record.candidate_claims[0],
            ReleaseSelection(foundation=catalog.release.release_id),
        )

    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_claim_runs_the_engine_only_with_catalog_operational_capability(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, _store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )

    verdict = service.verify_claim(
        record.candidate_claims[0],
        ReleaseSelection(foundation=catalog.release.release_id),
    )

    assert verdict.verdict is PrimaryVerdict.VIOLATION
    assert verdict.releases.combined_digest == catalog.release_set.combined_digest
    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_records_unresolved_ambiguity_without_a_verdict(
    science_identity: AuthIdentity,
):
    service, catalog, store, _llm = _service()
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )

    report = service.verify_document(
        record.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
    )

    assert report.verdict_packets == []
    assert report.unresolved_ambiguities == [
        {
            "claim_id": record.candidate_claims[0].claim_id,
            "ambiguity_ids": ["ambiguity:spin-stage"],
            "decision_impact": record.decision_impact,
        }
    ]
    assert store.report_identity is science_identity
    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_uses_only_grounded_knowledge_and_server_evidence_links(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )

    report = service.verify_document(
        record.interpretation_id,
        ReleaseSelection(foundation=catalog.release.release_id),
        identity=science_identity,
    )

    assert report.verdict_packets[0].verdict is PrimaryVerdict.VIOLATION
    assert report.annotations == [
        {
            "claim_id": record.candidate_claims[0].claim_id,
            "fact_id": "fact:sci:rule:spin-direction:contradicts",
            "text": catalog.knowledge_statement,
            "knowledge_refs": ["sci:knowledge:spin-direction"],
            "evidence_links": [
                {
                    "evidence_id": "sci:evidence:spin-direction",
                    "source_id": "sci:source:spin-paper",
                    "url": "https://example.test/spin-paper",
                    "locator": {"section": "3.2", "equation": "7"},
                }
            ],
        }
    ]
    assert report.report_digest == sha256_digest(
        report.model_dump(mode="json", exclude={"report_digest"})
    )
    assert store.reports[report.report_id] == report
    assert catalog.resolve_operational_calls == 1
    assert catalog.resolve_legacy_calls == 0


def test_verify_document_fails_if_a_decisive_fact_has_no_approved_statement(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )
    catalog.knowledge_statement = ""

    with pytest.raises(ScienceOperationalError, match="grounded statement"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )
    assert store.reports == {}


def test_verify_document_rejects_evidence_not_matching_the_pinned_digest(
    science_identity: AuthIdentity,
):
    content = _llm_content()
    content["claims"][0]["decision_impact"][0]["changes_outcome"] = False
    service, catalog, store, _llm = _service(content)
    record = service.interpret_document(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
    )
    catalog.evidence_digest = "sha256:changed-after-release"

    with pytest.raises(ScienceOperationalError, match="release digest"):
        service.verify_document(
            record.interpretation_id,
            ReleaseSelection(foundation=catalog.release.release_id),
            identity=science_identity,
        )

    assert store.reports == {}
