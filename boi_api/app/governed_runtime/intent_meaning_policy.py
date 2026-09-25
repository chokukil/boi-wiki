"""Versioned, domain-neutral NL interpretation policy. No examples or oracle."""

MEANING_V2 = """Read the original question and the authorized logical context. Submit one
typed logical intent using only context identifiers. Do not generate SQL, physical
names, data values, mappings, policy, approval, attestation or a prose answer.

Preserve the user's requested meaning, not just an executable subset. entity_ids
contains the requested ObjectTypes, root first. A path-only or bridge object is
not a result entity unless its records are requested. RelationType IDs describe
paths, never entities. metric_ids contains only actual Metric entries.

Separate displayed attributes from transport identity and grain. property_ids
lists the logical attributes that answer the request. Requests for details,
settings, records or history mean the relevant descriptive/value attributes, not
merely their identifiers. Use the logical names and definitions to choose them;
include the attribute that identifies what a value describes and its unit when
available. Do not substitute a list of IDs for requested content. Do not add
unrelated audit metadata or filters. If the desired contents are materially
ambiguous, propose one clear choice of available logical attributes. If the
question explicitly asks only for identifiers, project only those identifiers.
Explicitly named display fields must remain projected even when also used for
order, filtering or grouping. Fields used only for connecting objects are
transport dependencies, not additional user display requirements.

For a single-object projection use its declared logical grain, not every displayed
attribute. For nested/linked results, grain and dimensions identify the root
object only; child identities are separate row identities and never a Cartesian
root grain. Keep siblings as separate collections. For aggregates use the
requested grouping dimensions/grain. Aggregated values do not also belong in
property_ids. count of an entity targets its ObjectType; distinct_count of a
property targets that PropertyDefinition. Scope each child aggregation explicitly.

latest is a row-selection window, not a maximum value or identity projection.
Its target_id is the recency property, scope_object_id the versioned object, and
partition_by the business grouping asked for. Business groups can have multiple
event/version identities. Project the requested value fields. Do not partition
by a unique event ID merely to satisfy a type check. Recency and tie-break order
must be supported by the question or logical contracts; if ambiguous, ask a
single choice instead of inventing a time field. Keep identity grain distinct
from latest business partitions.

Only add filters actually requested. A value is applied to the property whose
logical meaning it qualifies, not the first nearby identifier. Use eq/ne/gt/gte/
lt/lte/in/is_null/is_not_null; null tests have value null. Inclusive ranges use
gte and lte. For child filters COLLECTION_CONTENT retains roots and filters
children; ROOT_EXISTENCE filters roots and retains their full child collections;
ROOT_AND_COLLECTION restricts both. Keep these meanings distinct. Preserve exact
time boundaries, inclusivity and timezone; explicit UTC uses an offset. Ordering
has property_id and ASC/DESC. Preserve explicit limit; absent limit is policy 100.

unresolved_terms contains only requested domain concepts absent from the logical
context, not polite phrasing or generic control words. ambiguity_alternatives
contains readable choices with competing ObjectType/PropertyDefinition logical_ids,
not path RelationType IDs. On a bound clarification follow the selected meaning
without changing the original question; do not request another clarification.
Never treat confidence, counts or schema-valid JSON as proof of correctness.
"""

MEANING_V4_MEMBERSHIP = """
Use scoped-result-intent-v4. This revision replaces the earlier entity-list
membership rule: entity_ids lists referenced ObjectTypes, root first, whereas
rowset_object_ids explicitly lists only ObjectTypes whose individual records are
requested as root rows or child collections. Both use context ObjectType IDs.
Every rowset object must also be in entity_ids. A referenced aggregation subject
does not imply its raw collection is requested. A request for grouped counts
asks for grouping root rows and an aggregate, not the counted records as well.
Include child rowsets only when their actual individual records are requested.
property_ids contains display fields from requested rowsets, not aggregate input
fields or internal transport keys. The service supplies transport identity.
Keep the grouping root in rowset_object_ids and use its display attributes.
For non-latest reducers scope_object_id is the counted/measured ObjectType;
group_by exactly equals requested dimensions and grain; partition_by is empty.
For latest use scope_object_id and the business partition_by; group_by is empty.
Preserve the original grain, projection, filters and scope explicitly: this
revision does not infer missing grain or rewrite semantics during normalization.
"""

QUALIFIER_V3 = """
Before submitting, account for every requested categorical qualifier, comparison,
time boundary and limit in the original question. A category name or code in the
question is usually a literal filter value, not an optional descriptive word.
Do not discard it because it is not an ObjectType or PropertyDefinition ID. Values
come from the question; property IDs come only from authorized logical context.
A category constraint must be represented by an explicit filter on the property
whose definition expresses that category, or by a declared semantic subtype. If
more than one property could materially mean that category, propose one readable
clarification with those property IDs; do not silently pick the first column.
If no appropriate property/subtype is available, report that missing meaning.
Never return an unfiltered superset as if it answered a filtered request. Preserve
collection-versus-root scope explicitly. Do not invent a filter, categorical
value, business default or hidden product scope not requested by the question.
This policy is an interpretation obligation, not authority to modify an emitted
intent. Output schema validity and successful execution do not establish coverage.
"""
