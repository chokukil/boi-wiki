"""Shared non-secret validation for immutable Science records."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlsplit


class ScienceSensitivePersistenceError(ValueError):
    """A secret or service endpoint reached a non-secret persistence boundary."""


_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "base_url",
    "client_secret",
    "credential",
    "credentials",
    "endpoint",
    "password",
    "private_key",
    "secret",
    "token",
    "url",
}
_SENSITIVE_SCALAR_PATTERNS = (
    re.compile(r"(?i)\b(?:https?|wss?)://"),
    re.compile(r"(?i)\b(?:sk|pk|rk|ghp|xox[baprs])-[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(?:localhost|(?:[a-z0-9-]+\.)+[a-z]{2,})"
        r":[0-9]{2,5}(?:/[^\s]*)?"
    ),
    re.compile(r"(?i)\b[^\s:@/]+:[^\s@/]+@[a-z0-9.-]+\b"),
    re.compile(r"(?i)\b(?:bearer|basic)(?:\s|[-_:])+[^\s]+"),
    re.compile(
        r"(?i)\b(?:access[_-]?token|api[_-]?key|authorization|base[_-]?url|"
        r"client[_-]?secret|credential|endpoint|password|private[_-]?key|"
        r"secret|token)\s*[:=]"
    ),
)
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")
_SCHEMELESS_MODEL_ENDPOINT_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.-]*:[0-9]{2,5}(?:/|$)"
)


def _normalized_key(key: object) -> str:
    raw = str(key).strip().replace("-", "_")
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw)
    return snake.lower()


def _sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return normalized in _SENSITIVE_KEYS or any(
        normalized.endswith(f"_{suffix}") for suffix in _SENSITIVE_KEYS
    )


def reject_sensitive_persistence(value: Any, *, path: str = "value") -> None:
    """Reject credential/endpoint keys and scalar values at any nesting depth."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if _sensitive_key(key):
                raise ScienceSensitivePersistenceError(
                    f"sensitive field is forbidden at {path}.{key}"
                )
            reject_sensitive_persistence(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            reject_sensitive_persistence(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and any(
        pattern.search(value) for pattern in _SENSITIVE_SCALAR_PATTERNS
    ):
        raise ScienceSensitivePersistenceError(
            f"credential or endpoint scalar is forbidden at {path}"
        )


def validate_model_identifier(value: str) -> str:
    """Validate the persisted provider/model identifier, never its endpoint."""

    if (
        not isinstance(value, str)
        or not _MODEL_ID_RE.fullmatch(value)
        or _SCHEMELESS_MODEL_ENDPOINT_RE.match(value)
    ):
        raise ScienceSensitivePersistenceError("model_id is not a safe identifier")
    reject_sensitive_persistence(value, path="model_id")
    return value


def validate_credential_free_https_url(value: str) -> str:
    """Admit an HTTPS locator only when it carries no credential material."""

    if not isinstance(value, str):
        raise ScienceSensitivePersistenceError("reviewed URL must be a string")
    parsed = urlsplit(value)
    forbidden_keys = {
        "accesstoken",
        "apikey",
        "authorization",
        "basicauth",
        "clientsecret",
        "credential",
        "password",
        "privatekey",
        "secret",
        "token",
    }
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    fragment_items = parse_qsl(parsed.fragment, keep_blank_values=True)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(
            key.lower().replace("-", "").replace("_", "") in forbidden_keys
            for key, _item in [*query_items, *fragment_items]
        )
    ):
        raise ScienceSensitivePersistenceError(
            "reviewed URL contains credentials or is not HTTPS"
        )
    reject_sensitive_persistence(
        [item for _key, item in [*query_items, *fragment_items]],
        path="reviewed_url_parameters",
    )
    return value
