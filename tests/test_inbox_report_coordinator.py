from __future__ import annotations

import sqlite3
from pathlib import Path

from boi_api.app.inbox_report_coordinator import InboxReportCoordinator


def test_coordinator_backfills_active_and_seed_jobs_durably(tmp_path: Path) -> None:
    processed: list[str] = []
    jobs = [
        {
            "report_id": "inbox-report-item-active0000000000",
            "employee_id": "100001",
            "report_type": "item",
            "source_kind": "active",
            "task_ref": "task:active",
        },
        {
            "report_id": "inbox-report-item-seed00000000000",
            "employee_id": "100001",
            "report_type": "item",
            "source_kind": "seed",
            "task_ref": "task:seed",
        },
    ]

    def process(job: dict) -> dict:
        processed.append(str(job["report_id"]))
        return {"report_state": "ready", "report_boi_ref": f"boi:{job['report_id']}"}

    db_path = tmp_path / "coordinator.sqlite3"
    coordinator = InboxReportCoordinator(
        db_path=db_path,
        discover_jobs=lambda: jobs,
        process_job=process,
        batch_size=8,
    )

    scan = coordinator.scan_once()
    assert scan["queued"] == 2
    assert coordinator.process_once() is True
    assert coordinator.process_once() is True
    assert coordinator.process_once() is False
    assert set(processed) == {job["report_id"] for job in jobs}
    assert coordinator.diagnostics()["ready"] == 2

    restarted = InboxReportCoordinator(
        db_path=db_path,
        discover_jobs=lambda: jobs,
        process_job=lambda _job: (_ for _ in ()).throw(AssertionError("ready jobs must not rerun")),
    )
    restarted.initialize()
    assert restarted.scan_once()["queued"] == 0
    assert restarted.diagnostics()["ready"] == 2

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(inbox_report_jobs)")}
    assert "items" not in columns
    assert "raw_payload" not in columns


def test_coordinator_retries_failure_without_losing_job(tmp_path: Path) -> None:
    job = {
        "report_id": "inbox-report-item-retry0000000000",
        "employee_id": "100001",
        "report_type": "item",
        "source_kind": "seed",
        "task_ref": "task:retry",
    }
    coordinator = InboxReportCoordinator(
        db_path=tmp_path / "coordinator.sqlite3",
        discover_jobs=lambda: [job],
        process_job=lambda _job: (_ for _ in ()).throw(RuntimeError("temporary model error")),
    )

    coordinator.scan_once()
    assert coordinator.process_once() is True
    state = coordinator.state_for(job["report_id"])
    assert state is not None
    assert state["status"] == "retry_wait"
    assert state["attempts"] == 1
    assert "temporary model error" in state["last_error_message"]


def test_coordinator_reclaims_running_job_immediately_after_restart(tmp_path: Path) -> None:
    job = {
        "report_id": "inbox-report-item-restart00000000",
        "employee_id": "100001",
        "report_type": "item",
        "source_kind": "active",
        "task_ref": "task:restart",
    }
    db_path = tmp_path / "coordinator.sqlite3"
    first = InboxReportCoordinator(
        db_path=db_path,
        discover_jobs=lambda: [job],
        process_job=lambda _job: {"report_state": "ready"},
    )
    first.scan_once()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE inbox_report_jobs SET status='running', lease_until=9999999999 WHERE report_id=?",
            (job["report_id"],),
        )

    restarted = InboxReportCoordinator(
        db_path=db_path,
        discover_jobs=lambda: [job],
        process_job=lambda _job: {"report_state": "ready"},
    )
    restarted.initialize()

    assert restarted.state_for(job["report_id"])["status"] == "queued"
