#!/usr/bin/env python3
"""Build the digest-pinned inactive Science 0.1.0 Release candidate."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.science.catalog import (  # noqa: E402
    ScienceCatalog,
    _release_manifest_digest,
)


RELEASE_ID = "sci-release:0.1.0"
COMPONENT_KINDS = (
    "source",
    "evidence",
    "knowledge",
    "rule",
    "ontology_binding",
    "qualification_matrix",
    "pack",
)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _frontmatter(metadata: dict[str, object], body: str) -> str:
    return (
        "---\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=False)
        + "\n---\n"
        + body
    )


def build_candidate(boi_root: Path) -> tuple[Path, Path]:
    catalog = ScienceCatalog(boi_root)
    component_digests = {
        object_id: stored.digest
        for kind in COMPONENT_KINDS
        for object_id, stored in catalog._objects[kind].items()
    }
    component_digests = dict(sorted(component_digests.items()))
    body = (
        "# Science Release 0.1.0 candidate\n\n"
        "This manifest pins the candidate Science knowledge graph and public qualification corpus. "
        "It is not reviewed, approved, active, or operational.\n"
    )
    metadata: dict[str, object] = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "sci_profile_version": "0.1",
        "type": "boi/science-release",
        "title": "Science Release 0.1.0 candidate",
        "description": "Digest-pinned inactive candidate awaiting independent holdout and human Admin review",
        "tags": ["ScienceVerifier", "ReleaseCandidate", "PendingReview"],
        "timestamp": "2026-08-25T16:00:00+09:00",
        "boi_id": "boi:public:science:release:0.1.0",
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "author": {"type": "agent", "agent_id": "codex"},
        "acl_policy": "acl:public",
        "status": "draft",
        "source_refs": [
            {"type": "boi", "ref": "sci-pack:science-foundation/0.1.0"},
            {"type": "boi", "ref": "sci-pack:spin-coating/0.1.0"},
        ],
        "review": {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        },
        "science": {
            "release_id": RELEASE_ID,
            "schema_version": "sci-profile/0.1",
            "content_hash": "",
            "status": "release_candidate",
            "active": False,
            "components": list(component_digests),
            "component_digests": component_digests,
            "qualification_report": "sci:report:preflight:science-release-0.1.0",
            "holdout_manifest_ref": "boi:public:science:holdout-manifest:0.1.0",
            "supported_scopes": [
                "release-pinned public qualification of reviewed example forms",
                "five primary verdict labels through closed evaluator kinds",
                "Foundation, Physics, Chemistry, Circuits, Materials, Semiconductor Devices, and Spin Coating candidate packs",
            ],
            "partial_scopes": [
                "general dimensional analysis is represented by narrow reviewed examples rather than an arbitrary symbolic solver",
                "empirical SUPPORTS remains unavailable until a released observation schema and qualified observations exist",
            ],
            "unsupported_scopes": [
                "automatic scientific truth, safety, process approval, or recipe recommendation",
                "facts or equations outside release-pinned Knowledge, Rule, conditions, and Evidence spans",
                "activation without independent holdout and authorized human Admin review",
            ],
            "known_limitations": [
                "All v0.1 scientific objects are AI-authored drafts pending authorized Admin review.",
                "G5 independent holdout, G6 channel parity, and G7 human approval are not yet satisfied.",
                "No active or last-safe Science Release exists yet.",
            ],
            "last_safe_release_id": None,
        },
    }
    # ``split_frontmatter`` preserves the newline after the closing delimiter.
    metadata["science"]["content_hash"] = _release_manifest_digest(
        metadata, "\n" + body
    )
    science_root = boi_root / "public" / "science"
    release_path = science_root / "releases" / "science-release-0.1.0.md"
    _atomic_text(release_path, _frontmatter(metadata, body))

    holdout_body = (
        "# Science 0.1.0 independent holdout reservation\n\n"
        "The actual holdout claims are not stored in this development tree. After Rule freeze, "
        "an independent reviewer writes them to the ACL-controlled external location. This "
        "reservation grants no review, approval, qualification, or activation authority.\n"
    )
    holdout_metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/report",
        "title": "Science 0.1.0 independent holdout reservation",
        "description": "Non-authorizing manifest for a post-freeze external sealed holdout",
        "tags": ["ScienceVerifier", "Holdout", "Pending"],
        "timestamp": "2026-08-25T16:00:00+09:00",
        "boi_id": "boi:public:science:holdout-manifest:0.1.0",
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "author": {"type": "agent", "agent_id": "codex"},
        "acl_policy": "acl:public",
        "status": "draft",
        "source_refs": [{"type": "boi", "ref": "boi:public:science:release:0.1.0"}],
        "review": {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        },
        "science_holdout": {
            "manifest_version": "science-holdout/0.1",
            "release_id": RELEASE_ID,
            "state": "pending_independent_commission",
            "external_acl_url": "boi-private://science-verifier/holdouts/science-release-0.1.0.json",
            "sealed_sha256": None,
            "rule_freeze_commit": None,
            "reviewer_role": "independent_science_reviewer",
            "minimum_cases_per_rule": 2,
            "expected_rule_count": 44,
            "expected_minimum_case_count": 88,
            "required_non_spin_majority": True,
            "required_case_families": [
                "violation",
                "false_red",
                "missing_condition",
                "ambiguity",
                "outside_validity_domain",
                "empirical_verification_required",
            ],
            "domain_distribution": {},
        },
    }
    holdout_path = science_root / "qualification" / "holdouts" / "manifest.md"
    _atomic_text(holdout_path, _frontmatter(holdout_metadata, holdout_body))
    return release_path, holdout_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boi-root", type=Path, default=Path("data/boi"))
    arguments = parser.parse_args()
    release, holdout = build_candidate(arguments.boi_root.resolve())
    print(json.dumps({"release": str(release), "holdout": str(holdout)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
