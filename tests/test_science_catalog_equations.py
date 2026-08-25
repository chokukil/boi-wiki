from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from pathlib import Path

import pytest

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError
from tests.test_science_catalog import (
    _metadata,
    _object_metadata,
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
