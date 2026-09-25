"""Deterministic Science source-family expansion planning.

The planner inventories already-migrated Science candidates and partitions them
by their complete authoritative source-family closure.  It does not evaluate,
qualify, promote, create a ReleaseManifest, or mutate an active pointer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Literal, Sequence
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .qualification_contract import (
    QualificationContractError,
    validate_qualification_receipt_payload,
)
from .okf_v02 import validate_boi_profile_v02
from .science_canary import SHA256_RE, ScienceCanaryRunner
from .science_evaluator import (
    CheckApplicability,
    CheckOutcome,
    PrimaryVerdict,
    ScienceCheckInput,
    ScienceEvaluationInput,
    ScienceEvaluator,
)
from ..okf import split_frontmatter


SOURCE_FAMILY_HOSTS = {
    "www.bipm.org": "bipm",
    "physics.nist.gov": "nist",
    "ocw.mit.edu": "mit",
    "feynmanlectures.caltech.edu": "feynman",
}


class ScienceSourceFamilyExpansionError(RuntimeError):
    """The source-family expansion closure is incomplete or unauthorized."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def science_source_family_planner_code_digest() -> str:
    return _bytes_digest(Path(__file__).read_bytes())


def source_family_check_input_digest(
    candidate: "ScienceSourceFamilyCandidate",
    checks: Sequence[ScienceCheckInput],
    check_executor_code_digest: str,
    *,
    executor_resource_ids: Sequence[str] = (),
    evidence_span_ids: Sequence[str] = (),
) -> str:
    return _digest(
        {
            "path": candidate.path,
            "candidate_digest": candidate.candidate_digest,
            "sources_digest": candidate.sources_digest,
            "family_closure": list(candidate.family_closure),
            "check_contract_digest": candidate.check_contract_digest,
            "checks": [
                item.model_dump(mode="json")
                for item in sorted(checks, key=lambda value: value.check_id)
            ],
            "check_executor_code_digest": check_executor_code_digest,
            "executor_resource_ids": sorted(str(item) for item in executor_resource_ids),
            "evidence_span_ids": sorted(str(item) for item in evidence_span_ids),
        }
    )


@dataclass(frozen=True)
class ScienceSourceFamilyCandidate:
    path: str
    candidate_digest: str
    byte_length: int
    boi_id: str
    family_closure: tuple[str, ...]
    sources_digest: str
    science_kind: str
    required_checks: tuple["ScienceRequiredCheck", ...]
    check_contract_digest: str


@dataclass(frozen=True)
class ScienceRequiredCheck:
    check_id: str
    required: bool
    executor_role: Literal["deterministic"]
    rule_digest: str


_COMMON_REQUIRED_CHECK_IDS = (
    "candidate-byte-parity",
    "strict-sci-profile-conformance",
    "source-family-closure",
)
_KIND_REQUIRED_CHECK_IDS = {
    "dictionary": ("dictionary-source-semantic-grounding",),
    "constant": ("constant-source-value-verification",),
    "derivation": ("registered-symbolic-derivation",),
    "formula": (
        "formula-symbol-dimension-verification",
        "formula-source-equation-grounding",
    ),
    "unit": (
        "unit-si-registry-identity",
        "unit-source-definition-grounding",
    ),
}
SCIENCE_CHECK_CONTRACT_VERSION = "boi-science-source-family-required-checks/0.2.0"


def required_science_checks(science_kind: str) -> tuple[ScienceRequiredCheck, ...]:
    """Return the exact substantive check closure for one Science concept kind."""

    kind_checks = _KIND_REQUIRED_CHECK_IDS.get(science_kind)
    if kind_checks is None:
        raise ScienceSourceFamilyExpansionError(
            f"unsupported Science kind for required checks: {science_kind}"
        )
    return tuple(
        ScienceRequiredCheck(
            check_id=check_id,
            required=True,
            executor_role="deterministic",
            rule_digest=_digest(
                {
                    "contract_version": SCIENCE_CHECK_CONTRACT_VERSION,
                    "science_kind": science_kind,
                    "check_id": check_id,
                }
            ),
        )
        for check_id in (*_COMMON_REQUIRED_CHECK_IDS, *kind_checks)
    )


def science_check_contract_digest(
    science_kind: str, required_checks: Sequence[ScienceRequiredCheck]
) -> str:
    return _digest(
        {
            "contract_version": SCIENCE_CHECK_CONTRACT_VERSION,
            "science_kind": science_kind,
            "required_checks": [asdict(item) for item in required_checks],
        }
    )


@dataclass(frozen=True)
class ScienceSourceFamilyShard:
    shard_id: str
    family_closure: tuple[str, ...]
    object_count: int
    candidates: tuple[ScienceSourceFamilyCandidate, ...]
    shard_digest: str


@dataclass(frozen=True)
class ScienceSourceFamilyExpansionPlan:
    schema: str
    status: Literal[
        "WAITING_PARENT_QUALIFICATION", "READY_FOR_SOURCE_FAMILY_EVALUATION"
    ]
    package_digest: str
    snapshot_digest: str
    planner_code_digest: str
    parent_staging_digest: str
    parent_revision_ids: tuple[str, ...]
    parent_qualification_receipt_id: str | None
    parent_qualification_contract_digest: str | None
    excluded_canary_paths: tuple[str, ...]
    total_candidate_count: int
    attention_count: int
    excluded_canary_count: int
    expansion_candidate_count: int
    family_closure_counts: tuple[tuple[str, int], ...]
    shards: tuple[ScienceSourceFamilyShard, ...]
    plan_digest: str
    authorization_digest: str | None = None
    release_manifest_id: None = None
    active_release_transition: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ScienceSourceFamilyCheckBundle(BaseModel):
    """Authenticated deterministic check output for exactly one candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-science-source-family-check-bundle/v2"] = (
        "boi-science-source-family-check-bundle/v2"
    )
    path: str = Field(min_length=1)
    checks: list[ScienceCheckInput]
    coverage_complete: bool
    evidence_complete: bool
    check_executor_code_digest: str
    input_closure_digest: str
    check_execution_run_id: str = Field(min_length=1)
    executor_resource_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def canonical_path(cls, value: str) -> str:
        if value != value.strip() or value.startswith("/") or ".." in Path(value).parts:
            raise ValueError("path must be canonical and relative")
        return value

    @field_validator("check_executor_code_digest", "input_closure_digest")
    @classmethod
    def canonical_digest(cls, value: str) -> str:
        if not SHA256_RE.fullmatch(value):
            raise ValueError("check bundle digests must be canonical sha256")
        return value

    @model_validator(mode="after")
    def unique_checks(self) -> "ScienceSourceFamilyCheckBundle":
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("check bundle IDs must be unique")
        if len(self.executor_resource_ids) != len(set(self.executor_resource_ids)):
            raise ValueError("executor resource IDs must be unique")
        if len(self.evidence_span_ids) != len(set(self.evidence_span_ids)):
            raise ValueError("evidence span IDs must be unique")
        return self


def _check_bundle_digest(bundle: ScienceSourceFamilyCheckBundle) -> str:
    return _digest(bundle.model_dump(mode="json", exclude={"check_execution_run_id"}))


@dataclass(frozen=True)
class ScienceSourceFamilyShardEvaluationReceipt:
    schema: str
    status: Literal["CHECKED", "WITHHELD"]
    plan_digest: str
    authorization_digest: str
    shard_id: str
    shard_digest: str
    candidate_count: int
    verdict_counts: tuple[tuple[str, int], ...]
    result_digest: str
    run_id: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceSourceFamilyExpansionPlanner:
    """Build and parent-authorize a bounded, non-promoting expansion plan."""

    @staticmethod
    def _validate_plan(plan: ScienceSourceFamilyExpansionPlan) -> None:
        if plan.schema != "boi-science-source-family-expansion-plan/v5":
            raise ScienceSourceFamilyExpansionError("source-family plan schema is invalid")
        if plan.planner_code_digest != science_source_family_planner_code_digest():
            raise ScienceSourceFamilyExpansionError("source-family planner code is stale")
        candidates = [candidate for shard in plan.shards for candidate in shard.candidates]
        paths = [candidate.path for candidate in candidates]
        if (
            plan.total_candidate_count != plan.expansion_candidate_count + plan.excluded_canary_count
            or plan.excluded_canary_count != len(plan.excluded_canary_paths)
            or plan.expansion_candidate_count != len(candidates)
            or len(paths) != len(set(paths))
            or set(paths) & set(plan.excluded_canary_paths)
            or any(shard.object_count != len(shard.candidates) or not 1 <= shard.object_count <= 100 for shard in plan.shards)
        ):
            raise ScienceSourceFamilyExpansionError("source-family plan closure is invalid")
        observed_counts = Counter("+".join(candidate.family_closure) for candidate in candidates)
        if tuple(sorted(observed_counts.items())) != plan.family_closure_counts:
            raise ScienceSourceFamilyExpansionError("source-family plan counts are invalid")
        for shard in plan.shards:
            for candidate in shard.candidates:
                expected_checks = required_science_checks(candidate.science_kind)
                if (
                    candidate.required_checks != expected_checks
                    or candidate.check_contract_digest
                    != science_check_contract_digest(candidate.science_kind, expected_checks)
                ):
                    raise ScienceSourceFamilyExpansionError(
                        "source-family required check contract is invalid"
                    )
            values = {
                "family_closure": list(shard.family_closure),
                "candidate_paths": [item.path for item in shard.candidates],
                "candidate_digests": [item.candidate_digest for item in shard.candidates],
                "sources_digests": [item.sources_digest for item in shard.candidates],
                "check_contract_digests": [
                    item.check_contract_digest for item in shard.candidates
                ],
            }
            if shard.shard_digest != _digest(values):
                raise ScienceSourceFamilyExpansionError("source-family shard digest is invalid")
        base = {
            "schema": plan.schema,
            "status": "WAITING_PARENT_QUALIFICATION",
            "package_digest": plan.package_digest,
            "snapshot_digest": plan.snapshot_digest,
            "planner_code_digest": plan.planner_code_digest,
            "parent_staging_digest": plan.parent_staging_digest,
            "parent_revision_ids": list(plan.parent_revision_ids),
            "parent_qualification_receipt_id": None,
            "parent_qualification_contract_digest": None,
            "excluded_canary_paths": list(plan.excluded_canary_paths),
            "total_candidate_count": plan.total_candidate_count,
            "attention_count": plan.attention_count,
            "excluded_canary_count": plan.excluded_canary_count,
            "expansion_candidate_count": plan.expansion_candidate_count,
            "family_closure_counts": list(plan.family_closure_counts),
            "shards": [asdict(shard) for shard in plan.shards],
            "authorization_digest": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        if plan.plan_digest != _digest(base):
            raise ScienceSourceFamilyExpansionError("source-family plan digest is invalid")

    @classmethod
    def build(
        cls,
        *,
        package_path: Path | str,
        canary_paths: Sequence[str],
        parent_staging_digest: str,
        parent_revision_ids: Sequence[str],
        max_objects_per_shard: int = 100,
    ) -> ScienceSourceFamilyExpansionPlan:
        if not SHA256_RE.fullmatch(parent_staging_digest):
            raise ScienceSourceFamilyExpansionError("parent staging digest is invalid")
        if not 1 <= max_objects_per_shard <= 100:
            raise ScienceSourceFamilyExpansionError("shard size must be between 1 and 100")
        excluded = tuple(sorted(str(item).strip() for item in canary_paths))
        if not excluded or any(not item for item in excluded) or len(excluded) != len(set(excluded)):
            raise ScienceSourceFamilyExpansionError("canary paths must be nonempty and unique")
        parent_revisions = tuple(str(item).strip() for item in parent_revision_ids)
        if (
            len(parent_revisions) != len(excluded)
            or len(parent_revisions) != len(set(parent_revisions))
            or any(not item.startswith("KnowledgeRevision:sha256:") for item in parent_revisions)
        ):
            raise ScienceSourceFamilyExpansionError("parent revision closure is invalid")

        root = Path(package_path)
        try:
            manifest = ScienceCanaryRunner._load_manifest(root)
        except (OSError, ValueError, KeyError) as error:
            raise ScienceSourceFamilyExpansionError("candidate package is invalid") from error
        package_digest = str(manifest.get("package_digest") or "")
        snapshot_digest = str(manifest.get("snapshot_digest") or "")
        if not SHA256_RE.fullmatch(package_digest) or not SHA256_RE.fullmatch(snapshot_digest):
            raise ScienceSourceFamilyExpansionError("candidate package digests are invalid")

        candidate_root = (root / "candidate").resolve()
        candidates: list[ScienceSourceFamilyCandidate] = []
        attention_count = 0
        for item in manifest.get("knowledge") or []:
            if not isinstance(item, dict):
                raise ScienceSourceFamilyExpansionError("knowledge inventory entry is invalid")
            if item.get("state") != "candidate":
                attention_count += 1
                continue
            if item.get("error_codes"):
                raise ScienceSourceFamilyExpansionError("candidate has unresolved errors")
            relative = str(item.get("path") or "").strip()
            raw_path = candidate_root / relative
            if not relative or raw_path.is_symlink():
                raise ScienceSourceFamilyExpansionError("candidate path is unsafe")
            path = raw_path.resolve()
            try:
                path.relative_to(candidate_root)
            except ValueError as error:
                raise ScienceSourceFamilyExpansionError("candidate path escapes package") from error
            if not path.is_file():
                raise ScienceSourceFamilyExpansionError("candidate file is missing")
            payload = path.read_bytes()
            candidate_digest = str(item.get("candidate_digest") or "")
            if not SHA256_RE.fullmatch(candidate_digest) or _bytes_digest(payload) != candidate_digest:
                raise ScienceSourceFamilyExpansionError("candidate byte digest mismatch")
            try:
                metadata, _body = split_frontmatter(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as error:
                raise ScienceSourceFamilyExpansionError("candidate frontmatter is invalid") from error
            sources = metadata.get("sources")
            if not isinstance(sources, list) or not sources:
                raise ScienceSourceFamilyExpansionError("candidate sources are missing")
            families: set[str] = set()
            for source in sources:
                if not isinstance(source, dict):
                    raise ScienceSourceFamilyExpansionError("candidate source is invalid")
                resource = str(source.get("resource") or "").strip()
                relation = str(source.get("relation") or "").strip()
                if not resource or not relation:
                    raise ScienceSourceFamilyExpansionError("candidate source closure is incomplete")
                parsed = urlparse(resource)
                family = (
                    SOURCE_FAMILY_HOSTS.get(parsed.netloc.lower())
                    if parsed.scheme == "https"
                    else None
                )
                if family:
                    families.add(family)
            if not families:
                raise ScienceSourceFamilyExpansionError(
                    "candidate has no recognized authoritative source family"
                )
            boi_id = str(metadata.get("boi_id") or "").strip()
            if not boi_id:
                raise ScienceSourceFamilyExpansionError("candidate boi_id is missing")
            science = metadata.get("science")
            science_kind = str(science.get("kind") if isinstance(science, dict) else "").strip()
            required_checks = required_science_checks(science_kind)
            candidates.append(
                ScienceSourceFamilyCandidate(
                    path=relative,
                    candidate_digest=candidate_digest,
                    boi_id=boi_id,
                    byte_length=len(payload),
                    family_closure=tuple(sorted(families)),
                    sources_digest=_digest(sources),
                    science_kind=science_kind,
                    required_checks=required_checks,
                    check_contract_digest=science_check_contract_digest(
                        science_kind, required_checks
                    ),
                )
            )

        by_path = {candidate.path: candidate for candidate in candidates}
        if len(by_path) != len(candidates) or not set(excluded) <= set(by_path):
            raise ScienceSourceFamilyExpansionError("canary closure is not an exact candidate subset")
        remaining = [candidate for candidate in candidates if candidate.path not in set(excluded)]
        grouped: dict[tuple[str, ...], list[ScienceSourceFamilyCandidate]] = {}
        for candidate in remaining:
            grouped.setdefault(candidate.family_closure, []).append(candidate)

        shards: list[ScienceSourceFamilyShard] = []
        family_counts: list[tuple[str, int]] = []
        for closure in sorted(grouped):
            values = sorted(grouped[closure], key=lambda item: item.path)
            closure_name = "+".join(closure)
            family_counts.append((closure_name, len(values)))
            for offset in range(0, len(values), max_objects_per_shard):
                chunk = tuple(values[offset : offset + max_objects_per_shard])
                shard_values = {
                    "family_closure": list(closure),
                    "candidate_paths": [item.path for item in chunk],
                    "candidate_digests": [item.candidate_digest for item in chunk],
                    "sources_digests": [item.sources_digest for item in chunk],
                    "check_contract_digests": [
                        item.check_contract_digest for item in chunk
                    ],
                }
                shard_digest = _digest(shard_values)
                shards.append(
                    ScienceSourceFamilyShard(
                        shard_id=f"science-source-family:{closure_name}:{offset // max_objects_per_shard + 1}",
                        family_closure=closure,
                        object_count=len(chunk),
                        candidates=chunk,
                        shard_digest=shard_digest,
                    )
                )

        plan_values = {
            "schema": "boi-science-source-family-expansion-plan/v5",
            "status": "WAITING_PARENT_QUALIFICATION",
            "package_digest": package_digest,
            "snapshot_digest": snapshot_digest,
            "planner_code_digest": science_source_family_planner_code_digest(),
            "parent_staging_digest": parent_staging_digest,
            "parent_revision_ids": list(parent_revisions),
            "parent_qualification_receipt_id": None,
            "parent_qualification_contract_digest": None,
            "excluded_canary_paths": list(excluded),
            "total_candidate_count": len(candidates),
            "attention_count": attention_count,
            "excluded_canary_count": len(excluded),
            "expansion_candidate_count": len(remaining),
            "family_closure_counts": family_counts,
            "shards": [asdict(shard) for shard in shards],
            "authorization_digest": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        return ScienceSourceFamilyExpansionPlan(
            schema=str(plan_values["schema"]),
            status="WAITING_PARENT_QUALIFICATION",
            package_digest=package_digest,
            snapshot_digest=snapshot_digest,
            planner_code_digest=str(plan_values["planner_code_digest"]),
            parent_staging_digest=parent_staging_digest,
            parent_revision_ids=parent_revisions,
            parent_qualification_receipt_id=None,
            parent_qualification_contract_digest=None,
            excluded_canary_paths=excluded,
            total_candidate_count=len(candidates),
            attention_count=attention_count,
            excluded_canary_count=len(excluded),
            expansion_candidate_count=len(remaining),
            family_closure_counts=tuple(family_counts),
            shards=tuple(shards),
            plan_digest=_digest(plan_values),
        )

    @staticmethod
    def authorize(
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        qualification_receipt_id: str,
        ledger: GovernedRuntimeLedger,
    ) -> ScienceSourceFamilyExpansionPlan:
        ScienceSourceFamilyExpansionPlanner._validate_plan(plan)
        if plan.status != "WAITING_PARENT_QUALIFICATION" or plan.parent_qualification_receipt_id:
            raise ScienceSourceFamilyExpansionError("only a waiting plan can be authorized")
        try:
            receipt = ledger.read(qualification_receipt_id)
        except LedgerError as error:
            raise ScienceSourceFamilyExpansionError("parent qualification receipt is missing") from error
        if receipt.kind is not RecordKind.QUALIFICATION_RECEIPT:
            raise ScienceSourceFamilyExpansionError("parent record is not a qualification receipt")
        try:
            validate_qualification_receipt_payload(receipt.payload)
        except QualificationContractError as error:
            raise ScienceSourceFamilyExpansionError("parent qualification receipt is invalid") from error
        revisions = tuple(str(item) for item in receipt.payload.get("revision_ids") or ())
        if revisions != plan.parent_revision_ids:
            raise ScienceSourceFamilyExpansionError("parent revision closure does not match")
        contract = receipt.payload.get("qualification_contract") or {}
        required = contract.get("required_checks") or []
        if not any(item.get("check_id") == "canary-100-over-48h" for item in required):
            raise ScienceSourceFamilyExpansionError("parent canary evidence is missing")
        contract_digest = str(receipt.payload["qualification_contract_digest"])
        authorization_digest = _digest(
            {
                "plan_digest": plan.plan_digest,
                "parent_qualification_receipt_id": receipt.record_id,
                "parent_qualification_contract_digest": contract_digest,
                "revision_ids": list(revisions),
            }
        )
        return replace(
            plan,
            status="READY_FOR_SOURCE_FAMILY_EVALUATION",
            parent_qualification_receipt_id=receipt.record_id,
            parent_qualification_contract_digest=contract_digest,
            authorization_digest=authorization_digest,
        )


class ScienceSourceFamilyCheckReceiptRecorder:
    """Persist executor-owned check output against an exact v5 check contract.

    This boundary records results produced by deterministic check executors. It
    does not derive outcomes, evaluate a Verdict, or grant qualification.
    """

    @staticmethod
    def _validate_check_closure(
        candidate: ScienceSourceFamilyCandidate,
        checks: Sequence[ScienceCheckInput],
    ) -> None:
        expected = {item.check_id: item for item in candidate.required_checks}
        actual = {item.check_id: item for item in checks}
        if len(actual) != len(checks) or set(actual) != set(expected):
            raise ScienceSourceFamilyExpansionError("required check closure is incomplete or contains extras")
        for check_id, contract in expected.items():
            check = actual[check_id]
            if check.required is not contract.required or check.rule_digest != contract.rule_digest:
                raise ScienceSourceFamilyExpansionError("required check closure does not match its contract")

    @classmethod
    def record(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        checks: Sequence[ScienceCheckInput],
        coverage_complete: bool,
        evidence_complete: bool,
        check_executor_code_digest: str,
        executor_resource_ids: Sequence[str] = (),
        evidence_span_ids: Sequence[str] = (),
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        if plan.status != "READY_FOR_SOURCE_FAMILY_EVALUATION" or not plan.authorization_digest:
            raise ScienceSourceFamilyExpansionError("authorized source-family plan is required")
        ScienceSourceFamilyExpansionPlanner._validate_plan(plan)
        selected = [shard for shard in plan.shards if shard.shard_id == shard_id]
        if len(selected) != 1:
            raise ScienceSourceFamilyExpansionError("exact shard is required")
        candidates = [item for item in selected[0].candidates if item.path == candidate_path]
        if len(candidates) != 1:
            raise ScienceSourceFamilyExpansionError("exact candidate is required")
        candidate = candidates[0]
        if not SHA256_RE.fullmatch(check_executor_code_digest):
            raise ScienceSourceFamilyExpansionError("check executor code digest is invalid")
        cls._validate_check_closure(candidate, checks)
        resources = sorted(str(item) for item in executor_resource_ids)
        for resource_id in resources:
            try:
                resource = ledger.read(resource_id)
            except LedgerError as error:
                raise ScienceSourceFamilyExpansionError("executor resource is missing") from error
            if resource.kind is not RecordKind.SOURCE_ARTIFACT or resource.authority != "intake_service":
                raise ScienceSourceFamilyExpansionError("executor resource authority is invalid")
        spans = sorted(str(item) for item in evidence_span_ids)
        for span_id in spans:
            try:
                span = ledger.read(span_id)
            except LedgerError as error:
                raise ScienceSourceFamilyExpansionError("executor EvidenceSpan is missing") from error
            if span.kind is not RecordKind.EVIDENCE_SPAN or span.authority not in {
                "intake_service",
                "evidence_service",
            }:
                raise ScienceSourceFamilyExpansionError("executor EvidenceSpan authority is invalid")
            if str(span.payload.get("source_artifact_id") or "") not in resources:
                raise ScienceSourceFamilyExpansionError("executor EvidenceSpan source is outside resource closure")
        input_closure_digest = source_family_check_input_digest(
            candidate,
            checks,
            check_executor_code_digest,
            executor_resource_ids=resources,
            evidence_span_ids=spans,
        )
        provisional = ScienceSourceFamilyCheckBundle(
            path=candidate.path,
            checks=list(checks),
            coverage_complete=coverage_complete,
            evidence_complete=evidence_complete,
            check_executor_code_digest=check_executor_code_digest,
            input_closure_digest=input_closure_digest,
            check_execution_run_id="pending",
            executor_resource_ids=resources,
            evidence_span_ids=spans,
        )
        bundle_digest = _check_bundle_digest(provisional)
        run = ledger.append(
            RecordKind.RUN,
            {
                "schema": "boi-science-source-family-check-execution/v2",
                "scope": "science-source-family-check-execution",
                "status": "RECORDED",
                "plan_digest": plan.plan_digest,
                "authorization_digest": plan.authorization_digest,
                "shard_id": selected[0].shard_id,
                "shard_digest": selected[0].shard_digest,
                "candidate_path": candidate.path,
                "candidate_digest": candidate.candidate_digest,
                "science_kind": candidate.science_kind,
                "check_contract_digest": candidate.check_contract_digest,
                "input_closure_digest": input_closure_digest,
                "check_executor_code_digest": check_executor_code_digest,
                "executor_resource_ids": resources,
                "evidence_span_ids": spans,
                "bundle_digest": bundle_digest,
                "checks": [item.model_dump(mode="json") for item in checks],
                "coverage_complete": coverage_complete,
                "evidence_complete": evidence_complete,
                "qualification": False,
                "release_authority": False,
                "active_release_transition": False,
            },
            authority="executor",
            occurred_at=occurred_at,
        )
        return provisional.model_copy(update={"check_execution_run_id": run.record_id})


class ScienceSourceFamilyDeterministicCheckRunner:
    """Run safe candidate-local checks and explicitly withhold unavailable checks."""

    @classmethod
    def run_preflight(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        candidate_path: str,
        package_path: Path | str,
        ledger: GovernedRuntimeLedger,
        occurred_at: str,
    ) -> ScienceSourceFamilyCheckBundle:
        selected = [shard for shard in plan.shards if shard.shard_id == shard_id]
        if len(selected) != 1:
            raise ScienceSourceFamilyExpansionError("exact shard is required")
        matches = [item for item in selected[0].candidates if item.path == candidate_path]
        if len(matches) != 1:
            raise ScienceSourceFamilyExpansionError("exact candidate is required")
        candidate = matches[0]
        root = Path(package_path).resolve()
        candidate_root = (root / "candidate").resolve()
        raw = candidate_root / candidate.path
        if raw.is_symlink():
            raise ScienceSourceFamilyExpansionError("candidate path is unsafe")
        path = raw.resolve()
        try:
            path.relative_to(candidate_root)
        except ValueError as error:
            raise ScienceSourceFamilyExpansionError("candidate path escapes package") from error
        if not path.is_file():
            raise ScienceSourceFamilyExpansionError("candidate file is missing")
        payload = path.read_bytes()
        byte_ok = _bytes_digest(payload) == candidate.candidate_digest and len(payload) == candidate.byte_length
        try:
            metadata, _body = split_frontmatter(payload.decode("utf-8"))
            validation = validate_boi_profile_v02(metadata)
            profile_ok = validation.ok and metadata.get("profiles") == ["boi/sci@0.7.0"]
            sources = metadata.get("sources")
            families = {
                SOURCE_FAMILY_HOSTS.get(urlparse(str(source.get("resource") or "")).netloc.lower())
                for source in sources
                if isinstance(source, dict)
            } if isinstance(sources, list) else set()
            families.discard(None)
            source_ok = (
                isinstance(sources, list)
                and bool(sources)
                and _digest(sources) == candidate.sources_digest
                and tuple(sorted(families)) == candidate.family_closure
            )
            profile_evidence = {
                "validation_error_codes": [issue.code for issue in validation.errors],
                "profiles": metadata.get("profiles"),
                "science_kind": (metadata.get("science") or {}).get("kind")
                if isinstance(metadata.get("science"), dict)
                else None,
            }
        except (UnicodeDecodeError, ValueError):
            profile_ok = False
            source_ok = False
            profile_evidence = {"validation_error_codes": ["CANDIDATE_PARSE_FAILED"]}

        observed = {
            "candidate-byte-parity": (byte_ok, {"candidate_digest": _bytes_digest(payload), "byte_length": len(payload)}),
            "strict-sci-profile-conformance": (profile_ok, profile_evidence),
            "source-family-closure": (
                source_ok,
                {
                    "sources_digest": candidate.sources_digest,
                    "family_closure": list(candidate.family_closure),
                },
            ),
        }
        checks: list[ScienceCheckInput] = []
        for contract in candidate.required_checks:
            if contract.check_id in observed:
                passed, evidence = observed[contract.check_id]
                outcome = CheckOutcome.PASS if passed else CheckOutcome.FAIL
            else:
                outcome = CheckOutcome.NOT_RUN
                evidence = {
                    "reason_code": "SUBSTANTIVE_EXECUTOR_NOT_REGISTERED",
                    "check_id": contract.check_id,
                }
            checks.append(
                ScienceCheckInput(
                    check_id=contract.check_id,
                    outcome=outcome,
                    applicability=CheckApplicability.IN_SCOPE,
                    required=contract.required,
                    rule_digest=contract.rule_digest,
                    evidence_digest=_digest(evidence),
                )
            )
        return ScienceSourceFamilyCheckReceiptRecorder.record(
            plan,
            shard_id=shard_id,
            candidate_path=candidate.path,
            checks=checks,
            coverage_complete=all(item.outcome is not CheckOutcome.NOT_RUN for item in checks),
            evidence_complete=True,
            check_executor_code_digest=science_source_family_planner_code_digest(),
            ledger=ledger,
            occurred_at=occurred_at,
        )


class ScienceSourceFamilyShardEvaluator:
    """Persist exact shard checks and Verdicts without qualification authority."""

    @staticmethod
    def _source_artifact(
        plan: ScienceSourceFamilyExpansionPlan,
        ledger: GovernedRuntimeLedger,
    ):
        root = ledger.records_root / RecordKind.SOURCE_ARTIFACT.value
        matches = []
        for path in sorted(root.glob("*.json")) if root.exists() else ():
            try:
                record = ledger.read(f"{RecordKind.SOURCE_ARTIFACT.value}:sha256:{path.stem}")
            except LedgerError as error:
                raise ScienceSourceFamilyExpansionError("SourceArtifact ledger is invalid") from error
            if (
                record.authority == "intake_service"
                and record.payload.get("package_digest") == plan.package_digest
                and record.payload.get("content_digest") == plan.snapshot_digest
            ):
                matches.append(record)
        if len(matches) != 1:
            raise ScienceSourceFamilyExpansionError("exact package SourceArtifact is required")
        return matches[0]

    @classmethod
    def evaluate(
        cls,
        plan: ScienceSourceFamilyExpansionPlan,
        *,
        shard_id: str,
        bundles: Sequence[ScienceSourceFamilyCheckBundle],
        ledger: GovernedRuntimeLedger,
    ) -> ScienceSourceFamilyShardEvaluationReceipt:
        if (
            plan.status != "READY_FOR_SOURCE_FAMILY_EVALUATION"
            or not plan.authorization_digest
            or not plan.parent_qualification_receipt_id
        ):
            raise ScienceSourceFamilyExpansionError("authorized source-family plan is required")
        ScienceSourceFamilyExpansionPlanner._validate_plan(plan)
        selected = [shard for shard in plan.shards if shard.shard_id == shard_id]
        if len(selected) != 1:
            raise ScienceSourceFamilyExpansionError("exact shard is required")
        shard = selected[0]
        by_path = {bundle.path: bundle for bundle in bundles}
        expected_paths = {candidate.path for candidate in shard.candidates}
        if len(by_path) != len(bundles) or set(by_path) != expected_paths:
            raise ScienceSourceFamilyExpansionError("check bundle closure is incomplete or contains extras")
        try:
            parent = ledger.read(plan.parent_qualification_receipt_id)
            validate_qualification_receipt_payload(parent.payload)
        except (LedgerError, QualificationContractError) as error:
            raise ScienceSourceFamilyExpansionError("parent qualification receipt is invalid") from error
        if parent.authority != "qualification_service":
            raise ScienceSourceFamilyExpansionError("parent qualification authority is invalid")
        parent_revisions = tuple(str(item) for item in parent.payload.get("revision_ids") or ())
        parent_contract_digest = str(parent.payload.get("qualification_contract_digest") or "")
        if (
            parent_revisions != plan.parent_revision_ids
            or parent_contract_digest != plan.parent_qualification_contract_digest
            or plan.authorization_digest
            != _digest(
                {
                    "plan_digest": plan.plan_digest,
                    "parent_qualification_receipt_id": parent.record_id,
                    "parent_qualification_contract_digest": parent_contract_digest,
                    "revision_ids": list(parent_revisions),
                }
            )
        ):
            raise ScienceSourceFamilyExpansionError("source-family authorization digest is invalid")
        source = cls._source_artifact(plan, ledger)
        occurred_at = parent.occurred_at

        result_rows: list[dict[str, object]] = []
        verdict_counts: Counter[str] = Counter()
        all_checked = True
        for candidate in sorted(shard.candidates, key=lambda item: item.path):
            bundle = by_path[candidate.path]
            ScienceSourceFamilyCheckReceiptRecorder._validate_check_closure(
                candidate, bundle.checks
            )
            if bundle.input_closure_digest != source_family_check_input_digest(
                candidate,
                bundle.checks,
                bundle.check_executor_code_digest,
                executor_resource_ids=bundle.executor_resource_ids,
                evidence_span_ids=bundle.evidence_span_ids,
            ):
                raise ScienceSourceFamilyExpansionError("check input closure digest is invalid")
            try:
                execution = ledger.read(bundle.check_execution_run_id)
            except LedgerError as error:
                raise ScienceSourceFamilyExpansionError("check execution receipt is missing") from error
            expected_execution = {
                "schema": "boi-science-source-family-check-execution/v2",
                "scope": "science-source-family-check-execution",
                "status": "RECORDED",
                "plan_digest": plan.plan_digest,
                "authorization_digest": plan.authorization_digest,
                "shard_id": shard.shard_id,
                "shard_digest": shard.shard_digest,
                "candidate_path": candidate.path,
                "candidate_digest": candidate.candidate_digest,
                "science_kind": candidate.science_kind,
                "check_contract_digest": candidate.check_contract_digest,
                "input_closure_digest": bundle.input_closure_digest,
                "check_executor_code_digest": bundle.check_executor_code_digest,
                "executor_resource_ids": bundle.executor_resource_ids,
                "evidence_span_ids": bundle.evidence_span_ids,
                "bundle_digest": _check_bundle_digest(bundle),
                "checks": [item.model_dump(mode="json") for item in bundle.checks],
                "coverage_complete": bundle.coverage_complete,
                "evidence_complete": bundle.evidence_complete,
                "qualification": False,
                "release_authority": False,
                "active_release_transition": False,
            }
            if (
                execution.kind is not RecordKind.RUN
                or execution.authority != "executor"
                or execution.payload != expected_execution
            ):
                raise ScienceSourceFamilyExpansionError("check execution receipt is invalid")
            span = ledger.append(
                RecordKind.EVIDENCE_SPAN,
                {
                    "source_artifact_id": source.record_id,
                    "locator": f"candidate/{candidate.path}",
                    "content_digest": candidate.candidate_digest,
                    "byte_start": 0,
                    "byte_end": candidate.byte_length,
                    "sources_digest": candidate.sources_digest,
                    "source_family_closure": list(candidate.family_closure),
                },
                authority="evidence_service",
                occurred_at=occurred_at,
            )
            revision = ledger.append(
                RecordKind.KNOWLEDGE_REVISION,
                {
                    "status": "candidate",
                    "boi_id": candidate.boi_id,
                    "source_ids": [source.record_id],
                    "evidence_span_ids": [span.record_id],
                    "document_digest": candidate.candidate_digest,
                    "package_digest": plan.package_digest,
                    "path_digest": _digest(candidate.path),
                    "source_family_closure": list(candidate.family_closure),
                    "source_family_plan_digest": plan.plan_digest,
                    "source_family_authorization_digest": plan.authorization_digest,
                },
                authority="migration_service",
                occurred_at=occurred_at,
            )
            evaluation = ScienceEvaluationInput(
                knowledge_revision_id=revision.record_id,
                checks=bundle.checks,
                coverage_complete=bundle.coverage_complete,
                evidence_complete=bundle.evidence_complete,
                historical_labels=[],
            )
            result, verdict = ScienceEvaluator.evaluate_to_ledger(
                evaluation,
                ledger=ledger,
                occurred_at=occurred_at,
            )
            required_complete = all(
                not check.required or check.outcome is CheckOutcome.PASS
                for check in bundle.checks
            )
            checked = (
                result.verdict is PrimaryVerdict.CONSISTENT
                and bundle.coverage_complete
                and bundle.evidence_complete
                and required_complete
            )
            all_checked = all_checked and checked
            verdict_counts[result.verdict.value] += 1
            result_rows.append(
                {
                    "path": candidate.path,
                    "revision_id": revision.record_id,
                    "verdict_id": verdict.record_id,
                    "verdict": result.verdict.value,
                    "result_digest": result.result_digest,
                    "check_executor_code_digest": bundle.check_executor_code_digest,
                    "input_closure_digest": bundle.input_closure_digest,
                    "checked": checked,
                }
            )
        status: Literal["CHECKED", "WITHHELD"] = "CHECKED" if all_checked else "WITHHELD"
        result_digest = _digest(result_rows)
        run = ledger.append(
            RecordKind.RUN,
            {
                "scope": "science-source-family-shard-evaluation",
                "status": status,
                "plan_digest": plan.plan_digest,
                "authorization_digest": plan.authorization_digest,
                "shard_id": shard.shard_id,
                "shard_digest": shard.shard_digest,
                "candidate_count": len(result_rows),
                "verdict_counts": dict(sorted(verdict_counts.items())),
                "result_digest": result_digest,
                "results": result_rows,
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
            authority="science_evaluator",
            occurred_at=occurred_at,
        )
        return ScienceSourceFamilyShardEvaluationReceipt(
            schema="boi-science-source-family-shard-evaluation/v2",
            status=status,
            plan_digest=plan.plan_digest,
            authorization_digest=plan.authorization_digest,
            shard_id=shard.shard_id,
            shard_digest=shard.shard_digest,
            candidate_count=len(result_rows),
            verdict_counts=tuple(sorted(verdict_counts.items())),
            result_digest=result_digest,
            run_id=run.record_id,
        )
