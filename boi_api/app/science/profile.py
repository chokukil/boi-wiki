"""Validation for the additive Science profile carried by OKF documents."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse


SCIENCE_TYPE_REQUIREMENTS = {
    "boi/science-source": {"source_id", "source_role", "original_url", "content_hash"},
    "boi/science-evidence": {
        "evidence_id",
        "source_id",
        "locator",
        "original_text",
        "original_text_hash",
        "reviewed_translation",
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
