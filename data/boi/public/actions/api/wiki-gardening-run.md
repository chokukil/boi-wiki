---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 위키 가드닝 점검 실행
description: wiki.gardening.requested.v1 이벤트를 받아 BoI Wiki 지식 정원 점검(stale/orphan/broken link/중복 후보/피드백)을 실행하는 API action
tags:
- ActionGateway
- API
- Gardening
timestamp: 2026-07-18 09:00:00+09:00
boi_id: boi:public:actions:api:wiki-gardening-run
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: claude
acl_policy: acl:public
status: reviewed
action_key: wiki.gardening.run
connector_kind: api
execution_mode: gateway
event_types:
- wiki.gardening.requested.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required: []
  optional:
  - max_age_days
  - limit
result_contract:
  status: live
  fields:
  - status
  - job
source_refs:
- type: action_catalog
  ref: data/action_catalog/actions.yaml
- type: plan
  ref: docs/HTML_SHARE_AND_META_HARNESS_PLAN.md
review:
  reviewer: tf-lead
  review_status: reviewed
protocol: http
method: POST
url: http://boi-api:8000/api/gardening/run
auth:
  type: header
  header: x-service-token
  value: $SERVICE_TOKEN
headers:
  Content-Type: application/json
  x-service-token: ${service_token}
request_schema:
  type: object
  properties:
    payload:
      type: object
    event:
      type: object
    request_id:
      type: string
    dry_run:
      type: boolean
    approved_by:
      type: string
response_schema:
  type: object
  required:
  - ok
  - status
  properties:
    ok:
      type: boolean
    status:
      type: string
    job:
      type: object
example_request:
  payload:
    reason: nightly gardening schedule
  event:
    event_type: wiki.gardening.requested.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  status: started
  job:
    state: running
    started_at: '2026-07-18T02:00:00+09:00'
curl: 'curl -X POST ''http://boi-api:8000/api/gardening/run'' -H ''x-service-token:
  $SERVICE_TOKEN'' -H ''Content-Type: application/json'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: wiki.gardening.run
  catalog_type: api
  doc_ref: boi:public:actions:api:wiki-gardening-run
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/health' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
- 발견 항목은 wiki.remediation.requested.v1로만 재발행되며 자동 수정/삭제는 하지 않는다(HOTL).
---

# Usage

스케줄러는 외부 cron/이벤트 발행자다. 주기적으로 `wiki.gardening.requested.v1` 이벤트를
발행하면 이 action이 boi-api의 gardening 점검을 호출하고, 발견 항목을
`wiki.remediation.requested.v1`로 재발행해 `boi.materialize_event`가 Inbox 루프를 닫는다.
`POST /api/gardening/run`은 수동/로컬 트리거로도 사용된다.

기본은 비동기 job이다: 이 action이 호출하는 응답은 스캔이 끝났다는 뜻이 아니라
`{ok, status: started|already_running, job}`로 스캔이 "시작됐다"는 즉시 응답이다(문서
수천 개 규모에서 요청 스레드가 타임아웃나던 문제를 막는다). 실제 점검 결과는
`GET /api/gardening/report`를 폴링해 `state`가 `ready`가 될 때까지 기다린 뒤 그 응답의
`report`/`remediation` 필드에서 읽는다. 테스트/소규모 코퍼스에서 즉시 블로킹 응답이
필요하면 `sync=true` 쿼리 파라미터를 준다(이 경우 응답이 `{ok, report, remediation}`이 된다).
