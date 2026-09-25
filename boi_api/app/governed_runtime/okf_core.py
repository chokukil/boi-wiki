"""Shared formal OKF 0.2 core checks, independent of domain/server policy."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _issue(code: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, path=path, message=message)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_okf_v02_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Return a non-mutating normalization accepted by the pinned OKF 0.2 spec."""

    normalized = deepcopy(dict(metadata))
    if isinstance(normalized.get("verified"), Mapping):
        normalized["verified"] = [deepcopy(dict(normalized["verified"]))]
    return normalized


def validate_okf_v02_core(metadata: Mapping[str, Any], *, path: str | None = None) -> ValidationResult:
    """Validate only formal OKF 0.2 compatibility requirements.

    Unknown types and keys are deliberately allowed.  A root ``index.md`` is
    bundle metadata and may carry ``okf_version`` without a concept ``type``.
    """

    errors: list[ValidationIssue] = []
    normalized_path = PurePosixPath(path.replace("\\", "/")) if path else None
    if normalized_path and normalized_path.name == "index.md":
        if len(normalized_path.parts) == 1:
            if metadata.get("okf_version") not in (None, "0.2"):
                errors.append(_issue("OKF_CORE_VERSION", "okf_version", "root index version must be 0.2"))
            return ValidationResult(tuple(errors))
        if metadata:
            errors.append(
                _issue(
                    "OKF_CORE_NESTED_INDEX_FRONTMATTER",
                    str(normalized_path),
                    "only the root index.md may declare bundle frontmatter",
                )
            )
            return ValidationResult(tuple(errors))
    if not _nonempty_string(metadata.get("type")):
        errors.append(_issue("OKF_CORE_TYPE_REQUIRED", "type", "concept type must be a nonempty string"))
    return ValidationResult(tuple(errors))
