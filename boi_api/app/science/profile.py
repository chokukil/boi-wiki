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


def is_science_document(metadata: dict[str, Any]) -> bool:
    """Return whether metadata declares a supported stored Science object."""
    return metadata.get("type") in SCIENCE_TYPE_REQUIREMENTS


def _reference_values(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    refs: set[str] = set()
    for item in value:
        if isinstance(item, str) and item:
            refs.add(item)
        elif isinstance(item, Mapping):
            ref = item.get("ref")
            if isinstance(ref, str) and ref:
                refs.add(ref)
    return refs


def validate_sci_profile_metadata(metadata: dict[str, Any]) -> list[str]:
    """Validate only recognized Science documents, preserving normal OKF behavior."""
    if not is_science_document(metadata):
        return []

    science = metadata.get("science")
    if not isinstance(science, Mapping):
        return ["science is required"]

    errors: list[str] = []
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
        if isinstance(original_url, str) and urlparse(original_url).scheme != "https":
            errors.append("science.original_url must use HTTPS for public sources")

    if metadata["type"] == "boi/science-evidence":
        original_text = science.get("original_text")
        original_text_hash = science.get("original_text_hash")
        if isinstance(original_text, str) and isinstance(original_text_hash, str):
            expected_hash = "sha256:" + hashlib.sha256(original_text.encode("utf-8")).hexdigest()
            if original_text_hash != expected_hash:
                errors.append("science.original_text_hash must match original_text UTF-8 SHA-256")

    if "evidence_refs" in science:
        science_refs = _reference_values(science["evidence_refs"])
        source_refs = _reference_values(metadata.get("source_refs"))
        if source_refs != science_refs:
            errors.append("science.evidence_refs must match OKF source_refs")

    return errors
