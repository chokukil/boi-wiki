"""Reuse-first ontology migration planning with hash-bound dry runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping


class BatchPolicyError(ValueError):
    pass


class StaleBatchError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return "".join(character.casefold() for character in str(value) if character.isalnum())


@dataclass(frozen=True)
class ConceptDefinition:
    concept_id: str
    kind: str
    canonical_name: str
    aliases: tuple[str, ...] = ()
    properties: tuple[str, ...] = ()
    evidence_digests: tuple[str, ...] = ()
    revision_digest: str = ""

    @property
    def normalized_names(self) -> frozenset[str]:
        return frozenset(_normalize(name) for name in (self.canonical_name, *self.aliases))


@dataclass(frozen=True)
class ConceptCandidate:
    candidate_id: str
    kind: str
    proposed_name: str
    aliases: tuple[str, ...] = ()
    properties: tuple[str, ...] = ()
    evidence_digests: tuple[str, ...] = ()
    requested_action: str | None = None
    force_new_reason: str | None = None

    def to_canonical(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "proposed_name": self.proposed_name,
            "aliases": list(self.aliases),
            "properties": list(self.properties),
            "evidence_digests": list(self.evidence_digests),
            "requested_action": self.requested_action,
            "force_new_reason": self.force_new_reason,
        }


@dataclass(frozen=True)
class ReuseDecision:
    candidate_id: str
    action: str
    existing_concept_id: str | None
    match_ids: tuple[str, ...]
    added_properties: tuple[str, ...]
    added_evidence: tuple[str, ...]
    reason_code: str
    attention_required: bool

    def to_canonical(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "existing_concept_id": self.existing_concept_id,
            "match_ids": list(self.match_ids),
            "added_properties": list(self.added_properties),
            "added_evidence": list(self.added_evidence),
            "reason_code": self.reason_code,
            "attention_required": self.attention_required,
        }


@dataclass(frozen=True)
class MigrationBatchPlan:
    candidate_ids: tuple[str, ...]
    dependency_closure: dict[str, tuple[str, ...]]
    before_hashes: dict[str, str]
    decisions: tuple[ReuseDecision, ...]
    preview_hash: str


@dataclass(frozen=True)
class BatchConfirmation:
    preview_hash: str
    confirmed: bool
    authority: str = "candidate-plan-only"


class MigrationBatchPlanner:
    def __init__(self, existing: tuple[ConceptDefinition, ...]) -> None:
        self.existing = existing

    def _exact_matches(self, candidate: ConceptCandidate) -> tuple[ConceptDefinition, ...]:
        candidate_names = frozenset(
            _normalize(name) for name in (candidate.proposed_name, *candidate.aliases)
        )
        return tuple(
            sorted(
                (
                    concept
                    for concept in self.existing
                    if concept.kind == candidate.kind
                    and candidate_names.intersection(concept.normalized_names)
                ),
                key=lambda concept: concept.concept_id,
            )
        )

    def decide(self, candidate: ConceptCandidate) -> ReuseDecision:
        if candidate.requested_action not in {None, "force_new"}:
            raise BatchPolicyError(f"UNSUPPORTED_REQUESTED_ACTION:{candidate.requested_action}")
        matches = self._exact_matches(candidate)
        match_ids = tuple(concept.concept_id for concept in matches)

        if candidate.requested_action == "force_new":
            if not candidate.force_new_reason or not candidate.force_new_reason.strip():
                raise BatchPolicyError("FORCE_NEW_REASON_REQUIRED")
            return ReuseDecision(
                candidate_id=candidate.candidate_id,
                action="new",
                existing_concept_id=None,
                match_ids=match_ids,
                added_properties=(),
                added_evidence=(),
                reason_code="FORCED_NEW_DUPLICATE_RISK" if matches else "FORCED_NEW_REVIEW",
                attention_required=True,
            )

        if len(matches) > 1:
            return ReuseDecision(
                candidate_id=candidate.candidate_id,
                action="reuse",
                existing_concept_id=None,
                match_ids=match_ids,
                added_properties=(),
                added_evidence=(),
                reason_code="MULTIPLE_EXISTING_MATCHES",
                attention_required=True,
            )

        if len(matches) == 1:
            match = matches[0]
            existing_properties = {_normalize(name) for name in match.properties}
            added = tuple(
                name for name in candidate.properties if _normalize(name) not in existing_properties
            )
            existing_evidence = set(match.evidence_digests)
            added_evidence = tuple(
                digest for digest in candidate.evidence_digests if digest not in existing_evidence
            )
            if added:
                action = "extend"
                reason_code = "EXISTING_CONCEPT_EXTENSION"
            elif added_evidence:
                action = "add_evidence"
                reason_code = "EXISTING_CONCEPT_EVIDENCE_ADDITION"
            else:
                action = "reuse"
                reason_code = "EXACT_EXISTING_CONCEPT"
            return ReuseDecision(
                candidate_id=candidate.candidate_id,
                action=action,
                existing_concept_id=match.concept_id,
                match_ids=match_ids,
                added_properties=added,
                added_evidence=added_evidence,
                reason_code=reason_code,
                attention_required=False,
            )

        return ReuseDecision(
            candidate_id=candidate.candidate_id,
            action="new",
            existing_concept_id=None,
            match_ids=(),
            added_properties=(),
            added_evidence=tuple(candidate.evidence_digests),
            reason_code="NO_EXISTING_MATCH",
            attention_required=False,
        )

    @staticmethod
    def _dependency_closure(
        selected_ids: tuple[str, ...],
        candidates: Mapping[str, ConceptCandidate],
        dependencies: Mapping[str, tuple[str, ...]],
    ) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
        ordered: list[str] = []
        complete: set[str] = set()
        visiting: set[str] = set()

        def visit(candidate_id: str) -> None:
            if candidate_id in complete:
                return
            if candidate_id in visiting:
                raise BatchPolicyError(f"DEPENDENCY_CYCLE:{candidate_id}")
            if candidate_id not in candidates:
                raise BatchPolicyError(f"MISSING_DEPENDENCY:{candidate_id}")
            visiting.add(candidate_id)
            for dependency_id in sorted(dependencies.get(candidate_id, ())):
                visit(dependency_id)
            visiting.remove(candidate_id)
            complete.add(candidate_id)
            ordered.append(candidate_id)

        for selected_id in sorted(selected_ids):
            visit(selected_id)
        closure = {
            candidate_id: tuple(sorted(dependencies.get(candidate_id, ())))
            for candidate_id in ordered
        }
        return tuple(ordered), closure

    def plan_batch(
        self,
        *,
        selected_ids: tuple[str, ...],
        candidates: Mapping[str, ConceptCandidate],
        dependencies: Mapping[str, tuple[str, ...]],
        before_hashes: Mapping[str, str],
    ) -> MigrationBatchPlan:
        candidate_ids, closure = self._dependency_closure(
            selected_ids,
            candidates,
            dependencies,
        )
        if len(candidate_ids) > 100:
            raise BatchPolicyError(f"BATCH_SIZE_EXCEEDED:{len(candidate_ids)}")
        decisions = tuple(self.decide(candidates[candidate_id]) for candidate_id in candidate_ids)
        payload = {
            "candidate_ids": list(candidate_ids),
            "candidates": [candidates[candidate_id].to_canonical() for candidate_id in candidate_ids],
            "dependency_closure": {key: list(value) for key, value in sorted(closure.items())},
            "before_hashes": dict(sorted(before_hashes.items())),
            "decisions": [decision.to_canonical() for decision in decisions],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        preview_hash = f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
        return MigrationBatchPlan(
            candidate_ids=candidate_ids,
            dependency_closure=closure,
            before_hashes=dict(sorted(before_hashes.items())),
            decisions=decisions,
            preview_hash=preview_hash,
        )

    @staticmethod
    def confirm(
        plan: MigrationBatchPlan,
        *,
        approved_preview_hash: str,
        current_hashes: Mapping[str, str],
    ) -> BatchConfirmation:
        if approved_preview_hash != plan.preview_hash:
            raise StaleBatchError("PREVIEW_HASH_MISMATCH")
        for concept_id, before_hash in plan.before_hashes.items():
            actual = current_hashes.get(concept_id)
            if actual != before_hash:
                raise StaleBatchError(
                    f"BEFORE_HASH_MISMATCH:{concept_id}:expected={before_hash}:actual={actual}"
                )
        return BatchConfirmation(preview_hash=plan.preview_hash, confirmed=True)
