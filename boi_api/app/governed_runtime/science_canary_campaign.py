"""Fixed-schedule Science canary campaign with no Release authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Literal, Mapping

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .science_canary import (
    SHA256_RE,
    PinnedCheckSpec,
    ScienceCanaryError,
    ScienceCanaryRunner,
)
from .science_evaluator import PrimaryVerdict


CAMPAIGN_REQUEST_COUNT = 100
CAMPAIGN_MINIMUM_DURATION = timedelta(hours=48)
DEFAULT_INTERVAL_SECONDS = 30 * 60
DEFAULT_MAXIMUM_LATENESS_SECONDS = DEFAULT_INTERVAL_SECONDS - 60


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _aware_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ScienceCanaryError("CAMPAIGN_TIME_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScienceCanaryError("CAMPAIGN_TIMEZONE_REQUIRED")
    return parsed


@dataclass(frozen=True)
class ScienceCanaryScheduledRequest:
    request_id: str
    sequence: int
    relative_path: str
    scheduled_at: str


@dataclass(frozen=True)
class ScienceCanarySchedule:
    schema_name: Literal["boi-science-canary-schedule/v1"]
    campaign_id: str
    package_digest: str
    check_id: str
    check_script_digest: str
    start_at: str
    interval_seconds: int
    maximum_lateness_seconds: int
    minimum_duration_seconds: int
    requests: tuple[ScienceCanaryScheduledRequest, ...]
    schedule_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_name": self.schema_name,
            "campaign_id": self.campaign_id,
            "package_digest": self.package_digest,
            "check_id": self.check_id,
            "check_script_digest": self.check_script_digest,
            "start_at": self.start_at,
            "interval_seconds": self.interval_seconds,
            "maximum_lateness_seconds": self.maximum_lateness_seconds,
            "minimum_duration_seconds": self.minimum_duration_seconds,
            "requests": [asdict(item) for item in self.requests],
            "schedule_digest": self.schedule_digest,
        }


@dataclass(frozen=True)
class ScienceCanaryProgress:
    campaign_id: str
    schedule_digest: str
    observed_at: str
    completed_requests: int
    consistent_requests: int
    failed_requests: int
    elapsed_seconds: int
    request_gate_passed: bool
    duration_gate_passed: bool
    quality_gate_passed: bool
    eligible_for_qualification: bool
    progress_digest: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class ScienceCanaryCampaignRunReceipt:
    campaign_id: str
    schedule_digest: str
    executed_request_count: int
    executed_request_ids: tuple[str, ...]
    progress: ScienceCanaryProgress


def build_science_canary_schedule(
    *,
    campaign_id: str,
    package_digest: str,
    check_id: str,
    check_script_digest: str,
    relative_paths: tuple[str, ...],
    start_at: str,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    maximum_lateness_seconds: int = DEFAULT_MAXIMUM_LATENESS_SECONDS,
) -> ScienceCanarySchedule:
    campaign_id = campaign_id.strip()
    check_id = check_id.strip()
    paths = tuple(path.strip() for path in relative_paths)
    if not campaign_id or not check_id or not paths or any(not path for path in paths):
        raise ScienceCanaryError("CAMPAIGN_IDENTITY_REQUIRED")
    if len(paths) != len(set(paths)):
        raise ScienceCanaryError("CAMPAIGN_PATHS_MUST_BE_UNIQUE")
    if not SHA256_RE.fullmatch(package_digest) or not SHA256_RE.fullmatch(
        check_script_digest
    ):
        raise ScienceCanaryError("CAMPAIGN_DIGEST_INVALID")
    if interval_seconds < 1:
        raise ScienceCanaryError("CAMPAIGN_INTERVAL_INVALID")
    if not 0 <= maximum_lateness_seconds < interval_seconds:
        raise ScienceCanaryError("CAMPAIGN_LATENESS_WINDOW_INVALID")
    duration = timedelta(seconds=interval_seconds * (CAMPAIGN_REQUEST_COUNT - 1))
    if duration < CAMPAIGN_MINIMUM_DURATION:
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_SHORTER_THAN_48_HOURS")
    start = _aware_datetime(start_at)
    requests: list[ScienceCanaryScheduledRequest] = []
    for index in range(CAMPAIGN_REQUEST_COUNT):
        scheduled_at = (start + timedelta(seconds=index * interval_seconds)).isoformat()
        relative_path = paths[index % len(paths)]
        base = {
            "campaign_id": campaign_id,
            "sequence": index + 1,
            "relative_path": relative_path,
            "scheduled_at": scheduled_at,
            "package_digest": package_digest,
            "check_id": check_id,
            "check_script_digest": check_script_digest,
        }
        requests.append(
            ScienceCanaryScheduledRequest(
                request_id=f"science-canary-request:{_digest(base)}",
                sequence=index + 1,
                relative_path=relative_path,
                scheduled_at=scheduled_at,
            )
        )
    base = {
        "schema_name": "boi-science-canary-schedule/v1",
        "campaign_id": campaign_id,
        "package_digest": package_digest,
        "check_id": check_id,
        "check_script_digest": check_script_digest,
        "start_at": start.isoformat(),
        "interval_seconds": interval_seconds,
        "maximum_lateness_seconds": maximum_lateness_seconds,
        "minimum_duration_seconds": int(CAMPAIGN_MINIMUM_DURATION.total_seconds()),
        "requests": [asdict(item) for item in requests],
    }
    return ScienceCanarySchedule(
        schema_name=base["schema_name"],
        campaign_id=campaign_id,
        package_digest=package_digest,
        check_id=check_id,
        check_script_digest=check_script_digest,
        start_at=start.isoformat(),
        interval_seconds=interval_seconds,
        maximum_lateness_seconds=maximum_lateness_seconds,
        minimum_duration_seconds=int(CAMPAIGN_MINIMUM_DURATION.total_seconds()),
        requests=tuple(requests),
        schedule_digest=_digest(base),
    )


def parse_science_canary_schedule(
    value: Mapping[str, object],
) -> ScienceCanarySchedule:
    expected_keys = {
        "schema_name",
        "campaign_id",
        "package_digest",
        "check_id",
        "check_script_digest",
        "start_at",
        "interval_seconds",
        "maximum_lateness_seconds",
        "minimum_duration_seconds",
        "requests",
        "schedule_digest",
    }
    if set(value) != expected_keys or value.get("schema_name") != (
        "boi-science-canary-schedule/v1"
    ):
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_SCHEMA_INVALID")
    raw_requests = value.get("requests")
    if (
        not isinstance(raw_requests, list)
        or len(raw_requests) != CAMPAIGN_REQUEST_COUNT
    ):
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_REQUEST_COUNT")
    try:
        campaign_id = str(value["campaign_id"])
        package_digest = str(value["package_digest"])
        check_id = str(value["check_id"])
        check_script_digest = str(value["check_script_digest"])
        start_at = str(value["start_at"])
        interval_seconds = int(value["interval_seconds"])
        maximum_lateness_seconds = int(value["maximum_lateness_seconds"])
        minimum_duration_seconds = int(value["minimum_duration_seconds"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_SCHEMA_INVALID") from exc
    if (
        not campaign_id
        or not check_id
        or not SHA256_RE.fullmatch(package_digest)
        or not SHA256_RE.fullmatch(check_script_digest)
        or interval_seconds < 1
        or not 0 <= maximum_lateness_seconds < interval_seconds
        or minimum_duration_seconds != int(CAMPAIGN_MINIMUM_DURATION.total_seconds())
    ):
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_SCHEMA_INVALID")
    start = _aware_datetime(start_at)
    requests: list[ScienceCanaryScheduledRequest] = []
    for index, raw_request in enumerate(raw_requests):
        if not isinstance(raw_request, dict) or set(raw_request) != {
            "request_id",
            "sequence",
            "relative_path",
            "scheduled_at",
        }:
            raise ScienceCanaryError("CAMPAIGN_SCHEDULE_REQUEST_INVALID")
        sequence = index + 1
        relative_path = str(raw_request["relative_path"])
        scheduled_at = str(raw_request["scheduled_at"])
        expected_at = (start + timedelta(seconds=index * interval_seconds)).isoformat()
        request_base = {
            "campaign_id": campaign_id,
            "sequence": sequence,
            "relative_path": relative_path,
            "scheduled_at": scheduled_at,
            "package_digest": package_digest,
            "check_id": check_id,
            "check_script_digest": check_script_digest,
        }
        expected_id = f"science-canary-request:{_digest(request_base)}"
        if (
            raw_request["sequence"] != sequence
            or not relative_path
            or scheduled_at != expected_at
            or raw_request["request_id"] != expected_id
        ):
            raise ScienceCanaryError("CAMPAIGN_SCHEDULE_REQUEST_INVALID")
        requests.append(
            ScienceCanaryScheduledRequest(
                request_id=expected_id,
                sequence=sequence,
                relative_path=relative_path,
                scheduled_at=scheduled_at,
            )
        )
    digest_base = {key: value[key] for key in expected_keys - {"schedule_digest"}}
    schedule_digest = str(value["schedule_digest"])
    if schedule_digest != _digest(digest_base):
        raise ScienceCanaryError("CAMPAIGN_SCHEDULE_DIGEST_MISMATCH")
    return ScienceCanarySchedule(
        schema_name="boi-science-canary-schedule/v1",
        campaign_id=campaign_id,
        package_digest=package_digest,
        check_id=check_id,
        check_script_digest=check_script_digest,
        start_at=start.isoformat(),
        interval_seconds=interval_seconds,
        maximum_lateness_seconds=maximum_lateness_seconds,
        minimum_duration_seconds=minimum_duration_seconds,
        requests=tuple(requests),
        schedule_digest=schedule_digest,
    )


def evaluate_science_canary_progress(
    schedule: ScienceCanarySchedule,
    *,
    completed_request_ids: Iterable[str],
    observed_at: str,
    failed_request_ids: Iterable[str] = (),
) -> ScienceCanaryProgress:
    known_ids = {item.request_id for item in schedule.requests}
    completed = set(completed_request_ids)
    failed = set(failed_request_ids)
    if not completed <= known_ids or not failed <= completed:
        raise ScienceCanaryError("CAMPAIGN_PROGRESS_REQUEST_UNKNOWN")
    observed = _aware_datetime(observed_at)
    start = _aware_datetime(schedule.start_at)
    elapsed_seconds = max(0, int((observed - start).total_seconds()))
    request_gate_passed = len(completed) == CAMPAIGN_REQUEST_COUNT
    duration_gate_passed = elapsed_seconds >= schedule.minimum_duration_seconds
    quality_gate_passed = not failed and len(completed) == CAMPAIGN_REQUEST_COUNT
    eligible = request_gate_passed and duration_gate_passed and quality_gate_passed
    values = {
        "campaign_id": schedule.campaign_id,
        "schedule_digest": schedule.schedule_digest,
        "observed_at": observed.isoformat(),
        "completed_request_ids": sorted(completed),
        "failed_request_ids": sorted(failed),
        "elapsed_seconds": elapsed_seconds,
        "request_gate_passed": request_gate_passed,
        "duration_gate_passed": duration_gate_passed,
        "quality_gate_passed": quality_gate_passed,
        "eligible_for_qualification": eligible,
        "qualification_receipt_id": None,
        "release_manifest_id": None,
        "active_release_transition": False,
    }
    return ScienceCanaryProgress(
        campaign_id=schedule.campaign_id,
        schedule_digest=schedule.schedule_digest,
        observed_at=observed.isoformat(),
        completed_requests=len(completed),
        consistent_requests=len(completed - failed),
        failed_requests=len(failed),
        elapsed_seconds=elapsed_seconds,
        request_gate_passed=request_gate_passed,
        duration_gate_passed=duration_gate_passed,
        quality_gate_passed=quality_gate_passed,
        eligible_for_qualification=eligible,
        progress_digest=_digest(values),
    )


def _campaign_observations(
    ledger: GovernedRuntimeLedger,
    schedule: ScienceCanarySchedule,
) -> tuple[set[str], set[str]]:
    verification = ledger.verify()
    if not verification.ok:
        raise ScienceCanaryError("CAMPAIGN_LEDGER_INVALID")
    observed: dict[str, tuple[str, bool]] = {}
    run_root = ledger.records_root / RecordKind.RUN.value
    for path in sorted(run_root.glob("*.json")) if run_root.exists() else ():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            record = ledger.read(str(stored["record_id"]))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError, LedgerError) as exc:
            raise ScienceCanaryError("CAMPAIGN_LEDGER_INVALID") from exc
        payload = record.payload
        if payload.get("scope") != "science-canary-campaign-observation":
            continue
        if payload.get("campaign_id") != schedule.campaign_id:
            continue
        if payload.get("schedule_digest") != schedule.schedule_digest:
            raise ScienceCanaryError("CAMPAIGN_SCHEDULE_DRIFT")
        request_id = str(payload.get("request_id") or "")
        child_run_id = str(payload.get("child_run_id") or "")
        passed = payload.get("passed") is True
        prior = observed.get(request_id)
        if prior is not None and prior != (child_run_id, passed):
            raise ScienceCanaryError("CAMPAIGN_DUPLICATE_OBSERVATION")
        child = ledger.read(child_run_id)
        if (
            child.kind is not RecordKind.RUN
            or child.payload.get("scope") != "science-canary"
        ):
            raise ScienceCanaryError("CAMPAIGN_CHILD_RUN_INVALID")
        observed[request_id] = (child_run_id, passed)
    known_ids = {item.request_id for item in schedule.requests}
    if not set(observed) <= known_ids:
        raise ScienceCanaryError("CAMPAIGN_PROGRESS_REQUEST_UNKNOWN")
    completed = set(observed)
    failed = {request_id for request_id, (_, passed) in observed.items() if not passed}
    return completed, failed


class ScienceCanaryCampaignRunner:
    @classmethod
    def run_due(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanarySchedule,
        check: PinnedCheckSpec,
        ledger: GovernedRuntimeLedger,
        observed_at: str,
        max_requests: int | None = None,
    ) -> ScienceCanaryCampaignRunReceipt:
        if check.check_id != schedule.check_id or check.script_digest != (
            schedule.check_script_digest
        ):
            raise ScienceCanaryError("CAMPAIGN_CHECK_DRIFT")
        manifest = ScienceCanaryRunner._load_manifest(Path(package_path))
        if manifest.get("package_digest") != schedule.package_digest:
            raise ScienceCanaryError("CAMPAIGN_PACKAGE_DRIFT")
        observed = _aware_datetime(observed_at)
        completed, failed = _campaign_observations(ledger, schedule)
        due = [
            request
            for request in schedule.requests
            if _aware_datetime(request.scheduled_at) <= observed
            and request.request_id not in completed
        ]
        if (
            due
            and (observed - _aware_datetime(due[0].scheduled_at)).total_seconds()
            > schedule.maximum_lateness_seconds
        ):
            raise ScienceCanaryError("CAMPAIGN_REQUEST_WINDOW_MISSED")
        if max_requests is not None:
            if max_requests < 0:
                raise ScienceCanaryError("CAMPAIGN_MAX_REQUESTS_INVALID")
            due = due[:max_requests]
        executed: list[str] = []
        for request in due:
            child = ScienceCanaryRunner.run(
                package_path,
                relative_paths=[request.relative_path],
                check=check,
                ledger=ledger,
                occurred_at=observed.isoformat(),
            )
            passed = (
                child.verdict_counts == {PrimaryVerdict.CONSISTENT.value: 1}
                and not child.execution_error_counts
            )
            ledger.append(
                RecordKind.RUN,
                {
                    "scope": "science-canary-campaign-observation",
                    "campaign_id": schedule.campaign_id,
                    "schedule_digest": schedule.schedule_digest,
                    "request_id": request.request_id,
                    "sequence": request.sequence,
                    "scheduled_at": request.scheduled_at,
                    "relative_path_digest": _digest(request.relative_path),
                    "child_run_id": child.run_id,
                    "passed": passed,
                    "verdict_counts": child.verdict_counts,
                    "execution_error_counts": child.execution_error_counts,
                    "qualification_receipt_id": None,
                    "release_manifest_id": None,
                    "active_release_transition": False,
                },
                authority="science_evaluator",
                occurred_at=observed.isoformat(),
            )
            executed.append(request.request_id)
        completed, failed = _campaign_observations(ledger, schedule)
        progress = evaluate_science_canary_progress(
            schedule,
            completed_request_ids=completed,
            failed_request_ids=failed,
            observed_at=observed.isoformat(),
        )
        return ScienceCanaryCampaignRunReceipt(
            campaign_id=schedule.campaign_id,
            schedule_digest=schedule.schedule_digest,
            executed_request_count=len(executed),
            executed_request_ids=tuple(executed),
            progress=progress,
        )
