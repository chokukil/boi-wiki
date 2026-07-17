"""HTML 공유 + 단축주소(Phase 1) 로직 모듈.

docs/HTML_SHARE_AND_META_HARNESS_PLAN.md §4.2~4.4 구현.
main.py에는 라우트 등록/글루만 두고, 이름 정책·레지스트리·저장 경로·ACL·업로드 검증은
전부 이 모듈에 둔다. (main.py 비대화 방지 — 계획서 §8)
"""

from __future__ import annotations

import copy
import json
import re
import threading
from pathlib import Path
from typing import Any, Pattern

import yaml

from .okf import HTML_PROFILE_SCRIPT_RE, parse_html_profile

SHORTLINK_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

# 루트 catch-all(GET /{name})과 충돌하는 모든 루트 경로 세그먼트 + 성장 예약분.
# 새 루트 라우트를 추가하면 이 목록도 함께 갱신해야 하며,
# tests/test_html_share.py의 route-collision 테스트가 누락을 강제로 잡아낸다.
RESERVED_SHORTLINK_NAMES = frozenset(
    {
        # 현재 등록된 루트 세그먼트
        "health",
        "inbox",
        "ops",
        "events",
        "actions",
        "sops",
        "source",
        "permissions",
        "capabilities",
        "event-types",
        "api",
        "static",
        "docs",
        "auth",
        "okf-media",
        "sop-runs",
        "workflows",
        "agents",
        "openapi.json",
        "redoc",
        "share",
        "r",
        # 성장 예약분
        "go",
        "raw",
        "html",
        "s",
        "link",
        "login",
        "logout",
        "admin",
        "search",
        "mcp",
        "files",
        "new",
        "me",
        "favicon.ico",
        "robots.txt",
    }
)

HTML_SHARE_MAX_BYTES = 20 * 1024 * 1024
HTML_SHARE_SUBFOLDER = "html"

_REGISTRY_LOCK = threading.Lock()
_REGISTRY_CACHE: dict[str, tuple[tuple[int, int], list[dict[str, Any]]]] = {}


def normalize_share_name(value: str) -> str:
    return str(value or "").strip().lower()


def suggest_share_name(filename: str, fallback: str = "shared-html") -> str:
    stem = Path(str(filename or "")).stem
    slug = re.sub(r"[^a-z0-9]+", "-", stem.strip().lower()).strip("-")
    slug = slug[:64].strip("-")
    if not SHORTLINK_NAME_RE.match(slug) or slug in RESERVED_SHORTLINK_NAMES:
        return fallback
    return slug


def share_name_error(name: str) -> str:
    normalized = normalize_share_name(name)
    if normalized in RESERVED_SHORTLINK_NAMES:
        return f"'{normalized}'은(는) BoI Wiki가 예약한 주소라 사용할 수 없습니다. 다른 이름을 선택해주세요."
    if not SHORTLINK_NAME_RE.match(normalized):
        return "단축주소 이름은 영문 소문자 또는 숫자로 시작하고, 소문자·숫자·하이픈(-)으로만 이루어진 2~64자여야 합니다."
    return ""


def _registry_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def registry_load(path: Path) -> list[dict[str, Any]]:
    key = str(path)
    signature = _registry_signature(path)
    with _REGISTRY_LOCK:
        cached = _REGISTRY_CACHE.get(key)
        if cached is not None and signature is not None and cached[0] == signature:
            return copy.deepcopy(cached[1])
    if signature is None:
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    records = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    with _REGISTRY_LOCK:
        _REGISTRY_CACHE[key] = (signature, copy.deepcopy(records))
    return records


def registry_save(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    signature = _registry_signature(path)
    with _REGISTRY_LOCK:
        if signature is not None:
            _REGISTRY_CACHE[str(path)] = (signature, copy.deepcopy(records))
        else:
            _REGISTRY_CACHE.pop(str(path), None)


def registry_find(records: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    normalized = normalize_share_name(name)
    for record in records:
        if normalize_share_name(str(record.get("name") or "")) == normalized:
            return record
    return None


def registry_upsert(path: Path, record: dict[str, Any]) -> None:
    with _REGISTRY_LOCK:
        _REGISTRY_CACHE.pop(str(path), None)
    records = registry_load(path)
    normalized = normalize_share_name(str(record.get("name") or ""))
    replaced = False
    for index, existing in enumerate(records):
        if normalize_share_name(str(existing.get("name") or "")) == normalized:
            records[index] = record
            replaced = True
            break
    if not replaced:
        records.append(record)
    registry_save(path, records)


def registry_tombstone(path: Path, name: str, now: str) -> dict[str, Any] | None:
    records = registry_load(path)
    record = registry_find(records, name)
    if record is None:
        return None
    record["status"] = "tombstone"
    record["updated_at"] = now
    registry_save(path, records)
    return record


def build_shortlink_record(
    *,
    name: str,
    target_kind: str,
    target: str,
    owner_employee_id: str,
    visibility: str,
    team_id: str,
    title: str,
    description: str,
    now: str,
    created_at: str = "",
) -> dict[str, Any]:
    return {
        "name": normalize_share_name(name),
        "target_kind": target_kind,
        "target": target,
        "owner_employee_id": owner_employee_id,
        "visibility": visibility,
        "team_id": team_id,
        "title": title,
        "description": description,
        "created_at": created_at or now,
        "updated_at": now,
        "status": "active",
    }


def shortlink_name_status(records: list[dict[str, Any]], name: str, employee_id: str) -> str:
    normalized = normalize_share_name(name)
    if normalized in RESERVED_SHORTLINK_NAMES:
        return "reserved"
    if not SHORTLINK_NAME_RE.match(normalized):
        return "invalid"
    record = registry_find(records, normalized)
    if record is None:
        return "available"
    if str(record.get("status") or "") == "tombstone":
        return "tombstone"
    if str(record.get("owner_employee_id") or "") == employee_id:
        return "owned_by_me"
    return "taken"


def suggested_alternative_names(records: list[dict[str, Any]], base_name: str, count: int = 3) -> list[str]:
    normalized = normalize_share_name(base_name)
    used = {normalize_share_name(str(record.get("name") or "")) for record in records}
    suggestions: list[str] = []
    suffix_index = 2
    while len(suggestions) < count and suffix_index < 100:
        suffix = f"-{suffix_index}"
        candidate = f"{normalized[: 64 - len(suffix)].rstrip('-')}{suffix}"
        suffix_index += 1
        if not SHORTLINK_NAME_RE.match(candidate) or candidate in RESERVED_SHORTLINK_NAMES:
            continue
        if candidate in used:
            continue
        suggestions.append(candidate)
    return suggestions


def share_boi_id(visibility: str, name: str, *, employee_id: str = "", team_id: str = "") -> str:
    normalized = normalize_share_name(name)
    if visibility == "team":
        return f"boi:team:{team_id}:html:{normalized}"
    if visibility == "private":
        return f"boi:private:{employee_id}:html:{normalized}"
    return f"boi:public:html:{normalized}"


def share_acl_policy(visibility: str, *, employee_id: str = "", team_id: str = "") -> str:
    if visibility == "team":
        return f"acl:team:{team_id}"
    if visibility == "private":
        return f"acl:private:{employee_id}"
    return "acl:public"


def share_card_description(title: str, description: str) -> str:
    text = str(description or "").strip()
    if text:
        return text
    return f"'{str(title or '').strip() or '공유 HTML'}' 공유 HTML 문서"


def html_storage_path(data_root: Path, visibility: str, name: str, *, employee_id: str = "", team_id: str = "") -> Path:
    normalized = normalize_share_name(name)
    if not SHORTLINK_NAME_RE.match(normalized):
        raise ValueError("invalid shortlink name")
    if visibility == "public":
        relative = Path("public") / HTML_SHARE_SUBFOLDER / f"{normalized}.html"
    elif visibility == "team":
        if not team_id:
            raise ValueError("team_id is required for team visibility")
        relative = Path("team") / team_id / HTML_SHARE_SUBFOLDER / f"{normalized}.html"
    elif visibility == "private":
        if not employee_id:
            raise ValueError("employee_id is required for private visibility")
        relative = Path("private") / employee_id / HTML_SHARE_SUBFOLDER / f"{normalized}.html"
    else:
        raise ValueError(f"unknown visibility: {visibility}")
    target_path = (Path(data_root) / relative).resolve()
    # /okf-media와 동일한 경로 탈출 방지 패턴: data_root 밖으로 나가면 거부.
    target_path.relative_to(Path(data_root).resolve())
    return target_path


def storage_path_for_record(data_root: Path, record: dict[str, Any]) -> Path:
    return html_storage_path(
        data_root,
        str(record.get("visibility") or "public"),
        str(record.get("name") or ""),
        employee_id=str(record.get("owner_employee_id") or ""),
        team_id=str(record.get("team_id") or ""),
    )


def looks_like_html(content: bytes, content_type: str) -> bool:
    if str(content_type or "").lower().split(";")[0].strip() == "text/html":
        return True
    head = content[:65536].decode("utf-8", errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head


def validate_html_upload(content: bytes, content_type: str, secret_pattern: Pattern[str]) -> tuple[int, str] | None:
    if not content:
        return (400, "업로드된 파일이 비어 있습니다. HTML 파일을 선택한 뒤 다시 시도해주세요.")
    if len(content) > HTML_SHARE_MAX_BYTES:
        return (413, "HTML 파일은 20MB 이하만 업로드할 수 있습니다.")
    if not looks_like_html(content, content_type):
        return (400, "HTML 파일이 아닙니다. <html> 태그 또는 <!doctype html> 선언이 포함된 self-contained HTML 파일만 업로드할 수 있습니다.")
    text = content.decode("utf-8", errors="ignore")
    if secret_pattern.search(text):
        return (400, "API key/token/password로 보이는 비밀 값이 포함되어 있어 업로드할 수 없습니다. 비밀 값을 제거한 뒤 다시 업로드해주세요.")
    return None


def can_read_share(record: dict[str, Any], *, employee_id: str, teams: list[str]) -> bool:
    visibility = str(record.get("visibility") or "public")
    if visibility == "public":
        return True
    if visibility == "team":
        return str(record.get("team_id") or "") in set(teams)
    if visibility == "private":
        return str(record.get("owner_employee_id") or "") == employee_id
    return False


def share_record_view(record: dict[str, Any]) -> dict[str, Any]:
    name = normalize_share_name(str(record.get("name") or ""))
    return {
        "name": name,
        "url": f"/{name}",
        "raw_url": f"/r/{name}",
        "target_kind": str(record.get("target_kind") or "html"),
        "title": str(record.get("title") or name),
        "description": str(record.get("description") or ""),
        "owner_employee_id": str(record.get("owner_employee_id") or ""),
        "visibility": str(record.get("visibility") or "public"),
        "team_id": str(record.get("team_id") or ""),
        "created_at": str(record.get("created_at") or ""),
        "updated_at": str(record.get("updated_at") or ""),
        "status": str(record.get("status") or "active"),
    }


# --- Phase 2: BoI HTML Profile(JSON-LD) + 지식 카드 (계획서 §4.1) ---------------
# 공유 HTML은 보고서/대시보드/가이드 등 무엇이든 담을 수 있는 일반 문서다.
# HTML 자체는 내장 BoI HTML Profile로 단독 식별·검증되고,
# 지식 그래프 정본은 같은 이름의 지식 카드(.md)가 대표한다.


def build_html_profile_jsonld(
    *,
    name: str,
    title: str,
    description: str,
    visibility: str,
    team_id: str,
    owner: str,
    owner_employee_id: str,
    reviewer: str,
    timestamp: str,
    original_filename: str,
    original_sha256: str,
) -> dict[str, Any]:
    """Markdown frontmatter와 같은 BoI Profile 필드를 schema.org JSON-LD로 직렬화한다."""
    normalized = normalize_share_name(name)
    card_description = share_card_description(title, description)
    boi_profile: dict[str, Any] = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/html-document",
        "title": str(title or normalized),
        "description": card_description,
        "timestamp": timestamp,
        "boi_id": share_boi_id(visibility, normalized, employee_id=owner_employee_id, team_id=team_id),
        "visibility": visibility,
        "classification": "internal",
        "owner": owner,
        "acl_policy": share_acl_policy(visibility, employee_id=owner_employee_id, team_id=team_id),
        "status": "reviewed",
        "content_role": "html_artifact",
        "shortlink": f"/{normalized}",
        "review": {"reviewer": reviewer, "review_status": "user_confirmed"},
        "source_refs": [
            {
                "type": "upload",
                "ref": str(original_filename or f"{normalized}.html"),
                "uploaded_by": owner_employee_id,
                "sha256": original_sha256,
            }
        ],
    }
    if visibility == "team":
        boi_profile["team_id"] = team_id
    return {
        "@context": "https://schema.org",
        "@type": "DigitalDocument",
        "name": boi_profile["title"],
        "description": card_description,
        "dateModified": timestamp,
        "boiProfile": boi_profile,
    }


def inject_html_profile(content: str, payload: dict[str, Any]) -> str:
    """단일 <script type="application/ld+json" id="boi-profile"> 블록을 <head>에 주입한다.

    재업로드 시 기존 boi-profile 블록은 모두 제거 후 다시 넣어 중복을 막고,
    나머지 문서는 그대로 보존한다. (json.dumps가 "</"를 "<\\/"로 이스케이프해
    </script> 조기 종료를 막는다.)
    """
    block = (
        '<script type="application/ld+json" id="boi-profile">'
        + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        + "</script>"
    )
    text = HTML_PROFILE_SCRIPT_RE.sub("", str(content or ""))
    head_match = re.search(r"<head\b[^>]*>", text, flags=re.IGNORECASE)
    if head_match:
        index = head_match.end()
        return text[:index] + "\n" + block + text[index:]
    html_match = re.search(r"<html\b[^>]*>", text, flags=re.IGNORECASE)
    if html_match:
        index = html_match.end()
        return text[:index] + "\n<head>" + block + "</head>" + text[index:]
    return "<head>" + block + "</head>\n" + text


def extract_html_profile(content: str) -> dict[str, Any] | None:
    """주입된 BoI HTML Profile 블록을 관대하게 파싱한다. (okf.parse_html_profile 재사용)"""
    return parse_html_profile(content)


def build_knowledge_card_markdown(
    *,
    name: str,
    title: str,
    description: str,
    visibility: str,
    team_id: str,
    owner: str,
    owner_label: str,
    owner_employee_id: str,
    created_at: str,
    updated_at: str,
    original_filename: str,
    original_sha256: str,
    stored_sha256: str,
    html_repo_path: str,
    analysis: dict[str, Any] | None = None,
) -> str:
    """공유 HTML 옆에 놓이는 지식 카드(.md)를 생성한다.

    카드가 정본 boi_id를 소유하며(콜론→경로 매핑이 이 .md로 자연 해석됨),
    검색·링크 그래프·신선도·promotion 루프에는 카드가 HTML을 대표한다.
    analysis(loops.analyze_html_content 결과, 결정적·LLM 없음)가 주어지면
    `# 자동 분석` 섹션과 사전 기반 tags를 함께 기록한다.
    """
    from . import loops as wiki_loops

    normalized = normalize_share_name(name)
    card_title = str(title or normalized)
    card_description = share_card_description(card_title, description)
    card_tags = wiki_loops.analysis_tags(analysis) if analysis else ["HTML", "Share"]
    metadata: dict[str, Any] = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/html-document",
        "title": card_title,
        "description": card_description,
        "tags": card_tags,
        "timestamp": created_at,
        "boi_id": share_boi_id(visibility, normalized, employee_id=owner_employee_id, team_id=team_id),
        "visibility": visibility,
        "classification": "internal",
        "owner": owner,
        "acl_policy": share_acl_policy(visibility, employee_id=owner_employee_id, team_id=team_id),
        "status": "reviewed",
        "review": {"reviewer": owner_label, "review_status": "user_confirmed"},
        "source_refs": [
            {"type": "html_artifact", "ref": html_repo_path, "sha256": stored_sha256},
            {
                "type": "upload",
                "ref": str(original_filename or f"{normalized}.html"),
                "uploaded_by": owner_employee_id,
                "sha256": original_sha256,
            },
        ],
    }
    if visibility == "team":
        metadata["team_id"] = team_id
    analysis_section = (wiki_loops.render_analysis_section(analysis).rstrip("\n") + "\n\n") if analysis else ""
    body = (
        "# Summary\n\n"
        f"{card_description}\n\n"
        "보고서, 대시보드, 가이드 등 무엇이든 담을 수 있는 self-contained 공유 HTML 문서입니다. "
        "이 카드는 업로드 시 자동 생성되어 검색과 지식 그래프에서 해당 HTML 문서를 대표합니다.\n\n"
        "# 링크\n\n"
        f"- 뷰어: [/{normalized}](/{normalized})\n"
        f"- 원본 HTML: [/r/{normalized}](/r/{normalized})\n\n"
        "# 출처\n\n"
        f"- 업로더: {owner_label}\n"
        f"- 원본 파일명: {original_filename or f'{normalized}.html'}\n"
        f"- 갱신 시각: {updated_at}\n\n"
        + analysis_section
        + "# Citations\n\n"
        f"- HTML 파일: `{html_repo_path}`\n"
    )
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body
