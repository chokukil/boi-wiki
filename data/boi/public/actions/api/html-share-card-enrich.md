---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/action-spec
title: 공유 HTML 지식 카드 enrich
description: html.share.published.v1 이벤트를 받아 지식 카드의 자동 분석 섹션과 사전 기반 tags를 다시 계산하는 API action (결정적 추출, LLM 없음)
tags:
- ActionGateway
- API
- HTML
- Share
timestamp: 2026-07-18 09:00:00+09:00
boi_id: boi:public:actions:api:html-share-card-enrich
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: claude
acl_policy: acl:public
status: reviewed
action_key: share.html_card.enrich
connector_kind: api
execution_mode: gateway
event_types:
- html.share.published.v1
risk_level: low
approval_required: false
dry_run_default: false
payload_contract:
  required:
  - name
  optional:
  - boi_id
  - visibility
result_contract:
  status: live
  fields:
  - updated
  - analysis
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
url: http://boi-api:8000/api/share/${payload.name}/enrich
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
      required:
      - name
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
  - name
  properties:
    ok:
      type: boolean
    name:
      type: string
    updated:
      type: boolean
    analysis:
      type: object
example_request:
  payload:
    name: weekly-etch-report
    boi_id: boi:public:html:weekly-etch-report
    visibility: public
  event:
    event_type: html.share.published.v1
  dry_run: false
  approved_by: ''
example_response:
  ok: true
  name: weekly-etch-report
  updated: true
  analysis:
    heading_count: 4
    table_count: 2
    script_count: 1
    tags:
    - HTML
    - Share
    - Etch
curl: 'curl -X POST ''http://boi-api:8000/api/share/weekly-etch-report/enrich'' -H
  ''x-service-token: $SERVICE_TOKEN'''
action_gateway_mapping:
  invoke_url: http://localhost:8100/api/actions/invoke
  action_key: share.html_card.enrich
  catalog_type: api
  doc_ref: boi:public:actions:api:html-share-card-enrich
health_check:
  type: http
  command: curl -fsS 'http://boi-api:8000/health' || true
security_notes:
- Use environment variables for tokens.
- Do not store real service tokens or API keys in public BoI docs.
- 카드 본문 재작성은 자동 분석 섹션과 tags에 한정되며 소유자/서비스 토큰 호출만 허용된다.
---

# Usage

공유 HTML이 게시/갱신되면(`html.share.published.v1`) 이 action이 지식 카드의
`# 자동 분석` 섹션(제목/추출 목차/본문 발췌/표·스크립트 수)과 공개 사전 용어 기반
tags를 다시 계산한다. 추출은 완전 결정적이며 LLM을 호출하지 않는다.
