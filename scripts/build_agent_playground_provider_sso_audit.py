#!/usr/bin/env python3
"""Build a requirement-by-requirement audit for provider-neutral Playground SSO."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENT_HUB = Path("/home/chokukil/agent-hub-pr25-validation")
AGENT_HUB_SHA = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
LANGFLOW_IMAGE = (
    "langflowai/langflow:1.11.0@"
    "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def nested(value: Any, *keys: str, default: Any = None) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def corporate_evidence_ok(corporate: dict[str, Any]) -> bool:
    """Accept only a complete, redacted result produced in the corporate environment."""
    return (
        corporate.get("schema")
        == "boi.agent-playground.corporate-sso-acceptance.v1"
        and corporate.get("ok") is True
        and corporate.get("final_acceptance") is True
        and corporate.get("environment") == "corporate"
        and corporate.get("auth_mode")
        in {"external_jwt", "trusted_header_bridge", "embedded_sso"}
        and nested(corporate, "browser_sso", "mode")
        == corporate.get("auth_mode")
        and corporate.get("boi_auth_source") not in {None, "", "dev"}
        and bool(corporate.get("employee_id"))
        and corporate.get("employee_id") == corporate.get("langflow_user")
        and corporate.get("second_password_form") is False
        and corporate.get("principal_match") is True
        and corporate.get("exact_canvas_loaded") is True
        and int(nested(corporate, "canvas_state", "node_count", default=0)) > 0
        and nested(corporate, "canvas_state", "untitled_visible") is False
        and nested(corporate, "exact_reference", "environment") == "prd"
        and nested(corporate, "exact_reference", "origin_label") == "Agent Hub"
        and nested(corporate, "browser_sso", "status") == "ready"
        and nested(corporate, "browser_sso", "principal_match") is True
        and corporate.get("spoof_status") == 403
        and nested(corporate, "logout", "boi_session_cleared") is True
        and nested(corporate, "logout", "langflow_session_cleared") is True
        and nested(
            corporate,
            "logout",
            "canvas_requires_reauthentication",
        )
        is True
        and nested(corporate, "hcp_fail_closed", "environment") == "corporate"
        and nested(corporate, "hcp_fail_closed", "role_reduction_status") == 403
        and nested(corporate, "hcp_fail_closed", "account_disabled_status") == 403
        and nested(corporate, "hcp_fail_closed", "outage_status") == 503
        and nested(corporate, "hcp_fail_closed", "recovered_status") == 200
        and nested(corporate, "hcp_fail_closed", "ok") is True
        and not corporate.get("error")
        and not corporate.get("unexpected_http_errors")
        and not corporate.get("console_errors")
        and not corporate.get("page_errors")
        and not any(
            bool(value)
            for value in (corporate.get("secret_exposure") or {}).values()
        )
    )


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--corporate-evidence", type=Path)
    args = parser.parse_args()
    evidence = args.evidence_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    paths = {
        "oidc": evidence / "agent-playground-browser-sso/result.json",
        "trusted": evidence / "agent-playground-trusted-header/result.json",
        "external": (
            evidence
            / "agent-playground-current/regression/langflow-external-auth-contract-final.json"
        ),
        "keycloak": (
            evidence
            / "agent-playground-current/regression/keycloak-reference-contract-final.json"
        ),
        "hardening": evidence / "agent-playground-security-context-hardening/result.json",
        "onboarding": evidence / "agent-playground-sso-onboarding/result.json",
        "hub": evidence / "agent-playground-agent-hub-sso/playwright-result.json",
        "origin": evidence / "agent-playground-flow-origin/playwright-result.json",
        "exact": evidence / "agent-playground-universal-exact-chain-final/result.json",
        "drift": evidence / "agent-playground-universal-drift-final/result.json",
        "wiki": (
            evidence
            / "agent-playground-wiki-onboarding/wiki-onboarding-docs-result.json"
        ),
        "action": (
            evidence
            / "agent-playground-current/browser/action-abstraction/action-abstraction-result.json"
        ),
        "team": (
            evidence
            / "agent-playground-current/browser/team-action-execution/result.json"
        ),
        "component": (
            evidence
            / "agent-playground-current/browser/component-composition-drift/result.json"
        ),
        "migration": (
            evidence
            / "agent-playground-current/regression/langflow-migration-rollback-revalidation.json"
        ),
        "clean_import": (
            evidence / "agent-playground-current/regression/langflow-110-clean-import.json"
        ),
        "langflow_boundary": (
            evidence / "agent-playground-current/regression/langflow-boundary-final.json"
        ),
        "bundle_boundary": (
            evidence
            / "agent-playground-current/regression/langflow-bundle-boundary-final.json"
        ),
        "mainline_boundary": (
            evidence / "agent-playground-current/regression/mainline-boundary-final.json"
        ),
        "pytest": (
            evidence
            / "agent-playground-current/regression/full-pytest-provider-neutral-final.log"
        ),
    }
    payloads = {
        name: read_json(path)
        for name, path in paths.items()
        if name != "pytest"
    }
    rows: list[dict[str, Any]] = []

    def add(
        section: str,
        requirement: str,
        ok: bool,
        observed: Any,
        *sources: str,
        status: str = "",
    ) -> None:
        rows.append(
            {
                "section": section,
                "requirement": requirement,
                "status": status or ("pass" if ok else "fail"),
                "observed": observed,
                "evidence": [str(paths[name].relative_to(evidence)) for name in sources],
            }
        )

    oidc = payloads["oidc"]
    add(
        "3, 6",
        "OIDC+PKCE same-user Canvas with coordinated logout",
        oidc.get("ok") is True
        and oidc.get("employee_id") == oidc.get("langflow_user") == "100002"
        and oidc.get("second_password_form") is False
        and oidc.get("browser_sso_mode") == "embedded_sso"
        and all(
            nested(oidc, "logout", key) is True
            for key in (
                "boi_session_cleared",
                "langflow_session_cleared",
                "provider_session_cleared",
                "canvas_requires_reauthentication",
            )
        ),
        {
            "employee": oidc.get("employee_id"),
            "langflow_user": oidc.get("langflow_user"),
            "mode": oidc.get("browser_sso_mode"),
            "logout": oidc.get("logout"),
        },
        "oidc",
    )

    external = payloads["external"]
    add(
        "5",
        "Official 1.11 fixed-digest external JWT/JWKS validation",
        external.get("ok") is True
        and external.get("image") == LANGFLOW_IMAGE
        and nested(external, "checks", "valid", "username") == "100002"
        and all(
            nested(external, "checks", name, "rejected") is True
            for name in (
                "invalid_signature",
                "invalid_issuer",
                "invalid_audience",
                "expired",
                "missing_token",
            )
        )
        and external.get("token_exposed") is False,
        {
            "valid": nested(external, "checks", "valid"),
            "negative_statuses": {
                name: nested(external, "checks", name, "status")
                for name in (
                    "invalid_signature",
                    "invalid_issuer",
                    "invalid_audience",
                    "expired",
                    "missing_token",
                )
            },
            "jwks_requests": external.get("jwks_requests"),
        },
        "external",
    )

    keycloak = payloads["keycloak"]
    add(
        "6",
        "Local Keycloak reference clients are confidential PKCE S256 contracts",
        keycloak.get("ok") is True
        and keycloak.get("provider_role") == "local reference implementation only"
        and all((keycloak.get("checks") or {}).values()),
        keycloak.get("checks"),
        "keycloak",
    )

    trusted = payloads["trusted"]
    add(
        "4",
        "Trusted header plus RS256 Token Bridge without callback or spoof",
        trusted.get("ok") is True
        and nested(trusted, "identity", "auth_source") == "trusted_header"
        and nested(trusted, "bridge", "algorithm") == "RS256"
        and nested(trusted, "bridge", "ttl_seconds") == 60
        and nested(trusted, "bridge", "token_exposed") is False
        and nested(trusted, "spoof", "stripped_by_gateway") is True
        and trusted.get("keycloak_callback_used") is False,
        {
            "bridge": trusted.get("bridge"),
            "spoof": trusted.get("spoof"),
            "langflow": trusted.get("langflow"),
        },
        "trusted",
    )

    hardening = payloads["hardening"]
    add(
        "3, 12",
        "HCP is fail-closed and run token is exact-audience caller authority",
        hardening.get("ok") is True
        and nested(hardening, "hcp", "role_reduction", "response", "status") == 403
        and nested(hardening, "hcp", "account_disabled", "response", "status") == 403
        and nested(hardening, "hcp", "outage", "response", "status") == 503
        and nested(hardening, "run_token_audience", "ok") is True,
        {
            "hcp": hardening.get("hcp"),
            "run_token_audience": hardening.get("run_token_audience"),
        },
        "hardening",
    )
    add(
        "11",
        "Server-resolved SOP Task and typed Ontology provenance",
        nested(hardening, "task_context", "semantic_assertions", "server_resolved")
        is True
        and nested(hardening, "task_context", "ordinary_question", "context_profile")
        == "knowledge_lookup"
        and nested(hardening, "typed_ontology", "all_edges_have_provenance") is True
        and nested(hardening, "typed_ontology", "fallback", "ontology_status")
        == "grounded_document_fallback"
        and nested(hardening, "typed_ontology", "acl_exclusion", "leaked_ids") == [],
        {
            "task": hardening.get("task_context"),
            "ontology": hardening.get("typed_ontology"),
        },
        "hardening",
    )

    onboarding = payloads["onboarding"]
    add(
        "9",
        "Four-step onboarding uses standard Langflow key and hides secrets",
        onboarding.get("ok") is True
        and onboarding.get("employee_id") == "100002"
        and onboarding.get("api_key_created_in_langflow_ui") is True
        and onboarding.get("api_key_response_redacted") is True
        and onboarding.get("endpoint_owner") == "100002"
        and onboarding.get("project_name") == "boi-100002"
        and onboarding.get("recommended_flow") == "BoI Universal Simulation MCP"
        and onboarding.get("preview_smoke") == "passed",
        onboarding,
        "onboarding",
    )

    hub = payloads["hub"]
    hub_flow = str(nested(hub, "exact_chain", "flow_id") or "")
    add(
        "2, 10",
        "Immutable Agent Hub UI deploys and returns an exact Flow",
        hub.get("passed") is True
        and bool(hub_flow)
        and nested(hub, "exact_chain", "artifact_checksum")
        and not hub.get("unexpected_http_errors")
        and not hub.get("console_errors")
        and not hub.get("page_errors"),
        {
            "flow_id": hub_flow,
            "checksum": nested(hub, "exact_chain", "artifact_checksum"),
            "project": nested(hub, "agent_hub", "project"),
        },
        "hub",
    )

    origin = payloads["origin"]
    add(
        "7, 8",
        "DEV/PRD badges and SSO Canvas links use exact server URLs",
        origin.get("ok") is True
        and nested(origin, "desktop", "expected_prd_flow_id") == hub_flow
        and all(
            "host.docker.internal" not in str(item.get("canvas_url") or "")
            and "host.docker.internal" not in str(item.get("asset_url") or "")
            for item in origin.get("links") or []
        )
        and nested(origin, "mobile", "viewport_width") == 390
        and nested(origin, "mobile", "scroll_width") == 390,
        {
            "desktop": origin.get("desktop"),
            "mobile": origin.get("mobile"),
        },
        "origin",
    )

    exact = payloads["exact"]
    drift = payloads["drift"]
    exact_flow = str(nested(exact, "exact_reference", "flow_id") or "")
    exact_checksum = str(nested(exact, "exact_reference", "artifact_checksum") or "")
    add(
        "10, 11, 12",
        "MCP preview and exact Action preserve source, Ontology, SOP and caller draft",
        exact.get("ok") is True
        and exact_flow == hub_flow
        and nested(exact, "mcp", "forced_private_draft", "write_blocked") is True
        and nested(exact, "caller_bound_save", "action", "owner_employee_id") == "100002"
        and nested(exact, "viewer", "action_status") == 403,
        {
            "flow_id": exact_flow,
            "checksum": exact_checksum,
            "contract_comparison": exact.get("contract_comparison"),
            "caller_bound_save": exact.get("caller_bound_save"),
        },
        "exact",
    )
    add(
        "12",
        "Live checksum drift blocks MCP and Action then recovers exact reference",
        drift.get("ok") is True
        and nested(drift, "drift", "mcp_status") == 409
        and nested(drift, "drift", "action_status") == 409
        and nested(drift, "recovery", "flow_id") == exact_flow
        and nested(drift, "recovery", "checksum") == exact_checksum,
        {"drift": drift.get("drift"), "recovery": drift.get("recovery")},
        "drift",
    )

    action = payloads["action"]
    connectors = {
        str(item.get("connector_kind") or "")
        for item in action.get("gateway_invocations") or []
    }
    add(
        "12",
        "Action remains connector-neutral across seven live bindings",
        action.get("ok") is True
        and connectors
        == {"api", "mcp", "webhook", "manual", "event_broker", "boi_writer", "langflow"}
        and all(
            item.get("called") is True
            and int(item.get("http_status") or 0) in {200, 202}
            for item in action.get("gateway_invocations") or []
        ),
        {"connectors": sorted(connectors)},
        "action",
    )

    team = payloads["team"]
    add(
        "12",
        "Team Action uses endpoint-owner key and caller Wiki ACL",
        team.get("ok") is True
        and nested(team, "endpoint_owner", "employee_id") == "100002"
        and nested(team, "caller", "employee_id") == "100001"
        and nested(team, "private_draft", "owner_employee_id") == "100001"
        and nested(team, "viewer", "execution_status") == 403,
        team,
        "team",
    )

    component = payloads["component"]
    add(
        "10",
        "Shared component must be connected and executed; incompatible stays manual",
        component.get("ok") is True
        and nested(component, "disconnected", "validation_status") == "blocked"
        and nested(component, "runtime", "component_id")
        in nested(component, "runtime", "executed_component_ids", default=[])
        and nested(component, "incompatible", "status") == "manual_required",
        {
            "disconnected": component.get("disconnected"),
            "runtime": component.get("runtime"),
            "incompatible": component.get("incompatible"),
        },
        "component",
    )

    wiki = payloads["wiki"]
    documents = wiki.get("documents") or []
    add(
        "14",
        "User and operator Wiki guides are real HTTP desktop/mobile pages",
        wiki.get("ok") is True
        and len(documents) >= 10
        and all(
            item.get("status") == 200
            and item.get("pet_dom_count") == 0
            and nested(item, "mobile", "viewport") == 390
            for item in documents
        ),
        {"documents": [item.get("key") for item in documents]},
        "wiki",
    )

    migration = payloads["migration"]
    clean_import = payloads["clean_import"]
    add(
        "15",
        "1.10 clean import, clone migration, credential preservation and rollback",
        migration.get("ok") is True
        and all((migration.get("checks") or {}).values())
        and clean_import.get("ok") is True
        and nested(clean_import, "target", "run_http") == 200,
        {
            "migration_checks": migration.get("checks"),
            "clean_import": clean_import.get("target"),
        },
        "migration",
        "clean_import",
    )

    boundary = payloads["langflow_boundary"]
    bundle = payloads["bundle_boundary"]
    mainline = payloads["mainline_boundary"]
    add(
        "2",
        "Langflow and Agent Hub source remain unmodified external systems",
        boundary.get("ok") is True
        and bundle.get("ok") is True
        and nested(bundle, "package_integrity", "identical") is True
        and nested(bundle, "bundle", "component_mount", "read_only") is True
        and git("rev-parse", "HEAD", cwd=AGENT_HUB) == AGENT_HUB_SHA
        and not git("status", "--short", cwd=AGENT_HUB),
        {
            "langflow_public_api_checks": boundary.get("checks"),
            "package_integrity": bundle.get("package_integrity"),
            "agent_hub_sha": AGENT_HUB_SHA,
            "agent_hub_clean": True,
            "mainline_boundary_ok": mainline.get("ok"),
        },
        "langflow_boundary",
        "bundle_boundary",
        "mainline_boundary",
    )

    pytest_text = paths["pytest"].read_text(encoding="utf-8", errors="replace")
    passed_match = re.search(r"(\d+) passed", pytest_text)
    add(
        "15",
        "Full main regression passes",
        bool(passed_match) and " failed" not in pytest_text,
        {"passed": int(passed_match.group(1)) if passed_match else 0},
        "pytest",
    )

    corporate_status = "pending_external"
    corporate_observed: Any = {
        "reason": "no access to the corporate SSO gateway or embedded Langflow SSO environment",
        "required_next_evidence": (
            "one intranet browser trace proving no-password exact Canvas access, "
            "matching employee identity, logout, and HCP fail-closed behavior"
        ),
    }
    if args.corporate_evidence:
        corporate = read_json(args.corporate_evidence)
        corporate_ok = corporate_evidence_ok(corporate)
        corporate_status = "pass" if corporate_ok else "fail"
        corporate_observed = corporate
    add(
        "15, 16",
        "At least one supported SSO mode passes in the corporate environment",
        corporate_status == "pass",
        corporate_observed,
        status=corporate_status,
    )

    implementation_rows = [
        row for row in rows if row["status"] != "pending_external"
    ]
    implementation_ok = all(row["status"] == "pass" for row in implementation_rows)
    goal_complete = implementation_ok and all(row["status"] == "pass" for row in rows)
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_commit": git("rev-parse", "HEAD", cwd=ROOT),
        "base_commit": "53912644",
        "implementation_and_local_validation_ok": implementation_ok,
        "goal_complete": goal_complete,
        "external_gate": corporate_status,
        "rows": rows,
    }
    (output / "REQUIREMENT_AUDIT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Agent Playground provider-neutral SSO requirement audit",
        "",
        f"- feature commit: `{result['feature_commit']}`",
        f"- local implementation and validation: `{'PASS' if implementation_ok else 'FAIL'}`",
        f"- complete goal: `{'PASS' if goal_complete else 'PENDING'}`",
        f"- corporate environment gate: `{corporate_status}`",
        "",
        "| Section | Requirement | Status | Evidence |",
        "| --- | --- | --- | --- |",
        *[
            "| {section} | {requirement} | {status} | {evidence} |".format(
                section=row["section"],
                requirement=row["requirement"].replace("|", "\\|"),
                status=row["status"],
                evidence="<br>".join(f"`{item}`" for item in row["evidence"]) or "-",
            )
            for row in rows
        ],
        "",
        "The corporate gate is intentionally not inferred from localhost evidence.",
        "Attach a sanitized corporate browser result and rerun this builder with",
        "`--corporate-evidence` before changing `goal_complete` to true.",
    ]
    (output / "REQUIREMENT_AUDIT.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if implementation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
