from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import ScienceAuthorization
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.llm import ScienceInterpretationUnavailable
from boi_api.app.science.models import ReleaseSelection, VerificationReport


class FakeService:
    def __init__(self, report: VerificationReport) -> None:
        self.report = report
        self.interpret_error: Exception | None = None
        self.calls: list[tuple[str, object]] = []

    def interpret_document(self, document: str, **kwargs):
        self.calls.append(("interpret", document))
        if self.interpret_error:
            raise self.interpret_error
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "interpretation_id": "sci-interpretation:proposal",
                "candidate_claims": [],
                "decision_impact": [],
            }
        )

    def confirm_interpretation(self, interpretation_id: str, **kwargs):
        self.calls.append(("confirm", interpretation_id))
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "interpretation_id": "sci-interpretation:confirmed",
                "candidate_claims": [],
            }
        )

    def verify_claim(
        self,
        interpretation_id: str,
        claim_id: str,
        selection: ReleaseSelection,
    ):
        self.calls.append(("verify_claim", (interpretation_id, claim_id, selection)))
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "claim_id": claim_id,
                "verdict": "INSUFFICIENT_INFORMATION",
            }
        )

    def verify_document(self, interpretation_id: str, selection, **kwargs):
        self.calls.append(("verify_document", (interpretation_id, selection)))
        return self.report

    def detect_aliases(self, document: str, **kwargs):
        self.calls.append(("detect_aliases", document))
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "document_ref": kwargs["document_ref"],
                "document_digest": sha256_digest(document),
                "matches": [],
            }
        )

    def submit_claim_candidate(self, document: str, **kwargs):
        self.calls.append(("submit_claim_candidate", (document, kwargs)))
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "interpretation_id": "sci-interpretation:submitted",
                "candidate_claims": [],
                "decision_impact": [],
                "submission_client_kind": kwargs["client_kind"],
            }
        )


class FakeStore:
    def __init__(self, report: VerificationReport) -> None:
        self.report = report

    def load_report(self, report_id: str) -> VerificationReport:
        assert report_id == self.report.report_id
        return self.report


class FakeCatalog:
    def evidence(self, evidence_id: str):
        return SimpleNamespace(
            evidence_id=evidence_id,
            source_id="sci-source:fixture",
            locator={"section": "1"},
            original_text="Reviewed original text.",
            original_text_hash="sha256:" + "1" * 64,
            reviewed_translation="검토된 번역.",
            claim_scope={"schema_version": "0.1"},
            claim_scope_hash="sha256:" + "2" * 64,
            digest="sha256:" + "3" * 64,
        )

    def source(self, source_id: str):
        return SimpleNamespace(
            source_id=source_id,
            boi_id="boi:public:science:source:fixture",
            original_url="https://example.org/source",
            content_hash="sha256:" + "4" * 64,
            digest="sha256:" + "5" * 64,
        )


def _report() -> VerificationReport:
    return VerificationReport.model_construct(
        report_id="sci-report:fixture",
        document_ref=None,
        document_digest="sha256:" + "6" * 64,
        release_selection=ReleaseSelection(foundation="sci-release:0.1.0"),
        release_digests={"sci-release:0.1.0": "sha256:" + "7" * 64},
        interpretation_ids=["sci-interpretation:confirmed"],
        confirmed_claims=[],
        verdict_packets=[],
        unresolved_ambiguities=[],
        annotations=[],
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        created_by="100001",
        report_digest="sha256:" + "8" * 64,
        operation_binding=None,
    )


def _client(
    *,
    roles: list[str] | None = None,
    can_read: bool = True,
    can_export: bool = True,
) -> tuple[TestClient, FakeService]:
    from boi_api.app.science.routes import (
        ScienceRouteDependencies,
        create_science_router,
    )

    identity = AuthIdentity(
        employee_id="100001",
        display_name="Science Admin",
        roles=roles or ["science.admin", "boi.viewer"],
    )
    report = _report()
    service = FakeService(report)
    dependencies = ScienceRouteDependencies(
        authorization=ScienceAuthorization("admin_only"),
        service_provider=lambda: service,
        runtime_store=FakeStore(report),
        catalog=FakeCatalog(),
        boi_root=None,
        current_identity_dependency=lambda: identity,
        roles_for=lambda employee_id: identity.roles,
        load_document=lambda _identity, ref: (
            "ACL-resolved canonical document" if ref == "boi:doc:fixture" else None
        ),
        can_read_boi=lambda _identity, _ref: can_read,
        can_export_boi=lambda _identity, _ref: can_export,
        can_read_report=lambda _identity, _report: can_read,
        can_export_report=lambda _identity, _report: can_export,
    )
    app = FastAPI()
    app.include_router(create_science_router(dependencies))
    return TestClient(app), service


def _claim_candidate() -> dict:
    exact = "RPM 증가 시 두께 변화"
    return {
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
        "ambiguity_ids": [],
        "candidate_meanings": [
            {
                "ambiguity_id": None,
                "concept_role": "subject",
                "surface_term": "RPM",
                "ontology_ref": "sci:binding:rpm",
                "meaning": "untrusted",
            },
            {
                "ambiguity_id": None,
                "concept_role": "relation",
                "surface_term": "증가",
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
        ],
        "decision_impact": [],
    }


def test_report_exports_share_one_canonical_report_digest() -> None:
    client, _service = _client()

    stored = client.get("/api/science/reports/sci-report:fixture")
    markdown = client.get(
        "/api/science/reports/sci-report:fixture/export?format=markdown"
    )
    pdf = client.get("/api/science/reports/sci-report:fixture/export?format=pdf")

    assert stored.status_code == 200
    assert stored.json()["report_digest"] == "sha256:" + "8" * 64
    assert markdown.headers["x-science-report-digest"] == stored.json()["report_digest"]
    assert pdf.headers["x-science-report-digest"] == stored.json()["report_digest"]
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_verification_never_accepts_a_caller_authored_claim_packet() -> None:
    client, service = _client()

    response = client.post(
        "/api/science/claims/claim:fixture/verify",
        json={
            "interpretation_id": "sci-interpretation:confirmed",
            "release_selection": {"foundation": "sci-release:0.1.0"},
            "claim_packet": {"claim_id": "forged"},
        },
    )

    assert response.status_code == 422
    assert not service.calls


def test_alias_detection_route_returns_only_exact_non_verdict_matches() -> None:
    client, service = _client()

    response = client.post(
        "/api/science/aliases/detect",
        json={
            "document": "RPM 증가 시 두께 변화",
            "request_id": "aliases-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["matches"] == []
    assert "verdict" not in response.text.lower()
    assert service.calls == [("detect_aliases", "RPM 증가 시 두께 변화")]


def test_claim_submission_route_creates_only_a_paused_interpretation() -> None:
    client, service = _client()

    response = client.post(
        "/api/science/claims/submit",
        json={
            "document": "RPM 증가 시 두께 변화",
            "client_kind": "codex",
            "candidate": _claim_candidate(),
            "idempotency_key": "claim-submit-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["interpretation_id"] == "sci-interpretation:submitted"
    assert "verdict" not in response.text.lower()
    call, (_document, kwargs) = service.calls[0]
    assert call == "submit_claim_candidate"
    assert kwargs["client_kind"] == "codex"
    assert kwargs["candidate"].normalized_claim.predicate == "increases"


@pytest.mark.parametrize("forbidden", ["verdict", "evidence", "rule"])
def test_claim_submission_rejects_client_authored_scientific_authority(
    forbidden: str,
) -> None:
    client, service = _client()
    candidate = _claim_candidate()
    candidate[forbidden] = "client-forged"

    response = client.post(
        "/api/science/claims/submit",
        json={
            "document": "RPM 증가 시 두께 변화",
            "client_kind": "claude",
            "candidate": candidate,
            "idempotency_key": f"claim-submit-forbidden-{forbidden}",
        },
    )

    assert response.status_code == 422
    assert not service.calls


def test_interpretation_failure_is_closed_and_has_no_verdict() -> None:
    client, service = _client()
    service.interpret_error = ScienceInterpretationUnavailable(
        "Science LLM is offline", diagnostic_code="transport_unavailable"
    )

    response = client.post(
        "/api/science/interpret",
        json={
            "document": "과학 주장을 검증한다.",
            "request_id": "request-001",
            "idempotency_key": "interpret-001",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "science_interpretation_unavailable",
            "diagnostic_code": "transport_unavailable",
            "message": "Scientific interpretation is temporarily unavailable.",
        }
    }
    assert "verdict" not in response.text.lower()
    assert "offline" not in response.text.lower()


def test_report_and_evidence_recheck_read_and_export_acl() -> None:
    read_denied, _service = _client(can_read=False)
    export_denied, _service = _client(can_export=False)

    evidence = read_denied.get("/api/science/evidence/sci:evidence:fixture")
    export = export_denied.get(
        "/api/science/reports/sci-report:fixture/export?format=markdown"
    )

    assert evidence.status_code == 403
    assert export.status_code == 403


def test_generic_boi_admin_does_not_gain_science_access() -> None:
    client, _service = _client(roles=["boi.admin", "boi.viewer"])

    response = client.post(
        "/api/science/interpret",
        json={
            "document": "과학 주장",
            "request_id": "request-002",
            "idempotency_key": "interpret-002",
        },
    )

    assert response.status_code == 403


def test_proposal_requires_exact_digest_and_explicit_confirmation() -> None:
    client, _service = _client()

    response = client.post(
        "/api/science/proposals",
        json={
            "proposal": {
                "domain": "lithography",
                "kind": "term_alias",
                "payload": {"alias": "PR"},
            },
            "request_digest": "sha256:" + "0" * 64,
            "idempotency_key": "proposal-001",
            "user_confirmed": True,
        },
    )

    assert response.status_code == 422


def test_release_mutation_cannot_be_implied_without_authoritative_manager() -> None:
    client, _service = _client()
    release_id = "sci-release:0.1.0"
    release_digest = "sha256:" + "7" * 64
    request_digest = sha256_digest(
        {
            "operation": "activate",
            "release_id": release_id,
            "release_digest": release_digest,
        }
    )

    response = client.post(
        f"/api/science/admin/releases/{release_id}/activate",
        json={
            "release_digest": release_digest,
            "request_digest": request_digest,
            "idempotency_key": "activate-001",
            "user_confirmed": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "science_release_manager_unavailable"
    assert "activated" not in response.text.lower()
