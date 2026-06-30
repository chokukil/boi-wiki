---
title: Data Lake Query Harness
type: boi/harness
status: reviewed
---

# Data Lake Query Harness

Use this harness when adding or using optional Data Lake evidence.

## Boundary

BoI Wiki core is DB-less. PostgreSQL and MinIO are optional `local-full-datalake` demo dependencies only.

Agents, MCP clients, and UI screens must not connect directly to PostgreSQL or MinIO. They use BoI API/MCP Data Lake tools.

## Flow

1. Check `data_lake_status`.
2. If disabled, continue with OKF/Event/Action/BoI evidence and tell the user Data Lake is not enabled.
3. If enabled, call `data_lake_query_plan`.
4. Preview with `data_lake_query_preview`.
5. Execute only after explicit confirmation with `data_lake_query_execute`.
6. Use returned artifact links, profiles, samples, and summaries as report evidence. Do not paste large raw tables into LLM prompts.
7. When a source should be reusable by reports or Agent reasoning, materialize its profile with `data_lake_import_sources` or `POST /api/data-lake/import`. This creates private OKF Data Context BoI documents; it does not make PostgreSQL/MinIO a core dependency.

The demo profile is started with `.env.local-full.example` plus `.env.local-full-datalake.example`. The default profile must stay disabled.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context
```

The core profile boundary is checked separately. This must pass without PostgreSQL or MinIO.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
```

Inbox reports should use available Data Lake evidence automatically when the profile is enabled. Do not add a required "use this file as evidence" checkbox for normal users. If Data Lake is disabled or has no matching source, the report must continue with Event/Action/BoI evidence.

## Fixture Sources

The optional demo importer can use `/home/chokukil/ontology` as an import source, not as a runtime dependency.

- `backend/data/seed/demo/sqliteData.json`
- `backend/data/seed/demo/mesPfo.json`
- `exports/etch_process_sequence_by_product_route.csv/json`

`~/ontology/data/mes.sqlite` is not a v1 source unless it contains real data.

When only a subset of fixture files exists, the status API must mark each source with `available` and use only available sources for plan/preview/execute.
