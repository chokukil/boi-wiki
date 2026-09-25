from __future__ import annotations

import hashlib
import hmac
import json
import threading
from pathlib import Path
from typing import Any

import yaml

from .capabilities import CapabilityRegistry
from .config import AgentV2Settings
from .harness import (
    HARNESS_PARETO_METRICS,
    HARNESS_REQUIRED_PARETO_DIMENSIONS,
    HarnessRegistry,
)
from .ontology_registry import OntologySchemaRegistry


PACKAGE_SCHEMA = "boi-harness-package/v1"
COMPATIBILITY_VERSION = "boi-platform-contract/v2"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _checksum(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class HarnessPackageCompiler:
    """Compile immutable, agent-independent Harness releases from canonical sources."""

    def __init__(
        self,
        *,
        settings: AgentV2Settings,
        capabilities: CapabilityRegistry,
        harnesses: HarnessRegistry,
        ontology: OntologySchemaRegistry,
    ) -> None:
        self.settings = settings
        self.capabilities = capabilities
        self.harnesses = harnesses
        self.ontology = ontology
        self._lock = threading.Lock()
        self._cached_key = ""
        self._cached_package: dict[str, Any] = {}

    def _repo_root(self) -> Path | None:
        configured_root = self.settings.repo_root
        if (configured_root / ".git").exists():
            return configured_root
        starts = [
            self.settings.agent_catalog_root,
            self.settings.ontology_registry_root,
            self.settings.content_root,
        ]
        for start in starts:
            for candidate in [start, *start.parents]:
                if (candidate / ".git").exists():
                    return candidate
        return None

    @staticmethod
    def _git_revision(repo_root: Path | None) -> str:
        if repo_root is None:
            return "unversioned"
        git_dir = repo_root / ".git"
        try:
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            if head.startswith("ref:"):
                ref = head.split(":", 1)[1].strip()
                ref_path = git_dir / ref
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
                packed = git_dir / "packed-refs"
                if packed.exists():
                    for line in packed.read_text(encoding="utf-8").splitlines():
                        if line and not line.startswith("#") and line.endswith(f" {ref}"):
                            return line.split(" ", 1)[0]
            return head or "unversioned"
        except OSError:
            return "unversioned"

    @staticmethod
    def _yaml(path: Path) -> Any:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    @staticmethod
    def _file_manifest(root: Path, *, include_body: bool = False) -> list[dict[str, Any]]:
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            raw = path.read_bytes()
            row: dict[str, Any] = {
                "path": str(path.relative_to(root)),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            if include_body:
                row["content"] = raw.decode("utf-8", errors="replace")
            rows.append(row)
        return rows

    def _evaluation_refs(self, repo_root: Path | None) -> list[dict[str, Any]]:
        if repo_root is None:
            return []
        relative_paths = [
            "tests/fixtures/agent_v2_product_golden.yaml",
            "tests/fixtures/agent_v2_platform_golden.yaml",
            "tests/fixtures/agent_v2_immutable_holdout.yaml",
            "scripts/evaluate_agent_v2_work_scenarios.py",
        ]
        rows: list[dict[str, Any]] = []
        for relative in relative_paths:
            path = repo_root / relative
            if not path.exists():
                continue
            raw = path.read_bytes()
            rows.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "immutable": "fixture" in relative,
                }
            )
        return rows

    @staticmethod
    def _runtime_contract_manifest(repo_root: Path | None) -> list[dict[str, Any]]:
        """Bind a Harness release to the product code that enforces its contracts.

        Git HEAD alone is insufficient in an intentionally dirty stabilization
        workspace: two different runtimes could otherwise advertise the same
        signed Harness checksum. Keep this surface explicit and product-only so
        evaluator or fixture edits cannot silently redefine the runtime release.
        """

        if repo_root is None:
            return []
        relative_paths = {
            path.relative_to(repo_root)
            for path in (repo_root / "boi_api" / "app" / "v2").glob("*.py")
            if path.is_file()
        }
        relative_paths.update(
            Path(value)
            for value in (
                "boi_api/app/main.py",
                "boi_api/app/domain_status.py",
                "boi_api/app/static/agent_workspace_v2.js",
                "boi_api/app/static/style.css",
                "boi_api/app/templates/_agent_surface_v2.html",
                "boi_api/app/templates/_app_shell.html",
                "boi_api/app/templates/agent_workspace.html",
                "boi_api/app/templates/task_console.html",
                "boi_wiki_mcp/app/main.py",
                "boi_wiki_mcp/app/v2.py",
            )
        )
        rows: list[dict[str, Any]] = []
        for relative in sorted(relative_paths, key=str):
            path = repo_root / relative
            if not path.is_file():
                continue
            raw = path.read_bytes()
            rows.append(
                {
                    "path": relative.as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
            )
        return rows

    def _source_payload(self) -> dict[str, Any]:
        repo_root = self._repo_root()
        catalog_root = self.settings.agent_catalog_root
        public_harness_root = self.settings.content_root / "public" / "harness"
        harness_definitions = self.harnesses.definitions()
        editable_surfaces = sorted(
            {
                surface
                for definition in harness_definitions
                for surface in definition.get("editable_surfaces") or []
            }
        )
        immutable_surfaces = sorted(
            {
                surface
                for definition in harness_definitions
                for surface in definition.get("immutable_boundaries") or []
            }
        )
        runtime_contract_manifest = self._runtime_contract_manifest(repo_root)
        payload = {
            "package_schema": PACKAGE_SCHEMA,
            "compatibility_version": COMPATIBILITY_VERSION,
            "source_revision": self._git_revision(repo_root),
            "runtime_contract_revision": _checksum(runtime_contract_manifest),
            "runtime_contract_manifest": runtime_contract_manifest,
            "schema_revision": self.ontology.schema_revision,
            "capability_catalog": self._yaml(catalog_root / "capabilities-v2.yaml"),
            "draft_contract_catalog": self._yaml(catalog_root / "draft-contracts-v2.yaml"),
            "harness_catalog": {
                "version": self.harnesses.version,
                "definitions": harness_definitions,
            },
            "ontology_schema_registry": self.ontology.public_payload(),
            "domain_catalogs": {
                "actions": self._yaml(self.settings.action_catalog_root / "actions.yaml"),
                "skills": self._yaml(self.settings.action_skill_catalog_root / "skills.yaml"),
                "events": self._yaml(self.settings.event_catalog_root / "event_types.yaml"),
                "workflows": self._yaml(self.settings.workflow_catalog_root / "workflows.yaml"),
            },
            "harness_documents": self._file_manifest(public_harness_root),
            "policies": {
                "ontology_acl": dict(self.ontology.document.acl_policy),
                "confirmation": "preview_then_authenticated_confirmation",
                "read_mutation": "work_session_only",
                "private_draft": "private_until_reviewed_promotion",
                "external_agent": "principal_acl_inheritance",
                "harness_improvement": {
                    "candidate_change_scope": "one_causal_pattern_one_editable_surface",
                    "candidate_min_distinct_runs": max(
                        [
                            int(item.get("candidate_min_distinct_runs") or 3)
                            for item in harness_definitions
                        ]
                        or [3]
                    ),
                    "editable_surfaces": editable_surfaces,
                    "read_only_surfaces": immutable_surfaces,
                    "evaluation_suites": [
                        "held_in",
                        "held_out",
                        "preserved_success",
                        "adversarial",
                        "long_term",
                    ],
                    "evaluation_lock_required": True,
                    "pareto_required_dimensions": sorted(
                        HARNESS_REQUIRED_PARETO_DIMENSIONS
                    ),
                    "pareto_metrics": {
                        key: {"dimension": dimension, "direction": direction}
                        for key, (dimension, direction) in HARNESS_PARETO_METRICS.items()
                    },
                    "candidate_auto_stop": [
                        "safety_violation",
                        "evaluation_regression",
                        "three_no_improvement",
                    ],
                    "canary": {
                        "environment": "local-full",
                        "isolation": "overlay",
                        "production_changed": False,
                    },
                    "code_change": "review_only_patch_artifact",
                },
            },
            "model_profiles": {
                "codex": {"bootstrap": "/api/v2/harness/bootstrap/codex", "canonical_rules_embedded": False},
                "claude": {"bootstrap": "/api/v2/harness/bootstrap/claude", "canonical_rules_embedded": False},
                "custom": {"bootstrap": "/api/v2/harness/bootstrap/custom", "canonical_rules_embedded": False},
            },
            "client_bindings": {
                "web": {
                    "entry": "/api/v2/bootstrap",
                    "transport": "embedded_rest",
                    "harness_resource": "boi://harness/current",
                    "installation_required": False,
                },
                "rest": {
                    "entry": "/api/v2/harness/current",
                    "transport": "https",
                    "harness_resource": "boi://harness/current",
                    "installation_required": False,
                },
                "mcp": {
                    "entry": "boi://harness/current",
                    "transport": "streamable_http",
                    "harness_resource": "boi://harness/current",
                    "installation_required": False,
                },
                "external_agent": {
                    "entry": "/api/v2/harness/bootstrap/{client}",
                    "transport": "rest_or_mcp",
                    "harness_resource": "boi://harness/current",
                    "installation_required": False,
                },
                "local": {
                    "entry": "/api/v2/harness/local-lock",
                    "transport": "offline_snapshot",
                    "harness_resource": "boi://harness/current",
                    "installation_required": False,
                },
            },
            "evaluation_refs": self._evaluation_refs(repo_root),
            "resources": [
                "boi://harness/current",
                "boi://ontology/schema/current",
                "boi://capabilities/current",
            ],
        }
        payload["component_checksums"] = {
            "catalogs": {
                "capabilities": _checksum(payload["capability_catalog"]),
                "draft_contracts": _checksum(payload["draft_contract_catalog"]),
                "harnesses": _checksum(payload["harness_catalog"]),
                "domain": _checksum(payload["domain_catalogs"]),
                "ontology": _checksum(payload["ontology_schema_registry"]),
            },
            "policies": {
                key: _checksum(value)
                for key, value in sorted(payload["policies"].items())
            },
            "runtime": payload["runtime_contract_revision"],
        }
        return payload

    def current(self) -> dict[str, Any]:
        source = self._source_payload()
        cache_key = _checksum(source)
        with self._lock:
            if cache_key == self._cached_key and self._cached_package:
                return json.loads(json.dumps(self._cached_package, ensure_ascii=False))
            release = f"harness-{self.harnesses.version}-{cache_key[:12]}"
            unsigned = {"release": release, **source}
            checksum = _checksum(unsigned)
            signing_key = self.settings.harness_signing_key
            if signing_key:
                signature = hmac.new(
                    signing_key.encode("utf-8"),
                    checksum.encode("ascii"),
                    hashlib.sha256,
                ).hexdigest()
                signature_algorithm = "hmac-sha256"
                signature_status = "signed"
                readiness = "ready"
            else:
                signature = hashlib.sha256(
                    f"development-integrity:{checksum}".encode("utf-8")
                ).hexdigest()
                signature_algorithm = "sha256-development-integrity"
                signature_status = "development"
                readiness = "degraded"
            package = {
                **unsigned,
                "checksum": checksum,
                "signature": signature,
                "signature_algorithm": signature_algorithm,
                "signature_status": signature_status,
                "readiness": readiness,
                "warnings": []
                if signing_key
                else ["BOI_HARNESS_SIGNING_KEY가 없어 production-authenticated signature는 unavailable입니다."],
            }
            self._cached_key = cache_key
            self._cached_package = package
            return json.loads(json.dumps(package, ensure_ascii=False))

    def resource(self, uri: str) -> dict[str, Any]:
        package = self.current()
        resources: dict[str, Any] = {
            "boi://harness/current": package,
            "boi://ontology/schema/current": {
                "release": package["release"],
                "checksum": package["checksum"],
                "schema": package["ontology_schema_registry"],
            },
            "boi://capabilities/current": {
                "release": package["release"],
                "checksum": package["checksum"],
                "catalog": package["capability_catalog"],
            },
        }
        try:
            payload = resources[uri]
        except KeyError as exc:
            raise KeyError(f"unknown Harness resource: {uri}") from exc
        return {"uri": uri, **payload}

    def bootstrap(self, client: str) -> dict[str, Any]:
        package = self.current()
        normalized_client = str(client or "custom").strip().lower()
        profile = package["model_profiles"].get(normalized_client) or package["model_profiles"]["custom"]
        return {
            "client": normalized_client,
            "release": package["release"],
            "checksum": package["checksum"],
            "signature": package["signature"],
            "generated_from_checksum": package["checksum"],
            "canonical_rules_embedded": False,
            "harness_resource": "boi://harness/current",
            "mcp_endpoint": self.settings.mcp_external_url,
            "client_binding": package["client_bindings"]["external_agent"],
            "profile": profile,
            "instructions": [
                "Fetch the current HarnessPackage before claiming or executing work.",
                "Use the authenticated principal ACL and package checksum on every TaskPackage.",
                "Preview mutations and require the shared confirmation contract.",
            ],
        }

    def local_lock(self) -> dict[str, Any]:
        package = self.current()
        lock = {
            "schema": "boi-harness-lock/v1",
            "release": package["release"],
            "checksum": package["checksum"],
            "signature": package["signature"],
            "signature_algorithm": package["signature_algorithm"],
            "offline_snapshot_resource": "boi://harness/current",
        }
        return {
            **lock,
            "harness_lock": lock,
            "private_files_overwritten": False,
            "update_policy": "show_version_diff_then_replace_package_only",
        }

    def verify_offline_lock(
        self,
        harness_lock: dict[str, Any],
        *,
        expected_checksum: str,
    ) -> dict[str, Any]:
        package = self.current()
        lock = dict(harness_lock or {})
        checksum = str(lock.get("checksum") or "")
        signature = str(lock.get("signature") or "")
        algorithm = str(lock.get("signature_algorithm") or "")
        signature_valid = False
        if algorithm == "hmac-sha256" and self.settings.harness_signing_key:
            expected_signature = hmac.new(
                self.settings.harness_signing_key.encode("utf-8"),
                checksum.encode("ascii"),
                hashlib.sha256,
            ).hexdigest()
            signature_valid = hmac.compare_digest(signature, expected_signature)
        elif algorithm == "sha256-development-integrity":
            expected_signature = hashlib.sha256(
                f"development-integrity:{checksum}".encode("utf-8")
            ).hexdigest()
            signature_valid = hmac.compare_digest(signature, expected_signature)
        lock_valid = bool(
            lock.get("schema") == "boi-harness-lock/v1"
            and checksum
            and checksum == expected_checksum
            and checksum == package["checksum"]
            and str(lock.get("release") or "") == package["release"]
            and signature_valid
        )
        return {
            "lock_valid": lock_valid,
            "offline_snapshot_consumed": lock_valid,
            "release": str(lock.get("release") or ""),
            "checksum": checksum,
            "signature_valid": signature_valid,
            "network_accessed": False,
            "private_files_overwritten": False,
        }

    def preview_local_update(
        self,
        current_lock: dict[str, Any],
        *,
        target_release: str,
    ) -> dict[str, Any]:
        package = self.current()
        current = dict(current_lock or {})
        current_release = str(current.get("release") or "")
        current_checksum = str(current.get("checksum") or "")
        target_matches_current = (
            target_release == package["release"]
            and current_checksum == package["checksum"]
        )
        return {
            "status": "no_change" if target_matches_current else "preview",
            "version_diff": {
                "from_release": current_release,
                "to_release": target_release,
                "from_checksum": current_checksum,
                "to_checksum": package["checksum"],
                "changed": not target_matches_current,
                "component_checksums": package["component_checksums"],
            },
            "private_files_overwritten": False,
            "package_files_only": True,
            "production_changed": False,
        }
