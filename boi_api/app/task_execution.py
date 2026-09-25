from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _values(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        candidates = raw.replace(",", " ").split()
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(item) for item in raw]
    else:
        candidates = [str(raw)]
    return list(dict.fromkeys(item.strip() for item in candidates if item.strip()))


def task_identity(row: dict[str, Any]) -> str:
    return str(row.get("request_id") or row.get("_log_ref") or row.get("task_id") or "").removeprefix("task:")


def task_storage_key(row: dict[str, Any]) -> str:
    identity = task_identity(row) or "unbound"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:28]


class TaskExecutionStore:
    """Small durable store for shared assignment and human work records.

    The task identity is independent from the viewer so several assignees see
    and update one execution state while every record still retains its actor.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.assignments_root = self.root / "assignments"
        self.assignment_history_root = self.root / "assignment-history"
        self.records_root = self.root / "work-records"

    def _atomic_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def assignment(self, row: dict[str, Any]) -> dict[str, Any]:
        key = task_storage_key(row)
        path = self.assignments_root / f"{key}.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except (OSError, json.JSONDecodeError):
                pass
        embedded = row.get("assignment_design") if isinstance(row.get("assignment_design"), dict) else {}
        assignment = row.get("assignment") if isinstance(row.get("assignment"), dict) else {}
        assignees = _values(
            embedded.get("assignee_employee_ids")
            or assignment.get("assignee_employee_ids")
            or row.get("assignee_employee_ids")
            or row.get("assigned_employee_ids")
            or row.get("employee_id")
        )
        return {
            "task_key": key,
            "task_identity": task_identity(row),
            "assignee_employee_ids": assignees,
            "reviewer_employee_ids": _values(embedded.get("reviewer_employee_ids") or assignment.get("reviewer_employee_ids")),
            "related_team_ids": _values(embedded.get("related_team_ids") or assignment.get("related_team_ids")),
            "completion_policy": "any_assignee",
            "revision": 0,
            "updated_at": "",
            "updated_by": "",
        }

    def update_assignment(
        self,
        row: dict[str, Any],
        *,
        actor_employee_id: str,
        assignee_employee_ids: list[str],
        reviewer_employee_ids: list[str],
        related_team_ids: list[str],
        expected_revision: int | None,
    ) -> dict[str, Any]:
        with _LOCK:
            current = self.assignment(row)
            revision = int(current.get("revision") or 0)
            if expected_revision is not None and expected_revision != revision:
                raise ValueError("assignment_revision_conflict")
            payload = {
                **current,
                "assignee_employee_ids": _values(assignee_employee_ids),
                "reviewer_employee_ids": _values(reviewer_employee_ids),
                "related_team_ids": _values(related_team_ids),
                "completion_policy": "any_assignee",
                "revision": revision + 1,
                "updated_at": _now_iso(),
                "updated_by": actor_employee_id,
            }
            self._atomic_json(self.assignments_root / f"{payload['task_key']}.json", payload)
            history_path = self.assignment_history_root / f"{payload['task_key']}.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with history_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "change_id": f"assignment-change-{uuid.uuid4().hex}",
                            "task_key": payload["task_key"],
                            "revision": payload["revision"],
                            "changed_at": payload["updated_at"],
                            "changed_by": actor_employee_id,
                            "before": current,
                            "after": payload,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
            return payload

    def assignment_history(self, row: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        path = self.assignment_history_root / f"{task_storage_key(row)}.jsonl"
        if not path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result[-max(1, min(limit, 500)) :]

    def records(self, row: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        path = self.records_root / f"{task_storage_key(row)}.jsonl"
        if not path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
        return records[-max(1, min(limit, 500)) :]

    def append_record(self, row: dict[str, Any], record: dict[str, Any], actor_employee_id: str) -> dict[str, Any]:
        key = task_storage_key(row)
        payload = {
            "record_id": f"work-record-{uuid.uuid4().hex}",
            "task_key": key,
            "task_identity": task_identity(row),
            "actor_employee_id": actor_employee_id,
            "recorded_at": _now_iso(),
            **record,
        }
        path = self.records_root / f"{key}.jsonl"
        with _LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        return payload
