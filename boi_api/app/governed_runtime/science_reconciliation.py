"""Deterministic reconciliation of Science producer and later runtime checkpoints."""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml


class ReconciliationError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _read_pi_inventory(path: Path) -> dict[str, tuple[str, int]]:
    result: dict[str, tuple[str, int]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.split("\t")
        if len(parts) != 3:
            raise ReconciliationError(f"invalid Pi inventory row: {line_number}")
        raw_digest, raw_size, raw_path = parts
        relative = raw_path.removeprefix("./")
        digest = raw_digest if raw_digest.startswith("sha256:") else "sha256:" + raw_digest
        if relative in result:
            raise ReconciliationError(f"duplicate Pi path: {relative}")
        result[relative] = (digest, int(raw_size))
    return result


def _markdown_projection(payload: bytes) -> tuple[str | None, str | None]:
    try:
        text = payload.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return None, None
    match = re.match(r"\A---\n(?P<header>.*?)\n---\n(?P<body>.*)\Z", text, flags=re.DOTALL)
    if not match:
        return _digest(text.encode("utf-8")), None
    try:
        metadata = yaml.safe_load(match.group("header")) or {}
    except yaml.YAMLError:
        return _digest(text.encode("utf-8")), None
    if not isinstance(metadata, dict):
        return _digest(text.encode("utf-8")), None
    normalized = deepcopy(metadata)
    for field in ("timestamp", "generated", "generated_at", "updated_at", "reviewed_at"):
        normalized.pop(field, None)
    projection = {"metadata": _json_safe(normalized), "body": match.group("body")}
    boi_id = str(metadata.get("boi_id") or "") or None
    return _digest(_canonical_json(projection)), boi_id


def _semantic_relation(path: str, pi_payload: bytes, runtime_payload: bytes) -> str:
    if pi_payload == runtime_payload:
        return "identical_bytes"
    pi_projection, _ = _markdown_projection(pi_payload)
    runtime_projection, _ = _markdown_projection(runtime_payload)
    if path.endswith(".md") and pi_projection == runtime_projection:
        return "normalized_markdown_equal"
    try:
        pi_text = pi_payload.decode("utf-8-sig").replace("\r\n", "\n")
        runtime_text = runtime_payload.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return "binary_changed"
    return "normalized_text_equal" if pi_text == runtime_text else "semantic_or_text_changed"


def _contract_family(path: str) -> str:
    lowered = path.lower().replace("-", "_")
    if any(token in lowered for token in ("prompt", "role", "qwen", "ninfer", "local_model", ".pi/")):
        return "local_model_prompt_role_contract"
    if path.startswith(("artifacts/", "captures/", "reports/")) or any(
        token in lowered for token in ("/runs/", "manifest", "report")
    ):
        return "run_report_manifest"
    if "sci_profile" in lowered or "science_profile" in lowered:
        return "science_profile_contract"
    if path.startswith("boi_api/app/science/") or any(
        token in lowered for token in ("science_verifier", "science_verification", "verdict", "evaluator")
    ):
        return "science_evaluator_deterministic_check"
    if path.startswith("tests/") or any(token in lowered for token in ("golden", "fixture", "regression")):
        return "golden_fixture_regression"
    if path.startswith("data/boi/"):
        return "knowledge_asset"
    return "runtime_support_contract"


def _destination(family: str) -> str:
    return {
        "local_model_prompt_role_contract": "ModelPromptRoleContractCandidate",
        "science_profile_contract": "ScienceProfileContractCandidate",
        "science_evaluator_deterministic_check": "DeterministicEvaluatorContractCandidate",
        "golden_fixture_regression": "GoldenFixtureOrRebuildRecipe",
        "run_report_manifest": "HistoricalRunCheckVerdictLedger",
        "knowledge_asset": "KnowledgeRevisionCandidate",
        "runtime_support_contract": "SourceArtifactOrRuntimeContractCandidate",
    }[family]


def _ignored_history(archive_path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    directories: list[str] = []
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ReconciliationError("unsafe ignored-history archive path")
            if member.isdir():
                directories.append(path.as_posix())
                continue
            if not member.isfile():
                raise ReconciliationError(f"unsupported ignored-history entry: {member.name}")
            if path.name == ".env":
                raise ReconciliationError("credential-bearing .env cannot enter reconciliation")
            handle = archive.extractfile(member)
            if handle is None:
                raise ReconciliationError(f"ignored-history entry cannot be read: {member.name}")
            payload = handle.read()
            result.append(
                {
                    "path": path.as_posix(),
                    "size_bytes": len(payload),
                    "sha256": _digest(payload),
                    "destination": "HistoricalReasoningReviewArtifact",
                    "qualification_eligible": False,
                    "canonical_projection_eligible": False,
                    "legacy_history_eligible": False,
                }
            )
    return sorted(result, key=lambda item: item["path"]), sorted(directories)


def build_science_runtime_reconciliation(
    *,
    pi_inventory_path: Path,
    pi_root: Path,
    runtime_root: Path,
    runtime_paths: Iterable[str],
    ignored_history_archive: Path,
    pi_coverage_digest: str,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pi_inventory = _read_pi_inventory(pi_inventory_path)
    supplied_runtime_paths = list(runtime_paths)
    runtime_path_list = sorted(set(supplied_runtime_paths))
    if len(runtime_path_list) != len(supplied_runtime_paths):
        raise ReconciliationError("duplicate runtime tracked path")
    runtime: dict[str, tuple[str, int, bytes]] = {}
    for relative in runtime_path_list:
        path = runtime_root / relative
        if path.is_symlink() or not path.is_file():
            raise ReconciliationError(f"runtime tracked path is not a regular file: {relative}")
        payload = path.read_bytes()
        runtime[relative] = (_digest(payload), len(payload), payload)

    pi_digest_paths: dict[str, list[str]] = defaultdict(list)
    for relative, (digest, _) in pi_inventory.items():
        pi_digest_paths[digest].append(relative)

    runtime_ids: dict[str, list[str]] = defaultdict(list)
    for relative, (_, _, payload) in runtime.items():
        if relative.endswith(".md"):
            _, boi_id = _markdown_projection(payload)
            if boi_id:
                runtime_ids[boi_id].append(relative)
    duplicate_ids = {boi_id: paths for boi_id, paths in runtime_ids.items() if len(paths) > 1}
    duplicate_paths = {path for paths in duplicate_ids.values() for path in paths}

    runtime_assets: list[dict[str, Any]] = []
    for relative in sorted(runtime):
        digest, size, payload = runtime[relative]
        family = _contract_family(relative)
        asset: dict[str, Any] = {
            "path": relative,
            "size_bytes": size,
            "sha256": digest,
            "contract_family": family,
            "destination": _destination(family),
            "canonical_projection_eligible": False,
            "qualification_eligible": False,
            "release_authority": False,
        }
        decoded = payload.decode("utf-8", errors="ignore")
        contract_tags: list[str] = []
        for marker, tag in (
            ("prompt_digest", "prompt-digest-binding"),
            ("model_digest", "model-digest-binding"),
            ("role_digest", "role-digest-binding"),
            ("model_id", "model-identity-binding"),
            ("qualification_eligible", "qualification-eligibility-boundary"),
        ):
            if marker in decoded:
                contract_tags.append(tag)
        if all(
            verdict in decoded
            for verdict in (
                "VIOLATION",
                "CONSISTENT",
                "INSUFFICIENT_INFORMATION",
                "OUTSIDE_VALIDITY_DOMAIN",
                "EMPIRICAL_VERIFICATION_REQUIRED",
            )
        ):
            contract_tags.append("five-verdict-contract")
        if contract_tags:
            asset["contract_tags"] = contract_tags
        if relative in pi_inventory:
            pi_digest, _ = pi_inventory[relative]
            pi_payload = (pi_root / relative).read_bytes()
            if digest == pi_digest:
                asset.update(
                    {
                        "path_relation": "identical_path_bytes",
                        "semantic_relation": "identical_bytes",
                        "import_disposition": "deduplicated_by_digest",
                    }
                )
            else:
                asset.update(
                    {
                        "path_relation": "changed_path",
                        "pi_sha256": pi_digest,
                        "semantic_relation": _semantic_relation(relative, pi_payload, payload),
                        "import_disposition": "semantic_review_candidate",
                    }
                )
        else:
            digest_matches = sorted(pi_digest_paths.get(digest, []))
            if digest_matches:
                asset.update(
                    {
                        "path_relation": "runtime_only",
                        "semantic_relation": "identical_digest_different_path",
                        "dedupe_pi_paths": digest_matches,
                        "import_disposition": "deduplicated_by_digest",
                    }
                )
            else:
                asset.update(
                    {
                        "path_relation": "runtime_only",
                        "semantic_relation": "runtime_unique",
                        "import_disposition": (
                            "preserved_as_historical_evidence"
                            if family == "run_report_manifest"
                            else "reproducible_from_recipe"
                            if family == "golden_fixture_regression"
                            else "candidate_imported"
                            if family == "knowledge_asset"
                            else "contract_candidate_imported"
                            if family
                            in {
                                "local_model_prompt_role_contract",
                                "science_profile_contract",
                                "science_evaluator_deterministic_check",
                            }
                            else "preserved_as_source"
                        ),
                    }
                )
        if relative in duplicate_paths:
            boi_id = next(key for key, paths in duplicate_ids.items() if relative in paths)
            asset.update(
                {
                    "destination": "Attention",
                    "import_disposition": "attention_required",
                    "reason_codes": ["DUPLICATE_BOI_ID"],
                    "duplicate_boi_id": boi_id,
                }
            )
        runtime_assets.append(asset)

    pi_only_paths = sorted(set(pi_inventory) - set(runtime))
    pi_only = [
        {
            "path": relative,
            "sha256": pi_inventory[relative][0],
            "size_bytes": pi_inventory[relative][1],
            "covered_by": pi_coverage_digest,
        }
        for relative in pi_only_paths
    ]
    history, history_directories = _ignored_history(ignored_history_archive)
    path_relations = Counter(asset["path_relation"] for asset in runtime_assets)
    path_relations["pi_only"] = len(pi_only)
    manifest: dict[str, Any] = {
        "schema": "boi-science-runtime-reconciliation/v1",
        "pi_coverage_digest": pi_coverage_digest,
        "lineage": deepcopy(lineage or {}),
        "authority": {
            "canonical_write": False,
            "release_authority": False,
            "active_release_transition": False,
            "mechanical_git_merge": False,
            "source_overwrite": False,
        },
        "counts": {
            "pi_assets": len(pi_inventory),
            "runtime_tracked_assets": len(runtime_assets),
            "ignored_history_assets": len(history),
            "ignored_history_directories": len(history_directories),
            "ignored_history_archive_entries": len(history) + len(history_directories),
            "path_relation": dict(sorted(path_relations.items())),
            "runtime_semantic_relation": dict(
                sorted(Counter(asset["semantic_relation"] for asset in runtime_assets).items())
            ),
            "contract_family": dict(sorted(Counter(asset["contract_family"] for asset in runtime_assets).items())),
            "contract_tag": dict(
                sorted(Counter(tag for asset in runtime_assets for tag in asset.get("contract_tags", [])).items())
            ),
            "import_disposition": dict(
                sorted(Counter(asset["import_disposition"] for asset in runtime_assets).items())
            ),
            "duplicate_boi_ids": len(duplicate_ids),
            "duplicate_boi_id_assets": len(duplicate_paths),
            "unresolved": 0,
            "silently_skipped": 0,
        },
        "duplicate_boi_ids": dict(sorted(duplicate_ids.items())),
        "runtime_assets": runtime_assets,
        "pi_only_assets": pi_only,
        "ignored_history": history,
        "ignored_history_directories": history_directories,
    }
    manifest["reconciliation_digest"] = _digest(_canonical_json(manifest))
    return manifest
