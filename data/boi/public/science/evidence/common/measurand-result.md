---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: measurand-result'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:measurand-result
visibility: public
classification: internal
owner: science-admin
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
- type: boi
  ref: boi:public:science:source:jcgm-vim-3-2012
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:common:measurand-result
  source_id: sci-source:jcgm-vim-3-2012
  locator:
    medium: pdf
    resource_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    content_hash: sha256:8a603e99d236a65d771f38b6dcf627953146fe023a5266b3307681ada30f4fe7
    section: 2.9 measurement result, Note 2
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    resolved_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 34
    printed_page: printed 19; PDF page 35
    hash_scope: retrieved_pdf_bytes
  original_text: A measurement result is generally expressed as a single measured quantity value and a measurement uncertainty.
  original_text_hash: sha256:75561497ed7d51ebbe73a03c3f73f785f833c50d1bbd1265a7bcb43fc865c167
  language: en
  reviewed_translation: 측정 결과는 일반적으로 하나의 측정량 값과 측정불확도로 표현한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The VIM says generally; a result can require more than a bare numerical value.
  supports_knowledge: []
  curation_actor:
    type: agent
    agent_id: codex
  curated_at: '2026-08-25T03:26:00+09:00'
  release_eligibility: blocked_pending_authorized_admin_review
  translation:
    status: unofficial_internal_draft
    permission_status: not_recorded
    original_controls: true
    actor:
      type: agent
      agent_id: codex
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
