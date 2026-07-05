---
title: Data Lake Query Harness
type: boi/harness
status: reviewed
---

# Data Lake Query Harness

Use this harness when adding or using optional Data Lake evidence.

## Boundary

BoI Wiki core is DB-less for OKF content. The user-facing Data Lake is MinIO-backed artifact storage. PostgreSQL is not part of Data Lake; it is only an optional `local-full-legacy-db-demo` structured query adapter.

Agents, MCP clients, and UI screens must not connect directly to PostgreSQL or MinIO. They use BoI API/MCP tools. Files are Data Lake artifacts, not Markdown body blobs. SQL-style demos use the Legacy DB Demo adapter only when explicitly enabled.

## Flow

1. Check `data_lake_status`.
2. If disabled, continue with OKF/Event/Action/BoI evidence and tell the user Data Lake is not enabled.
3. If enabled, call `data_lake_query_plan`.
4. Preview with `data_lake_query_preview`.
5. Execute only after explicit confirmation with `data_lake_query_execute`.
6. Use returned artifact links, profiles, samples, and summaries as report evidence. Do not paste large raw tables into LLM prompts.
7. When a source should be reusable by reports or Agent reasoning, materialize its profile with `data_lake_import_sources` or `POST /api/data-lake/import`. This creates private OKF Data Context BoI documents; it does not make MinIO or the Legacy DB Demo a core dependency.

## Artifact Flow

Use this flow for user files, sandbox outputs, report charts, CSV/JSON/PDF/image evidence, and any raw source that could exceed context budget.

1. Upload with `data_lake_artifact_upload` or `POST /api/data-lake/artifacts/upload`.
2. Profile with `data_lake_artifact_profile` or `POST /api/data-lake/artifacts/{artifact_id}/profile`.
3. Link the original through `GET /api/data-lake/artifacts/{artifact_id}/download`.
4. Attach to workflow stage, Inbox task/report, Report BoI, action result, or Agent conversation with `data_lake_artifact_attach`.
5. Put only the stable download URL, profile, sample, chart/preview, checksum, validation result, and ACL metadata into BoI/LLM context.

SOP Builder should not upload raw files while defining a future SOP. It should capture required evidence types and the stage where evidence will be attached. Actual files are uploaded later from SOP Run, Inbox decision, Manual Action completion, Report BoI review, Agent conversation, or sandbox/report workflows.

The artifact profile is started with `.env.local-full.example` plus `.env.local-full-datalake.example`. The default profile must stay disabled. PostgreSQL demos require the separate `.env.local-full-legacy-db-demo.example` overlay and `local-full-legacy-db-demo` profile.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context --artifact-smoke
```

Optional Legacy DB Demo smoke:

```bash
BOI_COMPOSE_PROFILE=local-full-legacy-db-demo \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example:.env.local-full-legacy-db-demo.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --legacy-db-demo-smoke
```

The core profile boundary is checked separately. This must pass without MinIO or PostgreSQL.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
python scripts/check_data_lake_artifacts.py --base-url http://localhost:28000 --strict
```

Inbox reports should use available Data Lake evidence automatically when the profile is enabled. Do not add a required "use this file as evidence" checkbox for normal users. If Data Lake is disabled or has no matching source, the report must continue with Event/Action/BoI evidence.

## Fixture Sources

The optional demo importer can use `/home/chokukil/ontology` as an import source, not as a runtime dependency.

- `backend/data/seed/demo/sqliteData.json`
- `backend/data/seed/demo/mesPfo.json`
- `exports/etch_process_sequence_by_product_route.csv/json`

`~/ontology/data/mes.sqlite` is not a v1 source unless it contains real data.

When only a subset of fixture files exists, the status API must mark each source with `available` and use only available sources for plan/preview/execute.
