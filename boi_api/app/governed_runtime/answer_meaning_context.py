"""Lossless logical meaning supplied with a governed result.

This is a projection of already authorized definitions, not a new interpretation
or a semantic-equivalence decision. Physical mappings and SQL are not inputs.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Sequence

from pydantic import Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, semantic_digest
from .semantic_profile_loader import LoadedProfileEntry
from .semantic_profile_retrieval import HybridSemanticRetriever


def _meaning_dependencies(entry):
    refs = HybridSemanticRetriever._query_dependencies(entry)
    semantics = entry.payload.get('semantic_contract') or {}
    refs.update(semantics[key] for key in ('quantity_kind_ref','unit_ref') if semantics.get(key))
    for qualifier in (entry.payload.get('applicability') or {}).get('conditions', ()):
        if isinstance(qualifier, dict):
            refs.update(item['property_ref'] for item in qualifier.get('predicates', ())
                if isinstance(item, dict) and item.get('property_ref'))
    return tuple(sorted(refs))


class AnswerDefinition(FrozenContract):
    ref: Ref
    revision_id: Ref
    revision_digest: Digest
    definition_digest: Digest
    logical_definition: dict[str, Any]
    evidence_refs: tuple[str, ...]
    dependency_refs: tuple[str, ...]

    @model_validator(mode='after')
    def definition_binding(self):
        if self.logical_definition.get('id') != self.ref:
            raise ValueError('ANSWER_DEFINITION_ID_MISMATCH')
        if self.definition_digest != semantic_digest(self.logical_definition):
            raise ValueError('ANSWER_DEFINITION_CONTENT_MISMATCH')
        return self


class AnswerMeaningContext(FrozenContract):
    contract_version: Literal['boi/answer-meaning-context@1'] = 'boi/answer-meaning-context@1'
    input_context_digest: Digest
    root_definition_refs: tuple[Ref, ...] = Field(min_length=1)
    definitions: tuple[AnswerDefinition, ...]
    unresolved_definition_refs: tuple[Ref, ...]
    resolved_intent: dict[str, Any]
    result_shape_contract: dict[str, Any] | None
    completeness: Literal['complete', 'partial']
    semantic_equivalence_decided: Literal[False] = False
    context_digest: Digest

    @model_validator(mode='after')
    def closed_projection(self):
        refs = {item.ref for item in self.definitions}
        missing = set(self.unresolved_definition_refs)
        if (len(refs) != len(self.definitions) or refs & missing
                or len(missing) != len(self.unresolved_definition_refs)):
            raise ValueError('ANSWER_MEANING_REFERENCE_CONFLICT')
        required = set(self.root_definition_refs)
        for item in self.definitions:
            required.update(item.dependency_refs)
        if required - refs != missing:
            raise ValueError('ANSWER_MEANING_CLOSURE_INCOMPLETE')
        reachable, pending = set(), list(self.root_definition_refs)
        by_id = {item.ref:item for item in self.definitions}
        while pending:
            ref = pending.pop()
            if ref not in reachable:
                reachable.add(ref)
                if ref in by_id:
                    pending.extend(by_id[ref].dependency_refs)
        if reachable != refs | missing:
            raise ValueError('ANSWER_MEANING_UNRELATED_DEFINITION')
        if self.completeness != ('partial' if missing else 'complete'):
            raise ValueError('ANSWER_MEANING_COMPLETENESS_MISMATCH')
        if self.context_digest != semantic_digest(self.model_dump(mode='json', exclude={'context_digest'})):
            raise ValueError('ANSWER_MEANING_DIGEST_MISMATCH')
        return self


def build_answer_meaning_context(*, entries: Sequence[LoadedProfileEntry], root_refs: Sequence[str],
        input_context_digest: str, resolved_intent: dict, result_shape_contract: dict | None = None):
    """Preserve complete definitions for the used dependency closure.

    Object property inventories remain in the original definition but do not
    force unrelated properties into a result's used closure. Missing dependencies
    are disclosed explicitly; a label is never substituted for a definition.
    """
    by_id = {}
    for entry in entries:
        if entry.category != 'domain':
            raise ValueError('ANSWER_MEANING_DOMAIN_ENTRY_REQUIRED')
        if entry.entry_id in by_id and by_id[entry.entry_id] != entry:
            raise ValueError('ANSWER_MEANING_DEFINITION_CONFLICT')
        by_id[entry.entry_id] = entry
    roots = tuple(sorted(set(root_refs)))
    pending = list(roots)
    visited, missing, definitions = set(), set(), []
    while pending:
        ref = pending.pop(0)
        if ref in visited:
            continue
        visited.add(ref)
        entry = by_id.get(ref)
        if entry is None:
            missing.add(ref)
            continue
        dependencies = _meaning_dependencies(entry)
        definitions.append(AnswerDefinition(ref=ref, revision_id=entry.revision_id,
            revision_digest=entry.revision_digest, definition_digest=semantic_digest(entry.payload),
            logical_definition=entry.payload, evidence_refs=entry.evidence_resources,
            dependency_refs=dependencies))
        pending.extend(dependencies)
    body = dict(contract_version='boi/answer-meaning-context@1', input_context_digest=input_context_digest,
        root_definition_refs=roots,
        definitions=[item.model_dump(mode='json') for item in sorted(definitions, key=lambda item: item.ref)],
        unresolved_definition_refs=sorted(missing), resolved_intent=deepcopy(resolved_intent),
        result_shape_contract=deepcopy(result_shape_contract), completeness='partial' if missing else 'complete',
        semantic_equivalence_decided=False)
    return AnswerMeaningContext.model_validate({**body, 'context_digest': semantic_digest(body)})
