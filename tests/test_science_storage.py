from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
)
from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import (
    ClaimPacket,
    InterpretationRecord,
    ReleaseSelection,
    ScienceOperationBinding,
    VerdictPacket,
    VerificationReport,
)
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
    ScienceAuditRecord,
    ScienceProposalApproval,
    ScienceRuntimeStore,
    ScienceSensitivePersistenceError,
    ScienceTransactionPendingError,
    UnsafeScienceRuntimePathError,
)


def digest(label: str) -> str:
    return "sha256:" + sha256(label.encode("utf-8")).hexdigest()


def proposal_request_digest(
    *, domain: str, kind: str, payload: dict[str, object]
) -> str:
    return sha256_digest({"domain": domain, "kind": kind, "payload": payload})


def test_user_action_challenge_is_durable_exact_and_consumed_once(
    tmp_path: Path,
) -> None:
    """Catches process-local, replayable, or payload-unbound challenges."""

    authorization = ScienceAuthorization("admin_only")

    def roles_for(_employee_id: str) -> list[str]:
        return ["science.admin", "boi.viewer"]

    issued_at = datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc)
    expires_at = datetime(2026, 8, 25, 4, 5, tzinfo=timezone.utc)
    request_digest = digest("trusted-user-action")
    store = ScienceRuntimeStore(
        tmp_path / "runtime",
        authorization=authorization,
        roles_for=roles_for,
    )

    challenge = store.issue_user_action_challenge(
        operation="submit_user_revision",
        actor_id="100001",
        request_digest=request_digest,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    store.close()

    reopened = ScienceRuntimeStore(
        tmp_path / "runtime",
        authorization=authorization,
        roles_for=roles_for,
    )
    with pytest.raises(ValueError, match="does not match"):
        reopened.consume_user_action_challenge(
            challenge.challenge_id,
            operation="submit_user_revision",
            actor_id="100002",
            request_digest=request_digest,
            consumed_at=datetime(2026, 8, 25, 4, 1, tzinfo=timezone.utc),
        )

    consumed = reopened.consume_user_action_challenge(
        challenge.challenge_id,
        operation="submit_user_revision",
        actor_id="100001",
        request_digest=request_digest,
        consumed_at=datetime(2026, 8, 25, 4, 1, tzinfo=timezone.utc),
    )
    assert consumed == challenge
    with pytest.raises(KeyError, match="missing or already used"):
        reopened.consume_user_action_challenge(
            challenge.challenge_id,
            operation="submit_user_revision",
            actor_id="100001",
            request_digest=request_digest,
            consumed_at=datetime(2026, 8, 25, 4, 1, tzinfo=timezone.utc),
        )


def test_user_action_challenge_consumption_is_atomic_across_store_instances(
    tmp_path: Path,
) -> None:
    """Catches two workers both accepting one human-action challenge."""

    authorization = ScienceAuthorization("admin_only")

    def roles_for(_employee_id: str) -> list[str]:
        return ["science.admin", "boi.viewer"]

    root = tmp_path / "runtime"
    first = ScienceRuntimeStore(
        root,
        authorization=authorization,
        roles_for=roles_for,
    )
    second = ScienceRuntimeStore(
        root,
        authorization=authorization,
        roles_for=roles_for,
    )
    request_digest = digest("atomic-user-action")
    challenge = first.issue_user_action_challenge(
        operation="confirm_interpretation",
        actor_id="100001",
        request_digest=request_digest,
        issued_at=datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 8, 25, 4, 5, tzinfo=timezone.utc),
    )

    def consume(store: ScienceRuntimeStore) -> str:
        try:
            store.consume_user_action_challenge(
                challenge.challenge_id,
                operation="confirm_interpretation",
                actor_id="100001",
                request_digest=request_digest,
                consumed_at=datetime(2026, 8, 25, 4, 1, tzinfo=timezone.utc),
            )
        except KeyError:
            return "rejected"
        return "consumed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(consume, (first, second)))

    assert sorted(outcomes) == ["consumed", "rejected"]


def save_proposal_fixture(
    store: ScienceRuntimeStore,
    *,
    identity: AuthIdentity,
    domain: str,
    kind: str,
    payload: dict[str, object],
    key_label: str,
):
    return store.save_proposal(
        identity=identity,
        domain=domain,
        kind=kind,
        payload=payload,
        idempotency_key=f"proposal-fixture:{key_label}",
        request_digest=proposal_request_digest(
            domain=domain,
            kind=kind,
            payload=payload,
        ),
    )


def interpretation_payload(
    interpretation_id: str = "sci-interpretation:fixture",
    *,
    model_id: str = "fixture-model",
    actor_id: str = "100001",
) -> dict[str, object]:
    payload = {
        "interpretation_id": interpretation_id,
        "document_digest": digest("document"),
        "candidate_claims": [],
        "model_id": model_id,
        "model_settings": {"temperature": 0},
        "prompt_version": "science-interpretation/0.1",
        "dictionary_release_id": "dictionary:0.1",
        "ontology_release_id": "ontology:0.1",
        "ontology_refs": [],
        "candidate_meanings": [],
        "decision_impact": [],
        "user_revision_history": [],
        "confirmed_claim_packet_digest": None,
        "response_digest": digest("response"),
    }
    payload["operation_binding"] = {
        "operation": "interpret_document",
        "idempotency_key_digest": digest(f"idempotency:{interpretation_id}"),
        "actor_id": actor_id,
        "request_digest": digest(f"request:{interpretation_id}"),
        "document_digest": payload["document_digest"],
        "claim_digest": digest("empty-claims"),
        "release_digest": None,
        "prompt_digest": digest("prompt"),
        "source_interpretation_id": None,
        "claim_ids": [],
    }
    payload["operation_binding"]["claim_digest"] = (
        "sha256:" + sha256(canonical_json_bytes({"claim_packets": []})).hexdigest()
    )
    return payload


def _save_report_fixture(
    store: ScienceRuntimeStore,
    identity: AuthIdentity,
    report_id: str = "sci-report:fixture",
) -> VerificationReport:
    suffix = sha256(report_id.encode("utf-8")).hexdigest()[:16]
    proposal_id = f"sci-interpretation:proposal-{suffix}"
    confirmation_id = f"sci-interpretation:confirmation-{suffix}"
    document_ref = "boi:public:science:fixture"
    document_digest = digest(f"document:{suffix}")
    span = {
        "start": 0,
        "end": 3,
        "exact": "RPM",
        "prefix": "",
        "suffix": "",
    }
    normalized_claim = {
        "subject_concept_id": "sci:concept:rpm",
        "relation_kind": "monotonic_direction",
        "predicate": "increases",
        "object_concept_id": "sci:concept:thickness",
        "polarity": "positive",
        "quantities": [],
        "conditions": [],
        "process_stage": "final_spin",
        "material_state": "liquid_film",
    }
    proposal_claim = ClaimPacket.model_validate(
        {
            "claim_id": f"sci-claim:{suffix}",
            "document_ref": document_ref,
            "document_digest": document_digest,
            "source_span": span,
            "normalized_claim": normalized_claim,
            "interpretation": {
                "ontology_refs": [],
                "proposed_ontology_refs": [],
                "ambiguity_ids": [f"ambiguity:{suffix}"],
                "user_confirmed": False,
            },
        }
    )
    common = {
        "document_digest": document_digest,
        "model_id": "fixture-model",
        "model_settings": {"temperature": 0},
        "prompt_version": "science-interpretation/0.1",
        "dictionary_release_id": "dictionary:0.1",
        "ontology_release_id": "ontology:0.1",
        "ontology_refs": [],
        "candidate_meanings": [],
        "decision_impact": [
            {
                "claim_id": proposal_claim.claim_id,
                "status": "requires_user_confirmation",
                "issue_codes": ["USER_CONFIRMATION_REQUIRED"],
            }
        ],
        "response_digest": digest(f"response:{suffix}"),
    }
    proposal_binding = {
        "operation": "interpret_document",
        "idempotency_key_digest": digest(f"proposal-key:{suffix}"),
        "actor_id": identity.employee_id,
        "request_digest": digest(f"proposal-request:{suffix}"),
        "document_digest": document_digest,
        "claim_digest": sha256_digest({"claim_packets": [proposal_claim]}),
        "release_digest": None,
        "prompt_digest": digest(f"prompt:{suffix}"),
        "source_interpretation_id": None,
        "claim_ids": [proposal_claim.claim_id],
    }
    proposal = InterpretationRecord(
        interpretation_id=proposal_id,
        candidate_claims=[proposal_claim],
        user_revision_history=[],
        confirmed_claim_packet_digest=None,
        operation_binding=proposal_binding,
        **common,
    )
    store.save_interpretation(proposal, identity=identity)

    confirmed_claim = proposal_claim.model_copy(
        update={
            "interpretation": proposal_claim.interpretation.model_copy(
                update={"ambiguity_ids": [], "user_confirmed": True}
            )
        },
        deep=True,
    )
    confirmed_digest = sha256_digest(confirmed_claim)
    confirmation_binding = {
        "operation": "confirm_interpretation",
        "idempotency_key_digest": digest(f"confirmation-key:{suffix}"),
        "actor_id": identity.employee_id,
        "request_digest": digest(f"confirmation-request:{suffix}"),
        "document_digest": document_digest,
        "claim_digest": confirmed_digest,
        "release_digest": None,
        "prompt_digest": proposal.operation_binding.prompt_digest,
        "source_interpretation_id": proposal_id,
        "claim_ids": [proposal_claim.claim_id],
    }
    confirmation = InterpretationRecord(
        interpretation_id=confirmation_id,
        candidate_claims=[confirmed_claim],
        user_revision_history=[
            {
                "action": "claim_confirmed",
                "actor_id": identity.employee_id,
                "source_interpretation_id": proposal_id,
                "claim_ids": [proposal_claim.claim_id],
                "occurred_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
            }
        ],
        confirmed_claim_packet_digest=confirmed_digest,
        operation_binding=confirmation_binding,
        **common,
    )
    store.save_interpretation(confirmation, identity=identity)

    selection = ReleaseSelection(foundation="sci-release:foundation:0.1.0")
    release_digests = {selection.foundation: digest("foundation")}
    verdict = VerdictPacket(
        claim_id=confirmed_claim.claim_id,
        claim_packet_digest=sha256_digest(confirmed_claim),
        verifier_version="fixture-verifier/0.1",
        releases={
            "selection": selection,
            "digests": release_digests,
            "combined_digest": digest("combined-release"),
        },
        verdict="VIOLATION",
        reason_codes=["FIXTURE"],
        condition_evaluations=[],
        decisive_rule_ids=["sci:rule:fixture"],
        knowledge_refs=[],
        evidence_refs=[],
        corrected_claim=None,
        explanation_facts=[],
        limitations=[],
    )
    request_digest = sha256_digest(
        {
            "operation": "verify_document",
            "interpretation_id": confirmation_id,
            "claim_digest": confirmed_digest,
            "release_selection": selection,
        }
    )
    binding = ScienceOperationBinding(
        operation="verify_document",
        idempotency_key_digest=digest(f"report-key:{suffix}"),
        actor_id=identity.employee_id,
        request_digest=request_digest,
        document_digest=document_digest,
        claim_digest=confirmed_digest,
        release_digest=sha256_digest(selection),
        prompt_digest=proposal.operation_binding.prompt_digest,
        source_interpretation_id=confirmation_id,
        claim_ids=[confirmed_claim.claim_id],
    )
    payload = {
        "report_id": report_id,
        "document_ref": document_ref,
        "document_digest": document_digest,
        "release_selection": selection,
        "release_digests": release_digests,
        "interpretation_ids": [confirmation_id],
        "confirmed_claims": [confirmed_claim],
        "verdict_packets": [verdict],
        "unresolved_ambiguities": [],
        "annotations": [],
        "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "created_by": identity.employee_id,
        "operation_binding": binding,
    }
    canonical_payload = VerificationReport.model_construct(
        **payload,
        report_digest="sha256:pending",
    ).model_dump(mode="json", exclude={"report_digest"})
    report = VerificationReport(
        **payload,
        report_digest=sha256_digest(canonical_payload),
    )
    return store.save_report(report, identity=identity)


def science_roles(identity: AuthIdentity) -> list[str]:
    return {
        "100001": ["science.admin"],
        "100002": ["science.power_user:lithography"],
        "100003": ["science.user"],
        "200001": ["science.power_user:materials"],
        "200002": ["science.power_user:lithography"],
    }.get(identity.employee_id, [])


@pytest.fixture
def runtime_store(tmp_path: Path) -> ScienceRuntimeStore:
    return ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization(access_mode="pilot"),
        roles_for=science_roles,
        report_authority_validator=lambda _report: None,
    )


@pytest.fixture
def science_admin() -> AuthIdentity:
    return AuthIdentity(
        employee_id="100001",
        display_name="Science admin",
        roles=["boi.admin"],
    )


@pytest.fixture
def lithography_power_user() -> AuthIdentity:
    return AuthIdentity(
        employee_id="100002",
        display_name="lithography reviewer",
        roles=["boi.viewer"],
    )


def test_save_interpretation_is_idempotent_but_rejects_changed_canonical_bytes(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """An existing record ID must never be overwritten with changed content."""
    original = runtime_store.save_interpretation(
        interpretation_payload(), identity=science_admin
    )
    repeated = runtime_store.save_interpretation(
        interpretation_payload(), identity=science_admin
    )

    assert repeated == original
    with pytest.raises(ImmutableScienceRecordError, match="immutable record collision"):
        runtime_store.save_interpretation(
            interpretation_payload(model_id="changed-model"), identity=science_admin
        )
    assert runtime_store.load_interpretation(original.interpretation_id) == original


def test_save_report_uses_private_permissions_and_leaves_no_temp_files(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """A permissive mode or leaked temp file would expose immutable report contents."""
    report = _save_report_fixture(runtime_store, science_admin)
    path = runtime_store.record_path("reports", report.report_id)

    assert runtime_store.load_report(report.report_id) == report
    assert path.stat().st_mode & 0o777 == 0o600
    assert runtime_store.root.stat().st_mode & 0o777 == 0o700
    assert not list(path.parent.glob(".*.tmp"))


def test_concurrent_different_writes_to_one_id_never_overwrite_each_other(
    runtime_store: ScienceRuntimeStore,
):
    """Removing the write lock would allow the last os.replace call to win."""
    barrier = Barrier(2)

    def save(model_id: str, employee_id: str):
        barrier.wait()
        caller = AuthIdentity(employee_id=employee_id, display_name=model_id)
        return runtime_store.save_interpretation(
            interpretation_payload(model_id=model_id, actor_id=employee_id),
            identity=caller,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(save, model_id, employee_id)
            for model_id, employee_id in (
                ("model-a", "300001"),
                ("model-b", "300002"),
            )
        ]
        outcomes: list[object] = []
        errors: list[BaseException] = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except (
                BaseException
            ) as exc:  # the exception itself is the concurrency outcome
                errors.append(exc)

    assert len(outcomes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ImmutableScienceRecordError)
    persisted = runtime_store.load_interpretation("sci-interpretation:fixture")
    assert persisted.model_id in {"model-a", "model-b"}


def test_atomic_replace_failure_does_not_publish_or_leave_temporary_bytes(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failed publication must not leave a partial final or reusable temp file."""
    real_replace = os.replace

    def fail_replace(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    payload = interpretation_payload("sci-interpretation:replace-failure")
    with pytest.raises(OSError, match="simulated replace failure"):
        runtime_store.save_interpretation(payload, identity=science_admin)
    monkeypatch.setattr(os, "replace", real_replace)

    final_path = runtime_store.record_path(
        "interpretations", "sci-interpretation:replace-failure"
    )
    assert not final_path.exists()
    assert not list(final_path.parent.glob(".*.tmp"))


def test_power_user_cannot_approve_own_proposal(
    runtime_store: ScienceRuntimeStore,
    lithography_power_user: AuthIdentity,
):
    """Dropping the actor comparison would allow Power Users to self-promote changes."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=lithography_power_user,
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
        key_label="power-user-self-approval",
    )

    with pytest.raises(ScienceAuthorizationError, match="self-approval"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            identity=lithography_power_user,
        )


@pytest.mark.parametrize(
    ("actor_id", "domain", "kind", "payload"),
    [
        ("100002", "lithography", "term_alias", {"alias": "PR"}),
        ("100001", "materials", "term_alias", {"alias": "PR"}),
        ("100001", "lithography", "term_meaning", {"alias": "PR"}),
        ("100001", "lithography", "term_alias", {"alias": "photoresist"}),
    ],
)
def test_proposal_idempotency_key_reuse_rejects_changed_operation_binding(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    actor_id: str,
    domain: str,
    kind: str,
    payload: dict[str, object],
):
    """Dropping any actor/request field from collision checks would alias proposals."""
    raw_key = "proposal-store-conflict-001"
    original_payload = {"alias": "PR"}
    runtime_store.save_proposal(
        identity=science_admin,
        domain="lithography",
        kind="term_alias",
        payload=original_payload,
        idempotency_key=raw_key,
        request_digest=proposal_request_digest(
            domain="lithography",
            kind="term_alias",
            payload=original_payload,
        ),
    )
    changed_identity = AuthIdentity(
        employee_id=actor_id,
        display_name="changed proposal actor",
    )

    with pytest.raises(ImmutableScienceRecordError, match="idempotency|collision"):
        runtime_store.save_proposal(
            identity=changed_identity,
            domain=domain,
            kind=kind,
            payload=payload,
            idempotency_key=raw_key,
            request_digest=proposal_request_digest(
                domain=domain,
                kind=kind,
                payload=payload,
            ),
        )
    rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["action"] == "proposal_saved"
    ]
    assert len(rows) == 1


def test_proposal_key_reuse_rejects_a_different_request_digest(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    payload = {"alias": "PR"}
    raw_key = "proposal-store-digest-conflict-001"
    exact_digest = proposal_request_digest(
        domain="lithography",
        kind="term_alias",
        payload=payload,
    )
    runtime_store.save_proposal(
        identity=science_admin,
        domain="lithography",
        kind="term_alias",
        payload=payload,
        idempotency_key=raw_key,
        request_digest=exact_digest,
    )

    with pytest.raises(ImmutableScienceRecordError, match="idempotency|collision"):
        runtime_store.save_proposal(
            identity=science_admin,
            domain="lithography",
            kind="term_alias",
            payload=payload,
            idempotency_key=raw_key,
            request_digest=digest("different-request"),
        )


def test_proposal_exact_retry_survives_store_restart_with_one_audit(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    payload = {"alias": "PR"}
    raw_key = "proposal-store-restart-001"
    request_digest = proposal_request_digest(
        domain="lithography",
        kind="term_alias",
        payload=payload,
    )
    first = runtime_store.save_proposal(
        identity=science_admin,
        domain="lithography",
        kind="term_alias",
        payload=payload,
        idempotency_key=raw_key,
        request_digest=request_digest,
    )
    root = runtime_store.root
    runtime_store.close()
    restarted = ScienceRuntimeStore(
        root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )

    retried = restarted.save_proposal(
        identity=science_admin,
        domain="lithography",
        kind="term_alias",
        payload=payload,
        idempotency_key=raw_key,
        request_digest=request_digest,
    )

    assert retried == first
    rows = [
        json.loads(line)
        for line in restarted.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["action"] == "proposal_saved"
    ]
    assert len(rows) == 1


def test_concurrent_exact_proposal_retries_publish_once(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    payload = {"alias": "PR"}
    raw_key = "proposal-store-concurrent-001"
    request_digest = proposal_request_digest(
        domain="lithography",
        kind="term_alias",
        payload=payload,
    )
    barrier = Barrier(4)

    def create_proposal():
        barrier.wait()
        return runtime_store.save_proposal(
            identity=science_admin,
            domain="lithography",
            kind="term_alias",
            payload=payload,
            idempotency_key=raw_key,
            request_digest=request_digest,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        proposals = list(pool.map(lambda _index: create_proposal(), range(4)))

    assert all(proposal == proposals[0] for proposal in proposals)
    rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["action"] == "proposal_saved"
    ]
    assert len(rows) == 1


def test_proposal_restart_recovers_pending_wal_before_idempotent_return(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    payload = {"alias": "PR"}
    raw_key = "proposal-store-wal-001"
    request_digest = proposal_request_digest(
        domain="lithography",
        kind="term_alias",
        payload=payload,
    )
    real_append = runtime_store._append_audit_event_locked

    def fail_proposal_audit(event: ScienceAuditRecord):
        if event.action == "proposal_saved":
            raise OSError("injected proposal audit failure")
        return real_append(event)

    monkeypatch.setattr(
        runtime_store,
        "_append_audit_event_locked",
        fail_proposal_audit,
    )
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.save_proposal(
            identity=science_admin,
            domain="lithography",
            kind="term_alias",
            payload=payload,
            idempotency_key=raw_key,
            request_digest=request_digest,
        )
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)
    root = runtime_store.root
    runtime_store.close()
    restarted = ScienceRuntimeStore(
        root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )

    retried = restarted.save_proposal(
        identity=science_admin,
        domain="lithography",
        kind="term_alias",
        payload=payload,
        idempotency_key=raw_key,
        request_digest=request_digest,
    )

    rows = [
        json.loads(line)
        for line in restarted.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["action"] == "proposal_saved"
    ]
    assert retried.proposal_id.startswith("sci-proposal:")
    assert len(rows) == 1
    assert restarted.pending_transaction_ids() == []


def test_power_user_approval_is_domain_scoped_and_keeps_proposal_immutable(
    runtime_store: ScienceRuntimeStore,
):
    """Ignoring the proposal domain would let one pilot curate every domain."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="concept_link",
        payload={"from": "RPM", "to": "rotational_speed"},
        key_label="domain-scoped-approval",
    )
    original_path = runtime_store.record_path("proposals", proposal.proposal_id)
    original_bytes = original_path.read_bytes()

    with pytest.raises(ScienceAuthorizationError, match="domain"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            identity=AuthIdentity(employee_id="200001", display_name="materials"),
        )

    approval = runtime_store.approve_proposal(
        proposal.proposal_id,
        identity=AuthIdentity(employee_id="200002", display_name="lithography"),
    )
    assert approval.status == "release_candidate"
    assert approval.domain == "lithography"
    assert original_path.read_bytes() == original_bytes


def test_science_admin_can_approve_without_inheriting_boi_admin(
    runtime_store: ScienceRuntimeStore,
):
    """A boi.admin role must not replace the Science authority model."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="materials",
        kind="term_meaning",
        payload={"term": "film"},
        key_label="science-admin-approval",
    )

    with pytest.raises(ScienceAuthorizationError, match="approval"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            identity=AuthIdentity(
                employee_id="blocked", display_name="BoI admin", roles=["boi.admin"]
            ),
        )
    approval = runtime_store.approve_proposal(
        proposal.proposal_id,
        identity=AuthIdentity(
            employee_id="100001", display_name="Science admin", roles=["boi.admin"]
        ),
    )
    assert approval.approved_by == "100001"


def test_audit_rows_are_append_only_and_action_typed(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """Audit serialization rejects nested endpoint and credential values."""
    runtime_store.append_audit(
        identity=science_admin,
        action="standalone_note_recorded",
        target_id="sci-note:00000000-0000-4000-8000-000000000001",
        details={
            "note_digest": digest("note-one"),
        },
    )
    runtime_store.append_audit(
        identity=science_admin,
        action="standalone_note_recorded",
        target_id="sci-note:00000000-0000-4000-8000-000000000002",
        details={"note_digest": digest("note-two")},
    )

    raw = runtime_store.audit_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row["action"] for row in rows[-2:]] == [
        "standalone_note_recorded",
        "standalone_note_recorded",
    ]
    assert rows[-2]["details"] == {
        "note_digest": digest("note-one"),
    }
    assert runtime_store.audit_path.stat().st_mode & 0o777 == 0o600


def test_public_audit_rejects_ordinary_user_forged_approval(
    runtime_store: ScienceRuntimeStore,
):
    """A pilot user cannot manufacture release-candidate history."""
    proposal_id = "sci-proposal:00000000-0000-4000-8000-000000000010"
    approval_id = "sci-approval:00000000-0000-4000-8000-000000000010"

    with pytest.raises(ScienceAuthorizationError, match="internal|admin"):
        runtime_store.append_audit(
            identity=AuthIdentity(employee_id="100003", display_name="ordinary user"),
            action="proposal_approved_for_release_candidate",
            target_id=proposal_id,
            details={"approval_id": approval_id, "domain": "lithography"},
        )

    assert not runtime_store.audit_path.exists()
    assert runtime_store.pending_transaction_ids() == []


@pytest.mark.parametrize(
    ("action", "target_id", "details"),
    [
        (
            "interpretation_saved",
            "sci-interpretation:nonexistent",
            {"document_digest": digest("nonexistent")},
        ),
        (
            "proposal_approved_for_release_candidate",
            "sci-proposal:00000000-0000-4000-8000-000000000011",
            {
                "approval_id": "sci-approval:00000000-0000-4000-8000-000000000011",
                "domain": "lithography",
            },
        ),
    ],
)
def test_public_audit_rejects_admin_record_actions_without_dependencies(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    action: str,
    target_id: str,
    details: dict[str, str],
):
    """Admin authority cannot bypass immutable record-bound event production."""
    with pytest.raises(ScienceAuthorizationError, match="internal"):
        runtime_store.append_audit(
            identity=science_admin,
            action=action,
            target_id=target_id,
            details=details,
        )

    assert not runtime_store.audit_path.exists()


def test_public_audit_cannot_duplicate_saved_or_approved_events(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """Only the immutable record transactions may produce the four mutation actions."""
    interpretation = runtime_store.save_interpretation(
        interpretation_payload("sci-interpretation:no-duplicate"),
        identity=science_admin,
    )
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
        key_label="audit-cannot-duplicate",
    )
    approval = runtime_store.approve_proposal(
        proposal.proposal_id, identity=science_admin
    )
    before = runtime_store.audit_path.read_bytes()

    with pytest.raises(ScienceAuthorizationError, match="internal"):
        runtime_store.append_audit(
            identity=science_admin,
            action="interpretation_saved",
            target_id=interpretation.interpretation_id,
            details={"document_digest": interpretation.document_digest},
        )
    with pytest.raises(ScienceAuthorizationError, match="internal"):
        runtime_store.append_audit(
            identity=science_admin,
            action="proposal_approved_for_release_candidate",
            target_id=proposal.proposal_id,
            details={"approval_id": approval.approval_id, "domain": proposal.domain},
        )

    assert runtime_store.audit_path.read_bytes() == before
    rows = [json.loads(line) for line in before.splitlines()]
    assert (
        sum(
            row["action"] == "interpretation_saved"
            and row["target_id"] == interpretation.interpretation_id
            for row in rows
        )
        == 1
    )
    assert (
        sum(
            row["action"] == "proposal_approved_for_release_candidate"
            and row["target_id"] == proposal.proposal_id
            for row in rows
        )
        == 1
    )


def test_public_standalone_audit_requires_science_admin(
    runtime_store: ScienceRuntimeStore,
):
    """The only public audit action is a non-authoritative admin note."""
    with pytest.raises(ScienceAuthorizationError, match="science.admin"):
        runtime_store.append_audit(
            identity=AuthIdentity(employee_id="100003", display_name="ordinary user"),
            action="standalone_note_recorded",
            target_id="sci-note:00000000-0000-4000-8000-000000000012",
            details={"note_digest": digest("admin-note")},
        )


def test_public_standalone_note_target_is_semantically_unique(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """A standalone note ID names one immutable operational note."""
    target_id = "sci-note:00000000-0000-4000-8000-000000000013"
    runtime_store.append_audit(
        identity=science_admin,
        action="standalone_note_recorded",
        target_id=target_id,
        details={"note_digest": digest("first-note")},
    )

    with pytest.raises(ImmutableScienceRecordError, match="note target"):
        runtime_store.append_audit(
            identity=science_admin,
            action="standalone_note_recorded",
            target_id=target_id,
            details={"note_digest": digest("second-note")},
        )

    rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert sum(row["target_id"] == target_id for row in rows) == 1


def test_recovery_rejects_audit_only_wal_forged_into_record_action(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Canonical audit-only bytes cannot bypass the internal-action boundary."""
    real_append = runtime_store._append_audit_event_locked

    def fail_note_audit(event: ScienceAuditRecord):
        raise OSError("leave standalone WAL pending")

    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", fail_note_audit)
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.append_audit(
            identity=science_admin,
            action="standalone_note_recorded",
            target_id="sci-note:00000000-0000-4000-8000-000000000014",
            details={"note_digest": digest("pending-note")},
        )
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)
    transaction_id = runtime_store.pending_transaction_ids()[0]
    journal_path = runtime_store.record_path("transactions", transaction_id)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    journal["audit"]["action"] = "interpretation_saved"
    journal["audit"]["target_id"] = "sci-interpretation:forged-recovery"
    journal["audit"]["details"] = {"document_digest": digest("forged")}
    journal_path.write_bytes(canonical_json_bytes(journal))

    with pytest.raises(ImmutableScienceRecordError, match="Record-mutation|immutable"):
        runtime_store.recover_pending_transactions()

    assert journal_path.exists()
    assert not runtime_store.audit_path.exists()


def test_proposal_authorship_and_approval_use_one_trusted_identity_resolver(
    runtime_store: ScienceRuntimeStore,
):
    """A caller must not forge another author or independently submit approval roles."""
    attacker = AuthIdentity(
        employee_id="100002",
        display_name="attacker",
        roles=["science.admin"],  # deliberately disagrees with the trusted resolver
    )
    proposal = save_proposal_fixture(
        runtime_store,
        identity=attacker,
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
        key_label="trusted-identity-resolver",
    )
    assert proposal.created_by == "100002"

    with pytest.raises(ScienceAuthorizationError, match="self-approval"):
        runtime_store.approve_proposal(proposal.proposal_id, identity=attacker)

    with pytest.raises(TypeError):
        runtime_store.save_proposal(
            identity=attacker,
            actor="victim",
            domain="lithography",
            kind="term_alias",
            payload={"alias": "forged"},
            idempotency_key="proposal-fixture:forged-actor",
            request_digest=proposal_request_digest(
                domain="lithography",
                kind="term_alias",
                payload={"alias": "forged"},
            ),
        )
    with pytest.raises(TypeError):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            identity=attacker,
            actor="victim",
            roles=["science.admin"],
        )


@pytest.mark.parametrize(
    ("identity", "target_id", "details"),
    [
        (
            AuthIdentity(employee_id="Bearer-actor-secret", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {"note_digest": digest("note")},
        ),
        (
            AuthIdentity(employee_id="sk-live-secret", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {"note_digest": digest("note")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "https://internal.invalid/token=target-secret",
            {"note_digest": digest("note")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "internal.invalid:1236",
            {"note_digest": digest("note")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {"note_digest": "Bearer detail-secret"},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {"note_digest": "endpoint=https://internal.invalid/v1"},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {
                "note_digest": digest("note"),
                "apiKey": "camel-secret",
            },
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-note:00000000-0000-4000-8000-000000000020",
            {
                "note_digest": digest("note"),
                "context": ["safe", "Bearer list-secret"],
            },
        ),
    ],
)
def test_audit_rejects_sensitive_scalars_in_every_persisted_position(
    runtime_store: ScienceRuntimeStore,
    identity: AuthIdentity,
    target_id: str,
    details: dict[str, object],
):
    """Redaction by suspicious key alone would retain disguised secrets or endpoints."""
    before = (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    )
    with pytest.raises(ScienceSensitivePersistenceError):
        runtime_store.append_audit(
            identity=identity,
            action="standalone_note_recorded",
            target_id=target_id,
            details=details,
        )
    after = (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    )
    assert after == before


def test_audit_rejects_unknown_but_nonsecret_action_details(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """Allowing arbitrary audit mappings would make secret exclusion non-auditable."""
    with pytest.raises(ScienceSensitivePersistenceError, match="failed|rejected"):
        runtime_store.append_audit(
            identity=science_admin,
            action="standalone_note_recorded",
            target_id="sci-note:00000000-0000-4000-8000-000000000021",
            details={"note_digest": digest("note"), "note": "safe"},
        )


def test_audit_short_write_is_completed_as_one_valid_json_row(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Treating a short write as final would leave a corrupt JSON fragment."""
    real_write = os.write
    calls = 0
    audit_inode: int | None = None

    def short_once(descriptor: int, data: bytes) -> int:
        nonlocal audit_inode, calls
        if bytes(data).endswith(b"\n"):
            audit_inode = os.fstat(descriptor).st_ino
        if audit_inode is None or os.fstat(descriptor).st_ino != audit_inode:
            return real_write(descriptor, data)
        calls += 1
        if calls == 1:
            return real_write(descriptor, data[: max(1, len(data) // 2)])
        return real_write(descriptor, data)

    monkeypatch.setattr(os, "write", short_once)
    runtime_store.append_audit(
        identity=science_admin,
        action="standalone_note_recorded",
        target_id="sci-note:00000000-0000-4000-8000-000000000030",
        details={"note_digest": digest("short-write")},
    )

    rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["target_id"] == "sci-note:00000000-0000-4000-8000-000000000030"
    assert calls >= 2


def test_audit_mid_row_error_rolls_back_and_fsyncs_previous_eof(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A second-write exception must leave the prior JSONL bytes exactly intact."""
    runtime_store.append_audit(
        identity=science_admin,
        action="standalone_note_recorded",
        target_id="sci-note:00000000-0000-4000-8000-000000000031",
        details={"note_digest": digest("seed")},
    )
    before = runtime_store.audit_path.read_bytes()
    audit_inode = runtime_store.audit_path.stat().st_ino
    real_write = os.write
    calls = 0

    def partial_then_error(descriptor: int, data: bytes) -> int:
        nonlocal calls
        if os.fstat(descriptor).st_ino != audit_inode:
            return real_write(descriptor, data)
        calls += 1
        if calls == 1:
            return real_write(descriptor, data[: max(1, len(data) // 2)])
        raise OSError("injected mid-row failure")

    monkeypatch.setattr(os, "write", partial_then_error)
    with pytest.raises(
        ScienceTransactionPendingError, match="injected mid-row failure"
    ) as caught:
        runtime_store.append_audit(
            identity=science_admin,
            action="standalone_note_recorded",
            target_id="sci-note:00000000-0000-4000-8000-000000000032",
            details={"note_digest": digest("failed")},
        )
    assert runtime_store.audit_path.read_bytes() == before
    assert caught.value.record_published is False
    assert caught.value.audit_pending is True
    assert runtime_store.pending_transaction_ids()


def test_record_load_rejects_final_component_symlink(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    tmp_path: Path,
):
    """Following a same-name symlink would let approval consume an external record."""
    report = _save_report_fixture(runtime_store, science_admin)
    record_path = runtime_store.record_path("reports", report.report_id)
    external = tmp_path / "external-report.json"
    shutil.copyfile(record_path, external)
    record_path.unlink()
    record_path.symlink_to(external)

    with pytest.raises(
        UnsafeScienceRuntimePathError, match="symbolic link|safe regular"
    ):
        runtime_store.load_report(report.report_id)


def test_record_load_rejects_collection_directory_swap(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """A collection renamed and replaced after initialization must fail closed."""
    report = _save_report_fixture(runtime_store, science_admin)
    original = runtime_store.root / "reports"
    moved = runtime_store.root / "reports-original"
    original.rename(moved)
    original.mkdir(mode=0o700)

    with pytest.raises(UnsafeScienceRuntimePathError, match="directory.*changed"):
        runtime_store.load_report(report.report_id)


def test_record_load_rejects_nonprivate_existing_file(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """A group-readable replacement must not become an accepted immutable record."""
    report = _save_report_fixture(runtime_store, science_admin)
    path = runtime_store.record_path("reports", report.report_id)
    path.chmod(0o640)

    with pytest.raises(UnsafeScienceRuntimePathError, match="private mode"):
        runtime_store.load_report(report.report_id)


def test_after_rename_failure_is_typed_and_recovered_from_durable_journal(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A raised replace wrapper must not hide that immutable bytes became visible."""
    real_replace = os.replace
    payload = interpretation_payload("sci-interpretation:after-rename")
    record_filename = runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    ).name

    def replace_then_fail(*args, **kwargs):
        real_replace(*args, **kwargs)
        if Path(args[1]).name == record_filename:
            raise OSError("injected after rename")

    monkeypatch.setattr(os, "replace", replace_then_fail)
    with pytest.raises(ScienceTransactionPendingError) as caught:
        runtime_store.save_interpretation(payload, identity=science_admin)
    assert caught.value.record_published is True
    assert caught.value.audit_pending is True
    assert runtime_store.load_interpretation(payload["interpretation_id"])
    assert runtime_store.pending_transaction_ids()

    monkeypatch.setattr(os, "replace", real_replace)
    recovered = ScienceRuntimeStore(
        runtime_store.root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )
    assert recovered.pending_transaction_ids() == []
    assert recovered.load_interpretation(payload["interpretation_id"])
    assert any(
        json.loads(line)["target_id"] == payload["interpretation_id"]
        for line in recovered.audit_path.read_text(encoding="utf-8").splitlines()
    )


def test_after_rename_inspection_failure_is_conservatively_typed_as_published(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Failure to inspect after rename must not escape as an ambiguous generic error."""
    payload = interpretation_payload("sci-interpretation:inspection-failure")
    record_filename = runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    ).name
    real_replace = os.replace
    real_existing = runtime_store._existing_bytes_locked
    renamed = False

    def replace_then_fail(*args, **kwargs):
        nonlocal renamed
        real_replace(*args, **kwargs)
        if Path(args[1]).name == record_filename:
            renamed = True
            raise OSError("injected after rename")

    def fail_post_rename_inspection(collection: str, record_id: str):
        if renamed and collection == "interpretations":
            raise OSError("injected inspection failure")
        return real_existing(collection, record_id)

    monkeypatch.setattr(os, "replace", replace_then_fail)
    monkeypatch.setattr(
        runtime_store, "_existing_bytes_locked", fail_post_rename_inspection
    )

    with pytest.raises(ScienceTransactionPendingError) as caught:
        runtime_store.save_interpretation(payload, identity=science_admin)
    assert caught.value.record_published is True
    assert caught.value.audit_pending is True


def test_record_directory_fsync_failure_is_typed_and_recoverable(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Directory durability failure after publication must expose committed state."""
    real_fsync = os.fsync
    failed = False

    def fail_interpretation_directory_once(descriptor: int):
        nonlocal failed
        target = os.readlink(f"/proc/self/fd/{descriptor}")
        if not failed and target.endswith("/interpretations"):
            failed = True
            raise OSError("injected interpretation directory fsync")
        return real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", fail_interpretation_directory_once)
    payload = interpretation_payload("sci-interpretation:directory-fsync")
    with pytest.raises(ScienceTransactionPendingError) as caught:
        runtime_store.save_interpretation(payload, identity=science_admin)
    assert caught.value.record_published is True
    assert caught.value.audit_pending is True

    monkeypatch.setattr(os, "fsync", real_fsync)
    assert runtime_store.recover_pending_transactions() == 1
    assert runtime_store.pending_transaction_ids() == []


def test_audit_failure_after_record_publish_is_typed_and_reconciled(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A generic exception must never conceal a published but unaudited record."""

    def fail_audit(event):
        raise OSError("injected audit failure")

    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", fail_audit)
    payload = interpretation_payload("sci-interpretation:audit-pending")
    with pytest.raises(ScienceTransactionPendingError) as caught:
        runtime_store.save_interpretation(payload, identity=science_admin)
    assert caught.value.record_published is True
    assert caught.value.audit_pending is True
    assert runtime_store.load_interpretation(payload["interpretation_id"])
    assert runtime_store.pending_transaction_ids()

    monkeypatch.undo()
    assert runtime_store.recover_pending_transactions() == 1
    assert runtime_store.pending_transaction_ids() == []


def test_same_process_retry_reconciles_a_prior_audit_pending_transaction(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """An exact retry cannot succeed while its journal remains unaudited."""
    real_append = runtime_store._append_audit_event_locked
    failed = False

    def fail_once(event):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("injected first audit failure")
        return real_append(event)

    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", fail_once)
    payload = interpretation_payload("sci-interpretation:retry-reconcile")
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.save_interpretation(payload, identity=science_admin)

    saved = runtime_store.save_interpretation(payload, identity=science_admin)

    assert saved.interpretation_id == payload["interpretation_id"]
    assert runtime_store.pending_transaction_ids() == []
    matching_rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["target_id"] == payload["interpretation_id"]
    ]
    assert len(matching_rows) == 1


def test_approval_retry_recovers_its_audit_before_returning_existing_record(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """The approval fast path must not bypass its pending WAL and audit event."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
        key_label="approval-audit-retry",
    )
    real_append = runtime_store._append_audit_event_locked

    def fail_approval_audit(event: ScienceAuditRecord):
        if event.action == "proposal_approved_for_release_candidate":
            raise OSError("injected approval audit failure")
        return real_append(event)

    monkeypatch.setattr(
        runtime_store, "_append_audit_event_locked", fail_approval_audit
    )
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.approve_proposal(proposal.proposal_id, identity=science_admin)
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)

    approval = runtime_store.approve_proposal(
        proposal.proposal_id, identity=science_admin
    )

    assert approval.proposal_id == proposal.proposal_id
    assert runtime_store.pending_transaction_ids() == []
    approval_rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["action"] == "proposal_approved_for_release_candidate"
    ]
    assert len(approval_rows) == 1


def test_approval_restart_recovers_pending_audit_and_exact_linkage(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Restart recovery must complete an approval before its idempotent return path."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="materials",
        kind="concept_link",
        payload={"from": "film", "to": "material_layer"},
        key_label="approval-restart",
    )
    real_append = runtime_store._append_audit_event_locked

    def fail_approval_audit(event: ScienceAuditRecord):
        if event.action == "proposal_approved_for_release_candidate":
            raise OSError("injected approval audit failure")
        return real_append(event)

    monkeypatch.setattr(
        runtime_store, "_append_audit_event_locked", fail_approval_audit
    )
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.approve_proposal(proposal.proposal_id, identity=science_admin)
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)
    runtime_store.close()

    restarted = ScienceRuntimeStore(
        runtime_store.root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )
    approval = restarted.approve_proposal(proposal.proposal_id, identity=science_admin)

    assert approval.domain == proposal.domain
    assert approval.proposal_kind == proposal.kind
    assert approval.approved_by == science_admin.employee_id
    assert restarted.pending_transaction_ids() == []


def test_tampered_existing_approval_never_uses_the_idempotent_fast_path(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
):
    """Matching approver alone cannot authorize a mislinked approval."""
    proposal = save_proposal_fixture(
        runtime_store,
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="term_meaning",
        payload={"term": "film"},
        key_label="tampered-approval-fast-path",
    )
    approval = runtime_store.approve_proposal(
        proposal.proposal_id, identity=science_admin
    )
    path = runtime_store.record_path("proposal-approvals", approval.approval_id)
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["domain"] = "materials"
    path.write_bytes(canonical_json_bytes(tampered))

    with pytest.raises(ImmutableScienceRecordError, match="approval|collision|link"):
        runtime_store.approve_proposal(proposal.proposal_id, identity=science_admin)


@pytest.mark.parametrize("changed_path", ["root", "reports"])
def test_every_operation_rechecks_runtime_directory_private_mode(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    changed_path: str,
):
    """A post-construction chmod must invalidate both path and pinned-FD trust."""
    report = _save_report_fixture(runtime_store, science_admin)
    target = (
        runtime_store.root if changed_path == "root" else runtime_store.root / "reports"
    )
    target.chmod(0o755)

    with pytest.raises(UnsafeScienceRuntimePathError, match="private"):
        runtime_store.load_report(report.report_id)


def test_every_operation_rechecks_pinned_collection_owner(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A changed collection owner must fail even when its inode remains pinned."""
    report = _save_report_fixture(runtime_store, science_admin)
    reports_fd = runtime_store._dir_fds["reports"]
    real_fstat = os.fstat

    def changed_owner(descriptor: int):
        result = real_fstat(descriptor)
        if descriptor != reports_fd:
            return result
        values = list(result)
        values[4] = result.st_uid + 1
        return os.stat_result(values)

    monkeypatch.setattr(os, "fstat", changed_owner)
    with pytest.raises(UnsafeScienceRuntimePathError, match="owner"):
        runtime_store.load_report(report.report_id)


def test_pre_record_failure_plus_journal_cleanup_failure_is_typed_pending(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A prepared journal must never survive behind a generic cleanup exception."""
    payload = interpretation_payload("sci-interpretation:pre-record-cleanup")
    record_filename = runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    ).name
    real_replace = os.replace
    real_remove = runtime_store._remove_record_locked

    def fail_record_replace(*args, **kwargs):
        if Path(args[1]).name == record_filename:
            raise OSError("injected pre-record publication failure")
        return real_replace(*args, **kwargs)

    def fail_journal_cleanup(collection: str, record_id: str):
        if collection == "transactions":
            raise OSError("injected journal cleanup failure")
        return real_remove(collection, record_id)

    monkeypatch.setattr(os, "replace", fail_record_replace)
    monkeypatch.setattr(runtime_store, "_remove_record_locked", fail_journal_cleanup)
    with pytest.raises(ScienceTransactionPendingError) as caught:
        runtime_store.save_interpretation(payload, identity=science_admin)
    assert caught.value.record_published is False
    assert caught.value.audit_pending is True
    assert runtime_store.pending_transaction_ids()


def leave_pending_interpretation(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    interpretation_id: str,
) -> tuple[dict[str, object], str, Path, dict[str, object]]:
    real_append = runtime_store._append_audit_event_locked

    def fail_audit(event: ScienceAuditRecord):
        raise OSError("injected pending audit")

    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", fail_audit)
    payload = interpretation_payload(interpretation_id)
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.save_interpretation(payload, identity=science_admin)
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)
    transaction_id = runtime_store.pending_transaction_ids()[0]
    journal_path = runtime_store.record_path("transactions", transaction_id)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    return payload, transaction_id, journal_path, journal


def test_real_process_crash_residues_are_bounded_and_reconciled(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Startup recovers partial audit and exact private temporary residues."""
    payload, _, _, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:subprocess-crash",
    )
    expected_row = canonical_json_bytes(journal["audit"]) + b"\n"
    runtime_root = runtime_store.root
    runtime_store.close()
    script = r"""
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
row = bytes.fromhex(sys.argv[2])
for collection, marker in (("transactions", "1"), ("reports", "2")):
    name = "." + (marker * 64) + "." + (marker * 32) + ".tmp"
    descriptor = os.open(
        root / collection / name,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    os.write(descriptor, b"crash-residue")
    os.fsync(descriptor)
    os.close(descriptor)
audit = os.open(root / "audit.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
os.write(audit, row[: max(1, len(row) // 2)])
os.fsync(audit)
os._exit(23)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", script, str(runtime_root), expected_row.hex()],
        check=False,
        timeout=10,
    )
    assert crashed.returncode == 23

    recovered = ScienceRuntimeStore(
        runtime_root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )

    assert recovered.pending_transaction_ids() == []
    assert recovered.load_interpretation(payload["interpretation_id"])
    assert not list((runtime_root / "transactions").glob(".*.tmp"))
    assert not list((runtime_root / "reports").glob(".*.tmp"))
    audit_bytes = recovered.audit_path.read_bytes()
    assert audit_bytes.endswith(b"\n")
    assert audit_bytes.count(expected_row) == 1


def test_real_process_crash_during_actual_journal_temp_write_is_cleaned(
    runtime_store: ScienceRuntimeStore,
):
    """An os._exit inside the real journal writer may leave only a bounded temp."""
    runtime_root = runtime_store.root
    runtime_store.close()
    payload = interpretation_payload("sci-interpretation:journal-temp-crash")
    script = r"""
import json
import os
import sys
from pathlib import Path

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import ScienceAuthorization
from boi_api.app.science.storage import ScienceRuntimeStore

store = ScienceRuntimeStore(
    Path(sys.argv[1]),
    authorization=ScienceAuthorization("pilot"),
    roles_for=lambda identity: ["science.admin"],
)

def crash_during_write(descriptor, data):
    os.write(descriptor, data[: max(1, len(data) // 2)])
    os.fsync(descriptor)
    os._exit(24)

store._write_all = crash_during_write
store.save_interpretation(
    json.loads(sys.argv[2]),
    identity=AuthIdentity(employee_id="100001", display_name="crash writer"),
)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", script, str(runtime_root), json.dumps(payload)],
        cwd=Path(__file__).parents[1],
        check=False,
        timeout=10,
    )
    assert crashed.returncode == 24
    assert list((runtime_root / "transactions").glob(".*.tmp"))

    recovered = ScienceRuntimeStore(
        runtime_root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )

    assert recovered.pending_transaction_ids() == []
    assert not list((runtime_root / "transactions").glob(".*.tmp"))
    with pytest.raises(KeyError):
        recovered.load_interpretation(payload["interpretation_id"])


def test_recovery_rejects_canonical_journal_with_embedded_record_id_mismatch(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A journal key must bind the exact embedded typed record identity."""
    payload, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:journal-claimed",
    )
    runtime_store.record_path("interpretations", payload["interpretation_id"]).unlink()
    journal["record"]["interpretation_id"] = "sci-interpretation:embedded-other"
    journal_path.write_bytes(canonical_json_bytes(journal))

    with pytest.raises(ImmutableScienceRecordError, match="identity|record_id"):
        runtime_store.recover_pending_transactions()
    assert not runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    ).exists()
    assert journal_path.exists()


def test_recovery_rejects_journal_audit_not_derived_from_record(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A valid audit schema is insufficient when its details do not match the record."""
    _, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:audit-contract",
    )
    journal["audit"]["details"]["document_digest"] = digest("other-document")
    journal_path.write_bytes(canonical_json_bytes(journal))
    before_audit = (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    )

    with pytest.raises(ImmutableScienceRecordError, match="audit|contract|details"):
        runtime_store.recover_pending_transactions()
    assert (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    ) == before_audit
    assert journal_path.exists()


@pytest.mark.parametrize(
    ("field", "forbidden_value"),
    [
        ("actor", "sk-live-recovered-secret"),
        ("target_id", "internal.invalid:1236"),
    ],
)
def test_recovery_applies_the_same_sensitive_audit_validator_as_new_events(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    forbidden_value: str,
):
    """A canonical journal must not be a privileged path around audit safety."""
    _, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:recovered-secret",
    )
    journal["audit"][field] = forbidden_value
    journal_path.write_bytes(canonical_json_bytes(journal))

    with pytest.raises(
        (
            ScienceSensitivePersistenceError,
            ValidationError,
            ImmutableScienceRecordError,
        ),
        match="sensitive|pattern|actor|journal is invalid",
    ):
        runtime_store.recover_pending_transactions()
    raw = (
        runtime_store.audit_path.read_text(encoding="utf-8")
        if runtime_store.audit_path.exists()
        else ""
    )
    assert forbidden_value not in raw


@pytest.mark.parametrize("duplicate_variant", ["same", "different"])
def test_recovery_rejects_duplicate_audit_event_ids_before_mutation(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    duplicate_variant: str,
):
    """Event-ID equality is idempotent only for one exact canonical audit row."""
    _, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        f"sci-interpretation:duplicate-{duplicate_variant}",
    )
    expected = journal["audit"]
    if duplicate_variant == "same":
        rows = [expected, expected]
    else:
        spoof = dict(expected)
        spoof["actor"] = "999999"
        spoof["target_id"] = "sci-interpretation:spoof"
        rows = [spoof]
    runtime_store.audit_path.write_bytes(
        b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    )
    runtime_store.audit_path.chmod(0o600)

    with pytest.raises(ImmutableScienceRecordError, match="duplicate|event|bytes"):
        runtime_store.recover_pending_transactions()
    assert journal_path.exists()


@pytest.mark.parametrize("variant", ["corrupt-json", "noncanonical-json"])
def test_recovery_rejects_corrupt_or_noncanonical_audit_before_journal_change(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
):
    """Recovery must validate the entire audit ledger before deleting any journal."""
    _, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        f"sci-interpretation:{variant}",
    )
    if variant == "corrupt-json":
        row = b"{not-json}\n"
    else:
        row = json.dumps(journal["audit"], indent=2).encode("utf-8") + b"\n"
    runtime_store.audit_path.write_bytes(row)
    runtime_store.audit_path.chmod(0o600)

    with pytest.raises(ImmutableScienceRecordError, match="audit|canonical|JSON"):
        runtime_store.recover_pending_transactions()
    assert journal_path.exists()


def test_recovery_rejects_tampered_journal_filename_before_mutation(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A canonical journal is still untrusted when its hashed filename is different."""
    _, _, journal_path, _ = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:filename-tamper",
    )
    tampered_path = journal_path.with_name("f" * 64 + ".json")
    journal_path.rename(tampered_path)

    with pytest.raises(ImmutableScienceRecordError, match="filename"):
        runtime_store.recover_pending_transactions()
    assert tampered_path.exists()


def write_cloned_journal(
    runtime_store: ScienceRuntimeStore,
    source: dict[str, object],
) -> tuple[Path, dict[str, object]]:
    clone = deepcopy(source)
    transaction_id = f"sci-transaction:{uuid4()}"
    clone["transaction_id"] = transaction_id
    path = runtime_store.record_path("transactions", transaction_id)
    path.write_bytes(canonical_json_bytes(clone))
    path.chmod(0o600)
    return path, clone


def leave_verified_temp_residue(runtime_store: ScienceRuntimeStore) -> Path:
    residue = runtime_store.root / "reports" / f".{('a' * 64)}.{('b' * 32)}.tmp"
    residue.write_bytes(b"verified-private-residue")
    residue.chmod(0o600)
    return residue


@pytest.mark.parametrize("different_record_bytes", [False, True])
def test_global_recovery_preflight_rejects_every_duplicate_record_target(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
    different_record_bytes: bool,
):
    """No filename ordering may select one of two WALs for the same record."""
    payload, _, first_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        f"sci-interpretation:duplicate-target-{different_record_bytes}",
    )
    runtime_store.record_path("interpretations", payload["interpretation_id"]).unlink()
    second_path, clone = write_cloned_journal(runtime_store, journal)
    clone["audit"]["event_id"] = f"sci-audit:{uuid4()}"
    if different_record_bytes:
        clone["record"]["model_id"] = "conflicting-model"
    second_path.write_bytes(canonical_json_bytes(clone))
    residue = leave_verified_temp_residue(runtime_store)
    audit_before = (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    )

    with pytest.raises(ImmutableScienceRecordError, match="duplicate|record target"):
        runtime_store.recover_pending_transactions()

    assert first_path.exists() and second_path.exists()
    assert residue.exists()
    assert not runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    ).exists()
    assert (
        runtime_store.audit_path.read_bytes()
        if runtime_store.audit_path.exists()
        else b""
    ) == audit_before


def test_global_recovery_preflight_rejects_duplicate_journal_event_ids(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """One event ID cannot authorize two different record transactions."""
    payload, _, first_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:event-owner-a",
    )
    runtime_store.record_path("interpretations", payload["interpretation_id"]).unlink()
    second_path, clone = write_cloned_journal(runtime_store, journal)
    second_id = "sci-interpretation:event-owner-b"
    clone["record_id"] = second_id
    clone["record"]["interpretation_id"] = second_id
    clone["audit"]["target_id"] = second_id
    second_path.write_bytes(canonical_json_bytes(clone))
    residue = leave_verified_temp_residue(runtime_store)

    with pytest.raises(
        ImmutableScienceRecordError, match="duplicate.*event|event.*duplicate"
    ):
        runtime_store.recover_pending_transactions()

    assert first_path.exists() and second_path.exists() and residue.exists()
    assert not runtime_store.record_path("interpretations", second_id).exists()


def test_global_preflight_checks_existing_record_collisions_before_any_publish(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A late WAL collision must prevent an earlier valid WAL from publishing."""
    first_id = "sci-interpretation:preflight-first"
    payload, _, first_path, journal = leave_pending_interpretation(
        runtime_store, science_admin, monkeypatch, first_id
    )
    runtime_store.record_path("interpretations", first_id).unlink()
    second_path, clone = write_cloned_journal(runtime_store, journal)
    second_id = "sci-interpretation:preflight-existing-collision"
    clone["record_id"] = second_id
    clone["record"]["interpretation_id"] = second_id
    clone["audit"]["event_id"] = f"sci-audit:{uuid4()}"
    clone["audit"]["target_id"] = second_id
    second_path.write_bytes(canonical_json_bytes(clone))
    collision = interpretation_payload(second_id, model_id="existing-conflict")
    collision_path = runtime_store.record_path("interpretations", second_id)
    collision_path.write_bytes(canonical_json_bytes(collision))
    collision_path.chmod(0o600)

    with pytest.raises(ImmutableScienceRecordError, match="collision"):
        runtime_store.recover_pending_transactions()

    assert first_path.exists() and second_path.exists()
    assert not runtime_store.record_path("interpretations", first_id).exists()
    assert runtime_store.record_path(
        "interpretations", second_id
    ).read_bytes() == canonical_json_bytes(collision)
    assert payload["interpretation_id"] == first_id


def test_global_preflight_rejects_ledger_event_collision_before_record_publish(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A spoofed ledger row must be found before its WAL record becomes visible."""
    payload, _, journal_path, journal = leave_pending_interpretation(
        runtime_store,
        science_admin,
        monkeypatch,
        "sci-interpretation:ledger-preflight",
    )
    record_path = runtime_store.record_path(
        "interpretations", payload["interpretation_id"]
    )
    record_path.unlink()
    spoof = deepcopy(journal["audit"])
    spoof["actor"] = "999999"
    runtime_store.audit_path.write_bytes(canonical_json_bytes(spoof) + b"\n")
    runtime_store.audit_path.chmod(0o600)
    residue = leave_verified_temp_residue(runtime_store)

    with pytest.raises(
        ImmutableScienceRecordError, match="event.*collision|collision.*event"
    ):
        runtime_store.recover_pending_transactions()

    assert journal_path.exists() and residue.exists()
    assert not record_path.exists()


def leave_pending_approval(
    runtime_store: ScienceRuntimeStore,
    proposer: AuthIdentity,
    approver: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, Path, Path, dict[str, object]]:
    proposal = save_proposal_fixture(
        runtime_store,
        identity=proposer,
        domain="lithography",
        kind="concept_link",
        payload={"from": "RPM", "to": "rotational_speed"},
        key_label="pending-approval",
    )
    before = set(runtime_store.pending_transaction_ids())
    real_append = runtime_store._append_audit_event_locked

    def fail_approval_audit(event: ScienceAuditRecord):
        if event.action == "proposal_approved_for_release_candidate":
            raise OSError("injected pending approval")
        return real_append(event)

    monkeypatch.setattr(
        runtime_store, "_append_audit_event_locked", fail_approval_audit
    )
    with pytest.raises(ScienceTransactionPendingError):
        runtime_store.approve_proposal(proposal.proposal_id, identity=approver)
    monkeypatch.setattr(runtime_store, "_append_audit_event_locked", real_append)
    transaction_id = (set(runtime_store.pending_transaction_ids()) - before).pop()
    journal_path = runtime_store.record_path("transactions", transaction_id)
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    approval_path = runtime_store.record_path(
        "proposal-approvals", journal["record_id"]
    )
    return proposal, journal_path, approval_path, journal


def test_approval_recovery_requires_existing_source_proposal(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A self-consistent approval WAL cannot invent a nonexistent proposal."""
    proposal, journal_path, approval_path, _ = leave_pending_approval(
        runtime_store,
        AuthIdentity(employee_id="100003", display_name="proposer"),
        science_admin,
        monkeypatch,
    )
    runtime_store.record_path("proposals", proposal.proposal_id).unlink()
    approval_path.unlink()
    audit_before = runtime_store.audit_path.read_bytes()

    with pytest.raises(
        ImmutableScienceRecordError, match="proposal.*missing|dependency"
    ):
        runtime_store.recover_pending_transactions()

    assert journal_path.exists() and not approval_path.exists()
    assert runtime_store.audit_path.read_bytes() == audit_before


def test_approval_recovery_rejects_self_consistent_proposal_mismatch(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Approval fields and snapshot must still match the referenced proposal bytes."""
    _, journal_path, approval_path, journal = leave_pending_approval(
        runtime_store,
        AuthIdentity(employee_id="100003", display_name="proposer"),
        science_admin,
        monkeypatch,
    )
    approval_path.unlink()
    journal["record"]["domain"] = "materials"
    journal["record"]["proposal_kind"] = "term_alias"
    journal["audit"]["details"]["domain"] = "materials"
    snapshot = journal["record"].get("authority_snapshot")
    if snapshot:
        snapshot["domain"] = "materials"
        snapshot["proposal_kind"] = "term_alias"
    journal_path.write_bytes(canonical_json_bytes(journal))

    with pytest.raises(ImmutableScienceRecordError, match="proposal.*mismatch|linkage"):
        runtime_store.recover_pending_transactions()

    assert journal_path.exists() and not approval_path.exists()


def test_approval_recovery_requires_proposal_derived_approval_id(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A separate valid approval UUID cannot be attached to a real proposal."""
    _, journal_path, approval_path, journal = leave_pending_approval(
        runtime_store,
        AuthIdentity(employee_id="100003", display_name="proposer"),
        science_admin,
        monkeypatch,
    )
    approval_path.unlink()
    unrelated_id = f"sci-approval:{uuid4()}"
    journal["record_id"] = unrelated_id
    journal["record"]["approval_id"] = unrelated_id
    journal["audit"]["details"]["approval_id"] = unrelated_id
    journal_path.write_bytes(canonical_json_bytes(journal))

    with pytest.raises(ImmutableScienceRecordError, match="proposal.*linkage|linkage"):
        runtime_store.recover_pending_transactions()

    assert journal_path.exists()
    assert not runtime_store.record_path("proposal-approvals", unrelated_id).exists()


def test_approval_recovery_preserves_historical_trusted_authority_snapshot(
    runtime_store: ScienceRuntimeStore,
    monkeypatch: pytest.MonkeyPatch,
):
    """Role changes after a crash must not rewrite the authorized past decision."""
    proposal, _, _, journal = leave_pending_approval(
        runtime_store,
        AuthIdentity(employee_id="100003", display_name="proposer"),
        AuthIdentity(employee_id="200002", display_name="domain reviewer"),
        monkeypatch,
    )
    runtime_root = runtime_store.root
    runtime_store.close()

    recovered = ScienceRuntimeStore(
        runtime_root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=lambda identity: [],
    )
    approval_id = journal["record_id"]
    approval = recovered._load(
        "proposal-approvals", approval_id, ScienceProposalApproval
    )

    assert approval.proposal_id == proposal.proposal_id
    assert (
        approval.authority_snapshot.authority_role == "science.power_user:lithography"
    )
    assert approval.authority_snapshot.approved_by == "200002"
    assert recovered.pending_transaction_ids() == []


def test_public_append_audit_half_row_process_crash_recovers_from_audit_wal(
    runtime_store: ScienceRuntimeStore,
):
    """The public audit interface must not leave an unbound partial-row startup DoS."""
    runtime_root = runtime_store.root
    runtime_store.close()
    script = r"""
import os
import sys
from pathlib import Path

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import ScienceAuthorization
from boi_api.app.science.storage import ScienceRuntimeStore

store = ScienceRuntimeStore(
    Path(sys.argv[1]),
    authorization=ScienceAuthorization("pilot"),
    roles_for=lambda identity: ["science.admin"],
)
real_write_all = store._write_all

def crash_on_audit_row(descriptor, data):
    if data.endswith(b"\n"):
        os.write(descriptor, data[: max(1, len(data) // 2)])
        os.fsync(descriptor)
        os._exit(31)
    return real_write_all(descriptor, data)

store._write_all = crash_on_audit_row
store.append_audit(
    identity=AuthIdentity(employee_id="100001", display_name="audit writer"),
    action="standalone_note_recorded",
    target_id="sci-note:00000000-0000-4000-8000-000000000040",
    details={"note_digest": sys.argv[2]},
)
"""
    crashed = subprocess.run(
        [sys.executable, "-c", script, str(runtime_root), digest("audit-crash")],
        cwd=Path(__file__).parents[1],
        check=False,
        timeout=10,
    )
    assert crashed.returncode == 31

    recovered = ScienceRuntimeStore(
        runtime_root,
        authorization=ScienceAuthorization("pilot"),
        roles_for=science_roles,
    )

    rows = [
        json.loads(line)
        for line in recovered.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["target_id"] for row in rows] == [
        "sci-note:00000000-0000-4000-8000-000000000040"
    ]
    assert recovered.pending_transaction_ids() == []
