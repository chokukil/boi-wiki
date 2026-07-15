from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    CapabilityDefinition,
    CapabilityState,
    DraftContractDefinition,
    HelperTemplateDefinition,
    OperationClass,
    Principal,
    TaskMode,
    WorkAssetKind,
)


class CapabilityRegistry:
    HANDLER_PLUGINS = {
        "grounded_read",
        "current_work",
        "task_runtime",
        "artifact_transform",
        "draft_artifact",
        "routine_plan",
        "deep_job",
    }
    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self.version = "2.0"
        self._definitions: dict[str, CapabilityDefinition] = {}
        self._draft_contracts: dict[str, DraftContractDefinition] = {}
        self._legacy_capability_aliases: dict[str, str] = {}
        self._legacy_source_aliases: dict[str, str] = {}
        self._legacy_required_capabilities: list[str] = []
        self._helper_templates: dict[str, HelperTemplateDefinition] = {}
        self._asset_defaults: dict[WorkAssetKind, str] = {}
        self.reload()

    def reload(self) -> None:
        payload = yaml.safe_load(self.catalog_path.read_text(encoding="utf-8")) or {}
        definitions = [CapabilityDefinition.model_validate(item) for item in payload.get("capabilities") or []]
        helper_templates = [
            HelperTemplateDefinition.model_validate(item)
            for item in payload.get("helper_templates") or []
        ]
        contract_path = self.catalog_path.with_name("draft-contracts-v2.yaml")
        contract_payload = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
        contracts = [
            DraftContractDefinition.model_validate(item)
            for item in contract_payload.get("draft_contracts") or []
        ]
        ids = [item.capability_id for item in definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability_id in v2 catalog")
        offer_ids = [offer.offer_id for item in definitions for offer in item.starter_offers]
        if len(offer_ids) != len(set(offer_ids)):
            raise ValueError("duplicate starter offer in v2 catalog")
        helper_template_ids = [item.template_id for item in helper_templates]
        if len(helper_template_ids) != len(set(helper_template_ids)):
            raise ValueError("duplicate helper template in v2 catalog")
        known_capabilities = set(ids)
        unknown_template_capabilities = sorted(
            {
                capability_id
                for template in helper_templates
                for capability_id in template.capability_ids
                if capability_id not in known_capabilities
            }
        )
        if unknown_template_capabilities:
            raise ValueError("unknown helper template capabilities: " + ", ".join(unknown_template_capabilities))
        raw_asset_defaults = payload.get("asset_defaults") if isinstance(payload.get("asset_defaults"), dict) else {}
        asset_defaults: dict[WorkAssetKind, str] = {}
        for raw_kind, raw_capability_id in raw_asset_defaults.items():
            try:
                asset_kind = WorkAssetKind(str(raw_kind))
            except ValueError as exc:
                raise ValueError(f"unknown asset default kind: {raw_kind}") from exc
            capability_id = str(raw_capability_id or "").strip()
            if capability_id not in known_capabilities:
                raise ValueError(f"unknown asset default capability: {capability_id}")
            definition = next(item for item in definitions if item.capability_id == capability_id)
            if asset_kind not in definition.supported_assets:
                raise ValueError(
                    f"asset default {capability_id} does not support {asset_kind.value}"
                )
            asset_defaults[asset_kind] = capability_id
        contract_ids = [item.contract_id for item in contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError("duplicate draft contract in v2 catalog")
        known_contracts = set(contract_ids)
        missing_contracts = sorted(
            {
                str(item.handler_config.get("draft_contract") or "")
                for item in definitions
                if item.handler_config.get("draft_contract")
                and str(item.handler_config.get("draft_contract")) not in known_contracts
            }
        )
        if missing_contracts:
            raise ValueError("unknown draft contracts: " + ", ".join(missing_contracts))
        self.version = str(payload.get("version") or "2.0")
        self._definitions = {item.capability_id: item for item in definitions}
        self._draft_contracts = {item.contract_id: item for item in contracts}
        self._helper_templates = {item.template_id: item for item in helper_templates}
        self._asset_defaults = asset_defaults
        legacy_import = payload.get("legacy_import") if isinstance(payload.get("legacy_import"), dict) else {}
        self._legacy_capability_aliases = {
            str(key): str(value)
            for key, value in (legacy_import.get("capability_aliases") or {}).items()
            if str(key) and str(value)
        }
        self._legacy_source_aliases = {
            str(key): str(value)
            for key, value in (legacy_import.get("source_scope_aliases") or {}).items()
            if str(key) and str(value)
        }
        self._legacy_required_capabilities = [
            str(value)
            for value in (legacy_import.get("required_capabilities") or [])
            if str(value)
        ]

    def get(self, capability_id: str) -> CapabilityDefinition:
        try:
            return self._definitions[capability_id]
        except KeyError as exc:
            raise KeyError(f"unknown capability: {capability_id}") from exc

    def all(self, *, external_only: bool = False) -> list[CapabilityDefinition]:
        values = list(self._definitions.values())
        if external_only:
            values = [item for item in values if item.external]
        return values

    def starter_offers(self) -> list[tuple[CapabilityDefinition, Any]]:
        return [
            (definition, offer)
            for definition in self.all()
            for offer in definition.starter_offers
        ]

    def helper_template(self, template_id: str) -> HelperTemplateDefinition:
        candidate = str(template_id or "").strip()
        try:
            return self._helper_templates[candidate]
        except KeyError as exc:
            raise KeyError(f"unknown helper template: {candidate}") from exc

    def default_for_asset(self, asset_kind: WorkAssetKind) -> CapabilityDefinition:
        try:
            capability_id = self._asset_defaults[asset_kind]
        except KeyError as exc:
            raise KeyError(f"no catalog default for asset: {asset_kind.value}") from exc
        return self.get(capability_id)

    def unique_for_handler(self, handler: str) -> CapabilityDefinition:
        matches = [item for item in self.all() if item.handler == handler]
        if len(matches) != 1:
            raise KeyError(
                f"handler {handler!r} requires an explicit capability; found {len(matches)} catalog entries"
            )
        return matches[0]

    def draft_contract(self, contract_id: str) -> DraftContractDefinition:
        try:
            return self._draft_contracts[contract_id]
        except KeyError as exc:
            raise KeyError(f"unknown draft contract: {contract_id}") from exc

    def legacy_capability_id(self, value: str) -> str:
        candidate = str(value or "").strip()
        return self._legacy_capability_aliases.get(candidate, candidate)

    def legacy_source_scope(self, value: str) -> str:
        candidate = str(value or "").strip()
        return self._legacy_source_aliases.get(candidate, candidate)

    def legacy_required_capabilities(self) -> list[str]:
        return list(self._legacy_required_capabilities)

    @staticmethod
    def effective_mode(task_mode: str | TaskMode | None) -> TaskMode:
        try:
            return task_mode if isinstance(task_mode, TaskMode) else TaskMode(str(task_mode or "copilot"))
        except ValueError:
            return TaskMode.copilot

    def state_for(
        self,
        definition: CapabilityDefinition,
        *,
        principal: Principal,
        readiness: dict[str, bool],
        task_mode: str | TaskMode | None,
        supplied_input: dict[str, Any] | None = None,
    ) -> tuple[CapabilityState, list[str], str]:
        if not principal.is_admin and not any(role in principal.roles for role in definition.permissions):
            return CapabilityState.unavailable, [], "권한이 없습니다."
        mode = self.effective_mode(task_mode)
        if mode not in definition.task_modes:
            return CapabilityState.unavailable, [], f"{mode.value} 모드에서는 사용할 수 없습니다."
        missing_dependencies = [name for name in definition.readiness if not readiness.get(name, False)]
        if missing_dependencies:
            return CapabilityState.unavailable, [], "필요한 기능이 준비되지 않았습니다: " + ", ".join(missing_dependencies)
        required = [str(item) for item in (definition.input_schema.get("required") or [])]
        values = supplied_input or {}
        missing = [name for name in required if not str(values.get(name) or "").strip()]
        if missing:
            return CapabilityState.needs_input, missing, "실행에 필요한 내용을 입력해주세요."
        return CapabilityState.ready, [], "바로 사용할 수 있습니다."

    def public_payload(self, *, principal: Principal, readiness: dict[str, bool]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for item in self.all(external_only=True):
            state, required, reason = self.state_for(
                item,
                principal=principal,
                readiness=readiness,
                task_mode=TaskMode.copilot,
                supplied_input={},
            )
            result.append(
                {
                    "capability_id": item.capability_id,
                    "version": item.version,
                    "title": item.title,
                    "description": item.description,
                    "operation": item.operation.value,
                    "user_effects": list(item.user_effects),
                    "default_user_effect": item.default_user_effect,
                    "semantic_operations": [operation.value for operation in item.semantic_operations],
                    "presentations": list(item.presentations),
                    "graph_query_kinds": list(item.graph_query_kinds),
                    "harness_ids": list(item.harness_ids),
                    "risk": item.risk.value,
                    "state": state.value,
                    "required_inputs": required,
                    "state_reason": reason,
                    "renderer": item.renderer,
                    "deep": item.deep,
                }
            )
        return result

    def runnable_ids(self, *, principal: Principal, readiness: dict[str, bool]) -> list[str]:
        result: list[str] = []
        for item in self.all():
            state, _, _ = self.state_for(
                item,
                principal=principal,
                readiness=readiness,
                task_mode=TaskMode.copilot,
                supplied_input={"query": "x", "goal": "x"},
            )
            if state == CapabilityState.ready:
                result.append(item.capability_id)
        return result

    def operation_allowed(self, definition: CapabilityDefinition, mode: TaskMode) -> bool:
        if definition.operation == OperationClass.read:
            return True
        return mode in {TaskMode.copilot, TaskMode.autopilot}

    @staticmethod
    def handler_supported(definition: CapabilityDefinition) -> bool:
        """Return whether the turn service has an executable handler class.

        Mutating work is represented as a guarded plan and confirmed through the
        domain APIs. A catalog entry must not fall through to a runtime 501.
        """
        return definition.handler in CapabilityRegistry.HANDLER_PLUGINS
