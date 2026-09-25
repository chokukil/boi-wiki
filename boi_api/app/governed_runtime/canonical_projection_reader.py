"""Strict read adapter for canonical active-Release projection surfaces."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical_runtime_pointer import (
    CanonicalRuntimePointerError,
    CanonicalRuntimePointerStore,
)


_CORE_REQUIRED_FILES = frozenset(
    {
        "search.jsonl",
        "graph.json",
        "mcp.json",
        "download-index.json",
        "report-index.json",
    }
)


class CanonicalProjectionError(RuntimeError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_json(value: Any) -> str:
    return _digest_bytes(_canonical_json(value))


@dataclass(frozen=True)
class CanonicalProjectionBundle:
    release_id: str
    release_manifest_digest: str
    qualification_receipt_id: str
    projection_digest: str
    projection_path: Path
    search_rows: tuple[dict[str, Any], ...]
    graph_edges: tuple[dict[str, Any], ...]
    mcp_documents: tuple[dict[str, Any], ...]
    download_objects: dict[str, str]


class CanonicalProjectionReader:
    """Consume rebuild products without accepting a raw content-root fallback."""

    def __init__(self, runtime_root: Path | str):
        self.runtime_root = Path(runtime_root)
        self.projections_root = self.runtime_root / "governed-runtime" / "projections"

    @staticmethod
    def _read_json(path: Path, code: str) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CanonicalProjectionError(code) from exc
        if not isinstance(value, dict):
            raise CanonicalProjectionError(code)
        return value

    def _active_manifest(self) -> tuple[Path, dict[str, Any]]:
        try:
            generation = CanonicalRuntimePointerStore(
                self.runtime_root / "governed-runtime" / "runtime-pointers"
            ).load_current()
        except CanonicalRuntimePointerError as exc:
            raise CanonicalProjectionError("CANONICAL_RUNTIME_POINTER_INVALID") from exc
        if generation is None:
            raise CanonicalProjectionError("CANONICAL_RUNTIME_POINTER_ABSENT")
        pointer = generation["active_release_pointer"]
        release_id = pointer["release_id"]
        release_manifest_digest = pointer["release_manifest_digest"]
        matches: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(self.projections_root.glob("*/projection-manifest.json")):
            manifest = self._read_json(path, "PROJECTION_MANIFEST_INVALID")
            if (
                manifest.get("release_id") == release_id
                and manifest.get("release_manifest_digest") == release_manifest_digest
            ):
                matches.append((path.parent, manifest))
        if not matches:
            raise CanonicalProjectionError("ACTIVE_RELEASE_PROJECTION_ABSENT")
        if len(matches) != 1:
            raise CanonicalProjectionError("ACTIVE_RELEASE_PROJECTION_AMBIGUOUS")
        return matches[0]

    @staticmethod
    def _verify_manifest(path: Path, manifest: dict[str, Any]) -> None:
        if manifest.get("schema") != "boi-release-projection/v1":
            raise CanonicalProjectionError("PROJECTION_SCHEMA_INVALID")
        files = manifest.get("files")
        if not isinstance(files, dict) or not _CORE_REQUIRED_FILES <= set(files):
            raise CanonicalProjectionError("PROJECTION_FILE_CLOSURE_INVALID")
        report_index = CanonicalProjectionReader._read_json(
            path / "report-index.json", "PROJECTION_REPORT_INDEX_INVALID"
        )
        reports = report_index.get("reports")
        revisions = list(manifest.get("revision_ids") or [])
        if (
            report_index.get("release_id") != manifest.get("release_id")
            or not isinstance(reports, dict)
            or set(reports) != set(revisions)
        ):
            raise CanonicalProjectionError("PROJECTION_REPORT_CLOSURE_INVALID")
        report_paths: set[str] = set()
        for revision_id, report in reports.items():
            if not isinstance(report, dict) or report.get("knowledge_revision_id") != revision_id:
                raise CanonicalProjectionError("PROJECTION_REPORT_CLOSURE_INVALID")
            for kind in ("html", "pdf"):
                name = report.get(f"{kind}_path")
                digest = report.get(f"{kind}_digest")
                if (
                    not isinstance(name, str)
                    or not re.fullmatch(rf"reports/[0-9a-f]{{64}}\.{kind}", name)
                    or files.get(name) != digest
                ):
                    raise CanonicalProjectionError("PROJECTION_REPORT_CLOSURE_INVALID")
                report_paths.add(name)
        if set(files) != _CORE_REQUIRED_FILES | report_paths:
            raise CanonicalProjectionError("PROJECTION_FILE_CLOSURE_INVALID")
        for name, expected in files.items():
            try:
                actual = _digest_bytes((path / name).read_bytes())
            except OSError as exc:
                raise CanonicalProjectionError("PROJECTION_FILE_ABSENT") from exc
            if actual != expected:
                raise CanonicalProjectionError("PROJECTION_FILE_DIGEST_MISMATCH")
        base = dict(manifest)
        projection_digest = base.pop("projection_digest", None)
        if projection_digest != _digest_json(base):
            raise CanonicalProjectionError("PROJECTION_MANIFEST_DIGEST_MISMATCH")
        if path.name != str(projection_digest).removeprefix("sha256:"):
            raise CanonicalProjectionError("PROJECTION_PATH_DIGEST_MISMATCH")

    @staticmethod
    def _jsonl(path: Path) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError
                rows.append(value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CanonicalProjectionError("PROJECTION_SEARCH_INVALID") from exc
        return tuple(rows)

    def load_active(self) -> CanonicalProjectionBundle:
        path, manifest = self._active_manifest()
        self._verify_manifest(path, manifest)
        graph = self._read_json(path / "graph.json", "PROJECTION_GRAPH_INVALID")
        mcp = self._read_json(path / "mcp.json", "PROJECTION_MCP_INVALID")
        downloads = self._read_json(
            path / "download-index.json", "PROJECTION_DOWNLOAD_INDEX_INVALID"
        )
        release_id = str(manifest["release_id"])
        if any(item.get("release_id") != release_id for item in (graph, mcp, downloads)):
            raise CanonicalProjectionError("PROJECTION_SURFACE_RELEASE_MISMATCH")
        edges = graph.get("edges")
        documents = mcp.get("documents")
        objects = downloads.get("objects")
        if (
            not isinstance(edges, list)
            or not all(isinstance(item, dict) for item in edges)
            or not isinstance(documents, list)
            or not all(isinstance(item, dict) for item in documents)
            or not isinstance(objects, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in objects.items())
        ):
            raise CanonicalProjectionError("PROJECTION_SURFACE_SHAPE_INVALID")
        search_rows = self._jsonl(path / "search.jsonl")
        revisions = list(manifest.get("revision_ids") or [])
        if (
            [item.get("knowledge_revision_id") for item in search_rows] != revisions
            or [item.get("knowledge_revision_id") for item in documents] != revisions
            or set(objects) != set(revisions)
        ):
            raise CanonicalProjectionError("PROJECTION_REVISION_CLOSURE_MISMATCH")
        return CanonicalProjectionBundle(
            release_id=release_id,
            release_manifest_digest=str(manifest["release_manifest_digest"]),
            qualification_receipt_id=str(manifest["qualification_receipt_id"]),
            projection_digest=str(manifest["projection_digest"]),
            projection_path=path,
            search_rows=search_rows,
            graph_edges=tuple(edges),
            mcp_documents=tuple(documents),
            download_objects=dict(objects),
        )

    def wiki_documents(self) -> tuple[dict[str, Any], ...]:
        """Project canonical documents into the existing read-only Wiki shape."""

        bundle = self.load_active()
        documents: list[dict[str, Any]] = []
        for item in bundle.mcp_documents:
            metadata = item.get("metadata")
            body = item.get("body")
            revision_id = item.get("knowledge_revision_id")
            if (
                not isinstance(metadata, dict)
                or not isinstance(body, str)
                or not isinstance(revision_id, str)
                or "source_refs" in metadata
            ):
                raise CanonicalProjectionError("CANONICAL_DOCUMENT_SHAPE_INVALID")
            boi_id = str(metadata.get("boi_id") or "")
            if not boi_id:
                raise CanonicalProjectionError("CANONICAL_DOCUMENT_ID_ABSENT")
            source_event = (
                metadata.get("source_event")
                if isinstance(metadata.get("source_event"), dict)
                else {}
            )
            event_type = metadata.get("event_type") or source_event.get("event_type")
            visibility = str(metadata.get("visibility") or "")
            if visibility == "team":
                scope = str(metadata.get("team_id") or "")
                virtual_path = f"team/{scope}/{boi_id}.md"
            elif visibility == "private":
                scope = str(metadata.get("owner") or "")
                virtual_path = f"private/{scope}/{boi_id}.md"
            else:
                virtual_path = f"public/{boi_id}.md"
            documents.append(
                {
                    "path": virtual_path,
                    "uri": "/" + boi_id,
                    "metadata": dict(metadata),
                    "body": body,
                    "visibility": visibility,
                    "event_type": event_type,
                    "canonical_projection": True,
                    "governance": {
                        "knowledge_revision_id": revision_id,
                        "release_id": bundle.release_id,
                        "release_manifest_digest": bundle.release_manifest_digest,
                    },
                }
            )
        return tuple(documents)

    def download_document(self, revision_id: str) -> bytes:
        """Return immutable bytes only for a revision in the active download index."""

        bundle = self.load_active()
        object_id = bundle.download_objects.get(revision_id)
        if not object_id:
            raise CanonicalProjectionError("DOWNLOAD_REVISION_NOT_IN_ACTIVE_RELEASE")
        digest = object_id.removeprefix("sha256:")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise CanonicalProjectionError("DOWNLOAD_OBJECT_ID_INVALID")
        path = (
            self.runtime_root
            / "governed-runtime"
            / "knowledge-objects"
            / digest[:2]
            / digest
        )
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise CanonicalProjectionError("DOWNLOAD_OBJECT_ABSENT") from exc
        if _digest_bytes(payload) != object_id:
            raise CanonicalProjectionError("DOWNLOAD_OBJECT_DIGEST_MISMATCH")
        return payload


__all__ = [
    "CanonicalProjectionBundle",
    "CanonicalProjectionError",
    "CanonicalProjectionReader",
]
