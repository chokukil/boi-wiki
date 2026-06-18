from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

REQUIRED_FIELDS = [
    "okf_version",
    "boi_profile_version",
    "type",
    "title",
    "description",
    "timestamp",
    "boi_id",
    "visibility",
    "classification",
    "owner",
    "acl_policy",
    "status",
]

VALID_VISIBILITIES = {"private", "team", "public"}
VALID_STATUSES = {"draft", "reviewed", "approved", "deprecated"}
RESERVED_FILENAMES = {"index.md", "log.md"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass
class OkfLintResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_markdown_count: int = 0
    checked_log_item_count: int = 0
    markdown_link_count: int = 0
    link_edges: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, prefix: str, errors: list[str]) -> None:
        self.errors.extend(f"{prefix}: {error}" for error in errors)


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if not markdown.startswith("---"):
        return {}, markdown
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    return yaml.safe_load(parts[1]) or {}, parts[2]


def validate_okf_core_metadata(metadata: dict[str, Any]) -> list[str]:
    if not metadata.get("type"):
        return ["missing required OKF core metadata: type"]
    return []


def validate_boi_profile_metadata(metadata: dict[str, Any], promotion: bool = False) -> list[str]:
    errors: list[str] = []
    for field_name in REQUIRED_FIELDS:
        if field_name not in metadata or metadata[field_name] in (None, ""):
            errors.append(f"missing required metadata: {field_name}")
    if metadata.get("visibility") not in VALID_VISIBILITIES:
        errors.append("visibility must be private/team/public")
    if metadata.get("status") not in VALID_STATUSES:
        errors.append("status must be draft/reviewed/approved/deprecated")
    if metadata.get("visibility") in {"team", "public"} or promotion:
        if not metadata.get("source_refs"):
            errors.append("team/public BoI requires source_refs")
        review = metadata.get("review") or {}
        if not review.get("reviewer") and not metadata.get("reviewer"):
            errors.append("team/public BoI requires reviewer")
        if metadata.get("status") == "approved" and not review.get("reviewed_at"):
            errors.append("approved BoI requires review.reviewed_at")
    return errors


def validate_okf_metadata(metadata: dict[str, Any], promotion: bool = False) -> list[str]:
    """Backward-compatible BoI Profile validation entrypoint."""
    return validate_boi_profile_metadata(metadata, promotion=promotion)


def concept_id_for_path(path: Path, boi_root: Path) -> str:
    return str(path.relative_to(boi_root).with_suffix("")).replace("\\", "/")


def is_external_href(href: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href)) or href.startswith("#")


def extract_markdown_links(body: str) -> list[dict[str, str]]:
    return [{"label": m.group(1), "href": m.group(2)} for m in MARKDOWN_LINK_RE.finditer(body)]


def resolve_okf_link(href: str, *, source_path: Path, boi_root: Path) -> tuple[str, bool]:
    href_without_fragment = href.split("#", 1)[0]
    if is_external_href(href_without_fragment) or not href_without_fragment:
        return href, False
    if href_without_fragment.startswith("/"):
        target_path = boi_root / href_without_fragment.lstrip("/")
    else:
        target_path = source_path.parent / href_without_fragment
    target_path = target_path.resolve()
    root = boi_root.resolve()
    try:
        target_path.relative_to(root)
    except ValueError:
        return href, False
    if target_path.suffix != ".md":
        target_path = target_path / "index.md" if target_path.is_dir() else target_path.with_suffix(".md")
    if target_path.exists() and target_path.name not in RESERVED_FILENAMES:
        return concept_id_for_path(target_path, root), True
    try:
        return str(target_path.relative_to(root).with_suffix("")).replace("\\", "/"), False
    except ValueError:
        return href, False


def markdown_link_edges(path: Path, body: str, boi_root: Path, source_concept_id: str | None = None) -> list[dict[str, Any]]:
    source = source_concept_id or concept_id_for_path(path, boi_root)
    edges = []
    for link in extract_markdown_links(body):
        href = link["href"]
        if is_external_href(href):
            continue
        target, resolved = resolve_okf_link(href, source_path=path, boi_root=boi_root)
        edges.append(
            {
                "source": source,
                "target": target,
                "href": href,
                "label": link["label"],
                "resolved": resolved,
            }
        )
    return edges


def materialized_item_from_action_result(result: dict[str, Any]) -> dict[str, Any] | None:
    response = result.get("response")
    if not isinstance(response, dict):
        return None
    item = response.get("item")
    if not isinstance(item, dict):
        return None
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        return None
    return item


def iter_materialized_items(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        item = materialized_item_from_action_result(value)
        if item is not None:
            yield item
        for child in value.values():
            yield from iter_materialized_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_materialized_items(child)


def iter_jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def lint_reserved_markdown_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        return [f"reserved {path.name} must be directory listing, not BoI concept frontmatter"]
    if path.name == "log.md":
        for line in text.splitlines():
            if line.startswith("## ") and not re.match(r"^## \d{4}-\d{2}-\d{2}\b", line):
                return ["log.md date headings must use YYYY-MM-DD"]
    return []


def lint_markdown_file(path: Path, boi_root: Path | None = None, strict_links: bool = False) -> tuple[list[str], list[dict[str, Any]]]:
    if path.name in RESERVED_FILENAMES:
        return lint_reserved_markdown_file(path), []
    boi_root = boi_root or path.parents[0]
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not metadata:
        return ["missing YAML frontmatter"], []
    errors = validate_okf_core_metadata(metadata) + validate_boi_profile_metadata(metadata)
    edges = markdown_link_edges(path, body, boi_root)
    if strict_links:
        errors.extend(f"unresolved OKF markdown link: {edge['href']}" for edge in edges if not edge["resolved"])
    return errors, edges


def lint_data_root(root: Path, include_logs: bool = False, strict_links: bool = False) -> OkfLintResult:
    root = Path(root)
    result = OkfLintResult()
    boi_root = root / "boi"
    for path in sorted(boi_root.rglob("*.md")):
        result.checked_markdown_count += 1
        errors, edges = lint_markdown_file(path, boi_root=boi_root, strict_links=strict_links)
        result.extend(str(path), errors)
        result.link_edges.extend(edges)
        result.markdown_link_count += len(edges)
    if include_logs:
        for log_root_name in ("events", "actions"):
            for path in sorted((root / log_root_name).glob("*.jsonl")):
                for row_index, row in enumerate(iter_jsonl_rows(path), start=1):
                    for item_index, item in enumerate(iter_materialized_items(row), start=1):
                        result.checked_log_item_count += 1
                        metadata = item.get("metadata") or {}
                        prefix = f"{path}:{row_index}:materialized_item:{item_index}"
                        result.extend(prefix, validate_boi_profile_metadata(metadata))
                        body = item.get("body") or ""
                        if isinstance(body, str):
                            item_uri = str(item.get("uri") or "").strip("/")
                            source_concept = item_uri[:-3] if item_uri.endswith(".md") else item_uri or prefix
                            edges = markdown_link_edges(path, body, boi_root=boi_root, source_concept_id=source_concept)
                            result.link_edges.extend(edges)
                            result.markdown_link_count += len(edges)
    return result
