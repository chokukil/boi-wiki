---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Data Lake Artifact Lifecycle
description: MinIO Data Lake artifact를 업무 근거로 첨부, 조회, 검증, 보고서에 연결하는 기준
tags: [Manual, DataLake, Artifact, MinIO, Evidence, Workflow]
timestamp: 2026-07-04T12:00:00+09:00
boi_id: boi:public:boi-wiki-manual:data-lake:data-lake-artifact-lifecycle
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
    ref: boi_api/app/main.py
  - type: repo
    ref: data/boi/public/harness/data-lake-artifact-harness.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

Data Lake는 사용자-facing 명칭이며 MinIO 기반 artifact store다. Raw Data, PDF, PPT, Excel, 로그, 캡처, chart, table, sandbox 산출물 같은 원본 파일은 OKF Markdown 본문에 넣지 않고 Data Lake artifact로 저장한다.

BoI, SOP, Inbox, Report, Agent 대화에는 원본 대신 stable download URL, profile, sample, checksum, validation metadata, 첨부 사유를 남긴다. 이렇게 해야 사람이 원본을 클릭해 확인할 수 있고, Agent는 bounded profile과 preview만 써서 context가 터지지 않는다.

# What Goes Into Data Lake

| Artifact | 예시 | 기본 연결 위치 |
|---|---|---|
| Raw data | CSV, JSONL, 장비 로그, trend export | SOP Run Task, Inbox 판단 |
| 작업 결과 | PPT, PDF, Excel, 캡처, 수동 점검 기록 | Manual Action result |
| 분석 산출물 | chart PNG, table CSV, report HTML, notebook output | Report BoI, Agent conversation |
| 참고 자료 | API 문서, 외부 가이드, spec 파일 | Workflow Task, Report review |

모든 artifact는 기본 private이다. team/public 공유는 명시 승인과 ACL/RBAC 검사를 거친다.

# Where Upload Is Allowed

SOP Builder는 미래 SOP의 근거 요구사항과 첨부 위치를 설계하는 화면이다. `/sops/new`에서는 원본 파일을 업로드하지 않는다.

파일 첨부는 실제 업무 맥락이 있는 화면에서만 노출한다.

| Surface | target_type | 목적 |
|---|---|---|
| SOP Run Task panel | `workflow_stage` | 현재 Task 판단에 필요한 Raw Data 또는 근거 첨부 |
| Inbox 승인/조치 | `inbox_task` | 승인, 반려, 보류, 추가 근거 요청의 판단 근거 첨부 |
| Manual Action 완료 | `action_result` | 사람이 수행한 조치 결과 파일 첨부 |
| Report BoI 검토/편집 | `report` | 보고서 보강 파일, chart source, 원본 링크 첨부 |
| Agent/Report Agent 대화 | `conversation` | 분석 대상 파일 또는 생성 artifact 첨부 |

현재 화면의 업무 맥락과 선택된 Task/report/decision이 attachment target을 결정한다. 사용자가 “근거로 사용”을 별도 체크하지 않아도 현재 대상에 자동 연결된다.

# Artifact Record

Artifact attachment는 다음 metadata를 남긴다.

| Field | Meaning |
|---|---|
| `uploaded_by_employee_id` | 업로더 사번 |
| `attached_from_surface` | 업로드가 발생한 화면 |
| `target_type` / `target_id` | 연결된 업무 대상 |
| `attachment_role` | `raw_data`, `evidence`, `result_file`, `reference`, `visualization_source` |
| `human_note` | 사람이 남긴 한 줄 맥락 |
| `validation_state` | `uploaded`, `profiled`, `review_required`, `verified_evidence` |
| `checksum` | 원본 파일 검증용 checksum |
| `download_url` | BoI API stable download URL |

`artifact_id`, object key, checksum 같은 내부 식별자는 기본 UI에 노출하지 않고 기술 세부정보에 둔다.

# API And MCP

| Interface | Use |
|---|---|
| `POST /api/data-lake/artifacts/upload` | 파일 업로드와 artifact record 생성 |
| `GET /api/data-lake/artifacts?target_type=&target_id=` | 특정 업무 대상의 artifact 목록 조회 |
| `GET /api/data-lake/artifacts/{artifact_id}` | artifact metadata 조회 |
| `GET /api/data-lake/artifacts/{artifact_id}/download` | 원본 파일 다운로드 |
| `POST /api/data-lake/artifacts/{artifact_id}/profile` | profile/sample/preview 생성 |
| `POST /api/data-lake/artifacts/{artifact_id}/attach` | 업무 대상에 artifact 연결 |
| `DELETE /api/data-lake/artifacts/{artifact_id}/attach` | 업무 대상 연결 해제 |

MCP client는 `data_lake_artifact_upload`, `data_lake_artifact_get`, `data_lake_artifact_download_url`, `data_lake_artifact_profile`, `data_lake_artifact_attach`, `data_lake_artifact_list`를 사용한다. UI, Agent, MCP는 MinIO에 직접 접속하지 않고 BoI API/MCP contract만 사용한다.

# Data Lake vs Legacy DB Demo

`Data Lake`는 MinIO artifact store를 의미한다. PostgreSQL은 Data Lake 필수 구성요소가 아니며, 별도 `Legacy DB Demo` 또는 structured query adapter 예시다.

Data Lake가 비활성화된 local-full에서도 BoI Wiki core, SOP Builder, Inbox, manual 문서 조회는 계속 동작해야 한다. 이때 artifact API는 disabled contract를 반환하고 업로드 UI는 비활성 안내를 보여준다.

# Related Documents

- [Data Lake Artifact Harness](/public/harness/data-lake-artifact-harness.md)
- [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md)
- [SOP Workflow 작성과 Runtime 연결](/public/boi-wiki-manual/sop-workflows/create-and-connect-sop.md)
