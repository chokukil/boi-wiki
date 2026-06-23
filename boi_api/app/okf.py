from __future__ import annotations

import json
import re
import hashlib
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
VALID_RETENTION_CLASSES = {"ephemeral", "working", "record", "promoted_source"}
VALID_ARCHIVE_STATUSES = {"active", "archived", "exported", "deleted"}
VALID_SENSITIVE_FLAGS = {"unknown", "yes", "no"}
RESERVED_FILENAMES = {"index.md", "log.md"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
ALLOWED_MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


@dataclass
class OkfLintResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_markdown_count: int = 0
    checked_log_item_count: int = 0
    markdown_link_count: int = 0
    media_link_count: int = 0
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
    if metadata.get("retention_class") and metadata.get("retention_class") not in VALID_RETENTION_CLASSES:
        errors.append("retention_class must be ephemeral/working/record/promoted_source")
    if metadata.get("archive_status") and metadata.get("archive_status") not in VALID_ARCHIVE_STATUSES:
        errors.append("archive_status must be active/archived/exported/deleted")
    if metadata.get("contains_sensitive") and metadata.get("contains_sensitive") not in VALID_SENSITIVE_FLAGS:
        errors.append("contains_sensitive must be unknown/yes/no")
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


def validate_boi_profile_path_acl(metadata: dict[str, Any], path: Path, boi_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        parts = path.resolve().relative_to(boi_root.resolve()).parts
    except ValueError:
        return ["BoI path must be under boi root"]
    visibility = str(metadata.get("visibility") or "")
    owner = str(metadata.get("owner") or "")
    raw_acl_policy = metadata.get("acl_policy")
    acl_policy = raw_acl_policy if isinstance(raw_acl_policy, str) else ""
    if visibility == "private":
        if len(parts) < 3 or parts[0] != "private" or not re.fullmatch(r"\d{6,7}", parts[1]):
            errors.append("private BoI must live under data/boi/private/{numeric-employee-id}/")
        else:
            employee_id = parts[1]
            if owner != employee_id:
                errors.append("private BoI owner must match path employee_id")
            if acl_policy and acl_policy != f"acl:private:{employee_id}":
                errors.append("private BoI acl_policy must match acl:private:{employee_id}")
    elif visibility == "team":
        if len(parts) < 3 or parts[0] != "team" or not parts[1]:
            errors.append("team BoI must live under data/boi/team/{team_id}/")
        else:
            path_team_id = parts[1]
            if str(metadata.get("team_id") or "") and str(metadata.get("team_id")) != parts[1]:
                errors.append("team BoI team_id must match path team_id")
            if acl_policy and acl_policy != f"acl:team:{path_team_id}":
                errors.append("team BoI acl_policy must match acl:team:{team_id}")
    elif visibility == "public":
        if not parts or parts[0] != "public":
            errors.append("public BoI must live under data/boi/public/")
        if acl_policy and acl_policy != "acl:public":
            errors.append("public BoI acl_policy must be acl:public")
    return errors


def concept_id_for_path(path: Path, boi_root: Path) -> str:
    return str(path.relative_to(boi_root).with_suffix("")).replace("\\", "/")


def is_external_href(href: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href)) or href.startswith("#")


def is_okf_concept_href(href: str) -> bool:
    href_without_fragment = str(href or "").split("#", 1)[0].split("?", 1)[0].strip()
    if not href_without_fragment or is_external_href(href_without_fragment):
        return False
    if href_without_fragment.startswith("/"):
        return href_without_fragment.startswith(("/public/", "/team/", "/private/")) and href_without_fragment.endswith(".md")
    return href_without_fragment.endswith(".md")


def markdown_without_fenced_code(body: str) -> str:
    return re.sub(r"```.*?```", "", body, flags=re.DOTALL)


def extract_markdown_links(body: str) -> list[dict[str, str]]:
    body = markdown_without_fenced_code(body)
    return [{"label": m.group(1), "href": m.group(2)} for m in MARKDOWN_LINK_RE.finditer(body)]


def extract_markdown_images(body: str) -> list[dict[str, str]]:
    body = markdown_without_fenced_code(body)
    return [{"alt": m.group(1), "href": m.group(2)} for m in MARKDOWN_IMAGE_RE.finditer(body)]


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
        if not is_okf_concept_href(href):
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


def resolve_okf_media_path(href: str, *, source_path: Path, boi_root: Path) -> tuple[Path | None, str | None]:
    href_without_fragment = href.split("#", 1)[0]
    if is_external_href(href_without_fragment) or not href_without_fragment:
        return None, None
    if Path(href_without_fragment).suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
        return None, f"image link has unsupported extension: {href}"
    if href_without_fragment.startswith("/"):
        target_path = boi_root / href_without_fragment.lstrip("/")
    else:
        target_path = source_path.parent / href_without_fragment
    target_path = target_path.resolve()
    root = boi_root.resolve()
    try:
        target_path.relative_to(root)
    except ValueError:
        return None, f"image link escapes OKF bundle: {href}"
    if "_media" not in target_path.parts:
        return None, f"image link must target a _media directory: {href}"
    return target_path, None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_media_manifest(boi_root: Path) -> dict[str, dict[str, Any]]:
    manifest_by_path: dict[str, dict[str, Any]] = {}
    for manifest_path in sorted(boi_root.rglob("media-manifest.yaml")):
        if "_media" not in manifest_path.parts:
            continue
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        items = data.get("media") if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            manifest_by_path[str(item["path"]).lstrip("/")] = item
    return manifest_by_path


def lint_media_links(path: Path, body: str, boi_root: Path, strict_media: bool = False) -> list[str]:
    errors: list[str] = []
    root = boi_root.resolve()
    manifest = load_media_manifest(root) if strict_media else {}
    for image in extract_markdown_images(body):
        href = image["href"]
        target_path, error = resolve_okf_media_path(href, source_path=path, boi_root=boi_root)
        if error:
            errors.append(error)
            continue
        if target_path is None:
            continue
        if not target_path.exists():
            errors.append(f"image link target does not exist: {href}")
            continue
        if not strict_media:
            continue
        rel_path = str(target_path.relative_to(root)).replace("\\", "/")
        manifest_item = manifest.get(rel_path)
        if not manifest_item:
            errors.append(f"image asset missing from media manifest: /{rel_path}")
            continue
        expected_sha = str(manifest_item.get("sha256") or "")
        actual_sha = file_sha256(target_path)
        if expected_sha and expected_sha != actual_sha:
            errors.append(f"image asset sha256 mismatch: /{rel_path}")
    return errors


def lint_media_assets(boi_root: Path, strict_media: bool = False) -> list[str]:
    errors: list[str] = []
    seen_hashes: dict[str, str] = {}
    root = boi_root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "_media" not in path.parts:
            continue
        if path.name == "media-manifest.yaml":
            continue
        if path.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
            errors.append(f"unsupported media asset extension: {path}")
            continue
        digest = file_sha256(path)
        rel_path = str(path.relative_to(root)).replace("\\", "/")
        existing = seen_hashes.get(digest)
        if existing and existing != rel_path and strict_media:
            errors.append(f"duplicate media asset content: /{existing} and /{rel_path}")
        seen_hashes.setdefault(digest, rel_path)
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


def lint_reserved_markdown_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        return [f"reserved {path.name} must be directory listing, not BoI concept frontmatter"]
    if path.name == "log.md":
        for line in text.splitlines():
            if line.startswith("## ") and not re.match(r"^## \d{4}-\d{2}-\d{2}\b", line):
                return ["log.md date headings must use YYYY-MM-DD"]
    return []


def lint_markdown_file(
    path: Path,
    boi_root: Path | None = None,
    strict_links: bool = False,
    strict_media: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    if path.name in RESERVED_FILENAMES:
        return lint_reserved_markdown_file(path), []
    boi_root = boi_root or path.parents[0]
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if not metadata:
        return ["missing YAML frontmatter"], []
    errors = (
        validate_okf_core_metadata(metadata)
        + validate_boi_profile_metadata(metadata)
        + validate_boi_profile_path_acl(metadata, path, boi_root)
    )
    edges = markdown_link_edges(path, body, boi_root)
    if strict_links:
        errors.extend(f"unresolved OKF markdown link: {edge['href']}" for edge in edges if not edge["resolved"])
    errors.extend(lint_media_links(path, body, boi_root, strict_media=strict_media))
    return errors, edges


def materialized_item_acl_errors(item: dict[str, Any], boi_root: Path) -> list[str]:
    metadata = item.get("metadata") or {}
    uri = str(item.get("uri") or "").strip()
    if not uri:
        return ["materialized BoI requires uri for ACL path validation"]
    uri_path = uri.split("#", 1)[0].split("?", 1)[0].lstrip("/")
    if not uri_path:
        return ["materialized BoI uri is empty after normalization"]
    path = boi_root / uri_path
    if path.suffix != ".md":
        path = path.with_suffix(".md")
    return validate_boi_profile_path_acl(metadata, path, boi_root)


def lint_data_root(
    root: Path,
    include_logs: bool = False,
    strict_links: bool = False,
    strict_media: bool = False,
) -> OkfLintResult:
    root = Path(root)
    result = OkfLintResult()
    boi_root = root / "boi"
    for path in sorted(boi_root.rglob("*.md")):
        result.checked_markdown_count += 1
        errors, edges = lint_markdown_file(path, boi_root=boi_root, strict_links=strict_links, strict_media=strict_media)
        result.extend(str(path), errors)
        result.link_edges.extend(edges)
        result.markdown_link_count += len(edges)
        try:
            _metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
            result.media_link_count += len(extract_markdown_images(body))
        except Exception:
            pass
    result.errors.extend(lint_media_assets(boi_root, strict_media=strict_media))
    if include_logs:
        for log_root_name in ("events", "actions"):
            for path in sorted((root / log_root_name).glob("*.jsonl")):
                for row_index, row in enumerate(iter_jsonl_rows(path), start=1):
                    for item_index, item in enumerate(iter_materialized_items(row), start=1):
                        result.checked_log_item_count += 1
                        metadata = item.get("metadata") or {}
                        prefix = f"{path}:{row_index}:materialized_item:{item_index}"
                        result.extend(prefix, validate_boi_profile_metadata(metadata) + materialized_item_acl_errors(item, boi_root))
                        body = item.get("body") or ""
                        if isinstance(body, str):
                            item_uri = str(item.get("uri") or "").strip("/")
                            source_concept = item_uri[:-3] if item_uri.endswith(".md") else item_uri or prefix
                            edges = markdown_link_edges(path, body, boi_root=boi_root, source_concept_id=source_concept)
                            result.link_edges.extend(edges)
                            result.markdown_link_count += len(edges)
    return result
