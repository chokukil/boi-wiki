"""Trusted-time Science canary v2, isolated from the historical v1 campaign."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable, Literal, Mapping

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .science_canary import SHA256_RE, PinnedCheckSpec, ScienceCanaryError, ScienceCanaryRunner
from .science_evaluator import PrimaryVerdict


REQUEST_COUNT = 100
MINIMUM_DURATION = timedelta(hours=48)
INTERVAL_SECONDS = 30 * 60
MAXIMUM_LATENESS_SECONDS = INTERVAL_SECONDS - 60
MAXIMUM_FUTURE_SECONDS = 5
MAXIMUM_CLOCK_JUMP_SECONDS = 120


def science_canary_runtime_code_digest() -> str:
    """Digest the exact deterministic code closure used by each v2 tick."""

    root = Path(__file__).resolve().parent
    closure = {}
    for name in (
        "ledger.py",
        "science_canary.py",
        "science_canary_campaign_v2.py",
        "science_evaluator.py",
    ):
        payload = (root / name).read_bytes()
        closure[name] = "sha256:" + hashlib.sha256(payload).hexdigest()
    return _digest(closure)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _aware(value: str | datetime) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as error:
        raise ScienceCanaryError("TRUSTED_TIME_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScienceCanaryError("TRUSTED_TIME_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _require_digest(value: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ScienceCanaryError("V2_DIGEST_INVALID")


@dataclass(frozen=True)
class ScienceCanaryScheduledRequestV2:
    request_id: str
    sequence: int
    relative_path: str
    scheduled_at: str


@dataclass(frozen=True)
class ScienceCanaryScheduleV2:
    schema_name: Literal["boi-science-canary-schedule/v2"]
    campaign_id: str
    package_digest: str
    check_id: str
    check_script_digest: str
    start_at: str
    interval_seconds: int
    maximum_lateness_seconds: int
    minimum_duration_seconds: int
    scheduler_id: str
    scheduler_revision_digest: str
    reviewed_by: str
    review_approval_digest: str
    requests: tuple[ScienceCanaryScheduledRequestV2, ...]
    schedule_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "requests": [asdict(item) for item in self.requests],
        }


@dataclass(frozen=True)
class TrustedTimeSampleV2:
    wall_time: str
    monotonic_ns: int
    boot_id: str
    scheduler_invocation_id: str


@dataclass(frozen=True)
class ScienceCanaryProgressV2:
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
    v1_carried_request_count: Literal[0]
    progress_digest: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class ScienceCanarySchedulerTickV2:
    schema_name: Literal["boi-science-canary-scheduler-tick/v2"]
    campaign_id: str
    schedule_digest: str
    scheduler_id: str
    scheduler_revision_digest: str
    scheduler_invocation_id: str
    wall_time: str
    monotonic_ns: int
    boot_id: str
    previous_observation_digest: str | None
    observation_digest: str
    executed_request_count: int
    executed_request_ids: tuple[str, ...]
    progress_digest: str
    tick_receipt_digest: str
    idempotent_replay: bool = False


@dataclass(frozen=True)
class ScienceCanaryCampaignRunReceiptV2:
    tick: ScienceCanarySchedulerTickV2
    progress: ScienceCanaryProgressV2


def build_science_canary_schedule_v2(
    *,
    campaign_id: str,
    package_digest: str,
    check_id: str,
    check_script_digest: str,
    relative_paths: tuple[str, ...],
    start_at: str,
    scheduler_id: str,
    scheduler_revision_digest: str,
    reviewed_by: str,
    review_approval_digest: str,
    interval_seconds: int = INTERVAL_SECONDS,
    maximum_lateness_seconds: int = MAXIMUM_LATENESS_SECONDS,
) -> ScienceCanaryScheduleV2:
    identity = tuple(
        value.strip()
        for value in (campaign_id, check_id, scheduler_id, reviewed_by)
    )
    paths = tuple(path.strip() for path in relative_paths)
    if any(not value for value in identity) or not paths or any(not path for path in paths):
        raise ScienceCanaryError("V2_SCHEDULE_IDENTITY_REQUIRED")
    if len(paths) != len(set(paths)):
        raise ScienceCanaryError("V2_SCHEDULE_PATHS_NOT_UNIQUE")
    for value in (
        package_digest,
        check_script_digest,
        scheduler_revision_digest,
        review_approval_digest,
    ):
        _require_digest(value)
    if interval_seconds < 1 or not 0 <= maximum_lateness_seconds < interval_seconds:
        raise ScienceCanaryError("V2_SCHEDULE_INTERVAL_INVALID")
    if timedelta(seconds=interval_seconds * (REQUEST_COUNT - 1)) < MINIMUM_DURATION:
        raise ScienceCanaryError("V2_SCHEDULE_SHORTER_THAN_48_HOURS")
    start = _aware(start_at)
    requests = []
    for index in range(REQUEST_COUNT):
        scheduled_at = (start + timedelta(seconds=index * interval_seconds)).isoformat()
        relative_path = paths[index % len(paths)]
        request_values = {
            "campaign_id": identity[0],
            "sequence": index + 1,
            "relative_path": relative_path,
            "scheduled_at": scheduled_at,
            "package_digest": package_digest,
            "check_id": identity[1],
            "check_script_digest": check_script_digest,
            "scheduler_revision_digest": scheduler_revision_digest,
            "review_approval_digest": review_approval_digest,
        }
        requests.append(
            ScienceCanaryScheduledRequestV2(
                request_id=f"science-canary-v2-request:{_digest(request_values)}",
                sequence=index + 1,
                relative_path=relative_path,
                scheduled_at=scheduled_at,
            )
        )
    values = {
        "schema_name": "boi-science-canary-schedule/v2",
        "campaign_id": identity[0],
        "package_digest": package_digest,
        "check_id": identity[1],
        "check_script_digest": check_script_digest,
        "start_at": start.isoformat(),
        "interval_seconds": interval_seconds,
        "maximum_lateness_seconds": maximum_lateness_seconds,
        "minimum_duration_seconds": int(MINIMUM_DURATION.total_seconds()),
        "scheduler_id": identity[2],
        "scheduler_revision_digest": scheduler_revision_digest,
        "reviewed_by": identity[3],
        "review_approval_digest": review_approval_digest,
        "requests": [asdict(item) for item in requests],
    }
    return ScienceCanaryScheduleV2(
        **{**values, "requests": tuple(requests)},
        schedule_digest=_digest(values),
    )


def parse_science_canary_schedule_v2(
    value: Mapping[str, object],
) -> ScienceCanaryScheduleV2:
    expected_keys = {
        "schema_name", "campaign_id", "package_digest", "check_id",
        "check_script_digest", "start_at", "interval_seconds",
        "maximum_lateness_seconds", "minimum_duration_seconds", "scheduler_id",
        "scheduler_revision_digest", "reviewed_by", "review_approval_digest",
        "requests", "schedule_digest",
    }
    if set(value) != expected_keys or value.get("schema_name") != "boi-science-canary-schedule/v2":
        raise ScienceCanaryError("V2_SCHEDULE_SCHEMA_INVALID")
    raw_requests = value.get("requests")
    if not isinstance(raw_requests, list) or len(raw_requests) != REQUEST_COUNT:
        raise ScienceCanaryError("V2_SCHEDULE_REQUEST_COUNT")
    try:
        rebuilt = build_science_canary_schedule_v2(
            campaign_id=str(value["campaign_id"]),
            package_digest=str(value["package_digest"]),
            check_id=str(value["check_id"]),
            check_script_digest=str(value["check_script_digest"]),
            relative_paths=tuple(
                dict.fromkeys(str(item["relative_path"]) for item in raw_requests)
            ),
            start_at=str(value["start_at"]),
            scheduler_id=str(value["scheduler_id"]),
            scheduler_revision_digest=str(value["scheduler_revision_digest"]),
            reviewed_by=str(value["reviewed_by"]),
            review_approval_digest=str(value["review_approval_digest"]),
            interval_seconds=int(value["interval_seconds"]),
            maximum_lateness_seconds=int(value["maximum_lateness_seconds"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ScienceCanaryError("V2_SCHEDULE_SCHEMA_INVALID") from error
    if rebuilt.to_dict() != dict(value):
        raise ScienceCanaryError("V2_SCHEDULE_DIGEST_OR_REQUEST_MISMATCH")
    return rebuilt


class ScienceCanaryV2Ledger:
    """A fresh, schedule-bound ledger root that refuses historical v1 events."""

    def __init__(self, root: Path, *, campaign_id: str, schedule_digest: str) -> None:
        _require_digest(schedule_digest)
        self.root = root
        self.binding_path = root / "science-canary-v2-binding.json"
        existing_events = root / "events.jsonl"
        if not self.binding_path.exists() and existing_events.exists() and existing_events.stat().st_size:
            raise ScienceCanaryError("V2_LEDGER_NOT_FRESH")
        values = {
            "schema_name": "boi-science-canary-ledger-binding/v2",
            "campaign_id": campaign_id,
            "schedule_digest": schedule_digest,
            "v1_carried_request_count": 0,
        }
        payload = {**values, "binding_digest": _digest(values)}
        encoded = _canonical_json(payload) + b"\n"
        root.mkdir(parents=True, exist_ok=True)
        if self.binding_path.exists():
            if self.binding_path.read_bytes() != encoded:
                raise ScienceCanaryError("V2_LEDGER_BINDING_CONFLICT")
        else:
            self.binding_path.write_bytes(encoded)
        self.campaign_id = campaign_id
        self.schedule_digest = schedule_digest
        self.ledger = GovernedRuntimeLedger(root)

    def _records(self, scope: str) -> Iterable[dict[str, object]]:
        run_root = self.ledger.records_root / RecordKind.RUN.value
        for path in sorted(run_root.glob("*.json")) if run_root.exists() else ():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                record = self.ledger.read(str(stored["record_id"]))
            except (OSError, KeyError, ValueError, LedgerError) as error:
                raise ScienceCanaryError("V2_LEDGER_INVALID") from error
            if record.payload.get("scope") == scope:
                if (
                    record.payload.get("campaign_id") != self.campaign_id
                    or record.payload.get("schedule_digest") != self.schedule_digest
                ):
                    raise ScienceCanaryError("V2_LEDGER_SCOPE_CONFLICT")
                yield record.payload

    def observations(self) -> tuple[dict[str, object], ...]:
        return tuple(self._records("science-canary-v2-observation"))

    def ticks(self) -> tuple[dict[str, object], ...]:
        records = sorted(
            self._records("science-canary-v2-scheduler-tick"),
            key=lambda item: int(item.get("sequence") or 0),
        )
        previous_observation_digest = None
        invocation_ids: set[str] = set()
        for sequence, record in enumerate(records, 1):
            tick = record.get("tick")
            if not isinstance(tick, dict) or record.get("sequence") != sequence:
                raise ScienceCanaryError("V2_TICK_CHAIN_INVALID")
            try:
                parsed = ScienceCanarySchedulerTickV2(**tick)
            except (TypeError, ValueError) as error:
                raise ScienceCanaryError("V2_TICK_CHAIN_INVALID") from error
            receipt_values = {
                key: value
                for key, value in tick.items()
                if key not in {"tick_receipt_digest", "idempotent_replay"}
            }
            observation_values = {
                "wall_time": parsed.wall_time,
                "monotonic_ns": parsed.monotonic_ns,
                "boot_id": parsed.boot_id,
                "scheduler_invocation_id": parsed.scheduler_invocation_id,
                "previous_observation_digest": parsed.previous_observation_digest,
            }
            outer_bindings = {
                "wall_time": parsed.wall_time,
                "monotonic_ns": parsed.monotonic_ns,
                "boot_id": parsed.boot_id,
                "scheduler_invocation_id": parsed.scheduler_invocation_id,
                "observation_digest": parsed.observation_digest,
            }
            if (
                parsed.campaign_id != self.campaign_id
                or parsed.schedule_digest != self.schedule_digest
                or parsed.previous_observation_digest != previous_observation_digest
                or parsed.observation_digest != _digest(observation_values)
                or parsed.tick_receipt_digest != _digest(receipt_values)
                or any(record.get(key) != value for key, value in outer_bindings.items())
                or parsed.scheduler_invocation_id in invocation_ids
            ):
                raise ScienceCanaryError("V2_TICK_CHAIN_INVALID")
            invocation_ids.add(parsed.scheduler_invocation_id)
            previous_observation_digest = parsed.observation_digest
        return tuple(records)

    def qualification_snapshot(
        self, schedule: ScienceCanaryScheduleV2
    ) -> tuple[ScienceCanaryProgressV2, str]:
        """Recompute qualification progress from the verified append-only ledger.

        Callers cannot supply a claimed progress object.  Every observation must
        bind to a real one-request child run, and the final scheduler tick must
        carry the independently recomputed progress digest.
        """

        if schedule.campaign_id != self.campaign_id or schedule.schedule_digest != self.schedule_digest:
            raise ScienceCanaryError("V2_LEDGER_SCHEDULE_MISMATCH")
        verification = self.ledger.verify()
        if not verification.ok:
            raise ScienceCanaryError("V2_LEDGER_INVALID")
        ticks = self.ticks()
        if not ticks:
            raise ScienceCanaryError("V2_QUALIFICATION_TICK_REQUIRED")
        observations = self.observations()
        expected_ids = {request.request_id for request in schedule.requests}
        observed_ids: set[str] = set()
        for observation in observations:
            request_id = str(observation.get("request_id") or "")
            if request_id in observed_ids or request_id not in expected_ids:
                raise ScienceCanaryError("V2_QUALIFICATION_OBSERVATION_CLOSURE")
            observed_ids.add(request_id)
            child_run_id = str(observation.get("child_run_id") or "")
            try:
                child = self.ledger.read(child_run_id)
            except LedgerError as error:
                raise ScienceCanaryError("V2_QUALIFICATION_CHILD_RUN_MISSING") from error
            if (
                child.kind is not RecordKind.RUN
                or child.payload.get("scope") != "science-canary"
                or child.payload.get("package_digest") != schedule.package_digest
                or child.payload.get("check_id") != schedule.check_id
                or child.payload.get("check_script_digest") != schedule.check_script_digest
                or child.payload.get("request_count") != 1
                or child.payload.get("verdict_counts") != {PrimaryVerdict.CONSISTENT.value: 1}
                or child.payload.get("execution_error_counts") != {}
                or observation.get("passed") is not True
            ):
                raise ScienceCanaryError("V2_QUALIFICATION_CHILD_RUN_INVALID")
        last_tick = ticks[-1]
        observed_at = _aware(str(last_tick["wall_time"]))
        progress = _progress(schedule, observations, observed_at=observed_at)
        tick_payload = last_tick.get("tick")
        if not isinstance(tick_payload, dict) or tick_payload.get("progress_digest") != progress.progress_digest:
            raise ScienceCanaryError("V2_QUALIFICATION_PROGRESS_MISMATCH")
        evidence = {
            "schema_name": "boi-science-canary-qualification-evidence/v2",
            "campaign_id": self.campaign_id,
            "schedule_digest": self.schedule_digest,
            "ledger_binding_digest": _digest(
                json.loads(self.binding_path.read_text(encoding="utf-8"))
            ),
            "tick_receipt_digests": [str(item["tick"]["tick_receipt_digest"]) for item in ticks],
            "observation_digests": [_digest(item) for item in observations],
            "progress_digest": progress.progress_digest,
            "record_count": verification.record_count,
            "event_count": verification.event_count,
        }
        return progress, _digest(evidence)


class SystemTrustedTimeSourceV2:
    @staticmethod
    def capture() -> TrustedTimeSampleV2:
        invocation_id = str(os.environ.get("INVOCATION_ID") or "").strip()
        if not invocation_id:
            raise ScienceCanaryError("TRUSTED_TIME_SCHEDULER_INVOCATION_REQUIRED")
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except OSError as error:
            raise ScienceCanaryError("TRUSTED_TIME_BOOT_ID_UNAVAILABLE") from error
        if not boot_id:
            raise ScienceCanaryError("TRUSTED_TIME_BOOT_ID_UNAVAILABLE")
        return TrustedTimeSampleV2(
            wall_time=datetime.now(timezone.utc).isoformat(),
            monotonic_ns=time.monotonic_ns(),
            boot_id=boot_id,
            scheduler_invocation_id=invocation_id,
        )


def _progress(
    schedule: ScienceCanaryScheduleV2,
    observations: Iterable[dict[str, object]],
    *,
    observed_at: datetime,
) -> ScienceCanaryProgressV2:
    observed = {str(item["request_id"]): item for item in observations}
    known = {item.request_id for item in schedule.requests}
    if not set(observed) <= known:
        raise ScienceCanaryError("V2_PROGRESS_REQUEST_UNKNOWN")
    failed = {key for key, item in observed.items() if item.get("passed") is not True}
    elapsed = max(0, int((observed_at - _aware(schedule.start_at)).total_seconds()))
    request_gate = len(observed) == REQUEST_COUNT
    duration_gate = elapsed >= int(MINIMUM_DURATION.total_seconds())
    quality_gate = request_gate and not failed
    values = {
        "campaign_id": schedule.campaign_id,
        "schedule_digest": schedule.schedule_digest,
        "observed_at": observed_at.isoformat(),
        "completed_request_ids": sorted(observed),
        "failed_request_ids": sorted(failed),
        "elapsed_seconds": elapsed,
        "request_gate_passed": request_gate,
        "duration_gate_passed": duration_gate,
        "quality_gate_passed": quality_gate,
        "eligible_for_qualification": request_gate and duration_gate and quality_gate,
        "v1_carried_request_count": 0,
        "qualification_receipt_id": None,
        "release_manifest_id": None,
        "active_release_transition": False,
    }
    return ScienceCanaryProgressV2(
        campaign_id=schedule.campaign_id,
        schedule_digest=schedule.schedule_digest,
        observed_at=observed_at.isoformat(),
        completed_requests=len(observed),
        consistent_requests=len(observed) - len(failed),
        failed_requests=len(failed),
        elapsed_seconds=elapsed,
        request_gate_passed=request_gate,
        duration_gate_passed=duration_gate,
        quality_gate_passed=quality_gate,
        eligible_for_qualification=request_gate and duration_gate and quality_gate,
        v1_carried_request_count=0,
        progress_digest=_digest(values),
    )


class ScienceCanaryCampaignV2Runner:
    @classmethod
    def run_due(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV2,
        check: PinnedCheckSpec,
        ledger: ScienceCanaryV2Ledger,
        max_requests: int | None = None,
    ) -> ScienceCanaryCampaignRunReceiptV2:
        sample = SystemTrustedTimeSourceV2.capture()
        return cls._run_due(
            package_path,
            schedule=schedule,
            check=check,
            ledger=ledger,
            sample=sample,
            trusted_reference_wall=_aware(sample.wall_time),
            max_requests=max_requests,
        )

    @classmethod
    def run_due_for_test(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV2,
        check: PinnedCheckSpec,
        ledger: ScienceCanaryV2Ledger,
        sample: TrustedTimeSampleV2,
        trusted_reference_wall: datetime,
        max_requests: int | None = None,
    ) -> ScienceCanaryCampaignRunReceiptV2:
        return cls._run_due(
            package_path,
            schedule=schedule,
            check=check,
            ledger=ledger,
            sample=sample,
            trusted_reference_wall=_aware(trusted_reference_wall),
            max_requests=max_requests,
        )

    @classmethod
    def _run_due(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV2,
        check: PinnedCheckSpec,
        ledger: ScienceCanaryV2Ledger,
        sample: TrustedTimeSampleV2,
        trusted_reference_wall: datetime,
        max_requests: int | None,
    ) -> ScienceCanaryCampaignRunReceiptV2:
        if ledger.campaign_id != schedule.campaign_id or ledger.schedule_digest != schedule.schedule_digest:
            raise ScienceCanaryError("V2_LEDGER_SCHEDULE_MISMATCH")
        if schedule.scheduler_revision_digest != science_canary_runtime_code_digest():
            raise ScienceCanaryError("V2_SCHEDULER_CODE_DRIFT")
        if check.check_id != schedule.check_id or check.script_digest != schedule.check_script_digest:
            raise ScienceCanaryError("V2_CHECK_DRIFT")
        manifest = ScienceCanaryRunner._load_manifest(Path(package_path))
        if manifest.get("package_digest") != schedule.package_digest:
            raise ScienceCanaryError("V2_PACKAGE_DRIFT")
        wall = _aware(sample.wall_time)
        if wall > trusted_reference_wall + timedelta(seconds=MAXIMUM_FUTURE_SECONDS):
            raise ScienceCanaryError("TRUSTED_TIME_FUTURE")
        if sample.monotonic_ns < 0 or not sample.boot_id.strip() or not sample.scheduler_invocation_id.strip():
            raise ScienceCanaryError("TRUSTED_TIME_IDENTITY_INVALID")
        ticks = ledger.ticks()
        by_invocation = {
            str(item["scheduler_invocation_id"]): item for item in ticks
        }
        prior_same = by_invocation.get(sample.scheduler_invocation_id)
        if prior_same is not None:
            if any(
                prior_same[key] != expected
                for key, expected in {
                    "wall_time": wall.isoformat(),
                    "monotonic_ns": sample.monotonic_ns,
                    "boot_id": sample.boot_id,
                }.items()
            ):
                raise ScienceCanaryError("TRUSTED_TIME_INVOCATION_CONFLICT")
            progress = _progress(schedule, ledger.observations(), observed_at=wall)
            tick_values = dict(prior_same["tick"])
            tick = ScienceCanarySchedulerTickV2(**tick_values)
            return ScienceCanaryCampaignRunReceiptV2(
                tick=replace(tick, idempotent_replay=True), progress=progress
            )
        previous = max(ticks, key=lambda item: int(item["sequence"])) if ticks else None
        previous_digest = None
        if previous is not None:
            previous_wall = _aware(str(previous["wall_time"]))
            previous_digest = str(previous["observation_digest"])
            if wall < previous_wall:
                raise ScienceCanaryError("TRUSTED_TIME_WALL_REGRESSION")
            if sample.boot_id == previous["boot_id"]:
                previous_monotonic = int(previous["monotonic_ns"])
                if sample.monotonic_ns <= previous_monotonic:
                    raise ScienceCanaryError("TRUSTED_TIME_MONOTONIC_REGRESSION")
                wall_delta = (wall - previous_wall).total_seconds()
                monotonic_delta = (sample.monotonic_ns - previous_monotonic) / 1_000_000_000
                if abs(wall_delta - monotonic_delta) > MAXIMUM_CLOCK_JUMP_SECONDS:
                    raise ScienceCanaryError("TRUSTED_TIME_EXCESSIVE_JUMP")
        completed_ids = {str(item["request_id"]) for item in ledger.observations()}
        due = [
            request for request in schedule.requests
            if _aware(request.scheduled_at) <= wall and request.request_id not in completed_ids
        ]
        if due and (wall - _aware(due[0].scheduled_at)).total_seconds() > schedule.maximum_lateness_seconds:
            raise ScienceCanaryError("V2_REQUEST_WINDOW_MISSED")
        if max_requests is not None:
            if max_requests < 0:
                raise ScienceCanaryError("V2_MAX_REQUESTS_INVALID")
            due = due[:max_requests]
        executed = []
        for request in due:
            child = ScienceCanaryRunner.run(
                package_path,
                relative_paths=[request.relative_path],
                check=check,
                ledger=ledger.ledger,
                occurred_at=wall.isoformat(),
            )
            passed = (
                child.verdict_counts == {PrimaryVerdict.CONSISTENT.value: 1}
                and not child.execution_error_counts
            )
            ledger.ledger.append(
                RecordKind.RUN,
                {
                    "scope": "science-canary-v2-observation",
                    "campaign_id": schedule.campaign_id,
                    "schedule_digest": schedule.schedule_digest,
                    "request_id": request.request_id,
                    "sequence": request.sequence,
                    "scheduled_at": request.scheduled_at,
                    "child_run_id": child.run_id,
                    "passed": passed,
                    "qualification_receipt_id": None,
                    "release_manifest_id": None,
                    "active_release_transition": False,
                },
                authority="science_evaluator",
                occurred_at=wall.isoformat(),
            )
            executed.append(request.request_id)
        progress = _progress(schedule, ledger.observations(), observed_at=wall)
        observation_values = {
            "wall_time": wall.isoformat(),
            "monotonic_ns": sample.monotonic_ns,
            "boot_id": sample.boot_id,
            "scheduler_invocation_id": sample.scheduler_invocation_id,
            "previous_observation_digest": previous_digest,
        }
        observation_digest = _digest(observation_values)
        tick_values = {
            "schema_name": "boi-science-canary-scheduler-tick/v2",
            "campaign_id": schedule.campaign_id,
            "schedule_digest": schedule.schedule_digest,
            "scheduler_id": schedule.scheduler_id,
            "scheduler_revision_digest": schedule.scheduler_revision_digest,
            "scheduler_invocation_id": sample.scheduler_invocation_id,
            "wall_time": wall.isoformat(),
            "monotonic_ns": sample.monotonic_ns,
            "boot_id": sample.boot_id,
            "previous_observation_digest": previous_digest,
            "observation_digest": observation_digest,
            "executed_request_count": len(executed),
            "executed_request_ids": tuple(executed),
            "progress_digest": progress.progress_digest,
        }
        tick = ScienceCanarySchedulerTickV2(
            **tick_values,
            tick_receipt_digest=_digest(tick_values),
        )
        ledger.ledger.append(
            RecordKind.RUN,
            {
                "scope": "science-canary-v2-scheduler-tick",
                "campaign_id": schedule.campaign_id,
                "schedule_digest": schedule.schedule_digest,
                "sequence": len(ticks) + 1,
                "wall_time": wall.isoformat(),
                "monotonic_ns": sample.monotonic_ns,
                "boot_id": sample.boot_id,
                "scheduler_invocation_id": sample.scheduler_invocation_id,
                "observation_digest": observation_digest,
                "tick": asdict(tick),
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
            authority="science_evaluator",
            occurred_at=wall.isoformat(),
        )
        return ScienceCanaryCampaignRunReceiptV2(tick=tick, progress=progress)


__all__ = [
    "ScienceCanaryCampaignRunReceiptV2",
    "ScienceCanaryCampaignV2Runner",
    "ScienceCanaryProgressV2",
    "ScienceCanaryScheduleV2",
    "ScienceCanarySchedulerTickV2",
    "ScienceCanaryV2Ledger",
    "SystemTrustedTimeSourceV2",
    "TrustedTimeSampleV2",
    "build_science_canary_schedule_v2",
    "parse_science_canary_schedule_v2",
    "science_canary_runtime_code_digest",
]
