"""Windows-host trusted-time Science canary v3.

This contract is deliberately isolated from the historical v1 and v2
campaigns.  Windows QPC is the only authority for elapsed campaign time;
guest clocks are observations only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import base64
from pathlib import Path
import shutil
import subprocess
import time
from typing import Iterable, Literal, Mapping

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .science_canary import SHA256_RE, ScienceCanaryError
from .science_canary import PinnedCheckSpec, ScienceCanaryRunner
from .science_evaluator import PrimaryVerdict


REQUEST_COUNT = 100
MINIMUM_DURATION = timedelta(hours=48)
INTERVAL_SECONDS = 30 * 60
MAXIMUM_LATENESS_SECONDS = INTERVAL_SECONDS - 60
R4_CAMPAIGN_ID = "science-canary-20260903-trusted-v2-cron-r4"

_HOST_CLOCK_COMMAND = (
    "$o=[ordered]@{"
    "host_utc=[DateTimeOffset]::UtcNow.ToString(\"yyyy-MM-ddTHH:mm:ss.ffffffK\");"
    "host_qpc=[System.Diagnostics.Stopwatch]::GetTimestamp();"
    "host_qpc_frequency=[System.Diagnostics.Stopwatch]::Frequency;"
    "host_boot_id=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime."
    "ToUniversalTime().ToString(\"o\")};"
    "$o|ConvertTo-Json -Compress"
)
_TASK_EXPORT_COMMAND = (
    "$xml=Export-ScheduledTask -TaskName $env:BOI_WINDOWS_TASK_NAME -TaskPath '\\';"
    "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($xml))"
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _aware(value: str | datetime) -> datetime:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except ValueError as error:
        raise ScienceCanaryError("HOST_TIME_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScienceCanaryError("HOST_TIME_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _require_digest(value: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ScienceCanaryError("V3_DIGEST_INVALID")


def science_canary_runtime_code_digest_v3() -> str:
    root = Path(__file__).resolve().parent
    closure = {}
    for name in (
        "ledger.py",
        "science_canary.py",
        "science_canary_campaign_v3.py",
        "science_evaluator.py",
    ):
        closure[name] = _bytes_digest((root / name).read_bytes())
    return _digest(closure)


def science_canary_host_clock_provider_digest_v3() -> str:
    executable = shutil.which("powershell.exe")
    if not executable:
        raise ScienceCanaryError("V3_HOST_PROBE_UNAVAILABLE")
    bridge = Path(executable)
    try:
        bridge_digest = _bytes_digest(bridge.read_bytes())
        windows_binary = Path(
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        windows_binary_digest = _bytes_digest(windows_binary.read_bytes())
    except OSError as error:
        raise ScienceCanaryError("V3_HOST_PROBE_UNAVAILABLE") from error
    return _digest(
        {
            "provider": "windows-powershell-stopwatch-qpc/v1",
            "command": _HOST_CLOCK_COMMAND,
            "bridge_path": str(bridge.resolve()),
            "bridge_digest": bridge_digest,
            "windows_binary_path": str(windows_binary),
            "windows_binary_digest": windows_binary_digest,
        }
    )


@dataclass(frozen=True)
class WindowsHostClockReadingV3:
    host_utc: str
    host_qpc: int
    host_qpc_frequency: int
    host_boot_id: str
    host_clock_provider_digest: str


class WindowsHostClockProviderV3:
    """Capture Windows UTC, QPC, frequency and boot identity in one process."""

    @staticmethod
    def capture() -> WindowsHostClockReadingV3:
        executable = shutil.which("powershell.exe")
        if not executable:
            raise ScienceCanaryError("V3_HOST_PROBE_UNAVAILABLE")
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _HOST_CLOCK_COMMAND,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            value = json.loads(completed.stdout.strip())
            host_utc = _aware(str(value["host_utc"])).isoformat()
            host_qpc = int(value["host_qpc"])
            frequency = int(value["host_qpc_frequency"])
            boot_id = str(value["host_boot_id"]).strip()
        except (
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise ScienceCanaryError("V3_HOST_PROBE_MALFORMED") from error
        if host_qpc < 0 or frequency <= 0 or not boot_id:
            raise ScienceCanaryError("V3_HOST_PROBE_MALFORMED")
        return WindowsHostClockReadingV3(
            host_utc=host_utc,
            host_qpc=host_qpc,
            host_qpc_frequency=frequency,
            host_boot_id=boot_id,
            host_clock_provider_digest=science_canary_host_clock_provider_digest_v3(),
        )


class WindowsTaskDefinitionProviderV3:
    """Read the exact current Windows Task Scheduler XML definition."""

    @staticmethod
    def capture_digest(task_name: str) -> str:
        name = task_name.strip()
        executable = shutil.which("powershell.exe")
        if not executable or not name or any(character in name for character in "\r\n"):
            raise ScienceCanaryError("V3_SCHEDULER_DEFINITION_UNAVAILABLE")
        environment = os.environ.copy()
        environment["BOI_WINDOWS_TASK_NAME"] = name
        wsl_entries = [
            entry for entry in environment.get("WSLENV", "").split(":") if entry
        ]
        if not any(
            entry.split("/", 1)[0] == "BOI_WINDOWS_TASK_NAME"
            for entry in wsl_entries
        ):
            wsl_entries.append("BOI_WINDOWS_TASK_NAME")
        environment["WSLENV"] = ":".join(wsl_entries)
        try:
            completed = subprocess.run(
                [
                    executable,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _TASK_EXPORT_COMMAND,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
                env=environment,
            )
            xml = base64.b64decode(completed.stdout.strip(), validate=True)
        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
        ) as error:
            raise ScienceCanaryError("V3_SCHEDULER_DEFINITION_UNAVAILABLE") from error
        if not xml:
            raise ScienceCanaryError("V3_SCHEDULER_DEFINITION_UNAVAILABLE")
        return _bytes_digest(xml)


@dataclass(frozen=True)
class HostTimeAnchorV3:
    host_utc: str
    host_qpc: int
    host_qpc_frequency: int
    host_boot_id: str
    host_clock_provider_digest: str


@dataclass(frozen=True)
class ScienceCanaryScheduledRequestV3:
    request_id: str
    sequence: int
    relative_path: str
    scheduled_offset_seconds: int
    scheduled_at_display: str


@dataclass(frozen=True)
class ScienceCanaryScheduleV3:
    schema_name: Literal["boi-science-canary-schedule/v3"]
    campaign_id: str
    package_digest: str
    check_id: str
    check_script_digest: str
    profile_digest: str
    host_anchor: HostTimeAnchorV3
    interval_seconds: int
    maximum_lateness_seconds: int
    minimum_duration_seconds: int
    scheduler_id: str
    scheduler_definition_digest: str
    runtime_code_digest: str
    reviewed_by: str
    review_approval_digest: str
    prior_campaign_carried_request_count: Literal[0]
    requests: tuple[ScienceCanaryScheduledRequestV3, ...]
    schedule_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "host_anchor": asdict(self.host_anchor),
            "requests": [asdict(item) for item in self.requests],
        }


@dataclass(frozen=True)
class TrustedTimeSampleV3:
    host_utc: str
    host_qpc: int
    host_qpc_frequency: int
    host_boot_id: str
    host_clock_provider_digest: str
    guest_wall_time: str
    guest_monotonic_ns: int
    guest_boot_id: str
    scheduler_invocation_id: str
    scheduler_definition_digest: str


@dataclass(frozen=True)
class ClockAdjustmentReceiptV3:
    schema_name: Literal["boi-science-clock-adjustment-receipt/v3"]
    campaign_id: str
    schedule_digest: str
    scheduler_invocation_id: str
    host_elapsed_seconds: int
    host_wall_adjustment_seconds: float
    guest_wall_adjustment_seconds: float
    adjustment_detected: bool
    evidence_digest: str
    receipt_digest: str
    record_id: str


@dataclass(frozen=True)
class ScienceCanaryProgressV3:
    campaign_id: str
    schedule_digest: str
    observed_at: str
    completed_requests: int
    consistent_requests: int
    failed_requests: int
    host_elapsed_seconds: int
    request_gate_passed: bool
    duration_gate_passed: bool
    quality_gate_passed: bool
    eligible_for_qualification: bool
    prior_campaign_carried_request_count: Literal[0]
    progress_digest: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


@dataclass(frozen=True)
class ScienceCanarySchedulerTickV3:
    schema_name: Literal["boi-science-canary-scheduler-tick/v3"]
    campaign_id: str
    schedule_digest: str
    scheduler_id: str
    scheduler_definition_digest: str
    scheduler_invocation_id: str
    host_utc: str
    host_qpc: int
    host_qpc_frequency: int
    host_boot_id: str
    host_clock_provider_digest: str
    guest_wall_time: str
    guest_monotonic_ns: int
    guest_boot_id: str
    previous_observation_digest: str | None
    observation_digest: str
    clock_adjustment_record_id: str
    clock_adjustment_receipt_digest: str
    executed_request_count: int
    executed_request_ids: tuple[str, ...]
    progress_digest: str
    tick_receipt_digest: str
    idempotent_replay: bool = False


@dataclass(frozen=True)
class ScienceCanaryCampaignRunReceiptV3:
    tick: ScienceCanarySchedulerTickV3
    progress: ScienceCanaryProgressV3
    clock_adjustment: ClockAdjustmentReceiptV3


def build_science_canary_schedule_v3(
    *,
    campaign_id: str,
    package_digest: str,
    check_id: str,
    check_script_digest: str,
    profile_digest: str,
    relative_paths: tuple[str, ...],
    host_anchor: HostTimeAnchorV3,
    scheduler_id: str,
    scheduler_definition_digest: str,
    runtime_code_digest: str,
    reviewed_by: str,
    review_approval_digest: str,
    interval_seconds: int = INTERVAL_SECONDS,
    maximum_lateness_seconds: int = MAXIMUM_LATENESS_SECONDS,
) -> ScienceCanaryScheduleV3:
    identity = tuple(
        value.strip()
        for value in (campaign_id, check_id, scheduler_id, reviewed_by)
    )
    paths = tuple(path.strip() for path in relative_paths)
    if any(not value for value in identity) or not paths or any(not path for path in paths):
        raise ScienceCanaryError("V3_SCHEDULE_IDENTITY_REQUIRED")
    if identity[0] == R4_CAMPAIGN_ID or "v3" not in identity[0].lower():
        raise ScienceCanaryError("V3_PRIOR_CAMPAIGN_ID_FORBIDDEN")
    if len(paths) != len(set(paths)):
        raise ScienceCanaryError("V3_SCHEDULE_PATHS_NOT_UNIQUE")
    for value in (
        package_digest,
        check_script_digest,
        profile_digest,
        host_anchor.host_clock_provider_digest,
        scheduler_definition_digest,
        runtime_code_digest,
        review_approval_digest,
    ):
        _require_digest(value)
    _aware(host_anchor.host_utc)
    if (
        host_anchor.host_qpc < 0
        or host_anchor.host_qpc_frequency <= 0
        or not host_anchor.host_boot_id.strip()
    ):
        raise ScienceCanaryError("V3_HOST_ANCHOR_INVALID")
    if interval_seconds < 1 or not 0 <= maximum_lateness_seconds < interval_seconds:
        raise ScienceCanaryError("V3_SCHEDULE_INTERVAL_INVALID")
    if timedelta(seconds=interval_seconds * (REQUEST_COUNT - 1)) < MINIMUM_DURATION:
        raise ScienceCanaryError("V3_SCHEDULE_SHORTER_THAN_48_HOURS")

    start = _aware(host_anchor.host_utc)
    requests = []
    for index in range(REQUEST_COUNT):
        offset = index * interval_seconds
        request_values = {
            "campaign_id": identity[0],
            "sequence": index + 1,
            "relative_path": paths[index % len(paths)],
            "scheduled_offset_seconds": offset,
            "package_digest": package_digest,
            "check_id": identity[1],
            "check_script_digest": check_script_digest,
            "profile_digest": profile_digest,
            "scheduler_definition_digest": scheduler_definition_digest,
            "runtime_code_digest": runtime_code_digest,
            "host_anchor": asdict(host_anchor),
        }
        requests.append(
            ScienceCanaryScheduledRequestV3(
                request_id=f"science-canary-v3-request:{_digest(request_values)}",
                sequence=index + 1,
                relative_path=paths[index % len(paths)],
                scheduled_offset_seconds=offset,
                scheduled_at_display=(start + timedelta(seconds=offset)).isoformat(),
            )
        )
    values = {
        "schema_name": "boi-science-canary-schedule/v3",
        "campaign_id": identity[0],
        "package_digest": package_digest,
        "check_id": identity[1],
        "check_script_digest": check_script_digest,
        "profile_digest": profile_digest,
        "host_anchor": asdict(host_anchor),
        "interval_seconds": interval_seconds,
        "maximum_lateness_seconds": maximum_lateness_seconds,
        "minimum_duration_seconds": int(MINIMUM_DURATION.total_seconds()),
        "scheduler_id": identity[2],
        "scheduler_definition_digest": scheduler_definition_digest,
        "runtime_code_digest": runtime_code_digest,
        "reviewed_by": identity[3],
        "review_approval_digest": review_approval_digest,
        "prior_campaign_carried_request_count": 0,
        "requests": [asdict(item) for item in requests],
    }
    typed_values = {
        key: value for key, value in values.items() if key not in {"host_anchor", "requests"}
    }
    return ScienceCanaryScheduleV3(
        **typed_values,
        host_anchor=host_anchor,
        requests=tuple(requests),
        schedule_digest=_digest(values),
    )


def parse_science_canary_schedule_v3(value: Mapping[str, object]) -> ScienceCanaryScheduleV3:
    expected_keys = {
        "schema_name", "campaign_id", "package_digest", "check_id",
        "check_script_digest", "profile_digest", "host_anchor",
        "interval_seconds", "maximum_lateness_seconds", "minimum_duration_seconds",
        "scheduler_id", "scheduler_definition_digest", "runtime_code_digest",
        "reviewed_by", "review_approval_digest", "prior_campaign_carried_request_count",
        "requests", "schedule_digest",
    }
    if set(value) != expected_keys or value.get("schema_name") != "boi-science-canary-schedule/v3":
        raise ScienceCanaryError("V3_SCHEDULE_SCHEMA_INVALID")
    raw_anchor = value.get("host_anchor")
    raw_requests = value.get("requests")
    if not isinstance(raw_anchor, dict) or not isinstance(raw_requests, list) or len(raw_requests) != REQUEST_COUNT:
        raise ScienceCanaryError("V3_SCHEDULE_SCHEMA_INVALID")
    try:
        anchor = HostTimeAnchorV3(**raw_anchor)
        paths = tuple(dict.fromkeys(str(item["relative_path"]) for item in raw_requests))
        rebuilt = build_science_canary_schedule_v3(
            campaign_id=str(value["campaign_id"]),
            package_digest=str(value["package_digest"]),
            check_id=str(value["check_id"]),
            check_script_digest=str(value["check_script_digest"]),
            profile_digest=str(value["profile_digest"]),
            relative_paths=paths,
            host_anchor=anchor,
            scheduler_id=str(value["scheduler_id"]),
            scheduler_definition_digest=str(value["scheduler_definition_digest"]),
            runtime_code_digest=str(value["runtime_code_digest"]),
            reviewed_by=str(value["reviewed_by"]),
            review_approval_digest=str(value["review_approval_digest"]),
            interval_seconds=int(value["interval_seconds"]),
            maximum_lateness_seconds=int(value["maximum_lateness_seconds"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ScienceCanaryError("V3_SCHEDULE_SCHEMA_INVALID") from error
    if rebuilt.to_dict() != dict(value):
        raise ScienceCanaryError("V3_SCHEDULE_DIGEST_OR_REQUEST_MISMATCH")
    return rebuilt


class SystemTrustedTimeSourceV3:
    """Build one v3 sample without accepting a caller-supplied clock."""

    @staticmethod
    def capture(schedule: ScienceCanaryScheduleV3) -> TrustedTimeSampleV3:
        prefix = "windows-task:"
        if not schedule.scheduler_id.startswith(prefix):
            raise ScienceCanaryError("V3_SCHEDULER_ID_INVALID")
        task_name = schedule.scheduler_id[len(prefix):].strip()
        scheduler_digest = WindowsTaskDefinitionProviderV3.capture_digest(task_name)
        reading = WindowsHostClockProviderV3.capture()
        if reading.host_qpc < schedule.host_anchor.host_qpc:
            raise ScienceCanaryError("V3_QPC_REGRESSION")
        elapsed_seconds = (
            reading.host_qpc - schedule.host_anchor.host_qpc
        ) // schedule.host_anchor.host_qpc_frequency
        due_slot = elapsed_seconds // schedule.interval_seconds
        invocation_id = "windows-task-v3:" + _digest(
            {
                "campaign_id": schedule.campaign_id,
                "schedule_digest": schedule.schedule_digest,
                "host_boot_id": reading.host_boot_id,
                "due_slot": due_slot,
                "scheduler_definition_digest": scheduler_digest,
            }
        )
        try:
            guest_boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        except OSError as error:
            raise ScienceCanaryError("V3_GUEST_OBSERVATION_UNAVAILABLE") from error
        if not guest_boot_id:
            raise ScienceCanaryError("V3_GUEST_OBSERVATION_UNAVAILABLE")
        return TrustedTimeSampleV3(
            **asdict(reading),
            guest_wall_time=datetime.now(timezone.utc).isoformat(),
            guest_monotonic_ns=time.monotonic_ns(),
            guest_boot_id=guest_boot_id,
            scheduler_invocation_id=invocation_id,
            scheduler_definition_digest=scheduler_digest,
        )


class ScienceCanaryV3Ledger:
    """Fresh host-QPC ledger which refuses v1/v2 history and count carry-over."""

    def __init__(self, root: Path, *, campaign_id: str, schedule_digest: str) -> None:
        _require_digest(schedule_digest)
        self.root = root
        self.binding_path = root / "science-canary-v3-binding.json"
        existing_events = root / "events.jsonl"
        if (
            not self.binding_path.exists()
            and existing_events.exists()
            and existing_events.stat().st_size
        ):
            raise ScienceCanaryError("V3_LEDGER_NOT_FRESH")
        values = {
            "schema_name": "boi-science-canary-ledger-binding/v3",
            "campaign_id": campaign_id,
            "schedule_digest": schedule_digest,
            "prior_campaign_carried_request_count": 0,
        }
        payload = {**values, "binding_digest": _digest(values)}
        encoded = _canonical_json(payload) + b"\n"
        root.mkdir(parents=True, exist_ok=True)
        if self.binding_path.exists():
            if self.binding_path.read_bytes() != encoded:
                raise ScienceCanaryError("V3_LEDGER_BINDING_CONFLICT")
        else:
            self.binding_path.write_bytes(encoded)
        self.campaign_id = campaign_id
        self.schedule_digest = schedule_digest
        self.ledger = GovernedRuntimeLedger(root)

    def _records(self, scope: str, kind: RecordKind = RecordKind.RUN) -> Iterable[dict[str, object]]:
        record_root = self.ledger.records_root / kind.value
        for path in sorted(record_root.glob("*.json")) if record_root.exists() else ():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                record = self.ledger.read(str(stored["record_id"]))
            except (OSError, KeyError, ValueError, LedgerError) as error:
                raise ScienceCanaryError("V3_LEDGER_INVALID") from error
            if record.payload.get("scope") == scope:
                if (
                    record.payload.get("campaign_id") != self.campaign_id
                    or record.payload.get("schedule_digest") != self.schedule_digest
                ):
                    raise ScienceCanaryError("V3_LEDGER_SCOPE_CONFLICT")
                yield {**record.payload, "_record_id": record.record_id}

    def observations(self) -> tuple[dict[str, object], ...]:
        return tuple(self._records("science-canary-v3-observation"))

    def adjustments(self) -> tuple[dict[str, object], ...]:
        return tuple(
            self._records("science-canary-v3-clock-adjustment", RecordKind.CHECK)
        )

    def ticks(self) -> tuple[dict[str, object], ...]:
        records = sorted(
            self._records("science-canary-v3-scheduler-tick"),
            key=lambda item: int(item.get("sequence") or 0),
        )
        previous_digest = None
        invocation_ids: set[str] = set()
        for sequence, record in enumerate(records, 1):
            tick_value = record.get("tick")
            if not isinstance(tick_value, dict) or record.get("sequence") != sequence:
                raise ScienceCanaryError("V3_TICK_CHAIN_INVALID")
            try:
                tick = ScienceCanarySchedulerTickV3(**tick_value)
                adjustment_record = self.ledger.read(tick.clock_adjustment_record_id)
            except (TypeError, ValueError, LedgerError) as error:
                raise ScienceCanaryError("V3_TICK_CHAIN_INVALID") from error
            receipt_values = {
                key: value
                for key, value in tick_value.items()
                if key not in {"tick_receipt_digest", "idempotent_replay"}
            }
            observation_values = {
                "host_utc": tick.host_utc,
                "host_qpc": tick.host_qpc,
                "host_qpc_frequency": tick.host_qpc_frequency,
                "host_boot_id": tick.host_boot_id,
                "host_clock_provider_digest": tick.host_clock_provider_digest,
                "guest_wall_time": tick.guest_wall_time,
                "guest_monotonic_ns": tick.guest_monotonic_ns,
                "guest_boot_id": tick.guest_boot_id,
                "scheduler_invocation_id": tick.scheduler_invocation_id,
                "scheduler_definition_digest": tick.scheduler_definition_digest,
                "previous_observation_digest": tick.previous_observation_digest,
            }
            if (
                tick.campaign_id != self.campaign_id
                or tick.schedule_digest != self.schedule_digest
                or tick.previous_observation_digest != previous_digest
                or tick.observation_digest != _digest(observation_values)
                or tick.tick_receipt_digest != _digest(receipt_values)
                or tick.scheduler_invocation_id in invocation_ids
                or adjustment_record.kind is not RecordKind.CHECK
                or adjustment_record.payload.get("receipt_digest")
                != tick.clock_adjustment_receipt_digest
            ):
                raise ScienceCanaryError("V3_TICK_CHAIN_INVALID")
            invocation_ids.add(tick.scheduler_invocation_id)
            previous_digest = tick.observation_digest
        return tuple(records)

    def qualification_snapshot(
        self, schedule: ScienceCanaryScheduleV3
    ) -> tuple[ScienceCanaryProgressV3, str]:
        if (
            schedule.campaign_id != self.campaign_id
            or schedule.schedule_digest != self.schedule_digest
        ):
            raise ScienceCanaryError("V3_LEDGER_SCHEDULE_MISMATCH")
        verification = self.ledger.verify()
        if not verification.ok:
            raise ScienceCanaryError("V3_LEDGER_INVALID")
        ticks = self.ticks()
        if not ticks:
            raise ScienceCanaryError("V3_QUALIFICATION_TICK_REQUIRED")
        observations = self.observations()
        expected_ids = {request.request_id for request in schedule.requests}
        observed_ids: set[str] = set()
        for observation in observations:
            request_id = str(observation.get("request_id") or "")
            if request_id in observed_ids or request_id not in expected_ids:
                raise ScienceCanaryError("V3_QUALIFICATION_OBSERVATION_CLOSURE")
            observed_ids.add(request_id)
            try:
                child = self.ledger.read(str(observation.get("child_run_id") or ""))
            except LedgerError as error:
                raise ScienceCanaryError("V3_QUALIFICATION_CHILD_RUN_MISSING") from error
            if (
                child.kind is not RecordKind.RUN
                or child.payload.get("scope") != "science-canary"
                or child.payload.get("package_digest") != schedule.package_digest
                or child.payload.get("check_id") != schedule.check_id
                or child.payload.get("check_script_digest") != schedule.check_script_digest
                or child.payload.get("request_count") != 1
                or child.payload.get("verdict_counts")
                != {PrimaryVerdict.CONSISTENT.value: 1}
                or child.payload.get("execution_error_counts") != {}
                or observation.get("passed") is not True
            ):
                raise ScienceCanaryError("V3_QUALIFICATION_CHILD_RUN_INVALID")
        last_tick_value = ticks[-1].get("tick")
        if not isinstance(last_tick_value, dict):
            raise ScienceCanaryError("V3_TICK_CHAIN_INVALID")
        sample = _sample_from_tick(ScienceCanarySchedulerTickV3(**last_tick_value))
        progress = _progress_v3(schedule, observations, sample=sample)
        if last_tick_value.get("progress_digest") != progress.progress_digest:
            raise ScienceCanaryError("V3_QUALIFICATION_PROGRESS_MISMATCH")
        evidence = {
            "schema_name": "boi-science-canary-qualification-evidence/v3",
            "campaign_id": self.campaign_id,
            "schedule_digest": self.schedule_digest,
            "ledger_binding_digest": _digest(
                json.loads(self.binding_path.read_text(encoding="utf-8"))
            ),
            "tick_receipt_digests": [
                str(item["tick"]["tick_receipt_digest"]) for item in ticks
            ],
            "clock_adjustment_receipt_digests": [
                str(item["tick"]["clock_adjustment_receipt_digest"]) for item in ticks
            ],
            "observation_digests": [_digest(item) for item in observations],
            "progress_digest": progress.progress_digest,
            "record_count": verification.record_count,
            "event_count": verification.event_count,
        }
        return progress, _digest(evidence)


def _host_elapsed_seconds(schedule: ScienceCanaryScheduleV3, sample: TrustedTimeSampleV3) -> int:
    ticks = sample.host_qpc - schedule.host_anchor.host_qpc
    if ticks < 0:
        raise ScienceCanaryError("V3_QPC_REGRESSION")
    return ticks // schedule.host_anchor.host_qpc_frequency


def _progress_v3(
    schedule: ScienceCanaryScheduleV3,
    observations: Iterable[dict[str, object]],
    *,
    sample: TrustedTimeSampleV3,
) -> ScienceCanaryProgressV3:
    observed = {str(item["request_id"]): item for item in observations}
    known = {item.request_id for item in schedule.requests}
    if not set(observed) <= known:
        raise ScienceCanaryError("V3_PROGRESS_REQUEST_UNKNOWN")
    failed = {key for key, item in observed.items() if item.get("passed") is not True}
    elapsed = _host_elapsed_seconds(schedule, sample)
    request_gate = len(observed) == REQUEST_COUNT
    duration_gate = elapsed >= int(MINIMUM_DURATION.total_seconds())
    quality_gate = request_gate and not failed
    values = {
        "campaign_id": schedule.campaign_id,
        "schedule_digest": schedule.schedule_digest,
        "observed_at": _aware(sample.host_utc).isoformat(),
        "completed_request_ids": sorted(observed),
        "failed_request_ids": sorted(failed),
        "host_elapsed_seconds": elapsed,
        "request_gate_passed": request_gate,
        "duration_gate_passed": duration_gate,
        "quality_gate_passed": quality_gate,
        "eligible_for_qualification": request_gate and duration_gate and quality_gate,
        "prior_campaign_carried_request_count": 0,
        "qualification_receipt_id": None,
        "release_manifest_id": None,
        "active_release_transition": False,
    }
    return ScienceCanaryProgressV3(
        campaign_id=schedule.campaign_id,
        schedule_digest=schedule.schedule_digest,
        observed_at=_aware(sample.host_utc).isoformat(),
        completed_requests=len(observed),
        consistent_requests=len(observed) - len(failed),
        failed_requests=len(failed),
        host_elapsed_seconds=elapsed,
        request_gate_passed=request_gate,
        duration_gate_passed=duration_gate,
        quality_gate_passed=quality_gate,
        eligible_for_qualification=request_gate and duration_gate and quality_gate,
        prior_campaign_carried_request_count=0,
        progress_digest=_digest(values),
    )


def _sample_from_tick(tick: ScienceCanarySchedulerTickV3) -> TrustedTimeSampleV3:
    return TrustedTimeSampleV3(
        host_utc=tick.host_utc,
        host_qpc=tick.host_qpc,
        host_qpc_frequency=tick.host_qpc_frequency,
        host_boot_id=tick.host_boot_id,
        host_clock_provider_digest=tick.host_clock_provider_digest,
        guest_wall_time=tick.guest_wall_time,
        guest_monotonic_ns=tick.guest_monotonic_ns,
        guest_boot_id=tick.guest_boot_id,
        scheduler_invocation_id=tick.scheduler_invocation_id,
        scheduler_definition_digest=tick.scheduler_definition_digest,
    )


class ScienceCanaryCampaignV3Runner:
    @classmethod
    def run_due(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV3,
        check: PinnedCheckSpec,
        profile_digest: str,
        ledger: ScienceCanaryV3Ledger,
        max_requests: int | None = None,
    ) -> ScienceCanaryCampaignRunReceiptV3:
        return cls._run_due(
            package_path,
            schedule=schedule,
            check=check,
            profile_digest=profile_digest,
            ledger=ledger,
            sample=SystemTrustedTimeSourceV3.capture(schedule),
            max_requests=max_requests,
        )

    @classmethod
    def run_due_for_test(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV3,
        check: PinnedCheckSpec,
        profile_digest: str,
        ledger: ScienceCanaryV3Ledger,
        sample: TrustedTimeSampleV3,
        max_requests: int | None = None,
    ) -> ScienceCanaryCampaignRunReceiptV3:
        return cls._run_due(
            package_path,
            schedule=schedule,
            check=check,
            profile_digest=profile_digest,
            ledger=ledger,
            sample=sample,
            max_requests=max_requests,
        )

    @classmethod
    def _run_due(
        cls,
        package_path: Path | str,
        *,
        schedule: ScienceCanaryScheduleV3,
        check: PinnedCheckSpec,
        profile_digest: str,
        ledger: ScienceCanaryV3Ledger,
        sample: TrustedTimeSampleV3,
        max_requests: int | None,
    ) -> ScienceCanaryCampaignRunReceiptV3:
        # A typed object is not authority by itself: re-run the canonical
        # schedule parser so dataclass replacement cannot bypass its digest.
        parse_science_canary_schedule_v3(schedule.to_dict())
        if (
            ledger.campaign_id != schedule.campaign_id
            or ledger.schedule_digest != schedule.schedule_digest
        ):
            raise ScienceCanaryError("V3_LEDGER_SCHEDULE_MISMATCH")
        if schedule.runtime_code_digest != science_canary_runtime_code_digest_v3():
            raise ScienceCanaryError("V3_RUNTIME_CODE_DRIFT")
        if check.check_id != schedule.check_id or check.script_digest != schedule.check_script_digest:
            raise ScienceCanaryError("V3_CHECK_DRIFT")
        _require_digest(profile_digest)
        if profile_digest != schedule.profile_digest:
            raise ScienceCanaryError("V3_PROFILE_DRIFT")
        manifest = ScienceCanaryRunner._load_manifest(Path(package_path))
        if manifest.get("package_digest") != schedule.package_digest:
            raise ScienceCanaryError("V3_PACKAGE_DRIFT")
        if sample.host_clock_provider_digest != schedule.host_anchor.host_clock_provider_digest:
            raise ScienceCanaryError("V3_HOST_PROVIDER_DRIFT")
        if sample.scheduler_definition_digest != schedule.scheduler_definition_digest:
            raise ScienceCanaryError("V3_SCHEDULER_DEFINITION_DRIFT")
        if sample.host_qpc_frequency != schedule.host_anchor.host_qpc_frequency:
            raise ScienceCanaryError("V3_QPC_FREQUENCY_CHANGED")
        if sample.host_boot_id != schedule.host_anchor.host_boot_id:
            raise ScienceCanaryError("V3_HOST_BOOT_CHANGED")
        if (
            sample.host_qpc < 0
            or sample.guest_monotonic_ns < 0
            or not sample.scheduler_invocation_id.strip()
            or not sample.guest_boot_id.strip()
        ):
            raise ScienceCanaryError("V3_TIME_IDENTITY_INVALID")
        _aware(sample.host_utc)
        _aware(sample.guest_wall_time)
        elapsed = _host_elapsed_seconds(schedule, sample)
        ticks = ledger.ticks()
        by_invocation = {str(item["scheduler_invocation_id"]): item for item in ticks}
        prior_same = by_invocation.get(sample.scheduler_invocation_id)
        if prior_same is not None:
            prior_tick = ScienceCanarySchedulerTickV3(**prior_same["tick"])
            prior_sample = _sample_from_tick(prior_tick)
            if prior_sample != sample:
                raise ScienceCanaryError("V3_INVOCATION_CONFLICT")
            adjustment_record = ledger.ledger.read(prior_tick.clock_adjustment_record_id)
            adjustment = ClockAdjustmentReceiptV3(
                **{
                    key: value
                    for key, value in adjustment_record.payload.items()
                    if key != "scope"
                },
                record_id=adjustment_record.record_id,
            )
            return ScienceCanaryCampaignRunReceiptV3(
                tick=replace(prior_tick, idempotent_replay=True),
                progress=_progress_v3(schedule, ledger.observations(), sample=sample),
                clock_adjustment=adjustment,
            )

        previous = ticks[-1] if ticks else None
        previous_digest = None
        if previous is not None:
            previous_tick = ScienceCanarySchedulerTickV3(**previous["tick"])
            previous_digest = previous_tick.observation_digest
            if sample.host_qpc <= previous_tick.host_qpc:
                raise ScienceCanaryError("V3_QPC_REGRESSION")
        completed_ids = {str(item["request_id"]) for item in ledger.observations()}
        due = [
            request
            for request in schedule.requests
            if request.scheduled_offset_seconds <= elapsed
            and request.request_id not in completed_ids
        ]
        if due and elapsed - due[0].scheduled_offset_seconds > schedule.maximum_lateness_seconds:
            raise ScienceCanaryError("V3_REQUEST_WINDOW_MISSED")
        if max_requests is not None:
            if max_requests < 0:
                raise ScienceCanaryError("V3_MAX_REQUESTS_INVALID")
            due = due[:max_requests]

        host_wall_elapsed = (
            _aware(sample.host_utc) - _aware(schedule.host_anchor.host_utc)
        ).total_seconds()
        guest_wall_elapsed = (
            _aware(sample.guest_wall_time) - _aware(schedule.host_anchor.host_utc)
        ).total_seconds()
        host_adjustment = host_wall_elapsed - elapsed
        guest_adjustment = guest_wall_elapsed - elapsed
        adjustment_evidence = {
            "host_anchor": asdict(schedule.host_anchor),
            "host_utc": _aware(sample.host_utc).isoformat(),
            "guest_wall_time": _aware(sample.guest_wall_time).isoformat(),
            "host_elapsed_seconds": elapsed,
            "host_wall_adjustment_seconds": host_adjustment,
            "guest_wall_adjustment_seconds": guest_adjustment,
        }
        adjustment_values = {
            "schema_name": "boi-science-clock-adjustment-receipt/v3",
            "campaign_id": schedule.campaign_id,
            "schedule_digest": schedule.schedule_digest,
            "scheduler_invocation_id": sample.scheduler_invocation_id,
            "host_elapsed_seconds": elapsed,
            "host_wall_adjustment_seconds": host_adjustment,
            "guest_wall_adjustment_seconds": guest_adjustment,
            "adjustment_detected": abs(host_adjustment) > 1 or abs(guest_adjustment) > 1,
            "evidence_digest": _digest(adjustment_evidence),
        }
        adjustment_receipt_digest = _digest(adjustment_values)

        executed: list[str] = []
        host_utc = _aware(sample.host_utc).isoformat()
        for request in due:
            child = ScienceCanaryRunner.run(
                package_path,
                relative_paths=[request.relative_path],
                check=check,
                ledger=ledger.ledger,
                occurred_at=host_utc,
            )
            passed = (
                child.verdict_counts == {PrimaryVerdict.CONSISTENT.value: 1}
                and not child.execution_error_counts
            )
            ledger.ledger.append(
                RecordKind.RUN,
                {
                    "scope": "science-canary-v3-observation",
                    "campaign_id": schedule.campaign_id,
                    "schedule_digest": schedule.schedule_digest,
                    "request_id": request.request_id,
                    "sequence": request.sequence,
                    "scheduled_offset_seconds": request.scheduled_offset_seconds,
                    "child_run_id": child.run_id,
                    "passed": passed,
                    "qualification_receipt_id": None,
                    "release_manifest_id": None,
                    "active_release_transition": False,
                },
                authority="science_evaluator",
                occurred_at=host_utc,
            )
            executed.append(request.request_id)

        progress = _progress_v3(schedule, ledger.observations(), sample=sample)
        adjustment_record = ledger.ledger.append(
            RecordKind.CHECK,
            {
                "scope": "science-canary-v3-clock-adjustment",
                **adjustment_values,
                "receipt_digest": adjustment_receipt_digest,
            },
            authority="science_evaluator",
            occurred_at=host_utc,
        )
        adjustment = ClockAdjustmentReceiptV3(
            **adjustment_values,
            receipt_digest=adjustment_receipt_digest,
            record_id=adjustment_record.record_id,
        )
        observation_values = {
            **asdict(sample),
            "host_utc": host_utc,
            "guest_wall_time": _aware(sample.guest_wall_time).isoformat(),
            "previous_observation_digest": previous_digest,
        }
        observation_digest = _digest(observation_values)
        tick_values = {
            "schema_name": "boi-science-canary-scheduler-tick/v3",
            "campaign_id": schedule.campaign_id,
            "schedule_digest": schedule.schedule_digest,
            "scheduler_id": schedule.scheduler_id,
            "scheduler_definition_digest": sample.scheduler_definition_digest,
            "scheduler_invocation_id": sample.scheduler_invocation_id,
            "host_utc": host_utc,
            "host_qpc": sample.host_qpc,
            "host_qpc_frequency": sample.host_qpc_frequency,
            "host_boot_id": sample.host_boot_id,
            "host_clock_provider_digest": sample.host_clock_provider_digest,
            "guest_wall_time": _aware(sample.guest_wall_time).isoformat(),
            "guest_monotonic_ns": sample.guest_monotonic_ns,
            "guest_boot_id": sample.guest_boot_id,
            "previous_observation_digest": previous_digest,
            "observation_digest": observation_digest,
            "clock_adjustment_record_id": adjustment_record.record_id,
            "clock_adjustment_receipt_digest": adjustment_receipt_digest,
            "executed_request_count": len(executed),
            "executed_request_ids": tuple(executed),
            "progress_digest": progress.progress_digest,
        }
        tick = ScienceCanarySchedulerTickV3(
            **tick_values,
            tick_receipt_digest=_digest(tick_values),
        )
        ledger.ledger.append(
            RecordKind.RUN,
            {
                "scope": "science-canary-v3-scheduler-tick",
                "campaign_id": schedule.campaign_id,
                "schedule_digest": schedule.schedule_digest,
                "sequence": len(ticks) + 1,
                "scheduler_invocation_id": sample.scheduler_invocation_id,
                "observation_digest": observation_digest,
                "tick": asdict(tick),
                "qualification_receipt_id": None,
                "release_manifest_id": None,
                "active_release_transition": False,
            },
            authority="science_evaluator",
            occurred_at=host_utc,
        )
        return ScienceCanaryCampaignRunReceiptV3(
            tick=tick,
            progress=progress,
            clock_adjustment=adjustment,
        )


__all__ = [
    "ClockAdjustmentReceiptV3",
    "HostTimeAnchorV3",
    "ScienceCanaryCampaignRunReceiptV3",
    "ScienceCanaryCampaignV3Runner",
    "ScienceCanaryProgressV3",
    "ScienceCanaryScheduleV3",
    "ScienceCanarySchedulerTickV3",
    "ScienceCanaryV3Ledger",
    "SystemTrustedTimeSourceV3",
    "TrustedTimeSampleV3",
    "WindowsHostClockProviderV3",
    "WindowsTaskDefinitionProviderV3",
    "build_science_canary_schedule_v3",
    "parse_science_canary_schedule_v3",
    "science_canary_host_clock_provider_digest_v3",
    "science_canary_runtime_code_digest_v3",
]
