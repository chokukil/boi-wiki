"""Application orchestration around interpretation and deterministic verification."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable

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
    ClaimInterpretation,
    ClaimPacket,
    InterpretationRecord,
    ReleaseSelection,
    ResolvedReleaseSet,
    SourceSpan,
    VerificationReport,
    VerdictPacket,
)
from boi_api.app.science.operational import OperationalVerification


class ScienceService:
    """Keep untrusted language interpretation outside the verdict boundary."""

    def __init__(
        self,
        *,
        catalog: Any,
        runtime_store: Any,
        llm_client: ScienceLLMClient,
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
            meaning = getattr(binding, "meaning", None)
            aliases = getattr(binding, "aliases", None)
            domain = getattr(binding, "domain", None)
            if (
                not isinstance(concept_id, str)
                or not concept_id
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
    ) -> tuple[ClaimPacket, list[dict[str, object]], list[dict[str, object]]]:
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
        unknown_refs = (supplied_refs | meaning_refs) - set(ontology_index)
        if unknown_refs:
            raise ScienceInterpretationUnavailable(
                "LLM returned an ontology reference outside the pinned index"
            )
        known_concepts = {str(item["concept_id"]) for item in ontology_index.values()}
        normalized = candidate.normalized_claim
        if {
            normalized.subject_concept_id,
            normalized.object_concept_id,
        } - known_concepts:
            raise ScienceInterpretationUnavailable(
                "LLM returned a concept outside the pinned ontology index"
            )

        decisive_ambiguities = sorted(
            impact.ambiguity_id
            for impact in candidate.decision_impact
            if impact.changes_outcome
        )
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
                ontology_refs=sorted(supplied_refs | meaning_refs),
                ambiguity_ids=decisive_ambiguities,
                user_confirmed=not decisive_ambiguities,
            ),
        )
        meanings = []
        for meaning in candidate.candidate_meanings:
            if meaning.surface_term not in resolved.exact:
                raise ScienceInterpretationUnavailable(
                    "ontology candidate term is not anchored in the claim text"
                )
            canonical = ontology_index[meaning.ontology_ref]
            meanings.append(
                {
                    "claim_id": claim_id,
                    "ambiguity_id": meaning.ambiguity_id,
                    "surface_term": meaning.surface_term,
                    "ontology_ref": meaning.ontology_ref,
                    "concept_id": canonical["concept_id"],
                    "meaning": canonical["meaning"],
                    "domain": canonical["domain"],
                }
            )
        impacts = [
            {"claim_id": claim_id, **impact.model_dump(mode="json")}
            for impact in candidate.decision_impact
        ]
        return claim, meanings, impacts

    def interpret_document(
        self,
        document_text: str,
        *,
        document_ref: str,
        identity: AuthIdentity,
        selection_anchor: SourceSpan | None = None,
        user_revision_history: Sequence[Mapping[str, object]] = (),
    ) -> InterpretationRecord:
        if not document_text:
            raise ScienceInterpretationUnavailable("document text must be nonempty")
        document_digest = sha256_digest(document_text)
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

        ontology_index = self._ontology_index()
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
        meanings: list[dict[str, object]] = []
        impacts: list[dict[str, object]] = []
        for candidate in result.payload.claims:
            claim, candidate_meanings, decision_impacts = self._claim_from_candidate(
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
            impacts.extend(decision_impacts)
        claim_ids = [claim.claim_id for claim in claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ScienceInterpretationUnavailable(
                "LLM returned duplicate scientific claim candidates"
            )

        confirmed_claims = [
            claim for claim in claims if claim.interpretation.user_confirmed
        ]
        confirmed_digest = self._confirmed_claims_digest(confirmed_claims)
        record = InterpretationRecord(
            interpretation_id=f"sci-interpretation:{uuid.uuid4()}",
            document_digest=document_digest,
            candidate_claims=claims,
            model_id=self.llm_client.config.model_id,
            model_settings=self.llm_client.config.safe_model_settings(),
            prompt_version=PROMPT_VERSION,
            dictionary_release_id=self.dictionary_release_id,
            ontology_release_id=self.ontology_release_id,
            ontology_refs=sorted(
                {ref for claim in claims for ref in claim.interpretation.ontology_refs}
            ),
            candidate_meanings=meanings,
            decision_impact=impacts,
            user_revision_history=deepcopy(list(user_revision_history)),
            confirmed_claim_packet_digest=confirmed_digest,
            response_digest=response_digest,
        )
        return self.runtime_store.save_interpretation(record, identity=identity)

    @staticmethod
    def _confirmed_claims_digest(claims: Sequence[ClaimPacket]) -> str | None:
        if not claims:
            return None
        if len(claims) == 1:
            return sha256_digest(claims[0])
        return sha256_digest({"claim_packets": list(claims)})

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
    ) -> dict[str, object]:
        evidence = self._pinned_object(
            release_set,
            ref=evidence_ref,
            kind="evidence",
        )
        source_id = getattr(evidence, "source_id", None)
        locator = getattr(evidence, "locator", None)
        if not isinstance(source_id, str) or not isinstance(locator, Mapping):
            raise ScienceOperationalError(
                f"grounded Evidence has no source locator: {evidence_ref}"
            )
        source = self._pinned_object(
            release_set,
            ref=source_id,
            kind="source",
        )
        url = getattr(source, "original_url", None)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ScienceOperationalError(
                f"grounded Evidence has no approved source link: {evidence_ref}"
            )
        return {
            "evidence_id": evidence_ref,
            "source_id": source_id,
            "url": url,
            "locator": deepcopy(dict(locator)),
        }

    def _grounded_annotations(
        self,
        claim_id: str,
        verdict: VerdictPacket,
        release_set: ResolvedReleaseSet,
    ) -> list[dict[str, object]]:
        annotations: list[dict[str, object]] = []
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
                    {
                        "claim_id": claim_id,
                        "fact_id": fact.fact_id,
                        "text": statement,
                        "knowledge_refs": [knowledge_ref],
                        "evidence_links": [
                            self._evidence_link(release_set, evidence_ref)
                            for evidence_ref in sentence_evidence
                        ],
                    }
                )
            if mapped_evidence != allowed_evidence:
                raise ScienceOperationalError(
                    f"decisive Explanation Fact has unmapped Evidence: {fact.fact_id}"
                )
        return annotations

    def verify_claim(
        self,
        claim: ClaimPacket,
        selection: ReleaseSelection,
    ) -> VerdictPacket:
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
    ) -> VerificationReport:
        interpretation = self.runtime_store.load_interpretation(interpretation_id)
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
        release_set, operational = self._operational_verification(selection)

        verdicts: list[VerdictPacket] = []
        unresolved: list[dict[str, object]] = []
        annotations: list[dict[str, object]] = []
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
        for claim in interpretation.candidate_claims:
            if (
                claim.interpretation.ambiguity_ids
                or not claim.interpretation.user_confirmed
            ):
                unresolved.append(
                    {
                        "claim_id": claim.claim_id,
                        "ambiguity_ids": list(claim.interpretation.ambiguity_ids),
                        "decision_impact": [
                            deepcopy(impact)
                            for impact in interpretation.decision_impact
                            if impact.get("claim_id") == claim.claim_id
                        ],
                    }
                )
                continue
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
            "report_id": f"sci-report:{uuid.uuid4()}",
            "document_ref": interpretation.candidate_claims[0].document_ref,
            "document_digest": interpretation.document_digest,
            "release_selection": selection,
            "release_digests": release_set.release_digests,
            "interpretation_ids": [interpretation.interpretation_id],
            "verdict_packets": verdicts,
            "unresolved_ambiguities": unresolved,
            "annotations": annotations,
            "created_at": created_at,
            "created_by": identity.employee_id,
        }
        report = VerificationReport(**payload, report_digest="sha256:pending")
        report = report.model_copy(
            update={
                "report_digest": sha256_digest(
                    report.model_dump(mode="json", exclude={"report_digest"})
                )
            },
            deep=True,
        )
        return self.runtime_store.save_report(report, identity=identity)
