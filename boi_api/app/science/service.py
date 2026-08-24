"""Application orchestration around interpretation and deterministic verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import ValidationError

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.anchors import resolve_anchor
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.engine import verify_claim as verify_scientific_claim
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
    GroundedAnnotation,
    InterpretationDecisionImpact,
    InterpretationRecord,
    InterpretationRevisionEvent,
    LLMModelSettings,
    ReleaseSelection,
    ResolvedReleaseSet,
    ScienceOperationBinding,
    SourceLookupIdentity,
    SourceSpan,
    VerdictPacket,
    VerificationReport,
)
from boi_api.app.science.operational import OperationalVerification
from boi_api.app.science.safety import validate_with_closed_error
from boi_api.app.science.source_identity import (
    ReviewedSourceURLIdentity,
    _open_reviewed_source_url_identity,
)
from boi_api.app.science.storage import ImmutableScienceRecordError


class ScienceConfirmationRequired(ScienceOperationalError):
    """A server-validated interpretation still needs an explicit user action."""


class ScienceIdempotencyConflict(ScienceOperationalError):
    """A trusted idempotency key was already bound to another operation."""


CLAIM_SUBMISSION_VERSION = "science-claim-submission/0.1.0"


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
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.catalog = catalog
        self.runtime_store = runtime_store
        self.llm_client = llm_client
        self.dictionary_release_id = dictionary_release_id
        self.ontology_release_id = ontology_release_id
        self.ontology_binding_ids = tuple(ontology_binding_ids)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

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

    def _prompt_digest(self) -> str:
        if self.llm_client is None:
            raise ScienceInterpretationUnavailable(
                "Experimental Science LLM adapter is disabled",
                diagnostic_code="adapter_disabled",
            )
        return sha256_digest(
            {
                "prompt_version": PROMPT_VERSION,
                "system_prompt_digest": sha256_digest(
                    ScienceLLMClient._system_prompt()
                ),
                "model_id": self.llm_client.config.model_id,
                "transport_mode": self.llm_client.config.transport_mode,
                "response_format_mode": self.llm_client.config.response_format_mode,
                "reasoning_mode": self.llm_client.config.reasoning_mode,
                "max_attempts": self.llm_client.config.max_attempts,
                "model_settings": self.llm_client.config.safe_model_settings(),
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
    ) -> tuple[
        ClaimPacket,
        list[CandidateMeaningRecord],
        InterpretationDecisionImpact,
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
        return claim, meanings, impact

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
                    offset = position + 1
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

        claim, meanings, impact = self._claim_from_candidate(
            candidate,
            document_text=document_text,
            interpreted_text=interpreted_text,
            document_ref=document_ref,
            document_digest=document_digest,
            selection_start=selection_start,
            ontology_index=self._ontology_index(),
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
                decision_impact=[impact],
                user_revision_history=[],
                confirmed_claim_packet_digest=None,
                response_digest=response_digest,
                operation_binding=operation_binding,
                submission_client_kind=client_kind,
                supersedes_claim_id=supersedes_claim_id,
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
        prompt_digest = self._prompt_digest()
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
            if any(
                alias in interpreted_text
                for alias in candidate["aliases"]
            )
        }
        result = self.llm_client.interpret(
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
        impacts: list[InterpretationDecisionImpact] = []
        for candidate in result.payload.claims:
            claim, candidate_meanings, decision_impact = self._claim_from_candidate(
                candidate,
                document_text=document_text,
                interpreted_text=interpreted_text,
                document_ref=document_ref,
                document_digest=document_digest,
                selection_start=selection_start,
                ontology_index=ontology_index,
            )
            claims.append(claim)
            meanings.extend(candidate_meanings)
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
                model_id=self.llm_client.config.model_id,
                model_settings=self.llm_client.config.safe_model_settings(),
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

    def confirm_interpretation(
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

    def _authoritative_confirmation(
        self, interpretation_id: str
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
    ) -> VerdictPacket:
        interpretation = self._authoritative_confirmation(interpretation_id)
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
        interpretation = self._authoritative_confirmation(interpretation_id)
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
        for claim in confirmed_claims:
            verdict = verify_scientific_claim(claim, operational)
            self._assert_verdict_release_binding(verdict, release_set)
            verdicts.append(verdict)
            annotations.extend(
                self._grounded_annotations(claim.claim_id, verdict, release_set)
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
            "created_at": created_at,
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
        try:
            return self.runtime_store.save_report(report, identity=identity)
        except ImmutableScienceRecordError:
            winner = self._existing_report(report_id, binding)
            if winner is None:
                raise
            return winner
