"""OKF 0.2 compatibility and protected BoI Profile 0.2 validation.

The official OKF core is intentionally forward compatible.  The BoI profile is
the fail-closed boundary used before a candidate can enter governed storage.
Keeping these validators separate prevents local policy from being presented as
an OKF compatibility requirement.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping

from .okf_core import (ValidationIssue, ValidationResult, _issue, _nonempty_string,
                       normalize_okf_v02_metadata, validate_okf_v02_core)

from pydantic import ValidationError

from .cardinality_query_shape import (
    DataQualityReceipt,
    RelationshipContract,
    ResultShapeContract,
)
from .domain_profile_v02 import validate_domain_profile_entry
from .domain_profile_v03 import validate_domain_profile_entry as validate_domain_v03
from .domain_profile_v04 import validate_domain_profile_entry as validate_domain_v04
from .domain_profile_v05 import validate_domain_profile_entry as validate_domain_v05
from .latest_selection_contract import LatestSelectionContract, LatestSelectionContractV1
from .semantic_binding_contract import SEMANTIC_AUTHORITY_BASES


SUPPORTED_PROFILES = frozenset(
    {
        "boi/sci@0.7.0",
        "boi/domain@0.1.0",
        "boi/domain@0.2.0",
        "boi/domain@0.3.0",
        "boi/domain@0.4.0",
        "boi/domain@0.5.0",
        "boi/data-mapping@0.1.0",
        "boi/data-mapping@0.2.0",
        "boi/query@0.1.0",
        "boi/query@0.2.0",
        "boi/query@0.3.0",
        "boi/query@0.4.0",
        "boi/content@0.1.0",
    }
)
BOI_PROTECTED_EXTENSION_FIELDS = frozenset(
    {
        "okf_version",
        "boi_profile_version",
        "profiles",
        "boi_id",
        "visibility",
        "classification",
        "owner",
        "acl_policy",
        "sources[].type",
        "sources[].relation",
    }
)
LEGACY_PROVENANCE_FIELDS = frozenset({"source_refs", "generated_from", "timestamp"})
VALID_VISIBILITIES = frozenset({"private", "team", "public"})
VALID_CLASSIFICATIONS = frozenset({"internal", "confidential", "restricted"})
VALID_STATUSES = frozenset({"draft", "stable", "deprecated"})
SCIENCE_KINDS = frozenset(
    {"formula", "constant", "unit", "derivation", "dictionary", "case", "claim", "law", "principle"}
)
SCIENCE_LAYERS = frozenset({"L0", "L1", "L2", "L3", "L4"})
DOMAIN_KINDS = frozenset(
    {"Term", "ObjectType", "PropertyDefinition", "RelationType", "ValueType", "Metric", "Rule"}
)
DOMAIN_AUTHORITY_BASES = SEMANTIC_AUTHORITY_BASES
DOMAIN_FORBIDDEN_FIELDS = frozenset(
    {
        "source",
        "source_id",
        "table",
        "column",
        "physical",
        "sql",
        "raw_sql",
        "dialect",
        "schema_snapshot",
        "schema_snapshot_digest",
    }
)
QUERY_FORBIDDEN_FIELDS = frozenset({"raw_sql", "sql", "executed_sql", "repaired_sql"})
QUERY_BOUNDARY_FIELDS = frozenset(
    {
        "source",
        "source_id",
        "table",
        "column",
        "physical",
        "dialect",
        "schema_snapshot",
        "schema_snapshot_digest",
        "question",
        "question_text",
        "natural_language_question",
        "golden",
        "golden_answer",
        "golden_digest",
        "expected_digest",
        "expected_result_digest",
        "expected_fixture_contract",
        "multi_result_plan",
    }
)
CONTENT_KINDS = frozenset(
    {
        "action",
        "action-skill",
        "action-spec",
        "data-context",
        "event-skill",
        "event-type",
        "harness",
        "manual",
        "reference",
        "report",
        "sop",
        "source-wiki-page",
        "validation-report",
        "workflow-definition",
    }
)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _validation_summary(exc: ValidationError) -> str:
    """Return stable schema diagnostics without echoing governed input values."""

    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '<root>'}:{item['type']}"
        for item in exc.errors(include_url=False, include_input=False)
    )


def _deep_field_paths(value: object, forbidden: frozenset[str], *, path: str) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}"
            if key.casefold() in forbidden:
                found.append(child_path)
            found.extend(_deep_field_paths(child, forbidden, path=child_path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_deep_field_paths(child, forbidden, path=f"{path}[{index}]"))
    return tuple(found)


def _offset_datetime(value: Any) -> bool:
    if not _nonempty_string(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _validate_required_contract(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    for field in (
        "okf_version",
        "boi_profile_version",
        "profiles",
        "type",
        "title",
        "description",
        "boi_id",
        "visibility",
        "classification",
        "owner",
        "acl_policy",
        "generated",
        "sources",
        "status",
        "stale_after",
    ):
        if field not in metadata or metadata[field] in (None, ""):
            errors.append(_issue("BOI_V02_REQUIRED_FIELD", field, f"required field is missing: {field}"))

    if metadata.get("okf_version") != "0.2":
        errors.append(_issue("BOI_V02_VERSION", "okf_version", "protected documents must use OKF 0.2"))
    if metadata.get("boi_profile_version") != "0.2":
        errors.append(
            _issue("BOI_V02_PROFILE_VERSION", "boi_profile_version", "protected documents must use BoI Profile 0.2")
        )

    for field in sorted(LEGACY_PROVENANCE_FIELDS.intersection(metadata)):
        errors.append(
            _issue(
                "BOI_V02_LEGACY_FIELD",
                field,
                f"canonical 0.2 documents cannot contain legacy provenance field: {field}",
            )
        )

    generated = metadata.get("generated")
    if not isinstance(generated, Mapping) or not _nonempty_string(generated.get("by")):
        errors.append(_issue("BOI_V02_GENERATED_BY", "generated.by", "generated.by is required"))
    if not isinstance(generated, Mapping) or not _offset_datetime(generated.get("at")):
        errors.append(
            _issue("BOI_V02_GENERATED_AT", "generated.at", "generated.at must be an ISO-8601 offset datetime")
        )
    if not _offset_datetime(metadata.get("stale_after")):
        errors.append(
            _issue("BOI_V02_STALE_AFTER", "stale_after", "stale_after must be an ISO-8601 offset datetime")
        )

    sources = metadata.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append(_issue("BOI_V02_SOURCES", "sources", "at least one canonical source is required"))
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, Mapping):
                errors.append(_issue("BOI_V02_SOURCE", f"sources[{index}]", "source must be a mapping"))
                continue
            for key in ("type", "resource", "relation"):
                if not _nonempty_string(source.get(key)):
                    errors.append(
                        _issue("BOI_V02_SOURCE", f"sources[{index}].{key}", f"source {key} is required")
                    )

    if metadata.get("status") not in VALID_STATUSES:
        errors.append(_issue("BOI_V02_STATUS", "status", "status must be draft, stable, or deprecated"))
    if metadata.get("classification") not in VALID_CLASSIFICATIONS:
        errors.append(
            _issue(
                "BOI_V02_CLASSIFICATION",
                "classification",
                "classification must be internal, confidential, or restricted",
            )
        )


def _validate_acl(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    visibility = metadata.get("visibility")
    owner = metadata.get("owner")
    acl_policy = metadata.get("acl_policy")
    if visibility not in VALID_VISIBILITIES:
        errors.append(_issue("BOI_V02_VISIBILITY", "visibility", "visibility must be private, team, or public"))
        return
    if visibility == "private" and acl_policy != f"acl:private:{owner}":
        errors.append(_issue("BOI_V02_ACL", "acl_policy", "private ACL must be bound to the owner"))
    elif visibility == "team":
        team_id = metadata.get("team_id")
        if not _nonempty_string(team_id) or acl_policy != f"acl:team:{team_id}":
            errors.append(_issue("BOI_V02_ACL", "acl_policy", "team ACL must be bound to team_id"))
    elif visibility == "public" and acl_policy != "acl:public":
        errors.append(
            _issue(
                "BOI_V02_ACL",
                "acl_policy",
                "public is organization-wide internal visibility and requires acl:public",
            )
        )


def _validate_science(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    science = metadata.get("science")
    if not isinstance(science, Mapping):
        errors.append(_issue("BOI_SCI_REQUIRED", "science", "sci profile requires a science payload"))
        return
    if science.get("kind") not in SCIENCE_KINDS:
        errors.append(_issue("BOI_SCI_KIND", "science.kind", "science.kind is not supported by sci 0.7"))
    if science.get("layer") not in SCIENCE_LAYERS:
        errors.append(_issue("BOI_SCI_LAYER", "science.layer", "science.layer must be L0 through L4"))


def _validate_domain(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    domain = metadata.get("domain")
    if not isinstance(domain, Mapping):
        errors.append(_issue("BOI_DOMAIN_REQUIRED", "domain", "domain profile requires a domain payload"))
        return
    if domain.get("kind") not in DOMAIN_KINDS:
        errors.append(_issue("BOI_DOMAIN_KIND", "domain.kind", "unsupported domain knowledge kind"))
    if not _nonempty_string(domain.get("id")):
        errors.append(_issue("BOI_DOMAIN_ID", "domain.id", "domain knowledge requires a stable id"))
    if domain.get("authority_basis") not in DOMAIN_AUTHORITY_BASES:
        errors.append(
            _issue("BOI_DOMAIN_AUTHORITY", "domain.authority_basis", "domain authority_basis is required")
        )
    for field_path in sorted(
        _deep_field_paths(domain, DOMAIN_FORBIDDEN_FIELDS, path="domain")
    ):
        errors.append(
            _issue(
                "BOI_DOMAIN_BOUNDARY",
                field_path,
                "domain profile cannot own physical mapping or SQL",
            )
        )
    if domain.get("kind") == "Metric":
        for field in ("grain", "unit", "aggregation", "time_semantics"):
            if not _nonempty_string(domain.get(field)):
                errors.append(_issue("BOI_DOMAIN_METRIC", f"domain.{field}", f"Metric requires {field}"))


def _validate_domain_v02(
    metadata: Mapping[str, Any], errors: list[ValidationIssue]
) -> None:
    domain = metadata.get("domain")
    if not isinstance(domain, Mapping):
        errors.append(
            _issue(
                "BOI_DOMAIN_REQUIRED",
                "domain",
                "domain profile requires a domain payload",
            )
        )
        return
    try:
        validate_domain_profile_entry(domain)
    except ValidationError as exc:
        errors.append(
            _issue(
                "BOI_DOMAIN_V02_INVALID",
                "domain",
                f"strict domain entry is invalid: {_validation_summary(exc)}",
            )
        )


def _validate_domain_v03(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    try:
        validate_domain_v03(metadata.get("domain"))
    except ValidationError as exc:
        errors.append(_issue("BOI_DOMAIN_V03_INVALID", "domain", _validation_summary(exc)))


def _validate_domain_v04(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    try:
        validate_domain_v04(metadata.get("domain"))
    except ValidationError as exc:
        errors.append(_issue("BOI_DOMAIN_V04_INVALID", "domain", _validation_summary(exc)))


def _validate_domain_v05(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    try:
        validate_domain_v05(metadata.get('domain'))
    except ValidationError as exc:
        errors.append(_issue('BOI_DOMAIN_V05_INVALID', 'domain', _validation_summary(exc)))


def _validate_mapping(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    mapping = metadata.get("data_mapping")
    if not isinstance(mapping, Mapping):
        errors.append(
            _issue("BOI_MAPPING_REQUIRED", "data_mapping", "data-mapping profile requires a mapping payload")
        )
        return
    for field in ("mapping_id", "domain_ref"):
        if not _nonempty_string(mapping.get(field)):
            errors.append(_issue("BOI_MAPPING_FIELD", f"data_mapping.{field}", f"mapping requires {field}"))
    availability = mapping.get("availability", "bound")
    if availability not in {"bound", "unbound"}:
        errors.append(
            _issue("BOI_MAPPING_AVAILABILITY", "data_mapping.availability", "availability must be bound or unbound")
        )
    physical = mapping.get("physical")
    if availability == "unbound":
        if physical is not None:
            errors.append(
                _issue("BOI_MAPPING_UNBOUND_PHYSICAL", "data_mapping.physical", "unbound mapping cannot own a physical binding")
            )
        if not _nonempty_string(mapping.get("unbound_reason")):
            errors.append(
                _issue("BOI_MAPPING_UNBOUND_REASON", "data_mapping.unbound_reason", "unbound mapping requires a reason")
            )
    elif not isinstance(physical, Mapping):
        errors.append(_issue("BOI_MAPPING_PHYSICAL", "data_mapping.physical", "physical mapping is required"))
    else:
        for field in ("source", "table", "column"):
            if not _nonempty_string(physical.get(field)):
                errors.append(
                    _issue("BOI_MAPPING_PHYSICAL", f"data_mapping.physical.{field}", f"physical {field} is required")
                )
    if not SHA256_RE.fullmatch(str(mapping.get("schema_snapshot_digest") or "")):
        errors.append(
            _issue(
                "BOI_MAPPING_SCHEMA_DIGEST",
                "data_mapping.schema_snapshot_digest",
                "schema snapshot digest must be canonical sha256",
            )
        )

    parsed_relationship: RelationshipContract | None = None
    relationship_contract = mapping.get("relationship_contract")
    if relationship_contract is not None:
        try:
            parsed_relationship = RelationshipContract.model_validate(relationship_contract)
        except ValidationError as exc:
            errors.append(
                _issue(
                    "BOI_RELATIONSHIP_CONTRACT_INVALID",
                    "data_mapping.relationship_contract",
                    f"relationship contract is invalid: {_validation_summary(exc)}",
                )
            )
    parsed_quality: DataQualityReceipt | None = None
    quality_receipt = mapping.get("data_quality_receipt")
    if "boi/data-mapping@0.2.0" not in metadata.get("profiles", []) and (
        "directional_quality_receipts" in mapping or isinstance(quality_receipt,Mapping) and quality_receipt.get("directional_scope") is not None):
        errors.append(_issue("BOI_DIRECTIONAL_QUALITY_PROFILE_VERSION", "data_mapping", "directional quality requires data-mapping 0.2"))
    if quality_receipt is not None:
        try:
            parsed_quality = DataQualityReceipt.model_validate(quality_receipt)
        except ValidationError as exc:
            errors.append(
                _issue(
                    "BOI_DATA_QUALITY_RECEIPT_INVALID",
                    "data_mapping.data_quality_receipt",
                    f"data quality receipt is invalid: {_validation_summary(exc)}",
                )
            )
    if parsed_relationship is not None and parsed_quality is not None:
        if (
            parsed_quality.relationship_contract_digest
            != parsed_relationship.contract_digest
            or parsed_quality.schema_snapshot_digest
            != parsed_relationship.schema_snapshot_digest
            or parsed_quality.applied_orphan_policy
            != parsed_relationship.orphan_policy
        ):
            errors.append(
                _issue(
                    "BOI_DATA_QUALITY_CONTRACT_MISMATCH",
                    "data_mapping.data_quality_receipt",
                    "quality receipt must bind the exact relationship, schema snapshot, and orphan policy",
                )
            )


def _validate_mapping_v02(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    _validate_mapping(metadata,errors)
    mapping=metadata.get("data_mapping")
    if not isinstance(mapping,Mapping):
        return
    raw_relationship=mapping.get("relationship_contract")
    raw_qualities=mapping.get("directional_quality_receipts")
    if raw_relationship is None and raw_qualities is None:
        return
    try:
        if raw_relationship is None or not isinstance(raw_qualities,list) or not 1<=len(raw_qualities)<=2 or mapping.get("data_quality_receipt") is not None:
            raise ValueError("directional closure required")
        from .cardinality_query_shape import validate_directional_quality_closure
        relationship=RelationshipContract.model_validate(raw_relationship)
        qualities=tuple(DataQualityReceipt.model_validate(item) for item in raw_qualities)
        validate_directional_quality_closure(relationship,qualities)
    except ValueError:
        errors.append(_issue("BOI_DIRECTIONAL_QUALITY_INVALID", "data_mapping.directional_quality_receipts", "exact authorized direction, schema, policy and evidence closure required"))


def _validate_query_payload(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    query = metadata.get("query")
    if not isinstance(query, Mapping):
        errors.append(_issue("BOI_QUERY_REQUIRED", "query", "query profile requires a query payload"))
        return
    if "latest_selection_contracts" in query and not set(metadata.get("profiles", ())) & {"boi/query@0.3.0", "boi/query@0.4.0"}:
        errors.append(_issue("BOI_LATEST_PROFILE_REVISION_REQUIRED", "query.latest_selection_contracts", "latest requires an explicit protected query revision"))
    for field_path in sorted(
        _deep_field_paths(query, QUERY_FORBIDDEN_FIELDS, path="query")
    ):
        errors.append(
            _issue(
                "BOI_QUERY_RAW_SQL_FORBIDDEN",
                field_path,
                "query profile accepts logical plans, never raw or repaired SQL",
            )
        )
    for field_path in sorted(
        _deep_field_paths(query, QUERY_BOUNDARY_FIELDS, path="query")
    ):
        errors.append(
            _issue(
                "BOI_QUERY_BOUNDARY",
                field_path,
                "query profile cannot own physical identifiers, question text, oracle data, or a completed physical plan",
            )
        )
    if not _nonempty_string(query.get("query_spec_id")):
        errors.append(_issue("BOI_QUERY_ID", "query.query_spec_id", "query_spec_id is required"))
    if not isinstance(query.get("logical_plan"), Mapping):
        errors.append(_issue("BOI_QUERY_PLAN", "query.logical_plan", "logical_plan must be a mapping"))
    result_shape_contract = query.get("result_shape_contract")
    if result_shape_contract is not None:
        try:
            ResultShapeContract.model_validate(result_shape_contract)
        except ValidationError as exc:
            errors.append(
                _issue(
                    "BOI_RESULT_SHAPE_CONTRACT_INVALID",
                    "query.result_shape_contract",
                    f"result shape contract is invalid: {_validation_summary(exc)}",
                )
            )
    parameters = query.get("parameters")
    if not isinstance(parameters, list):
        errors.append(_issue("BOI_QUERY_PARAMETERS", "query.parameters", "typed parameter list is required"))
    else:
        names: set[str] = set()
        for index, parameter in enumerate(parameters):
            if not isinstance(parameter, Mapping):
                errors.append(_issue("BOI_QUERY_PARAMETER", f"query.parameters[{index}]", "parameter must be a mapping"))
                continue
            name = parameter.get("name")
            if not _nonempty_string(name) or not _nonempty_string(parameter.get("type")):
                errors.append(
                    _issue(
                        "BOI_QUERY_PARAMETER",
                        f"query.parameters[{index}]",
                        "parameter requires a name and declared type",
                    )
                )
            elif name in names:
                errors.append(
                    _issue("BOI_QUERY_PARAMETER", f"query.parameters[{index}].name", "parameter names must be unique")
                )
            else:
                names.add(name)


def _validate_attested_computation(
    metadata: Mapping[str, Any], errors: list[ValidationIssue]
) -> None:
    runtime = metadata.get("runtime")
    if not _nonempty_string(runtime):
        errors.append(
            _issue(
                "BOI_QUERY_RUNTIME_REQUIRED",
                "runtime",
                "official Attested Computation runtime must be a nonempty string",
            )
        )
    parameters = metadata.get("parameters")
    if not isinstance(parameters, list):
        errors.append(
            _issue(
                "BOI_QUERY_PARAMETERS",
                "parameters",
                "official Attested Computation parameters must be a list",
            )
        )
    else:
        names: set[str] = set()
        for index, parameter in enumerate(parameters):
            if (
                not isinstance(parameter, Mapping)
                or not _nonempty_string(parameter.get("name"))
                or not _nonempty_string(parameter.get("type"))
                or not isinstance(parameter.get("required"), bool)
            ):
                errors.append(
                    _issue(
                        "BOI_QUERY_PARAMETER",
                        f"parameters[{index}]",
                        "official parameter requires name, type, and boolean required",
                    )
                )
                continue
            name = str(parameter["name"])
            if name in names:
                errors.append(
                    _issue(
                        "BOI_QUERY_PARAMETER",
                        f"parameters[{index}].name",
                        "parameter names must be unique",
                    )
                )
            names.add(name)
    if "computation" in metadata and not _nonempty_string(metadata.get("computation")):
        errors.append(
            _issue(
                "BOI_QUERY_COMPUTATION_INVALID",
                "computation",
                "computation path must be a nonempty string when present",
            )
        )
    executor = metadata.get("executor")
    receipt = executor.get("receipt") if isinstance(executor, Mapping) else None
    if (
        not isinstance(executor, Mapping)
        or not _nonempty_string(executor.get("resource"))
        or not isinstance(receipt, list)
        or not receipt
        or any(not _nonempty_string(item) for item in receipt)
    ):
        errors.append(
            _issue(
                "BOI_QUERY_EXECUTOR_REQUIRED",
                "executor",
                "official executor requires resource and a nonempty receipt field list",
            )
        )
    attester = metadata.get("attester")
    if not isinstance(attester, Mapping) or not _nonempty_string(attester.get("resource")):
        errors.append(
            _issue(
                "BOI_QUERY_ATTESTER_REQUIRED",
                "attester.resource",
                "official attester resource is required",
            )
        )


def _validate_query(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    """Historical BoI query profile reader; never a new canonical writer."""

    _validate_query_payload(metadata, errors)

    if metadata.get("type") == "Attested Computation":
        runtime = metadata.get("runtime")
        if not isinstance(runtime, Mapping) or not _nonempty_string(
            runtime.get("resource")
        ):
            errors.append(
                _issue(
                    "BOI_QUERY_RUNTIME_REQUIRED",
                    "runtime.resource",
                    "legacy query 0.1 runtime contract is required",
                )
            )
        executor = metadata.get("executor")
        if (
            not isinstance(executor, Mapping)
            or not _nonempty_string(executor.get("resource"))
            or not _nonempty_string(executor.get("receipt"))
        ):
            errors.append(
                _issue(
                    "BOI_QUERY_EXECUTOR_REQUIRED",
                    "executor",
                    "legacy query 0.1 executor contract is required",
                )
            )
        attester = metadata.get("attester")
        if not isinstance(attester, Mapping) or not _nonempty_string(
            attester.get("resource")
        ):
            errors.append(
                _issue(
                    "BOI_QUERY_ATTESTER_REQUIRED",
                    "attester.resource",
                    "legacy query 0.1 attester contract is required",
                )
            )


def _validate_query_v02(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    concept_type = metadata.get("type")
    if concept_type == "Attested Computation":
        if "query" in metadata:
            errors.append(
                _issue(
                    "BOI_QUERY_ATTESTED_NESTED_FORBIDDEN",
                    "query",
                    "official Attested Computation fields must remain top-level",
                )
            )
        _validate_attested_computation(metadata, errors)
        return
    if concept_type != "boi/Exploratory Query Contract":
        errors.append(
            _issue(
                "BOI_QUERY_CONCEPT_TYPE",
                "type",
                "query 0.2 requires official Attested Computation or BoI exploratory type",
            )
        )
        return
    _validate_query_payload(metadata, errors)


def _validate_content(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    content = metadata.get("content")
    if not isinstance(content, Mapping):
        errors.append(_issue("BOI_CONTENT_REQUIRED", "content", "content profile requires a content payload"))
        return
    kind = content.get("kind")
    if kind not in CONTENT_KINDS:
        errors.append(_issue("BOI_CONTENT_KIND", "content.kind", "unsupported governed content kind"))
    if content.get("legacy_type") != f"boi/{kind}":
        errors.append(
            _issue(
                "BOI_CONTENT_LEGACY_TYPE",
                "content.legacy_type",
                "legacy_type must exactly preserve the governed boi content type",
            )
        )


def _validate_query_v03(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    _validate_latest_query(metadata, errors, LatestSelectionContractV1)


def _validate_query_v04(metadata: Mapping[str, Any], errors: list[ValidationIssue]) -> None:
    _validate_latest_query(metadata, errors, LatestSelectionContract)


def _validate_latest_query(metadata, errors, contract_type) -> None:
    _validate_query_v02(metadata, errors)
    if metadata.get("type") != "boi/Exploratory Query Contract":
        return
    query = metadata.get("query")
    if not isinstance(query, Mapping):
        return
    contracts = query.get("latest_selection_contracts", [])
    if not isinstance(contracts, list):
        errors.append(_issue("BOI_LATEST_CONTRACT_INVALID", "query.latest_selection_contracts", "expected a list"))
        return
    ids = set()
    for value in contracts:
        try:
            contract = contract_type.model_validate(value)
            if contract.policy_id in ids:
                raise ValueError("LATEST_POLICY_ID_DUPLICATE")
            ids.add(contract.policy_id)
        except ValidationError as exc:
            errors.append(_issue("BOI_LATEST_CONTRACT_INVALID", "query.latest_selection_contracts", _validation_summary(exc)))
        except ValueError:
            errors.append(_issue("BOI_LATEST_CONTRACT_INVALID", "query.latest_selection_contracts", "duplicate policy id"))


PROFILE_VALIDATORS = {
    "boi/sci@0.7.0": _validate_science,
    "boi/domain@0.1.0": _validate_domain,
    "boi/domain@0.2.0": _validate_domain_v02,
    "boi/domain@0.3.0": _validate_domain_v03,
    "boi/domain@0.4.0": _validate_domain_v04,
    "boi/domain@0.5.0": _validate_domain_v05,
    "boi/data-mapping@0.1.0": _validate_mapping,
    "boi/data-mapping@0.2.0": _validate_mapping_v02,
    "boi/query@0.1.0": _validate_query,
    "boi/query@0.2.0": _validate_query_v02,
    "boi/query@0.3.0": _validate_query_v03,
    "boi/query@0.4.0": _validate_query_v04,
    "boi/content@0.1.0": _validate_content,
}
PROFILE_PAYLOADS = {
    "boi/sci@0.7.0": "science",
    "boi/domain@0.1.0": "domain",
    "boi/domain@0.2.0": "domain",
    "boi/domain@0.3.0": "domain",
    "boi/domain@0.4.0": "domain",
    "boi/domain@0.5.0": "domain",
    "boi/data-mapping@0.1.0": "data_mapping",
    "boi/data-mapping@0.2.0": "data_mapping",
    "boi/query@0.1.0": "query",
    "boi/query@0.2.0": "query",
    "boi/query@0.3.0": "query",
    "boi/query@0.4.0": "query",
    "boi/content@0.1.0": "content",
}


def validate_boi_profile_v02(metadata: Mapping[str, Any]) -> ValidationResult:
    """Fail closed for protected BoI canonical/candidate surfaces."""

    errors: list[ValidationIssue] = list(validate_okf_v02_core(metadata).errors)
    _validate_required_contract(metadata, errors)
    _validate_acl(metadata, errors)

    profiles = metadata.get("profiles")
    if not isinstance(profiles, list) or not profiles or any(not _nonempty_string(item) for item in profiles):
        errors.append(_issue("BOI_V02_PROFILES", "profiles", "profiles must be a nonempty string list"))
        selected: list[str] = []
    else:
        selected = list(dict.fromkeys(profiles))
        if len(selected) != len(profiles):
            errors.append(_issue("BOI_V02_PROFILES", "profiles", "profiles must not contain duplicates"))

    for profile in selected:
        validator = PROFILE_VALIDATORS.get(profile)
        if validator is None:
            errors.append(_issue("BOI_V02_PROFILE_UNKNOWN", "profiles", f"unsupported protected profile: {profile}"))
        else:
            validator(metadata, errors)

    selected_payloads = {PROFILE_PAYLOADS[p] for p in selected if p in PROFILE_PAYLOADS}
    for profile, payload in PROFILE_PAYLOADS.items():
        if payload in metadata and payload not in selected_payloads:
            errors.append(
                _issue(
                    "BOI_V02_PROFILE_BOUNDARY",
                    payload,
                    f"payload {payload} requires selected profile {profile}",
                )
            )

    return ValidationResult(errors=tuple(errors))
