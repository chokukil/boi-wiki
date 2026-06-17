from __future__ import annotations

import json
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


@dataclass
class OkfLintResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_markdown_count: int = 0
    checked_log_item_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, prefix: str, errors: list[str]) -> None:
        self.errors.extend(f"{prefix}: {error}" for error in errors)


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown
    return yaml.safe_load(parts[1]) or {}, parts[2]


def validate_okf_metadata(metadata: dict[str, Any], promotion: bool = False) -> list[str]:
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


def lint_markdown_file(path: Path) -> list[str]:
    metadata, _body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not metadata:
        return ["missing YAML frontmatter"]
    return validate_okf_metadata(metadata)


def lint_data_root(root: Path, include_logs: bool = False) -> OkfLintResult:
    root = Path(root)
    result = OkfLintResult()
    boi_root = root / "boi"
    for path in sorted(boi_root.rglob("*.md")):
        result.checked_markdown_count += 1
        result.extend(str(path), lint_markdown_file(path))
    if include_logs:
        for log_root_name in ("events", "actions"):
            for path in sorted((root / log_root_name).glob("*.jsonl")):
                for row_index, row in enumerate(iter_jsonl_rows(path), start=1):
                    for item_index, item in enumerate(iter_materialized_items(row), start=1):
                        result.checked_log_item_count += 1
                        metadata = item.get("metadata") or {}
                        prefix = f"{path}:{row_index}:materialized_item:{item_index}"
                        result.extend(prefix, validate_okf_metadata(metadata))
    return result
