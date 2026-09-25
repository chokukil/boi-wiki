"""Authority-bounded skill contracts for ontology migration work."""

from __future__ import annotations

from dataclasses import dataclass


FORBIDDEN_SKILL_AUTHORITIES = frozenset(
    {
        "compile_sql",
        "execute_database",
        "attest",
        "issue_verdict",
        "approve",
        "release",
        "activate_release",
    }
)


@dataclass(frozen=True)
class MigrationSkillContract:
    skill_id: str
    purpose: str
    required_inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    output_authority: str
    allowed_actions: tuple[str, ...]
    forbidden_actions: frozenset[str]
    deterministic_first: bool
    local_model_allowed: bool
    local_model_fallback: str = "blocked"


def ontology_migration_skill_registry() -> dict[str, MigrationSkillContract]:
    definitions = (
        MigrationSkillContract(
            "legacy-source-intake",
            "Capture SQL, catalog, system/module/menu/purpose, and source manifest.",
            (
                "source_ref",
                "source_digest",
                "source_role",
                "catalog_snapshot_ref",
                "system_context",
            ),
            ("SourceArtifactCandidate", "source_manifest"),
            "candidate",
            ("hash", "inventory", "classify_source"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
        MigrationSkillContract(
            "sql-lineage-extract",
            "Extract AST filters, joins, aggregation, order, and column lineage.",
            ("sql_source_ref", "catalog_snapshot"),
            ("lineage_report", "unresolved_items"),
            "evidence",
            ("parse_ast", "classify_lineage", "emit_evidence"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
        MigrationSkillContract(
            "domain-ontology-draft",
            "Draft terms, objects, properties, rules, and metrics from bounded evidence.",
            ("evidence_spans", "domain_context"),
            ("domain_candidates", "uncertainties"),
            "candidate",
            ("extract_claims", "draft_semantics", "cite_evidence"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            True,
        ),
        MigrationSkillContract(
            "existing-concept-match",
            "Propose reuse, evidence addition, extension, or new concept in that order.",
            ("domain_candidate", "active_concept_index"),
            ("match_candidates", "duplicate_risks"),
            "candidate",
            ("rank_matches", "explain_match", "route_attention"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            True,
        ),
        MigrationSkillContract(
            "physical-mapping-verify",
            "Check schema, key, type, cardinality, freshness, and ACL against catalog.",
            ("mapping_candidate", "catalog_snapshot"),
            ("mapping_checks", "mapping_health"),
            "evidence",
            ("validate_catalog", "check_cardinality", "detect_drift"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
        MigrationSkillContract(
            "query-contract-author",
            "Draft logical plan, typed parameters, golden question, and invariants.",
            ("domain_refs", "mapping_refs", "lineage_report"),
            ("LogicalQuerySpecCandidate", "golden_questions", "invariants"),
            "candidate",
            ("draft_logical_plan", "declare_parameters", "declare_invariants"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
        MigrationSkillContract(
            "migration-batch-review",
            "Build dependency closure, exact diff, impact, and preview hash.",
            ("candidate_ids", "before_hashes", "dependency_graph"),
            ("review_plan", "preview_hash", "attention_items"),
            "review_plan",
            ("close_dependencies", "compute_diff", "compute_preview_hash"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
        MigrationSkillContract(
            "harness-evolution",
            "Turn repeated failures into rule, skill, or evaluation candidates.",
            ("failure_clusters", "run_metrics"),
            ("rule_candidates", "skill_candidates", "evaluation_candidates"),
            "candidate",
            ("cluster_failures", "draft_rule_candidate", "draft_eval_candidate"),
            FORBIDDEN_SKILL_AUTHORITIES,
            True,
            False,
        ),
    )
    return {definition.skill_id: definition for definition in definitions}
