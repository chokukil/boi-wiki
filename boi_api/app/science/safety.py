"""Shared non-secret validation for immutable Science records."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit


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


_URL_CREDENTIAL_KEYS = {
    "accesskey",
    "accesstoken",
    "apikey",
    "auth",
    "authorization",
    "basicauth",
    "bearer",
    "clientsecret",
    "credential",
    "password",
    "passwd",
    "privatekey",
    "secret",
    "sig",
    "signature",
    "token",
}
_STABLE_SOURCE_QUERY_ALLOWLIST = {"download": {"1", "true"}}


def _fully_decode_url_component(value: str) -> str:
    decoded = value
    try:
        for _attempt in range(8):
            candidate = unquote(decoded, errors="strict")
            if candidate == decoded:
                return unicodedata.normalize("NFKC", candidate)
            decoded = candidate
    except UnicodeDecodeError:
        raise ScienceSensitivePersistenceError(
            "stable source URL contains invalid encoding"
        ) from None
    if unquote(decoded, errors="strict") != decoded:
        raise ScienceSensitivePersistenceError(
            "stable source URL contains excessive encoding"
        )
    return unicodedata.normalize("NFKC", decoded)


def _credential_key(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", value.casefold())
    return normalized in _URL_CREDENTIAL_KEYS or normalized.startswith("xamz")


def _validate_stable_source_path(path: str) -> None:
    decoded_path = _fully_decode_url_component(path)
    if any(
        unicodedata.category(character).startswith("C") for character in decoded_path
    ):
        raise ScienceSensitivePersistenceError(
            "stable source URL path contains control characters"
        )
    segments = [
        segment for segment in decoded_path.replace("\\", "/").split("/") if segment
    ]
    for index, segment in enumerate(segments):
        key = re.split(r"[=:@;,]", segment, maxsplit=1)[0]
        if _credential_key(key) and (key != segment or index + 1 < len(segments)):
            raise ScienceSensitivePersistenceError(
                "stable source URL path contains credential material"
            )
        normalized = re.sub(r"[^a-z0-9]", "", segment.casefold())
        if normalized.startswith(("bearer", "presigned")) and normalized not in {
            "bearer",
            "presigned",
        }:
            raise ScienceSensitivePersistenceError(
                "stable source URL path contains bearer material"
            )


def validate_credential_free_https_url(value: str) -> str:
    """Admit one stable HTTPS source identity with no bearer material."""

    if not isinstance(value, str):
        raise ScienceSensitivePersistenceError("reviewed URL must be a string")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ScienceSensitivePersistenceError("reviewed URL is malformed") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ScienceSensitivePersistenceError(
            "reviewed URL contains credentials or is not HTTPS"
        )
    _validate_stable_source_path(parsed.path)
    try:
        query_items = parse_qsl(
            parsed.query, keep_blank_values=True, strict_parsing=True
        )
    except ValueError:
        raise ScienceSensitivePersistenceError(
            "stable source URL query is malformed"
        ) from None
    seen_query_keys: set[str] = set()
    for raw_key, raw_value in query_items:
        key = _fully_decode_url_component(raw_key)
        item = _fully_decode_url_component(raw_value)
        normalized_key = re.sub(r"[^a-z0-9]", "", key.casefold())
        if normalized_key in seen_query_keys:
            raise ScienceSensitivePersistenceError(
                "stable source URL query contains duplicate keys"
            )
        seen_query_keys.add(normalized_key)
        if _credential_key(key):
            raise ScienceSensitivePersistenceError(
                "stable source URL query contains credential material"
            )
        allowed_values = _STABLE_SOURCE_QUERY_ALLOWLIST.get(normalized_key)
        if allowed_values is None or item.casefold() not in allowed_values:
            raise ScienceSensitivePersistenceError(
                "stable source URL query is not allowlisted"
            )
        reject_sensitive_persistence(item, path="stable_source_url_query")
    return value
