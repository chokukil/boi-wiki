from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
)
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
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
        "release_digests": {
            "sci-release:foundation:0.1.0": "sha256:foundation"
        },
        "interpretation_ids": ["sci-interpretation:fixture"],
        "verdict_packets": [],
        "unresolved_ambiguities": [],
        "annotations": [],
        "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "created_by": "100001",
        "report_digest": "sha256:report",
    }


@pytest.fixture
def runtime_store(tmp_path: Path) -> ScienceRuntimeStore:
    return ScienceRuntimeStore(
        tmp_path / "science-runtime",
        authorization=ScienceAuthorization(access_mode="pilot"),
    )


@pytest.fixture
def lithography_power_user() -> AuthIdentity:
    return AuthIdentity(
        employee_id="100002",
        display_name="lithography reviewer",
        roles=["boi.viewer", "science.power_user:lithography"],
    )


def test_save_interpretation_is_idempotent_but_rejects_changed_canonical_bytes(
    runtime_store: ScienceRuntimeStore,
):
    """An existing record ID must never be overwritten with changed content."""
    original = runtime_store.save_interpretation(
        interpretation_payload(), actor="100001"
    )
    repeated = runtime_store.save_interpretation(
        interpretation_payload(), actor="100001"
    )

    assert repeated == original
    with pytest.raises(ImmutableScienceRecordError, match="immutable record collision"):
        runtime_store.save_interpretation(
            interpretation_payload(model_id="changed-model"), actor="100001"
        )
    assert runtime_store.load_interpretation(original.interpretation_id) == original


def test_save_report_uses_private_permissions_and_leaves_no_temp_files(
    runtime_store: ScienceRuntimeStore,
):
    """A permissive mode or leaked temp file would expose immutable report contents."""
    report = runtime_store.save_report(report_payload(), actor="100001")
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
        return runtime_store.save_interpretation(
            interpretation_payload(model_id=model_id), actor=model_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(save, model_id) for model_id in ("model-a", "model-b")]
        outcomes: list[object] = []
        errors: list[BaseException] = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except BaseException as exc:  # the exception itself is the concurrency outcome
                errors.append(exc)

    assert len(outcomes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ImmutableScienceRecordError)
    persisted = runtime_store.load_interpretation("sci-interpretation:fixture")
    assert persisted.model_id in {"model-a", "model-b"}


def test_atomic_replace_failure_does_not_publish_or_leave_temporary_bytes(
    runtime_store: ScienceRuntimeStore, monkeypatch: pytest.MonkeyPatch
):
    """A failed publication must not leave a partial final or reusable temp file."""
    real_replace = os.replace

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    payload = interpretation_payload("sci-interpretation:replace-failure")
    with pytest.raises(OSError, match="simulated replace failure"):
        runtime_store.save_interpretation(payload, actor="100001")
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
        actor="100002",
        domain="lithography",
        kind="term_alias",
        payload={"alias": "PR"},
    )

    with pytest.raises(ScienceAuthorizationError, match="self-approval"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            actor="100002",
            roles=lithography_power_user.roles,
        )


def test_power_user_approval_is_domain_scoped_and_keeps_proposal_immutable(
    runtime_store: ScienceRuntimeStore,
):
    """Ignoring the proposal domain would let one pilot curate every domain."""
    proposal = runtime_store.save_proposal(
        actor="100003",
        domain="lithography",
        kind="concept_link",
        payload={"from": "RPM", "to": "rotational_speed"},
    )
    original_path = runtime_store.record_path("proposals", proposal.proposal_id)
    original_bytes = original_path.read_bytes()

    with pytest.raises(ScienceAuthorizationError, match="domain"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            actor="200001",
            roles=["science.power_user:materials"],
        )

    approval = runtime_store.approve_proposal(
        proposal.proposal_id,
        actor="200002",
        roles=["science.power_user:lithography"],
    )
    assert approval.status == "release_candidate"
    assert approval.domain == "lithography"
    assert original_path.read_bytes() == original_bytes


def test_science_admin_can_approve_without_inheriting_boi_admin(
    runtime_store: ScienceRuntimeStore,
):
    """Replacing the Science role check with boi.admin would invert the authority model."""
    proposal = runtime_store.save_proposal(
        actor="100003", domain="materials", kind="term_meaning", payload={"term": "film"}
    )

    with pytest.raises(ScienceAuthorizationError, match="approval"):
        runtime_store.approve_proposal(
            proposal.proposal_id,
            actor="100001",
            roles=["boi.admin"],
        )
    approval = runtime_store.approve_proposal(
        proposal.proposal_id,
        actor="100001",
        roles=["science.admin"],
    )
    assert approval.approved_by == "100001"


def test_audit_rows_are_append_only_and_remove_nested_secrets_and_endpoints(
    runtime_store: ScienceRuntimeStore,
):
    """Audit serialization must not retain endpoint or credential values at any depth."""
    runtime_store.append_audit(
        actor="100001",
        action="interpretation_requested",
        target_id="sci-interpretation:fixture",
        details={
            "model_id": "qwen-fixture",
            "api_key": "secret-value",
            "endpoint": "http://internal.invalid/v1",
            "nested": {
                "authorization": "Bearer private-token",
                "safe": "kept",
            },
        },
    )
    runtime_store.append_audit(
        actor="100002",
        action="proposal_created",
        target_id="sci-proposal:fixture",
        details={"domain": "lithography"},
    )

    raw = runtime_store.audit_path.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row["action"] for row in rows[-2:]] == [
        "interpretation_requested",
        "proposal_created",
    ]
    assert rows[-2]["details"] == {
        "model_id": "qwen-fixture",
        "nested": {"safe": "kept"},
    }
    assert "secret-value" not in raw
    assert "internal.invalid" not in raw
    assert "private-token" not in raw
    assert runtime_store.audit_path.stat().st_mode & 0o777 == 0o600
