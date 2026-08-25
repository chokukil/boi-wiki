"""Application orchestration around interpretation and deterministic verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal

from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.anchors import resolve_anchor
from boi_api.app.science.authorization import ScienceAuthorizationError
from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.engine import verify_claim as verify_scientific_claim
from boi_api.app.science.equation_assets import equation_asset_index
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.llm import (
    PROMPT_VERSION,
    LLMClaimCandidate,
    ScienceInterpretationUnavailable,
    ScienceLLMClient,
)
from boi_api.app.science.models import (
    AliasDetectionResult,
    CandidateMeaningRecord,
    ClaimSubmissionClientKind,
    ClaimInterpretation,
    ClaimPacket,
    DetectedAlias,
    EvidenceLink,
    FormulaInterpretationRecord,
    FormulaSymbolInterpretationRecord,
    GroundedAnnotation,
    GroundedEquationRef,
    GroundedExplanation,
    GroundedExplanationBlock,
    GroundedObjectRef,
    InterpretationDecisionImpact,
    InterpretationRecord,
    InterpretationRevisionEvent,
    LLMModelSettings,
    ReleaseSelection,
    ReportEquationAsset,
    ResolvedReleaseSet,
    ScienceOperationBinding,
    SourceLookupIdentity,
    SourceSpan,
    VerdictPacket,
    VerificationReport,
    verification_report_scientific_payload,
)
from boi_api.app.science.operational import OperationalVerification
from boi_api.app.science.safety import validate_with_closed_error
from boi_api.app.science.source_identity import (
    ReviewedSourceURLIdentity,
    _open_reviewed_source_url_identity,
)
from boi_api.app.science.storage import ImmutableScienceRecordError
from boi_api.app.science.rules import VerificationRule


class ScienceConfirmationRequired(ScienceOperationalError):
    """A server-validated interpretation still needs an explicit user action."""


class ScienceIdempotencyConflict(ScienceOperationalError):
    """A trusted idempotency key was already bound to another operation."""


CLAIM_SUBMISSION_VERSION = "science-claim-submission/0.1.0"
USER_ACTION_CHALLENGE_TTL = timedelta(minutes=5)


def submitted_root_document_ref(
    *,
    actor_id: str,
    initial_document_digest: str,
) -> str:
    """Derive the only owner-bound identity for an initial submitted document."""

    submitted_id = sha256_digest(
        {
            "actor_id": actor_id,
            "initial_document_digest": initial_document_digest,
        }
    ).removeprefix("sha256:")
    return f"boi:submitted:{submitted_id}"


def submitted_revision_document_ref(
    *,
    actor_id: str,
    source_document_ref: str,
    source_document_digest: str,
) -> str:
    """Derive one actor-bound destination for a trusted document lineage."""

    if source_document_ref.startswith("boi:submitted:"):
        return source_document_ref
    submitted_id = sha256_digest(
        {
            "actor_id": actor_id,
            "source_document_ref": source_document_ref,
            "source_document_digest": source_document_digest,
        }
    ).removeprefix("sha256:")
    return f"boi:submitted:{submitted_id}"


def _has_deterministic_alias_boundary(
    text: str,
    *,
    alias: str,
    start: int,
) -> bool:
    """Keep ASCII identifier aliases out of larger ASCII identifiers."""

    ascii_token = alias.isascii() and all(
        character.isalnum() or character == "_" for character in alias
    )
    if not ascii_token:
        return True
    end = start + len(alias)

    def is_ascii_identifier(value: str) -> bool:
        return value.isascii() and (value.isalnum() or value == "_")

    return (start == 0 or not is_ascii_identifier(text[start - 1])) and (
        end == len(text) or not is_ascii_identifier(text[end])
    )


class ScienceService:
    """Keep untrusted language interpretation outside the verdict boundary."""

    def __init__(
        self,
        *,
        catalog: Any,
        runtime_store: Any,
        llm_client: ScienceLLMClient | None,
        dictionary_release_id: str,
        ontology_release_id: str,
        ontology_binding_ids: Sequence[str],
        document_access_check: Callable[[AuthIdentity, str], bool],
        llm_client_factory: Callable[[], ScienceLLMClient | None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.catalog = catalog
        self.runtime_store = runtime_store
        self.llm_client = llm_client
        self._llm_client_factory = llm_client_factory
        self.dictionary_release_id = dictionary_release_id
        self.ontology_release_id = ontology_release_id
        self.ontology_binding_ids = tuple(ontology_binding_ids)
        self._document_access_check = document_access_check
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _trusted_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ScienceOperationalError(
                "Science trusted user action clock must be timezone-aware"
            )
        return now

    def _issue_trusted_user_action_challenge(
        self,
        *,
        operation: Literal["submit_user_revision", "confirm_interpretation"],
        identity: AuthIdentity,
        payload: Mapping[str, Any],
    ) -> dict[str, str]:
        now = self._trusted_now()
        request_digest = sha256_digest(
            {
                "operation": operation,
                "actor_id": identity.employee_id,
                "payload": payload,
            }
        )
        issue = getattr(self.runtime_store, "issue_user_action_challenge", None)
        if not callable(issue):
            raise ScienceConfirmationRequired(
                "durable trusted user action storage is unavailable"
            )
        challenge = issue(
            operation=operation,
            actor_id=identity.employee_id,
            request_digest=request_digest,
            issued_at=now,
            expires_at=now + USER_ACTION_CHALLENGE_TTL,
        )
        return {
            "challenge_id": challenge.challenge_id,
            "operation": operation,
            "request_digest": request_digest,
            "expires_at": challenge.expires_at.isoformat().replace("+00:00", "Z"),
        }

    def _consume_trusted_user_action_challenge(
        self,
        challenge_id: str,
        *,
        operation: Literal["submit_user_revision", "confirm_interpretation"],
        identity: AuthIdentity,
        request_digest: str,
    ) -> None:
        if not isinstance(challenge_id, str) or not challenge_id.startswith(
            "sci-user-action:"
        ):
            raise ScienceConfirmationRequired(
                "a server-issued trusted user action challenge is required"
            )
        consume = getattr(self.runtime_store, "consume_user_action_challenge", None)
        if not callable(consume):
            raise ScienceConfirmationRequired(
                "durable trusted user action storage is unavailable"
            )
        try:
            consume(
                challenge_id,
                operation=operation,
                actor_id=identity.employee_id,
                request_digest=request_digest,
                consumed_at=self._trusted_now(),
            )
        except (KeyError, ValueError) as exc:
            raise ScienceConfirmationRequired(
                "trusted user action challenge is missing, expired, used, or mismatched"
            ) from exc

    def _require_interpretation_access(
        self,
        interpretation: InterpretationRecord,
        *,
        identity: AuthIdentity,
    ) -> None:
        canonical_source = self._canonical_source_lineage(
            interpretation,
            identity=identity,
        )
        if canonical_source is not None and not self._document_access_check(
            identity, canonical_source[0]
        ):
            raise ScienceAuthorizationError(
                "Science interpretation document access is not authorized"
            )

    def _proposal_records_for_claim(
        self, claim_id: str
    ) -> tuple[InterpretationRecord, ...]:
        resolver = getattr(self.runtime_store, "interpretations_for_claim", None)
        if callable(resolver):
            return tuple(resolver(claim_id))
        return tuple(
            record
            for record in getattr(self.runtime_store, "interpretations", {}).values()
            if record.operation_binding.operation
            in {"interpret_document", "submit_claim_candidate"}
            and any(claim.claim_id == claim_id for claim in record.candidate_claims)
        )

    def _canonical_source_lineage(
        self,
        interpretation: InterpretationRecord,
        *,
        identity: AuthIdentity,
        visited: frozenset[str] = frozenset(),
    ) -> tuple[str, str] | None:
        """Resolve a submitted revision back to its immutable Wiki ACL source."""

        if interpretation.operation_binding.actor_id != identity.employee_id:
            raise ScienceAuthorizationError(
                "Science interpretation owner does not match trusted identity"
            )
        if interpretation.interpretation_id in visited:
            raise ScienceAuthorizationError(
                "Science interpretation source lineage is not authorized"
            )
        document_refs = {
            claim.document_ref for claim in interpretation.candidate_claims
        }
        if len(document_refs) != 1:
            raise ScienceAuthorizationError(
                "Science interpretation document binding is not authorized"
            )
        document_ref = next(iter(document_refs))
        persisted_ref = interpretation.canonical_source_document_ref
        persisted_digest = interpretation.canonical_source_document_digest
        persisted = (
            (persisted_ref, persisted_digest)
            if persisted_ref is not None and persisted_digest is not None
            else None
        )
        if not document_ref.startswith("boi:submitted:"):
            if persisted is not None:
                raise ScienceAuthorizationError(
                    "Science interpretation source lineage is not authorized"
                )
            return document_ref, interpretation.document_digest

        predecessor_claim_id = interpretation.supersedes_claim_id
        if predecessor_claim_id is None:
            if persisted is not None:
                raise ScienceAuthorizationError(
                    "Science interpretation source lineage is not authorized"
                )
            if (
                interpretation.submission_client_kind is not None
                and document_ref
                != submitted_root_document_ref(
                    actor_id=identity.employee_id,
                    initial_document_digest=interpretation.document_digest,
                )
            ):
                raise ScienceAuthorizationError(
                    "Science interpretation source lineage is not authorized"
                )
            return None

        predecessors = self._proposal_records_for_claim(predecessor_claim_id)
        owned = [
            record
            for record in predecessors
            if record.operation_binding.actor_id == identity.employee_id
        ]
        if not owned:
            raise ScienceAuthorizationError(
                "Science interpretation source lineage is not authorized"
            )
        matching = [
            record
            for record in owned
            if len(record.candidate_claims) == 1
            and document_ref
            == submitted_revision_document_ref(
                actor_id=identity.employee_id,
                source_document_ref=record.candidate_claims[0].document_ref,
                source_document_digest=record.document_digest,
            )
        ]
        if not matching:
            raise ScienceAuthorizationError(
                "Science interpretation source lineage is not authorized"
            )
        next_visited = visited | {interpretation.interpretation_id}
        resolved = {
            self._canonical_source_lineage(
                record,
                identity=identity,
                visited=next_visited,
            )
            for record in matching
        }
        if len(resolved) != 1:
            raise ScienceAuthorizationError(
                "Science interpretation source lineage is not authorized"
            )
        canonical_source = next(iter(resolved))
        if persisted is not None and persisted != canonical_source:
            raise ScienceAuthorizationError(
                "Science interpretation source lineage is not authorized"
            )
        return canonical_source

    @staticmethod
    def _idempotency_digest(value: str) -> str:
        if (
            not isinstance(value, str)
            or not 8 <= len(value) <= 256
            or any(character.isspace() for character in value)
        ):
            raise ScienceIdempotencyConflict("trusted idempotency key is malformed")
        return sha256_digest(value)

    @classmethod
    def _record_id(cls, prefix: Literal["interpretation", "report"], key: str) -> str:
        return f"sci-{prefix}:" + cls._idempotency_digest(key).removeprefix("sha256:")

    def _interpretation_client(self) -> ScienceLLMClient:
        client = self.llm_client
        if client is None and self._llm_client_factory is not None:
            client = self._llm_client_factory()
        if client is None:
            raise ScienceInterpretationUnavailable(
                "Experimental Science LLM adapter is disabled",
                diagnostic_code="adapter_disabled",
            )
        return client

    def _prompt_digest(self, client: ScienceLLMClient) -> str:
        return sha256_digest(
            {
                "prompt_version": PROMPT_VERSION,
                "system_prompt_digest": sha256_digest(
                    ScienceLLMClient._system_prompt()
                ),
                "model_id": client.config.model_id,
                "transport_mode": client.config.transport_mode,
                "response_format_mode": client.config.response_format_mode,
                "reasoning_mode": client.config.reasoning_mode,
                "max_attempts": client.config.max_attempts,
                "model_settings": client.config.safe_model_settings(),
                "dictionary_release_id": self.dictionary_release_id,
                "ontology_release_id": self.ontology_release_id,
                "ontology_binding_ids": self.ontology_binding_ids,
            }
        )

    @staticmethod
    def _assert_operation_retry(
        actual: ScienceOperationBinding,
        expected: ScienceOperationBinding,
        *,
        derived_claim_digest: bool = False,
    ) -> None:
        fields = {
            "operation",
            "idempotency_key_digest",
            "actor_id",
            "request_digest",
            "document_digest",
            "release_digest",
            "prompt_digest",
            "source_interpretation_id",
        }
        if not derived_claim_digest:
            fields.update({"claim_digest", "claim_ids"})
        if any(getattr(actual, field) != getattr(expected, field) for field in fields):
            raise ScienceIdempotencyConflict(
                "idempotency key is already bound to different canonical inputs"
            )

    def _existing_interpretation(
        self,
        interpretation_id: str,
        expected: ScienceOperationBinding,
        *,
        derived_claim_digest: bool = False,
    ) -> InterpretationRecord | None:
        recover = getattr(self.runtime_store, "recover_pending_transactions", None)
        if callable(recover):
            recover()
        try:
            record = self.runtime_store.load_interpretation(interpretation_id)
        except KeyError:
            return None
        self._assert_operation_retry(
            record.operation_binding,
            expected,
            derived_claim_digest=derived_claim_digest,
        )
        return record

    def _existing_report(
        self,
        report_id: str,
        expected: ScienceOperationBinding,
    ) -> VerificationReport | None:
        recover = getattr(self.runtime_store, "recover_pending_transactions", None)
        if callable(recover):
            recover()
        try:
            report = self.runtime_store.load_report(report_id)
        except KeyError:
            return None
        self._assert_operation_retry(report.operation_binding, expected)
        return report

    def _ontology_index(self) -> dict[str, dict[str, object]]:
        index: dict[str, dict[str, object]] = {}
        concepts: set[str] = set()
        for binding_id in self.ontology_binding_ids:
            try:
                binding = self.catalog.ontology_binding(binding_id)
            except (KeyError, ScienceCatalogError) as exc:
                raise ScienceInterpretationUnavailable(
                    f"pinned ontology binding is unavailable: {binding_id}"
                ) from exc
            if getattr(binding, "object_id", None) != binding_id:
                raise ScienceInterpretationUnavailable(
                    "ontology binding identity does not match the pinned index"
                )
            if (
                getattr(binding, "ontology_release_id", None)
                != self.ontology_release_id
            ):
                raise ScienceInterpretationUnavailable(
                    "ontology binding is not from the selected ontology release"
                )
            concept_id = getattr(binding, "concept_id", None)
            binding_digest = getattr(binding, "digest", None)
            meaning = getattr(binding, "meaning", None)
            aliases = getattr(binding, "aliases", None)
            domain = getattr(binding, "domain", None)
            if (
                not isinstance(concept_id, str)
                or not concept_id
                or not isinstance(binding_digest, str)
                or not binding_digest.startswith("sha256:")
                or len(binding_digest) != 71
                or any(
                    character not in "0123456789abcdef"
                    for character in binding_digest.removeprefix("sha256:")
                )
                or not isinstance(meaning, str)
                or not meaning
                or not isinstance(aliases, list)
                or not all(isinstance(alias, str) and alias for alias in aliases)
                or not isinstance(domain, str)
                or not domain
            ):
                raise ScienceInterpretationUnavailable(
                    f"ontology binding is incomplete: {binding_id}"
                )
            if concept_id in concepts:
                raise ScienceInterpretationUnavailable(
                    f"ontology concept has multiple pinned meanings: {concept_id}"
                )
            concepts.add(concept_id)
            index[binding_id] = {
                "ontology_ref": binding_id,
                "concept_id": concept_id,
                "binding_digest": binding_digest,
                "aliases": list(aliases),
                "meaning": meaning,
                "domain": domain,
            }
        return index

    @staticmethod
    def _absolute_span(
        document_text: str,
        interpreted_span: SourceSpan,
        *,
        selection_start: int,
    ) -> SourceSpan:
        start = selection_start + interpreted_span.start
        end = start + len(interpreted_span.exact)
        prefix_size = len(interpreted_span.prefix)
        suffix_size = len(interpreted_span.suffix)
        return SourceSpan(
            start=start,
            end=end,
            exact=interpreted_span.exact,
            prefix=document_text[max(0, start - prefix_size) : start],
            suffix=document_text[end : end + suffix_size],
        )

    def _claim_from_candidate(
        self,
        candidate: LLMClaimCandidate,
        *,
        document_text: str,
        interpreted_text: str,
        document_ref: str,
        document_digest: str,
        selection_start: int,
        ontology_index: Mapping[str, Mapping[str, object]],
        client_kind: ClaimSubmissionClientKind,
    ) -> tuple[
        ClaimPacket,
        list[CandidateMeaningRecord],
        InterpretationDecisionImpact,
        list[FormulaInterpretationRecord],
    ]:
        resolved_local = resolve_anchor(
            interpreted_text,
            candidate.source_span,
            document_digest=sha256_digest(interpreted_text),
        )
        absolute = self._absolute_span(
            document_text,
            resolved_local,
            selection_start=selection_start,
        )
        resolved = resolve_anchor(
            document_text,
            absolute,
            document_digest=document_digest,
        )

        supplied_refs = set(candidate.ontology_refs)
        meaning_refs = {
            meaning.ontology_ref for meaning in candidate.candidate_meanings
        }
        proposed_refs = supplied_refs | meaning_refs
        issues: set[str] = {"USER_CONFIRMATION_REQUIRED"}
        if not supplied_refs:
            issues.add("ONTOLOGY_REFS_REQUIRED")
        unknown_refs = proposed_refs - set(ontology_index)
        if unknown_refs:
            issues.add("UNKNOWN_ONTOLOGY_REF")
        if supplied_refs != meaning_refs:
            issues.add("ONTOLOGY_REF_MISMATCH")

        normalized = candidate.normalized_claim
        if client_kind != "user" and (
            normalized.quantities
            or normalized.conditions
            or normalized.process_stage is not None
            or normalized.material_state is not None
        ):
            issues.add("EXTERNAL_CONTEXT_REQUIRES_USER_REVISION")
        by_role: dict[str, list[Any]] = {"subject": [], "relation": [], "object": []}
        for meaning in candidate.candidate_meanings:
            by_role[meaning.concept_role].append(meaning)
        role_issue = {
            "subject": "SUBJECT_BINDING_REQUIRED",
            "relation": "RELATION_BINDING_REQUIRED",
            "object": "OBJECT_BINDING_REQUIRED",
        }
        for role, meanings_for_role in by_role.items():
            if len(meanings_for_role) != 1:
                issues.add(role_issue[role])

        claim_id = "sci-claim:" + sha256_digest(
            {
                "document_digest": document_digest,
                "source_span": resolved,
                "normalized_claim": normalized,
            }
        ).removeprefix("sha256:")
        claim = ClaimPacket(
            claim_id=claim_id,
            document_ref=document_ref,
            document_digest=document_digest,
            source_span=resolved,
            normalized_claim=normalized,
            interpretation=ClaimInterpretation(
                ontology_refs=[],
                proposed_ontology_refs=sorted(proposed_refs),
                ambiguity_ids=sorted(candidate.ambiguity_ids),
                user_confirmed=False,
            ),
        )

        expected_concepts = {
            "subject": normalized.subject_concept_id,
            "relation": normalized.predicate,
            "object": normalized.object_concept_id,
        }
        meanings: list[CandidateMeaningRecord] = []
        surface_spans: dict[str, tuple[int, int]] = {}
        validated_refs: set[str] = set()
        for meaning in candidate.candidate_meanings:
            canonical = ontology_index.get(meaning.ontology_ref)
            binding_matches = False
            alias_matches = False
            if canonical is not None:
                concept_id = str(canonical["concept_id"])
                binding_matches = concept_id == expected_concepts[meaning.concept_role]
                if not binding_matches:
                    issues.add("BINDING_CONCEPT_MISMATCH")
                aliases = canonical["aliases"]
                alias_matches = meaning.surface_term in aliases
                if not alias_matches:
                    issues.add("ALIAS_BINDING_MISMATCH")
                canonical_meaning = str(canonical["meaning"])
                domain = str(canonical["domain"])
            else:
                concept_id = None
                canonical_meaning = None
                domain = None
            occurrence_count = sum(
                1
                for offset in range(
                    0, len(resolved.exact) - len(meaning.surface_term) + 1
                )
                if resolved.exact.startswith(meaning.surface_term, offset)
            )
            position = resolved.exact.find(meaning.surface_term)
            if occurrence_count != 1:
                issues.add("COMPLETE_RELATION_SPAN_REQUIRED")
            if position >= 0 and meaning.concept_role not in surface_spans:
                surface_spans[meaning.concept_role] = (
                    position,
                    position + len(meaning.surface_term),
                )
            if (
                canonical is not None
                and binding_matches
                and alias_matches
                and occurrence_count == 1
                and meaning.ontology_ref in supplied_refs
                and len(by_role[meaning.concept_role]) == 1
            ):
                validated_refs.add(meaning.ontology_ref)
            meanings.append(
                CandidateMeaningRecord(
                    claim_id=claim_id,
                    ambiguity_id=meaning.ambiguity_id,
                    concept_role=meaning.concept_role,
                    surface_term=meaning.surface_term,
                    ontology_ref=meaning.ontology_ref,
                    binding_digest=(
                        str(canonical["binding_digest"])
                        if canonical is not None
                        else None
                    ),
                    concept_id=concept_id,
                    meaning=canonical_meaning,
                    domain=domain,
                )
            )
        ordered_surface_spans = sorted(surface_spans.values())
        has_overlapping_roles = any(
            left[1] > right[0]
            for left, right in zip(
                ordered_surface_spans,
                ordered_surface_spans[1:],
                strict=False,
            )
        )
        if set(surface_spans) != {"subject", "relation", "object"} or (
            has_overlapping_roles
        ):
            issues.add("COMPLETE_RELATION_SPAN_REQUIRED")
        claim = claim.model_copy(
            update={
                "interpretation": claim.interpretation.model_copy(
                    update={"ontology_refs": sorted(validated_refs)}
                )
            },
            deep=True,
        )

        formula_records, formula_issues = self._formula_records_from_candidate(
            candidate,
            claim_id=claim_id,
            claim_span=resolved,
            document_text=document_text,
            interpreted_text=interpreted_text,
            document_digest=document_digest,
            selection_start=selection_start,
            ontology_index=ontology_index,
            client_kind=client_kind,
        )
        issues.update(formula_issues)

        ordered_issues = [
            issue
            for issue in (
                "USER_CONFIRMATION_REQUIRED",
                "ONTOLOGY_REFS_REQUIRED",
                "UNKNOWN_ONTOLOGY_REF",
                "ONTOLOGY_REF_MISMATCH",
                "SUBJECT_BINDING_REQUIRED",
                "RELATION_BINDING_REQUIRED",
                "OBJECT_BINDING_REQUIRED",
                "BINDING_CONCEPT_MISMATCH",
                "ALIAS_BINDING_MISMATCH",
                "COMPLETE_RELATION_SPAN_REQUIRED",
                "EXTERNAL_CONTEXT_REQUIRES_USER_REVISION",
                "FORMULA_OUTSIDE_CLAIM_SPAN",
                "FORMULA_SPAN_OVERLAP",
                "FORMULA_SYMBOL_INCOMPLETE",
                "FORMULA_SYMBOL_OVERLAP",
                "FORMULA_UNDECLARED_VARIABLE",
                "FORMULA_ONTOLOGY_MISMATCH",
                "FORMULA_SYMBOL_AMBIGUITY",
                "FORMULA_CONTEXT_REQUIRES_USER_REVISION",
                "UNKNOWN_EQUATION_REF",
                "EQUATION_IDENTITY_MISMATCH",
                "FORMULA_SEMANTIC_MISMATCH",
            )
            if issue in issues
        ]
        impact = InterpretationDecisionImpact(
            claim_id=claim_id,
            status=(
                "requires_user_confirmation"
                if ordered_issues == ["USER_CONFIRMATION_REQUIRED"]
                else "blocked_semantic_mismatch"
            ),
            issue_codes=ordered_issues,
        )
        return claim, meanings, impact, formula_records

    def _formula_records_from_candidate(
        self,
        candidate: LLMClaimCandidate,
        *,
        claim_id: str,
        claim_span: SourceSpan,
        document_text: str,
        interpreted_text: str,
        document_digest: str,
        selection_start: int,
        ontology_index: Mapping[str, Mapping[str, object]],
        client_kind: ClaimSubmissionClientKind,
    ) -> tuple[list[FormulaInterpretationRecord], set[str]]:
        """Re-anchor formula proposals and compare them to reviewed Catalog identity.

        The returned records intentionally retain ``verdict_authority=False`` and
        are not copied into ``ClaimPacket``.  They exist only for later UI review.
        """

        records: list[FormulaInterpretationRecord] = []
        all_issues: set[str] = set()
        equation_issue_codes = {
            "FORMULA_SYMBOL_INCOMPLETE",
            "FORMULA_UNDECLARED_VARIABLE",
            "FORMULA_ONTOLOGY_MISMATCH",
            "UNKNOWN_EQUATION_REF",
            "EQUATION_IDENTITY_MISMATCH",
            "FORMULA_SEMANTIC_MISMATCH",
        }
        formula_issue_order = (
            "FORMULA_OUTSIDE_CLAIM_SPAN",
            "FORMULA_SPAN_OVERLAP",
            "FORMULA_SYMBOL_INCOMPLETE",
            "FORMULA_SYMBOL_OVERLAP",
            "FORMULA_UNDECLARED_VARIABLE",
            "FORMULA_ONTOLOGY_MISMATCH",
            "FORMULA_SYMBOL_AMBIGUITY",
            "FORMULA_CONTEXT_REQUIRES_USER_REVISION",
            "UNKNOWN_EQUATION_REF",
            "EQUATION_IDENTITY_MISMATCH",
            "FORMULA_SEMANTIC_MISMATCH",
        )

        for formula in candidate.formula_candidates:
            local_formula_span = resolve_anchor(
                interpreted_text,
                formula.formula_span,
                document_digest=sha256_digest(interpreted_text),
            )
            absolute_formula_span = self._absolute_span(
                document_text,
                local_formula_span,
                selection_start=selection_start,
            )
            formula_span = resolve_anchor(
                document_text,
                absolute_formula_span,
                document_digest=document_digest,
            )
            issues: set[str] = set()
            if not (
                claim_span.start <= formula_span.start
                and formula_span.end <= claim_span.end
            ):
                issues.add("FORMULA_OUTSIDE_CLAIM_SPAN")

            semantic_payload = formula.semantic_expression.model_dump(
                mode="json", exclude_none=True
            )
            semantic_digest = sha256_digest(semantic_payload)
            semantic_variables = formula.semantic_expression.variable_ids()
            candidate_variable_ids = {
                symbol.variable_id for symbol in formula.symbol_candidates
            }
            if semantic_variables - candidate_variable_ids:
                issues.add("FORMULA_SYMBOL_INCOMPLETE")
            if candidate_variable_ids - semantic_variables:
                issues.add("FORMULA_UNDECLARED_VARIABLE")

            symbol_records: list[FormulaSymbolInterpretationRecord] = []
            symbol_ranges: list[tuple[int, int]] = []
            formula_binding_refs = {
                symbol.ontology_ref for symbol in formula.symbol_candidates
            }
            if formula_binding_refs != set(formula.ontology_refs):
                issues.add("FORMULA_ONTOLOGY_MISMATCH")

            proposed_equation = None
            catalog_match_status: Literal[
                "not_proposed",
                "unknown_equation",
                "mismatch",
                "exact_candidate_match",
            ] = "not_proposed"
            catalog_variables: dict[str, Any] = {}
            if formula.proposed_equation_id is not None:
                try:
                    proposed_equation = self.catalog.equation(
                        formula.proposed_equation_id
                    ).equation
                except ScienceCatalogError:
                    issues.add("UNKNOWN_EQUATION_REF")
                    catalog_match_status = "unknown_equation"
                else:
                    catalog_match_status = "exact_candidate_match"
                    if (
                        proposed_equation.equation_digest
                        != formula.proposed_equation_digest
                    ):
                        issues.add("EQUATION_IDENTITY_MISMATCH")
                    expected_semantic_digest = sha256_digest(
                        proposed_equation.semantic_expression.model_dump(
                            mode="json", exclude_none=True
                        )
                    )
                    if expected_semantic_digest != semantic_digest:
                        issues.add("FORMULA_SEMANTIC_MISMATCH")
                    catalog_variables = {
                        item.variable_id: item for item in proposed_equation.variables
                    }
                    if set(catalog_variables) - candidate_variable_ids:
                        issues.add("FORMULA_SYMBOL_INCOMPLETE")
                    if candidate_variable_ids - set(catalog_variables):
                        issues.add("FORMULA_UNDECLARED_VARIABLE")

            for symbol in formula.symbol_candidates:
                local_symbol_span = resolve_anchor(
                    interpreted_text,
                    symbol.source_span,
                    document_digest=sha256_digest(interpreted_text),
                )
                absolute_symbol_span = self._absolute_span(
                    document_text,
                    local_symbol_span,
                    selection_start=selection_start,
                )
                symbol_span = resolve_anchor(
                    document_text,
                    absolute_symbol_span,
                    document_digest=document_digest,
                )
                if symbol_span.exact != symbol.symbol:
                    issues.add("FORMULA_ONTOLOGY_MISMATCH")
                in_formula = (
                    formula_span.start <= symbol_span.start
                    and symbol_span.end <= formula_span.end
                )
                in_claim = (
                    claim_span.start <= symbol_span.start
                    and symbol_span.end <= claim_span.end
                )
                if not in_formula and not in_claim:
                    issues.add("FORMULA_OUTSIDE_CLAIM_SPAN")
                elif not in_formula and client_kind != "user":
                    issues.add("FORMULA_CONTEXT_REQUIRES_USER_REVISION")
                symbol_ranges.append((symbol_span.start, symbol_span.end))

                canonical = ontology_index.get(symbol.ontology_ref)
                binding_digest: str | None = None
                if canonical is None:
                    issues.add("FORMULA_ONTOLOGY_MISMATCH")
                else:
                    binding_digest = str(canonical["binding_digest"])
                    if (
                        canonical["concept_id"] != symbol.concept_ref
                        or symbol.symbol not in canonical["aliases"]
                    ):
                        issues.add("FORMULA_ONTOLOGY_MISMATCH")

                alias_concepts = {
                    str(binding["concept_id"])
                    for binding in ontology_index.values()
                    if symbol.symbol in binding["aliases"]
                }
                if proposed_equation is None and len(alias_concepts) > 1:
                    issues.add("FORMULA_SYMBOL_AMBIGUITY")

                catalog_variable = catalog_variables.get(symbol.variable_id)
                catalog_variable_match: bool | None = None
                if proposed_equation is not None:
                    catalog_variable_match = catalog_variable is not None and (
                        catalog_variable.symbol == symbol.symbol
                        and catalog_variable.concept_ref == symbol.concept_ref
                        and catalog_variable.quantity_kind == symbol.quantity_kind
                        and (
                            symbol.unit is None or catalog_variable.unit == symbol.unit
                        )
                    )
                    if not catalog_variable_match:
                        issues.add("FORMULA_ONTOLOGY_MISMATCH")

                symbol_records.append(
                    FormulaSymbolInterpretationRecord(
                        variable_id=symbol.variable_id,
                        symbol=symbol.symbol,
                        source_span=symbol_span,
                        concept_ref=symbol.concept_ref,
                        quantity_kind=symbol.quantity_kind,
                        unit=symbol.unit,
                        ontology_ref=symbol.ontology_ref,
                        binding_digest=binding_digest,
                        catalog_variable_match=catalog_variable_match,
                    )
                )

            sorted_symbol_ranges = sorted(symbol_ranges)
            if any(
                left[1] > right[0]
                for left, right in zip(
                    sorted_symbol_ranges,
                    sorted_symbol_ranges[1:],
                    strict=False,
                )
            ):
                issues.add("FORMULA_SYMBOL_OVERLAP")
            if client_kind != "user" and (
                formula.condition_candidates
                or formula.sign_convention_candidate is not None
                or any(symbol.unit is not None for symbol in formula.symbol_candidates)
            ):
                issues.add("FORMULA_CONTEXT_REQUIRES_USER_REVISION")

            if proposed_equation is not None and issues & equation_issue_codes:
                catalog_match_status = "mismatch"
            ordered_formula_issues = [
                issue for issue in formula_issue_order if issue in issues
            ]
            all_issues.update(issues)
            record_payload: dict[str, Any] = {
                "claim_id": claim_id,
                "formula_span": formula_span,
                "semantic_expression": formula.semantic_expression,
                "semantic_expression_digest": semantic_digest,
                "proposed_equation_id": formula.proposed_equation_id,
                "proposed_equation_digest": formula.proposed_equation_digest,
                "catalog_match_status": catalog_match_status,
                "symbol_candidates": symbol_records,
                "condition_candidates": formula.condition_candidates,
                "sign_convention_candidate": formula.sign_convention_candidate,
                "ontology_refs": formula.ontology_refs,
                "issue_codes": ordered_formula_issues,
                "verdict_authority": False,
            }
            record_payload["candidate_digest"] = sha256_digest(record_payload)
            records.append(FormulaInterpretationRecord.model_validate(record_payload))

        overlapping_record_indexes: set[int] = set()
        ordered_formula_ranges = sorted(
            (
                record.formula_span.start,
                record.formula_span.end,
                index,
            )
            for index, record in enumerate(records)
        )
        for left, right in zip(
            ordered_formula_ranges,
            ordered_formula_ranges[1:],
            strict=False,
        ):
            if left[1] > right[0]:
                overlapping_record_indexes.update((left[2], right[2]))
        if overlapping_record_indexes:
            all_issues.add("FORMULA_SPAN_OVERLAP")
            for index in overlapping_record_indexes:
                record = records[index]
                issue_set = {*record.issue_codes, "FORMULA_SPAN_OVERLAP"}
                record_payload = record.model_dump(
                    mode="json", exclude={"candidate_digest"}
                )
                record_payload["issue_codes"] = [
                    issue for issue in formula_issue_order if issue in issue_set
                ]
                record_payload["candidate_digest"] = sha256_digest(record_payload)
                records[index] = FormulaInterpretationRecord.model_validate(
                    record_payload
                )
        return records, all_issues

    def detect_aliases(
        self,
        document_text: str,
        *,
        document_ref: str,
        selection_anchor: SourceSpan | None = None,
    ) -> AliasDetectionResult:
        """Find exact registered aliases without creating a Claim or verdict."""

        if not document_text:
            raise ScienceInterpretationUnavailable("document text must be nonempty")
        document_digest = sha256_digest(document_text)
        search_text = document_text
        selection_start = 0
        if selection_anchor is not None:
            selection = resolve_anchor(
                document_text,
                selection_anchor,
                document_digest=document_digest,
            )
            search_text = selection.exact
            selection_start = selection.start

        matches: list[DetectedAlias] = []
        for ontology_ref, binding in self._ontology_index().items():
            for alias in binding["aliases"]:
                if not isinstance(alias, str) or not alias:
                    continue
                offset = 0
                while (position := search_text.find(alias, offset)) >= 0:
                    offset = position + 1
                    if not _has_deterministic_alias_boundary(
                        search_text,
                        alias=alias,
                        start=position,
                    ):
                        continue
                    start = selection_start + position
                    matches.append(
                        DetectedAlias(
                            binding_id=ontology_ref,
                            ontology_ref=ontology_ref,
                            concept_id=str(binding["concept_id"]),
                            surface_term=alias,
                            start=start,
                            end=start + len(alias),
                            meaning=str(binding["meaning"]),
                            domain=str(binding["domain"]),
                            binding_digest=str(binding["binding_digest"]),
                        )
                    )
        matches.sort(
            key=lambda match: (
                match.start,
                -len(match.surface_term),
                match.ontology_ref,
                match.surface_term,
            )
        )
        return AliasDetectionResult(
            document_ref=document_ref,
            document_digest=document_digest,
            matches=matches,
        )

    def _claim_submission_prompt_digest(self) -> str:
        return sha256_digest(
            {
                "contract_version": CLAIM_SUBMISSION_VERSION,
                "dictionary_release_id": self.dictionary_release_id,
                "ontology_release_id": self.ontology_release_id,
                "ontology_binding_ids": self.ontology_binding_ids,
            }
        )

    def issue_user_revision_challenge(
        self,
        document_text: str,
        *,
        document_ref: str,
        identity: AuthIdentity,
        candidate: LLMClaimCandidate,
        idempotency_key: str,
        selection_anchor: SourceSpan | None = None,
        supersedes_claim_id: str | None = None,
        source_lineage_document_ref: str | None = None,
        source_lineage_document_digest: str | None = None,
    ) -> dict[str, str]:
        """Bind one explicit web user edit to exact server-side inputs."""

        if not document_text:
            raise ScienceInterpretationUnavailable("document text must be nonempty")
        candidate = validate_with_closed_error(
            lambda: LLMClaimCandidate.model_validate(
                candidate.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError, AttributeError),
            closed_error=ScienceInterpretationUnavailable(
                "Claim candidate failed closed schema validation"
            ),
        )
        self._idempotency_digest(idempotency_key)
        payload = self._user_revision_challenge_payload(
            document_text=document_text,
            document_ref=document_ref,
            candidate=candidate,
            idempotency_key=idempotency_key,
            selection_anchor=selection_anchor,
            supersedes_claim_id=supersedes_claim_id,
            source_lineage_document_ref=source_lineage_document_ref,
            source_lineage_document_digest=source_lineage_document_digest,
        )
        return self._issue_trusted_user_action_challenge(
            operation="submit_user_revision",
            identity=identity,
            payload=payload,
        )

    @staticmethod
    def _user_revision_challenge_payload(
        *,
        document_text: str,
        document_ref: str,
        candidate: LLMClaimCandidate,
        idempotency_key: str,
        selection_anchor: SourceSpan | None,
        supersedes_claim_id: str | None,
        source_lineage_document_ref: str | None,
        source_lineage_document_digest: str | None,
    ) -> dict[str, Any]:
        return {
            "document_text": document_text,
            "document_ref": document_ref,
            "candidate": candidate,
            "idempotency_key": idempotency_key,
            "selection_anchor": selection_anchor,
            "supersedes_claim_id": supersedes_claim_id,
            "source_lineage_document_ref": source_lineage_document_ref,
            "source_lineage_document_digest": source_lineage_document_digest,
        }

    def commit_user_revision(
        self,
        challenge_id: str,
        *,
        identity: AuthIdentity,
        document_text: str,
        document_ref: str,
        candidate: LLMClaimCandidate,
        idempotency_key: str,
        selection_anchor: SourceSpan | None = None,
        supersedes_claim_id: str | None = None,
        source_lineage_document_ref: str | None = None,
        source_lineage_document_digest: str | None = None,
    ) -> InterpretationRecord:
        """Consume one exact user-edit challenge; it cannot be replayed."""

        candidate = validate_with_closed_error(
            lambda: LLMClaimCandidate.model_validate(
                candidate.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError, AttributeError),
            closed_error=ScienceInterpretationUnavailable(
                "Claim candidate failed closed schema validation"
            ),
        )
        payload = self._user_revision_challenge_payload(
            document_text=document_text,
            document_ref=document_ref,
            candidate=candidate,
            idempotency_key=idempotency_key,
            selection_anchor=selection_anchor,
            supersedes_claim_id=supersedes_claim_id,
            source_lineage_document_ref=source_lineage_document_ref,
            source_lineage_document_digest=source_lineage_document_digest,
        )
        request_digest = sha256_digest(
            {
                "operation": "submit_user_revision",
                "actor_id": identity.employee_id,
                "payload": payload,
            }
        )
        self._consume_trusted_user_action_challenge(
            challenge_id,
            operation="submit_user_revision",
            identity=identity,
            request_digest=request_digest,
        )
        return self._submit_claim_candidate(
            document_text,
            document_ref=document_ref,
            identity=identity,
            client_kind="user",
            candidate=candidate,
            idempotency_key=idempotency_key,
            selection_anchor=selection_anchor,
            supersedes_claim_id=supersedes_claim_id,
            source_lineage_document_ref=source_lineage_document_ref,
            source_lineage_document_digest=source_lineage_document_digest,
        )

    def submit_claim_candidate(
        self,
        document_text: str,
        *,
        document_ref: str,
        identity: AuthIdentity,
        client_kind: ClaimSubmissionClientKind,
        candidate: LLMClaimCandidate,
        idempotency_key: str,
        selection_anchor: SourceSpan | None = None,
        supersedes_claim_id: str | None = None,
        source_lineage_document_ref: str | None = None,
        source_lineage_document_digest: str | None = None,
    ) -> InterpretationRecord:
        """Revalidate an untrusted external Claim proposal."""

        if client_kind == "user":
            raise ScienceConfirmationRequired(
                "a server-issued user revision challenge is required"
            )
        return self._submit_claim_candidate(
            document_text,
            document_ref=document_ref,
            identity=identity,
            client_kind=client_kind,
            candidate=candidate,
            idempotency_key=idempotency_key,
            selection_anchor=selection_anchor,
            supersedes_claim_id=supersedes_claim_id,
            source_lineage_document_ref=source_lineage_document_ref,
            source_lineage_document_digest=source_lineage_document_digest,
        )

    def _submit_claim_candidate(
        self,
        document_text: str,
        *,
        document_ref: str,
        identity: AuthIdentity,
        client_kind: ClaimSubmissionClientKind,
        candidate: LLMClaimCandidate,
        idempotency_key: str,
        selection_anchor: SourceSpan | None = None,
        supersedes_claim_id: str | None = None,
        source_lineage_document_ref: str | None = None,
        source_lineage_document_digest: str | None = None,
    ) -> InterpretationRecord:
        """Revalidate one untrusted external Claim candidate and pause for confirmation."""

        if not document_text:
            raise ScienceInterpretationUnavailable("document text must be nonempty")
        candidate = validate_with_closed_error(
            lambda: LLMClaimCandidate.model_validate(
                candidate.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError, AttributeError),
            closed_error=ScienceInterpretationUnavailable(
                "Claim candidate failed closed schema validation"
            ),
        )
        document_digest = sha256_digest(document_text)
        lineage_provided = (
            source_lineage_document_ref is not None
            or source_lineage_document_digest is not None
        )
        if bool(source_lineage_document_ref) != bool(source_lineage_document_digest):
            raise ScienceConfirmationRequired(
                "submitted document lineage is incomplete"
            )
        if lineage_provided and supersedes_claim_id is None:
            raise ScienceConfirmationRequired(
                "submitted document lineage requires a predecessor Claim"
            )
        if lineage_provided and (
            not document_ref.startswith("boi:submitted:")
            or not str(source_lineage_document_ref).startswith("boi:")
        ):
            raise ScienceConfirmationRequired(
                "a document revision must be stored under a submitted document identity"
            )
        if (
            document_ref.startswith("boi:submitted:")
            and supersedes_claim_id is None
            and document_ref
            != submitted_root_document_ref(
                actor_id=identity.employee_id,
                initial_document_digest=document_digest,
            )
        ):
            raise ScienceConfirmationRequired(
                "submitted root document identity is not actor/digest bound"
            )
        canonical_source_lineage: tuple[str, str] | None = None
        if supersedes_claim_id is not None:
            predecessors = list(self._proposal_records_for_claim(supersedes_claim_id))
            if not predecessors:
                raise ScienceConfirmationRequired(
                    "superseded Claim provenance is unavailable"
                )
            owned = [
                record
                for record in predecessors
                if record.operation_binding.actor_id == identity.employee_id
            ]
            if not owned:
                raise ScienceAuthorizationError(
                    "superseded Claim owner does not match trusted identity"
                )
            if lineage_provided:
                same_lineage = [
                    record
                    for record in owned
                    if len(record.candidate_claims) == 1
                    and record.candidate_claims[0].document_ref
                    == source_lineage_document_ref
                ]
                if not same_lineage:
                    raise ScienceConfirmationRequired(
                        "submitted lineage document does not match the predecessor Claim"
                    )
                if not any(
                    record.document_digest == source_lineage_document_digest
                    for record in same_lineage
                ):
                    raise ScienceConfirmationRequired(
                        "submitted lineage digest does not match the predecessor Claim"
                    )
                exact_lineage = [
                    record
                    for record in same_lineage
                    if record.document_digest == source_lineage_document_digest
                ]
                expected_document_ref = submitted_revision_document_ref(
                    actor_id=identity.employee_id,
                    source_document_ref=str(source_lineage_document_ref),
                    source_document_digest=str(source_lineage_document_digest),
                )
                if document_ref != expected_document_ref:
                    raise ScienceConfirmationRequired(
                        "submitted revision destination does not match trusted lineage"
                    )
                canonical_sources = {
                    self._canonical_source_lineage(record, identity=identity)
                    for record in exact_lineage
                }
                if len(canonical_sources) != 1:
                    raise ScienceConfirmationRequired(
                        "submitted document lineage is ambiguous"
                    )
                canonical_source_lineage = next(iter(canonical_sources))
                if (
                    canonical_source_lineage is not None
                    and not self._document_access_check(
                        identity, canonical_source_lineage[0]
                    )
                ):
                    raise ScienceAuthorizationError(
                        "Science interpretation document access is not authorized"
                    )
            elif not any(
                record.document_digest == document_digest
                and len(record.candidate_claims) == 1
                and record.candidate_claims[0].document_ref == document_ref
                for record in owned
            ):
                raise ScienceConfirmationRequired(
                    "superseded Claim does not match the exact source document"
                )
        prompt_digest = self._claim_submission_prompt_digest()
        interpretation_id = self._record_id("interpretation", idempotency_key)
        request_digest = sha256_digest(
            {
                "operation": "submit_claim_candidate",
                "document_ref": document_ref,
                "document_digest": document_digest,
                "selection_anchor": selection_anchor,
                "client_kind": client_kind,
                "candidate": candidate,
                "supersedes_claim_id": supersedes_claim_id,
                "source_lineage_document_ref": source_lineage_document_ref,
                "source_lineage_document_digest": source_lineage_document_digest,
                "canonical_source_document_ref": (
                    canonical_source_lineage[0]
                    if canonical_source_lineage is not None
                    else None
                ),
                "canonical_source_document_digest": (
                    canonical_source_lineage[1]
                    if canonical_source_lineage is not None
                    else None
                ),
                "dictionary_release_id": self.dictionary_release_id,
                "ontology_release_id": self.ontology_release_id,
            }
        )
        pending_binding = ScienceOperationBinding(
            operation="submit_claim_candidate",
            idempotency_key_digest=self._idempotency_digest(idempotency_key),
            actor_id=identity.employee_id,
            request_digest=request_digest,
            document_digest=document_digest,
            claim_digest=None,
            release_digest=None,
            prompt_digest=prompt_digest,
            source_interpretation_id=None,
            claim_ids=[],
        )
        existing = self._existing_interpretation(
            interpretation_id,
            pending_binding,
            derived_claim_digest=True,
        )
        if existing is not None:
            return existing

        interpreted_text = document_text
        selection_start = 0
        if selection_anchor is not None:
            selection = resolve_anchor(
                document_text,
                selection_anchor,
                document_digest=document_digest,
            )
            interpreted_text = selection.exact
            selection_start = selection.start

        claim, meanings, impact, formula_records = self._claim_from_candidate(
            candidate,
            document_text=document_text,
            interpreted_text=interpreted_text,
            document_ref=document_ref,
            document_digest=document_digest,
            selection_start=selection_start,
            ontology_index=self._ontology_index(),
            client_kind=client_kind,
        )
        claims = [claim]
        operation_binding = pending_binding.model_copy(
            update={
                "claim_digest": sha256_digest({"claim_packets": claims}),
                "claim_ids": [claim.claim_id],
            }
        )
        response_digest = sha256_digest({"candidate": candidate})
        record = validate_with_closed_error(
            lambda: InterpretationRecord(
                interpretation_id=interpretation_id,
                document_digest=document_digest,
                candidate_claims=claims,
                model_id=f"claim-client/{client_kind}",
                model_settings=LLMModelSettings(),
                prompt_version=CLAIM_SUBMISSION_VERSION,
                dictionary_release_id=self.dictionary_release_id,
                ontology_release_id=self.ontology_release_id,
                ontology_refs=claim.interpretation.ontology_refs,
                candidate_meanings=meanings,
                formula_candidates=formula_records,
                decision_impact=[impact],
                user_revision_history=[],
                confirmed_claim_packet_digest=None,
                response_digest=response_digest,
                operation_binding=operation_binding,
                submission_client_kind=client_kind,
                supersedes_claim_id=supersedes_claim_id,
                canonical_source_document_ref=(
                    canonical_source_lineage[0]
                    if canonical_source_lineage is not None
                    else None
                ),
                canonical_source_document_digest=(
                    canonical_source_lineage[1]
                    if canonical_source_lineage is not None
                    else None
                ),
            ),
            caught=(ValidationError, ValueError),
            closed_error=ScienceInterpretationUnavailable(
                "Claim submission record failed closed validation"
            ),
        )
        try:
            return self.runtime_store.save_interpretation(record, identity=identity)
        except ImmutableScienceRecordError:
            winner = self._existing_interpretation(
                interpretation_id,
                pending_binding,
                derived_claim_digest=True,
            )
            if winner is None:
                raise
            return winner

    def interpret_document(
        self,
        document_text: str,
        *,
        document_ref: str,
        identity: AuthIdentity,
        idempotency_key: str,
        selection_anchor: SourceSpan | None = None,
    ) -> InterpretationRecord:
        if not document_text:
            raise ScienceInterpretationUnavailable("document text must be nonempty")
        document_digest = sha256_digest(document_text)
        interpretation_id = self._record_id("interpretation", idempotency_key)
        llm_client = self._interpretation_client()
        prompt_digest = self._prompt_digest(llm_client)
        request_digest = sha256_digest(
            {
                "operation": "interpret_document",
                "document_ref": document_ref,
                "document_digest": document_digest,
                "selection_anchor": selection_anchor,
                "dictionary_release_id": self.dictionary_release_id,
                "ontology_release_id": self.ontology_release_id,
            }
        )
        pending_binding = ScienceOperationBinding(
            operation="interpret_document",
            idempotency_key_digest=self._idempotency_digest(idempotency_key),
            actor_id=identity.employee_id,
            request_digest=request_digest,
            document_digest=document_digest,
            claim_digest=None,
            release_digest=None,
            prompt_digest=prompt_digest,
            source_interpretation_id=None,
            claim_ids=[],
        )
        existing = self._existing_interpretation(
            interpretation_id,
            pending_binding,
            derived_claim_digest=True,
        )
        if existing is not None:
            return existing

        selection_start = 0
        interpreted_text = document_text
        if selection_anchor is not None:
            selection = resolve_anchor(
                document_text,
                selection_anchor,
                document_digest=document_digest,
            )
            selection_start = selection.start
            interpreted_text = selection.exact

        ontology_index = {
            binding_id: candidate
            for binding_id, candidate in self._ontology_index().items()
            if any(alias in interpreted_text for alias in candidate["aliases"])
        }
        result = llm_client.interpret(
            interpreted_text,
            ontology_candidates=list(ontology_index.values()),
        )
        response_digest = result.response_digest
        if not (
            isinstance(response_digest, str)
            and response_digest.startswith("sha256:")
            and len(response_digest) == 71
            and all(
                character in "0123456789abcdef"
                for character in response_digest.removeprefix("sha256:")
            )
        ):
            raise ScienceInterpretationUnavailable(
                "LLM response digest is not a canonical SHA-256 identity"
            )
        claims: list[ClaimPacket] = []
        meanings: list[CandidateMeaningRecord] = []
        formula_records: list[FormulaInterpretationRecord] = []
        impacts: list[InterpretationDecisionImpact] = []
        for candidate in result.payload.claims:
            (
                claim,
                candidate_meanings,
                decision_impact,
                candidate_formula_records,
            ) = self._claim_from_candidate(
                candidate,
                document_text=document_text,
                interpreted_text=interpreted_text,
                document_ref=document_ref,
                document_digest=document_digest,
                selection_start=selection_start,
                ontology_index=ontology_index,
                client_kind="qwen",
            )
            claims.append(claim)
            meanings.extend(candidate_meanings)
            formula_records.extend(candidate_formula_records)
            impacts.append(decision_impact)
        claim_ids = [claim.claim_id for claim in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ScienceInterpretationUnavailable(
                "LLM returned duplicate scientific claim candidates"
            )

        claim_digest = sha256_digest({"claim_packets": claims})
        operation_binding = pending_binding.model_copy(
            update={"claim_digest": claim_digest, "claim_ids": sorted(claim_ids)}
        )
        record = validate_with_closed_error(
            lambda: InterpretationRecord(
                interpretation_id=interpretation_id,
                document_digest=document_digest,
                candidate_claims=claims,
                model_id=llm_client.config.model_id,
                model_settings=llm_client.config.safe_model_settings(),
                prompt_version=PROMPT_VERSION,
                dictionary_release_id=self.dictionary_release_id,
                ontology_release_id=self.ontology_release_id,
                ontology_refs=sorted(
                    {
                        ref
                        for claim in claims
                        for ref in claim.interpretation.ontology_refs
                    }
                ),
                candidate_meanings=meanings,
                formula_candidates=formula_records,
                decision_impact=impacts,
                user_revision_history=[],
                confirmed_claim_packet_digest=None,
                response_digest=response_digest,
                operation_binding=operation_binding,
            ),
            caught=(ValidationError, ValueError),
            closed_error=ScienceInterpretationUnavailable(
                "Science interpretation record failed closed validation"
            ),
        )
        try:
            return self.runtime_store.save_interpretation(record, identity=identity)
        except ImmutableScienceRecordError:
            winner = self._existing_interpretation(
                interpretation_id,
                pending_binding,
                derived_claim_digest=True,
            )
            if winner is None:
                raise
            return winner

    @staticmethod
    def _confirmed_claims_digest(claims: Sequence[ClaimPacket]) -> str | None:
        if not claims:
            return None
        if len(claims) == 1:
            return sha256_digest(claims[0])
        return sha256_digest({"claim_packets": list(claims)})

    def issue_confirmation_challenge(
        self,
        source_interpretation_id: str,
        *,
        claim_ids: Sequence[str],
        identity: AuthIdentity,
        idempotency_key: str,
    ) -> dict[str, str]:
        """Bind a human confirmation click to one immutable interpretation revision."""

        source = self.runtime_store.load_interpretation(source_interpretation_id)
        if source.interpretation_id != source_interpretation_id:
            raise ScienceOperationalError(
                "stored interpretation identity does not match the requested record"
            )
        self._require_interpretation_access(source, identity=identity)
        selected_ids = sorted(claim_ids)
        if not selected_ids or len(selected_ids) != len(set(selected_ids)):
            raise ScienceConfirmationRequired(
                "confirmation requires unique stored claim identities"
            )
        if set(selected_ids) - {
            claim.claim_id for claim in source.candidate_claims
        }:
            raise ScienceConfirmationRequired(
                "confirmation references an unknown claim candidate"
            )
        self._idempotency_digest(idempotency_key)
        payload = self._confirmation_challenge_payload(
            source=source,
            source_interpretation_id=source_interpretation_id,
            claim_ids=selected_ids,
            idempotency_key=idempotency_key,
        )
        return self._issue_trusted_user_action_challenge(
            operation="confirm_interpretation",
            identity=identity,
            payload=payload,
        )

    @staticmethod
    def _confirmation_challenge_payload(
        *,
        source: InterpretationRecord,
        source_interpretation_id: str,
        claim_ids: Sequence[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "source_interpretation_id": source_interpretation_id,
            "source_response_digest": source.response_digest,
            "source_operation_request_digest": (
                source.operation_binding.request_digest
            ),
            "claim_ids": sorted(claim_ids),
            "idempotency_key": idempotency_key,
        }

    def commit_interpretation_confirmation(
        self,
        challenge_id: str,
        *,
        identity: AuthIdentity,
        source_interpretation_id: str,
        claim_ids: Sequence[str],
        idempotency_key: str,
    ) -> InterpretationRecord:
        """Consume one exact confirmation challenge; it cannot be replayed."""

        source = self.runtime_store.load_interpretation(source_interpretation_id)
        self._require_interpretation_access(source, identity=identity)
        payload = self._confirmation_challenge_payload(
            source=source,
            source_interpretation_id=source_interpretation_id,
            claim_ids=claim_ids,
            idempotency_key=idempotency_key,
        )
        request_digest = sha256_digest(
            {
                "operation": "confirm_interpretation",
                "actor_id": identity.employee_id,
                "payload": payload,
            }
        )
        self._consume_trusted_user_action_challenge(
            challenge_id,
            operation="confirm_interpretation",
            identity=identity,
            request_digest=request_digest,
        )
        return self._confirm_interpretation(
            source_interpretation_id,
            claim_ids=sorted(claim_ids),
            identity=identity,
            idempotency_key=idempotency_key,
        )

    def confirm_interpretation(
        self,
        source_interpretation_id: str,
        *,
        claim_ids: Sequence[str],
        identity: AuthIdentity,
        idempotency_key: str,
    ) -> InterpretationRecord:
        """Reject direct confirmation without the trusted user ceremony."""

        raise ScienceConfirmationRequired(
            "a server-issued interpretation confirmation challenge is required"
        )

    def _confirm_interpretation(
        self,
        source_interpretation_id: str,
        *,
        claim_ids: Sequence[str],
        identity: AuthIdentity,
        idempotency_key: str,
    ) -> InterpretationRecord:
        source = self.runtime_store.load_interpretation(source_interpretation_id)
        if source.interpretation_id != source_interpretation_id:
            raise ScienceOperationalError(
                "stored interpretation identity does not match the requested record"
            )
        self._require_interpretation_access(source, identity=identity)
        if source.operation_binding.operation not in {
            "interpret_document",
            "submit_claim_candidate",
        }:
            raise ScienceConfirmationRequired(
                "confirmation requires an immutable interpretation proposal"
            )
        selected_ids = sorted(claim_ids)
        if not selected_ids or len(selected_ids) != len(set(selected_ids)):
            raise ScienceConfirmationRequired(
                "confirmation requires unique stored claim identities"
            )
        claims_by_id = {claim.claim_id: claim for claim in source.candidate_claims}
        if set(selected_ids) - set(claims_by_id):
            raise ScienceConfirmationRequired(
                "confirmation references an unknown claim candidate"
            )
        impacts_by_claim = {
            impact.claim_id: impact for impact in source.decision_impact
        }
        for claim_id in selected_ids:
            impact = impacts_by_claim.get(claim_id)
            if impact is None or impact.status != "requires_user_confirmation":
                raise ScienceConfirmationRequired(
                    "semantic mismatch must be revised before confirmation"
                )
            if impact.issue_codes != ["USER_CONFIRMATION_REQUIRED"]:
                raise ScienceConfirmationRequired(
                    "semantic mismatch must be revised before confirmation"
                )

        selected = set(selected_ids)
        confirmed_claims = [
            claim.model_copy(
                update={
                    "interpretation": claim.interpretation.model_copy(
                        update={"ambiguity_ids": [], "user_confirmed": True}
                    )
                },
                deep=True,
            )
            if claim.claim_id in selected
            else claim.model_copy(deep=True)
            for claim in source.candidate_claims
        ]
        confirmed_digest = self._confirmed_claims_digest(
            [claim for claim in confirmed_claims if claim.claim_id in selected]
        )
        if confirmed_digest is None:
            raise ScienceConfirmationRequired(
                "confirmation requires at least one validated claim"
            )
        request_digest = sha256_digest(
            {
                "operation": "confirm_interpretation",
                "source_interpretation_id": source_interpretation_id,
                "source_response_digest": source.response_digest,
                "claim_ids": selected_ids,
            }
        )
        interpretation_id = self._record_id("interpretation", idempotency_key)
        binding = ScienceOperationBinding(
            operation="confirm_interpretation",
            idempotency_key_digest=self._idempotency_digest(idempotency_key),
            actor_id=identity.employee_id,
            request_digest=request_digest,
            document_digest=source.document_digest,
            claim_digest=confirmed_digest,
            release_digest=None,
            prompt_digest=source.operation_binding.prompt_digest,
            source_interpretation_id=source_interpretation_id,
            claim_ids=selected_ids,
        )
        existing = self._existing_interpretation(interpretation_id, binding)
        if existing is not None:
            return existing

        occurred_at = self._clock()
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ScienceOperationalError(
                "Science confirmation clock must be timezone-aware"
            )
        revision = InterpretationRevisionEvent(
            action="claim_confirmed",
            actor_id=identity.employee_id,
            source_interpretation_id=source_interpretation_id,
            claim_ids=selected_ids,
            occurred_at=occurred_at,
        )
        record = source.model_copy(
            update={
                "interpretation_id": interpretation_id,
                "candidate_claims": confirmed_claims,
                "user_revision_history": [*source.user_revision_history, revision],
                "confirmed_claim_packet_digest": confirmed_digest,
                "operation_binding": binding,
            },
            deep=True,
        )
        record = validate_with_closed_error(
            lambda: InterpretationRecord.model_validate(
                record.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError),
            closed_error=ScienceConfirmationRequired(
                "confirmation failed closed validation"
            ),
        )
        try:
            return self.runtime_store.save_interpretation(record, identity=identity)
        except ImmutableScienceRecordError:
            winner = self._existing_interpretation(interpretation_id, binding)
            if winner is None:
                raise
            return winner

    def _operational_verification(
        self,
        selection: ReleaseSelection,
    ) -> tuple[ResolvedReleaseSet, OperationalVerification]:
        release_set = self.catalog.resolve_release_set(selection)
        if release_set.selection != selection:
            raise ScienceOperationalError(
                "Catalog result does not match the exact release selection"
            )
        operational = self.catalog.resolve_operational_rule_set(release_set)
        if type(operational) is not OperationalVerification:
            raise ScienceOperationalError(
                "Catalog-issued operational verification is required"
            )
        expected_release_ids = (
            selection.foundation,
            *selection.domains,
            *selection.applications,
        )
        if operational.release_ids != expected_release_ids:
            raise ScienceOperationalError(
                "operational verification does not match the exact release selection"
            )
        return release_set, operational

    @staticmethod
    def _assert_verdict_release_binding(
        verdict: VerdictPacket,
        release_set: ResolvedReleaseSet,
    ) -> None:
        if (
            verdict.releases.selection != release_set.selection
            or verdict.releases.digests != release_set.release_digests
            or verdict.releases.combined_digest != release_set.combined_digest
        ):
            raise ScienceOperationalError(
                "verdict does not match the exact operational release selection"
            )

    @staticmethod
    def _pinned_component(
        release_set: ResolvedReleaseSet,
        *,
        ref: str,
        kind: str,
    ):
        matches = [
            component
            for component in release_set.components
            if component.ref == ref and component.kind == kind
        ]
        if len(matches) != 1:
            raise ScienceOperationalError(
                f"grounded explanation reference is not pinned: {ref}"
            )
        component = matches[0]
        if component.declared_digest != component.actual_digest:
            raise ScienceOperationalError(
                f"grounded explanation digest is not verified: {ref}"
            )
        return component

    def _pinned_object(
        self,
        release_set: ResolvedReleaseSet,
        *,
        ref: str,
        kind: str,
    ):
        component = self._pinned_component(release_set, ref=ref, kind=kind)
        loader = getattr(self.catalog, kind)
        object_ = loader(ref)
        if (
            getattr(object_, "object_id", None) != ref
            or getattr(object_, "digest", None) != component.actual_digest
        ):
            raise ScienceOperationalError(
                f"grounded explanation object does not match its release digest: {ref}"
            )
        return object_

    def _evidence_link(
        self,
        release_set: ResolvedReleaseSet,
        evidence_ref: str,
    ) -> EvidenceLink:
        identity = self.catalog.resolve_reviewed_source_url_identity(
            release_set, evidence_ref
        )
        if type(identity) is not ReviewedSourceURLIdentity:
            raise ScienceOperationalError(
                "Catalog-issued reviewed Source URL identity is required"
            )
        reviewed_source = validate_with_closed_error(
            lambda: _open_reviewed_source_url_identity(identity),
            caught=(TypeError, ValueError),
            closed_error=ScienceOperationalError(
                "reviewed Source URL identity failed closed validation"
            ),
        )
        if (
            reviewed_source.release_set_digest != release_set.combined_digest
            or reviewed_source.evidence_id != evidence_ref
        ):
            raise ScienceOperationalError(
                "reviewed Source URL identity does not match the exact release"
            )
        evidence = self._pinned_object(
            release_set,
            ref=evidence_ref,
            kind="evidence",
        )
        source_id = getattr(evidence, "source_id", None)
        locator = getattr(evidence, "locator", None)
        if (
            not isinstance(source_id, str)
            or not isinstance(locator, Mapping)
            or source_id != reviewed_source.source_id
            or evidence.digest != reviewed_source.evidence_digest
            or dict(locator)
            != reviewed_source.locator.model_dump(mode="json", exclude_none=True)
        ):
            raise ScienceOperationalError(
                "grounded Evidence does not match its reviewed identity: "
                f"{evidence_ref}"
            )
        source = self._pinned_object(
            release_set,
            ref=source_id,
            kind="source",
        )
        url = getattr(source, "original_url", None)
        if (
            source.digest != reviewed_source.source_digest
            or url != reviewed_source.canonical_source_url
        ):
            raise ScienceOperationalError(
                f"grounded Source does not match its reviewed identity: {source_id}"
            )
        original_text = getattr(evidence, "original_text", None)
        original_text_hash = getattr(evidence, "original_text_hash", None)
        if (
            not isinstance(original_text, str)
            or not isinstance(original_text_hash, str)
            or sha256_digest(original_text) != original_text_hash
        ):
            raise ScienceOperationalError(
                f"grounded Evidence quote hash is invalid: {evidence_ref}"
            )
        required_source_fields = {
            "boi_id": getattr(source, "boi_id", None),
            "visibility": getattr(source, "visibility", None),
            "classification": getattr(source, "classification", None),
            "acl_policy": getattr(source, "acl_policy", None),
        }
        if not all(
            isinstance(value, str) and value
            for value in required_source_fields.values()
        ):
            raise ScienceOperationalError(
                f"grounded Source has no exact ACL identity: {source_id}"
            )
        path = getattr(source, "path", None)
        boi_root = getattr(self.catalog, "boi_root", None)
        try:
            versioned_path = path.relative_to(boi_root).as_posix()
        except (AttributeError, TypeError, ValueError):
            raise ScienceOperationalError(
                f"grounded Source has no versioned lookup path: {source_id}"
            ) from None
        source_lookup_data = {
            "source_id": source_id,
            "source_digest": source.digest,
            "boi_id": required_source_fields["boi_id"],
            "versioned_path": versioned_path,
            "visibility": required_source_fields["visibility"],
            "classification": required_source_fields["classification"],
            "acl_policy": required_source_fields["acl_policy"],
        }
        source_lookup = SourceLookupIdentity(
            **source_lookup_data,
            lookup_digest=sha256_digest(source_lookup_data),
        )
        return EvidenceLink(
            evidence_id=evidence_ref,
            evidence_digest=evidence.digest,
            source_id=source_id,
            source_digest=source.digest,
            original_text_hash=original_text_hash,
            quote_hash=original_text_hash,
            url=reviewed_source.canonical_source_url,
            locator=reviewed_source.locator,
            source_lookup=source_lookup,
            reviewed_source=reviewed_source,
        )

    def _grounded_annotations(
        self,
        claim_id: str,
        verdict: VerdictPacket,
        release_set: ResolvedReleaseSet,
    ) -> list[GroundedAnnotation]:
        annotations: list[GroundedAnnotation] = []
        for fact in verdict.explanation_facts:
            allowed_evidence = set(fact.evidence_refs)
            mapped_evidence: set[str] = set()
            for knowledge_ref in fact.knowledge_refs:
                knowledge = self._pinned_object(
                    release_set,
                    ref=knowledge_ref,
                    kind="knowledge",
                )
                statement = getattr(knowledge, "statement", None)
                evidence_refs = getattr(knowledge, "evidence_refs", None)
                if not isinstance(statement, str) or not statement.strip():
                    raise ScienceOperationalError(
                        f"grounded statement is unavailable: {knowledge_ref}"
                    )
                if not isinstance(evidence_refs, list) or not all(
                    isinstance(ref, str) for ref in evidence_refs
                ):
                    raise ScienceOperationalError(
                        f"grounded statement has invalid Evidence refs: {knowledge_ref}"
                    )
                sentence_evidence = sorted(allowed_evidence & set(evidence_refs))
                if not sentence_evidence:
                    raise ScienceOperationalError(
                        f"grounded statement has no decisive Evidence: {knowledge_ref}"
                    )
                mapped_evidence.update(sentence_evidence)
                annotations.append(
                    GroundedAnnotation(
                        claim_id=claim_id,
                        fact_id=fact.fact_id,
                        text=statement,
                        knowledge_id=knowledge_ref,
                        knowledge_digest=knowledge.digest,
                        evidence_links=[
                            self._evidence_link(release_set, evidence_ref)
                            for evidence_ref in sentence_evidence
                        ],
                    )
                )
            if mapped_evidence != allowed_evidence:
                raise ScienceOperationalError(
                    f"decisive Explanation Fact has unmapped Evidence: {fact.fact_id}"
                )
        return annotations

    @staticmethod
    def _fact_rule_id(fact_id: str, verdict: VerdictPacket) -> str:
        matches = [
            rule_id
            for rule_id in verdict.decisive_rule_ids
            if fact_id.startswith(f"fact:{rule_id}:")
        ]
        if len(matches) != 1:
            raise ScienceOperationalError(
                f"Explanation Fact has no exact decisive Rule: {fact_id}"
            )
        return matches[0]

    def _released_rule(
        self,
        release_set: ResolvedReleaseSet,
        rule_id: str,
    ) -> tuple[VerificationRule, str]:
        component = self._pinned_component(release_set, ref=rule_id, kind="rule")
        loader = getattr(self.catalog, "rule", None)
        if not callable(loader):
            raise ScienceOperationalError(
                f"grounded Rule loader is unavailable: {rule_id}"
            )
        stored = loader(rule_id)
        if (
            getattr(stored, "object_id", None) != rule_id
            or getattr(stored, "digest", None) != component.actual_digest
        ):
            raise ScienceOperationalError(
                f"grounded Rule does not match its release digest: {rule_id}"
            )
        payload = {
            field_name: getattr(stored, field_name)
            for field_name in VerificationRule.model_fields
            if hasattr(stored, field_name)
        }
        try:
            return VerificationRule.model_validate(payload), component.actual_digest
        except (ValidationError, ValueError, TypeError):
            raise ScienceOperationalError(
                f"grounded Rule payload is invalid: {rule_id}"
            ) from None

    @staticmethod
    def _object_refs(
        pairs: Sequence[tuple[str, str]],
    ) -> list[GroundedObjectRef]:
        return [
            GroundedObjectRef(object_id=object_id, object_digest=digest)
            for object_id, digest in pairs
        ]

    def _equation_grounding(
        self,
        *,
        rule: VerificationRule,
        rule_digest: str,
        release_set: ResolvedReleaseSet,
        evidence_links: Sequence[EvidenceLink],
    ) -> tuple[list[GroundedEquationRef], list[ReportEquationAsset]]:
        binding = rule.equation_binding
        if binding is None:
            return [], []
        equation_loader = getattr(self.catalog, "equation", None)
        if not callable(equation_loader):
            raise ScienceOperationalError(
                f"grounded Equation loader is unavailable: {binding.equation_id}"
            )
        try:
            resolved = equation_loader(binding.equation_id)
            equation = resolved.equation
        except (ScienceCatalogError, AttributeError, ValueError, TypeError):
            raise ScienceOperationalError(
                f"grounded Equation is unavailable: {binding.equation_id}"
            ) from None
        if (
            equation.equation_digest != binding.equation_digest
            or equation.decision_use != "deterministic_rule"
            or resolved.knowledge_id not in rule.knowledge_refs
        ):
            raise ScienceOperationalError(
                f"grounded Equation does not match its decisive Rule: {rule.rule_id}"
            )
        knowledge_component = self._pinned_component(
            release_set,
            ref=resolved.knowledge_id,
            kind="knowledge",
        )
        if knowledge_component.actual_digest != resolved.knowledge_digest:
            raise ScienceOperationalError(
                f"grounded Equation Knowledge digest is not pinned: {binding.equation_id}"
            )
        equation_evidence_ids = [use.evidence_ref for use in equation.evidence_uses]
        links_by_id = {link.evidence_id: link for link in evidence_links}
        if not set(equation_evidence_ids) <= set(links_by_id):
            raise ScienceOperationalError(
                f"grounded Equation Evidence is incomplete: {binding.equation_id}"
            )
        equation_links = [links_by_id[item] for item in equation_evidence_ids]
        equation_ref = GroundedEquationRef(
            equation_id=equation.equation_id,
            equation_digest=equation.equation_digest,
            knowledge_id=resolved.knowledge_id,
            knowledge_digest=resolved.knowledge_digest,
            rule_id=rule.rule_id,
            rule_digest=rule_digest,
            decision_use="deterministic_rule",
            evaluator_id=binding.evaluator_id,
            evaluator_version=binding.evaluator_version,
            evaluator_digest=binding.evaluator_digest,
            binding_digest=binding.binding_digest,
            variable_mappings=[
                item.model_dump(mode="json") for item in binding.variable_mappings
            ],
        )
        presentation = None
        try:
            presentation = equation_asset_index().get(
                (equation.equation_id, equation.equation_digest)
            )
        except ValueError:
            # Rendering is presentation-only.  The stored plain-text and LaTeX
            # fallbacks remain available and the verdict is unchanged.
            presentation = None
        asset_payload: dict[str, Any] = {
            "equation_id": equation.equation_id,
            "equation_digest": equation.equation_digest,
            "knowledge_id": resolved.knowledge_id,
            "knowledge_digest": resolved.knowledge_digest,
            "scientific_role": equation.scientific_role,
            "decision_use": equation.decision_use,
            "display_latex": equation.display_latex,
            "plain_text": equation.plain_text,
            "accessibility_reading": equation.accessibility_reading,
            "variables": equation.variables,
            "assumptions": equation.assumptions,
            "applicability": equation.applicability,
            "invalid_outside": equation.invalid_outside,
            "boundary_conditions": equation.boundary_conditions,
            "evidence_links": equation_links,
        }
        if presentation is not None:
            asset_payload.update(
                {
                    "sanitized_svg": presentation.sanitized_svg,
                    "svg_digest": presentation.svg_digest,
                    "renderer": presentation.renderer,
                    "asset_digest": presentation.asset_digest,
                }
            )
        return [equation_ref], [ReportEquationAsset(**asset_payload)]

    def _grounded_explanation(
        self,
        *,
        verdict: VerdictPacket,
        fact_id: str,
        annotations: Sequence[GroundedAnnotation],
        release_set: ResolvedReleaseSet,
    ) -> tuple[GroundedExplanation, list[ReportEquationAsset]]:
        rule_id = self._fact_rule_id(fact_id, verdict)
        rule, rule_digest = self._released_rule(release_set, rule_id)
        if {item.knowledge_id for item in annotations} != set(rule.knowledge_refs):
            raise ScienceOperationalError(
                f"structured explanation Knowledge is incomplete: {fact_id}"
            )
        evidence_links_by_id = {
            link.evidence_id: link
            for annotation in annotations
            for link in annotation.evidence_links
        }
        if set(evidence_links_by_id) != set(rule.evidence_refs):
            raise ScienceOperationalError(
                f"structured explanation Evidence is incomplete: {fact_id}"
            )
        evidence_links = [
            evidence_links_by_id[item] for item in sorted(evidence_links_by_id)
        ]
        knowledge_refs = self._object_refs(
            sorted((item.knowledge_id, item.knowledge_digest) for item in annotations)
        )
        rule_refs = self._object_refs([(rule.rule_id, rule_digest)])
        evidence_refs = self._object_refs(
            [(item.evidence_id, item.evidence_digest) for item in evidence_links]
        )
        equation_refs, equation_assets = self._equation_grounding(
            rule=rule,
            rule_digest=rule_digest,
            release_set=release_set,
            evidence_links=evidence_links,
        )

        blocks: list[GroundedExplanationBlock] = []

        def add(kind: str, text: str) -> None:
            if not text.strip():
                return
            blocks.append(
                GroundedExplanationBlock(
                    sequence=len(blocks) + 1,
                    block_kind=kind,
                    text=text,
                    knowledge_refs=knowledge_refs,
                    equation_refs=equation_refs,
                    rule_refs=rule_refs,
                    evidence_refs=evidence_refs,
                )
            )

        for annotation in sorted(annotations, key=lambda item: item.knowledge_id):
            add("applied_principle", annotation.text)
        for asset in equation_assets:
            add("reviewed_equation", asset.plain_text)
            for variable in asset.variables:
                add(
                    "variable_meaning",
                    (
                        f"{variable.symbol}: {variable.definition}; unit={variable.unit}; "
                        f"domain={variable.domain}; sign={variable.sign_constraint}"
                    ),
                )
            for statement in (*asset.assumptions, *asset.applicability):
                add("applicability", statement)
        for equation_ref in equation_refs:
            for mapping in equation_ref.variable_mappings:
                add(
                    "claim_mapping",
                    (
                        f"{mapping.equation_variable_id} -> "
                        f"Claim quantity {mapping.claim_quantity_kind} "
                        f"({mapping.constraint_operand})"
                    ),
                )
        add(
            "scientific_consequence",
            f"{verdict.verdict.value}: {', '.join(verdict.reason_codes)}",
        )
        if verdict.corrected_claim is not None:
            add("correction", verdict.corrected_claim)
        for limitation in verdict.limitations:
            add("limitation", limitation)
        for asset in equation_assets:
            for boundary in asset.invalid_outside:
                add("limitation", boundary)
        for link in evidence_links:
            locator = canonical_json_bytes(
                link.locator.model_dump(mode="json", exclude_none=True)
            ).decode("utf-8")
            add("evidence", f"{link.evidence_id}; locator={locator}")
        return (
            GroundedExplanation(
                claim_id=verdict.claim_id,
                fact_id=fact_id,
                knowledge_refs=knowledge_refs,
                equation_refs=equation_refs,
                rule_refs=rule_refs,
                evidence_links=evidence_links,
                blocks=blocks,
            ),
            equation_assets,
        )

    def _authoritative_confirmation(
        self, interpretation_id: str, *, identity: AuthIdentity
    ) -> InterpretationRecord:
        """Resolve an explicit confirmation and its immutable proposal dependency."""

        try:
            stored = self.runtime_store.load_interpretation(interpretation_id)
        except (KeyError, ValueError, AttributeError):
            raise ScienceConfirmationRequired(
                "verification requires a valid stored confirmation"
            ) from None
        interpretation = validate_with_closed_error(
            lambda: InterpretationRecord.model_validate(
                stored.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError, AttributeError),
            closed_error=ScienceConfirmationRequired(
                "verification requires a valid stored confirmation"
            ),
        )
        binding = interpretation.operation_binding
        if (
            interpretation.interpretation_id != interpretation_id
            or binding.operation != "confirm_interpretation"
            or binding.source_interpretation_id is None
        ):
            raise ScienceConfirmationRequired(
                "verification requires an explicit identity-bound confirmation"
            )
        self._require_interpretation_access(interpretation, identity=identity)
        try:
            source_stored = self.runtime_store.load_interpretation(
                binding.source_interpretation_id
            )
        except (KeyError, ValueError, AttributeError):
            raise ScienceConfirmationRequired(
                "confirmation proposal dependency is unavailable"
            ) from None
        source = validate_with_closed_error(
            lambda: InterpretationRecord.model_validate(
                source_stored.model_dump(mode="json", exclude_none=False)
            ),
            caught=(ValidationError, ValueError, AttributeError),
            closed_error=ScienceConfirmationRequired(
                "confirmation proposal dependency is unavailable"
            ),
        )
        if (
            source.interpretation_id != binding.source_interpretation_id
            or source.operation_binding.operation
            not in {"interpret_document", "submit_claim_candidate"}
        ):
            raise ScienceConfirmationRequired(
                "confirmation proposal dependency is invalid"
            )
        self._require_interpretation_access(source, identity=identity)

        selected = set(binding.claim_ids)
        expected_claims = [
            claim.model_copy(
                update={
                    "interpretation": claim.interpretation.model_copy(
                        update={"ambiguity_ids": [], "user_confirmed": True}
                    )
                },
                deep=True,
            )
            if claim.claim_id in selected
            else claim.model_copy(deep=True)
            for claim in source.candidate_claims
        ]
        immutable_fields = (
            "document_digest",
            "model_id",
            "model_settings",
            "prompt_version",
            "dictionary_release_id",
            "ontology_release_id",
            "ontology_refs",
            "candidate_meanings",
            "decision_impact",
            "response_digest",
            "submission_client_kind",
            "supersedes_claim_id",
            "canonical_source_document_ref",
            "canonical_source_document_digest",
        )
        if interpretation.candidate_claims != expected_claims or any(
            getattr(interpretation, field) != getattr(source, field)
            for field in immutable_fields
        ):
            raise ScienceConfirmationRequired(
                "confirmation does not match its immutable proposal"
            )
        return interpretation

    def verify_claim(
        self,
        interpretation_id: str,
        claim_id: str,
        selection: ReleaseSelection,
        *,
        identity: AuthIdentity,
    ) -> VerdictPacket:
        interpretation = self._authoritative_confirmation(
            interpretation_id, identity=identity
        )
        matching = [
            claim
            for claim in interpretation.candidate_claims
            if claim.claim_id == claim_id
        ]
        if len(matching) != 1:
            raise ScienceConfirmationRequired(
                "verification requires one stored claim candidate"
            )
        claim = matching[0]
        if (
            not claim.interpretation.user_confirmed
            or claim.interpretation.ambiguity_ids
        ):
            raise ScienceConfirmationRequired(
                "verification requires an explicitly confirmed interpretation"
            )
        confirmed = [
            item
            for item in interpretation.candidate_claims
            if item.interpretation.user_confirmed
            and not item.interpretation.ambiguity_ids
        ]
        if (
            interpretation.confirmed_claim_packet_digest
            != self._confirmed_claims_digest(confirmed)
        ):
            raise ScienceOperationalError(
                "confirmed Claim Packet digest does not match the stored claims"
            )
        release_set, operational = self._operational_verification(selection)
        verdict = verify_scientific_claim(claim, operational)
        self._assert_verdict_release_binding(verdict, release_set)
        return verdict

    def verify_document(
        self,
        interpretation_id: str,
        selection: ReleaseSelection,
        *,
        identity: AuthIdentity,
        idempotency_key: str,
    ) -> VerificationReport:
        interpretation = self._authoritative_confirmation(
            interpretation_id, identity=identity
        )
        if interpretation.interpretation_id != interpretation_id:
            raise ScienceOperationalError(
                "stored interpretation identity does not match the requested record"
            )
        if not interpretation.candidate_claims:
            raise ScienceOperationalError(
                "stored interpretation has no claim candidates"
            )
        for claim in interpretation.candidate_claims:
            if (
                claim.document_digest != interpretation.document_digest
                or claim.document_ref != interpretation.candidate_claims[0].document_ref
            ):
                raise ScienceOperationalError(
                    "stored interpretation claim/document binding is inconsistent"
                )
        confirmed_claims = [
            claim
            for claim in interpretation.candidate_claims
            if claim.interpretation.user_confirmed
            and not claim.interpretation.ambiguity_ids
        ]
        if (
            interpretation.confirmed_claim_packet_digest
            != self._confirmed_claims_digest(confirmed_claims)
        ):
            raise ScienceOperationalError(
                "confirmed Claim Packet digest does not match the stored claims"
            )
        if len(confirmed_claims) != len(interpretation.candidate_claims):
            raise ScienceConfirmationRequired(
                "document verification requires all claim candidates to be confirmed"
            )

        claim_digest = interpretation.confirmed_claim_packet_digest
        if claim_digest is None:
            raise ScienceConfirmationRequired(
                "document verification requires a confirmed Claim Packet digest"
            )
        release_digest = sha256_digest(selection)
        request_digest = sha256_digest(
            {
                "operation": "verify_document",
                "interpretation_id": interpretation_id,
                "claim_digest": claim_digest,
                "release_selection": selection,
            }
        )
        report_id = self._record_id("report", idempotency_key)
        binding = ScienceOperationBinding(
            operation="verify_document",
            idempotency_key_digest=self._idempotency_digest(idempotency_key),
            actor_id=identity.employee_id,
            request_digest=request_digest,
            document_digest=interpretation.document_digest,
            claim_digest=claim_digest,
            release_digest=release_digest,
            prompt_digest=interpretation.operation_binding.prompt_digest,
            source_interpretation_id=interpretation_id,
            claim_ids=sorted(claim.claim_id for claim in confirmed_claims),
        )
        existing = self._existing_report(report_id, binding)
        if existing is not None:
            return existing

        release_set, operational = self._operational_verification(selection)
        verdicts: list[VerdictPacket] = []
        annotations: list[GroundedAnnotation] = []
        explanations: list[GroundedExplanation] = []
        equation_assets_by_identity: dict[tuple[str, str], ReportEquationAsset] = {}
        for claim in confirmed_claims:
            verdict = verify_scientific_claim(claim, operational)
            self._assert_verdict_release_binding(verdict, release_set)
            verdicts.append(verdict)
            claim_annotations = self._grounded_annotations(
                claim.claim_id, verdict, release_set
            )
            annotations.extend(claim_annotations)
            by_fact: dict[str, list[GroundedAnnotation]] = {}
            for annotation in claim_annotations:
                by_fact.setdefault(annotation.fact_id, []).append(annotation)
            for fact in verdict.explanation_facts:
                explanation, assets = self._grounded_explanation(
                    verdict=verdict,
                    fact_id=fact.fact_id,
                    annotations=by_fact.get(fact.fact_id, []),
                    release_set=release_set,
                )
                explanations.append(explanation)
                for asset in assets:
                    identity_key = (asset.equation_id, asset.equation_digest)
                    existing_asset = equation_assets_by_identity.setdefault(
                        identity_key, asset
                    )
                    if existing_asset != asset:
                        raise ScienceOperationalError(
                            "one Equation identity resolved to different report assets"
                        )

        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ScienceOperationalError("Science report clock must be timezone-aware")
        payload = {
            "report_id": report_id,
            "document_ref": interpretation.candidate_claims[0].document_ref,
            "document_digest": interpretation.document_digest,
            "release_selection": selection,
            "release_digests": release_set.release_digests,
            "interpretation_ids": [interpretation.interpretation_id],
            "confirmed_claims": confirmed_claims,
            "verdict_packets": verdicts,
            "unresolved_ambiguities": [],
            "annotations": annotations,
            "explanations": explanations,
            "equation_assets": [
                equation_assets_by_identity[key]
                for key in sorted(equation_assets_by_identity)
            ],
            "created_at": created_at,
            "created_by": identity.employee_id,
            "operation_binding": binding,
        }
        provisional = VerificationReport.model_construct(
            **payload,
            report_digest="sha256:pending",
        )
        report = VerificationReport(
            **payload,
            report_digest=sha256_digest(
                verification_report_scientific_payload(provisional)
            ),
        )
        try:
            return self.runtime_store.save_report(report, identity=identity)
        except ImmutableScienceRecordError:
            winner = self._existing_report(report_id, binding)
            if winner is None:
                raise
            return winner
