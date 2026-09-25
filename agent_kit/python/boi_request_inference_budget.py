"""Persistent request admission for synchronous external inference.

Identity is authenticated by the host, never derived from prompts or output_dir.
The host must reuse its configured execution_journal_dir across request restarts.
This is an admission cap: an already dispatched synchronous provider may overrun
the remaining elapsed allowance. Provider settings and cancellation stay external.
Repeated identical options are distinct attempts. A restarting caller must keep
the immutable attempt ID and use explicit replay/reconciliation for prior work;
prompt equivalence never authorizes automatic replay or resets the allowance.
"""
import copy
import fcntl
import hashlib
import json
import math
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone


def _utc_now():
    return datetime.now(timezone.utc).isoformat()
from pathlib import Path
from uuid import uuid4


def _digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def result_digest(draft, run):
    """Digest the unmodified provider tuple, for explicit reference replay."""
    return _digest({"draft": draft, "provider": run})


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("REQUEST_INFERENCE_INVALID_SECONDS")
    return float(value)


class RequestInferenceBudget:
    def __init__(self, *, infer, execution_journal_dir, request_id, actor_id,
                 max_calls, max_active_seconds, clock=time.monotonic):
        if any(not isinstance(v, str) or not v.strip() for v in (request_id, actor_id)):
            raise ValueError("REQUEST_INFERENCE_AUTHENTICATED_IDENTITY_REQUIRED")
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError("REQUEST_INFERENCE_INVALID_CALL_LIMIT")
        seconds = _seconds(max_active_seconds)
        if seconds == 0:
            raise ValueError("REQUEST_INFERENCE_INVALID_SECONDS")
        if execution_journal_dir is None:
            raise ValueError("REQUEST_INFERENCE_JOURNAL_REQUIRED")
        self.infer, self.clock = infer, clock
        self.policy = {"max_calls": max_calls, "max_active_seconds": seconds}
        self.identity_digest = _digest([actor_id, request_id])
        root = Path(execution_journal_dir).resolve() / "request-inference"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.journal_path = root / (self.identity_digest.split(":")[1] + ".json")
        self.lock_path = self.journal_path.with_suffix(".lock")
        with self._locked():
            if self.journal_path.exists():
                self._read()
            else:
                self._write({"version": "boi/request-inference-budget@1",
                    "identity_digest": self.identity_digest, "policy": self.policy, "attempts": []})

    @contextmanager
    def _locked(self):
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read(self):
        data = json.loads(self.journal_path.read_text())
        if data["identity_digest"] != self.identity_digest:
            raise ValueError("REQUEST_INFERENCE_IDENTITY_MISMATCH")
        if data["policy"] != self.policy:
            raise ValueError("REQUEST_INFERENCE_POLICY_CHANGED")
        return data

    def _write(self, data):
        temporary = self.journal_path.with_suffix("." + uuid4().hex + ".tmp")
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.journal_path)
            directory = os.open(self.journal_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _summary(data):
        result = copy.deepcopy(data)
        result["calls_used"] = len(data["attempts"])
        result["active_elapsed_seconds"] = sum(a["provider_elapsed_seconds"] for a in data["attempts"])
        result["unresolved_attempt_ids"] = [a["attempt_id"] for a in data["attempts"] if a["status"] == "unknown"]
        return result

    def snapshot(self):
        with self._locked():
            return self._summary(self._read())

    def amend_policy(self, *, expected_policy, max_calls, max_active_seconds,
                     admission_ref, reason):
        """Record a host-authorized increase in this same locked journal.

        The host must verify authorization before calling. A supplied reference
        is audit provenance, not an authentication or approval mechanism.
        Unknown attempts must be reconciled first; historical use never resets.
        """
        if any(not isinstance(v, str) or not v.strip() for v in (admission_ref, reason)):
            raise ValueError("REQUEST_INFERENCE_ADMISSION_REFERENCE_REQUIRED")
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError("REQUEST_INFERENCE_INVALID_CALL_LIMIT")
        target = {"max_calls": max_calls, "max_active_seconds": _seconds(max_active_seconds)}
        with self._locked():
            data = self._read()
            previous = next((a for a in data.get("admissions", [])
                             if a["admission_ref"] == admission_ref), None)
            if previous is not None:
                if (previous["previous_policy"] != expected_policy or previous["policy"] != target
                        or previous["reason"] != reason):
                    raise ValueError("REQUEST_INFERENCE_ADMISSION_CONFLICT")
                return self._summary(data)
            if data["policy"] != expected_policy:
                raise ValueError("REQUEST_INFERENCE_ADMISSION_STALE")
            if self._summary(data)["unresolved_attempt_ids"]:
                raise ValueError("REQUEST_INFERENCE_ADMISSION_UNRESOLVED")
            if (target["max_calls"] < self.policy["max_calls"]
                    or target["max_active_seconds"] < self.policy["max_active_seconds"]
                    or target == self.policy):
                raise ValueError("REQUEST_INFERENCE_ADMISSION_INCREASE_REQUIRED")
            data.setdefault("admissions", []).append({
                "admission_ref": admission_ref, "reason": reason, "recorded_at": _utc_now(),
                "previous_policy": copy.deepcopy(self.policy), "policy": copy.deepcopy(target),
                "calls_used_at_admission": len(data["attempts"]),
                "attempts_digest": _digest(data["attempts"])})
            data["policy"] = target
            self._write(data)
            self.policy = target
            return self._summary(data)

    def bind(self, infer):
        """Bind a stage/recovery provider without allocating another budget."""
        def call(**options):
            return self.dispatch(infer=infer, **options)
        call.snapshot = self.snapshot
        call._request_budget = self
        call._request_provider = infer
        return call

    def __call__(self, **options):
        return self.dispatch(infer=self.infer, **options)

    def dispatch(self, *, infer, **options):
        # Restarted hosts may reconstruct the same durable budget. Unwrap
        # equivalent bindings/instances, not just this Python object. Every
        # layer's root, authenticated identity and pinned policy must agree.
        visited = set()
        while True:
            owner = infer if isinstance(infer, RequestInferenceBudget) else getattr(infer, "_request_budget", None)
            if not isinstance(owner, RequestInferenceBudget) or not (
                    owner.journal_path == self.journal_path and
                    owner.identity_digest == self.identity_digest and owner.policy == self.policy):
                break
            if id(infer) in visited:
                raise ValueError("REQUEST_INFERENCE_BINDING_CYCLE")
            visited.add(id(infer))
            infer = owner.infer if isinstance(infer, RequestInferenceBudget) else infer._request_provider
        waiting = self.clock()
        with self._locked():
            data = self._read()
            summary = self._summary(data)
            if summary["unresolved_attempt_ids"]:
                return None, {"status": "budget_unresolved", "request_budget": summary}
            if (summary["calls_used"] >= self.policy["max_calls"] or
                    summary["active_elapsed_seconds"] >= self.policy["max_active_seconds"]):
                return None, {"status": "budget_exhausted", "request_budget": summary}
            attempt_id = uuid4().hex
            record = {"attempt_id": attempt_id, "status": "unknown",
                "reserved_at": _utc_now(), "completed_at": None, "provider_status": None,
                "operation_outcome": "unknown_until_reconciled",
                "request_digest": _digest(options), "result_digest": None,
                "result_ref": None, "finish_reasons": None,
                "provider_elapsed_seconds": 0.0, "provider_queue_seconds": None,
                "admission_wait_seconds": max(0.0, self.clock() - waiting)}
            data["attempts"].append(record)
            self._write(data)
        started = self.clock()
        try:
            draft, run = infer(**options)
            elapsed = max(0.0, self.clock() - started)
            # Only known terminal responses are resolved. Never infer a length
            # outcome from a lost/exceptional call.
            status = run.get("status")
            known = (not run.get("error") and
                (status in ("completed", "invalid_json") or
                 status == "incomplete" and run.get("finish_reasons") in (["stop"], ["length"])))
            self._finish(attempt_id, status=status if known else "unknown",
                provider_elapsed_seconds=elapsed,
                provider_status=status, finish_reasons=run.get("finish_reasons"),
                result_digest=result_digest(draft, run),
                result_ref=str(Path(options["output_dir"]).resolve()) if options.get("output_dir") is not None else None)
        except BaseException as exc:
            # Do not store exception messages, which may contain prompt/secrets.
            self._finish(attempt_id, status="unknown",
                provider_status="timeout" if isinstance(exc, TimeoutError) else "error",
                provider_elapsed_seconds=max(0.0, self.clock() - started))
            raise
        return draft, {**run, "request_attempt_id": attempt_id}

    def _finish(self, attempt_id, **fields):
        with self._locked():
            data = self._read()
            record = next(a for a in data["attempts"] if a["attempt_id"] == attempt_id)
            if record["status"] != "unknown":
                raise ValueError("REQUEST_INFERENCE_RECONCILIATION_CONFLICT")
            record.update(fields)
            record["completed_at"] = _utc_now()
            record["operation_outcome"] = "unknown_until_reconciled" if fields["status"] == "unknown" else "response_recorded"
            self._write(data)

    def reconcile(self, attempt_id, *, status, provider_elapsed_seconds,
                  result_ref=None, result_digest=None, finish_reasons=None,
                  provider_status=None):
        """Host imports/reconciles an immutable prior attempt, never dispatching.

        Measured elapsed cannot decrease. A resolved record is immutable. Explicit
        reconciliation may resolve unknown once; identical repetitions are no-ops.
        References point to host-retained results; no model content is copied.
        """
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise ValueError("REQUEST_INFERENCE_ATTEMPT_ID_REQUIRED")
        if status not in ("unknown", "completed", "incomplete", "invalid_json", "error", "timeout"):
            raise ValueError("REQUEST_INFERENCE_INVALID_STATUS")
        elapsed = _seconds(provider_elapsed_seconds)
        fields = {"status": status, "provider_elapsed_seconds": elapsed,
            "result_ref": str(result_ref) if result_ref is not None else None,
            "result_digest": result_digest, "finish_reasons": finish_reasons,
            "provider_status": provider_status if provider_status is not None else status}
        with self._locked():
            data = self._read()
            old = next((a for a in data["attempts"] if a["attempt_id"] == attempt_id), None)
            if old:
                if all(old.get(k) == v for k, v in fields.items()):
                    return copy.deepcopy(old)
                if old["status"] != "unknown" or status == "unknown" or elapsed < old["provider_elapsed_seconds"]:
                    raise ValueError("REQUEST_INFERENCE_RECONCILIATION_CONFLICT")
                if old.get("result_digest") and old["result_digest"] != result_digest:
                    raise ValueError("REQUEST_INFERENCE_RECONCILIATION_CONFLICT")
                old.update(fields)
            else:
                old = {"attempt_id": attempt_id, "request_digest": None,
                    "reserved_at": None, "completed_at": None, "imported_at": _utc_now(),
                    "provider_queue_seconds": None, "admission_wait_seconds": None, **fields}
                data["attempts"].append(old)
            old["reconciled_at"] = _utc_now()
            old["operation_outcome"] = "unknown_until_reconciled" if status == "unknown" else "response_recorded"
            self._write(data)
            return copy.deepcopy(old)

    def replay(self, attempt_id, load_result):
        """Explicit reference replay. Loader must return the original draft/run."""
        with self._locked():
            data = self._read()
            record = next((a for a in data["attempts"] if a["attempt_id"] == attempt_id), None)
            if record is None or record["status"] == "unknown":
                raise ValueError("REQUEST_INFERENCE_RESULT_UNRESOLVED")
            if not record.get("result_ref") or not record.get("result_digest"):
                raise ValueError("REQUEST_INFERENCE_RESULT_REFERENCE_REQUIRED")
        draft, run = load_result(record["result_ref"])
        if result_digest(draft, run) != record["result_digest"]:
            raise ValueError("REQUEST_INFERENCE_RESULT_DIGEST_MISMATCH")
        if (run.get("status") != record.get("provider_status") or
                run.get("finish_reasons") != record.get("finish_reasons")):
            raise ValueError("REQUEST_INFERENCE_RESULT_METADATA_MISMATCH")
        return draft, {**run, "request_attempt_id": attempt_id, "request_budget_replayed": True}
