from __future__ import annotations

import pytest

from boi_api.app import auth as auth_module
from boi_api.app.auth import AuthIdentity, dev_identity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
    power_user_domains,
)


def identity(employee_id: str, *roles: str) -> AuthIdentity:
    return AuthIdentity(
        employee_id=employee_id,
        display_name=f"user-{employee_id}",
        roles=list(roles),
    )


def test_boi_admin_does_not_imply_science_admin():
    """Adding a boi.admin fallback would cross the Science authority boundary."""
    authz = ScienceAuthorization(access_mode="admin_only")
    generic_admin = identity("7", "boi.viewer", "boi.admin")

    assert not authz.can_access(generic_admin, roles=generic_admin.roles)
    with pytest.raises(ScienceAuthorizationError, match="Science Verifier access"):
        authz.require_access(generic_admin, roles=generic_admin.roles)
    with pytest.raises(ScienceAuthorizationError, match="science.admin"):
        authz.require_admin(
            generic_admin,
            roles_for=lambda resolved_identity: resolved_identity.roles,
        )


def test_admin_boundary_resolves_roles_for_the_authenticated_identity():
    """Accepting a caller-supplied role list would let a mutation forge final authority."""
    authz = ScienceAuthorization(access_mode="admin_only")
    caller = identity("7", "science.admin")
    resolved_employee_ids: list[str] = []

    def trusted_roles(resolved_identity: AuthIdentity) -> list[str]:
        resolved_employee_ids.append(resolved_identity.employee_id)
        return ["boi.admin"]

    with pytest.raises(ScienceAuthorizationError, match="science.admin"):
        authz.require_admin(caller, roles_for=trusted_roles)
    assert resolved_employee_ids == ["7"]


@pytest.mark.parametrize(
    ("access_mode", "roles", "expected"),
    [
        ("admin_only", ["science.admin"], True),
        ("admin_only", ["science.user"], False),
        ("pilot", ["science.admin"], True),
        ("pilot", ["science.power_user:lithography"], True),
        ("pilot", ["science.user"], True),
        ("pilot", ["boi.viewer"], False),
        ("open", ["boi.viewer"], True),
        ("open", [], False),
    ],
)
def test_access_mode_uses_only_the_complete_resolved_role_list(
    access_mode: str, roles: list[str], expected: bool
):
    """Falling back to identity.roles would bypass the caller's resolved-role decision."""
    authz = ScienceAuthorization(access_mode=access_mode)
    user = identity("8", "science.admin", "boi.viewer")

    assert authz.can_access(user, roles=roles) is expected


def test_science_access_mode_rejects_unknown_policy():
    """Silently treating a misspelled policy as open would expose the verifier."""
    with pytest.raises(ValueError, match="access mode"):
        ScienceAuthorization(access_mode="public")


def test_power_user_domains_accept_only_well_formed_domain_roles():
    """An empty or nested role suffix must not become a curation domain."""
    assert power_user_domains(
        [
            "science.power_user:lithography",
            "science.power_user:materials-science",
            "science.power_user:",
            "science.power_user:lithography:admin",
            "science.user",
        ]
    ) == {"lithography", "materials-science"}


def test_development_identities_receive_only_the_explicit_science_roles():
    """Changing shared BoI roles must not grant Science authority to other dev users."""
    admin = dev_identity("100001")
    power_user = dev_identity("100002")
    viewer = dev_identity("100003")

    assert "science.admin" in admin.roles
    assert "science.power_user:lithography" in power_user.roles
    assert not any(role.startswith("science.") for role in viewer.roles)
    assert "boi.promoter" in power_user.roles
    assert "boi.viewer" in viewer.roles


def test_non_admin_service_identity_does_not_inherit_development_science_admin(
    monkeypatch: pytest.MonkeyPatch,
):
    """Sharing the generic dev-admin list would leak Science admin to every service token."""
    monkeypatch.setattr(auth_module, "hcp_permissions", lambda employee_id: {})

    service = auth_module.service_identity("100003")

    assert "boi.admin" in service.roles  # preserve the existing service-token behavior
    assert "science.admin" not in service.roles
