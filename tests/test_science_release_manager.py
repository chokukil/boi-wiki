from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from boi_api.app.auth import AuthIdentity
from boi_api.app.okf import split_frontmatter
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceOperationalError
from boi_api.app.science.release_manager import (
    ReleaseActivationAuthority,
    ScienceAuthorityRegistry,
    ScienceReleaseManager,
)


RELEASE_ID = "sci-release:test"
CANDIDATE_DIGEST = "sha256:" + "1" * 64
DECISION_DIGEST = "sha256:" + "2" * 64


def _request_digest(operation: str, release_digest: str) -> str:
    return sha256_digest(
        {
            "operation": operation,
            "release_id": RELEASE_ID,
            "release_digest": release_digest,
        }
    )


def _identity(employee_id: str = "admin-1") -> AuthIdentity:
    return AuthIdentity(
        employee_id=employee_id,
        display_name=employee_id,
        roles=["caller-written-role-is-not-trusted"],
        auth_source="oidc",
    )


def _release_metadata(*, state: str = "candidate", approved: bool = True) -> dict:
    is_active = state == "active"
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "sci_profile_version": "0.1",
        "type": "boi/science-release",
        "boi_id": "boi:public:science:release:test",
        "author": {"type": "agent", "agent_id": "builder"},
        "status": "approved" if approved else "draft",
        "review": {
            "review_status": "approved" if approved else "pending_review",
            "authorized_review_events": (
                [
                    {
                        "decision": "approved",
                        "actor": {"type": "human", "user_id": "reviewer-1"},
                        "occurred_at": "2026-08-25T09:30:00+09:00",
                    }
                ]
                if approved
                else []
            ),
        },
        "science": {
            "release_id": RELEASE_ID,
            "content_hash": CANDIDATE_DIGEST,
            "frozen_release_content_hash": CANDIDATE_DIGEST,
            "decision_material_digest": DECISION_DIGEST,
            "status": "active" if is_active else "release_candidate",
            "active": is_active,
            "release_eligibility": (
                "active_release_eligible"
                if approved
                else "blocked_pending_authorized_admin_review"
            ),
            "component_digests": {"sci:rule:test": "sha256:" + "3" * 64},
        },
    }
    if is_active:
        metadata["activation"] = {
            "activation_status": "active",
            "authorized_activation_events": [
                {
                    "decision": "activated",
                    "operation": "activate",
                    "actor": {"type": "human", "user_id": "admin-1"},
                    "occurred_at": "2026-08-25T09:40:00+09:00",
                    "release_digest": CANDIDATE_DIGEST,
                    "request_digest": _request_digest("activate", CANDIDATE_DIGEST),
                    "idempotency_key_digest": sha256_digest("previous-key"),
                }
            ],
        }
    return metadata


def _write_release(boi_root: Path, metadata: dict) -> Path:
    path = boi_root / "public/science/releases/science-release-test.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
        + "---\n# Science Release test\n",
        encoding="utf-8",
    )
    return path


def _read_release(path: Path) -> dict:
    metadata, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    return metadata


class _FakeCatalog:
    def __init__(self, boi_root: Path):
        self.boi_root = Path(boi_root)
        matches = list(
            (self.boi_root / "public/science/releases").glob("*.md")
        )
        if len(matches) != 1:
            raise ScienceOperationalError("fixture release is unavailable")
        self.metadata = _read_release(matches[0])

    def resolve_release(self, release_id: str):
        science = self.metadata["science"]
        if release_id != science["release_id"]:
            raise ScienceOperationalError("unknown Release")
        return SimpleNamespace(
            release_id=release_id,
            content_hash=science["content_hash"],
            frozen_release_content_hash=science.get("frozen_release_content_hash"),
            decision_material_digest=science.get("decision_material_digest"),
            status=science["status"],
            component_digests=science.get("component_digests", {}),
        )

    def active_release(self):
        release = self.resolve_release(RELEASE_ID)
        if release.status != "active" or self.metadata["science"].get("active") is not True:
            raise ScienceOperationalError("no active Release")
        return release

    def resolve_release_set(self, selection):
        release = self.resolve_release(selection.foundation)
        return SimpleNamespace(foundation_release=release)

    def resolve_operational_rule_set(self, release_set):
        if release_set.foundation_release.status != "active":
            raise ScienceOperationalError("not operational")
        return SimpleNamespace(capability_digest="sha256:" + "9" * 64)

    def resolve_independent_holdout_qualification(self, release):
        return {
            "release_id": release.release_id,
            "object_digest": "sha256:" + "5" * 64,
            "result_digest": "sha256:" + "6" * 64,
            "qualification_gate": "G5",
        }


def _authority(*, release_digest: str = CANDIDATE_DIGEST) -> ReleaseActivationAuthority:
    payload = {
        "schema_version": "science-release-activation-authority/0.1",
        "release_id": RELEASE_ID,
        "release_digest": release_digest,
        "decision_material_digest": DECISION_DIGEST,
        "holdout_manifest_digest": "sha256:" + "5" * 64,
        "holdout_result_digest": "sha256:" + "6" * 64,
        "channel_parity_digest": "sha256:" + "7" * 64,
        "channel_parity_status": "passed",
        "qualification_status": "passed",
    }
    return ReleaseActivationAuthority(
        **payload,
        authority_digest=sha256_digest(payload),
    )


def _manager(
    boi_root: Path,
    *,
    roles_for=lambda employee_id: ["science.admin"],
    capability_validator=lambda **_kwargs: _authority(),
    catalog_factory=lambda root: _FakeCatalog(root),
    reload_callback=lambda _catalog: None,
) -> ScienceReleaseManager:
    lock_runtime = boi_root / "private-runtime"
    lock_runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_runtime.chmod(0o700)
    return ScienceReleaseManager(
        boi_root=boi_root,
        lock_root=lock_runtime / "locks",
        catalog_factory=catalog_factory,
        capability_validator=capability_validator,
        roles_for=roles_for,
        clock=lambda: datetime.fromisoformat("2026-08-25T10:00:00+09:00"),
        reload_callback=reload_callback,
    )


def test_activate_rechecks_trusted_admin_role_and_leaves_release_unchanged(
    tmp_path: Path,
):
    release_path = _write_release(tmp_path, _release_metadata())
    before = release_path.read_bytes()
    manager = _manager(tmp_path, roles_for=lambda _employee_id: [])

    with pytest.raises(ScienceOperationalError, match="science.admin"):
        manager.activate(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("activate", CANDIDATE_DIGEST),
            idempotency_key="activation-key-001",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before


@pytest.mark.parametrize("mismatch", ["release", "request"])
def test_activate_rejects_non_exact_release_or_request_digest(
    tmp_path: Path, mismatch: str
):
    release_path = _write_release(tmp_path, _release_metadata())
    before = release_path.read_bytes()
    release_digest = (
        "sha256:" + "8" * 64 if mismatch == "release" else CANDIDATE_DIGEST
    )
    request_digest = _request_digest("activate", CANDIDATE_DIGEST)
    if mismatch == "request":
        request_digest = "sha256:" + "8" * 64

    with pytest.raises(ScienceOperationalError, match="digest"):
        _manager(tmp_path).activate(
            release_id=RELEASE_ID,
            release_digest=release_digest,
            request_digest=request_digest,
            idempotency_key="activation-key-002",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before


def test_activate_requires_preapproved_release_and_does_not_auto_approve(tmp_path: Path):
    release_path = _write_release(tmp_path, _release_metadata(approved=False))
    before = release_path.read_bytes()

    with pytest.raises(ScienceOperationalError, match="already Admin-approved"):
        _manager(tmp_path).activate(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("activate", CANDIDATE_DIGEST),
            idempotency_key="activation-key-003",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before
    assert _read_release(release_path)["status"] == "draft"


def test_activate_requires_exact_holdout_and_channel_parity_authority(tmp_path: Path):
    release_path = _write_release(tmp_path, _release_metadata())
    before = release_path.read_bytes()

    def unavailable(**_kwargs):
        raise ScienceOperationalError("sealed holdout/channel parity unavailable")

    with pytest.raises(ScienceOperationalError, match="holdout/channel parity"):
        _manager(tmp_path, capability_validator=unavailable).activate(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("activate", CANDIDATE_DIGEST),
            idempotency_key="activation-key-004",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before


def test_activate_stages_then_atomically_publishes_exact_authorized_lifecycle(
    tmp_path: Path,
):
    release_path = _write_release(tmp_path, _release_metadata())
    reloaded: list[object] = []
    manager = _manager(tmp_path, reload_callback=reloaded.append)

    result = manager.activate(
        release_id=RELEASE_ID,
        release_digest=CANDIDATE_DIGEST,
        request_digest=_request_digest("activate", CANDIDATE_DIGEST),
        idempotency_key="activation-key-005",
        identity=_identity(),
    )

    stored = _read_release(release_path)
    assert result.operation == "activate"
    assert result.status == "active"
    assert result.input_release_digest == CANDIDATE_DIGEST
    assert result.decision_material_digest == DECISION_DIGEST
    assert result.authority_digest == _authority().authority_digest
    assert result.idempotent is False
    assert stored["status"] == "approved"
    assert stored["science"]["status"] == "active"
    assert stored["science"]["active"] is True
    assert stored["science"]["frozen_release_content_hash"] == CANDIDATE_DIGEST
    assert stored["science"]["decision_material_digest"] == DECISION_DIGEST
    assert stored["science"]["content_hash"] == result.resulting_release_digest
    _metadata, body = split_frontmatter(release_path.read_text(encoding="utf-8"))
    from boi_api.app.science.catalog import _release_manifest_digest

    assert stored["science"]["content_hash"] == _release_manifest_digest(
        stored, body
    )
    event = stored["activation"]["authorized_activation_events"][-1]
    assert event["actor"] == {"type": "human", "user_id": "admin-1"}
    assert event["release_digest"] == CANDIDATE_DIGEST
    assert event["request_digest"] == _request_digest(
        "activate", CANDIDATE_DIGEST
    )
    assert event["idempotency_key_digest"] == sha256_digest("activation-key-005")
    assert len(reloaded) == 1


def test_activate_is_exactly_idempotent_and_rejects_key_reuse(tmp_path: Path):
    release_path = _write_release(tmp_path, _release_metadata())
    manager = _manager(tmp_path)
    arguments = {
        "release_id": RELEASE_ID,
        "release_digest": CANDIDATE_DIGEST,
        "request_digest": _request_digest("activate", CANDIDATE_DIGEST),
        "idempotency_key": "activation-key-006",
        "identity": _identity(),
    }
    first = manager.activate(**arguments)
    after_first = release_path.read_bytes()

    second = manager.activate(**arguments)
    assert second.idempotent is True
    assert second.resulting_release_digest == first.resulting_release_digest
    assert release_path.read_bytes() == after_first

    with pytest.raises(ScienceOperationalError, match="idempotency"):
        manager.withdraw(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("withdraw", CANDIDATE_DIGEST),
            idempotency_key="activation-key-006",
            identity=_identity(),
        )


def test_idempotent_replay_returns_original_result_after_later_withdrawal(
    tmp_path: Path,
):
    release_path = _write_release(tmp_path, _release_metadata())
    manager = _manager(tmp_path)
    activation = manager.activate(
        release_id=RELEASE_ID,
        release_digest=CANDIDATE_DIGEST,
        request_digest=_request_digest("activate", CANDIDATE_DIGEST),
        idempotency_key="activation-history-001",
        identity=_identity(),
    )
    manager.withdraw(
        release_id=RELEASE_ID,
        release_digest=activation.resulting_release_digest,
        request_digest=_request_digest(
            "withdraw", activation.resulting_release_digest
        ),
        idempotency_key="withdraw-history-001",
        identity=_identity(),
    )
    after_withdrawal = release_path.read_bytes()

    replay = manager.activate(
        release_id=RELEASE_ID,
        release_digest=CANDIDATE_DIGEST,
        request_digest=_request_digest("activate", CANDIDATE_DIGEST),
        idempotency_key="activation-history-001",
        identity=_identity(),
    )

    assert replay.idempotent is True
    assert replay.status == "active"
    assert replay.resulting_release_digest == activation.resulting_release_digest
    assert release_path.read_bytes() == after_withdrawal


def test_activate_rolls_back_original_bytes_when_post_publish_reload_fails(
    tmp_path: Path,
):
    release_path = _write_release(tmp_path, _release_metadata())
    before = release_path.read_bytes()
    calls = 0

    def reload_fails_once(_catalog):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("reload failed")

    with pytest.raises(ScienceOperationalError, match="rolled back"):
        _manager(tmp_path, reload_callback=reload_fails_once).activate(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("activate", CANDIDATE_DIGEST),
            idempotency_key="activation-key-007",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before
    assert calls == 2


def test_withdraw_requires_current_active_digest_and_publishes_no_fallback(
    tmp_path: Path,
):
    metadata = _release_metadata(state="active")
    frozen_digest = metadata["science"]["frozen_release_content_hash"]
    active_digest = "sha256:" + "a" * 64
    metadata["science"]["content_hash"] = active_digest
    release_path = _write_release(tmp_path, metadata)
    manager = _manager(tmp_path)

    result = manager.withdraw(
        release_id=RELEASE_ID,
        release_digest=active_digest,
        request_digest=_request_digest("withdraw", active_digest),
        idempotency_key="withdraw-key-001",
        identity=_identity(),
    )

    stored = _read_release(release_path)
    assert result.operation == "withdraw"
    assert result.status == "withdrawn"
    assert stored["science"]["status"] == "withdrawn"
    assert stored["science"]["active"] is False
    assert stored["science"]["frozen_release_content_hash"] == frozen_digest
    assert stored["activation"]["activation_status"] == "withdrawn"
    assert stored["activation"]["authorized_activation_events"][-1][
        "decision"
    ] == "withdrawn"


def test_repository_candidate_is_rejected_and_unchanged(tmp_path: Path):
    from boi_api.app.science.catalog import ScienceCatalog

    boi_root = Path(__file__).resolve().parents[1] / "data/boi"
    catalog = ScienceCatalog(boi_root)
    release = catalog.resolve_release("sci-release:0.1.0")
    release_path = catalog._objects["release"][release.release_id].path
    before = release_path.read_bytes()
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(mode=0o700)
    manager = ScienceReleaseManager(
        boi_root=boi_root,
        lock_root=runtime_root / "locks",
        catalog_factory=lambda root: ScienceCatalog(root),
        capability_validator=lambda **_kwargs: _authority(
            release_digest=release.content_hash
        ),
        roles_for=lambda _employee_id: ["science.admin"],
        clock=lambda: datetime.fromisoformat("2026-08-25T10:00:00+09:00"),
        reload_callback=lambda _catalog: None,
    )

    with pytest.raises(ScienceOperationalError, match="already Admin-approved"):
        manager.activate(
            release_id=release.release_id,
            release_digest=release.content_hash,
            request_digest=sha256_digest(
                {
                    "operation": "activate",
                    "release_id": release.release_id,
                    "release_digest": release.content_hash,
                }
            ),
            idempotency_key="repository-candidate-001",
            identity=_identity(),
        )

    assert release_path.read_bytes() == before


def _authority_registry_payload() -> dict:
    record = {
        "release_id": RELEASE_ID,
        "frozen_release_content_hash": CANDIDATE_DIGEST,
        "decision_material_digest": DECISION_DIGEST,
        "component_digests": {"sci:rule:test": "sha256:" + "3" * 64},
        "holdout_manifest_digest": "sha256:" + "5" * 64,
        "holdout_result_digest": "sha256:" + "6" * 64,
        "rule_freeze_commit": "a" * 40,
        "channel_parity_digest": "sha256:" + "7" * 64,
        "channels": ["Web", "REST", "MCP", "Markdown", "PDF"],
        "channel_parity_status": "passed",
        "qualification_status": "passed",
    }
    record["record_digest"] = sha256_digest(record)
    payload = {
        "schema_version": "science-release-authority-registry/0.1",
        "entries": [record],
    }
    payload["registry_digest"] = sha256_digest(payload)
    return payload


def _write_authority_registry(runtime_root: Path, payload: dict) -> Path:
    runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime_root.chmod(0o700)
    path = runtime_root / "authority/science-release-authority-registry.json"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    import json

    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    path.chmod(0o600)
    return path


def test_private_authority_registry_issues_exact_holdout_and_channel_parity_authority(
    tmp_path: Path,
):
    _write_release(tmp_path, _release_metadata())
    runtime_root = tmp_path / "runtime"
    _write_authority_registry(runtime_root, _authority_registry_payload())
    registry = ScienceAuthorityRegistry(runtime_root / "authority")
    catalog = _FakeCatalog(tmp_path)

    trusted_holdout = registry.trusted_holdout_resolver(
        {
            "release_id": RELEASE_ID,
            "frozen_release_content_hash": CANDIDATE_DIGEST,
        }
    )
    authority = registry.validate_activation_authority(
        catalog=catalog,
        release_id=RELEASE_ID,
        release_digest=CANDIDATE_DIGEST,
        decision_material_digest=DECISION_DIGEST,
        operation="activate",
    )

    assert trusted_holdout == {
        "release_id": RELEASE_ID,
        "frozen_release_content_hash": CANDIDATE_DIGEST,
        "manifest_digest": "sha256:" + "5" * 64,
        "rule_freeze_commit": "a" * 40,
    }
    assert authority.channel_parity_status == "passed"
    assert authority.release_digest == CANDIDATE_DIGEST
    assert "admin_approval_digest" not in authority.model_dump(mode="json")
    assert authority.authority_digest == sha256_digest(
        authority.model_dump(mode="json", exclude={"authority_digest"})
    )


@pytest.mark.parametrize("tamper", ["registry_digest", "caller_verdict", "missing_pdf"])
def test_private_authority_registry_rejects_tamper_or_incomplete_channel_parity(
    tmp_path: Path, tamper: str
):
    payload = _authority_registry_payload()
    if tamper == "registry_digest":
        payload["registry_digest"] = "sha256:" + "0" * 64
    elif tamper == "caller_verdict":
        payload["entries"][0]["verdict"] = "VIOLATION"
        payload["entries"][0]["record_digest"] = sha256_digest(
            {
                key: value
                for key, value in payload["entries"][0].items()
                if key != "record_digest"
            }
        )
        payload["registry_digest"] = sha256_digest(
            {key: value for key, value in payload.items() if key != "registry_digest"}
        )
    else:
        payload["entries"][0]["channels"].remove("PDF")
        payload["entries"][0]["record_digest"] = sha256_digest(
            {
                key: value
                for key, value in payload["entries"][0].items()
                if key != "record_digest"
            }
        )
        payload["registry_digest"] = sha256_digest(
            {key: value for key, value in payload.items() if key != "registry_digest"}
        )
    runtime_root = tmp_path / "runtime"
    _write_authority_registry(runtime_root, payload)
    registry = ScienceAuthorityRegistry(runtime_root / "authority")

    with pytest.raises(ScienceOperationalError, match="authority registry"):
        registry.trusted_holdout_resolver(
            {
                "release_id": RELEASE_ID,
                "frozen_release_content_hash": CANDIDATE_DIGEST,
            }
        )


def test_private_authority_registry_fails_closed_when_missing(tmp_path: Path):
    registry = ScienceAuthorityRegistry(tmp_path / "runtime/authority")

    with pytest.raises(ScienceOperationalError, match="authority registry"):
        registry.validate_activation_authority(
            catalog=SimpleNamespace(),
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            decision_material_digest=DECISION_DIGEST,
            operation="activate",
        )


def test_private_authority_registry_rejects_group_writable_runtime_parent(
    tmp_path: Path,
):
    runtime_root = tmp_path / "runtime"
    _write_authority_registry(runtime_root, _authority_registry_payload())
    runtime_root.chmod(0o770)
    registry = ScienceAuthorityRegistry(runtime_root / "authority")

    with pytest.raises(ScienceOperationalError, match="authority registry"):
        registry.trusted_holdout_resolver(
            {
                "release_id": RELEASE_ID,
                "frozen_release_content_hash": CANDIDATE_DIGEST,
            }
        )


def test_release_manager_rejects_symlink_lock_root(tmp_path: Path):
    _write_release(tmp_path, _release_metadata())
    actual = tmp_path / "actual-locks"
    actual.mkdir(mode=0o700)
    runtime = tmp_path / "private-runtime"
    runtime.mkdir(mode=0o700)
    (runtime / "locks").symlink_to(actual, target_is_directory=True)
    manager = ScienceReleaseManager(
        boi_root=tmp_path,
        lock_root=runtime / "locks",
        catalog_factory=lambda root: _FakeCatalog(root),
        capability_validator=lambda **_kwargs: _authority(),
        roles_for=lambda _employee_id: ["science.admin"],
        clock=lambda: datetime.fromisoformat("2026-08-25T10:00:00+09:00"),
        reload_callback=lambda _catalog: None,
    )

    with pytest.raises(ScienceOperationalError, match="mutation lock"):
        manager.activate(
            release_id=RELEASE_ID,
            release_digest=CANDIDATE_DIGEST,
            request_digest=_request_digest("activate", CANDIDATE_DIGEST),
            idempotency_key="activation-key-symlink",
            identity=_identity(),
        )
