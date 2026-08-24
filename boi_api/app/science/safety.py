"""Shared non-secret validation for immutable Science records."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote, unquote, urlsplit


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


_EXACT_CREDENTIAL_TOKENS = frozenset(
    {
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
        "xamz",
        "xgoog",
        "xms",
        "sharedaccess",
        "sas",
        "presigned",
        "xamzcredential",
        "xamzsignature",
        "xgoogcredential",
        "xgoogsignature",
        "xmscredential",
        "xmssignature",
        "sharedaccesssignature",
    }
)
_CREDENTIAL_TOKEN_SEQUENCES = (
    ("access", "key"),
    ("access", "token"),
    ("api", "key"),
    ("basic", "auth"),
    ("client", "secret"),
    ("private", "key"),
    ("x", "amz", "credential"),
    ("x", "amz", "signature"),
    ("x", "goog", "credential"),
    ("x", "goog", "signature"),
    ("x", "ms", "credential"),
    ("x", "ms", "signature"),
    ("shared", "access", "signature"),
)
_STABLE_SOURCE_QUERIES = {"download=1", "download=true"}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


class SciencePublicValidationError(ValueError):
    """Closed REST/UI-safe replacement for input-bearing model errors."""

    diagnostic_code = "invalid_science_input"

    def __init__(self) -> None:
        super().__init__("Science input failed closed validation")


def closed_science_validation_error() -> SciencePublicValidationError:
    """Build a closed error after an input-bearing exception scope has ended."""

    return SciencePublicValidationError()


def _validate_percent_syntax(value: str) -> None:
    for index, character in enumerate(value):
        if character != "%":
            continue
        if (
            index + 2 >= len(value)
            or value[index + 1] not in _HEX_DIGITS
            or value[index + 2] not in _HEX_DIGITS
        ):
            raise ScienceSensitivePersistenceError(
                "stable source URL has malformed percent encoding"
            )


def _normalize_then_fully_decode(value: str) -> str:
    current = value
    try:
        for _attempt in range(8):
            normalized = unicodedata.normalize("NFKC", current)
            _validate_percent_syntax(normalized)
            decoded = unquote(normalized, errors="strict")
            candidate = unicodedata.normalize("NFKC", decoded)
            _validate_percent_syntax(candidate)
            if candidate == normalized:
                return candidate
            current = candidate
    except UnicodeDecodeError:
        raise ScienceSensitivePersistenceError(
            "stable source URL contains invalid encoding"
        ) from None
    try:
        normalized = unicodedata.normalize("NFKC", current)
        _validate_percent_syntax(normalized)
        decoded = unicodedata.normalize("NFKC", unquote(normalized, errors="strict"))
        _validate_percent_syntax(decoded)
    except UnicodeDecodeError:
        raise ScienceSensitivePersistenceError(
            "stable source URL contains invalid encoding"
        ) from None
    if decoded != normalized:
        raise ScienceSensitivePersistenceError(
            "stable source URL contains excessive encoding"
        )
    return decoded


def _boundary_tokens(parts: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        token for part in parts for token in re.findall(r"[a-z0-9]+", part.casefold())
    )


def _reject_credential_token_stream(parts: Sequence[str], *, location: str) -> None:
    tokens = _boundary_tokens(parts)
    if any(token in _EXACT_CREDENTIAL_TOKENS for token in tokens):
        raise ScienceSensitivePersistenceError(
            f"stable source URL {location} contains credential material"
        )
    for sequence in _CREDENTIAL_TOKEN_SEQUENCES:
        width = len(sequence)
        if any(
            tokens[index : index + width] == sequence
            for index in range(len(tokens) - width + 1)
        ):
            raise ScienceSensitivePersistenceError(
                f"stable source URL {location} contains credential material"
            )


def _validate_stable_source_path(path: str) -> str:
    decoded_path = _normalize_then_fully_decode(path)
    if any(
        unicodedata.category(character).startswith("C") for character in decoded_path
    ):
        raise ScienceSensitivePersistenceError(
            "stable source URL path contains control characters"
        )
    if any(delimiter in decoded_path for delimiter in ("=", "@", ":", ";", "\\")):
        raise ScienceSensitivePersistenceError(
            "stable source URL path contains forbidden key-value delimiters"
        )
    segments = [segment for segment in decoded_path.split("/") if segment]
    _reject_credential_token_stream(segments, location="path")
    canonical_path = quote(decoded_path, safe="/-._~!$&'()*+,")
    if canonical_path != path:
        raise ScienceSensitivePersistenceError(
            "stable source URL path is not canonical"
        )
    return canonical_path


def _validate_canonical_hostname(hostname: str) -> None:
    if len(hostname) > 253 or hostname.startswith(".") or hostname.endswith("."):
        raise ScienceSensitivePersistenceError(
            "stable source URL hostname is not canonical"
        )
    labels = hostname.split(".")
    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or re.fullmatch(r"[a-z0-9-]+", label) is None
        for label in labels
    ):
        raise ScienceSensitivePersistenceError(
            "stable source URL hostname is not canonical"
        )
    _reject_credential_token_stream(labels, location="hostname")


def validate_credential_free_https_url(value: str) -> str:
    """Admit one stable HTTPS source identity with no bearer material."""

    if not isinstance(value, str):
        raise ScienceSensitivePersistenceError("reviewed URL must be a string")
    normalized_value = unicodedata.normalize("NFKC", value)
    if normalized_value != value or not value.isascii():
        raise ScienceSensitivePersistenceError(
            "reviewed URL must use one canonical ASCII representation"
        )
    if any(ord(character) <= 0x20 or ord(character) == 0x7F for character in value):
        raise ScienceSensitivePersistenceError(
            "reviewed URL contains raw control or space characters"
        )
    if not value.startswith("https://"):
        raise ScienceSensitivePersistenceError("reviewed URL must use canonical HTTPS")
    authority = re.split(r"[/#?]", value.removeprefix("https://"), maxsplit=1)[0]
    if not authority or "%" in authority or "@" in authority:
        raise ScienceSensitivePersistenceError(
            "reviewed URL authority contains encoded or literal userinfo"
        )
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ScienceSensitivePersistenceError("reviewed URL is malformed") from None
    try:
        port = parsed.port
        hostname = parsed.hostname
    except ValueError:
        raise ScienceSensitivePersistenceError(
            "reviewed URL authority is malformed"
        ) from None
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
        or authority != hostname
    ):
        raise ScienceSensitivePersistenceError(
            "reviewed URL contains credentials or is not HTTPS"
        )
    _validate_canonical_hostname(hostname)
    canonical_path = _validate_stable_source_path(parsed.path)
    if parsed.query and parsed.query not in _STABLE_SOURCE_QUERIES:
        raise ScienceSensitivePersistenceError(
            "stable source URL query is not allowlisted"
        )
    canonical = f"https://{hostname}{canonical_path}"
    if parsed.query:
        canonical = f"{canonical}?{parsed.query}"
    if canonical != value:
        raise ScienceSensitivePersistenceError(
            "reviewed URL does not equal its checked canonical serialization"
        )
    return value
