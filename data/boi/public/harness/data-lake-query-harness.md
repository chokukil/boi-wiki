---
okf_version: "0.1"
boi_profile_version: "0.1"
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

BoI Wiki core는 DB 없이 OKF Markdown/JSONL 기반으로 동작한다. PostgreSQL과 MinIO는 선택형 `local-full-datalake` demo dependency이며, 기본 local-full 완료 기준이 아니다.

Agent, MCP, UI는 PostgreSQL/MinIO에 직접 접속하지 않고 BoI API/MCP Data Lake 도구만 사용한다. 흐름은 `status → plan → preview → confirmed execute → artifact link`다. 재사용할 source profile은 `data_lake_import_sources` 또는 `POST /api/data-lake/import`로 private OKF Data Context BoI에 materialize한다.

선택 fixture source는 `/home/chokukil/ontology`의 JSON/CSV이며 런타임 의존성이 아니다. 큰 raw table은 LLM prompt에 넣지 않고 profile, sample, chart, query result artifact 링크로 연결한다.

선택형 demo profile은 `.env.local-full.example`과 `.env.local-full-datalake.example` overlay로만 켠다. fixture 파일 일부만 있을 수 있으므로 `available` 상태를 먼저 확인하고, 없는 source를 보고서 근거처럼 꾸며 쓰지 않는다.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context
```

기본 `local-full`에서는 Data Lake가 꺼져 있어도 아래 경계 검사가 통과해야 한다.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
```

BoI Inbox 검증 보고서는 Data Lake가 켜져 있고 관련 source가 있으면 sample/profile/artifact link를 자동 근거 후보로 붙인다. 일반 사용자에게 “이 파일을 판단 근거로 사용” 같은 필수 체크를 요구하지 않는다. Data Lake가 꺼져 있거나 관련 source가 없으면 Event, Action, 생성 BoI, manual note, 과거 사례 근거만으로 계속 동작한다.
