"""Fail-closed, content-addressed intake for declared Science web sources.

This service only preserves authoritative source bytes and provenance.  It does
not extract semantic evidence, qualify candidates, or create a Release.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind, canonical_json


class ScienceSourceAcquisitionError(RuntimeError):
    """A declared source cannot be safely or immutably acquired."""


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(canonical_json(value))


@dataclass(frozen=True)
class FetchedSource:
    requested_resource: str
    final_resource: str
    status_code: int
    media_type: str
    payload: bytes
    response_header_digest: str


class SourceFetcher(Protocol):
    def fetch(self, resource: str, *, max_bytes: int) -> FetchedSource: ...


class UrlLibSourceFetcher:
    """Bounded HTTP fetcher whose output is revalidated by the intake service."""

    # Several standards publishers reject non-browser user agents before they
    # evaluate the resource.  Keep this stable because it is part of the
    # acquisition code digest; the service still applies its own URL allowlist.
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 "
        "BoI-Science-Source-Intake/1.0"
    )

    def fetch(self, resource: str, *, max_bytes: int) -> FetchedSource:
        request = Request(
            resource,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - allowlisted by caller
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise ScienceSourceAcquisitionError("source exceeds byte limit")
                payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise ScienceSourceAcquisitionError("source exceeds byte limit")
                headers = sorted(
                    (str(key).casefold(), " ".join(str(value).split()))
                    for key, value in response.headers.items()
                )
                return FetchedSource(
                    requested_resource=resource,
                    final_resource=response.geturl(),
                    status_code=int(response.status),
                    media_type=str(response.headers.get_content_type() or ""),
                    payload=payload,
                    response_header_digest=_digest(headers),
                )
        except (HTTPError, URLError, OSError, ValueError) as error:
            raise ScienceSourceAcquisitionError("authoritative source fetch failed") from error


@dataclass(frozen=True)
class AcquiredSourceArtifact:
    resource: str
    final_resource: str
    source_artifact_id: str
    content_digest: str
    byte_length: int
    media_type: str
    response_header_digest: str
    object_ref: str


@dataclass(frozen=True)
class ScienceSourceAcquisitionReceipt:
    schema: str
    request_id: str
    source_family: str
    requested_resources: int
    fetched_resources: int
    duplicate_source_bytes: int
    artifacts: tuple[AcquiredSourceArtifact, ...]
    policy_digest: str
    acquisition_code_digest: str
    receipt_digest: str
    qualification_receipt_id: None = None
    release_manifest_id: None = None
    active_release_transition: bool = False


class ScienceSourceAcquisitionService:
    """Acquire an exact set of declared source resources once."""

    SCHEMA = "boi-science-source-acquisition-receipt/v3"
    ALLOWED_HOSTS = frozenset(
        {
            "bipm.org",
            "www.bipm.org",
            "physics.nist.gov",
            "feynmanlectures.caltech.edu",
        }
    )

    def __init__(
        self,
        *,
        artifact_root: Path | str,
        ledger_root: Path | str,
        fetcher: SourceFetcher | None = None,
        clock: Callable[[], str] | None = None,
        max_bytes: int = 32 * 1024 * 1024,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.artifact_root = Path(artifact_root)
        self.ledger_root = Path(ledger_root)
        self.ledger = GovernedRuntimeLedger(self.ledger_root)
        self.fetcher = fetcher or UrlLibSourceFetcher()
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.max_bytes = max_bytes

    @classmethod
    def _validate_resource(cls, resource: str) -> str:
        parsed = urlsplit(resource)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in cls.ALLOWED_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ScienceSourceAcquisitionError("source resource is not allowlisted")
        return resource

    def _request_path(self, request_id: str) -> Path:
        if not request_id or len(request_id) > 200 or any(char in request_id for char in "/\\\0"):
            raise ScienceSourceAcquisitionError("request id is invalid")
        key = hashlib.sha256(request_id.encode()).hexdigest()
        return self.ledger_root / "acquisition-requests" / f"{key}.json"

    @staticmethod
    def _receipt_from_dict(value: dict[str, object]) -> ScienceSourceAcquisitionReceipt:
        values = dict(value)
        artifacts = tuple(
            AcquiredSourceArtifact(**item) for item in values.pop("artifacts")  # type: ignore[arg-type]
        )
        return ScienceSourceAcquisitionReceipt(artifacts=artifacts, **values)  # type: ignore[arg-type]

    def verify(self, *, request_id: str) -> ScienceSourceAcquisitionReceipt:
        """Re-verify the immutable receipt, ledger records, and stored bytes."""

        request_path = self._request_path(request_id)
        try:
            stored = json.loads(request_path.read_text("utf-8"))
            receipt = self._receipt_from_dict(stored)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise ScienceSourceAcquisitionError("acquisition receipt is invalid") from error
        if receipt.schema != self.SCHEMA or receipt.request_id != request_id:
            raise ScienceSourceAcquisitionError("acquisition receipt is invalid")
        base = asdict(receipt)
        base.pop("receipt_digest")
        if _digest(base) != receipt.receipt_digest:
            raise ScienceSourceAcquisitionError("acquisition receipt digest is invalid")
        for artifact in receipt.artifacts:
            object_ref = Path(artifact.object_ref)
            if object_ref.is_absolute() or ".." in object_ref.parts:
                raise ScienceSourceAcquisitionError("source object ref is invalid")
            object_path = self.artifact_root / object_ref
            try:
                payload = object_path.read_bytes()
                record = self.ledger.read(artifact.source_artifact_id)
            except (OSError, LedgerError) as error:
                raise ScienceSourceAcquisitionError("source artifact is unavailable") from error
            if (
                len(payload) != artifact.byte_length
                or _digest_bytes(payload) != artifact.content_digest
                or record.kind is not RecordKind.SOURCE_ARTIFACT
                or record.authority != "intake_service"
                or record.payload.get("content_digest") != artifact.content_digest
                or record.payload.get("byte_length") != artifact.byte_length
                or record.payload.get("resource") != artifact.resource
                or record.payload.get("object_ref") != artifact.object_ref
            ):
                raise ScienceSourceAcquisitionError("source artifact bytes are invalid")
        return receipt

    def acquire(
        self,
        *,
        resources: Sequence[str],
        source_family: str,
        request_id: str,
    ) -> ScienceSourceAcquisitionReceipt:
        normalized = tuple(sorted({self._validate_resource(str(item)) for item in resources}))
        if not normalized or not source_family.strip():
            raise ScienceSourceAcquisitionError("source request is empty")
        request_path = self._request_path(request_id)
        policy = {
            "schema": "boi-science-source-acquisition-policy/v1",
            "allowed_hosts": sorted(self.ALLOWED_HOSTS),
            "https_only": True,
            "max_bytes": self.max_bytes,
            "resources": list(normalized),
            "source_family": source_family,
            "acquisition_code_digest": _digest_bytes(Path(__file__).read_bytes()),
        }
        policy_digest = _digest(policy)
        if request_path.exists():
            receipt = self.verify(request_id=request_id)
            if receipt.policy_digest != policy_digest:
                raise ScienceSourceAcquisitionError("idempotency request conflicts")
            return receipt

        fetched: list[FetchedSource] = []
        for resource in normalized:
            response = self.fetcher.fetch(resource, max_bytes=self.max_bytes)
            if response.requested_resource != resource:
                raise ScienceSourceAcquisitionError("fetch request binding is invalid")
            self._validate_resource(response.final_resource)
            if response.status_code < 200 or response.status_code >= 300:
                raise ScienceSourceAcquisitionError("source response is not successful")
            if not response.payload:
                raise ScienceSourceAcquisitionError("source response is empty")
            if len(response.payload) > self.max_bytes:
                raise ScienceSourceAcquisitionError("source exceeds byte limit")
            fetched.append(response)

        occurred_at = self.clock()
        artifacts: list[AcquiredSourceArtifact] = []
        observed_digests: set[str] = set()
        duplicate_bytes = 0
        for response in fetched:
            content_digest = _digest_bytes(response.payload)
            digest_hex = content_digest.removeprefix("sha256:")
            object_ref = Path("objects") / "sha256" / digest_hex
            object_path = self.artifact_root / object_ref
            object_path.parent.mkdir(parents=True, exist_ok=True)
            if object_path.exists():
                if object_path.read_bytes() != response.payload:
                    raise ScienceSourceAcquisitionError("content-addressed object conflict")
            else:
                descriptor = os.open(object_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(response.payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            if content_digest in observed_digests:
                duplicate_bytes += 1
            observed_digests.add(content_digest)
            record = self.ledger.append(
                RecordKind.SOURCE_ARTIFACT,
                {
                    "content_digest": content_digest,
                    "byte_length": len(response.payload),
                    "resource": response.requested_resource,
                    "final_resource": response.final_resource,
                    "source_family": source_family,
                    "media_type": response.media_type,
                    "response_header_digest": response.response_header_digest,
                    "acquisition_policy_digest": policy_digest,
                    "object_ref": object_ref.as_posix(),
                },
                authority="intake_service",
                occurred_at=occurred_at,
            )
            artifacts.append(
                AcquiredSourceArtifact(
                    resource=response.requested_resource,
                    final_resource=response.final_resource,
                    source_artifact_id=record.record_id,
                    content_digest=content_digest,
                    byte_length=len(response.payload),
                    media_type=response.media_type,
                    response_header_digest=response.response_header_digest,
                    object_ref=object_ref.as_posix(),
                )
            )
        base = {
            "schema": self.SCHEMA,
            "request_id": request_id,
            "source_family": source_family,
            "requested_resources": len(normalized),
            "fetched_resources": len(fetched),
            "duplicate_source_bytes": duplicate_bytes,
            "artifacts": [asdict(item) for item in artifacts],
            "policy_digest": policy_digest,
            "acquisition_code_digest": policy["acquisition_code_digest"],
            "qualification_receipt_id": None,
            "release_manifest_id": None,
            "active_release_transition": False,
        }
        receipt = ScienceSourceAcquisitionReceipt(
            schema=self.SCHEMA,
            request_id=request_id,
            source_family=source_family,
            requested_resources=len(normalized),
            fetched_resources=len(fetched),
            duplicate_source_bytes=duplicate_bytes,
            artifacts=tuple(artifacts),
            policy_digest=policy_digest,
            acquisition_code_digest=policy["acquisition_code_digest"],
            receipt_digest=_digest(base),
        )
        request_path.parent.mkdir(parents=True, exist_ok=True)
        stored = canonical_json(asdict(receipt)) + b"\n"
        try:
            descriptor = os.open(request_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            existing = json.loads(request_path.read_text("utf-8"))
            if existing != asdict(receipt):
                raise ScienceSourceAcquisitionError("idempotency receipt conflict")
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(stored)
                handle.flush()
                os.fsync(handle.fileno())
        return receipt


__all__ = [
    "AcquiredSourceArtifact",
    "FetchedSource",
    "ScienceSourceAcquisitionError",
    "ScienceSourceAcquisitionReceipt",
    "ScienceSourceAcquisitionService",
    "UrlLibSourceFetcher",
]
