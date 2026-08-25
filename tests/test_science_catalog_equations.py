from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from pathlib import Path

import pytest

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError
from boi_api.app.science.models import ReleaseSelection
from boi_api.app.science.rules import (
    EQUATION_EVALUATOR_CONTRACT_DIGEST,
    EQUATION_EVALUATOR_ID,
    EQUATION_EVALUATOR_VERSION,
)
from tests.test_science_catalog import (
    _component_digest,
    _metadata,
    _object_metadata,
    _replace_release_components,
    _write_document,
    science_tree as _science_tree_fixture,
)
from tests.test_science_equations import valid_equation_payload


@pytest.fixture
def science_tree(tmp_path: Path) -> Path:
    return _science_tree_fixture.__wrapped__(tmp_path)


def _catalog_equation_payload() -> dict:
    equation = valid_equation_payload()
    evidence = _object_metadata()["evidence"][1]
    evidence_locator = evidence["locator"]
    locator = {
        "medium": "pdf",
        "resource_url": evidence_locator["resource_url"],
        "content_hash": evidence_locator["content_hash"],
        "exact": True,
        "section": evidence_locator["section"],
        "pdf_page_index": evidence_locator["pdf_page_index"],
        "printed_page": evidence_locator["printed_page"],
        "equation_label": "Fixture Equation 1",
    }
    use = equation["evidence_uses"][0]
    use["evidence_ref"] = "sci:evidence:fixture"
    use["claim_scope_hash"] = evidence["claim_scope_hash"]
    use["locator"] = locator
    use["locator_digest"] = sha256_digest(locator)
    equation["equation_digest"] = sha256_digest(
        {key: value for key, value in equation.items() if key != "equation_digest"}
    )
    return equation


def _install_equation(
    science_tree: Path,
    *,
    mutate: Callable[[dict], None] | None = None,
) -> dict:
    knowledge_type, knowledge, _ = _object_metadata()["knowledge"]
    knowledge = deepcopy(knowledge)
    equation = _catalog_equation_payload()
    if mutate is not None:
        mutate(equation)
        for use in equation["evidence_uses"]:
            use["locator_digest"] = sha256_digest(use["locator"])
        equation["equation_digest"] = sha256_digest(
            {
                key: value
                for key, value in equation.items()
                if key != "equation_digest"
            }
        )
    knowledge["equations"] = [equation]
    _write_document(
        science_tree,
        "knowledge/knowledge.md",
        _metadata(
            knowledge_type,
            knowledge,
            boi_id="boi:public:science:knowledge",
        ),
    )
    return equation


def _install_bound_equation_rule(
    science_tree: Path, *, pin_knowledge: bool = True
) -> dict:
    equation = _install_equation(
        science_tree,
        mutate=lambda item: item["evaluator"].update(
            {"evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST}
        ),
    )
    binding = {
        "equation_id": equation["equation_id"],
        "equation_digest": equation["equation_digest"],
        "evaluator_id": EQUATION_EVALUATOR_ID,
        "evaluator_version": EQUATION_EVALUATOR_VERSION,
        "evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST,
        "constraint_operator": "product",
        "variable_mappings": [
            {
                "equation_variable_id": "voltage",
                "claim_quantity_kind": "voltage",
                "constraint_operand": "left",
            },
            {
                "equation_variable_id": "current",
                "claim_quantity_kind": "current",
                "constraint_operand": "right_1",
            },
            {
                "equation_variable_id": "resistance",
                "claim_quantity_kind": "resistance",
                "constraint_operand": "right_2",
            },
        ],
    }
    binding["binding_digest"] = sha256_digest(binding)
    rule_type, rule, _ = _object_metadata()["rule"]
    rule = deepcopy(rule)
    for field_name in (
        "relation_kind",
        "expected_predicate",
        "contradiction_predicates",
    ):
        rule.pop(field_name, None)
    rule.update(
        {
            "rule_kind": "equation_constraint",
            "subject_concept_id": "sci:concept:voltage",
            "object_concept_id": "sci:concept:resistance",
            "equation": {
                "left_quantity_kind": "voltage",
                "right_quantity_kinds": ["current", "resistance"],
                "operator": "product",
                "relative_tolerance": "0",
            },
            "equation_binding": binding,
        }
    )
    _write_document(
        science_tree,
        "rules/rule.md",
        _metadata(rule_type, rule, boi_id="boi:public:science:rule"),
    )
    components = {
        "sci:evidence:fixture": _component_digest(
            science_tree, "evidence/evidence.md"
        ),
        "sci:rule:fixture": _component_digest(science_tree, "rules/rule.md"),
    }
    if pin_knowledge:
        components["sci:knowledge:fixture"] = _component_digest(
            science_tree, "knowledge/knowledge.md"
        )
    _replace_release_components(science_tree, "sci-release:0.1.0", components)
    return equation


def test_catalog_indexes_validated_equation_by_exact_knowledge_identity(
    science_tree: Path,
) -> None:
    from boi_api.app.science.catalog import ScienceCatalog

    expected = _install_equation(science_tree)
    catalog = ScienceCatalog(science_tree)

    resolved = catalog.equation(expected["equation_id"])
    assert resolved.knowledge_id == "sci:knowledge:fixture"
    assert resolved.equation.equation_digest == expected["equation_digest"]
    assert catalog.equations_for_knowledge("sci:knowledge:fixture") == (
        resolved,
    )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda equation: equation["evidence_uses"][0]["locator"].update(
                {"printed_page": "different page"}
            ),
            "locator",
        ),
        (
            lambda equation: equation["evidence_uses"][0].update(
                {"claim_scope_hash": "sha256:" + "9" * 64}
            ),
            "claim scope",
        ),
        (
            lambda equation: equation["variables"][0].update({"unit": "meter"}),
            "unit.*dimension",
        ),
        (
            lambda equation: equation["evidence_uses"][0].update(
                {"evidence_ref": "sci:evidence:not-present"}
            ),
            "Evidence",
        ),
    ],
)
def test_catalog_rejects_equation_evidence_or_unit_drift(
    science_tree: Path,
    mutation,
    match: str,
) -> None:
    from boi_api.app.science.catalog import ScienceCatalog

    _install_equation(science_tree, mutate=mutation)

    with pytest.raises(ScienceCatalogError, match=match):
        ScienceCatalog(science_tree)


def test_catalog_rejects_duplicate_equation_ids_across_knowledge(
    science_tree: Path,
) -> None:
    from boi_api.app.science.catalog import ScienceCatalog

    equation = _install_equation(science_tree)
    knowledge_type, knowledge, _ = _object_metadata()["knowledge"]
    second = deepcopy(knowledge)
    second["knowledge_id"] = "sci:knowledge:second"
    second["equations"] = [equation]
    _write_document(
        science_tree,
        "knowledge/second.md",
        _metadata(
            knowledge_type,
            second,
            boi_id="boi:public:science:knowledge:second",
        ),
    )

    with pytest.raises(ScienceCatalogError, match="duplicate Science Equation"):
        ScienceCatalog(science_tree)


def test_qualification_rule_binding_cross_checks_exact_released_equation(
    science_tree: Path,
) -> None:
    from boi_api.app.science.catalog import ScienceCatalog

    equation = _install_bound_equation_rule(science_tree)
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    resolved = catalog.resolve_qualification_rule_set(release_set)

    assert resolved.rules[0].rule.equation_binding.equation_digest == (
        equation["equation_digest"]
    )


def test_qualification_rule_binding_rejects_unpinned_equation_knowledge(
    science_tree: Path,
) -> None:
    from boi_api.app.science.catalog import ScienceCatalog

    _install_bound_equation_rule(science_tree, pin_knowledge=False)
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceCatalogError, match="not exactly release-pinned"):
        catalog.resolve_qualification_rule_set(release_set)
