from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
)
from boi_api.app.science.digests import canonical_json_bytes
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
    ScienceAuditRecord,
    ScienceSensitivePersistenceError,
    ScienceTransactionPendingError,
    UnsafeScienceRuntimePathError,
    ScienceRuntimeStore,
)


def digest(label: str) -> str:
    return "sha256:" + sha256(label.encode("utf-8")).hexdigest()


def interpretation_payload(
    interpretation_id: str = "sci-interpretation:fixture",
    *,
    model_id: str = "fixture-model",
) -> dict[str, object]:
    return {
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


def report_payload(report_id: str = "sci-report:fixture") -> dict[str, object]:
    return {
        "report_id": report_id,
        "document_ref": "boi:public:science:fixture",
        "document_digest": digest("document"),
        "release_selection": {
            "foundation": "sci-release:foundation:0.1.0",
            "domains": [],
            "applications": [],
        },
        "release_digests": {"sci-release:foundation:0.1.0": "sha256:foundation"},
        "interpretation_ids": ["sci-interpretation:fixture"],
        "verdict_packets": [],
        "unresolved_ambiguities": [],
        "annotations": [],
        "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "created_by": "100001",
        "report_digest": digest("report"),
    }


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
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
            interpretation_payload(model_id=model_id), identity=caller
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
    proposal = runtime_store.save_proposal(
        identity=lithography_power_user,
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
    )

    with pytest.raises(ScienceAuthorizationError, match="self-approval"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            identity=lithography_power_user,
        )


def test_power_user_approval_is_domain_scoped_and_keeps_proposal_immutable(
    runtime_store: ScienceRuntimeStore,
):
    """Ignoring the proposal domain would let one pilot curate every domain."""
    proposal = runtime_store.save_proposal(
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="concept_link",
        payload={"from": "RPM", "to": "rotational_speed"},
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
    """Replacing the Science role check with boi.admin would invert the authority model."""
    proposal = runtime_store.save_proposal(
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="materials",
        kind="term_meaning",
        payload={"term": "film"},
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
    """Audit serialization must not retain endpoint or credential values at any depth."""
    runtime_store.append_audit(
        identity=science_admin,
        action="interpretation_saved",
        target_id="sci-interpretation:fixture",
        details={
            "document_digest": digest("document"),
        },
    )
    runtime_store.append_audit(
        identity=AuthIdentity(employee_id="100002", display_name="power user"),
        action="proposal_saved",
        target_id="sci-proposal:00000000-0000-4000-8000-000000000001",
        details={"domain": "lithography", "kind": "term_alias"},
    )

    raw = runtime_store.audit_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row["action"] for row in rows[-2:]] == [
        "interpretation_saved",
        "proposal_saved",
    ]
    assert rows[-2]["details"] == {
        "document_digest": digest("document"),
    }
    assert runtime_store.audit_path.stat().st_mode & 0o777 == 0o600


def test_proposal_authorship_and_approval_use_one_trusted_identity_resolver(
    runtime_store: ScienceRuntimeStore,
):
    """A caller must not forge another author or independently submit approval roles."""
    attacker = AuthIdentity(
        employee_id="100002",
        display_name="attacker",
        roles=["science.admin"],  # deliberately disagrees with the trusted resolver
    )
    proposal = runtime_store.save_proposal(
        identity=attacker,
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
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
            "sci-interpretation:fixture",
            {"document_digest": digest("document")},
        ),
        (
            AuthIdentity(employee_id="sk-live-secret", display_name="bad"),
            "sci-interpretation:fixture",
            {"document_digest": digest("document")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "https://internal.invalid/token=target-secret",
            {"document_digest": digest("document")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "internal.invalid:1236",
            {"document_digest": digest("document")},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-interpretation:fixture",
            {"document_digest": "Bearer detail-secret"},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-interpretation:fixture",
            {"document_digest": "endpoint=https://internal.invalid/v1"},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-interpretation:fixture",
            {
                "document_digest": digest("document"),
                "apiKey": "camel-secret",
            },
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-interpretation:fixture",
            {
                "document_digest": digest("document"),
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
            action="interpretation_saved",
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
    with pytest.raises(ValidationError, match="Extra inputs"):
        runtime_store.append_audit(
            identity=science_admin,
            action="interpretation_saved",
            target_id="sci-interpretation:fixture",
            details={"document_digest": digest("document"), "note": "safe"},
        )


def test_audit_short_write_is_completed_as_one_valid_json_row(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """Treating a short write as final would leave a corrupt JSON fragment."""
    real_write = os.write
    calls = 0

    def short_once(descriptor: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, data[: max(1, len(data) // 2)])
        return real_write(descriptor, data)

    monkeypatch.setattr(os, "write", short_once)
    runtime_store.append_audit(
        identity=science_admin,
        action="interpretation_saved",
        target_id="sci-interpretation:short-write",
        details={"document_digest": digest("document")},
    )

    rows = [
        json.loads(line)
        for line in runtime_store.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["target_id"] == "sci-interpretation:short-write"
    assert calls >= 2


def test_audit_mid_row_error_rolls_back_and_fsyncs_previous_eof(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    monkeypatch: pytest.MonkeyPatch,
):
    """A second-write exception must leave the prior JSONL bytes exactly intact."""
    runtime_store.append_audit(
        identity=science_admin,
        action="interpretation_saved",
        target_id="sci-interpretation:seed",
        details={"document_digest": digest("seed")},
    )
    before = runtime_store.audit_path.read_bytes()
    real_write = os.write
    calls = 0

    def partial_then_error(descriptor: int, data: bytes) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_write(descriptor, data[: max(1, len(data) // 2)])
        raise OSError("injected mid-row failure")

    monkeypatch.setattr(os, "write", partial_then_error)
    with pytest.raises(OSError, match="injected mid-row failure"):
        runtime_store.append_audit(
            identity=science_admin,
            action="interpretation_saved",
            target_id="sci-interpretation:failed",
            details={"document_digest": digest("failed")},
        )
    assert runtime_store.audit_path.read_bytes() == before


def test_record_load_rejects_final_component_symlink(
    runtime_store: ScienceRuntimeStore,
    science_admin: AuthIdentity,
    tmp_path: Path,
):
    """Following a same-name symlink would let approval consume an external record."""
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
    """An exact-record retry must not report success while its journal remains unaudited."""
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
    proposal = runtime_store.save_proposal(
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
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
    proposal = runtime_store.save_proposal(
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="materials",
        kind="concept_link",
        payload={"from": "film", "to": "material_layer"},
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
    """Matching approver alone must not authorize a noncanonical or mislinked approval."""
    proposal = runtime_store.save_proposal(
        identity=AuthIdentity(employee_id="100003", display_name="proposer"),
        domain="lithography",
        kind="term_meaning",
        payload={"term": "film"},
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
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
    report = runtime_store.save_report(report_payload(), identity=science_admin)
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
    """Startup must recover a journal-related partial audit and exact private temp residues."""
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
    descriptor = os.open(root / collection / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
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
