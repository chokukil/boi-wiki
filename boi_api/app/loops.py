"""루프 엔지니어링(Phase 3) 로직 모듈 — docs/HTML_SHARE_AND_META_HARNESS_PLAN.md §4.6.

텔레메트리(클릭/조회/피드백), gardening(sleep-time 점검), promotion 추천,
지식 카드 자동 분석(enrich)을 담당한다. main.py에는 라우트 글루만 둔다.

핵심 불변식:
- 모든 루프 기능은 실패 허용(failure-tolerant)이다. 텔레메트리/가드닝/enrich 실패가
  업로드, 페이지 렌더, 기존 API를 깨뜨려서는 안 된다.
- 조회수/피드백 카운터는 runtime 전용({BOI_RUNTIME_ROOT}/telemetry)에만 산다.
  문서 frontmatter는 조회마다 다시 쓰지 않는다(git churn 방지).
- 자동 분석은 완전 결정적(LLM 호출 없음)이다.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .okf import HTML_PROFILE_SCRIPT_RE, split_frontmatter

KST = timezone(timedelta(hours=9))

# --- §10 P2-18: 텔레메트리 보존 정책 --------------------------------------------
TELEMETRY_RETENTION_DAYS_ENV = "BOI_TELEMETRY_RETENTION_DAYS"
TELEMETRY_RETENTION_DAYS_DEFAULT = 90
_EVENTS_FILENAME_RE = re.compile(r"^events-(\d{8})\.jsonl$")


def telemetry_retention_days() -> int:
    """env를 매번 새로 읽는다 — 테스트가 monkeypatch.setenv로 보존 기간을 바꿀 수 있게 한다."""
    try:
        value = int(os.getenv(TELEMETRY_RETENTION_DAYS_ENV, "") or TELEMETRY_RETENTION_DAYS_DEFAULT)
    except (TypeError, ValueError):
        return TELEMETRY_RETENTION_DAYS_DEFAULT
    return value if value > 0 else TELEMETRY_RETENTION_DAYS_DEFAULT

# --- 텔레메트리 루프 ---------------------------------------------------------

TELEMETRY_COUNTER_FIELDS = ("views", "viewer_views", "raw_views", "feedback_helpful", "feedback_needs_fix")
# 채널별 클릭 필드 (§10 P1-8): viewer 뷰어 페이지 렌더와 doc/url kind의 즉시 redirect는
# 둘 다 "/{name}"을 방문한 단일 클릭이므로 viewer_views에 합산한다. raw 채널(/r/{name}
# 원본 서빙)만 별도로 raw_views에 적립해, viewer 방문 1회가 viewer+iframe raw로 2배
# 집계되던 문제(계획서 §10 P1-8 근거)를 없앤다. 노출(UI/`/api/share/*` 목록/promotion)은
# 항상 viewer_views만 쓴다 — raw_views는 `/api/telemetry/usage` 상세 조회에만 노출한다.
_SHORTLINK_CLICK_CHANNEL_FIELD = {"raw": "raw_views"}
# 코멘트 있는 피드백만 담는 별도 append-only 로그 (§10 P0-2 피드백 표면화).
FEEDBACK_COMMENTS_FILENAME = "feedback-comments.jsonl"


def _now() -> datetime:
    return datetime.now(KST).replace(microsecond=0)


class TelemetryStore:
    """append-only JSONL(events-YYYYMMDD.jsonl) + 집계 카운터(counters.json).

    record()는 절대 예외를 던지지 않는다 — 텔레메트리는 페이지 렌더를 깨면 안 된다.
    카운터는 시작 시 로드 후 증분 저장하며, thread lock으로 보호한다.
    개인별 로그는 JSONL에만 남고 카운터/조회 API에는 집계 수치만 노출한다.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()
        self._counters: dict[str, Any] | None = None
        # §10 P2-18: 마커 속성 — 이 프로세스(인스턴스)에서 마지막으로 보존 정책 정리를
        # 수행한 날짜(YYYYMMDD). 같은 날 여러 번 record()가 호출돼도 디렉토리를 다시
        # 스캔하지 않는다.
        self._last_pruned_day: str = ""

    def _counters_path(self) -> Path:
        return self.root / "counters.json"

    def _load_counters_locked(self) -> dict[str, Any]:
        if self._counters is None:
            loaded: dict[str, Any] = {}
            try:
                raw = json.loads(self._counters_path().read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    loaded = raw
            except Exception:
                loaded = {}
            self._counters = loaded
        for section in ("docs", "shortlinks", "memories"):
            if not isinstance(self._counters.get(section), dict):
                self._counters[section] = {}
        return self._counters

    @staticmethod
    def _bump(section: dict[str, Any], key: str, field: str, ts: str) -> None:
        entry = section.setdefault(key, {})
        entry[field] = int(entry.get(field) or 0) + 1
        entry["last_seen"] = ts

    @staticmethod
    def _migrate_legacy_clicks(section: dict[str, Any], key: str) -> None:
        """구 스키마(§10 P1-8 이전 "clicks" 단일 합산)를 처음 새 채널 이벤트가 닿을 때
        물리적으로 viewer_views로 옮긴다. 값을 그대로 유지한 채 한 번만 변환하고,
        이후에는 채널별로 정상 분리 적립된다. 아예 새 이벤트가 다시 오지 않는 legacy
        항목은 _stats()의 읽기 시점 관대한 매핑이 대신 처리한다."""
        entry = section.get(key)
        if not isinstance(entry, dict):
            return
        if "viewer_views" not in entry and "raw_views" not in entry and "clicks" in entry:
            entry["viewer_views"] = int(entry.pop("clicks") or 0)

    def _apply_locked(self, counters: dict[str, Any], kind: str, row: dict[str, Any]) -> None:
        ts = str(row.get("ts") or "")
        docs = counters["docs"]
        shortlinks = counters["shortlinks"]
        target = str(row.get("target") or "")
        if kind == "doc_view":
            boi_id = str(row.get("boi_id") or "")
            if boi_id:
                self._bump(docs, boi_id, "views", ts)
        elif kind == "shortlink_click":
            # channel: viewer(뷰어 페이지) | raw(/r/ 원본 서빙) | redirect(doc/url kind 302).
            # redirect는 viewer와 같은 "/{name} 방문 1회"이므로 viewer_views에 합산한다.
            channel = str(row.get("channel") or "viewer")
            field = _SHORTLINK_CLICK_CHANNEL_FIELD.get(channel, "viewer_views")
            name = str(row.get("name") or "")
            if name:
                self._migrate_legacy_clicks(shortlinks, name)
                self._bump(shortlinks, name, field, ts)
            # 단축주소가 BoI를 가리키면 대상 문서(지식 카드)에도 같은 채널로 적립해
            # promotion 추천(usage = views + viewer_views)의 입력이 된다.
            if target.startswith("boi:"):
                self._migrate_legacy_clicks(docs, target)
                self._bump(docs, target, field, ts)
        elif kind in {"doc_feedback", "share_feedback"}:
            field = "feedback_helpful" if row.get("helpful") else "feedback_needs_fix"
            if kind == "doc_feedback":
                boi_id = str(row.get("boi_id") or "")
                if boi_id:
                    self._bump(docs, boi_id, field, ts)
            else:
                name = str(row.get("name") or "")
                if name:
                    self._bump(shortlinks, name, field, ts)
                if target.startswith("boi:"):
                    self._bump(docs, target, field, ts)
        elif kind == "memory_recall":
            boi_id = str(row.get("boi_id") or "")
            if boi_id:
                self._bump(counters["memories"], boi_id, "recalls", ts)

    def _prune_old_events_locked(self, now: datetime) -> None:
        """오래된 `events-*.jsonl`을 보존기간 밖이면 삭제한다 (§10 P2-18).

        `self._lock` 보유 상태에서 호출되어야 한다. 프로세스(인스턴스)당 하루 한 번만
        실제로 디렉토리를 스캔한다(마커 속성 `_last_pruned_day`). 텔레메트리 불변식대로
        어떤 예외도 밖으로 던지지 않는다 — 실패해도 record()가 계속 진행되어야 한다.
        """
        today_key = now.strftime("%Y%m%d")
        if self._last_pruned_day == today_key:
            return
        self._last_pruned_day = today_key
        try:
            if not self.root.exists():
                return
            cutoff = now.date() - timedelta(days=telemetry_retention_days())
            for path in self.root.glob("events-*.jsonl"):
                match = _EVENTS_FILENAME_RE.match(path.name)
                if not match:
                    continue
                try:
                    file_date = datetime.strptime(match.group(1), "%Y%m%d").date()
                except ValueError:
                    continue
                if file_date < cutoff:
                    try:
                        path.unlink()
                    except OSError:
                        pass
        except Exception:
            pass

    def record(self, kind: str, **fields: Any) -> bool:
        """이벤트 1건을 JSONL에 적재하고 카운터를 증분한다. 실패 시 False만 반환한다."""
        try:
            now = _now()
            with self._lock:
                self._prune_old_events_locked(now)
            row: dict[str, Any] = {"kind": str(kind), "ts": now.isoformat()}
            for key, value in fields.items():
                if value is None or value == "":
                    continue
                row[key] = value
            with self._lock:
                self.root.mkdir(parents=True, exist_ok=True)
                events_path = self.root / f"events-{now.strftime('%Y%m%d')}.jsonl"
                with events_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                counters = self._load_counters_locked()
                self._apply_locked(counters, str(kind), row)
                counters["updated_at"] = row["ts"]
                self._counters_path().write_text(
                    json.dumps(counters, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            return True
        except Exception:
            return False

    def _snapshot(self) -> dict[str, Any]:
        try:
            with self._lock:
                return json.loads(json.dumps(self._load_counters_locked()))
        except Exception:
            return {"docs": {}, "shortlinks": {}, "memories": {}}

    @staticmethod
    def _stats(entry: dict[str, Any]) -> dict[str, Any]:
        # 관대한 마이그레이션(§10 P1-8): 채널 분리 이전에는 "clicks" 하나로만 합산됐다.
        # viewer_views/raw_views 키가 아예 없는 legacy 항목은 옛 합산 클릭수를
        # viewer_views로 간주한다(raw_views=0) — 노출 기준이 viewer이므로 과거 조회수가
        # 갑자기 0으로 보이는 회귀를 막는다. 새 스키마 항목은 그대로 읽는다.
        has_split_schema = "viewer_views" in entry or "raw_views" in entry
        if has_split_schema:
            viewer_views = int(entry.get("viewer_views") or 0)
            raw_views = int(entry.get("raw_views") or 0)
        else:
            viewer_views = int(entry.get("clicks") or 0)
            raw_views = 0
        stats = {
            "views": int(entry.get("views") or 0),
            "viewer_views": viewer_views,
            "raw_views": raw_views,
            "feedback_helpful": int(entry.get("feedback_helpful") or 0),
            "feedback_needs_fix": int(entry.get("feedback_needs_fix") or 0),
        }
        stats["last_seen"] = str(entry.get("last_seen") or "")
        return stats

    def usage_counts(self) -> dict[str, dict[str, Any]]:
        """{boi_id 또는 단축주소 이름 → {views, viewer_views, raw_views, feedback_helpful, feedback_needs_fix, last_seen}}"""
        snapshot = self._snapshot()
        merged: dict[str, dict[str, Any]] = {}
        for boi_id, entry in (snapshot.get("docs") or {}).items():
            merged[str(boi_id)] = self._stats(entry if isinstance(entry, dict) else {})
        for name, entry in (snapshot.get("shortlinks") or {}).items():
            merged[str(name)] = self._stats(entry if isinstance(entry, dict) else {})
        return merged

    def doc_usage(self, boi_id: str) -> dict[str, Any]:
        entry = (self._snapshot().get("docs") or {}).get(str(boi_id))
        return self._stats(entry if isinstance(entry, dict) else {})

    def shortlink_views(self, name: str) -> int:
        """노출용 조회수 — 항상 viewer 채널 기준이다(§10 P1-8, raw iframe 재요청은 제외)."""
        entry = (self._snapshot().get("shortlinks") or {}).get(str(name))
        return self._stats(entry if isinstance(entry, dict) else {})["viewer_views"]

    def doc_feedback_counts(self, boi_id: str) -> dict[str, int]:
        stats = self.doc_usage(boi_id)
        return {"helpful": stats["feedback_helpful"], "needs_fix": stats["feedback_needs_fix"]}

    def shortlink_feedback_counts(self, name: str) -> dict[str, int]:
        entry = (self._snapshot().get("shortlinks") or {}).get(str(name))
        stats = self._stats(entry if isinstance(entry, dict) else {})
        return {"helpful": stats["feedback_helpful"], "needs_fix": stats["feedback_needs_fix"]}

    def docs_needs_fix_counts(self) -> dict[str, int]:
        snapshot = self._snapshot()
        return {
            str(boi_id): int(entry.get("feedback_needs_fix") or 0)
            for boi_id, entry in (snapshot.get("docs") or {}).items()
            if isinstance(entry, dict) and int(entry.get("feedback_needs_fix") or 0) > 0
        }

    def memory_recall_count(self, boi_id: str) -> int:
        entry = (self._snapshot().get("memories") or {}).get(str(boi_id))
        return int((entry or {}).get("recalls") or 0) if isinstance(entry, dict) else 0

    # --- §10 P2-16: 업로드 quota의 일일 한도 카운트 ---------------------------
    # 별도 ledger 파일 대신 기존 텔레메트리 이벤트("share_upload" kind)를 재사용한다
    # — 오늘 날짜의 events-*.jsonl 한 파일만 읽으면 돼서 무겁지 않고, 실패 허용
    # 원칙과 append-only 로그 패턴을 그대로 따른다.

    def share_uploads_today(self, employee_id: str) -> int:
        try:
            now = _now()
            events_path = self.root / f"events-{now.strftime('%Y%m%d')}.jsonl"
            if not events_path.exists():
                return 0
            count = 0
            for line in events_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("kind") or "") != "share_upload":
                    continue
                if str(row.get("employee_id") or "") == str(employee_id):
                    count += 1
            return count
        except Exception:
            return 0

    # --- 피드백 코멘트 표면화 (§10 P0-2) --------------------------------------
    # counters.json/events-*.jsonl과 별개로, "수정 필요"/"도움됨" 코멘트만
    # 조회 가능한 형태로 남긴다. 이 로그가 없으면 코멘트는 텔레메트리 JSONL에만
    # 쌓여 아무 API/UI로도 노출되지 않는다(수집만 하는 피드백은 루프가 아니다).

    def _feedback_comments_path(self) -> Path:
        return self.root / FEEDBACK_COMMENTS_FILENAME

    def record_feedback_comment(
        self, *, kind: str, employee_id: str, helpful: bool, comment: str, boi_id: str = "", name: str = ""
    ) -> bool:
        """comment가 있는 피드백만 별도 로그에 남긴다. 빈 코멘트는 남길 게 없어 True를 반환한다."""
        comment_text = str(comment or "").strip()
        if not comment_text:
            return True
        try:
            row: dict[str, Any] = {
                "ts": _now().isoformat(),
                "kind": str(kind),
                "employee_id": str(employee_id or ""),
                "helpful": bool(helpful),
                "comment": comment_text,
            }
            if boi_id:
                row["boi_id"] = str(boi_id)
            if name:
                row["name"] = str(name)
            with self._lock:
                self.root.mkdir(parents=True, exist_ok=True)
                with self._feedback_comments_path().open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def _feedback_comment_rows(self) -> list[dict[str, Any]]:
        path = self._feedback_comments_path()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        except Exception:
            return []
        return rows

    @staticmethod
    def _comment_view(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "ts": str(row.get("ts") or ""),
            "employee_id": str(row.get("employee_id") or ""),
            "helpful": bool(row.get("helpful")),
            "comment": str(row.get("comment") or ""),
        }

    def doc_feedback_comments(self, boi_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """최근 N건(최신순) — 문서 소유자/promoter/admin 전용 API가 그대로 노출한다."""
        matches = [row for row in self._feedback_comment_rows() if str(row.get("boi_id") or "") == str(boi_id)]
        matches.reverse()
        return [self._comment_view(row) for row in matches[: max(0, int(limit))]]

    def share_feedback_comments(self, name: str, limit: int = 20) -> list[dict[str, Any]]:
        matches = [row for row in self._feedback_comment_rows() if str(row.get("name") or "") == str(name)]
        matches.reverse()
        return [self._comment_view(row) for row in matches[: max(0, int(limit))]]


# --- Gardening 루프 (sleep-time 점검) ---------------------------------------

GARDENING_LATEST_FILENAME = "latest.json"
GARDENING_EMITTED_FILENAME = "emitted.json"
GARDENING_FINDING_KINDS = ("stale", "orphan", "broken_link", "duplicate", "feedback")
_GARDENING_LOCK = threading.Lock()
_UNRESOLVED_LINK_MARKER = "unresolved OKF markdown link:"


def normalize_title_key(title: str) -> str:
    """제목 중복 후보 판정용 정규화: 소문자화 후 구두점/공백 제거."""
    return re.sub(r"[^0-9a-z가-힣一-鿿]+", "", str(title or "").lower())


def finding_fingerprint(kind: str, ref: str, detail: str = "") -> str:
    return hashlib.sha256(f"{kind}|{ref}|{detail}".encode("utf-8")).hexdigest()[:16]


def parse_review_after(value: Any) -> date | None:
    """review_after를 관대하게 파싱한다(date/datetime/문자열 접두 YYYY-MM-DD)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(value or "").strip())
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _doc_scope(uri: str) -> str:
    stripped = str(uri or "").lstrip("/")
    return stripped.split("/", 1)[0] if stripped else ""


def _concept_id(uri: str) -> str:
    stripped = str(uri or "").lstrip("/")
    return stripped[:-3] if stripped.endswith(".md") else stripped


def _finding(kind: str, ref: str, detail: str, *, path: str = "", title: str = "") -> dict[str, Any]:
    item: dict[str, Any] = {
        "kind": kind,
        "boi_id": ref,
        "detail": detail,
        "fingerprint": finding_fingerprint(kind, ref, detail),
    }
    if path:
        item["path"] = path
    if title:
        item["title"] = title
    return item


def build_gardening_findings(
    *,
    docs: list[dict[str, Any]],
    link_edges: list[dict[str, Any]] | None,
    lint_errors: list[str],
    needs_fix_counts: dict[str, int],
    today: date,
    max_age_days: int | None = None,
    needs_fix_comments: dict[str, list[str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """public+team 문서에 대한 stale/orphan/broken_link/duplicate/feedback 점검.

    private 문서는 검사하지 않고 개수만 센다. link_edges가 None이면(링크 그래프 수집
    실패) 모든 문서를 orphan으로 오판하지 않도록 orphan 점검을 건너뛴다.
    반환은 (findings, meta_counts).
    """
    findings: list[dict[str, Any]] = []
    scanned = 0
    private_skipped = 0
    orphan_check_enabled = link_edges is not None
    inbound_targets = {
        str(edge.get("target") or "")
        for edge in link_edges or []
        if edge.get("resolved")
    }
    by_title_key: dict[str, list[dict[str, Any]]] = {}
    by_description: dict[str, list[dict[str, Any]]] = {}
    boi_ids_in_scope: set[str] = set()
    for doc in docs or []:
        uri = str(doc.get("uri") or "")
        scope = _doc_scope(uri)
        if scope == "private":
            private_skipped += 1
            continue
        if scope not in {"public", "team"}:
            continue
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        boi_id = str(metadata.get("boi_id") or "")
        if not boi_id:
            continue
        scanned += 1
        boi_ids_in_scope.add(boi_id)
        title = str(metadata.get("title") or "")
        doc_type = str(metadata.get("type") or "")
        ref = boi_id
        # stale: review_after 경과 (관대 파싱)
        review_after = parse_review_after(metadata.get("review_after"))
        if review_after is not None and review_after < today:
            findings.append(
                _finding("stale", ref, f"review_after {review_after.isoformat()} 경과", path=uri, title=title)
            )
        # stale: HTML 지식 카드의 timestamp가 max_age_days보다 오래된 경우 (기본 off)
        if max_age_days is not None and doc_type == "boi/html-document":
            card_timestamp = parse_review_after(metadata.get("timestamp"))
            if card_timestamp is not None and (today - card_timestamp).days > int(max_age_days):
                findings.append(
                    _finding(
                        "stale",
                        ref,
                        f"HTML 지식 카드 timestamp {card_timestamp.isoformat()}이 {max_age_days}일 초과",
                        path=uri,
                        title=title,
                    )
                )
        # duplicate 후보 그룹 재료 (public+team)
        title_key = normalize_title_key(title)
        if title_key:
            by_title_key.setdefault(title_key, []).append({"boi_id": boi_id, "title": title})
        description = str(metadata.get("description") or "").strip()
        if description:
            by_description.setdefault(description, []).append({"boi_id": boi_id, "title": title})
        # orphan: public 문서 중 역링크 0.
        # index/log 파일, 하네스 문서, 사전 용어는 제외한다. HTML 지식 카드도 제외 —
        # 카드는 단축주소 레지스트리가 항상 참조하므로 링크 그래프 역링크 0이 orphan이 아니다.
        if not orphan_check_enabled or scope != "public":
            continue
        basename = uri.rstrip("/").rsplit("/", 1)[-1]
        if basename in {"index.md", "log.md"}:
            continue
        if "/harness/" in uri or "/dictionary/" in uri:
            continue
        if doc_type == "boi/html-document":
            continue
        if _concept_id(uri) not in inbound_targets:
            findings.append(_finding("orphan", ref, "역링크 0 (OKF 링크 그래프 기준)", path=uri, title=title))
    # broken links: strict-links lint 오류를 실패 없이 findings로만 수집한다.
    for error in lint_errors or []:
        if _UNRESOLVED_LINK_MARKER not in str(error):
            continue
        prefix, _marker, href = str(error).partition(_UNRESOLVED_LINK_MARKER)
        findings.append(
            _finding("broken_link", prefix.rstrip(": ").strip(), f"unresolved link:{href.rstrip()}")
        )
    # duplicate 후보: 정규화 제목 충돌 + 동일 description
    seen_duplicate_groups: set[str] = set()
    for reason, groups in (("제목", by_title_key), ("설명", by_description)):
        for _key, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            ids = sorted({str(member["boi_id"]) for member in members})
            if len(ids) < 2:
                continue
            group_ref = ",".join(ids)
            if group_ref in seen_duplicate_groups:
                continue
            seen_duplicate_groups.add(group_ref)
            titles = " / ".join(sorted({str(member["title"]) for member in members}))
            findings.append(_finding("duplicate", group_ref, f"{reason} 중복 후보: {titles}"))
    # feedback: 수정 필요 피드백이 쌓인 문서는 gardening 우선순위를 높인다.
    # 최근 코멘트(최대 3건)를 detail에 포함해 담당자가 리포트만 보고도 무엇을
    # 고쳐야 하는지 알 수 있게 한다 (§10 P0-2 — 코멘트가 텔레메트리에만 갇히지 않도록).
    for boi_id, count in sorted((needs_fix_counts or {}).items()):
        if int(count) <= 0 or boi_id not in boi_ids_in_scope:
            continue
        detail = f"수정 필요 피드백 {int(count)}건"
        comments = [str(c).strip() for c in (needs_fix_comments or {}).get(boi_id) or [] if str(c or "").strip()]
        if comments:
            detail = f"{detail} — 최근 코멘트: " + " / ".join(comments[:3])
        findings.append(_finding("feedback", str(boi_id), detail))
    counts = {kind: 0 for kind in GARDENING_FINDING_KINDS}
    for finding in findings:
        counts[finding["kind"]] = counts.get(finding["kind"], 0) + 1
    meta = {**counts, "docs_scanned": scanned, "private_skipped": private_skipped}
    return findings, meta


def store_gardening_report(root: Path, report: dict[str, Any]) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    (root / GARDENING_LATEST_FILENAME).write_text(payload, encoding="utf-8")
    ran_at = str(report.get("ran_at") or "")
    day = re.sub(r"[^0-9]", "", ran_at[:10]) or _now().strftime("%Y%m%d")
    (root / f"report-{day}.json").write_text(payload, encoding="utf-8")


def load_gardening_report(root: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads((Path(root) / GARDENING_LATEST_FILENAME).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def claim_new_findings(
    root: Path, findings: list[dict[str, Any]], *, limit: int, now: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """생명주기 원장(emitted.json)을 갱신하고 이번 실행에 새로 발행할 finding을 반환한다.

    원장 스키마: ``{fingerprint: {status: open|resolved, first_emitted_at,
    last_seen_at, resolved_at?, kind}}``. 구 스키마(``{fingerprint: {claimed_at,
    kind}}``, status 없음)는 이미 발행된 open 항목으로 관대하게 마이그레이션한다.

    이번 스캔(``findings``)에 없는 open 항목은 resolved로 전환한다(원장에서 지우지
    않고 이력만 남긴다 — 발견→해결 추이 추적). resolved였던 항목이 이번 스캔에 다시
    나타나면 reopen되어 재발행 대상(claimed)에 포함된다 — 한 번 고쳐졌다가 재발한
    문제가 다시는 발행되지 않던 문제(§10 P0-1)를 고친다. limit은 이번 실행에서
    새로 claim(신규 + reopen 합산)할 수 있는 최대 건수다.
    반환: (claimed findings, {open, resolved_this_run, reopened_this_run, total_tracked}).
    """
    if limit < 0:
        limit = 0
    root = Path(root)
    with _GARDENING_LOCK:
        ledger_path = root / GARDENING_EMITTED_FILENAME
        try:
            raw = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger: dict[str, Any] = raw if isinstance(raw, dict) else {}
        except Exception:
            ledger = {}

        # 관대한 마이그레이션: status 없는 legacy 항목은 이미 발행된 open으로 간주한다.
        for fingerprint, entry in list(ledger.items()):
            if not isinstance(entry, dict):
                ledger[fingerprint] = {"status": "open", "first_emitted_at": now, "last_seen_at": now}
                continue
            if "status" not in entry:
                claimed_at = str(entry.get("claimed_at") or now)
                entry["status"] = "open"
                entry.setdefault("first_emitted_at", claimed_at)
                entry.setdefault("last_seen_at", claimed_at)

        current_fingerprints = {
            str(finding.get("fingerprint") or "") for finding in findings or [] if finding.get("fingerprint")
        }
        resolved_this_run = 0
        for fingerprint, entry in ledger.items():
            if isinstance(entry, dict) and entry.get("status") == "open" and fingerprint not in current_fingerprints:
                entry["status"] = "resolved"
                entry["resolved_at"] = now
                resolved_this_run += 1

        claimed: list[dict[str, Any]] = []
        reopened_this_run = 0
        for finding in findings or []:
            fingerprint = str(finding.get("fingerprint") or "")
            if not fingerprint:
                continue
            entry = ledger.get(fingerprint)
            if entry is None:
                if len(claimed) >= limit:
                    continue  # 다음 실행에서 다시 신규로 시도된다 (원장 미기록)
                ledger[fingerprint] = {
                    "status": "open",
                    "first_emitted_at": now,
                    "last_seen_at": now,
                    "kind": str(finding.get("kind") or ""),
                }
                claimed.append(finding)
            elif isinstance(entry, dict) and entry.get("status") == "resolved":
                if len(claimed) >= limit:
                    continue  # 다음 실행에서 다시 reopen 후보로 남는다 (resolved 유지)
                entry["status"] = "open"
                entry["last_seen_at"] = now
                entry["kind"] = str(finding.get("kind") or entry.get("kind") or "")
                reopened_this_run += 1
                claimed.append(finding)
            elif isinstance(entry, dict):
                entry["last_seen_at"] = now

        total_tracked = len(ledger)
        open_count = sum(1 for entry in ledger.values() if isinstance(entry, dict) and entry.get("status") == "open")
        root.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        meta = {
            "open": open_count,
            "resolved_this_run": resolved_this_run,
            "reopened_this_run": reopened_this_run,
            "total_tracked": total_tracked,
        }
        return claimed, meta


# --- Promotion 추천 루프 -----------------------------------------------------


def promotion_candidates(
    docs: list[dict[str, Any]],
    usage_counts: dict[str, dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """조회/클릭 상위 private·team 문서를 promotion 후보로 추천한다.

    자동 게시는 절대 하지 않는다(HOTL) — 추천 목록만 반환한다.
    """
    candidates: list[dict[str, Any]] = []
    for doc in docs or []:
        metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
        visibility = str(metadata.get("visibility") or "")
        if visibility not in {"private", "team"}:
            continue
        if str(metadata.get("status") or "") == "deprecated":
            continue
        if str(metadata.get("archive_status") or "active") not in {"", "active"}:
            continue
        boi_id = str(metadata.get("boi_id") or "")
        if not boi_id:
            continue
        stats = usage_counts.get(boi_id) or {}
        # usage는 viewer 채널 기준(§10 P1-8) — raw_views(원본 iframe 재요청)는 같은 방문의
        # 중복 신호라 promotion 우선순위 계산에서 제외한다.
        usage = int(stats.get("views") or 0) + int(stats.get("viewer_views") or 0)
        if usage <= 0:
            continue
        candidates.append(
            {
                "boi_id": boi_id,
                "title": str(metadata.get("title") or boi_id),
                "visibility": visibility,
                "usage": usage,
                "reason": f"조회 {int(stats.get('views') or 0)}회 · 단축주소 조회 {int(stats.get('viewer_views') or 0)}회",
            }
        )
    candidates.sort(key=lambda item: (-int(item["usage"]), str(item["boi_id"])))
    return candidates[: max(0, int(limit))]


# --- 지식 카드 자동 분석 (enrich, 결정적) ------------------------------------
# 미래 훅: LLM 기반 고품질 요약/태깅은 이 분석 dict를 입력으로 받아 확장할 수 있다.
# Phase 3에서는 어떤 LLM 호출도 하지 않는다 — 아래 추출은 전부 결정적이다.

ANALYSIS_SECTION_HEADING = "# 자동 분석"
ANALYSIS_EXCERPT_CHARS = 400
ANALYSIS_MAX_HEADINGS = 10
ANALYSIS_MAX_TAGS = 8
ANALYSIS_BASE_TAGS = ("HTML", "Share")

_HTML_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HTML_HEADING_RE = re.compile(r"<(h[1-3])\b[^>]*>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# 자동 분석 h1 섹션 전체(다음 h1 직전까지). "## " 하위 절은 섹션 내부에 머문다.
_ANALYSIS_SECTION_RE = re.compile(r"# 자동 분석\n.*?(?=\n# |\Z)", re.DOTALL)


def _plain_text(fragment: str) -> str:
    text = _HTML_TAG_RE.sub(" ", str(fragment or ""))
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _markdown_safe(text: str) -> str:
    # 발췌/제목이 카드 안에서 마크다운 링크로 재해석되어 strict-links lint를
    # 깨지 않도록 링크 구문 문자를 제거한다.
    return str(text or "").replace("[", "(").replace("]", ")").replace("`", "'")


def analyze_html_content(html_text: str, dictionary_titles: Iterable[str] = ()) -> dict[str, Any]:
    """업로드 HTML에서 제목/목차/발췌/표·스크립트 수/사전 태그를 결정적으로 추출한다."""
    text = HTML_PROFILE_SCRIPT_RE.sub("", str(html_text or ""))
    title_match = _HTML_TITLE_RE.search(text)
    title = _markdown_safe(_plain_text(title_match.group(1))) if title_match else ""
    headings: list[dict[str, str]] = []
    for match in _HTML_HEADING_RE.finditer(text):
        heading_text = _markdown_safe(_plain_text(match.group(2)))
        if not heading_text:
            continue
        headings.append({"level": match.group(1).lower(), "text": heading_text})
        if len(headings) >= ANALYSIS_MAX_HEADINGS:
            break
    without_scripts = _HTML_SCRIPT_STYLE_RE.sub(" ", text)
    plain = _plain_text(without_scripts)
    excerpt = plain[:ANALYSIS_EXCERPT_CHARS].strip()
    table_count = len(re.findall(r"<table\b", text, flags=re.IGNORECASE))
    script_count = len(re.findall(r"<script\b", text, flags=re.IGNORECASE))
    haystack = " ".join([title, *[item["text"] for item in headings], plain]).lower()
    matched_terms: list[str] = []
    base_lower = {tag.lower() for tag in ANALYSIS_BASE_TAGS}
    for raw_term in dictionary_titles or ():
        term = str(raw_term or "").strip()
        if not term or term.lower() in base_lower:
            continue
        if term.lower() in haystack and term not in matched_terms:
            matched_terms.append(term)
        if len(matched_terms) >= ANALYSIS_MAX_TAGS - len(ANALYSIS_BASE_TAGS):
            break
    return {
        "title": title,
        "headings": headings,
        "excerpt": excerpt,
        "table_count": table_count,
        "script_count": script_count,
        "matched_terms": matched_terms,
    }


def analysis_tags(analysis: dict[str, Any]) -> list[str]:
    tags = list(ANALYSIS_BASE_TAGS)
    for term in analysis.get("matched_terms") or []:
        if term not in tags:
            tags.append(str(term))
    # §10 P1-9: composer LLM이 성공하면 ai_tags가 채워진다 — 결정적 태그 뒤에 병합한다.
    for term in analysis.get("ai_tags") or []:
        term = str(term or "").strip()
        if term and term not in tags:
            tags.append(term)
    return tags[:ANALYSIS_MAX_TAGS]


def render_analysis_section(analysis: dict[str, Any]) -> str:
    """지식 카드용 `# 자동 분석` 섹션 마크다운을 생성한다."""
    lines = [
        ANALYSIS_SECTION_HEADING,
        "",
        f"- 문서 제목: {analysis.get('title') or '(없음)'}",
        f"- 표 {int(analysis.get('table_count') or 0)}개 · 스크립트/차트 {int(analysis.get('script_count') or 0)}개",
        f"- 자동 태그: {', '.join(analysis_tags(analysis))}",
        "",
    ]
    # §10 P1-9: composer LLM enrich 성공 시에만 채워진다 — 실패/비활성 시 이 절은 생략되고
    # 결정적 분석(목차/발췌/태그)만 유지된다.
    ai_summary = _markdown_safe(str(analysis.get("ai_summary") or "").strip())
    if ai_summary:
        lines.append("## 요약(AI)")
        lines.append("")
        lines.append(ai_summary)
        lines.append("")
    headings = analysis.get("headings") or []
    if headings:
        lines.append("## 추출 목차")
        lines.append("")
        lines.extend(f"- {item.get('level')}: {item.get('text')}" for item in headings)
        lines.append("")
    excerpt = str(analysis.get("excerpt") or "").strip()
    if excerpt:
        lines.append("## 본문 발췌")
        lines.append("")
        # 발췌는 코드 펜스로 감싸 마크다운 링크/이미지 해석을 차단한다(okf lint 보호).
        lines.append("```text")
        lines.append(excerpt.replace("```", "'''"))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def upsert_card_analysis(card_text: str, analysis: dict[str, Any]) -> str:
    """지식 카드의 `# 자동 분석` 섹션과 frontmatter tags를 다시 쓴다(enrich)."""
    metadata, body = split_frontmatter(str(card_text or ""))
    if not isinstance(metadata, dict) or not metadata:
        return str(card_text or "")
    metadata["tags"] = analysis_tags(analysis)
    section = render_analysis_section(analysis).rstrip("\n") + "\n"
    if _ANALYSIS_SECTION_RE.search(body):
        body = _ANALYSIS_SECTION_RE.sub(lambda _match: section, body, count=1)
    else:
        body = body.rstrip("\n") + "\n\n" + section
    if not body.endswith("\n"):
        body += "\n"
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---" + (
        body if body.startswith("\n") else "\n\n" + body
    )
