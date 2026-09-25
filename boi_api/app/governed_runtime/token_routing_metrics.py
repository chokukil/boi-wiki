"""Thread-safe token-routing metrics with no Release or activation authority."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Literal

from .local_model_routing import CodexReviewRequest, codex_review_context


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PiStatus = Literal["READY", "BLOCKED", "REJECTED"]


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TokenRoutingMetricsSnapshot:
    deterministic_items: int
    pi_requests: int
    pi_ready: int
    pi_blocked: int
    invalid_outputs: int
    withheld_items: int
    codex_reviews: int
    cache_hits: int
    input_bytes_total: int
    average_input_bytes: float
    metrics_digest: str


class TokenRoutingMetrics:
    """Accumulate only bounded operational counts and digests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counts = {
            "deterministic_items": 0,
            "pi_requests": 0,
            "pi_ready": 0,
            "pi_blocked": 0,
            "invalid_outputs": 0,
            "withheld_items": 0,
            "codex_reviews": 0,
            "cache_hits": 0,
            "input_bytes_total": 0,
        }

    @staticmethod
    def _positive_or_zero(value: int, *, code: str) -> int:
        if isinstance(value, bool) or value < 0:
            raise ValueError(code)
        return value

    def record_deterministic(self, *, items: int = 1) -> None:
        items = self._positive_or_zero(items, code="DETERMINISTIC_ITEM_COUNT_INVALID")
        with self._lock:
            self._counts["deterministic_items"] += items

    def record_pi(self, *, input_bytes: int, status: PiStatus) -> None:
        input_bytes = self._positive_or_zero(
            input_bytes, code="PI_INPUT_BYTE_COUNT_INVALID"
        )
        if status not in {"READY", "BLOCKED", "REJECTED"}:
            raise ValueError("PI_METRIC_STATUS_INVALID")
        with self._lock:
            self._counts["pi_requests"] += 1
            self._counts["input_bytes_total"] += input_bytes
            if status == "READY":
                self._counts["pi_ready"] += 1
            elif status == "BLOCKED":
                self._counts["pi_blocked"] += 1
                self._counts["withheld_items"] += 1
            else:
                self._counts["invalid_outputs"] += 1
                self._counts["withheld_items"] += 1

    def record_withheld(self, *, items: int = 1) -> None:
        items = self._positive_or_zero(items, code="WITHHELD_ITEM_COUNT_INVALID")
        with self._lock:
            self._counts["withheld_items"] += items

    def record_cache_hit(self, *, items: int = 1) -> None:
        items = self._positive_or_zero(items, code="CACHE_HIT_COUNT_INVALID")
        with self._lock:
            self._counts["cache_hits"] += items

    def prepare_codex_review(self, request: CodexReviewRequest) -> dict[str, object]:
        packet = codex_review_context(request)
        with self._lock:
            self._counts["codex_reviews"] += 1
        return packet

    def snapshot(self) -> TokenRoutingMetricsSnapshot:
        with self._lock:
            values = dict(self._counts)
        requests = values["pi_requests"]
        average = values["input_bytes_total"] / requests if requests else 0.0
        digest_values = {**values, "average_input_bytes": average}
        return TokenRoutingMetricsSnapshot(
            **values,
            average_input_bytes=average,
            metrics_digest=_digest(digest_values),
        )

    def release_projection(self, *, release_candidate_digest: str) -> dict[str, object]:
        if not SHA256_RE.fullmatch(release_candidate_digest):
            raise ValueError("RELEASE_CANDIDATE_DIGEST_INVALID")
        snapshot = self.snapshot()
        values = {
            "schema": "boi-token-routing-release-projection/v1",
            "release_candidate_digest": release_candidate_digest,
            **asdict(snapshot),
            "release_authority": False,
            "active_release_transition": False,
        }
        return {**values, "projection_digest": _digest(values)}
