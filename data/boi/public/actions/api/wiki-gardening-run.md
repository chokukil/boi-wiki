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
  - report
  - remediation
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
  - report
  properties:
    ok:
      type: boolean
    report:
      type: object
    remediation:
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
  report:
    ran_at: '2026-07-18T02:00:00+09:00'
    counts:
      stale: 1
      orphan: 2
      broken_link: 0
      duplicate: 1
      feedback: 0
  remediation:
    emitted_count: 4
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
