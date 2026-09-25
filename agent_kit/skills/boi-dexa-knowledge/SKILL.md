---
name: boi-dexa-knowledge
description: Answer business-data questions using available DEXA semantic metadata, supported native logical query plans and protected results.
---

Use the [shared workflow](../boi-domain-work/SKILL.md). Discover actual accessible connections and semantic definitions through `boi_native_query`. Interpret the request against read objects, properties, relations, grain, filters and time scope. The host proposes a logical plan; the declared engine compiles and executes deterministically. Never supply SQL, filesystem database paths or caller authority.

Distinguish absent rows, missing mappings, unsupported operators and invalid plans. Data unavailable through current mappings is an implementation gap, not proof of absent data. Reuse completed results by exact execution reference under current access; changed requests require corresponding plans. Retain whole-result access and snapshot/scope.

Capabilities are bounded: use actual returned schemas rather than claiming arbitrary database/operator support. Read [existing query contracts](../boi-domain-work/references/existing-contracts.md) when preparing, executing or restoring queries. Connect process/SVID meanings through evidenced concepts without flattening their domain contracts.

For a server-registered database source, follow [DB intake and reuse](../../references/database-intake.md). Read actual rows as well as schema, reuse admitted Profiles, preserve source roles/conditions and complete publication before fresh-session answers. The installed DB adapter handles evidence conversion and resume; the agent supplies grounded meaning, not caller SQL or fabricated review.
