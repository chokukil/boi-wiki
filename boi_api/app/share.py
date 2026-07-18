"""HTML 공유 + 단축주소(Phase 1) 로직 모듈.

docs/HTML_SHARE_AND_META_HARNESS_PLAN.md §4.2~4.4 구현.
main.py에는 라우트 등록/글루만 두고, 이름 정책·레지스트리·저장 경로·ACL·업로드 검증은
전부 이 모듈에 둔다. (main.py 비대화 방지 — 계획서 §8)
"""

from __future__ import annotations

import contextlib
import copy
import json
import re
import threading
from pathlib import Path
from typing import Any, Pattern
from urllib.parse import urlsplit

import yaml

from .okf import ALLOWED_HTML_BUNDLE_ASSET_EXTENSIONS, HTML_PROFILE_SCRIPT_RE, parse_html_profile

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Windows dev environments have no fcntl
    fcntl = None  # type: ignore[assignment]

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

# --- §10 P2-16: 업로드 quota 기본값 (env로 main.py에서 재정의) --------------------
BOI_SHARE_MAX_PER_USER_DEFAULT = 200
BOI_SHARE_MAX_UPLOADS_PER_DAY_DEFAULT = 50

# --- §10 P2-15: 다중 파일 번들(assets) 기본값 -----------------------------------
HTML_BUNDLE_ASSET_MAX_BYTES = 5 * 1024 * 1024
HTML_BUNDLE_ASSET_MAX_COUNT = 20
HTML_BUNDLE_INDEX_FILENAME = "index.html"

# --- §10 P2-13: url-kind go-link 이름/스킴 검증 ---------------------------------
SHARE_URL_ALLOWED_SCHEMES = {"http", "https"}

# --- §10 P2-14: 버전 이력 열람 대상 commit hash 검증 -----------------------------
GIT_COMMIT_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")

_REGISTRY_LOCK = threading.Lock()
_REGISTRY_CACHE: dict[str, tuple[tuple[int, int], list[dict[str, Any]]]] = {}


@contextlib.contextmanager
def _registry_file_lock(path: Path):
    """레지스트리 RMW(read-modify-write)를 위한 inter-process 파일락 (§10 P2-17).

    불변식: 멀티 워커(gunicorn 등) 배포에서 여러 프로세스가 동시에
    upsert/tombstone을 수행해도 마지막 쓰기가 이전 쓰기를 덮어써 레코드를 잃어버리지
    않아야 한다. `fcntl.flock`은 Linux 런타임에서만 사용 가능하다 — 임포트 실패
    (Windows 개발 환경)면 조용히 아무 것도 하지 않고, 기존 스레드 락(_REGISTRY_LOCK)만으로
    단일 프로세스 내 동시성을 계속 보호한다.
    """
    if fcntl is None:
        yield
        return
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


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
    # §10 P2-17: 파일락이 find→modify→save 전체 임계 구역을 감싼다 — 멀티 워커가 동시에
    # upsert해도 마지막 프로세스의 쓰기가 다른 프로세스의 upsert를 덮어써 지우지 않는다.
    with _registry_file_lock(path):
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
    with _registry_file_lock(path):
        with _REGISTRY_LOCK:
            _REGISTRY_CACHE.pop(str(path), None)
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
    bundle: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
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
    if bundle:
        record["bundle"] = True
    return record


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


def html_storage_path(
    data_root: Path,
    visibility: str,
    name: str,
    *,
    employee_id: str = "",
    team_id: str = "",
    bundle: bool = False,
) -> Path:
    """공유 HTML의 저장 경로. `bundle=True`면 `{name}/index.html`(§10 P2-15)을 반환한다.

    단일 파일과 번들은 이름 정책/레지스트리를 공유한다("이름 가용성은 파일/폴더 형태를
    같은 이름으로 취급한다") — 실제로 물리 경로만 다르고 이름 충돌 판정은 레지스트리
    (registry_find)만 본다.
    """
    normalized = normalize_share_name(name)
    if not SHORTLINK_NAME_RE.match(normalized):
        raise ValueError("invalid shortlink name")
    if visibility == "public":
        base = Path("public") / HTML_SHARE_SUBFOLDER
    elif visibility == "team":
        if not team_id:
            raise ValueError("team_id is required for team visibility")
        base = Path("team") / team_id / HTML_SHARE_SUBFOLDER
    elif visibility == "private":
        if not employee_id:
            raise ValueError("employee_id is required for private visibility")
        base = Path("private") / employee_id / HTML_SHARE_SUBFOLDER
    else:
        raise ValueError(f"unknown visibility: {visibility}")
    relative = (base / normalized / HTML_BUNDLE_INDEX_FILENAME) if bundle else (base / f"{normalized}.html")
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
        bundle=bool(record.get("bundle")),
    )


def card_path_for_stored_path(stored_path: Path, *, bundle: bool) -> Path:
    """저장된 HTML 경로에서 사이드카 지식 카드 경로를 계산한다.

    번들이면 폴더 한 단계 위 `{name}.md`, 단일 파일이면 기존과 동일한
    `{name}.html` → `{name}.md`다 (okf.html_bundle_card_path와 동일 규칙).
    """
    return stored_path.parent.with_suffix(".md") if bundle else stored_path.with_suffix(".md")


def card_path_for_record(data_root: Path, record: dict[str, Any]) -> Path:
    stored_path = storage_path_for_record(data_root, record)
    return card_path_for_stored_path(stored_path, bundle=bool(record.get("bundle")))


def bundle_dir_for_record(data_root: Path, record: dict[str, Any]) -> Path:
    """번들 레코드의 폴더 경로(`{name}/`)를 반환한다. 단일 파일 레코드에는 의미가 없다."""
    return storage_path_for_record(data_root, record).parent


# --- §10 P2-15: 번들 자산(assets) 검증 ------------------------------------------


def bundle_asset_filename(original_filename: str) -> str:
    """업로드된 자산 파일명을 평탄화한다 — 하위 폴더 없이 basename만 남긴다(MVP)."""
    name = str(original_filename or "").strip().replace("\\", "/")
    name = name.rsplit("/", 1)[-1].strip()
    return name


def bundle_asset_error(filename: str, size: int) -> str:
    """자산 파일명/크기를 검증한다. 문제 없으면 빈 문자열을 반환한다."""
    flattened = bundle_asset_filename(filename)
    if not flattened or flattened in {".", ".."}:
        return "번들 자산 파일명이 올바르지 않습니다."
    suffix = Path(flattened).suffix.lower()
    if suffix not in ALLOWED_HTML_BUNDLE_ASSET_EXTENSIONS:
        return f"'{flattened}'은(는) 지원하지 않는 확장자입니다. 허용 확장자: {', '.join(sorted(ext.lstrip('.') for ext in ALLOWED_HTML_BUNDLE_ASSET_EXTENSIONS))}"
    if size > HTML_BUNDLE_ASSET_MAX_BYTES:
        return f"'{flattened}' 파일이 5MB 상한을 초과했습니다."
    return ""


# --- §10 P2-16: 업로드 quota -----------------------------------------------------


def active_share_count_for_owner(records: list[dict[str, Any]], employee_id: str) -> int:
    """소유자의 활성 공유(신규 이름으로 등록된 것 전체) 개수를 센다. tombstone은 제외."""
    return sum(
        1
        for record in records
        if str(record.get("status") or "") == "active"
        and str(record.get("owner_employee_id") or "") == employee_id
    )


# --- §10 P2-13: url-kind go-link -------------------------------------------------


def share_url_target_error(target_url: str, allowed_hosts: set[str] | frozenset[str]) -> str:
    """url-kind 단축주소 대상 검증. http(s) 스킴 + 허용 호스트 목록만 통과시킨다."""
    value = str(target_url or "").strip()
    if not value:
        return "target_url이 필요합니다."
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in SHARE_URL_ALLOWED_SCHEMES:
        return "target_url은 http 또는 https 주소만 허용됩니다."
    hostname = (parsed.hostname or "").lower()
    normalized_allowed = {str(host or "").strip().lower() for host in allowed_hosts if str(host or "").strip()}
    if not hostname or hostname not in normalized_allowed:
        return (
            f"'{hostname or value}' 호스트는 허용된 내부 주소 목록(BOI_SHARE_URL_ALLOWED_HOSTS)에 없어 "
            "단축주소로 등록할 수 없습니다."
        )
    return ""


def looks_like_html(content: bytes, content_type: str) -> bool:
    if str(content_type or "").lower().split(";")[0].strip() == "text/html":
        return True
    head = content[:65536].decode("utf-8", errors="ignore").lower()
    return "<html" in head or "<!doctype html" in head


def validate_html_upload(
    content: bytes,
    content_type: str,
    secret_pattern: Pattern[str],
    *,
    decoded_text: str | None = None,
) -> tuple[int, str] | None:
    if not content:
        return (400, "업로드된 파일이 비어 있습니다. HTML 파일을 선택한 뒤 다시 시도해주세요.")
    if len(content) > HTML_SHARE_MAX_BYTES:
        return (413, "HTML 파일은 20MB 이하만 업로드할 수 있습니다.")
    if not looks_like_html(content, content_type):
        return (400, "HTML 파일이 아닙니다. <html> 태그 또는 <!doctype html> 선언이 포함된 self-contained HTML 파일만 업로드할 수 있습니다.")
    # 비밀 스캔은 실제로 저장될 디코딩 결과(decode_html_bytes)를 기준으로 한다 —
    # 비-UTF-8 업로드를 naive errors="ignore" 디코딩으로 스캔하면 멀티바이트 문자가
    # 깨져 비밀 값 패턴이 우연히 숨거나 왜곡될 수 있다 (§10 P0-3).
    text = decoded_text if decoded_text is not None else content.decode("utf-8", errors="ignore")
    if secret_pattern.search(text):
        return (400, "API key/token/password로 보이는 비밀 값이 포함되어 있어 업로드할 수 없습니다. 비밀 값을 제거한 뒤 다시 업로드해주세요.")
    return None


# --- Phase P0-3: 인코딩 감지·변환 (계획서 §10 항목 3) --------------------------
# 사내 legacy HTML 보고서는 EUC-KR/CP949일 가능성이 높다. 예전에는 errors="replace"로
# 무조건 깨진 채 저장했다 — 감지된 인코딩으로 정확히 디코딩해 utf-8로 다시 저장한다.

_BOM_UTF8 = b"\xef\xbb\xbf"
_BOM_UTF16_LE = b"\xff\xfe"
_BOM_UTF16_BE = b"\xfe\xff"
# <meta charset="..."> 또는 <meta http-equiv="Content-Type" content="...;charset=...">
# 양쪽 형태를 모두 첫 4KB(바이트 단위, ASCII 호환 인코딩이라면 태그 이름/속성은 항상
# 1바이트로 보존된다)에서 관대하게 탐지한다.
_META_CHARSET_RE = re.compile(rb'<meta[^>]*?charset\s*=\s*["\']?\s*([a-zA-Z0-9_\-]+)', re.IGNORECASE)
_META_CHARSET_SNIFF_BYTES = 4096
_CHARSET_ALIASES = {
    "euc-kr": "cp949",
    "euckr": "cp949",
    "ks_c_5601-1987": "cp949",
    "ks_c_5601": "cp949",
    "ksc5601": "cp949",
    "x-windows-949": "cp949",
    "ms949": "cp949",
    "utf8": "utf-8",
}


def _normalize_codec_name(raw: str) -> str:
    key = str(raw or "").strip().lower()
    return _CHARSET_ALIASES.get(key, key)


def sniff_meta_charset(content: bytes) -> str:
    """첫 4KB에서 <meta charset=...>/<meta http-equiv=... charset=...>를 탐지해 정규화한다."""
    match = _META_CHARSET_RE.search(content[:_META_CHARSET_SNIFF_BYTES])
    if not match:
        return ""
    return _normalize_codec_name(match.group(1).decode("ascii", errors="ignore"))


def decode_html_bytes(content: bytes) -> tuple[str, str, bool]:
    """업로드 바이트를 감지된 인코딩으로 디코딩한다. 반환: (텍스트, 감지된 인코딩, lossy 여부).

    감지 순서: UTF-8/UTF-16 BOM → strict UTF-8 → <meta charset> 스니핑(첫 4KB, 별칭
    euc-kr/ks_c_5601-1987/ksc5601 → cp949 정규화) 후 해당 코덱 시도 → 실패 시 cp949
    최종 시도 → 그래도 실패하면 utf-8 errors="replace" (lossy=True, 최후 수단).
    """
    if content.startswith(_BOM_UTF8):
        try:
            return content[len(_BOM_UTF8):].decode("utf-8"), "utf-8", False
        except UnicodeDecodeError:
            pass
    if content.startswith(_BOM_UTF16_LE) or content.startswith(_BOM_UTF16_BE):
        try:
            return content.decode("utf-16"), "utf-16", False
        except UnicodeDecodeError:
            pass
    try:
        return content.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        pass
    sniffed = sniff_meta_charset(content)
    if sniffed and sniffed != "utf-8":
        try:
            return content.decode(sniffed), sniffed, False
        except (UnicodeDecodeError, LookupError):
            pass
    if sniffed != "cp949":
        try:
            return content.decode("cp949"), "cp949", False
        except (UnicodeDecodeError, LookupError):
            pass
    return content.decode("utf-8", errors="replace"), "utf-8", True


_META_CHARSET_TAG_RE = re.compile(r'(<meta\b[^>]*\bcharset\s*=\s*["\']?)([a-zA-Z0-9_\-]+)', re.IGNORECASE)


def ensure_utf8_meta_charset(html_text: str) -> str:
    """비-UTF-8 업로드를 변환 저장한 뒤 charset 선언을 utf-8로 다시 쓴다.

    <meta charset=...>와 <meta http-equiv="Content-Type" content="...charset=...">
    양쪽 형태를 모두 처리한다(닫는 따옴표/태그는 건드리지 않아 원래 구문을 보존한다).
    선언이 아예 없으면 <head> 바로 뒤(없으면 <html> 바로 뒤, 그마저 없으면 문서
    맨 앞)에 새로 추가한다 — 그렇지 않으면 브라우저가 여전히 원본 인코딩으로 오인해
    변환된 utf-8 바이트를 다시 깨뜨려 렌더링한다.
    """
    text = str(html_text or "")
    if _META_CHARSET_TAG_RE.search(text):
        return _META_CHARSET_TAG_RE.sub(lambda m: m.group(1) + "utf-8", text)
    head_match = re.search(r"<head\b[^>]*>", text, flags=re.IGNORECASE)
    if head_match:
        index = head_match.end()
        return text[:index] + '\n<meta charset="utf-8">' + text[index:]
    html_match = re.search(r"<html\b[^>]*>", text, flags=re.IGNORECASE)
    if html_match:
        index = html_match.end()
        return text[:index] + '\n<head><meta charset="utf-8"></head>' + text[index:]
    return '<meta charset="utf-8">\n' + text


def original_upload_ref_from_card(card_metadata: dict[str, Any]) -> tuple[str, str]:
    """지식 카드 frontmatter의 upload source_ref에서 (원본 파일명, 원본 sha256)을 꺼낸다.

    PATCH(§10 P1-6)/소유권 이전(§10 P1-7)이 프로필·카드를 재생성할 때 최초 업로드
    당시의 provenance(파일명/sha256)를 그대로 보존하기 위해 재사용한다.
    """
    for ref in (card_metadata or {}).get("source_refs") or []:
        if isinstance(ref, dict) and str(ref.get("type") or "") == "upload":
            return str(ref.get("ref") or ""), str(ref.get("sha256") or "")
    return "", ""


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
    bundle: bool = False,
    asset_filenames: list[str] | None = None,
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
    if bundle:
        metadata["bundle"] = True
    analysis_section = (wiki_loops.render_analysis_section(analysis).rstrip("\n") + "\n\n") if analysis else ""
    assets_section = ""
    if bundle:
        listed = list(asset_filenames or [])
        assets_list = "\n".join(f"- `{item}`" for item in listed) if listed else "- (첨부된 자산 파일 없음)"
        assets_section = f"# 번들 자산\n\n{assets_list}\n\n"
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
        + assets_section
        + analysis_section
        + "# Citations\n\n"
        f"- HTML 파일: `{html_repo_path}`\n"
    )
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body
