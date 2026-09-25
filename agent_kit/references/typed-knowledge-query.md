# Query published knowledge through exact Profile declarations

Read the connected server's `boi_knowledge_query(operation="schema")`. For supported typed knowledge in a Private, Team or Public space, use this path before older answer adapters. The external host understands the request and selects meaning; Wiki executes the returned logical contract. Availability of a schema or tool does not prove that the user's domain, source population or operation is prepared.

1. Obtain a current `model_input` population using `boi_knowledge_set` and the intended `target_space`. Keep the user's authorized audience; Private is the default. A population handle replaces enumerating all member IDs. It does not grant source access or fact qualification.
2. Use `boi_knowledge_query(operation="discover", request={...})` with that `set_ref`. Search relevant terms or declared role/type/operator and inspect the returned exact component references, roles, cardinality, quantity/unit revisions and object-type links. Preserve the context of equipment, location, time, conditions and uncertainty. Lexical overlap supplies candidates; it does not choose the intended meaning or establish absence. Read the exact authorized native Profile when the declaration alone is insufficient. Follow the returned cursor with unchanged request fields; a changed scope, relevant record or implementation invalidates it.
3. Build the typed logical query from the current schema and selected declarations. Do not invent unit equivalence, sensor identity, physical SQL plans or unsupported operators. Preserve source modality, polarity, hypothetical conditions and supported/refuted/conflicted/unknown states. The discovery top-k is not the object population or the denominator of an exact count.
4. Execute with a stable idempotency key. After an uncertain execution response use `recover` with the identical original request; do not execute a replacement query to retrieve the lost result. Use `summary` and `page` for saved counts and bounded details, and follow exact `knowledge_read` arguments for content and evidence. Current rights and qualification remain necessary on subsequent reads. An invalidated saved result is not silently rerun.
5. Give the user a familiar answer with the relevant source links and material limitations. Separate a source's statement from verified truth. Unprepared coverage, unsupported operations and unknown values must remain visible in the answer when they affect it. A working transport or synthetic fixture is not proof of semantic quality, real-user delivery or latency acceptance.

For a saved statement result, follow a selected row's `witness_read` with `boi_knowledge_query(operation="witnesses")`. These are the exact source contexts and atomic facts evaluated in the original SQL snapshot. `effect` describes atomic support or refutation; `final_support` and `final_refute` separately identify contribution to the full expression. An atomic counterreport can remain visible while an OR branch masks it in the final result. Keep the expression, conditions, exceptions and source scope together. Follow the witness page's `document_read` through `boi_knowledge_read`; its `meaning_pointers` selects the relevant assertion roots and their declared dependencies, and `include_sources` checks current source rights before returning exact fields. Follow `next_cursor` if more witness rows are needed. Unknown objects have no positive witness; old results without recorded witnesses return an explicit error and are never rerun or backfilled automatically. Current result authority, qualifications and source access remain separate checks.

For `query@2` with `claim_basis="reported_statement_exists"`, top-level `polarity` selects positive or explicit negative reports. Each predicate may set `report_polarity` to override that default, so a conjunction can request an explicit negative application report and a positive evaluation report in the same source context. Negative support requires an authored negative assertion of the exact selected value. Missing records, missing preparation and positive assertions of other values never establish such a negative report. An equal positive report is counterevidence within that context. Other contexts cannot refute report existence elsewhere. Keep conflicted witnesses visible; do not describe these queries as complements or proof of actual nonapplication. Predicate overrides are rejected in query@1.

After a policy or checker change, use `boi_knowledge_qualification` schema and status to inspect exact published decisions. A refresh can reuse unchanged, source-bound node judgments. For a statement or relation grant, explicitly submit `statement_reviews` containing the full **current native** unresolved inventory, per-item judgments and exact `existing_source` quotations. Inventory/item digests include native source span references; original importer tokens are not native inventory. Review each relevant classification and preserve unsupported judgments. The server rechecks sources, edit rights, native scope, mechanical checks and current policy. Omitting the new review withholds a previous statement grant. The new review's authenticated provenance is separate from old node opinions; neither declares human approval or independent review. This operation preserves source bytes and published revisions. Recover an uncertain response using the exact original request and status; do not create a replacement request or reopen publication.

## Follow declared source relations

Use `boi_knowledge_query(operation="traverse")` with an exact published `start_revision` and the exact object-predicate components chosen from authorized Profile reads. This bounded read does not need a population handle or create a saved SQL result. Its direction is the authored subject-to-object link. A predicate declaring an earlier or later object retains that meaning; never reverse it from its name or infer immediate adjacency.

Each edge requires its own current `traverse` source-relation qualification. A source-inventory review for `filter` is not a traversal grant. The authoring contract is `boi/source-relation-review@1` under `LocalUseAssessment.statement_review`, with the full original unresolved inventory and complete selected assertion/dependency closure. Reconcile purposes in one explicit assessment per target; retain earlier opinions and provenance separately. Source fidelity/context unknowns remain blockers, and world applicability, physical binding, coverage and independent scientific validation remain limitations rather than certified truths.

The result preserves each qualified edge's source statement, polarity, conditions, exceptions, applicability, time, dependencies and exact source fields. It checks current target identity/type and source/Profile/use rights again before returning. Negative relations are retained without continuing through them. Repeated destinations can be merges; cycles are marked only when a returned positive path closes. Depth boundaries or missing qualifications make the result partial, and an exceeded output/source/time budget withholds the result. Zero qualified edges with `exact_traverse_source_qualification_required` means missing preparation, not that the source reports no relation.

Keep source-local mentions and explanatory contexts separate from global physical process identities. Do not inherit a target's use qualification or conditions, combine path conditions into world applicability, infer a cause, or treat a permitted source report as actual equipment execution. Use the returned source statement for an explicitly recorded reason and keep the declared direction and scope in the answer.

## Restore missing Profile indexes

When the server reports missing or inconsistent Profile preparation, an authorized editor can use `repair_profiles`. Identify exact relevant published Profile revisions from already authorized knowledge or the scoped `boi_knowledge_catalog(target_space=..., kind="profile")`. Keep following `next_cursor` if needed: the current catalog may return an empty filtered page with another page available. This is bounded maintenance discovery, not an everyday full-corpus semantic search.

Submit only `targets` and a stable `idempotency_key` using the current repair schema. The server reads native Profile content, checks current edit and model-input access, and reconstructs its declared component index. It preserves the original content revision, sharing policy and use decisions. It records previous metadata and derived rows, fences concurrent changes, and does not accept a caller-supplied replacement schema, `passed` flag, SQL or ACL. Repair of an unsupported legacy schema requires the relevant migration or authoring workflow; this operation does not reinterpret it.

If a repair response is uncertain, resend the identical repair request and key to recover the existing receipt. Do not switch target revisions under that key or infer success from a stored request alone. A changed repair increments affected space epochs, so obtain a new current population handle afterward. Unchanged repairs preserve existing handles. Neither repair nor a receipt establishes semantic correctness, broader sharing, fact qualification or source permission.


## Search candidates, correction and safe recovery (kit 0.2.34)

`boi_search` now returns `boi/scoped-search@1`. With default `scope=all`, there is deliberately no top-level `items`: read `result_groups` and their linked lists under `discovery`. Absence of that field is not zero matches. The repository index, current owned provisional assets and current Private published documents have different populations and rights; their ranks must not be compared or summed. Already returned group candidates can be inspected without another search. Use explicit `scope=indexed|owned_native|published` only when that collection fits the request; its `items` preserve the backend order, while other collections are not searched. Do not choose a fixed scope or the first group for every question.

Use descriptions to find the requested target and role, then the group's declared reader. For published candidates use `boi_knowledge_read(view=document)` and request original fields with `document_options.include_sources=true` when needed. For owned native assets prefer the matching `available_user_views` reader; kind=definition alone does not imply that the native meaning-index reader is authorized. Do not retry denied views automatically or broaden rights. Read conditions, direction, exclusions, source scope and declared neighboring dependencies before settling entity identity or final claims. A whole source field with several roles must not be flattened into one relation.

Keep the original question, including its language, as the answer request. A foreign-language description can be matched by the host against descriptions in accessible material without a translated identity or a preselected ID. If it still fails, use the existing bounded description-language recovery path; record the actual candidate wording and never turn it into an approved alias. No term tables or expected source IDs belong in code or guidance. Stop exploring when enough evidence is read. A top-k prefix is incomplete; the original bounded group and cursor remain available. For published continuation preserve `text_match_mode=ranked_candidates`; default all_terms is literal conjunction. Broad matching does not equate targets, roles or aliases.

A successful scoped search with zero matches permits “확인한 범위에서는 근거를 찾지 못했습니다.” An unavailable, failed or unprepared channel instead means “검색 경로 일부를 사용할 수 없어 확인 범위가 제한됩니다.” Answer the supported part with its source, and explain only the material remaining gap. Never convert either case into “그런 사실이 없습니다.” `semantic_search_unavailable` leaves authorized lexical search and reviewed concept discovery available; it does not permit inventing synonyms or silently enabling another model/provider.

For corrected sources, read the current head and `is_current_revision` plus current source access. Historical citations and saved answers remain history. Do not silently substitute a new revision in an old protected result. If rights, policy, preparation or revision invalidate a cursor/result, start a distinct authorized current read; preserve the failed read and do not call it replay success. Compare the actual corrected relation, condition, modality and scope with each final claim. Preserve supported answer parts while narrowing the affected claim. Source-reported operation is not a requirement; evaluation is not application; local conditions are not universal.

The portable MCP helper now retains a bounded `recovery` field for recognized authorized concept conflicts. Unknown spelling requires finding reviewed spelling or clarifying meaning; role/source-scope mismatch requires inspecting the requested relationship and evidence scope. Neither allows automatic alias/role substitution or repeated identical requests. Use the ordinary-language explanation for the user and keep HTTP/internal codes in the operational record. Server-supplied free text and candidate lists are not copied into recovery. Authorization failures do not reveal concept existence.


### Final explanation and citation consumption

The default grouped search and an explicitly selected scope are different output shapes. Legacy arguments remain accepted, but a client requiring top-level items for the default call must migrate; do not silently treat the missing field as empty. Explicit-scope items are a display prefix: inspect the already returned bounded discovery list before issuing another query. Neither view improves lexical rank or establishes the chosen meaning.

On published document reads with original fields, citation_presentation provides document titles, source locations and short reference labels. Use the exact reference URL next to supported claims and name the document/location once nearby. A concise paragraph can share one citation only if that exact evidence supports every claim. Preserve separate references for different evidence or revisions; renumber local labels when combining documents. Keep the original binding indices/claim correspondence in the work record. Never merge references merely because their titles match. Do not repeat unrelated source details just to add citations.

Compare the final text with the original question and complete relevant source fields: target, relation direction, conditions, negation, time and uncertain spelling. Supported source descriptions are not evidence of present operation. Reading or binding creates no semantic review. response_check/apply_response_repair belong to the existing process response review runner; ordinary boi_search/boi_knowledge_read and native composition do not execute them automatically. Record the actual review path used rather than claiming these helpers ran. Use the existing final-message source review when that host path is configured; preserve failed output and repair only unsupported or unclear parts. Do not send Private sources to an unapproved provider to obtain a review.

A published document's read permission does not imply native composition permission. Respect a denied preparation, preserve its failure, and do not retry it or substitute a different authority. Already authorized evidence may still support a direct, source-scoped explanation without claiming a stored or reviewed answer. Only report actual execution/binding if its protected result exists.

Human link acceptance requires the logged-in user's browser to open the exact source revision/location and return to the conversation. Configured localhost origins, HTTP responses and developer-browser PAT probes do not establish that acceptance. Leave user access and first-useful/final-display timing unobserved until that host is observable.

### Preserve explicit retrieval expressions and Published explanation authority (kit 0.2.35)

Discover the connected tool schema before using an optional field. Where `boi_search` supports `search_expression`, retain the user's original text in `query` and supply the host-authored retrieval description separately. The expression replaces retrieval text for each selected collection; it does not add another pool or create a cross-collection winner. Preserve names, units, numbers, negation, order, modality and scope. Returned `retrieval_query` and `query_expression` expose caller provenance with `equivalence_verified=false`; they are not verified translation, identity or aliases. Scope selection and continuation must retain this original-question provenance. If the field is unavailable, record the original question and explicit retrieval text separately in the existing host work record; do not silently drop the original question or invent a successful call.

Inspect the actual per-channel retrieval diagnostics. An enabled embedding provider, a Native flag, or a vector result in the repository channel does not establish semantic coverage of Published documents. Keep channel populations and lexical/semantic methods separate. A similarity score and a first-ranked candidate still require source comparison of the requested subject, role and conditions. Do not discard constraints to improve rank or generalize a selected small sample into full-population quality.

For `boi_native_answer` composition, discover its current schema. When it exposes `published_meaning_uses`, provide the exact revision and actual current **explain** qualification reference read from the selected Published document. Provide selected assertion references through `meaning_selection` and preserve their conditions/dependency closure. Never cast a filter qualification or a Native review reference into explain permission. A source-only supplement stays `source_definition_revisions` and supplies original quotations only. If no usable explain qualification is available, retain that limitation; source-reading permission does not create one.

Keep the preparation result's context/preparation references with the original answer question. Submit the host-authored draft through the supported binding contract, then read the actual final result with current authority. Preparation, nonzero context assets and qualification availability alone do not establish meaning consumption: inspect the final sentence/facet references, exact source bindings, conditions and qualification provenance. A source-only answer must not be labelled meaning reuse. Match each rendered citation to the source document that owns its fields, even when several records share one source revision.

An `interpretation` label does not establish applicability across records. A shared file, common method or two individually supported clauses cannot supply a missing connecting relation. Keep valid independent record descriptions and supported synthesis; leave an unsupported transfer unconfirmed. The question itself and its request facets are not evidence. Compare literal uncertain spellings with the original source instead of normalizing them into another material or condition.

This installed kit ships the official transport, shared guidance and local authoring contracts. It does **not** ship or run the repository's Python response-review/repair/model host helpers. Direct MCP discovery, reads and final binding remain available subject to server contracts, but do not claim automatic review merely because those operations succeeded. A configured supported host review adapter must be observed separately. Preserve exhausted inference budgets and failed/unknown review attempts; installation or a new directory does not admit another review.

## Source-declared comparisons and source-object counts (query@3)

Read the current query schema before selecting a version. Query@1 and query@2
retain their original semantics. Query@3 keeps `reported_statement_exists` and
adds `lt`, `lte`, `gt`, and `gte` for positive source-reported decimal values in
an exact Profile quantity/unit. No implicit unit conversion, live measurement,
world-condition proof, or negative interval inference is supplied.

Use `operation=count_reported_objects` with
`count_grain=source_object_identity` to count distinct source objects in the
saved set snapshot. Multiple witnesses for one stable object do not increase
its count. Report supported/conflicted/unknown separately; the existence count
is supported plus conflicted. Do not describe source-object counts as physical
process/equipment counts without an independently established identity model.
Use summary for this operation; it intentionally has no object page. Sum and
average are not part of this extension.

Incoming one-hop relation lookup can use `select_objects` over the full subject
population with the exact object-valued predicate `eq` the discovered target
identity. This returns the original source subject and authored predicate/value;
do not reverse the triple or drop its conditions. Read saved witnesses and source
fields. Filter report lookup and traversing a target still require their own
current use qualifications. Reverse multi-hop traversal is not provided by this
query extension.

The optional repository-development callback host is
`agent_kit/python/boi_ontology_query_host.py`. The caller supplies the model and
single-dispatch MCP transport. It contains no Wiki-side model, maintenance
permission, or question-specific answer route. Its final pointers prove that
references resolve in recorded tool results, not semantic support. The O_TYPED
harness remains experimental: document-only output, failed saved execution,
missing preparation, and final delivery failure must remain distinct. Do not
infer readiness from its Python tests or a successfully returned MCP envelope.
# Source modality queries (query contract v4)

`boi/knowledge-evidence-query@4` selects exact source reports by `modality`:
`asserted`, `possible`, `intended`, or `required`. For example, an intended
process purpose remains intended; it never becomes an observed process outcome.
Non-asserted reports need a current `boi/source-statement-review@2` qualification
covering their complete source-bound nodes and unresolved inventory.

Non-asserted modalities support equality and distinct reported-object counts.
Their different possible/intended values do not refute each other merely because
a Profile property has cardinality one. Explicit opposite-polarity reports of
the same value within the same exact context remain visible as conflicts.
Conditions, exceptions and applicability are returned with witnesses; their
real-world satisfaction is not evaluated. Numeric ranges remain supported only
for asserted source scalars in exact Profile quantity/unit definitions.

A query uses one exact modality. Separate queries for different modalities must
retain separate witnesses; do not infer a shared condition or physical outcome
from matching identities. Version 1–3 meanings remain unchanged, including the
asserted-only source-statement constraint in versions 2–3.

For local authoring, `review_validation: "strict"` requests exact review inventory,
source-closure and quotation checks before an assembly is written. The existing
default report mode remains available to inspect incomplete drafts and obtain
their exact review inventories. Neither mode grants server qualification.
