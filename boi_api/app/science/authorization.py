"""Explicit, product-local authorization for Science Verifier operations."""

from __future__ import annotations

import re
from collections.abc import Sequence

from boi_api.app.auth import AuthIdentity


SCIENCE_ADMIN_ROLE = "science.admin"
SCIENCE_USER_ROLE = "science.user"
SCIENCE_POWER_USER_PREFIX = "science.power_user:"
_ACCESS_MODES = {"admin_only", "pilot", "open"}
_DOMAIN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ScienceAuthorizationError(PermissionError):
    """The resolved Science roles do not authorize an operation."""


def power_user_domains(roles: Sequence[str]) -> set[str]:
    """Return only well-formed domain grants from a complete resolved role list."""

    domains: set[str] = set()
    for role in roles:
        if not isinstance(role, str) or not role.startswith(SCIENCE_POWER_USER_PREFIX):
            continue
        domain = role.removeprefix(SCIENCE_POWER_USER_PREFIX)
        if _DOMAIN_PATTERN.fullmatch(domain):
            domains.add(domain)
    return domains


class ScienceAuthorization:
    """Keep Science access and curation roles independent from generic BoI roles."""

    def __init__(self, access_mode: str):
        normalized = access_mode.strip().lower() if isinstance(access_mode, str) else ""
        if normalized not in _ACCESS_MODES:
            raise ValueError(f"invalid Science access mode: {access_mode!r}")
        self.access_mode = normalized

    @staticmethod
    def _role_set(roles: Sequence[str]) -> set[str]:
        return {role for role in roles if isinstance(role, str) and role}

    def can_access(self, identity: AuthIdentity, roles: Sequence[str]) -> bool:
        """Evaluate access from the supplied resolved roles, never identity fallbacks."""

        resolved = self._role_set(roles)
        if SCIENCE_ADMIN_ROLE in resolved:
            return True
        if self.access_mode == "admin_only":
            return False
        if self.access_mode == "pilot":
            return SCIENCE_USER_ROLE in resolved or bool(power_user_domains(tuple(resolved)))
        return bool(identity.employee_id.strip()) and "boi.viewer" in resolved

    def require_access(self, identity: AuthIdentity, roles: Sequence[str]) -> None:
        if not self.can_access(identity, roles):
            raise ScienceAuthorizationError("Science Verifier access is not authorized")

    def require_admin(self, identity: AuthIdentity, roles: Sequence[str]) -> None:
        del identity
        if SCIENCE_ADMIN_ROLE not in self._role_set(roles):
            raise ScienceAuthorizationError("science.admin role required")

    def require_proposal_approval(
        self,
        *,
        actor: str,
        roles: Sequence[str],
        domain: str,
        proposed_by: str,
    ) -> None:
        """Authorize release-candidate inclusion without broadening Science authority."""

        resolved = self._role_set(roles)
        if SCIENCE_ADMIN_ROLE in resolved:
            return
        domains = power_user_domains(tuple(resolved))
        if domain not in domains:
            raise ScienceAuthorizationError(
                f"Science proposal approval requires authority for domain {domain!r}"
            )
        if actor == proposed_by:
            raise ScienceAuthorizationError(
                "Science Power User proposal self-approval is forbidden"
            )
