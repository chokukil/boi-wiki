from __future__ import annotations

import json
from pathlib import Path

import yaml


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = text.split("---\n", 2)[1]
    return yaml.safe_load(frontmatter) or {}


def test_qwen_import_keeps_slash_numeric_bundle_out_of_public_without_override(tmp_path):
    from scripts.import_qwen_dictionary import import_qwen_dictionary

    source = tmp_path / "source_terms.jsonl"
    overrides = tmp_path / "curation_overrides.yaml"
    output_root = tmp_path / "dictionary"
    manifest = tmp_path / "import_manifest.jsonl"
    source.write_text(
        json.dumps({"term": "0-PG Dist / 1-NG Dist", "definition": "program-state disturbance variants"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    overrides.write_text("overrides: []\n", encoding="utf-8")

    result = import_qwen_dictionary(source, overrides, output_root, manifest)

    assert result["selected_count"] == 0
    assert result["needs_parent_curation_count"] == 1
    assert not (output_root / "0-pg-dist-1-ng-dist.md").exists()
    row = json.loads(manifest.read_text(encoding="utf-8").strip())
    assert row["source_term"] == "0-PG Dist / 1-NG Dist"
    assert row["curation_status"] == "needs_parent_curation"
    assert row["compound_reason"]


def test_qwen_import_override_writes_canonical_alias_and_manifest(tmp_path):
    from scripts.import_qwen_dictionary import import_qwen_dictionary

    source = tmp_path / "source_terms.jsonl"
    overrides = tmp_path / "curation_overrides.yaml"
    output_root = tmp_path / "dictionary"
    manifest = tmp_path / "import_manifest.jsonl"
    source.write_text(
        "\n".join(
            [
                json.dumps({"term": "0-PG Dist / 1-NG Dist", "definition": "program-state disturbance variants"}, ensure_ascii=False),
                json.dumps({"term": "2HI / 4HI / 8HI Stack", "definition": "memory stack height variants"}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    overrides.write_text(
        yaml.safe_dump(
            {
                "overrides": [
                    {
                        "source_term": "0-PG Dist / 1-NG Dist",
                        "action": "replace_with_canonical",
                        "canonical_term": "Word Line Disturbance Test",
                        "term_kind": "test-method",
                        "aliases": ["0-PG Dist", "1-NG Dist", "0-PG Dist / 1-NG Dist"],
                        "broader": ["Reliability Test", "NAND Flash"],
                        "related_terms": ["Reliability Test", "NAND Flash"],
                        "curation_status": "curated",
                        "compound_reason": "slash-bundle of program-state-specific disturbance test variants",
                    },
                    {
                        "source_term": "2HI / 4HI / 8HI Stack",
                        "action": "replace_with_canonical",
                        "canonical_term": "Memory Stack Height",
                        "term_kind": "concept",
                        "aliases": ["2HI", "4HI", "8HI", "2HI Stack", "4HI Stack", "8HI Stack", "3DS Stack Height"],
                        "broader": ["Advanced Packaging"],
                        "related_terms": ["Advanced Packaging", "HBM", "TSV"],
                        "curation_status": "curated",
                        "compound_reason": "numeric variant bundle for memory stack height",
                    },
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = import_qwen_dictionary(source, overrides, output_root, manifest)

    assert result["selected_count"] == 2
    assert not (output_root / "0-pg-dist-1-ng-dist.md").exists()
    word_line = output_root / "word-line-disturbance-test.md"
    stack_height = output_root / "memory-stack-height.md"
    assert word_line.exists()
    assert stack_height.exists()
    metadata = read_frontmatter(word_line)
    assert metadata["term"] == "Word Line Disturbance Test"
    assert metadata["term_kind"] == "test-method"
    assert "0-PG Dist" in metadata["aliases"]
    assert "Reliability Test" in metadata["broader"]
    manifest_rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert manifest_rows[0]["canonical_term"] == "Word Line Disturbance Test"
    assert manifest_rows[0]["curation_status"] == "curated"
    assert manifest_rows[1]["canonical_term"] == "Memory Stack Height"


def test_qwen_import_exclude_action_records_manifest_without_markdown(tmp_path):
    from scripts.import_qwen_dictionary import import_qwen_dictionary

    source = tmp_path / "source_terms.jsonl"
    overrides = tmp_path / "curation_overrides.yaml"
    output_root = tmp_path / "dictionary"
    manifest = tmp_path / "import_manifest.jsonl"
    source.write_text(
        json.dumps({"term": "Noise / 123", "definition": "bad extractor noise"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    overrides.write_text(
        yaml.safe_dump(
            {
                "overrides": [
                    {
                        "source_term": "Noise / 123",
                        "action": "exclude",
                        "curation_status": "excluded",
                        "compound_reason": "extractor noise",
                    }
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = import_qwen_dictionary(source, overrides, output_root, manifest)

    assert result["selected_count"] == 0
    assert result["excluded_count"] == 1
    assert not list(output_root.glob("*.md"))
    row = json.loads(manifest.read_text(encoding="utf-8").strip())
    assert row["action"] == "exclude"
    assert row["curation_status"] == "excluded"
