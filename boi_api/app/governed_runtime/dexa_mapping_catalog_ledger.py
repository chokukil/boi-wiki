"""Deterministic property-level physical mapping catalog ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_json(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _digest_bytes(raw)


def _valid_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(item in "0123456789abcdef" for item in value[7:])
    )


class CatalogSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MappingCatalogIssue:
    issue_id: str
    kind: Literal[
        "MISSING_TABLE",
        "MISSING_COLUMN",
        "CATALOG_UNAVAILABLE",
        "MALFORMED_MAPPING",
    ]
    object_type: str
    property_name: str
    source: str
    table: str
    column: str
    metadata_ready: Literal[False] = False


@dataclass(frozen=True)
class MappingCatalogCounts:
    object_types: int
    object_types_without_physical_mapping: int
    physical_bindings: int
    matched_bindings: int
    missing_table_bindings: int
    missing_table_groups: int
    missing_column_bindings: int
    catalog_unavailable_bindings: int
    malformed_bindings: int


@dataclass(frozen=True)
class MappingCatalogLedger:
    schema_name: Literal["boi-dexa-mapping-catalog-ledger/v1"]
    gate: Literal["ready", "blocked"]
    source_digests: dict[str, str]
    counts: MappingCatalogCounts
    issues: tuple[MappingCatalogIssue, ...]
    ledger_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_name": self.schema_name,
            "gate": self.gate,
            "source_digests": dict(self.source_digests),
            "counts": asdict(self.counts),
            "issues": [asdict(item) for item in self.issues],
            "ledger_digest": self.ledger_digest,
        }


def _read_verified(path: Path, *, expected_digest: str) -> bytes:
    if not _valid_digest(expected_digest):
        raise CatalogSourceError("SOURCE_DIGEST_INVALID")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CatalogSourceError("SOURCE_UNAVAILABLE") from exc
    if _digest_bytes(raw) != expected_digest:
        raise CatalogSourceError("SOURCE_DIGEST_MISMATCH")
    return raw


def load_json_source(path: Path, *, expected_digest: str) -> list[dict[str, object]]:
    raw = _read_verified(path, expected_digest=expected_digest)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogSourceError("SOURCE_JSON_INVALID") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise CatalogSourceError("SOURCE_OBJECT_TYPES_INVALID")
    return value


def load_sqlite_catalog(
    path: Path,
    *,
    expected_digest: str,
) -> dict[str, tuple[str, ...]]:
    _read_verified(path, expected_digest=expected_digest)
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise CatalogSourceError("CATALOG_OPEN_FAILED") from exc
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table', 'view') ORDER BY lower(name), name"
        ).fetchall()
        catalog: dict[str, tuple[str, ...]] = {}
        for (name,) in rows:
            normalized_name = str(name).strip().lower()
            escaped_name = str(name).replace('"', '""')
            columns = connection.execute(
                f'PRAGMA table_info("{escaped_name}")'
            ).fetchall()
            catalog[normalized_name] = tuple(
                sorted({str(row[1]).strip().lower() for row in columns if row[1]})
            )
        return catalog
    except sqlite3.Error as exc:
        raise CatalogSourceError("CATALOG_READ_FAILED") from exc
    finally:
        connection.close()


def _normalize_catalogs(
    catalogs: Mapping[str, Mapping[str, Sequence[str]]],
) -> dict[str, dict[str, frozenset[str]]]:
    return {
        str(source).strip().lower(): {
            str(table).strip().lower(): frozenset(
                str(column).strip().lower() for column in columns
            )
            for table, columns in tables.items()
        }
        for source, tables in catalogs.items()
    }


def build_mapping_catalog_ledger(
    *,
    object_types: Sequence[Mapping[str, object]],
    catalogs: Mapping[str, Mapping[str, Sequence[str]]],
    source_digests: Mapping[str, str],
) -> MappingCatalogLedger:
    normalized_digests = {
        str(name).strip(): str(value).strip() for name, value in source_digests.items()
    }
    if not normalized_digests or not all(
        name and _valid_digest(value) for name, value in normalized_digests.items()
    ):
        raise CatalogSourceError("LEDGER_SOURCE_DIGEST_INVALID")
    normalized_catalogs = _normalize_catalogs(catalogs)
    issues: list[MappingCatalogIssue] = []
    object_types_without_mapping = 0
    physical_bindings = 0
    matched_bindings = 0
    missing_table_groups: set[tuple[str, str]] = set()
    seen_bindings: set[tuple[str, str]] = set()

    for raw_object_type in object_types:
        object_type = str(raw_object_type.get("name") or "").strip()
        if not object_type:
            raise CatalogSourceError("OBJECT_TYPE_NAME_REQUIRED")
        schema = raw_object_type.get("schema")
        properties = schema.get("properties") if isinstance(schema, Mapping) else None
        if not isinstance(properties, Mapping):
            object_types_without_mapping += 1
            continue
        mapped_for_object = 0
        for raw_property_name, raw_property in properties.items():
            property_name = str(raw_property_name).strip()
            kinetic = (
                raw_property.get("kinetic")
                if isinstance(raw_property, Mapping)
                else None
            )
            if not isinstance(kinetic, Mapping):
                continue
            source = str(kinetic.get("source") or "").strip().lower()
            table = str(kinetic.get("table") or "").strip()
            column = str(kinetic.get("column") or "").strip()
            binding_identity = (object_type, property_name)
            if binding_identity in seen_bindings:
                raise CatalogSourceError("DUPLICATE_PROPERTY_BINDING")
            seen_bindings.add(binding_identity)
            mapped_for_object += 1
            physical_bindings += 1
            if not property_name or not source or not table or not column:
                issues.append(
                    MappingCatalogIssue(
                        issue_id=(f"MALFORMED_MAPPING:{object_type}.{property_name}"),
                        kind="MALFORMED_MAPPING",
                        object_type=object_type,
                        property_name=property_name,
                        source=source,
                        table=table,
                        column=column,
                    )
                )
                continue
            source_catalog = normalized_catalogs.get(source)
            if source_catalog is None:
                issues.append(
                    MappingCatalogIssue(
                        issue_id=(
                            "CATALOG_UNAVAILABLE:"
                            f"{object_type}.{property_name}@{source}.{table}.{column}"
                        ),
                        kind="CATALOG_UNAVAILABLE",
                        object_type=object_type,
                        property_name=property_name,
                        source=source,
                        table=table,
                        column=column,
                    )
                )
                continue
            columns = source_catalog.get(table.lower())
            if columns is None:
                missing_table_groups.add((source, table.lower()))
                issues.append(
                    MappingCatalogIssue(
                        issue_id=(
                            "MISSING_TABLE:"
                            f"{object_type}.{property_name}@{source}.{table}.{column}"
                        ),
                        kind="MISSING_TABLE",
                        object_type=object_type,
                        property_name=property_name,
                        source=source,
                        table=table,
                        column=column,
                    )
                )
                continue
            if column.lower() not in columns:
                issues.append(
                    MappingCatalogIssue(
                        issue_id=(
                            "MISSING_COLUMN:"
                            f"{object_type}.{property_name}@{source}.{table}.{column}"
                        ),
                        kind="MISSING_COLUMN",
                        object_type=object_type,
                        property_name=property_name,
                        source=source,
                        table=table,
                        column=column,
                    )
                )
                continue
            matched_bindings += 1
        if mapped_for_object == 0:
            object_types_without_mapping += 1

    issues.sort(key=lambda item: item.issue_id)
    counts = MappingCatalogCounts(
        object_types=len(object_types),
        object_types_without_physical_mapping=object_types_without_mapping,
        physical_bindings=physical_bindings,
        matched_bindings=matched_bindings,
        missing_table_bindings=sum(item.kind == "MISSING_TABLE" for item in issues),
        missing_table_groups=len(missing_table_groups),
        missing_column_bindings=sum(item.kind == "MISSING_COLUMN" for item in issues),
        catalog_unavailable_bindings=sum(
            item.kind == "CATALOG_UNAVAILABLE" for item in issues
        ),
        malformed_bindings=sum(item.kind == "MALFORMED_MAPPING" for item in issues),
    )
    base = {
        "schema_name": "boi-dexa-mapping-catalog-ledger/v1",
        "gate": "blocked" if issues else "ready",
        "source_digests": dict(sorted(normalized_digests.items())),
        "counts": asdict(counts),
        "issues": [asdict(item) for item in issues],
    }
    return MappingCatalogLedger(
        schema_name="boi-dexa-mapping-catalog-ledger/v1",
        gate=base["gate"],
        source_digests=base["source_digests"],
        counts=counts,
        issues=tuple(issues),
        ledger_digest=_digest_json(base),
    )
