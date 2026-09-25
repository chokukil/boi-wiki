from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from .models import (
    OntologyProjectionRecipeDefinition,
    OntologyQueryRecipeDefinition,
    OntologyRelationTypeDefinition,
    OntologySchemaRegistryDocument,
)


class OntologySchemaRegistry:
    """Versioned domain schema and data-owned query/projection recipes."""

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        document = OntologySchemaRegistryDocument.model_validate(
            yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        )
        self._activate_document(
            document,
            checksum=hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        )

    def _activate_document(
        self,
        document: OntologySchemaRegistryDocument,
        *,
        checksum: str = "",
    ) -> None:
        self.document = document
        self._validate_references()
        self.checksum = checksum or self.fingerprint()
        self._query_by_id = {
            item.recipe_id: item for item in self.document.query_recipes
        }
        self._query_by_kind = {
            item.query_kind: item for item in self.document.query_recipes
        }
        self._projection_by_id = {
            item.projection_id: item for item in self.document.projection_recipes
        }
        self._relation_by_id = {
            item.relation_type_id: item for item in self.document.relation_types
        }

    def activate_payload(self, payload: dict[str, Any]) -> None:
        document = OntologySchemaRegistryDocument.model_validate(payload)
        checksum = hashlib.sha256(
            json.dumps(
                document.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self._activate_document(document, checksum=checksum)

    @property
    def version(self) -> str:
        return self.document.version

    @property
    def schema_revision(self) -> str:
        return self.document.schema_revision

    def _validate_references(self) -> None:
        entity_ids = {item.entity_type_id for item in self.document.entity_types}
        relation_ids = {item.relation_type_id for item in self.document.relation_types}
        query_ids = {item.recipe_id for item in self.document.query_recipes}
        duplicate_groups = {
            "entity": len(entity_ids) != len(self.document.entity_types),
            "relation": len(relation_ids) != len(self.document.relation_types),
            "query": len(query_ids) != len(self.document.query_recipes),
            "query_kind": len({item.query_kind for item in self.document.query_recipes})
            != len(self.document.query_recipes),
            "projection": len({item.projection_id for item in self.document.projection_recipes})
            != len(self.document.projection_recipes),
        }
        duplicated = [name for name, present in duplicate_groups.items() if present]
        if duplicated:
            raise ValueError("duplicate ontology registry ids: " + ", ".join(duplicated))
        unknown_priority = set(self.document.provenance_priority) - set(
            self.document.provenance_types
        )
        if unknown_priority:
            raise ValueError(
                "provenance priority references unknown values: "
                + ", ".join(sorted(unknown_priority))
            )
        for binding_id, binding in self.document.source_bindings.items():
            relation_refs = {
                str(item)
                for item in (
                    binding.get("metadata_relation_fields") or {}
                ).values()
                if str(item)
            }
            relation_refs.update(
                str(item)
                for item in binding.get("excluded_explicit_relations") or []
                if str(item)
            )
            if binding.get("markdown_link_relation"):
                relation_refs.add(str(binding["markdown_link_relation"]))
            unknown_relations = relation_refs - relation_ids
            if unknown_relations:
                raise ValueError(
                    f"source binding {binding_id} references unknown relations: "
                    + ", ".join(sorted(unknown_relations))
                )
        for relation in self.document.relation_types:
            unknown_types = (
                set(relation.source_types) | set(relation.target_types)
            ) - entity_ids
            if unknown_types:
                raise ValueError(
                    f"relation {relation.relation_type_id} references unknown entity types: "
                    + ", ".join(sorted(unknown_types))
                )
            if relation.inverse_relation and relation.inverse_relation not in relation_ids:
                raise ValueError(
                    f"relation {relation.relation_type_id} has unknown inverse: "
                    f"{relation.inverse_relation}"
                )
        for recipe in self.document.query_recipes:
            unknown_relations = (
                set(recipe.relation_types)
                | set(recipe.excluded_relation_types)
                | {
                    relation
                    for relations in recipe.relation_groups.values()
                    for relation in relations
                }
            ) - relation_ids
            if unknown_relations:
                raise ValueError(
                    f"query recipe {recipe.recipe_id} references unknown relations: "
                    + ", ".join(sorted(unknown_relations))
                )
        for projection in self.document.projection_recipes:
            if projection.query_recipe_id not in query_ids:
                raise ValueError(
                    f"projection {projection.projection_id} references unknown query recipe: "
                    f"{projection.query_recipe_id}"
                )
            unknown_types = set(projection.subject_types) - entity_ids
            unknown_relations = {
                relation
                for relations in [
                    *projection.sections.values(),
                    projection.traversal_relation_types,
                ]
                for relation in relations
            } - relation_ids
            if unknown_types or unknown_relations:
                raise ValueError(
                    f"projection {projection.projection_id} has invalid schema references"
                )
            unknown_projection_refs = {
                source.projection_id
                for sources in projection.output_fields.values()
                for source in sources
                if source.projection_id not in {
                    item.projection_id for item in self.document.projection_recipes
                }
            }
            if unknown_projection_refs:
                raise ValueError(
                    f"projection {projection.projection_id} composes unknown projections: "
                    + ", ".join(sorted(unknown_projection_refs))
                )
            unknown_output_types = {
                node_type
                for sources in projection.output_fields.values()
                for source in sources
                for node_type in source.node_types
                if node_type not in entity_ids
            }
            if unknown_output_types:
                raise ValueError(
                    f"projection {projection.projection_id} emits unknown entity types: "
                    + ", ".join(sorted(unknown_output_types))
                )
            unknown_depth_subject_types = {
                subject_type
                for sources in projection.output_fields.values()
                for source in sources
                for subject_type in source.max_depth_by_subject_type
                if subject_type not in entity_ids
            }
            invalid_depths = {
                f"{subject_type}:{depth}"
                for sources in projection.output_fields.values()
                for source in sources
                for subject_type, depth in source.max_depth_by_subject_type.items()
                if depth < 1 or depth > 6
            }
            if unknown_depth_subject_types or invalid_depths:
                raise ValueError(
                    f"projection {projection.projection_id} has invalid output path bounds: "
                    + ", ".join(
                        sorted(
                            [
                                *unknown_depth_subject_types,
                                *invalid_depths,
                            ]
                        )
                    )
                )

    def preview_changes(
        self,
        changes: dict[str, Any],
        *,
        version: str,
        schema_revision: str,
    ) -> tuple[OntologySchemaRegistryDocument, dict[str, Any]]:
        payload = self.document.model_dump(mode="json")
        collection_keys = {
            "entity_types": "entity_type_id",
            "relation_types": "relation_type_id",
            "query_recipes": "recipe_id",
            "projection_recipes": "projection_id",
        }
        impact: dict[str, Any] = {"upserted": {}, "removed": {}}
        unknown_sections = set(changes) - {
            *collection_keys,
            "source_bindings",
            "acl_policy",
            "provenance_types",
            "provenance_priority",
        }
        if unknown_sections:
            raise ValueError(
                "unknown ontology change sections: " + ", ".join(sorted(unknown_sections))
            )
        for section, identity_key in collection_keys.items():
            delta = changes.get(section) if isinstance(changes.get(section), dict) else {}
            current = {
                str(item.get(identity_key) or ""): item
                for item in payload.get(section) or []
                if isinstance(item, dict) and item.get(identity_key)
            }
            removed = [str(item) for item in delta.get("remove") or [] if str(item)]
            for item_id in removed:
                current.pop(item_id, None)
            upserted: list[str] = []
            for item in delta.get("upsert") or []:
                if not isinstance(item, dict) or not str(item.get(identity_key) or ""):
                    raise ValueError(f"{section}.upsert requires {identity_key}")
                item_id = str(item[identity_key])
                current[item_id] = item
                upserted.append(item_id)
            payload[section] = list(current.values())
            impact["upserted"][section] = upserted
            impact["removed"][section] = removed
        for section in ("source_bindings", "acl_policy"):
            delta = changes.get(section)
            if isinstance(delta, dict):
                payload[section] = {**(payload.get(section) or {}), **delta}
                impact["upserted"][section] = sorted(delta)
        for section in ("provenance_types", "provenance_priority"):
            if isinstance(changes.get(section), list):
                payload[section] = list(
                    dict.fromkeys(str(item) for item in changes[section] if str(item))
                )
                impact["upserted"][section] = payload[section]
        payload["version"] = version
        payload["schema_revision"] = schema_revision
        candidate = OntologySchemaRegistryDocument.model_validate(payload)
        previous = self.document
        try:
            self.document = candidate
            self._validate_references()
        finally:
            self.document = previous
        impact["candidate_counts"] = {
            "entity_types": len(candidate.entity_types),
            "relation_types": len(candidate.relation_types),
            "query_recipes": len(candidate.query_recipes),
            "projection_recipes": len(candidate.projection_recipes),
        }
        return candidate, impact

    def query_recipe(
        self,
        *,
        query_kind: str = "",
        recipe_id: str = "",
    ) -> OntologyQueryRecipeDefinition:
        candidate = self._query_by_id.get(recipe_id) if recipe_id else self._query_by_kind.get(query_kind)
        if candidate is None:
            raise KeyError(f"unknown ontology query recipe: {recipe_id or query_kind}")
        return candidate.model_copy(deep=True)

    def projection_recipe(self, projection_id: str) -> OntologyProjectionRecipeDefinition:
        try:
            return self._projection_by_id[projection_id].model_copy(deep=True)
        except KeyError as exc:
            raise KeyError(f"unknown ontology projection recipe: {projection_id}") from exc

    def relation(self, relation_type_id: str) -> OntologyRelationTypeDefinition | None:
        value = self._relation_by_id.get(relation_type_id)
        return value.model_copy(deep=True) if value is not None else None

    def entity_type(self, entity_type: str):
        normalized = str(entity_type or "").strip().lower()
        for item in self.document.entity_types:
            if normalized in {item.entity_type_id.lower(), item.label.lower()}:
                return item.model_copy(deep=True)
        raise KeyError(f"unknown ontology entity type: {entity_type}")

    def entity_lookup_candidates(
        self,
        lookup_key: str,
        value: str,
    ) -> list[str]:
        """Compile Registry-owned identity aliases without domain routing."""

        clean_key = str(lookup_key or "").strip()
        clean_value = str(value or "").strip()
        if not clean_key or not clean_value:
            return []
        candidates: list[str] = []
        for definition in self.document.entity_types:
            template = str(definition.lookup_templates.get(clean_key) or "").strip()
            if not template:
                continue
            try:
                candidate = template.format(value=clean_value).strip()
            except (KeyError, ValueError):
                continue
            if candidate:
                candidates.append(candidate)
        return list(dict.fromkeys(candidates))

    def relation_ids_for_evidence_use(self, evidence_use: str) -> set[str]:
        return {
            item.relation_type_id
            for item in self.document.relation_types
            if evidence_use in item.evidence_uses
        }

    def public_payload(self) -> dict[str, Any]:
        payload = self.document.model_dump(mode="json")
        return {
            **payload,
            "checksum": self.checksum,
            "query_recipe_count": len(self.document.query_recipes),
            "projection_recipe_count": len(self.document.projection_recipes),
        }

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.document.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
