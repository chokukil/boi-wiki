---
okf_version: "0.1"
boi_profile_version: "0.1"
harness_version: "0.1.0"
type: boi/harness
title: Data Lake Query Harness
description: 선택형 Data Lake evidence를 BoI API/MCP를 통해 안전하게 쓰는 기준
tags: [BoIWiki, DataLake, Harness, MCP]
timestamp: 2026-06-30T00:00:00+09:00
boi_id: boi:public:harness:data-lake-query-harness
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: harness/data-lake-query-harness.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Data Lake Query Harness

BoI Wiki core는 OKF 내용을 DB에 넣지 않고 Markdown/JSONL 기반으로 동작한다. 사용자-facing Data Lake는 MinIO artifact store다. PostgreSQL은 Data Lake 필수 구성요소가 아니라 선택형 `local-full-legacy-db-demo` structured query adapter 예시다.

Agent, MCP, UI는 PostgreSQL에 직접 접속하지 않고, MinIO도 BoI API/MCP artifact 도구를 통해서만 사용한다. 파일 첨부는 Markdown body에 원문을 넣지 않고 Data Lake artifact로 저장한다. SQL-style 조회는 Legacy DB Demo adapter가 명시적으로 켜져 있을 때만 사용한다. 재사용할 source profile은 `data_lake_import_sources` 또는 `POST /api/data-lake/import`로 private OKF Data Context BoI에 materialize한다.

선택 fixture source는 `/home/chokukil/ontology`의 JSON/CSV이며 런타임 의존성이 아니다. 큰 raw table은 LLM prompt에 넣지 않고 profile, sample, chart, query result artifact 링크로 연결한다.

## Artifact Flow

사용자 첨부 파일, sandbox 산출물, report chart/table, CSV/JSON/PDF/이미지/raw evidence는 모두 같은 계약을 따른다.

1. `data_lake_artifact_upload` 또는 `POST /api/data-lake/artifacts/upload`로 private artifact를 만든다.
2. `data_lake_artifact_profile` 또는 `POST /api/data-lake/artifacts/{artifact_id}/profile`로 profile/sample을 만든다.
3. 원본은 `GET /api/data-lake/artifacts/{artifact_id}/download` stable URL로 연결한다.
4. workflow stage, Inbox task/report, Report BoI, action result, Agent conversation에는 `data_lake_artifact_attach`로 evidence 관계를 남긴다.
5. BoI/LLM context에는 원본 전체가 아니라 URL, profile, sample, chart/preview, checksum, validation metadata, ACL 정보만 넣는다.

SOP Builder는 미래 SOP의 근거 요구사항과 첨부 위치를 설계하는 화면이며 원본 파일 업로드 화면이 아니다. 실제 파일은 SOP Run, Inbox 판단, Manual Action 완료, Report BoI 검토, Agent 대화, sandbox/report workflow에서 업로드한다.

선택형 artifact profile은 `.env.local-full.example`과 `.env.local-full-datalake.example` overlay로만 켠다. PostgreSQL demo는 `.env.local-full-legacy-db-demo.example`과 `local-full-legacy-db-demo` profile로 별도 실행한다. fixture 파일 일부만 있을 수 있으므로 `available` 상태를 먼저 확인하고, 없는 source를 보고서 근거처럼 꾸며 쓰지 않는다.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context --artifact-smoke
```

PostgreSQL Legacy DB Demo까지 검증할 때만 별도 profile을 켠다.

```bash
BOI_COMPOSE_PROFILE=local-full-legacy-db-demo \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example:.env.local-full-legacy-db-demo.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --legacy-db-demo-smoke
```

기본 `local-full`에서는 Data Lake가 꺼져 있어도 아래 경계 검사가 통과해야 한다.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
python scripts/check_data_lake_artifacts.py --base-url http://localhost:28000 --strict
```

BoI Inbox 검증 보고서는 Data Lake가 켜져 있고 관련 source가 있으면 sample/profile/artifact link를 자동 근거 후보로 붙인다. 일반 사용자에게 “이 파일을 판단 근거로 사용” 같은 필수 체크를 요구하지 않는다. Data Lake가 꺼져 있거나 관련 source가 없으면 Event, Action, 생성 BoI, manual note, 과거 사례 근거만으로 계속 동작한다.
