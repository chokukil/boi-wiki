from __future__ import annotations

import json
import os
import shutil
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
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
    ScienceSensitivePersistenceError,
    ScienceTransactionPendingError,
    UnsafeScienceRuntimePathError,
    ScienceRuntimeStore,
)


def interpretation_payload(
    interpretation_id: str = "sci-interpretation:fixture",
    *,
    model_id: str = "fixture-model",
) -> dict[str, object]:
    return {
        "interpretation_id": interpretation_id,
        "document_digest": "sha256:document",
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
        "response_digest": "sha256:response",
    }


def report_payload(report_id: str = "sci-report:fixture") -> dict[str, object]:
    return {
        "report_id": report_id,
        "document_ref": "boi:public:science:fixture",
        "document_digest": "sha256:document",
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
        "report_digest": "sha256:report",
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

    def save(model_id: str):
        barrier.wait()
        caller = AuthIdentity(employee_id=model_id, display_name=model_id)
        return runtime_store.save_interpretation(
            interpretation_payload(model_id=model_id), identity=caller
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(save, model_id) for model_id in ("model-a", "model-b")
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
            "document_digest": "sha256:document",
        },
    )
    runtime_store.append_audit(
        identity=AuthIdentity(employee_id="100002", display_name="power user"),
        action="proposal_saved",
        target_id="sci-proposal:fixture",
        details={"domain": "lithography", "kind": "term_alias"},
    )

    raw = runtime_store.audit_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row["action"] for row in rows[-2:]] == [
        "interpretation_saved",
        "proposal_saved",
    ]
    assert rows[-2]["details"] == {
        "document_digest": "sha256:document",
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
            {"document_digest": "sha256:document"},
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "https://internal.invalid/token=target-secret",
            {"document_digest": "sha256:document"},
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
                "document_digest": "sha256:document",
                "apiKey": "camel-secret",
            },
        ),
        (
            AuthIdentity(employee_id="100001", display_name="bad"),
            "sci-interpretation:fixture",
            {
                "document_digest": "sha256:document",
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
            details={"document_digest": "sha256:document", "note": "safe"},
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
        details={"document_digest": "sha256:document"},
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
        details={"document_digest": "sha256:seed"},
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
            details={"document_digest": "sha256:failed"},
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
