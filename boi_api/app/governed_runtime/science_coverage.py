"""Content-addressed coverage accounting for preserved Science assets."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


class CoverageError(RuntimeError):
    pass


CLASSIFICATIONS = frozenset(
    {"canonical-source", "derived-reproducible", "run-evidence", "candidate-only", "cache"}
)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _normalized_digest(value: Any) -> str:
    digest = str(value or "")
    if digest.startswith("sha256:"):
        digest = digest.removeprefix("sha256:")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise CoverageError(f"invalid SHA-256 digest: {value}")
    return "sha256:" + digest


def _read_tsv(path: Path, *, classified: bool) -> dict[str, tuple[str, int, str | None]]:
    rows: dict[str, tuple[str, int, str | None]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split("\t")
        expected = 4 if classified else 3
        if len(parts) != expected:
            raise CoverageError(f"invalid TSV row at {path.name}:{line_number}")
        digest, raw_size, raw_path = parts[:3]
        relative = raw_path.removeprefix("./")
        if not relative or relative in rows:
            raise CoverageError(f"empty or duplicate asset path: {relative}")
        classification = parts[3] if classified else None
        if classification is not None and classification not in CLASSIFICATIONS:
            raise CoverageError(f"unclassified asset: {relative}")
        rows[relative] = (_normalized_digest(digest), int(raw_size), classification)
    return rows


def build_science_coverage(
    *,
    inventory_path: Path,
    classification_path: Path,
    candidate_manifest_path: Path,
    snapshot_contract_path: Path,
) -> dict[str, Any]:
    inventory = _read_tsv(inventory_path, classified=False)
    classifications = _read_tsv(classification_path, classified=True)
    if inventory != {path: (digest, size, None) for path, (digest, size, _) in classifications.items()}:
        raise CoverageError("inventory/classification mismatch")

    snapshot_contract = json.loads(snapshot_contract_path.read_text(encoding="utf-8"))
    expected_count = int(snapshot_contract["snapshot"]["entry_count"])
    if len(inventory) != expected_count:
        raise CoverageError("snapshot entry count does not match inventory")
    if int(snapshot_contract["classification"].get("unclassified", -1)) != 0:
        raise CoverageError("snapshot classification reports unresolved assets")

    candidate_manifest = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    package_digest = _normalized_digest(candidate_manifest["package_digest"])
    candidates: dict[str, dict[str, Any]] = {}
    for item in candidate_manifest.get("knowledge", []):
        relative = str(item.get("path") or "")
        if relative not in inventory or relative in candidates:
            raise CoverageError(f"candidate path is absent or duplicated: {relative}")
        if _normalized_digest(item.get("original_digest")) != inventory[relative][0]:
            raise CoverageError(f"candidate original digest mismatch: {relative}")
        if item.get("state") not in {"candidate", "attention_required"}:
            raise CoverageError(f"unsupported candidate state: {relative}")
        candidates[relative] = item

    snapshot_id = str(snapshot_contract["snapshot_id"])
    snapshot_digest = _normalized_digest(snapshot_contract["snapshot"]["sha256"])
    assets: list[dict[str, Any]] = []
    for relative in sorted(inventory):
        digest, size, _ = inventory[relative]
        classification = classifications[relative][2]
        asset: dict[str, Any] = {
            "path": relative,
            "size_bytes": size,
            "sha256": digest,
            "classification": classification,
            "asset_id": f"science-asset:{digest}",
            "canonical_projection_eligible": False,
            "qualification_eligible": False,
            "release_authority": False,
        }
        candidate = candidates.get(relative)
        if candidate and candidate["state"] == "candidate":
            asset.update(
                {
                    "disposition": "migrated",
                    "destination": "KnowledgeRevisionCandidate",
                    "candidate_digest": _normalized_digest(candidate["candidate_digest"]),
                    "package_digest": package_digest,
                    "runtime_contract": "inactive-candidate-until-qualified-release",
                }
            )
        elif candidate and candidate["state"] == "attention_required":
            asset.update(
                {
                    "disposition": "attention_required",
                    "destination": "Attention",
                    "package_digest": package_digest,
                    "reason_codes": sorted(str(code) for code in candidate.get("error_codes", [])),
                    "runtime_contract": "no-candidate-no-auto-approval",
                }
            )
        elif classification == "canonical-source":
            asset.update(
                {
                    "disposition": "preserved_as_source",
                    "destination": "SourceArtifact",
                    "source_locator": f"snapshot://{snapshot_id}/{relative}",
                    "runtime_contract": "evidence-source-history-lane-until-release-bound",
                }
            )
        elif classification == "derived-reproducible":
            asset.update(
                {
                    "disposition": "reproducible_from_recipe",
                    "destination": "RebuildRecipe",
                    "recipe_id": "science-snapshot-member-replay@1",
                    "input_digests": [snapshot_digest, digest],
                    "output_digest": digest,
                    "runtime_contract": "deterministic-rebuild-candidate-only",
                }
            )
        elif classification == "run-evidence":
            asset.update(
                {
                    "disposition": "preserved_as_historical_evidence",
                    "destination": "HistoricalRunCheckVerdictLedger",
                    "runtime_contract": "history-lane-qualification-ineligible",
                }
            )
        elif classification == "candidate-only":
            asset.update(
                {
                    "disposition": "attention_required",
                    "destination": "KnowledgeRevisionCandidateOrAttention",
                    "reason_codes": ["OUTSIDE_INITIAL_SCI_PROFILE_IMPORT_SCOPE"],
                    "runtime_contract": "explicit-review-before-structured-import",
                }
            )
        elif classification == "cache":
            asset.update(
                {
                    "disposition": "preserved_noncanonical_cache",
                    "destination": "PreservationInventory",
                    "deletion_authority": False,
                    "runtime_contract": "noncanonical-no-delete-before-retention-gate",
                }
            )
        else:  # pragma: no cover - guarded while parsing the classification TSV
            raise CoverageError(f"unclassified asset: {relative}")
        assets.append(asset)

    by_classification = Counter(asset["classification"] for asset in assets)
    by_disposition = Counter(asset["disposition"] for asset in assets)
    cross_tab = Counter((asset["classification"], asset["disposition"]) for asset in assets)
    manifest: dict[str, Any] = {
        "schema": "boi-science-asset-migration-coverage/v1",
        "snapshot_id": snapshot_id,
        "snapshot_digest": snapshot_digest,
        "inventory_digest": _normalized_digest(snapshot_contract["inventory"]["sha256"]),
        "classification_digest": _normalized_digest(snapshot_contract["classification"]["sha256"]),
        "candidate_package_digest": package_digest,
        "counts": {
            "total": len(assets),
            "unclassified": 0,
            "silently_skipped": 0,
            "by_classification": dict(sorted(by_classification.items())),
            "by_disposition": dict(sorted(by_disposition.items())),
            "cross_tab": {
                f"{classification}->{disposition}": count
                for (classification, disposition), count in sorted(cross_tab.items())
            },
        },
        "canonical_projection_policy": "active-release-only-fail-closed",
        "assets": assets,
    }
    manifest["coverage_digest"] = _sha256(_canonical_json(manifest))
    return manifest
