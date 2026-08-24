"""Validation for the additive Science profile carried by OKF documents."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from boi_api.app.science.digests import sha256_digest


SCIENCE_TYPE_REQUIREMENTS = {
    "boi/science-source": {"source_id", "source_role", "original_url", "content_hash"},
    "boi/science-evidence": {
        "evidence_id",
        "source_id",
        "locator",
        "original_text",
        "original_text_hash",
        "reviewed_translation",
        "claim_scope",
        "claim_scope_hash",
    },
    "boi/science-knowledge": {
        "knowledge_id",
        "pack_id",
        "knowledge_kind",
        "assurance_basis",
        "statement",
        "assumptions",
        "applicability",
        "limitations",
        "evidence_refs",
    },
    "boi/science-rule": {
        "rule_id",
        "pack_id",
        "rule_kind",
        "inputs",
        "outcomes",
        "knowledge_refs",
        "evidence_refs",
        "evidence_uses",
    },
    "boi/science-pack": {
        "pack_id",
        "version",
        "dependencies",
        "knowledge_refs",
        "rule_refs",
        "qualification_refs",
    },
    "boi/science-ontology-binding": {
        "binding_id",
        "ontology_release_id",
        "concept_id",
        "aliases",
        "meaning",
        "domain",
    },
    "boi/science-qualification-matrix": {"matrix_id", "rule_id", "cases", "release_refs"},
    "boi/science-release": {
        "release_id",
        "schema_version",
        "content_hash",
        "status",
        "component_digests",
        "known_limitations",
        "components",
        "qualification_report",
    },
}

KNOWLEDGE_KINDS = {
    "definition",
    "invariant",
    "law",
    "mechanism",
    "model",
    "conditional_relation",
    "qualified_rule",
    "observation",
    "measurement",
}

ASSURANCE_BASES = {
    "formal_theorem",
    "physical_law",
    "derived_model",
    "empirical_correlation",
    "vendor_process_rule",
    "internal_qualified_rule",
    "hypothesis",
}

PACK_RELATIONS = {
    "depends_on",
    "uses",
    "specializes",
    "adds_evidence",
    "validated_by",
    "supersedes",
}

_CLAIM_SCOPE_FIELDS = {
    "schema_version",
    "allowed_claims",
    "forbidden_claim_families",
    "limitations",
}
_ALLOWED_CLAIM_FIELDS = {
    "claim_family",
    "purpose",
    "required_conditions",
}
_EVIDENCE_USE_FIELDS = {
    "evidence_ref",
    "claim_family",
    "purpose",
    "required_conditions",
}


def is_science_document(metadata: dict[str, Any]) -> bool:
    """Return whether metadata declares a supported stored Science object."""
    return metadata.get("type") in SCIENCE_TYPE_REQUIREMENTS


def _validate_reference_collection(value: Any, field_name: str) -> tuple[set[str], list[str]]:
    if not isinstance(value, list):
        return set(), [f"{field_name} must be a list"]

    refs: set[str] = set()
    errors: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            refs.add(item)
        elif isinstance(item, Mapping):
            ref = item.get("ref")
            if isinstance(ref, str) and ref.strip():
                refs.add(ref)
            else:
                errors.append(f"{field_name} items must be nonempty strings or mappings with ref")
        else:
            errors.append(f"{field_name} items must be nonempty strings or mappings with ref")
    return refs, errors


def _nonempty_string_list(value: Any, field_name: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, list):
        return [], [f"{field_name} must be a list"]
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return [], [f"{field_name} items must be nonempty strings"]
    if len(value) != len(set(value)):
        return [], [f"{field_name} items must be unique"]
    return value, []


def _validate_claim_scope(science: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    scope = science.get("claim_scope")
    if not isinstance(scope, Mapping):
        return ["science.claim_scope must be an object"]
    if set(scope) != _CLAIM_SCOPE_FIELDS:
        errors.append("science.claim_scope has unsupported fields")
    if scope.get("schema_version") != "0.1":
        errors.append("science.claim_scope.schema_version must be exactly string '0.1'")

    allowed = scope.get("allowed_claims")
    allowed_families: list[str] = []
    if not isinstance(allowed, list):
        errors.append("science.claim_scope.allowed_claims must be a list")
    else:
        for claim in allowed:
            if not isinstance(claim, Mapping):
                errors.append("science.claim_scope.allowed_claims items must be objects")
                continue
            if set(claim) != _ALLOWED_CLAIM_FIELDS:
                errors.append("science.claim_scope.allowed_claims items have unsupported fields")
            family = claim.get("claim_family")
            purpose = claim.get("purpose")
            if not isinstance(family, str) or not family.strip():
                errors.append(
                    "science.claim_scope.allowed_claims claim_family must be a nonempty string"
                )
            else:
                allowed_families.append(family)
            if not isinstance(purpose, str) or not purpose.strip():
                errors.append(
                    "science.claim_scope.allowed_claims purpose must be a nonempty string"
                )
            _conditions, condition_errors = _nonempty_string_list(
                claim.get("required_conditions"),
                "science.claim_scope.allowed_claims required_conditions",
            )
            errors.extend(condition_errors)
    if len(allowed_families) != len(set(allowed_families)):
        errors.append("science.claim_scope.allowed_claims claim_family must be unique")

    forbidden, forbidden_errors = _nonempty_string_list(
        scope.get("forbidden_claim_families"),
        "science.claim_scope.forbidden_claim_families",
    )
    errors.extend(forbidden_errors)
    _limitations, limitation_errors = _nonempty_string_list(
        scope.get("limitations"), "science.claim_scope.limitations"
    )
    errors.extend(limitation_errors)
    if set(allowed_families) & set(forbidden):
        errors.append("science.claim_scope cannot both allow and forbid the same claim family")

    claim_scope_hash = science.get("claim_scope_hash")
    if not isinstance(claim_scope_hash, str):
        errors.append("science.claim_scope_hash must be a string")
    elif claim_scope_hash != sha256_digest(scope):
        errors.append("science.claim_scope_hash must match science.claim_scope")
    return errors


def _validate_evidence_uses(science: Mapping[str, Any]) -> list[str]:
    uses = science.get("evidence_uses")
    if not isinstance(uses, list) or not uses:
        return ["science.evidence_uses must be a nonempty list"]
    errors: list[str] = []
    raw_evidence_refs = science.get("evidence_refs")
    if isinstance(raw_evidence_refs, list):
        normalized_refs = [
            item if isinstance(item, str) else item.get("ref")
            for item in raw_evidence_refs
            if isinstance(item, (str, Mapping))
        ]
        if len(normalized_refs) != len(set(normalized_refs)):
            errors.append("science.evidence_refs must be unique")
    use_refs: list[str] = []
    for use in uses:
        if not isinstance(use, Mapping):
            errors.append("science.evidence_uses items must be objects")
            continue
        if set(use) != _EVIDENCE_USE_FIELDS:
            errors.append("science.evidence_uses items have unsupported fields")
        for field_name in ("evidence_ref", "claim_family", "purpose"):
            value = use.get(field_name)
            if not isinstance(value, str) or not value.strip():
                errors.append(
                    f"science.evidence_uses {field_name} must be a nonempty string"
                )
        ref = use.get("evidence_ref")
        if isinstance(ref, str) and ref.strip():
            use_refs.append(ref)
        _conditions, condition_errors = _nonempty_string_list(
            use.get("required_conditions"),
            "science.evidence_uses required_conditions",
        )
        errors.extend(condition_errors)
    evidence_refs, ref_errors = _validate_reference_collection(
        science.get("evidence_refs"), "science.evidence_refs"
    )
    if not ref_errors and set(use_refs) != evidence_refs:
        errors.append("science.evidence_uses must exactly match science.evidence_refs")
    if len(use_refs) != len(set(use_refs)):
        errors.append("science.evidence_uses must bind each Evidence exactly once")
    return errors


def validate_sci_profile_metadata(metadata: dict[str, Any]) -> list[str]:
    """Validate only recognized Science documents, preserving normal OKF behavior."""
    if not is_science_document(metadata):
        return []

    errors: list[str] = []
    if metadata.get("sci_profile_version") != "0.1" or not isinstance(
        metadata.get("sci_profile_version"), str
    ):
        errors.append("sci_profile_version must be exactly string '0.1'")

    science = metadata.get("science")
    if not isinstance(science, Mapping):
        return errors + ["science is required"]

    for field_name in sorted(SCIENCE_TYPE_REQUIREMENTS[metadata["type"]]):
        if science.get(field_name) in (None, ""):
            errors.append(f"science.{field_name} is required")

    if "confidence" in science:
        errors.append("science.confidence is forbidden")

    if metadata["type"] == "boi/science-knowledge":
        if science.get("knowledge_kind") not in KNOWLEDGE_KINDS:
            errors.append("science.knowledge_kind is invalid")
        if science.get("assurance_basis") not in ASSURANCE_BASES:
            errors.append("science.assurance_basis is invalid")

    if metadata["type"] == "boi/science-source" and metadata.get("visibility") == "public":
        original_url = science.get("original_url")
        parsed_url = urlparse(original_url) if isinstance(original_url, str) else None
        if parsed_url is None or parsed_url.scheme != "https" or not parsed_url.netloc:
            errors.append("science.original_url must use HTTPS for public sources")

    if metadata["type"] == "boi/science-evidence":
        original_text = science.get("original_text")
        original_text_hash = science.get("original_text_hash")
        if not isinstance(original_text, str):
            errors.append("science.original_text must be a string")
        if not isinstance(original_text_hash, str):
            errors.append("science.original_text_hash must be a string")
        if isinstance(original_text, str) and isinstance(original_text_hash, str):
            expected_hash = "sha256:" + hashlib.sha256(original_text.encode("utf-8")).hexdigest()
            if original_text_hash != expected_hash:
                errors.append("science.original_text_hash must match original_text UTF-8 SHA-256")
        errors.extend(_validate_claim_scope(science))

    if metadata["type"] == "boi/science-pack":
        dependencies = science.get("dependencies")
        if not isinstance(dependencies, list):
            errors.append("science.dependencies must be a list")
        else:
            for dependency in dependencies:
                if not isinstance(dependency, Mapping):
                    errors.append("science.dependencies items must be typed relationship edges")
                    continue
                if not set(dependency) <= {"relation", "ref"}:
                    errors.append("science.dependencies items must be typed relationship edges")
                    continue
                relation = dependency.get("relation")
                if relation is None:
                    errors.append("science.dependencies relation is required")
                elif relation not in PACK_RELATIONS:
                    errors.append("science.dependencies relation is invalid")
                ref = dependency.get("ref")
                if (
                    not isinstance(ref, str)
                    or not ref.startswith("sci-pack:")
                    or not ref.removeprefix("sci-pack:").strip()
                    or any(character.isspace() for character in ref)
                ):
                    errors.append("science.dependencies ref is invalid")

    if metadata["type"] == "boi/science-rule" and "evidence_uses" in science:
        errors.extend(_validate_evidence_uses(science))

    if "evidence_refs" in science:
        science_refs, science_ref_errors = _validate_reference_collection(
            science["evidence_refs"], "science.evidence_refs"
        )
        source_refs, source_ref_errors = _validate_reference_collection(metadata.get("source_refs"), "source_refs")
        errors.extend(science_ref_errors)
        errors.extend(source_ref_errors)
        if not science_ref_errors and not source_ref_errors and source_refs != science_refs:
            errors.append("science.evidence_refs must match OKF source_refs")

    return errors
