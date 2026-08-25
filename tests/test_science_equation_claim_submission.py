from __future__ import annotations

from types import MethodType, SimpleNamespace

import pytest
from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.anchors import SpanAnchorError
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.equations import ScienceEquationKnowledge
from boi_api.app.science.llm import ScienceInterpretationPayload
from boi_api.app.science.models import FormulaInterpretationRecord, SourceSpan
from boi_api.app.science.service import ScienceConfirmationRequired
from tests.test_science_equations import valid_equation_payload
from tests.test_science_interpretation import (
    _llm_content,
    _real_service,
    _service,
)
from tests.test_science_api import _client


DOCUMENT = "RPM 증가 시 두께 변화; V = I R"
FORMULA = "V = I R"


@pytest.fixture
def science_identity() -> AuthIdentity:
    return AuthIdentity(
        employee_id="100002",
        display_name="Science Pilot",
        roles=["boi.viewer", "science.power_user:lithography"],
    )


def _span(text: str, exact: str, *, start: int | None = None) -> dict[str, object]:
    resolved_start = text.index(exact) if start is None else start
    return {
        "start": resolved_start,
        "end": resolved_start + len(exact),
        "exact": exact,
        "prefix": text[max(0, resolved_start - 4) : resolved_start],
        "suffix": text[resolved_start + len(exact) : resolved_start + len(exact) + 4],
    }


def _install_equation_catalog(service, catalog, *, ambiguous_v: bool = False):
    equation = ScienceEquationKnowledge.model_validate(valid_equation_payload())
    binding_rows = {
        "sci:binding:voltage": ("sci:concept:voltage", "V", "voltage"),
        "sci:binding:electric-current": (
            "sci:concept:electric-current",
            "I",
            "electric current",
        ),
        "sci:binding:resistance": (
            "sci:concept:resistance",
            "R",
            "electrical resistance",
        ),
    }
    if ambiguous_v:
        binding_rows["sci:binding:volume"] = (
            "sci:concept:volume",
            "V",
            "physical volume",
        )
    for binding_id, (concept_id, alias, meaning) in binding_rows.items():
        catalog.bindings[binding_id] = SimpleNamespace(
            object_id=binding_id,
            digest=sha256_digest(binding_id),
            ontology_release_id="sci:ontology:0.1",
            concept_id=concept_id,
            aliases=[alias],
            meaning=meaning,
            domain="general-science",
        )
    service.ontology_binding_ids = (
        *service.ontology_binding_ids,
        *binding_rows,
    )

    def equation_lookup(_catalog, equation_id: str):
        if equation_id != equation.equation_id:
            from boi_api.app.science.exceptions import ScienceCatalogError

            raise ScienceCatalogError(f"unknown Science Equation: {equation_id}")
        return SimpleNamespace(
            knowledge_id="sci:knowledge:ohms-law",
            knowledge_digest=sha256_digest("ohms-law"),
            equation=equation,
        )

    catalog.equation = MethodType(equation_lookup, catalog)
    return equation


def _candidate_payload(equation: ScienceEquationKnowledge) -> dict[str, object]:
    content = _llm_content()
    claim = content["claims"][0]
    claim["source_span"] = _span(DOCUMENT, DOCUMENT)
    formula_start = DOCUMENT.index(FORMULA)
    symbols = []
    bindings = {
        "voltage": ("V", "sci:concept:voltage", "voltage", "sci:binding:voltage"),
        "current": (
            "I",
            "sci:concept:electric-current",
            "electric_current",
            "sci:binding:electric-current",
        ),
        "resistance": (
            "R",
            "sci:concept:resistance",
            "electrical_resistance",
            "sci:binding:resistance",
        ),
    }
    for variable_id, (symbol, concept_ref, quantity_kind, ontology_ref) in bindings.items():
        symbol_start = DOCUMENT.index(symbol, formula_start)
        symbols.append(
            {
                "variable_id": variable_id,
                "symbol": symbol,
                "source_span": _span(DOCUMENT, symbol, start=symbol_start),
                "concept_ref": concept_ref,
                "quantity_kind": quantity_kind,
                "unit": None,
                "ontology_ref": ontology_ref,
            }
        )
    claim["formula_candidates"] = [
        {
            "formula_span": _span(DOCUMENT, FORMULA),
            "semantic_expression": equation.semantic_expression.model_dump(
                mode="json", exclude_unset=True
            ),
            "proposed_equation_id": equation.equation_id,
            "proposed_equation_digest": equation.equation_digest,
            "symbol_candidates": symbols,
            "condition_candidates": [],
            "sign_convention_candidate": None,
            "ontology_refs": [row[3] for row in bindings.values()],
        }
    ]
    return claim


def test_exact_equation_candidate_is_persisted_only_as_untrusted_interpretation(
    science_identity,
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [_candidate_payload(equation)]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:equation-exact",
    )

    persisted = record.formula_candidates[0]
    assert persisted.claim_id == record.candidate_claims[0].claim_id
    assert persisted.formula_span.exact == FORMULA
    assert persisted.semantic_expression_digest == sha256_digest(
        equation.semantic_expression.model_dump(mode="json", exclude_unset=True)
    )
    assert persisted.catalog_match_status == "exact_candidate_match"
    assert persisted.verdict_authority is False
    assert record.decision_impact[0].issue_codes == ["USER_CONFIRMATION_REQUIRED"]


def test_formula_span_must_resolve_exactly_inside_claim(science_identity):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    payload["formula_candidates"][0]["formula_span"] = {
        **_span(DOCUMENT, FORMULA),
        "exact": "V = I X",
    }
    payload["formula_candidates"][0]["formula_span"]["end"] = (
        payload["formula_candidates"][0]["formula_span"]["start"]
        + len("V = I X")
    )
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    with pytest.raises(SpanAnchorError, match="anchor mismatch"):
        service.submit_claim_candidate(
            DOCUMENT,
            document_ref="boi:public:science:document:equation-fixture",
            identity=science_identity,
            client_kind="codex",
            candidate=candidate,
            idempotency_key="science-request:bad-formula-span",
        )


def test_formula_and_symbol_spans_are_reanchored_from_exact_selection(
    science_identity,
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [_candidate_payload(equation)]}
    ).claims[0]
    full_document = f"서론: {DOCUMENT} 결론"
    selection_start = full_document.index(DOCUMENT)
    selection = {
        "start": selection_start,
        "end": selection_start + len(DOCUMENT),
        "exact": DOCUMENT,
        "prefix": full_document[max(0, selection_start - 4) : selection_start],
        "suffix": full_document[
            selection_start + len(DOCUMENT) : selection_start + len(DOCUMENT) + 4
        ],
    }

    record = service.submit_claim_candidate(
        full_document,
        document_ref="boi:public:science:document:equation-selection",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:equation-selection",
        selection_anchor=SourceSpan.model_validate(selection),
    )

    persisted = record.formula_candidates[0]
    assert persisted.formula_span.start == full_document.index(FORMULA)
    assert all(
        full_document[symbol.source_span.start : symbol.source_span.end]
        == symbol.symbol
        for symbol in persisted.symbol_candidates
    )


def test_overlapping_formula_candidates_block_confirmation(science_identity):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    payload["formula_candidates"].append(payload["formula_candidates"][0].copy())
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="claude",
        candidate=candidate,
        idempotency_key="science-request:overlap-formula",
    )

    assert "FORMULA_SPAN_OVERLAP" in record.decision_impact[0].issue_codes
    with pytest.raises(ScienceConfirmationRequired):
        service.confirm_interpretation(
            record.interpretation_id,
            claim_ids=[record.candidate_claims[0].claim_id],
            identity=science_identity,
            idempotency_key="science-request:overlap-confirm",
        )


def test_invented_variable_is_rejected_against_proposed_equation(science_identity):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    payload["formula_candidates"][0]["symbol_candidates"].append(
        {
            "variable_id": "invented_power",
            "symbol": "V",
            "source_span": _span(DOCUMENT, "V", start=DOCUMENT.index(FORMULA)),
            "concept_ref": "sci:concept:voltage",
            "quantity_kind": "power",
            "unit": None,
            "ontology_ref": "sci:binding:voltage",
        }
    )
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:invented-variable",
    )

    assert "FORMULA_UNDECLARED_VARIABLE" in record.decision_impact[0].issue_codes
    assert record.formula_candidates[0].catalog_match_status == "mismatch"


def test_missing_symbol_binding_blocks_an_incomplete_formula(science_identity):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    payload["formula_candidates"][0]["symbol_candidates"] = payload[
        "formula_candidates"
    ][0]["symbol_candidates"][:-1]
    payload["formula_candidates"][0]["ontology_refs"] = payload[
        "formula_candidates"
    ][0]["ontology_refs"][:-1]
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:missing-formula-symbol",
    )

    assert "FORMULA_SYMBOL_INCOMPLETE" in record.decision_impact[0].issue_codes
    assert record.formula_candidates[0].catalog_match_status == "mismatch"


def test_unknown_equation_reference_is_retained_but_never_authoritative(
    science_identity,
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    formula = payload["formula_candidates"][0]
    formula["proposed_equation_id"] = "sci:equation:not-registered"
    formula["proposed_equation_digest"] = "sha256:" + "f" * 64
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:unknown-equation",
    )

    assert "UNKNOWN_EQUATION_REF" in record.decision_impact[0].issue_codes
    persisted = record.formula_candidates[0]
    assert persisted.catalog_match_status == "unknown_equation"
    assert persisted.verdict_authority is False


def test_v_voltage_vs_volume_requires_confirmation_when_equation_is_not_pinned(
    science_identity,
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog, ambiguous_v=True)
    payload = _candidate_payload(equation)
    formula = payload["formula_candidates"][0]
    formula["proposed_equation_id"] = None
    formula["proposed_equation_digest"] = None
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="user",
        candidate=candidate,
        idempotency_key="science-request:v-ambiguity",
    )

    assert "FORMULA_SYMBOL_AMBIGUITY" in record.decision_impact[0].issue_codes
    assert record.formula_candidates[0].catalog_match_status == "not_proposed"


@pytest.mark.parametrize("forbidden", ["verdict", "rule", "evidence", "locator"])
def test_formula_candidate_schema_rejects_client_authored_authority(forbidden: str):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    payload = _candidate_payload(equation)
    payload["formula_candidates"][0][forbidden] = "forged"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ScienceInterpretationPayload.model_validate({"claims": [payload]})


def test_rest_boundary_forwards_only_the_typed_formula_candidate():
    client, api_service = _client()
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate = _candidate_payload(equation)

    response = client.post(
        "/api/science/claims/submit",
        json={
            "document": DOCUMENT,
            "client_kind": "codex",
            "candidate": candidate,
            "idempotency_key": "claim-submit-equation-rest",
        },
    )

    assert response.status_code == 200
    _call, (_document, kwargs) = api_service.calls[-1]
    received = kwargs["candidate"].formula_candidates[0]
    assert received.formula_span.exact == FORMULA
    assert received.proposed_equation_id == equation.equation_id
    assert received.semantic_expression == equation.semantic_expression


def test_rest_boundary_rejects_nested_formula_verdict_and_evidence():
    client, api_service = _client()
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate = _candidate_payload(equation)
    candidate["formula_candidates"][0]["verdict"] = "CONSISTENT"
    candidate["formula_candidates"][0]["evidence"] = ["forged"]

    response = client.post(
        "/api/science/claims/submit",
        json={
            "document": DOCUMENT,
            "client_kind": "claude",
            "candidate": candidate,
            "idempotency_key": "claim-submit-equation-forged",
        },
    )

    assert response.status_code == 422
    assert not api_service.calls


@pytest.mark.parametrize(
    "context_update",
    [
        {"condition_candidates": [{"condition_id": "temperature", "value": 25}]},
        {"sign_convention_candidate": "Positive current enters the positive terminal."},
        {"symbol_unit": "volt"},
    ],
    ids=["condition", "sign-convention", "unit"],
)
def test_non_user_formula_context_requires_explicit_user_revision(
    science_identity,
    context_update: dict[str, object],
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate_payload = _candidate_payload(equation)
    formula = candidate_payload["formula_candidates"][0]
    if "symbol_unit" in context_update:
        formula["symbol_candidates"][0]["unit"] = context_update["symbol_unit"]
    else:
        formula.update(context_update)
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [candidate_payload]}
    ).claims[0]

    record = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key=f"science-request:formula-context-{next(iter(context_update))}",
    )

    assert "FORMULA_CONTEXT_REQUIRES_USER_REVISION" in (
        record.decision_impact[0].issue_codes
    )
    assert record.formula_candidates[0].verdict_authority is False


def test_claim_without_formula_remains_backward_compatible(science_identity):
    service, _catalog, _store, _llm = _service()
    candidate = ScienceInterpretationPayload.model_validate(_llm_content()).claims[0]

    record = service.submit_claim_candidate(
        "RPM 증가 시 두께 변화",
        document_ref="boi:public:science:document:fixture",
        identity=science_identity,
        client_kind="qwen",
        candidate=candidate,
        idempotency_key="science-request:no-formula-compatible",
    )

    assert record.formula_candidates == []
    assert record.decision_impact[0].issue_codes == ["USER_CONFIRMATION_REQUIRED"]


def test_formula_interpretation_round_trips_through_immutable_runtime_store(
    tmp_path,
    science_identity,
):
    service, catalog, store, _llm = _real_service(tmp_path)
    equation = _install_equation_catalog(service, catalog)
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [_candidate_payload(equation)]}
    ).claims[0]

    saved = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:equation-store-round-trip",
    )
    loaded = store.load_interpretation(saved.interpretation_id)

    assert loaded.formula_candidates == saved.formula_candidates
    assert loaded.formula_candidates[0].catalog_match_status == (
        "exact_candidate_match"
    )
    assert loaded.formula_candidates[0].verdict_authority is False


def test_persisted_formula_candidate_digest_detects_interpretation_drift(
    science_identity,
):
    service, catalog, _store, _llm = _service()
    equation = _install_equation_catalog(service, catalog)
    candidate = ScienceInterpretationPayload.model_validate(
        {"claims": [_candidate_payload(equation)]}
    ).claims[0]
    saved = service.submit_claim_candidate(
        DOCUMENT,
        document_ref="boi:public:science:document:equation-fixture",
        identity=science_identity,
        client_kind="codex",
        candidate=candidate,
        idempotency_key="science-request:equation-record-digest",
    )
    payload = saved.formula_candidates[0].model_dump(mode="json")
    payload["symbol_candidates"][0]["quantity_kind"] = "volume"

    with pytest.raises(ValidationError, match="formula candidate digest"):
        FormulaInterpretationRecord.model_validate(payload)
