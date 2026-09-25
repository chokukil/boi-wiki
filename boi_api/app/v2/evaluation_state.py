from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import AgentV2Settings
from .store import AgentV2Store


EVALUATION_STATE_SCHEMA = "boi-evaluation-state/v1"
ALLOWED_SEED_COLLECTIONS = {
    "a2ui_surfaces",
    "agent_task_packages",
    "artifacts",
    "checkpoints",
    "completion_records",
    "contexts",
    "evidence_ledger",
    "jobs",
    "knowledge_candidates",
    "knowledge_health_findings",
    "knowledge_patch_proposals",
    "knowledge_sources",
    "negative_results",
    "ontology_schema_proposals",
    "task_runs",
    "usage_ledgers",
    "usage_records",
    "work_runs",
    "work_run_checkpoints",
}
ALLOWED_CAPABILITY_STATES = {"ready", "degraded", "needs_input", "unavailable"}


class EvaluationStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvaluationRuntimeState:
    enabled: bool = False
    profile: str = ""
    manifest_path: str = ""
    checksum: str = ""
    records: tuple[dict[str, Any], ...] = ()
    dependency_overrides: dict[str, bool] = field(default_factory=dict)
    capability_overrides: dict[str, str] = field(default_factory=dict)
    connectors: dict[str, dict[str, Any]] = field(default_factory=dict)
    action_results: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def disabled(cls) -> "EvaluationRuntimeState":
        return cls()

    @classmethod
    def from_settings(cls, settings: AgentV2Settings) -> "EvaluationRuntimeState":
        if not settings.evaluation_mode:
            return cls.disabled()
        path = settings.evaluation_state_manifest
        expected_checksum = settings.evaluation_state_checksum
        if path is None or not expected_checksum:
            raise EvaluationStateError(
                "evaluation mode requires BOI_EVALUATION_STATE_MANIFEST and BOI_EVALUATION_STATE_SHA256"
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise EvaluationStateError(
                f"evaluation state manifest is unavailable: {path}"
            ) from exc
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != expected_checksum:
            raise EvaluationStateError(
                "evaluation state manifest checksum does not match BOI_EVALUATION_STATE_SHA256"
            )
        try:
            manifest = yaml.safe_load(raw.decode("utf-8")) or {}
        except (UnicodeError, yaml.YAMLError) as exc:
            raise EvaluationStateError("evaluation state manifest is invalid YAML") from exc
        if not isinstance(manifest, dict):
            raise EvaluationStateError("evaluation state manifest must be an object")
        if manifest.get("schema") != EVALUATION_STATE_SCHEMA:
            raise EvaluationStateError(
                f"evaluation state schema must be {EVALUATION_STATE_SCHEMA}"
            )
        if manifest.get("immutable") is not True:
            raise EvaluationStateError("evaluation state manifest must be immutable")
        profiles = manifest.get("profiles")
        if not isinstance(profiles, dict):
            raise EvaluationStateError("evaluation state manifest requires profiles")
        profile_name = settings.evaluation_profile or "holdout"
        profile = profiles.get(profile_name)
        if not isinstance(profile, dict):
            raise EvaluationStateError(
                f"evaluation state profile is not declared: {profile_name}"
            )
        raw_records = [
            *(manifest.get("records") or []),
            *(profile.get("records") or []),
        ]
        records: list[dict[str, Any]] = []
        for index, item in enumerate(raw_records, start=1):
            if not isinstance(item, dict):
                raise EvaluationStateError(
                    f"evaluation state record {index} must be an object"
                )
            collection = str(item.get("collection") or "").strip()
            key = str(item.get("key") or "").strip()
            value = item.get("value")
            if collection not in ALLOWED_SEED_COLLECTIONS:
                raise EvaluationStateError(
                    f"evaluation state record {index} uses forbidden collection {collection!r}"
                )
            if not key or not isinstance(value, dict):
                raise EvaluationStateError(
                    f"evaluation state record {index} requires key and object value"
                )
            records.append(
                {"collection": collection, "key": key, "value": copy.deepcopy(value)}
            )

        def bool_map(name: str) -> dict[str, bool]:
            raw_map = profile.get(name) or {}
            if not isinstance(raw_map, dict) or any(
                not isinstance(value, bool) for value in raw_map.values()
            ):
                raise EvaluationStateError(f"profile.{name} must be a boolean map")
            return {str(key): bool(value) for key, value in raw_map.items()}

        capability_overrides = profile.get("capability_overrides") or {}
        connectors = profile.get("connectors") or {}
        action_results = manifest.get("action_results") or {}
        if not isinstance(capability_overrides, dict):
            raise EvaluationStateError("profile.capability_overrides must be an object")
        invalid_capability_states = {
            str(value)
            for value in capability_overrides.values()
            if str(value) not in ALLOWED_CAPABILITY_STATES
        }
        if invalid_capability_states:
            raise EvaluationStateError(
                "profile.capability_overrides contains invalid states: "
                + ", ".join(sorted(invalid_capability_states))
            )
        if not isinstance(connectors, dict) or any(
            not isinstance(value, dict) for value in connectors.values()
        ):
            raise EvaluationStateError("profile.connectors must be an object map")
        if not isinstance(action_results, dict) or any(
            not isinstance(value, dict) for value in action_results.values()
        ):
            raise EvaluationStateError("action_results must be an object map")
        return cls(
            enabled=True,
            profile=profile_name,
            manifest_path=str(path),
            checksum=checksum,
            records=tuple(records),
            dependency_overrides=bool_map("dependency_overrides"),
            capability_overrides={
                str(key): str(value)
                for key, value in capability_overrides.items()
            },
            connectors={str(key): copy.deepcopy(value) for key, value in connectors.items()},
            action_results={
                str(key): copy.deepcopy(value) for key, value in action_results.items()
            },
        )

    def provision(self, store: AgentV2Store) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "seeded": 0}
        seeded = 0
        for record in self.records:
            collection = str(record["collection"])
            key = str(record["key"])
            value = copy.deepcopy(record["value"])
            fixture_metadata = value.get("evaluation_fixture")
            if fixture_metadata not in (None, {}):
                raise EvaluationStateError(
                    f"evaluation record {collection}/{key} may not supply fixture metadata"
                )
            value["evaluation_fixture"] = {
                "schema": EVALUATION_STATE_SCHEMA,
                "profile": self.profile,
                "checksum": self.checksum,
            }
            existing = store.get(collection, key)
            if existing:
                existing_fixture = existing.get("evaluation_fixture") or {}
                if existing_fixture.get("checksum") != self.checksum:
                    raise EvaluationStateError(
                        f"evaluation record collides with non-matching state: {collection}/{key}"
                    )
                continue
            store.put(collection, key, value)
            seeded += 1
        return {
            "enabled": True,
            "profile": self.profile,
            "checksum": self.checksum,
            "seeded": seeded,
        }

    def action_result(self, action_key: str) -> dict[str, Any] | None:
        result = self.action_results.get(str(action_key or ""))
        return copy.deepcopy(result) if isinstance(result, dict) else None

    def readiness_payload(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "profile": self.profile,
            "checksum": self.checksum,
            "connectors": copy.deepcopy(self.connectors),
        }
