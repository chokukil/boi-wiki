"""Deterministic, row-free corporate metadata intake.

This module turns immutable source bytes into bounded EvidenceSpan records and a
catalog reconciliation receipt.  It deliberately does not create ontology
concepts, mappings, queries, SQL, execution results, or Release state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

import yaml

from .physical_temporal_encoding import PhysicalTemporalEncoding


_FORBIDDEN_SEMANTIC_CONTROL_KEYS = frozenset(
    {
        "object_type",
        "query_spec_id",
        "golden_count",
        "golden_result",
        "golden_rows",
        "release_manifest",
        "active_release",
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _byte_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _catalog_columns(definition: object) -> dict[str, str]:
    if not isinstance(definition, Mapping):
        return {}
    raw = definition.get("columns", definition)
    if not isinstance(raw, Mapping):
        return {}
    return {str(name): str(kind) for name, kind in raw.items()}


def _semantic_control_injections(value: object, *, path: str = "$") -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).casefold()
            child_path = f"{path}.{key}"
            if key in _FORBIDDEN_SEMANTIC_CONTROL_KEYS:
                found.append(child_path)
            found.extend(_semantic_control_injections(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_semantic_control_injections(child, path=f"{path}[{index}]"))
    return tuple(found)


def build_corporate_metadata_intake(
    *,
    metadata_bytes: bytes,
    metadata_artifact_ref: str,
    metadata_digest: str,
    catalog_snapshot: Mapping[str, object],
    catalog_snapshot_digest: str,
) -> dict[str, object]:
    """Build candidate-only evidence and reconciliation without reading rows."""

    actual_digest = _byte_digest(metadata_bytes)
    if actual_digest != metadata_digest:
        raise ValueError("SOURCE_DIGEST_MISMATCH:corporate_metadata")
    parsed = yaml.safe_load(metadata_bytes.decode("utf-8"))
    if not isinstance(parsed, Mapping) or not isinstance(parsed.get("tables"), list):
        raise ValueError("CORPORATE_METADATA_SCHEMA_INVALID")
    injections = _semantic_control_injections(parsed)
    if injections:
        raise ValueError(
            "CORPORATE_METADATA_SEMANTIC_INJECTION:" + ",".join(injections)
        )

    catalog_tables_raw = catalog_snapshot.get("tables") or {}
    if not isinstance(catalog_tables_raw, Mapping):
        raise ValueError("CATALOG_SNAPSHOT_SCHEMA_INVALID")
    catalog_tables = {
        str(table): _catalog_columns(definition)
        for table, definition in catalog_tables_raw.items()
    }
    metadata_contract_version = str(parsed.get("snapshot_version") or "")

    stable_ids: list[str] = []
    evidence_spans: list[dict[str, object]] = []
    drift_items: list[dict[str, str]] = []
    column_count = 0
    for table_index, raw_table in enumerate(parsed["tables"]):
        if not isinstance(raw_table, Mapping):
            raise ValueError("CORPORATE_METADATA_TABLE_INVALID")
        table_name = str(raw_table.get("table_name") or "").strip()
        columns = raw_table.get("columns") or []
        if not table_name or not isinstance(columns, list):
            raise ValueError("CORPORATE_METADATA_TABLE_INVALID")
        if table_name not in catalog_tables:
            drift_items.append({"kind": "missing_table", "table": table_name})
        catalog_columns = catalog_tables.get(table_name, {})
        normalized_columns: list[dict[str, object]] = []
        for raw_column in columns:
            if not isinstance(raw_column, Mapping):
                raise ValueError("CORPORATE_METADATA_COLUMN_INVALID")
            column_name = str(raw_column.get("column_name") or "").strip()
            stable_id = str(raw_column.get("stable_id") or "").strip()
            if not column_name or not stable_id:
                raise ValueError("CORPORATE_METADATA_COLUMN_ID_REQUIRED")
            column_count += 1
            stable_ids.append(stable_id)
            if table_name in catalog_tables and column_name not in catalog_columns:
                drift_items.append(
                    {
                        "kind": "missing_column",
                        "table": table_name,
                        "column": column_name,
                    }
                )
            declared_type = str(raw_column.get("physical_type") or "").strip()
            actual_type = catalog_columns.get(column_name, "")
            if declared_type and actual_type and declared_type.casefold() != actual_type.casefold():
                drift_items.append(
                    {
                        "kind": "type_mismatch",
                        "table": table_name,
                        "column": column_name,
                        "declared_type": declared_type,
                        "catalog_type": actual_type,
                    }
                )
            normalized = {
                "column_name": column_name,
                "display_name": str(raw_column.get("display_name") or ""),
                "description": str(raw_column.get("description") or ""),
                "stable_id": stable_id,
                "catalog_type": actual_type,
            }
            if "temporal_encoding" in raw_column:
                if metadata_contract_version != "corporate-column-metadata/v2":
                    raise ValueError(
                        "CORPORATE_METADATA_TEMPORAL_ENCODING_REQUIRES_V2"
                    )
                try:
                    temporal = PhysicalTemporalEncoding.model_validate(
                        raw_column["temporal_encoding"]
                    )
                except ValueError:
                    raise ValueError(
                        "CORPORATE_METADATA_TEMPORAL_ENCODING_INVALID"
                    ) from None
                normalized["temporal_encoding"] = temporal.model_dump(mode="json")
            normalized_columns.append(normalized)
        table_evidence = {
            "table_name": table_name,
            "display_name": str(raw_table.get("display_name") or ""),
            "description": str(raw_table.get("description") or ""),
            "columns": normalized_columns,
            "business_context": dict(parsed.get("business_context") or {}),
        }
        if metadata_contract_version == "corporate-column-metadata/v2":
            table_evidence["metadata_contract_version"] = metadata_contract_version
        evidence_spans.append(
            {
                "evidence_span_ref": "evidence:" + _digest(table_evidence),
                "source_artifact_ref": metadata_artifact_ref,
                "source_digest": actual_digest,
                "source_locator": f"tables[{table_index}]",
                "relation": "describes_physical_table",
                "text": " | ".join(
                    filter(
                        None,
                        (
                            table_evidence["display_name"],
                            table_evidence["description"],
                        ),
                    )
                ),
                "structured_evidence": table_evidence,
                "span_digest": _digest(table_evidence),
            }
        )

    duplicate_ids = sorted(
        stable_id for stable_id in set(stable_ids) if stable_ids.count(stable_id) > 1
    )
    missing_tables = [item for item in drift_items if item["kind"] == "missing_table"]
    missing_columns = [item for item in drift_items if item["kind"] == "missing_column"]
    type_mismatches = [item for item in drift_items if item["kind"] == "type_mismatch"]
    reason_codes: list[str] = []
    if duplicate_ids:
        reason_codes.append("STABLE_PHYSICAL_ID_COLLISION")
    if drift_items:
        reason_codes.append("CATALOG_SCHEMA_DRIFT")
    evidence_digest = _digest(
        {
            "metadata_digest": actual_digest,
            "catalog_snapshot_digest": catalog_snapshot_digest,
            "evidence_span_digests": [item["span_digest"] for item in evidence_spans],
            "drift_items": drift_items,
            "duplicate_stable_ids": duplicate_ids,
        }
    )
    receipt = {
        "receipt_version": "boi/catalog-reconciliation-receipt@1.0.0",
        "status": "fail" if reason_codes else "pass",
        "metadata_artifact_ref": metadata_artifact_ref,
        "metadata_digest": actual_digest,
        "catalog_snapshot_digest": catalog_snapshot_digest,
        "table_count": len(evidence_spans),
        "column_count": column_count,
        "stable_id_collision_count": len(duplicate_ids),
        "duplicate_stable_ids": duplicate_ids,
        "missing_table_count": len(missing_tables),
        "missing_column_count": len(missing_columns),
        "type_mismatch_count": len(type_mismatches),
        "drift_items": drift_items,
        "reason_codes": reason_codes,
        "raw_row_access_count": 0,
        "evidence_digest": evidence_digest,
    }
    receipt["receipt_digest"] = _digest(receipt)
    return {
        "evidence_spans": evidence_spans,
        "catalog_reconciliation_receipt": receipt,
    }
