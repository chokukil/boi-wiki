"""Bounded NInfer client for logical-only Pi IntentCandidate synthesis."""

from __future__ import annotations

import hashlib
import json
from threading import Lock
from typing import Any, Callable
from urllib import request

from .local_model_routing import LocalModelRunIdentity
from .semantic_intent import (
    IntentCandidate,
    IntentModelInput,
    IntentModelOutputError,
)


JsonTransport = Callable[[str, str, dict[str, Any] | None, float], dict[str, Any]]


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _default_transport(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode()
    call = request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(call, timeout=timeout) as response:  # noqa: S310
        decoded = json.loads(response.read().decode())
    if not isinstance(decoded, dict):
        raise ValueError("LOCAL_MODEL_RESPONSE_NOT_OBJECT")
    return decoded


class NinferIntentClient:
    """OpenAI-compatible tool-call adapter with no SQL or DB-name authority."""

    ROLE = (
        "You are a logical analytics intent parser. Use only entry_id values in "
        "the supplied logical context. Do not invent identifiers, defaults, joins, "
        "database names, or executable text. If meaning is missing, list it under "
        "unresolved_terms. Always call submit_intent exactly once, including when "
        "the question is ambiguous or unanswerable. Encode clarification alternatives "
        "or unresolved terms in the tool arguments; never answer or ask in prose. "
        "Submit exactly one closed intent object."
    )
    PROMPT_CONTRACT = (
        "Map explicit entities, properties, filters, aggregation, grain, time "
        "boundaries, ordering, and limit from the question. Preserve every stated "
        "value. Use ambiguity_alternatives only when alternatives can change the "
        "result. Ignore qnonce_* request audit tokens. For entity-row projection, "
        "use only the primary entity identity property as both dimension and grain; "
        "joined labels are projected properties, not dimensions, unless explicitly "
        "grouped. property_ids contains non-aggregated output properties only; do not "
        "add fields used only for filter, time, order, latest, or aggregation. For "
        "limit, preserve an explicit user value; when absent, emit the bounded "
        "exploratory policy default 100. "
        "grouped aggregation, use the grouping property as both dimension and grain "
        "and leave property_ids empty because dimensions are emitted separately. "
        "For projection without aggregation, and for latest row selection, repeat "
        "every projected dimension in property_ids at its explicit question-order "
        "position; dimension/grain membership does not remove an output property. "
        "Include every entity explicitly requested as part of the result in entity_ids; "
        "a path-only relationship mention is governed by the relation contract. latest "
        "is a row-selection window: its aggregation target_id is the timestamp/date "
        "property that defines recency, while property_ids still contains every "
        "explicitly requested output property including the identity. "
        "metric_ids contains only context entries whose kind is Metric, never a "
        "PropertyDefinition. Represent entity count as operator count targeting its "
        "ObjectType with distinct false and empty property_ids, dimensions, and grain; "
        "the deterministic planner applies distinct identity. Represent distinct "
        "property count as distinct_count targeting the PropertyDefinition with "
        "distinct true. Operators are projection, eq, in, range comparisons, count, "
        "distinct_count, average, latest, ordering, and limit. For latest, emit the "
        "time property DESC first and the scoped object identity ASC second, and use "
        "that identity as grain and dimension. For linked or nested results, the root "
        "is the object named by each or for each; keep its identity as grain and "
        "dimension while child identities remain projected properties. A foreign key "
        "or relationship key used only to connect two requested objects is not an "
        "output property unless the question explicitly asks to display that key. "
        "For many-to-many endpoint lists, include the root and target ObjectTypes; a "
        "bridge or relationship mentioned only as through or via is path metadata, not "
        "a result entity. Include a bridge ObjectType or its identity only when the "
        "question explicitly asks for relationship records or relationship IDs. entity_ids "
        "contains ObjectType entries only; never include a RelationType, "
        "PropertyDefinition, Term, or ValueType there. unresolved_terms contains "
        "only a requested domain noun phrase that has no matching logical entry; do "
        "not list control words such as approved, active Release, each, collection, "
        "relationship object, or audit request. Polite framing and request-purpose "
        "discourse such as review, audit, planning, analysis, reporting, follow-up, "
        "briefly, or clearly never creates an entity, filter, value, or unresolved "
        "term. Project every field explicitly requested for display even when it is "
        "also used for ordering. In ambiguity_alternatives include only the competing "
        "semantic ObjectType or PropertyDefinition IDs; do not add RelationType IDs "
        "that merely connect those alternatives."
        " For an explicit null predicate use operator is_null with value null; never "
        "use eq with null. An inclusive numeric range is two filters on the same "
        "property, gte for the lower bound and lte for the upper bound; never emit "
        "a range operator. If the question explicitly says UTC, emit UTC and include "
        "an explicit Z or +00:00 offset on both time boundaries. For a child filter, "
        "COLLECTION_CONTENT means keep all "
        "roots and filter only returned children; ROOT_EXISTENCE means restrict "
        "roots by matching children while preserving each selected root's full "
        "child collection; ROOT_AND_COLLECTION means restrict both roots and the "
        "returned children. Follow those phrases exactly because they change results."
    )
    MAX_INPUT_BYTES = 11_264

    _SCHEMA: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "entity_ids": {"type": "array", "items": {"type": "string"}},
            "property_ids": {"type": "array", "items": {"type": "string"}},
            "metric_ids": {"type": "array", "items": {"type": "string"}},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "property_id": {"type": "string"},
                        "operator": {
                            "type": "string",
                            "enum": [
                                "eq", "ne", "gt", "gte", "lt", "lte", "in",
                                "is_null", "is_not_null",
                            ],
                        },
                        "value": {},
                        "unit_ref": {"type": ["string", "null"]},
                        "scope": {
                            "type": ["string", "null"],
                            "enum": [
                                "COLLECTION_CONTENT", "COLLECTION",
                                "ROOT_EXISTENCE", "ROOT_AND_COLLECTION", None,
                            ],
                        },
                    },
                    "required": ["property_id", "operator", "value"],
                },
            },
            "aggregations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operator": {"type": "string"},
                        "target_id": {"type": "string"},
                        "distinct": {"type": "boolean"},
                        "scope_object_id": {"type": ["string", "null"]},
                        "partition_by": {
                            "type": "array", "items": {"type": "string"},
                        },
                    },
                    "required": ["operator", "target_id", "distinct"],
                },
            },
            "grain": {"type": "array", "items": {"type": "string"}},
            "time_range": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "property_id": {"type": "string"},
                            "start": {"type": "string"},
                            "end": {"type": "string"},
                            "timezone": {"type": ["string", "null"]},
                            "start_inclusive": {"type": ["boolean", "null"]},
                            "end_inclusive": {"type": ["boolean", "null"]},
                        },
                        "required": [
                            "property_id",
                            "start",
                            "end",
                            "timezone",
                            "start_inclusive",
                            "end_inclusive",
                        ],
                    },
                ],
            },
            "ordering": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "property_id": {"type": "string"},
                        "direction": {"type": "string", "enum": ["ASC", "DESC"]},
                    },
                    "required": ["property_id", "direction"],
                },
            },
            "limit": {"type": "integer", "minimum": 1},
            "unresolved_terms": {"type": "array", "items": {"type": "string"}},
            "ambiguity_alternatives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "logical_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["label", "logical_ids"],
                },
            },
        },
        "required": [
            "entity_ids",
            "property_ids",
            "metric_ids",
            "dimensions",
            "filters",
            "aggregations",
            "grain",
            "time_range",
            "ordering",
            "limit",
            "unresolved_terms",
            "ambiguity_alternatives",
        ],
    }

    def __init__(
        self,
        *,
        base_url: str,
        model_id: str,
        model_digest: str,
        timeout_seconds: float = 60.0,
        transport: JsonTransport | None = None,
        input_encoding: str = "full-v1",
        inference_policy: str = "thinking-low-v1",
        intent_contract: str = "typed-intent-v1",
        meaning_policy: str = "legacy-v1",
        transport_receipt_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if input_encoding not in {"full-v1", "logical-compact-v2", "logical-compact-v3", "logical-table-v4", "logical-table-v5", "logical-symbols-v6", "logical-symbols-v7"}:
            raise ValueError("PI_INPUT_ENCODING_UNSUPPORTED")
        self.input_encoding = input_encoding
        self.transport_receipt_sink = transport_receipt_sink
        if meaning_policy not in {'legacy-v1', 'query-meaning-v2', 'query-meaning-v3'}:
            raise ValueError('PI_MEANING_POLICY_UNSUPPORTED')
        self.meaning_policy = meaning_policy
        if meaning_policy in {'query-meaning-v2', 'query-meaning-v3'}:
            from .intent_meaning_policy import MEANING_V2
            self.PROMPT_CONTRACT = MEANING_V2
        if meaning_policy == 'query-meaning-v3':
            from .intent_meaning_policy import QUALIFIER_V3
            self.PROMPT_CONTRACT = QUALIFIER_V3 + self.PROMPT_CONTRACT
        if intent_contract not in {"typed-intent-v1", "quality-intent-v2", "scoped-aggregate-v3", "scoped-result-intent-v4"}:
            raise ValueError("PI_INTENT_CONTRACT_UNSUPPORTED")
        self.intent_contract = intent_contract
        if intent_contract in {"quality-intent-v2", "scoped-aggregate-v3", "scoped-result-intent-v4"}:
            from copy import deepcopy
            self._SCHEMA = deepcopy(type(self)._SCHEMA)
            self._SCHEMA['properties'].update({
                'intent_contract_version': {'type':'string','enum':[intent_contract]},
                'quality_requests': {'type':'array','maxItems':4,'items':{
                    'type':'object','additionalProperties':False,
                    'properties':{
                        'subject_object_id':{'type':'string'},
                        'relationship_id':{'type':['string','null']},
                        'detail':{'type':'string','enum':['SUMMARY','ROWS']},
                        'measures':{'type':'array','minItems':1,'maxItems':7,'items':{'type':'string','enum':[
                            'matched','unmatched','null_fk','orphan','duplicate_key','excluded','coverage']}}},
                    'required':['subject_object_id','relationship_id','detail','measures']}}})
            self._SCHEMA['required'].extend(['intent_contract_version','quality_requests'])
            self.PROMPT_CONTRACT = self.PROMPT_CONTRACT + (
                '\nIntent contract quality-intent-v2: explicitly represent requested data-quality '
                'disclosure in quality_requests, separate from row filters and projection. SUMMARY '
                'requests audited matched/unmatched/null-FK/orphan/duplicate/excluded/coverage figures; '
                'ROWS requests actual quality-affected record values and is not the same answer. '
                'Use the subject ObjectType and a known RelationType or null if its relationship is unambiguous. '
                'A known object qualified by missing linkage is not an unknown domain object. '
                'The deterministic service checks approved relationship policy and evidence; never invent '
                'a count, choose an orphan policy, or rewrite the request. If summary versus rows materially '
                'remains ambiguous, use one precise ambiguity alternative. Unrelated quality_requests is [].')
        if intent_contract == 'scoped-aggregate-v3':
            self._SCHEMA['properties']['aggregations']['items']['properties']['group_by'] = {
                'type':'array','items':{'type':'string'},
                'description':'Reducer grouping property IDs, equal to dimensions/grain; not latest partition.'}
            self.PROMPT_CONTRACT += (
                '\nUse intent_contract_version scoped-aggregate-v3. For non-latest reducers, '
                'scope_object_id is the counted/measured ObjectType and group_by is the requested '
                'grouping, repeated exactly in dimensions and grain. partition_by must be empty '
                'for reducers; it belongs only to latest. Keep grouping root display attributes '
                'in property_ids. Aggregation-only child objects are dependencies, not requested '
                'raw collections: leave them out of entity_ids unless their records are requested. '
                'A latest item must have empty group_by; its partition_by remains the business window.')
        if intent_contract == 'scoped-result-intent-v4':
            from .intent_meaning_policy import MEANING_V4_MEMBERSHIP
            self._SCHEMA['properties']['aggregations']['items']['properties']['group_by'] = {
                'type': 'array', 'items': {'type': 'string'},
                'description': 'Reducer grouping, equal to dimensions/grain; empty for latest.'}
            self._SCHEMA['properties']['rowset_object_ids'] = {
                'type': 'array', 'minItems': 1, 'uniqueItems': True,
                'items': {'type': 'string'},
                'description': 'ObjectTypes whose individual records are requested, excluding aggregation-only subjects.'}
            self._SCHEMA['required'].append('rowset_object_ids')
            self.PROMPT_CONTRACT += MEANING_V4_MEMBERSHIP
        if input_encoding == 'logical-table-v4':
            self.PROMPT_CONTRACT += (
                '\nLogical context table encoding: each group supplies kind and common_payload '
                'for every entry. Each row is [original order, entry_id, payload column values, '
                'metadata column values] using the declared column order. Merge common_payload '
                'with row payload values to read the complete logical entry. IDs are unchanged. '
                'Metadata is provenance, not question semantics. All names, definitions, units '
                'and ownership are retained; select useful requested attributes from this inventory.')
        if input_encoding in {'logical-table-v5','logical-symbols-v6','logical-symbols-v7'}:
            self.PROMPT_CONTRACT += (
                '\nLogical context table v2: every row has an explicit entry_id and values '
                'in payload_columns order. Merge common_payload and row values; kind applies '
                'to all entries in the group. Copy entry_id verbatim. original_positions are '
                'serialization order only, never part of any identifier. Every ID, definition, '
                'unit and ownership is preserved. metadata is provenance, not query meaning.')
        if input_encoding in {'logical-symbols-v6','logical-symbols-v7'}:
            self.PROMPT_CONTRACT += (
                '\nLogical references use the exact local symbols L1, L2, etc from entry_id. '
                'Use only these symbols in typed reference positions. They are reversible '
                'transport identifiers, not names or data values. Do not invent or expand IDs. '
                'Preserve filter literal values and descriptions verbatim.')
        if input_encoding == 'logical-symbols-v7':
            if intent_contract == 'typed-intent-v1':
                raise ValueError('DECLARED_VERSION_ENVELOPE_REQUIRES_VERSIONED_INTENT')
            self._SCHEMA['required'].remove('intent_contract_version')
            self.PROMPT_CONTRACT += (
                '\nThe selected tool contract supplies intent_contract_version in its server-owned '
                'envelope. You may omit that metadata field; if supplied it must exactly equal '
                'the declared version. All semantic fields remain required. The envelope does not '
                'fill filters, entities, rowsets, grain, scope, or unresolved meaning.')
        if inference_policy not in {"thinking-low-v1", "nonthinking-v1"}:
            raise ValueError("PI_INFERENCE_POLICY_UNSUPPORTED")
        self.inference_policy = inference_policy
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.model_digest = model_digest
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport
        self._observation_lock = Lock()
        self._observed_input_sizes: list[int] = []

    @property
    def observed_input_sizes(self) -> tuple[int, ...]:
        with self._observation_lock:
            return tuple(self._observed_input_sizes)

    def probe_identity(self) -> LocalModelRunIdentity:
        healthy = False
        try:
            response = self.transport(
                "GET", f"{self.base_url}/models", None, self.timeout_seconds
            )
            data = response.get("data")
            healthy = isinstance(data, list) and any(
                isinstance(item, dict) and item.get("id") == self.model_id
                for item in data
            )
        except Exception:
            healthy = False
        return LocalModelRunIdentity(
            healthy=healthy,
            model_id=f"ninfer-local/{self.model_id}",
            model_digest=self.model_digest,
            role_digest=_sha256_text(self.ROLE),
            prompt_digest=_sha256_text(self.PROMPT_CONTRACT + (
                "\ninput_encoding=" + self.input_encoding if self.input_encoding != "full-v1" else ""
            ) + (
                "\ninference_policy=nonthinking-v1" if self.inference_policy != "thinking-low-v1" else ""
            )),
        )

    def encode_input(self, model_input: IntentModelInput) -> bytes:
        if self.input_encoding == "full-v1":
            return model_input.model_dump_json().encode()
        value = model_input.model_dump(mode="json")
        for entry in value["logical_context"]:
            # Remove only empty transport fields and provably redundant identity.
            # Names, definitions, ownership, units and every meaningful value stay.
            for key in ("revision_digest", "evidence_resources"):
                if not entry.get(key):
                    entry.pop(key, None)
            payload = entry["logical_payload"]
            for key, duplicate in (("id", entry["entry_id"]), ("kind", entry["kind"])):
                if payload.get(key) == duplicate:
                    payload.pop(key)
            if payload.get("aliases") == []:
                payload.pop("aliases")
        if self.input_encoding in {'logical-compact-v3', 'logical-table-v4', 'logical-table-v5', 'logical-symbols-v6', 'logical-symbols-v7'} and 'clarification_context' in value:
            # The immutable ledger binds all alternatives and transport digests.
            # Pi needs the selected meaning, not the rejected options or duplicate
            # original question. No chosen field, value or scope is rewritten.
            context = value['clarification_context']
            if context['original_question'] != value['question']:
                raise ValueError('CLARIFICATION_QUESTION_MISMATCH')
            selected = dict(context['selected_alternative'])
            selected.pop('option_id', None)
            value['clarification_context'] = {
                'selected_alternative': selected,
                'remaining_clarifications': context['remaining_clarifications'],
            }
        if self.input_encoding in {'logical-symbols-v6','logical-symbols-v7'}:
            from .logical_symbol_codec import encode_context, symbol_table
            value = encode_context(value, symbol_table(model_input))
        if self.input_encoding in {'logical-table-v4', 'logical-table-v5', 'logical-symbols-v6','logical-symbols-v7'}:
            from .logical_context_table import pack_context, unpack_context
            packed = pack_context(value['logical_context'], named_ids=self.input_encoding != 'logical-table-v4')
            if unpack_context(packed) != value['logical_context']:
                raise ValueError('PI_LOGICAL_CONTEXT_ROUNDTRIP_FAILED')
            value['logical_context'] = packed
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()

    def __call__(self, model_input: IntentModelInput) -> dict[str, Any]:
        if self.input_encoding in {'logical-symbols-v6','logical-symbols-v7'} and self.transport_receipt_sink is None:
            raise ValueError('LOGICAL_SYMBOL_RECEIPT_SINK_REQUIRED')
        encoded_input = self.encode_input(model_input)
        if len(encoded_input) > self.MAX_INPUT_BYTES:
            raise ValueError("PI_SERIALIZED_INPUT_BYTE_LIMIT")
        with self._observation_lock:
            self._observed_input_sizes.append(len(encoded_input))
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": f"{self.ROLE}\n\n{self.PROMPT_CONTRACT}"},
                {"role": "user", "content": encoded_input.decode()},
            ],
            "reasoning_effort": "low",
            "max_tokens": 4096,
            "temperature": 0,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "submit_intent",
                        "description": "Submit the closed logical analytics intent.",
                        "parameters": self._SCHEMA,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "submit_intent"}},
        }
        if self.inference_policy == "nonthinking-v1":
            payload.update(reasoning_effort="none", enable_thinking=False)
        response = self.transport(
            "POST",
            f"{self.base_url}/chat/completions",
            payload,
            self.timeout_seconds,
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise IntentModelOutputError("LOCAL_MODEL_SINGLE_CHOICE_REQUIRED")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(calls, list) or len(calls) != 1:
            raise IntentModelOutputError("LOCAL_MODEL_TOOL_CALL_REQUIRED")
        function = calls[0].get("function") if isinstance(calls[0], dict) else None
        if not isinstance(function, dict) or function.get("name") != "submit_intent":
            raise IntentModelOutputError("LOCAL_MODEL_TOOL_CALL_REQUIRED")
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            raise IntentModelOutputError("LOCAL_MODEL_TOOL_ARGUMENTS_INVALID")
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise IntentModelOutputError(
                "LOCAL_MODEL_TOOL_ARGUMENTS_INVALID"
            ) from error
        if not isinstance(decoded, dict):
            raise IntentModelOutputError("LOCAL_MODEL_TOOL_ARGUMENTS_INVALID")
        if self.input_encoding == 'logical-symbols-v7':
            from .logical_symbol_codec import bind_declared_version, digest
            try:
                decoded, envelope = bind_declared_version(decoded, self.intent_contract)
            except ValueError as error:
                self.transport_receipt_sink({'contract':'boi/declared-intent-envelope@1',
                    'status':'REJECTED','raw_candidate':decoded,'reason':str(error)})
                raise IntentModelOutputError(str(error)) from error
            self.transport_receipt_sink({**envelope,'input_digest':digest(model_input.model_dump(mode='json')),
                                         'wire_digest':_sha256_text(encoded_input.decode())})
        if self.input_encoding in {'logical-symbols-v6','logical-symbols-v7'}:
            from .logical_symbol_codec import symbol_table, decode_candidate, digest
            table = symbol_table(model_input)
            raw = decoded
            try:
                decoded = decode_candidate(raw, table)
            except (ValueError, KeyError, TypeError) as error:
                self.transport_receipt_sink({'contract':'boi/logical-symbol-transport@1',
                    'status':'REJECTED', 'input_digest':digest(model_input.model_dump(mode='json')),
                    'wire_digest':_sha256_text(encoded_input.decode()), 'symbol_table':table,
                    'raw_output':raw, 'reason':'LOCAL_MODEL_UNKNOWN_LOGICAL_SYMBOL'})
                raise IntentModelOutputError('LOCAL_MODEL_UNKNOWN_LOGICAL_SYMBOL') from error
            self.transport_receipt_sink({'contract':'boi/logical-symbol-transport@1',
                'status':'DECODED_NOT_VALIDATED', 'input_digest':digest(model_input.model_dump(mode='json')),
                'wire_digest':_sha256_text(encoded_input.decode()), 'symbol_table':table,
                'raw_output':raw, 'decoded_candidate_digest':digest(decoded),
                'meaning_change':False})
        if isinstance(decoded.get("time_range"), str) and decoded["time_range"].strip().casefold() in {
            "", "none", "null",
        }:
            decoded["time_range"] = None
        for aggregation in decoded.get("aggregations") or ():
            if isinstance(aggregation, dict) and aggregation.get("partition_by") is None:
                aggregation["partition_by"] = []
        try:
            candidate = IntentCandidate.model_validate(decoded)
        except ValueError as error:
            raise IntentModelOutputError(
                "LOCAL_MODEL_TOOL_ARGUMENTS_INVALID"
            ) from error
        if self.intent_contract != 'typed-intent-v1' and candidate.intent_contract_version != self.intent_contract:
            raise IntentModelOutputError('LOCAL_MODEL_INTENT_REVISION_MISMATCH')
        projection_like = not candidate.aggregations or all(
            item.operator == "latest" for item in candidate.aggregations
        )
        execution_candidate = not candidate.unresolved_terms and not candidate.ambiguity_alternatives
        if execution_candidate and projection_like and not set(candidate.dimensions) <= set(
            candidate.property_ids
        ):
            raise IntentModelOutputError("LOCAL_MODEL_NON_CANONICAL_PROJECTION")
        return decoded
