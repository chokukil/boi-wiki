from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PENDING_STATES = {"queued", "running", "retry_wait"}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InboxReportCoordinator:
    """Durable, low-concurrency coordinator for Inbox report materialization."""

    def __init__(
        self,
        *,
        db_path: Path,
        discover_jobs: Callable[[], list[dict[str, Any]]],
        process_job: Callable[[dict[str, Any]], dict[str, Any]],
        enabled: bool = True,
        scan_interval_seconds: float = 30.0,
        batch_size: int = 8,
        lease_seconds: float = 900.0,
    ) -> None:
        self.db_path = db_path
        self.discover_jobs = discover_jobs
        self.process_job = process_job
        self.enabled = enabled
        self.scan_interval_seconds = max(1.0, scan_interval_seconds)
        self.batch_size = max(1, batch_size)
        self.lease_seconds = max(30.0, lease_seconds)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._scan_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._init_lock = threading.Lock()
        self._initialized = False
        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "status": "disabled" if not enabled else "not_started",
            "last_scan_at": "",
            "last_success_at": "",
            "last_error": "",
            "deferred": 0,
        }

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def initialize(self) -> None:
        if not self.enabled or self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS inbox_report_jobs (
                        report_id TEXT PRIMARY KEY,
                        employee_id TEXT NOT NULL,
                        report_type TEXT NOT NULL DEFAULT 'item',
                        source_kind TEXT NOT NULL DEFAULT 'active',
                        task_ref TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        attempts INTEGER NOT NULL DEFAULT 0,
                        next_attempt_at REAL NOT NULL DEFAULT 0,
                        lease_until REAL NOT NULL DEFAULT 0,
                        last_error_code TEXT NOT NULL DEFAULT '',
                        last_error_message TEXT NOT NULL DEFAULT '',
                        result_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS inbox_report_jobs_status_idx "
                    "ON inbox_report_jobs(status, next_attempt_at)"
                )
                connection.execute(
                    "UPDATE inbox_report_jobs SET status='queued', lease_until=0, updated_at=? "
                    "WHERE status='running'",
                    (utc_iso(),),
                )
            self._initialized = True

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self.initialize()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="boi-inbox-report-coordinator", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(0.0, timeout))

    def wake(self) -> None:
        if self.enabled:
            self._scan_requested.set()
            self._wake.set()

    def enqueue(self, job: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        report_id = str(job.get("report_id") or "")
        employee_id = str(job.get("employee_id") or "")
        if not report_id or not employee_id:
            return False
        self.initialize()
        now = utc_iso()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT status FROM inbox_report_jobs WHERE report_id=?",
                (report_id,),
            ).fetchone()
            if existing and str(existing["status"]) in PENDING_STATES | {"ready", "ignored"}:
                return False
            connection.execute(
                """
                INSERT INTO inbox_report_jobs(
                    report_id, employee_id, report_type, source_kind, task_ref,
                    status, attempts, next_attempt_at, lease_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', 0, 0, 0, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    employee_id=excluded.employee_id,
                    report_type=excluded.report_type,
                    source_kind=excluded.source_kind,
                    task_ref=excluded.task_ref,
                    status='queued',
                    next_attempt_at=0,
                    lease_until=0,
                    updated_at=excluded.updated_at
                """,
                (
                    report_id,
                    employee_id,
                    str(job.get("report_type") or "item"),
                    str(job.get("source_kind") or "active"),
                    str(job.get("task_ref") or ""),
                    now,
                    now,
                ),
            )
        self._wake.set()
        return True

    def mark_ready(self, job: dict[str, Any], result: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        report_id = str(job.get("report_id") or "")
        employee_id = str(job.get("employee_id") or "")
        if not report_id or not employee_id:
            return
        self.initialize()
        now = utc_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO inbox_report_jobs(
                    report_id, employee_id, report_type, source_kind, task_ref,
                    status, attempts, next_attempt_at, lease_until, result_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'ready', 0, 0, 0, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    status='ready', next_attempt_at=0, lease_until=0,
                    last_error_code='', last_error_message='',
                    result_json=excluded.result_json, updated_at=excluded.updated_at
                """,
                (
                    report_id,
                    employee_id,
                    str(job.get("report_type") or "item"),
                    str(job.get("source_kind") or "active"),
                    str(job.get("task_ref") or ""),
                    json.dumps(result or {}, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
        with self._state_lock:
            self._state["last_success_at"] = now
            self._state["last_error"] = ""

    def mark_ignored(self, job: dict[str, Any], reason: str = "") -> None:
        if not self.enabled:
            return
        with self._connect() as connection:
            connection.execute(
                "UPDATE inbox_report_jobs SET status='ignored', lease_until=0, "
                "last_error_message=?, updated_at=? WHERE report_id=?",
                (reason[:500], utc_iso(), str(job.get("report_id") or "")),
            )

    def state_for(self, report_id: str) -> dict[str, Any] | None:
        if not self.enabled or not report_id:
            return None
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM inbox_report_jobs WHERE report_id=?",
                (report_id,),
            ).fetchone()
        return dict(row) if row else None

    def _claim(self) -> dict[str, Any] | None:
        now_epoch = time.time()
        now = utc_iso()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM inbox_report_jobs
                WHERE status IN ('queued', 'retry_wait') AND next_attempt_at <= ?
                ORDER BY created_at ASC LIMIT 1
                """,
                (now_epoch,),
            ).fetchone()
            if not row:
                connection.commit()
                return None
            connection.execute(
                "UPDATE inbox_report_jobs SET status='running', lease_until=?, updated_at=? WHERE report_id=?",
                (now_epoch + self.lease_seconds, now, str(row["report_id"])),
            )
            connection.commit()
        claimed = dict(row)
        claimed["status"] = "running"
        return claimed

    @staticmethod
    def _retry_delay(attempts: int) -> float:
        schedule = (30.0, 120.0, 600.0, 3600.0, 21600.0)
        return schedule[min(max(attempts - 1, 0), len(schedule) - 1)]

    def _retry(self, job: dict[str, Any], error: Exception) -> None:
        attempts = int(job.get("attempts") or 0) + 1
        delay = self._retry_delay(attempts)
        message = f"{type(error).__name__}: {error}"[:500]
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE inbox_report_jobs
                SET status='retry_wait', attempts=?, next_attempt_at=?, lease_until=0,
                    last_error_code=?, last_error_message=?, updated_at=?
                WHERE report_id=?
                """,
                (
                    attempts,
                    time.time() + delay,
                    str(getattr(error, "code", "inbox_report_generation_failed")),
                    message,
                    utc_iso(),
                    str(job.get("report_id") or ""),
                ),
            )
        with self._state_lock:
            self._state["last_error"] = message

    def scan_once(self) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "queued": 0, "deferred": 0}
        jobs = self.discover_jobs()
        queued = 0
        deferred = 0
        for job in jobs:
            if job.get("ready"):
                self.mark_ready(job, job.get("result") if isinstance(job.get("result"), dict) else {})
                continue
            existing = self.state_for(str(job.get("report_id") or ""))
            if existing and str(existing.get("status") or "") in PENDING_STATES | {"ready", "ignored"}:
                continue
            if queued >= self.batch_size:
                deferred += 1
                continue
            if self.enqueue(job):
                queued += 1
        now = utc_iso()
        with self._state_lock:
            self._state.update({"status": "running", "last_scan_at": now, "deferred": deferred})
        return {"status": "scanned", "queued": queued, "deferred": deferred, "discovered": len(jobs)}

    def process_once(self) -> bool:
        if not self.enabled:
            return False
        job = self._claim()
        if not job:
            return False
        try:
            result = self.process_job(job)
            status = str(result.get("status") or result.get("report_state") or "ready")
            if status in {"ignored", "missing"}:
                self.mark_ignored(job, str(result.get("message") or status))
            else:
                self.mark_ready(job, result)
        except Exception as exc:  # coordinator must survive individual report failures
            self._retry(job, exc)
        return True

    def diagnostics(self) -> dict[str, Any]:
        if not self.enabled:
            return {**self._state, "enabled": False, "db_path": str(self.db_path)}
        self.initialize()
        counts: dict[str, int] = {}
        with self._connect() as connection:
            for row in connection.execute(
                "SELECT status, COUNT(*) AS count FROM inbox_report_jobs GROUP BY status"
            ).fetchall():
                counts[str(row["status"])] = int(row["count"])
        with self._state_lock:
            state = dict(self._state)
        return {
            **state,
            "enabled": True,
            "db_path": str(self.db_path),
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "retrying": counts.get("retry_wait", 0),
            "ready": counts.get("ready", 0),
            "ignored": counts.get("ignored", 0),
        }

    def _run(self) -> None:
        with self._state_lock:
            self._state["status"] = "running"
        next_scan = 0.0
        rescan_when_idle = False
        while not self._stop.is_set():
            now = time.monotonic()
            if now >= next_scan or rescan_when_idle or self._scan_requested.is_set():
                self._scan_requested.clear()
                try:
                    scan = self.scan_once()
                    rescan_when_idle = int(scan.get("deferred") or 0) > 0
                except Exception as exc:  # discovery failures should not stop retry processing
                    with self._state_lock:
                        self._state["last_error"] = f"{type(exc).__name__}: {exc}"[:500]
                    rescan_when_idle = False
                next_scan = time.monotonic() + self.scan_interval_seconds
            if self.process_once():
                continue
            if rescan_when_idle:
                continue
            timeout = max(0.2, min(self.scan_interval_seconds, next_scan - time.monotonic()))
            self._wake.wait(timeout=timeout)
            self._wake.clear()
        with self._state_lock:
            self._state["status"] = "stopped"
