from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
DICTIONARY_ROOT = DATA_ROOT / "boi" / "public" / "dictionary"


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert match, f"{path} must have YAML frontmatter"
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def public_dictionary_docs() -> list[tuple[Path, dict, str]]:
    docs = []
    for path in sorted(DICTIONARY_ROOT.glob("*.md")):
        if path.name == "index.md":
            continue
        metadata, body = frontmatter_and_body(path)
        if metadata.get("type") == "boi/dictionary-term":
            docs.append((path, metadata, body))
    return docs


def markdown_links(markdown: str) -> list[str]:
    return re.findall(r"\[[^\]]+\]\(([^)]+)\)", markdown)


def load_event_types() -> set[str]:
    catalog = yaml.safe_load((DATA_ROOT / "event_catalog" / "event_types.yaml").read_text(encoding="utf-8"))
    items = catalog.get("event_types", catalog if isinstance(catalog, list) else [])
    return {str(item.get("event_type")) for item in items if item.get("event_type")}


def load_action_keys() -> set[str]:
    catalog = yaml.safe_load((DATA_ROOT / "action_catalog" / "actions.yaml").read_text(encoding="utf-8"))
    items = catalog.get("actions", catalog if isinstance(catalog, list) else [])
    return {str(item.get("action_key")) for item in items if item.get("action_key")}


def load_boi_ids() -> set[str]:
    boi_ids = set()
    for path in (DATA_ROOT / "boi").glob("**/*.md"):
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            metadata, _body = frontmatter_and_body(path)
        except AssertionError:
            continue
        boi_id = metadata.get("boi_id")
        if boi_id:
            boi_ids.add(str(boi_id))
    return boi_ids


def test_public_dictionary_seed_has_required_domain_coverage():
    docs = public_dictionary_docs()
    terms = {metadata["term"] for _path, metadata, _body in docs}

    assert len(docs) >= 50
    assert {
        "Fab",
        "Wafer",
        "Lot",
        "Die",
        "FDC",
        "SPC",
        "Cpk",
        "Control Chart",
        "Response Trend",
        "Map View",
        "Cross-section Inspection",
        "Quality System",
        "Equipment",
        "Alarm",
        "Root Cause Analysis",
        "Manual Handoff",
        "Approval",
        "HBM",
        "TSV",
        "Hybrid Bonding",
        "Advanced Packaging",
        "Time Series Forecast",
        "TimesFM",
    }.issubset(terms)


def test_public_dictionary_terms_have_profile_metadata_and_citations():
    for path, metadata, body in public_dictionary_docs():
        assert metadata.get("visibility") == "public", path
        assert metadata.get("status") == "reviewed", path
        assert metadata.get("term"), path
        assert metadata.get("definition"), path
        assert metadata.get("aliases"), path
        assert metadata.get("domain"), path
        assert metadata.get("source_refs"), path
        assert metadata.get("related_terms"), path
        assert "# Summary" in body, path
        assert "# Related Dictionary Terms" in body, path
        assert "# Citations" in body, path


def test_public_dictionary_index_lists_every_dictionary_term():
    index = (DICTIONARY_ROOT / "index.md").read_text(encoding="utf-8")
    links = set(markdown_links(index))
    missing = []
    for path, _metadata, _body in public_dictionary_docs():
        if path.name not in links:
            missing.append(path.name)

    assert not missing


def test_public_dictionary_related_term_links_resolve_to_dictionary_docs():
    dictionary_files = {path.name for path, _metadata, _body in public_dictionary_docs()}
    for path, _metadata, body in public_dictionary_docs():
        section = re.search(r"# Related Dictionary Terms\n\n(.*?)(?=\n# |\Z)", body, re.S)
        assert section, path
        links = markdown_links(section.group(1))
        assert links, path
        for link in links:
            assert not link.startswith("http"), (path, link)
            assert link in dictionary_files, (path, link)
            assert link != path.name, (path, link)


def test_public_dictionary_event_action_sop_mappings_resolve():
    event_types = load_event_types()
    action_keys = load_action_keys()
    boi_ids = load_boi_ids()

    for path, metadata, _body in public_dictionary_docs():
        event_type = metadata.get("maps_to_event_type")
        if event_type:
            assert event_type in event_types, (path, event_type)

        action_key = metadata.get("maps_to_action_key")
        if action_key:
            assert action_key in action_keys, (path, action_key)

        sop_ref = metadata.get("maps_to_sop")
        if sop_ref:
            assert sop_ref in boi_ids, (path, sop_ref)


def test_dictionary_authoring_harness_documents_quality_gate():
    harness = DATA_ROOT / "boi" / "public" / "harness" / "dictionary-authoring-harness.md"
    metadata, body = frontmatter_and_body(harness)

    assert metadata["boi_id"] == "boi:public:harness:dictionary-authoring-harness"
    assert "dictionary_resolve" in body
    assert "pytest tests/test_public_dictionary_quality.py -q -s" in body
    assert "python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links" in body
    assert "Public Dictionary index: `data/boi/public/dictionary/index.md`" in body
