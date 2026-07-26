#!/usr/bin/env python3
"""Audit the mainline Agent Playground handoff against its completion contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = "53912644c443b0a2af0e5c367901575a111b18ae"
AGENT_HUB_SHA = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
LANGFLOW_IMAGE = (
    "langflowai/langflow:1.11.0@"
    "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def run(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def http_status(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "boi-mainline-audit"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def checksum_errors(root: Path) -> list[str]:
    checksum_file = root / "SHA256SUMS"
    if not checksum_file.exists():
        return ["SHA256SUMS is missing"]
    errors: list[str] = []
    listed: set[str] = set()
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, relative = line.partition("  ")
        listed.add(relative)
        target = root / relative
        if not separator or not target.is_file():
            errors.append(f"missing or malformed: {relative or line}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(f"checksum mismatch: {relative}")
    expected = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    for relative in sorted(expected - listed):
        errors.append(f"unlisted file: {relative}")
    for relative in sorted(listed - expected):
        errors.append(f"listed file is absent: {relative}")
    return errors


def browser_errors(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "unexpected_http_errors": payload.get("unexpected_http_errors")
        or payload.get("unexpected_http")
        or [],
        "console_errors": payload.get("console_errors") or [],
        "page_errors": payload.get("page_errors") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--agent-hub-checkout",
        type=Path,
        default=Path("/home/chokukil/agent-hub-pr25-validation"),
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--verify-checksums", action="store_true")
    args = parser.parse_args()

    handoff = args.handoff_root.resolve()
    source_state = read_json(handoff / "source-state.json")
    mainline_boundary = read_json(handoff / "regression" / "mainline-boundary.json")
    langflow_boundary = read_json(handoff / "regression" / "langflow-boundary.json")
    bundle_boundary = read_json(handoff / "regression" / "langflow-bundle-boundary.json")
    langflow_patch = read_json(handoff / "regression" / "langflow-patch-compatibility.json")
    clean_import = read_json(handoff / "regression" / "langflow-110-clean-import.json")
    migration = read_json(
        handoff / "regression" / "langflow-migration-rollback-revalidation.json"
    )
    incompatible = read_json(
        handoff / "regression" / "incompatible-flow-validation.json"
    )
    secret_scan = read_json(handoff / "secret-scan.json")
    fresh = read_json(
        handoff / "browser" / "fresh-onboarding" / "fresh-onboarding-result.json"
    )
    negative = read_json(
        handoff / "browser" / "negative-recovery" / "negative-recovery-result.json"
    )
    cross_author = read_json(
        handoff
        / "browser"
        / "cross-author-adoption"
        / "cross-author-adoption-result.json"
    )
    action_abstraction = read_json(
        handoff / "browser" / "action-abstraction" / "action-abstraction-result.json"
    )
    wiki_docs = read_json(
        handoff
        / "browser"
        / "wiki-onboarding-docs"
        / "wiki-onboarding-docs-result.json"
    )
    canonical = read_json(
        handoff / "browser" / "canonical-exact-e2e" / "playwright-result.json"
    )
    model = read_json(
        handoff / "browser" / "model-agent-exact-e2e" / "playwright-result.json"
    )
    canonical_operator = read_json(
        handoff
        / "browser"
        / "canonical-exact-e2e"
        / "exact-action-chain-operator.json"
    )
    validation_summary = read_json(handoff / "validation-summary.json")
    hardening = read_json(
        handoff / "browser" / "security-context-hardening" / "result.json"
    )
    composition = read_json(
        handoff / "browser" / "component-composition-drift" / "result.json"
    )
    team_sharing = read_json(
        handoff / "browser" / "team-action-sharing" / "result.json"
    )
    workbench = read_json(
        handoff / "browser" / "staged-workbench" / "result.json"
    )

    checks: list[dict[str, Any]] = []

    def add(requirement: str, name: str, ok: bool, detail: Any) -> None:
        checks.append(
            {
                "requirement": requirement,
                "name": name,
                "ok": bool(ok),
                "detail": detail,
            }
        )

    feature = nested(source_state, "feature", default={})
    hub = nested(source_state, "agent_hub", default={})
    add(
        "mainline-1",
        "exact_origin_main_base",
        feature.get("base") == BASE,
        feature.get("base"),
    )
    add(
        "mainline-1",
        "reviewable_mainline_followup_commits",
        len(feature.get("commits") or []) >= 2
        and feature.get("head") == (feature.get("commits") or [""])[-1],
        feature.get("commits"),
    )
    add(
        "mainline-1",
        "mainline_branch_and_clean_source",
        feature.get("branch") == "codex/agent-playground-mainline"
        and not feature.get("porcelain"),
        {"branch": feature.get("branch"), "porcelain": feature.get("porcelain")},
    )
    add(
        "mainline-1",
        "mainline_changed_path_allowlist",
        bool(mainline_boundary.get("ok"))
        and all(item.get("ok") for item in mainline_boundary.get("checks") or []),
        mainline_boundary.get("checks"),
    )
    boundary_names = {
        item.get("name"): item for item in mainline_boundary.get("checks") or []
    }
    add(
        "mainline-1",
        "semantic_agent_v2_excluded",
        bool(nested(boundary_names, "no_agent_v2_added", "ok", default=False)),
        nested(boundary_names, "no_agent_v2_added", "detail"),
    )
    add(
        "mainline-1",
        "pet_disabled_and_playground_hidden",
        all(
            nested(boundary_names, name, "ok", default=False)
            for name in (
                "pet_default_disabled",
                "playground_explicitly_hides_pet",
                "playground_surface_has_no_pet_assets",
            )
        ),
        {
            name: nested(boundary_names, name, "detail")
            for name in (
                "pet_default_disabled",
                "playground_explicitly_hides_pet",
                "playground_surface_has_no_pet_assets",
            )
        },
    )
    add(
        "mainline-1",
        "immutable_agent_hub_checkout",
        hub.get("head") == AGENT_HUB_SHA
        and hub.get("expected_head") == AGENT_HUB_SHA
        and bool(hub.get("clean"))
        and not hub.get("porcelain"),
        {"head": hub.get("head"), "clean": hub.get("clean")},
    )

    playground_source = (ROOT / "boi_api" / "app" / "agent_playground.py").read_text(
        encoding="utf-8"
    )
    credential_source = (
        ROOT / "boi_api" / "app" / "agent_playground_credentials.py"
    ).read_text(encoding="utf-8")
    main_source = (ROOT / "boi_api" / "app" / "main.py").read_text(encoding="utf-8")
    gateway_source = (ROOT / "action_gateway" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    mcp_source = (ROOT / "boi_wiki_mcp" / "app" / "v2.py").read_text(encoding="utf-8")
    requirements = (ROOT / "boi_api" / "requirements.txt").read_text(encoding="utf-8")
    mainline_compose = (
        ROOT / "validation" / "agent-playground-mainline" / "docker-compose.yml"
    ).read_text(encoding="utf-8")
    add(
        "mainline-1",
        "authidentity_is_direct_identity_contract",
        "from .auth import AuthIdentity" in playground_source
        and "boi_api.app.v2" not in playground_source + credential_source,
        "AuthIdentity without boi_api.app.v2 imports",
    )
    add(
        "mainline-2",
        "endpoint_keys_use_explicit_aes_gcm_dependency",
        "AESGCM" in playground_source and "cryptography==" in requirements,
        "AES-GCM plus pinned cryptography dependency",
    )
    add(
        "mainline-2",
        "endpoint_collection_and_public_api_contract",
        "MAX_ENDPOINTS = 5" in playground_source
        and all(
            route in main_source
            for route in (
                '@app.get("/api/agent-playground/endpoints")',
                '@app.post("/api/agent-playground/endpoints")',
                '@app.patch("/api/agent-playground/endpoints/{endpoint_id}")',
                '@app.delete("/api/agent-playground/endpoints/{endpoint_id}")',
                '@app.post("/api/agent-playground/bootstrap")',
                '@app.post("/api/agent-playground/deployments")',
                '@app.post("/api/agent-playground/deployments/{deployment_id}/action-draft")',
            )
        ),
        "maximum five endpoints plus endpoint, bootstrap, deployment, Action APIs",
    )
    add(
        "mainline-2",
        "pat_and_run_tokens_use_dedicated_sqlite",
        '"agent-playground" / "credentials.sqlite3"' in credential_source
        and "token_hash" in credential_source
        and "BEGIN IMMEDIATE" in credential_source,
        "hashed PAT and transactional one-use run tokens",
    )
    add(
        "mainline-2",
        "independent_playground_token_api",
        all(
            route in main_source
            for route in (
                '@app.post("/api/v2/tokens")',
                '@app.get("/api/v2/tokens")',
                '@app.delete("/api/v2/tokens/{token_id}")',
            )
        ),
        "POST/GET/DELETE /api/v2/tokens",
    )
    mcp_tools = {"boi_search", "boi_get", "boi_plan", "boi_confirm"}
    add(
        "mainline-2",
        "minimal_pat_driven_mcp_v2",
        all(f'"name": "{name}"' in mcp_source for name in mcp_tools)
        and "Never send employee_id" in mcp_source
        and "Authorization" in mcp_source
        and "employee_id:" not in mcp_source,
        sorted(mcp_tools),
    )
    add(
        "mainline-2",
        "wiki_adapter_uses_acl_ontology_and_private_write",
        all(
            marker in main_source
            for marker in (
                "docs = accessible_docs(employee_id)",
                "ontology_search_payload(",
                '"status": "preview"',
                "write_boi(metadata, body)",
            )
        ),
        "main Wiki ACL, ontology search, preview, private BoI writer",
    )
    add(
        "mainline-2",
        "isolated_content_init_syncs_mainline_wiki_guides",
        "../../data/boi:/source:ro" in mainline_compose
        and "cp -a /source/. /content/" in mainline_compose
        and "boi-agent-playground-mainline-content" in mainline_compose
        and "agent-playground-onboarding.md" in mainline_compose
        and "agent-playground-operator-runbook.md" in mainline_compose,
        "read-only worktree source to isolated named content volume",
    )
    add(
        "mainline-3",
        "action_gateway_uses_server_side_exact_flow_proxy",
        "/internal/agent-playground/langflow-executions" in gateway_source
        and '@app.post("/internal/agent-playground/langflow-executions")'
        in main_source
        and "AGENT_PLAYGROUND_SERVICE.execution_connection(" in main_source
        and 'connection["api_key"]' in main_source
        and "X-LANGFLOW-GLOBAL-VAR-BOI_RUN_TOKEN" in main_source
        and "consume_run_token" in main_source,
        "endpoint owner key is resolved server-side; caller run token is consumed",
    )
    add(
        "hardening-authz",
        "hcp_role_reduction_disable_and_outage_fail_closed",
        nested(hardening, "hcp", "role_reduction", "request", "employee_id")
        == "100002"
        and nested(hardening, "hcp", "role_reduction", "response", "status")
        == 403
        and nested(hardening, "hcp", "account_disabled", "response", "status")
        == 403
        and nested(hardening, "hcp", "outage", "response", "status") == 503
        and nested(hardening, "hcp", "cache_bypassed") is True,
        hardening.get("hcp"),
    )
    run_audience = hardening.get("run_token_audience") or {}
    add(
        "hardening-token",
        "run_token_exact_audience_multi_call_then_consume",
        run_audience.get("same_execution_statuses") == [200, 200, 200, 200]
        and all(
            nested(run_audience, "mismatches", field, "status") == 403
            for field in (
                "action_key",
                "deployment_id",
                "endpoint_id",
                "project_id",
                "flow_id",
                "trace_id",
                "execution_id",
                "capability",
            )
        )
        and nested(run_audience, "after_execution", "status") == 401,
        run_audience,
    )
    task_context = hardening.get("task_context") or {}
    add(
        "hardening-context",
        "actual_task_context_is_server_resolved_and_fake_anchors_rejected",
        str(nested(task_context, "request", "task_ref") or "").startswith("task:")
        and nested(task_context, "response", "context_profile")
        == "sop_task_execution"
        and all(
            nested(task_context, "response", "context_pack", key)
            for key in ("task", "sop_stage", "trace_context")
        )
        and nested(task_context, "semantic_assertions", "server_resolved") is True
        and nested(task_context, "negative", "missing_task_status") == 404
        and nested(task_context, "negative", "inaccessible_task_status") in {403, 404}
        and nested(task_context, "ordinary_question", "context_profile")
        == "knowledge_lookup",
        task_context,
    )
    typed = hardening.get("typed_ontology") or {}
    relation_sets = typed.get("relation_sets") or {}
    add(
        "hardening-context",
        "typed_ontology_provenance_fallback_and_acl_aggregate",
        all(relation_sets.get(view) for view in ("workflow", "responsibility", "lineage", "impact"))
        and len(
            {
                tuple(sorted(relation_sets.get(view) or []))
                for view in ("workflow", "responsibility", "lineage", "impact")
            }
        )
        >= 3
        and typed.get("all_edges_have_provenance") is True
        and typed.get("markdown_links_not_typed_workflow") is True
        and nested(typed, "fallback", "ontology_status")
        == "grounded_document_fallback"
        and nested(typed, "acl_exclusion", "count", default=0) > 0
        and not nested(typed, "acl_exclusion", "leaked_ids", default=[]),
        typed,
    )

    add(
        "mainline-3",
        "official_langflow_image_is_pinned",
        nested(bundle_boundary, "official_image", "reference") == LANGFLOW_IMAGE
        and nested(langflow_patch, "checks", "container", "image") == LANGFLOW_IMAGE,
        nested(bundle_boundary, "official_image", "reference"),
    )
    add(
        "mainline-3",
        "langflow_public_api_only_no_patch_or_db_access",
        bool(langflow_boundary.get("ok"))
        and all(item.get("ok") for item in langflow_boundary.get("checks") or []),
        langflow_boundary.get("checks"),
    )
    add(
        "mainline-3",
        "readonly_bundle_preserves_official_package",
        bool(bundle_boundary.get("ok"))
        and bool(nested(bundle_boundary, "package_integrity", "identical"))
        and nested(bundle_boundary, "bundle", "component_mount", "read_only") is True
        and not any(
            nested(bundle_boundary, "pure", "api", "components", name, default=True)
            for name in ("BoIWikiKnowledge", "BoIWikiSave", "BoIModelAgent")
        ),
        {
            "package_integrity": bundle_boundary.get("package_integrity"),
            "mount": nested(bundle_boundary, "bundle", "component_mount"),
        },
    )

    add(
        "validation-oidc",
        "actual_oidc_pkce_session_and_spoof_protection",
        bool(canonical.get("passed"))
        and nested(canonical, "boi_oidc", "state_present") is True
        and nested(canonical, "boi_oidc", "nonce_present") is True
        and nested(canonical, "boi_oidc", "pkce_method") == "S256"
        and nested(canonical, "boi_sso", "auth_source") == "keycloak"
        and nested(canonical, "boi_sso", "query_spoof_status") == 403
        and nested(canonical, "boi_logout", "api_status_after_logout") == 401,
        {
            "employee_id": nested(canonical, "boi_sso", "employee_id"),
            "auth_source": nested(canonical, "boi_sso", "auth_source"),
            "spoof": nested(canonical, "boi_sso", "query_spoof_status"),
        },
    )
    add(
        "validation-onboarding",
        "empty_state_to_ready_onboarding",
        bool(fresh.get("ok"))
        and nested(fresh, "initial", "required") is True
        and nested(fresh, "initial", "endpoint_count") == 0
        and nested(fresh, "langflow", "key_hidden_after_creation") is True
        and nested(fresh, "ready", "status") == "ready",
        {"initial": fresh.get("initial"), "ready": fresh.get("ready")},
    )
    add(
        "validation-onboarding",
        "bootstrap_is_idempotent",
        nested(fresh, "idempotency", "bootstrap_status") == 200
        and nested(fresh, "idempotency", "same_project") is True
        and nested(fresh, "idempotency", "same_flow") is True,
        fresh.get("idempotency"),
    )
    add(
        "validation-onboarding",
        "invalid_other_user_and_unsupported_connections_blocked",
        bool(negative.get("ok"))
        and nested(negative, "negative_connections", "invalid_key", "status") == 502
        and nested(negative, "negative_connections", "other_user_key", "status") == 403
        and nested(negative, "negative_connections", "unsupported_version", "status")
        == 409,
        negative.get("negative_connections"),
    )
    add(
        "validation-onboarding",
        "multi_endpoint_recovery_isolated_and_duplicate_free",
        nested(
            negative,
            "endpoint_independence",
            "after_recovery",
            "distinct_endpoint_ids",
        )
        is True
        and nested(
            negative,
            "endpoint_independence",
            "after_recovery",
            "distinct_project_ids",
        )
        is True
        and nested(negative, "recovery", "duplicate_free") is True,
        {
            "endpoint_independence": negative.get("endpoint_independence"),
            "recovery": negative.get("recovery"),
        },
    )
    add(
        "validation-agent-hub",
        "other_author_approved_flow_and_component_adopted",
        bool(cross_author.get("ok"))
        and nested(cross_author, "authorship", "author_employee_id") == "100001"
        and nested(cross_author, "agent_hub_deploy", "adopter_employee_id") == "100002"
        and len(nested(cross_author, "authorship", "assets", default=[])) == 2
        and nested(cross_author, "validation", "status") == "action_ready",
        {
            "authorship": cross_author.get("authorship"),
            "adoption": cross_author.get("playground_adoption"),
        },
    )
    add(
        "validation-agent-hub",
        "component_is_connected_to_execution_path_and_proven_at_runtime",
        nested(composition, "disconnected", "validation_status") == "blocked"
        and nested(composition, "disconnected", "failure_reason")
        == "disconnected_component"
        and nested(composition, "compose", "public_patch_status") in {200, 201}
        and nested(composition, "compose", "previous_checksum")
        != nested(composition, "compose", "live_checksum")
        and nested(composition, "compose", "end_to_end_reachable") is True
        and nested(composition, "runtime", "status") == 200
        and nested(composition, "runtime", "component_id")
        in nested(composition, "runtime", "executed_component_ids", default=[]),
        composition,
    )
    add(
        "validation-agent-hub",
        "incompatible_component_requires_manual_canvas_without_patch",
        nested(composition, "incompatible", "status") == "manual_required"
        and nested(composition, "incompatible", "patch_request_count") == 0
        and bool(nested(composition, "incompatible", "reason"))
        and bool(nested(composition, "incompatible", "canvas_url")),
        composition.get("incompatible"),
    )
    add(
        "validation-flow",
        "live_checksum_drift_blocks_draft_operator_and_execution",
        nested(composition, "drift", "registered_checksum")
        != nested(composition, "drift", "live_checksum")
        and nested(composition, "drift", "flow_status") == "blocked"
        and nested(composition, "drift", "draft_status") == 409
        and nested(composition, "drift", "operator_status") == "rejected"
        and nested(composition, "drift", "execution_status") == 409
        and nested(composition, "revalidation", "same_exact_reference") is True,
        {
            "drift": composition.get("drift"),
            "revalidation": composition.get("revalidation"),
        },
    )
    expected_connectors = {
        "api",
        "mcp",
        "webhook",
        "manual",
        "event_broker",
        "boi_writer",
        "langflow",
    }
    gateway_invocations = {
        str(item.get("connector_kind") or ""): item
        for item in action_abstraction.get("gateway_invocations") or []
        if isinstance(item, dict) and item.get("connector_kind")
    }
    add(
        "validation-action",
        "action_contract_remains_connector_neutral",
        bool(action_abstraction.get("ok"))
        and nested(action_abstraction, "generic_action", "contract_schema")
        == "boi.action-contract.v1"
        and nested(action_abstraction, "generic_action", "execution_mode") == "gateway"
        and set(gateway_invocations) == expected_connectors
        and all(
            gateway_invocations[connector].get("called") is True
            and int(gateway_invocations[connector].get("http_status") or 0)
            in {200, 202}
            for connector in expected_connectors
        ),
        action_abstraction,
    )
    add(
        "validation-action",
        "team_action_uses_owner_endpoint_but_caller_wiki_acl",
        nested(team_sharing, "action", "scope") == "team"
        and nested(team_sharing, "action", "team_id")
        in nested(team_sharing, "caller", "teams", default=[])
        and nested(team_sharing, "endpoint_owner", "employee_id") == "100002"
        and nested(team_sharing, "caller", "employee_id") == "100001"
        and nested(team_sharing, "action", "status") == "langflow_invoked"
        and nested(
            team_sharing,
            "action",
            "general_execution",
            "task_context",
            "profile",
        )
        == "knowledge_lookup"
        and not nested(
            team_sharing,
            "action",
            "general_execution",
            "task_context",
            "sop_ref",
        )
        and nested(
            team_sharing,
            "action",
            "sop_execution",
            "task_context",
            "profile",
        )
        == "sop_task_execution"
        and all(
            nested(
                team_sharing,
                "action",
                "sop_execution",
                "task_context",
                field,
            )
            for field in (
                "task_ref",
                "sop_ref",
                "sop_stage",
                "event_ref",
                "action_ref",
            )
        )
        and nested(team_sharing, "private_draft", "owner_employee_id") == "100001"
        and nested(team_sharing, "viewer", "employee_id") == "100003"
        and nested(team_sharing, "viewer", "execution_status") == 403,
        team_sharing,
    )
    documents = wiki_docs.get("documents") or []
    add(
        "validation-wiki",
        "wiki_guides_are_oidc_http_200_pet_free_and_mobile",
        bool(wiki_docs.get("ok"))
        and {str(item.get("key") or "") for item in documents}
        == {
            "onboarding",
            "langflow-setup",
            "my-flow-deploy",
            "shared-assets",
            "action-wiki",
            "troubleshooting",
            "operator",
            "hub-boundary",
        }
        and all(
            item.get("status") == 200
            and item.get("pet_dom_count") == 0
            and nested(item, "mobile", "viewport") == 390
            and nested(item, "mobile", "body") == 390
            for item in documents
        ),
        documents,
    )

    canonical_flow = nested(canonical, "agent_hub", "deployment", "flow_id")
    canonical_chain = canonical.get("exact_chain") or {}
    canonical_execution = nested(canonical_chain, "execution", default={})
    add(
        "validation-agent-hub",
        "agent_hub_invalid_key_recovery_and_project_deploy",
        nested(canonical, "agent_hub", "invalid_endpoint_test") == "rejected"
        and nested(canonical, "agent_hub", "endpoint_test")
        == "Langflow 1.11 connected"
        and nested(canonical, "agent_hub", "project") == "boi-100002",
        canonical.get("agent_hub"),
    )
    add(
        "validation-flow",
        "canonical_exact_flow_rediscovered",
        bool(canonical_flow)
        and canonical_flow == nested(canonical, "langflow", "flow_id")
        == nested(canonical, "playground", "rediscovered_flow_id")
        == canonical_chain.get("flow_id")
        == nested(canonical_chain, "deployment_reference", "flow_id"),
        {
            "flow_id": canonical_flow,
            "checksum": canonical_chain.get("artifact_checksum"),
        },
    )
    add(
        "validation-action",
        "canonical_exact_draft_publish_and_operator_fixture",
        nested(canonical, "playground", "action_registration", "validation_status")
        == "valid"
        and nested(canonical, "playground", "action_registration", "publish_status")
        == "publish_requested"
        and canonical_operator.get("operator_mode") == "validation_only"
        and nested(canonical_operator, "deployment_reference", "flow_id")
        == canonical_flow
        and nested(canonical_operator, "deployment_reference", "artifact_checksum")
        == canonical_chain.get("artifact_checksum"),
        {
            "draft_id": canonical_chain.get("registration_draft_id"),
            "action_key": canonical_chain.get("action_key"),
        },
    )
    add(
        "validation-action",
        "canonical_action_general_sop_and_private_draft_execute",
        all(
            canonical_execution.get(name) == "langflow_invoked"
            for name in ("general_status", "sop_status", "private_draft_status")
        )
        and canonical_execution.get("private_draft_owner") == "100002",
        canonical_execution,
    )
    sop_context = nested(
        canonical_execution, "sop_execution", "task_context", default={}
    )
    general_context = nested(
        canonical_execution, "general_execution", "task_context", default={}
    )
    add(
        "validation-wiki",
        "ontology_grounding_and_sop_context_preserved",
        nested(canonical_execution, "general_execution", "source_reference_count", default=0)
        > 0
        and nested(
            canonical_execution,
            "general_execution",
            "ontology_relationship_count",
            default=0,
        )
        > 0
        and general_context.get("profile") == "knowledge_lookup"
        and not general_context.get("sop_ref")
        and sop_context.get("profile") == "sop_task_execution"
        and all(
            sop_context.get(name)
            for name in ("task_ref", "sop_ref", "sop_stage", "event_ref", "action_ref")
        )
        and bool(sop_context.get("prior_results"))
        and bool(sop_context.get("required_evidence"))
        and bool(sop_context.get("missing_evidence")),
        {"general": general_context, "sop": sop_context},
    )
    add(
        "validation-authz",
        "viewer_action_and_private_draft_denied",
        nested(canonical_execution, "viewer_denial", "employee_id") == "100003"
        and nested(canonical_execution, "viewer_denial", "status") == 403,
        canonical_execution.get("viewer_denial"),
    )

    model_flow = nested(model, "agent_hub", "deployment", "flow_id")
    add(
        "validation-model",
        "model_agent_has_independent_exact_flow_and_action",
        bool(model.get("passed"))
        and bool(model_flow)
        and model_flow != canonical_flow
        and model_flow == nested(model, "playground", "rediscovered_flow_id")
        == nested(model, "boi_action", "exact_flow_id")
        and nested(model, "boi_action", "general_status") == "langflow_invoked"
        and nested(model, "boi_action", "sop_status") == "langflow_invoked",
        {
            "canonical_flow": canonical_flow,
            "model_flow": model_flow,
            "action": nested(model, "boi_action", "action_key"),
        },
    )
    model_inference = nested(incompatible, "model_flow", "model_inference", default={})
    add(
        "validation-model",
        "lmstudio_gemma_real_inference",
        model_inference.get("ok") is True
        and nested(model_inference, "fields", "real_inference") is True
        and model_inference.get("model") == "google/gemma-4-26b-a4b-qat"
        and bool(model_inference.get("response_id"))
        and float(model_inference.get("latency_ms") or 0) > 0,
        model_inference,
    )
    add(
        "validation-flow",
        "incompatible_flow_blocked_before_action",
        bool(incompatible.get("ok"))
        and nested(incompatible, "incompatible_flow", "validation_status") == "blocked"
        and nested(incompatible, "incompatible_flow", "action_draft_status") == 409
        and bool(nested(incompatible, "incompatible_flow", "failure_reason")),
        incompatible.get("incompatible_flow"),
    )

    browser_payloads = {
        "fresh": fresh,
        "negative": negative,
        "cross_author": cross_author,
        "action_abstraction": action_abstraction,
        "wiki_docs": wiki_docs,
        "canonical": canonical,
        "model": model,
        "incompatible": incompatible,
        "hardening": hardening,
        "composition": composition,
        "team_sharing": team_sharing,
        "workbench": workbench,
    }
    collected_errors = {
        name: browser_errors(payload) for name, payload in browser_payloads.items()
    }
    add(
        "validation-browser",
        "all_browser_runs_have_zero_unexpected_errors",
        all(not any(errors.values()) for errors in collected_errors.values()),
        collected_errors,
    )
    add(
        "validation-browser",
        "desktop_and_mobile_show_one_primary_staged_workbench",
        bool(workbench.get("ok"))
        and nested(workbench, "desktop", "steps") == 4
        and nested(workbench, "desktop", "primary_actions") == 1
        and nested(workbench, "mobile", "viewport_width") == 390
        and nested(workbench, "mobile", "steps") == 4
        and nested(workbench, "mobile", "primary_actions") == 1
        and nested(workbench, "task_selector", "uses_acl_inbox") is True
        and nested(workbench, "component_statuses") == [
            "배포됨",
            "연결 필요",
            "연결됨",
            "실행 검증됨",
        ]
        and not any(browser_errors(workbench).values()),
        workbench,
    )
    add(
        "validation-langflow",
        "langflow_110_clean_import_and_v1_run",
        bool(clean_import.get("ok"))
        and nested(clean_import, "source", "version") == "1.10.0"
        and nested(clean_import, "target", "version") == "1.11.0"
        and nested(clean_import, "target", "upload_http") == 201
        and nested(clean_import, "target", "run_http") == 200
        and clean_import.get("public_api_only") is True,
        clean_import,
    )
    add(
        "validation-langflow",
        "db_clone_migration_credentials_and_rollback",
        bool(migration.get("ok"))
        and all((migration.get("checks") or {}).values())
        and migration.get("secrets_redacted") is True,
        migration.get("checks"),
    )
    pytest_text = (handoff / "regression" / "full-pytest.log").read_text(
        encoding="utf-8", errors="replace"
    )
    connector_text = (
        handoff / "regression" / "action-gateway-connectors.log"
    ).read_text(encoding="utf-8", errors="replace")
    pytest_counts = [
        int(match)
        for match in re.findall(r"(?m)(\d+) passed(?:,| in)", pytest_text)
    ]
    connector_counts = [
        int(match)
        for match in re.findall(r"(?m)(\d+) passed(?:,| in)", connector_text)
    ]
    add(
        "validation-regression",
        "full_main_and_connector_regressions_pass",
        bool(pytest_counts)
        and max(pytest_counts) >= 610
        and bool(connector_counts)
        and max(connector_counts) >= 19,
        {
            "full_passed": max(pytest_counts) if pytest_counts else 0,
            "connector_passed": max(connector_counts) if connector_counts else 0,
        },
    )
    add(
        "validation-secret",
        "handoff_secret_scan_clean",
        secret_scan.get("ok") is True and not secret_scan.get("matches"),
        secret_scan,
    )
    required_files = [
        "CHERRY_PICK_ORDER.md",
        "README.md",
        "delivery/boi-langflow-1.11-bundle.zip",
        "delivery/langflow/compatibility-manifest.json",
        "delivery/wiki/agent-playground-onboarding.md",
        "delivery/wiki/agent-playground-langflow-setup.md",
        "delivery/wiki/agent-playground-my-flow-deploy.md",
        "delivery/wiki/agent-playground-shared-assets.md",
        "delivery/wiki/agent-playground-action-wiki.md",
        "delivery/wiki/agent-playground-troubleshooting.md",
        "delivery/wiki/agent-playground-operator-runbook.md",
        "delivery/wiki/agent-hub-integration-boundary.md",
        "regression/full-pytest.log",
        "regression/action-gateway-connectors.log",
        "regression/langflow-bundle-boundary.json",
        "regression/incompatible-flow-validation.json",
        "browser/canonical-exact-e2e/playwright-result.json",
        "browser/model-agent-exact-e2e/playwright-result.json",
        "browser/security-context-hardening/result.json",
        "browser/component-composition-drift/result.json",
        "browser/team-action-sharing/result.json",
        "browser/staged-workbench/result.json",
    ]
    missing_files = [name for name in required_files if not (handoff / name).is_file()]
    add(
        "handoff",
        "handoff_contains_required_delivery_and_evidence",
        not missing_files and bool(validation_summary),
        {"missing": missing_files, "file_count": len(list(handoff.rglob("*")))},
    )

    if args.live:
        urls = {
            "main_boi": "http://localhost:28000/",
            "main_langflow": "http://localhost:7860/health",
            "mainline_boi": "http://localhost:28005/",
            "mainline_gateway": "http://localhost:18105/docs",
            "mainline_mcp": "http://localhost:18205/health",
            "mainline_langflow": "http://localhost:7867/health",
            "agent_hub_ui": "http://localhost:18080/AgentHub.html",
            "agent_hub_api": "http://localhost:18001/health",
            "keycloak": "http://localhost:18082/realms/boi-validation",
            "mock_hcp": "http://localhost:18083/health",
            "lmstudio": "http://localhost:1236/v1/models",
        }
        statuses = {name: http_status(url) for name, url in urls.items()}
        live_hub_head = run("git", "rev-parse", "HEAD", cwd=args.agent_hub_checkout)
        live_hub_status = run(
            "git", "status", "--short", cwd=args.agent_hub_checkout
        )
        langflow_inspect = run(
            "docker",
            "inspect",
            "--format",
            "{{.Image}}|{{.Config.Image}}|{{.State.Status}}",
            "boi-agent-playground-mainline-langflow",
        )
        add(
            "validation-live",
            "isolated_stack_and_existing_main_are_live",
            all(200 <= status < 500 for status in statuses.values()),
            statuses,
        )
        add(
            "validation-live",
            "live_langflow_digest_and_agent_hub_immutability",
            "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
            in langflow_inspect
            and live_hub_head == AGENT_HUB_SHA
            and not live_hub_status,
            {
                "langflow": langflow_inspect,
                "agent_hub_head": live_hub_head,
                "agent_hub_status": live_hub_status,
            },
        )

    if args.verify_checksums:
        checksum_failures = checksum_errors(handoff)
        add(
            "handoff",
            "sha256sums_verify",
            not checksum_failures,
            checksum_failures,
        )

    payload = {
        "ok": all(item["ok"] for item in checks),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "handoff_root": str(handoff),
        "base": BASE,
        "check_count": len(checks),
        "passed_count": sum(1 for item in checks if item["ok"]),
        "failed_count": sum(1 for item in checks if not item["ok"]),
        "checks": checks,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
