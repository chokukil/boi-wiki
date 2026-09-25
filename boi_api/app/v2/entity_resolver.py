from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import Principal
from .repository import KnowledgeRecord


ENTITY_PREFIXES = (
    "company:",
    "org-unit:",
    "project-group:",
    "person:",
    "team:",
    "role:",
    "task:",
    "runtime-task:",
    "boi:",
    "action:",
    "event:",
    "workflow:",
    "skill:",
    "outcome:",
    "usage:",
    "agent:",
    "agent-deployment:",
    "system:",
)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


@dataclass(frozen=True)
class EntityCandidate:
    entity_id: str
    label: str
    entity_kind: str


class AmbiguousEntityError(ValueError):
    def __init__(self, mention: str, candidates: list[EntityCandidate]):
        self.mention = mention
        self.candidates = candidates
        super().__init__(f"ambiguous entity: {mention}")


class EntityResolver:
    """Resolve user language to ACL-visible graph IDs without generating graph queries."""

    def __init__(self, directory_provider: Callable[[], list[Principal]] | None = None):
        self.directory_provider = directory_provider

    def directory(self, principal: Principal) -> list[Principal]:
        rows: list[Principal] = []
        if self.directory_provider is not None:
            try:
                rows = list(self.directory_provider() or [])
            except Exception:
                rows = []
        rows.append(principal)
        return list({item.employee_id: item for item in rows if item.employee_id}.values())

    @staticmethod
    def _person_visible(principal: Principal, person: Principal) -> bool:
        return bool(
            principal.is_admin
            or person.employee_id == principal.employee_id
            or set(principal.teams).intersection(person.teams)
        )

    def _directory_candidates(self, mention: str, principal: Principal) -> list[EntityCandidate]:
        normalised = _normalise(mention)
        candidates: list[EntityCandidate] = []
        for person in self.directory(principal):
            if not self._person_visible(principal, person):
                continue
            if normalised in {_normalise(person.employee_id), _normalise(person.display_name)}:
                candidates.append(
                    EntityCandidate(
                        entity_id=f"person:{person.employee_id}",
                        label=f"{person.display_name or person.employee_id} ({person.employee_id})",
                        entity_kind="person",
                    )
                )
        team_ids = sorted({team for person in self.directory(principal) for team in person.teams if team})
        for team_id in team_ids:
            if not principal.is_admin and team_id not in principal.teams:
                continue
            if normalised == _normalise(team_id):
                candidates.append(EntityCandidate(f"team:{team_id}", team_id, "team"))
        return candidates

    @staticmethod
    def _record_candidates(mention: str, records: Iterable[KnowledgeRecord]) -> list[EntityCandidate]:
        normalised = _normalise(mention)
        candidates: list[EntityCandidate] = []
        for record in records:
            identifiers = {
                _normalise(record.record_id),
                _normalise(record.title),
                *(
                    _normalise(str(record.metadata.get(key) or ""))
                    for key in (
                        "boi_id",
                        "event_type",
                        "action_key",
                        "workflow_definition_key",
                        "skill_key",
                        "term",
                    )
                ),
            }
            if normalised and normalised in identifiers:
                candidates.append(EntityCandidate(record.record_id, record.title, record.kind))
        return candidates

    def resolve_one(
        self,
        mention: str,
        *,
        principal: Principal,
        records: Iterable[KnowledgeRecord],
    ) -> str:
        clean = str(mention or "").strip()
        if not clean:
            return ""
        if clean.startswith(ENTITY_PREFIXES):
            if clean.startswith("person:"):
                employee_id = clean.split(":", 1)[1]
                visible = any(
                    item.employee_id == employee_id and self._person_visible(principal, item)
                    for item in self.directory(principal)
                )
                return clean if visible else ""
            if clean.startswith("team:"):
                team_id = clean.split(":", 1)[1]
                return clean if principal.is_admin or team_id in principal.teams else ""
            return clean
        candidates = [
            *self._directory_candidates(clean, principal),
            *self._record_candidates(clean, records),
        ]
        unique = list({item.entity_id: item for item in candidates}.values())
        if len(unique) > 1:
            raise AmbiguousEntityError(clean, unique)
        return unique[0].entity_id if unique else ""

    def resolve_many(
        self,
        mentions: Iterable[str],
        *,
        principal: Principal,
        records: Iterable[KnowledgeRecord],
    ) -> list[str]:
        resolved = [
            self.resolve_one(mention, principal=principal, records=records)
            for mention in mentions
        ]
        return list(dict.fromkeys(item for item in resolved if item))
