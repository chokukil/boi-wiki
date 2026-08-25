from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import ScienceAuthorization
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.llm import ScienceInterpretationUnavailable
from boi_api.app.science.models import ReleaseSelection, VerificationReport
from boi_api.app.science.storage import ScienceRuntimeStore


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

    def issue_user_revision_challenge(self, document: str, **kwargs):
        self.calls.append(("issue_user_revision_challenge", (document, kwargs)))
        return {
            "challenge_id": "sci-user-action:user-revision-test-token-0001",
            "operation": "submit_user_revision",
            "request_digest": "sha256:" + "a" * 64,
            "expires_at": "2026-08-25T04:05:00Z",
        }

    def commit_user_revision(self, challenge_id: str, **kwargs):
        self.calls.append(("commit_user_revision", (challenge_id, kwargs)))
        return SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "interpretation_id": "sci-interpretation:user-revision",
                "candidate_claims": [],
                "decision_impact": [],
                "submission_client_kind": "user",
            }
        )

    def issue_confirmation_challenge(self, interpretation_id: str, **kwargs):
        self.calls.append(
            ("issue_confirmation_challenge", (interpretation_id, kwargs))
        )
        return {
            "challenge_id": "sci-user-action:confirmation-test-token-0001",
            "operation": "confirm_interpretation",
            "request_digest": "sha256:" + "b" * 64,
            "expires_at": "2026-08-25T04:05:00Z",
        }

    def commit_interpretation_confirmation(self, challenge_id: str, **kwargs):
        self.calls.append(
            ("commit_interpretation_confirmation", (challenge_id, kwargs))
        )
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
        **_kwargs,
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
        self.user_action_challenges: dict[str, SimpleNamespace] = {}

    def load_report(self, report_id: str) -> VerificationReport:
        assert report_id == self.report.report_id
        return self.report

    def issue_user_action_challenge(self, **kwargs):
        challenge = SimpleNamespace(
            challenge_id=(
                "sci-user-action:00000000-0000-4000-8000-000000000001"
            ),
            **kwargs,
        )
        self.user_action_challenges[challenge.challenge_id] = challenge
        return challenge

    def consume_user_action_challenge(self, challenge_id: str, **kwargs):
        challenge = self.user_action_challenges.pop(challenge_id)
        assert challenge.operation == kwargs["operation"]
        assert challenge.actor_id == kwargs["actor_id"]
        assert challenge.request_digest == kwargs["request_digest"]
        return challenge


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
    employee_id: str = "100001",
    runtime_store: object | None = None,
    auth_source: str = "dev",
) -> tuple[TestClient, FakeService]:
    from boi_api.app.science.routes import (
        ScienceRouteDependencies,
        create_science_router,
    )

    identity = AuthIdentity(
        employee_id=employee_id,
        display_name="Science Admin",
        roles=roles or ["science.admin", "boi.viewer"],
        auth_source=auth_source,
    )
    report = _report()
    service = FakeService(report)
    dependencies = ScienceRouteDependencies(
        authorization=ScienceAuthorization("admin_only"),
        service_provider=lambda: service,
        runtime_store=runtime_store or FakeStore(report),
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


def test_science_rest_rejects_service_token_identity_spoofing():
    client, service = _client(auth_source="service_token")

    response = client.post(
        "/api/science/aliases/detect",
        json={"document": "RPM 증가", "request_id": "service-token-spoof"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "science_access_denied"
    assert service.calls == []


def test_standalone_evidence_lookup_never_claims_operational_eligibility():
    client, _service = _client()

    response = client.get("/api/science/evidence/sci:evidence:fixture")

    assert response.status_code == 200
    payload = response.json()
    assert payload["authority_scope"] == "standalone_lookup_non_authoritative"
    assert payload["operational_eligibility"] is False
    assert payload["release_binding"] is None


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
    assert markdown.headers["x-science-export-digest"] == (
        "sha256:" + hashlib.sha256(markdown.content).hexdigest()
    )
    assert pdf.headers["x-science-export-digest"] == (
        "sha256:" + hashlib.sha256(pdf.content).hexdigest()
    )
    assert (
        markdown.headers["x-science-export-digest"]
        != pdf.headers["x-science-export-digest"]
    )
    assert (
        markdown.headers["x-science-export-digest"]
        != markdown.headers["x-science-report-digest"]
    )
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


def test_generic_claim_submission_cannot_forge_a_trusted_user_revision() -> None:
    """Catches reintroducing caller-controlled client_kind=user as trust."""

    client, service = _client()

    response = client.post(
        "/api/science/claims/submit",
        json={
            "document": "RPM 증가 시 두께 변화",
            "client_kind": "user",
            "candidate": _claim_candidate(),
            "idempotency_key": "forged-user-revision",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "science_confirmation_or_identity_conflict"
    )
    assert service.calls == []


def test_web_user_revision_uses_an_actor_bound_one_time_challenge() -> None:
    """Catches bypassing the server-issued UI revision ceremony."""

    client, service = _client()
    challenge = client.post(
        "/api/science/user-revisions/challenge",
        json={
            "document": "RPM 증가 시 두께 변화",
            "candidate": _claim_candidate(),
            "idempotency_key": "trusted-user-revision",
        },
    )

    assert challenge.status_code == 200
    challenge_id = challenge.json()["challenge_id"]
    committed = client.post(
        "/api/science/user-revisions/commit",
        json={
            "challenge_id": challenge_id,
            "document": "RPM 증가 시 두께 변화",
            "candidate": _claim_candidate(),
            "idempotency_key": "trusted-user-revision",
        },
    )

    assert committed.status_code == 200
    assert committed.json()["submission_client_kind"] == "user"
    assert [call[0] for call in service.calls] == [
        "issue_user_revision_challenge",
        "commit_user_revision",
    ]
    _name, (_document, issue_kwargs) = service.calls[0]
    assert issue_kwargs["identity"].employee_id == "100001"
    assert issue_kwargs["candidate"].normalized_claim.predicate == "increases"
    _name, (committed_challenge_id, commit_kwargs) = service.calls[1]
    assert committed_challenge_id == challenge_id
    assert commit_kwargs["identity"].employee_id == "100001"


def test_bearer_identity_cannot_issue_or_commit_a_trusted_ui_challenge() -> None:
    """Catches an agent bearer replaying the browser-only human-action route."""

    client, service = _client(auth_source="dev_bearer")
    payload = {
        "document": "RPM 증가 시 두께 변화",
        "candidate": _claim_candidate(),
        "idempotency_key": "bearer-user-revision",
    }

    issued = client.post(
        "/api/science/user-revisions/challenge",
        headers={"authorization": "Bearer agent-token"},
        json=payload,
    )
    committed = client.post(
        "/api/science/user-revisions/commit",
        headers={"authorization": "Bearer agent-token"},
        json={
            **payload,
            "challenge_id": "sci-user-action:00000000-0000-4000-8000-000000000000",
        },
    )

    assert issued.status_code == 403
    assert committed.status_code == 403
    assert service.calls == []


def test_confirmation_requires_a_server_issued_one_time_challenge() -> None:
    """Catches treating user_confirmed=true as proof of human confirmation."""

    client, service = _client()
    forged = client.post(
        "/api/science/interpretations/sci-interpretation:proposal/confirm",
        json={
            "claim_ids": ["sci-claim:one"],
            "idempotency_key": "forged-confirmation",
            "user_confirmed": True,
        },
    )

    assert forged.status_code == 422
    assert service.calls == []

    challenge = client.post(
        "/api/science/interpretations/sci-interpretation:proposal/confirmation-challenge",
        json={
            "claim_ids": ["sci-claim:one"],
            "idempotency_key": "trusted-confirmation",
        },
    )
    assert challenge.status_code == 200
    challenge_id = challenge.json()["challenge_id"]

    confirmed = client.post(
        "/api/science/interpretations/sci-interpretation:proposal/confirm",
        json={
            "challenge_id": challenge_id,
            "claim_ids": ["sci-claim:one"],
            "idempotency_key": "trusted-confirmation",
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["interpretation_id"] == "sci-interpretation:confirmed"
    assert [call[0] for call in service.calls] == [
        "issue_confirmation_challenge",
        "commit_interpretation_confirmation",
    ]


def test_raw_claim_route_keeps_stable_document_identity_and_forwards_lineage() -> None:
    client, service = _client()
    original_text = "RPM 증가 시 두께 변화"

    def trusted_user_revision(payload: dict) -> object:
        challenge = client.post(
            "/api/science/user-revisions/challenge",
            json=payload,
        )
        assert challenge.status_code == 200
        return client.post(
            "/api/science/user-revisions/commit",
            json={**payload, "challenge_id": challenge.json()["challenge_id"]},
        )

    first = trusted_user_revision(
        {
            "document": original_text,
            "candidate": _claim_candidate(),
            "idempotency_key": "claim-submit-lineage-first",
        },
    )
    assert first.status_code == 200
    _call, (_document, first_kwargs) = service.calls[-1]
    logical_ref = first_kwargs["document_ref"]
    assert logical_ref.startswith("boi:submitted:")

    same_document_retry = trusted_user_revision(
        {
            "document": original_text,
            "candidate": _claim_candidate(),
            "idempotency_key": "claim-submit-lineage-same-document",
        },
    )
    assert same_document_retry.status_code == 200
    _call, (_document, retry_kwargs) = service.calls[-1]
    assert retry_kwargs["document_ref"] == logical_ref

    second = trusted_user_revision(
        {
            "document": f"검토: {original_text}",
            "candidate": _claim_candidate(),
            "supersedes_claim_id": "sci-claim:prior",
            "source_lineage": {
                "document_ref": logical_ref,
                "document_digest": sha256_digest(original_text),
            },
            "idempotency_key": "claim-submit-lineage-second",
        },
    )

    assert second.status_code == 200
    _call, (_document, second_kwargs) = service.calls[-1]
    assert second_kwargs["document_ref"] == logical_ref
    assert second_kwargs["source_lineage_document_ref"] == logical_ref
    assert second_kwargs["source_lineage_document_digest"] == sha256_digest(
        original_text
    )

    canonical_revision = trusted_user_revision(
        {
            "document": f"Wiki 수정: {original_text}",
            "candidate": _claim_candidate(),
            "supersedes_claim_id": "sci-claim:wiki-prior",
            "source_lineage": {
                "document_ref": "boi:public:science:document:fixture",
                "document_digest": sha256_digest(original_text),
            },
            "idempotency_key": "claim-submit-wiki-lineage-second",
        },
    )

    assert canonical_revision.status_code == 200
    _call, (_document, canonical_kwargs) = service.calls[-1]
    assert canonical_kwargs["document_ref"] == (
        "boi:submitted:"
        "03907111e63f944210b94ae1898d02749291ad4b7e4a25aa548997551073fdf5"
    )
    assert canonical_kwargs["document_ref"] != canonical_kwargs["source_lineage_document_ref"]
    assert (
        canonical_kwargs["source_lineage_document_ref"]
        == "boi:public:science:document:fixture"
    )


@pytest.mark.parametrize(
    "payload_update",
    [
        {"source_lineage": {"document_ref": "boi:submitted:x", "document_digest": "sha256:" + "1" * 64}},
        {"supersedes_claim_id": "sci-claim:prior", "source_lineage": {"document_ref": "external:science:document:fixture", "document_digest": "sha256:" + "1" * 64}},
    ],
)
def test_raw_claim_route_rejects_unbound_or_non_boi_lineage(
    payload_update: dict,
) -> None:
    client, service = _client()
    payload = {
        "document": "RPM 증가 시 두께 변화",
        "client_kind": "user",
        "candidate": _claim_candidate(),
        "idempotency_key": "claim-submit-invalid-lineage",
        **payload_update,
    }

    response = client.post("/api/science/claims/submit", json=payload)

    assert response.status_code == 422
    assert not service.calls


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


def test_proposal_exact_retry_returns_one_immutable_record_and_one_audit(
    tmp_path,
) -> None:
    store = ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization("admin_only"),
        roles_for=lambda _identity: ["science.admin"],
    )
    client, _service = _client(runtime_store=store)
    proposal = {
        "domain": "lithography",
        "kind": "term_alias",
        "payload": {"alias": "PR"},
    }
    raw_key = "proposal-exact-retry-001"
    request = {
        "proposal": proposal,
        "request_digest": sha256_digest(proposal),
        "idempotency_key": raw_key,
        "user_confirmed": True,
    }

    first = client.post("/api/science/proposals", json=request)
    second = client.post("/api/science/proposals", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    rows = [
        json.loads(line)
        for line in store.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["action"] for row in rows].count("proposal_saved") == 1
    assert first.json()["idempotency_key_digest"] == sha256_digest(raw_key)
    assert first.json()["request_digest"] == request["request_digest"]
    persisted_bytes = b"".join(
        path.read_bytes() for path in store.root.rglob("*") if path.is_file()
    )
    assert raw_key.encode() not in persisted_bytes


@pytest.mark.parametrize(
    "changed_proposal",
    [
        {
            "domain": "materials",
            "kind": "term_alias",
            "payload": {"alias": "PR"},
        },
        {
            "domain": "lithography",
            "kind": "term_meaning",
            "payload": {"alias": "PR"},
        },
        {
            "domain": "lithography",
            "kind": "term_alias",
            "payload": {"alias": "photoresist"},
        },
    ],
)
def test_proposal_key_reuse_with_changed_request_returns_conflict(
    tmp_path,
    changed_proposal: dict[str, object],
) -> None:
    store = ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization("admin_only"),
        roles_for=lambda _identity: ["science.admin"],
    )
    client, _service = _client(runtime_store=store)
    first_proposal = {
        "domain": "lithography",
        "kind": "term_alias",
        "payload": {"alias": "PR"},
    }
    first = client.post(
        "/api/science/proposals",
        json={
            "proposal": first_proposal,
            "request_digest": sha256_digest(first_proposal),
            "idempotency_key": "proposal-conflict-001",
            "user_confirmed": True,
        },
    )
    conflict = client.post(
        "/api/science/proposals",
        json={
            "proposal": changed_proposal,
            "request_digest": sha256_digest(changed_proposal),
            "idempotency_key": "proposal-conflict-001",
            "user_confirmed": True,
        },
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == (
        "science_confirmation_or_identity_conflict"
    )


def test_proposal_key_reuse_by_another_actor_returns_conflict(tmp_path) -> None:
    store = ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization("admin_only"),
        roles_for=lambda _identity: ["science.admin"],
    )
    first_client, _service = _client(
        employee_id="100001",
        runtime_store=store,
    )
    second_client, _service = _client(
        employee_id="100002",
        runtime_store=store,
    )
    proposal = {
        "domain": "lithography",
        "kind": "term_alias",
        "payload": {"alias": "PR"},
    }
    request = {
        "proposal": proposal,
        "request_digest": sha256_digest(proposal),
        "idempotency_key": "proposal-actor-conflict-001",
        "user_confirmed": True,
    }

    assert first_client.post("/api/science/proposals", json=request).status_code == 200
    conflict = second_client.post("/api/science/proposals", json=request)

    assert conflict.status_code == 409


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

    mutation = {
        "release_digest": release_digest,
        "request_digest": request_digest,
        "idempotency_key": "activate-001",
    }
    forged = client.post(
        f"/api/science/admin/releases/{release_id}/activate",
        json={**mutation, "user_confirmed": True},
    )
    assert forged.status_code == 422
    challenge = client.post(
        f"/api/science/admin/releases/{release_id}/activate-challenge",
        json=mutation,
    )
    assert challenge.status_code == 200
    response = client.post(
        f"/api/science/admin/releases/{release_id}/activate",
        json={
            **mutation,
            "challenge_id": challenge.json()["challenge_id"],
            "user_confirmed": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "science_release_manager_unavailable"
    assert "activated" not in response.text.lower()


def test_release_mutation_rejects_admin_bearer_without_trusted_browser_session() -> None:
    """Catches user_confirmed=true being treated as human Admin activation."""

    client, _service = _client(auth_source="dev_bearer")
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
        headers={"authorization": "Bearer admin-agent"},
        json={
            "release_digest": release_digest,
            "request_digest": request_digest,
            "idempotency_key": "bearer-activate-001",
            "user_confirmed": True,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "science_access_denied"
