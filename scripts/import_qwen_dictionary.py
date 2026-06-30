from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml


KST = timezone(timedelta(hours=9))
ALLOWED_ACTIONS = {
    "keep",
    "replace_with_canonical",
    "split_into_terms",
    "alias_to_existing",
    "exclude",
    "exclude_from_public",
    "needs_parent_curation",
}
TERM_KINDS = {"concept", "acronym", "test-method", "variant-group", "variant"}


def slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9가-힣]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-") or "dictionary-term"


def is_compound_bundle(term: str) -> bool:
    text = str(term or "")
    has_slash = "/" in text
    has_numeric_variant = bool(re.search(r"\b\d+[A-Za-z가-힣-]*\b", text))
    return has_slash and has_numeric_variant


def source_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides: dict[str, dict[str, Any]] = {}
    for item in data.get("overrides") or []:
        source_term = str(item.get("source_term") or "").strip()
        if not source_term:
            continue
        action = str(item.get("action") or "keep")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported Qwen dictionary override action: {action}")
        overrides[source_term] = dict(item)
    return overrides


def list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def markdown_link_for_term(term: str) -> str:
    return f"[{term}]({slugify(term)}.md)"


def dictionary_markdown(metadata: dict[str, Any], source_ref: str) -> str:
    related = list_values(metadata.get("related_terms")) or list_values(metadata.get("broader"))
    citations = metadata.get("source_refs") or [{"type": "qwen-import", "ref": source_ref}]
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    lines = [
        "---",
        frontmatter,
        "---",
        "",
        "# Summary",
        "",
        str(metadata.get("definition") or ""),
        "",
        "# BoI Usage",
        "",
        f"- Canonical term: {metadata.get('term')}",
        f"- Term kind: {metadata.get('term_kind') or 'concept'}",
        "- Qwen source terms are preserved as aliases or curation manifest rows; embedding vectors are not stored.",
        "",
        "# Agent Notes",
        "",
        "- Use this term for ontology search interpretation and query expansion only.",
        "- Execution authority remains with Event Broker, Action Gateway, and BoI Profile ACL.",
        "",
        "# Related Dictionary Terms",
        "",
    ]
    if related:
        lines.extend(f"- {markdown_link_for_term(term)}" for term in related)
    else:
        lines.append("- Related public parent is not set.")
    lines.extend(["", "# Citations", ""])
    for citation in citations:
        if isinstance(citation, dict):
            ref = str(citation.get("ref") or citation.get("type") or "Qwen source")
            url = str(citation.get("url") or "")
            lines.append(f"- [{ref}]({url})" if url else f"- {ref}")
        else:
            lines.append(f"- {citation}")
    return "\n".join(lines).strip() + "\n"


def metadata_for_term(source: dict[str, Any], override: dict[str, Any], *, canonical_term: str, action: str) -> dict[str, Any]:
    term_kind = str(override.get("term_kind") or source.get("term_kind") or "concept")
    if term_kind not in TERM_KINDS:
        term_kind = "concept"
    aliases = list_values(override.get("aliases"))
    source_term = str(source.get("term") or "").strip()
    if source_term and source_term != canonical_term and source_term not in aliases:
        aliases.append(source_term)
    source_ref = f"qwen-source:{source_hash(source)[:12]}"
    now = datetime.now(KST).replace(microsecond=0).isoformat()
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/dictionary-term",
        "title": canonical_term,
        "description": str(override.get("definition") or source.get("definition") or canonical_term),
        "tags": ["Dictionary", "QwenImport"],
        "timestamp": now,
        "boi_id": f"boi:public:dictionary:{slugify(canonical_term)}",
        "visibility": "public",
        "classification": "internal",
        "owner": "aix-tf",
        "author": {"type": "agent", "agent_id": "qwen-dictionary-import"},
        "acl_policy": "acl:public",
        "status": "reviewed",
        "review": {"reviewer": "dictionary-curator", "review_status": "reviewed"},
        "term": canonical_term,
        "term_kind": term_kind,
        "definition": str(override.get("definition") or source.get("definition") or canonical_term),
        "aliases": aliases or [canonical_term],
        "domain": str(override.get("domain") or source.get("domain") or "qwen-import"),
        "examples": list_values(override.get("examples") or source.get("examples")) or [f"{canonical_term} 용어를 BoI Wiki dictionary에서 해석한다."],
        "links": [],
        "related_terms": list_values(override.get("related_terms")),
        "broader": list_values(override.get("broader")),
        "narrower": list_values(override.get("narrower")),
        "same_as": list_values(override.get("same_as")),
        "curation_status": str(override.get("curation_status") or "curated"),
        "compound_reason": str(override.get("compound_reason") or ""),
        "source_refs": [{"type": "qwen-import", "ref": source_ref}],
    }
    metadata["source_refs"].append({"type": "qwen-override", "ref": action})
    return metadata


def manifest_row(source: dict[str, Any], *, action: str, canonical_term: str = "", term_kind: str = "", curation_status: str = "", compound_reason: str = "", output_path: str = "", broader: list[str] | None = None) -> dict[str, Any]:
    return {
        "source_term": str(source.get("term") or ""),
        "source_hash": source_hash(source),
        "action": action,
        "canonical_term": canonical_term,
        "term_kind": term_kind,
        "broader": broader or [],
        "curation_status": curation_status,
        "compound_reason": compound_reason,
        "output_path": output_path,
    }


def import_qwen_dictionary(source_path: Path, overrides_path: Path, output_root: Path, manifest_path: Path) -> dict[str, Any]:
    source_rows = load_jsonl(source_path)
    overrides = load_overrides(overrides_path)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    selected_count = 0
    needs_parent_count = 0
    excluded_count = 0

    for source in source_rows:
        source_term = str(source.get("term") or "").strip()
        override = overrides.get(source_term)
        if not override:
            if is_compound_bundle(source_term):
                needs_parent_count += 1
                manifest_rows.append(
                    manifest_row(
                        source,
                        action="needs_parent_curation",
                        curation_status="needs_parent_curation",
                        compound_reason="slash/numeric bundle requires parent curation before public canonical promotion",
                    )
                )
                continue
            override = {"action": "keep", "canonical_term": source_term, "term_kind": source.get("term_kind") or "concept", "curation_status": "selected"}

        action = str(override.get("action") or "keep")
        if action in {"exclude", "exclude_from_public", "alias_to_existing", "needs_parent_curation"}:
            if action == "needs_parent_curation":
                needs_parent_count += 1
            else:
                excluded_count += 1
            manifest_rows.append(
                manifest_row(
                    source,
                    action=action,
                    canonical_term=str(override.get("canonical_term") or ""),
                    term_kind=str(override.get("term_kind") or ""),
                    curation_status=str(override.get("curation_status") or action),
                    compound_reason=str(override.get("compound_reason") or ""),
                    broader=list_values(override.get("broader")),
                )
            )
            continue

        canonical_terms = list_values(override.get("canonical_terms")) if action == "split_into_terms" else [str(override.get("canonical_term") or source_term)]
        for canonical_term in canonical_terms:
            if not canonical_term:
                continue
            metadata = metadata_for_term(source, override, canonical_term=canonical_term, action=action)
            output_path = output_root / f"{slugify(canonical_term)}.md"
            output_path.write_text(dictionary_markdown(metadata, str(metadata["source_refs"][0]["ref"])), encoding="utf-8")
            selected_count += 1
            manifest_rows.append(
                manifest_row(
                    source,
                    action=action,
                    canonical_term=canonical_term,
                    term_kind=str(metadata.get("term_kind") or ""),
                    curation_status=str(metadata.get("curation_status") or "curated"),
                    compound_reason=str(metadata.get("compound_reason") or ""),
                    output_path=str(output_path),
                    broader=list_values(metadata.get("broader")),
                )
            )

    manifest_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in manifest_rows) + ("\n" if manifest_rows else ""), encoding="utf-8")
    return {
        "ok": True,
        "source_count": len(source_rows),
        "selected_count": selected_count,
        "needs_parent_curation_count": needs_parent_count,
        "excluded_count": excluded_count,
        "manifest_path": str(manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Qwen-derived dictionary terms with curation overrides.")
    parser.add_argument("--source", type=Path, default=Path("data/qwen_dictionary/source_terms.jsonl"))
    parser.add_argument("--overrides", type=Path, default=Path("data/qwen_dictionary/curation_overrides.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path("data/boi/public/dictionary"))
    parser.add_argument("--manifest", type=Path, default=Path("data/qwen_dictionary/import_manifest.jsonl"))
    args = parser.parse_args()
    result = import_qwen_dictionary(args.source, args.overrides, args.output_root, args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
