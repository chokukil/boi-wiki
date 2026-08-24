---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: repeatability-reproducibility'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:repeatability-reproducibility
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
  evidence_id: sci-evidence:common:repeatability-reproducibility
  source_id: sci-source:jcgm-vim-3-2012
  locator:
    medium: pdf
    resource_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    content_hash: sha256:8a603e99d236a65d771f38b6dcf627953146fe023a5266b3307681ada30f4fe7
    section: 2.24 reproducibility condition of measurement
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    resolved_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 39
    printed_page: printed 24; PDF page 40
    hash_scope: retrieved_pdf_bytes
  original_text: condition of measurement, out of a set of conditions that includes different locations, operators, measuring
    systems, and replicate measurements on the same or similar objects
  original_text_hash: sha256:2afe10eb83752121abfd3e76fb55c8faa88f7ffc03c98879cc6d6c157ccd09a1
  language: en
  reviewed_translation: 서로 다른 장소, 작업자, 측정시스템과 동일하거나 유사한 대상의 반복 측정을 포함하는 조건 집합에 속하는 측정 조건이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This span defines reproducibility conditions; repeatability uses a narrower condition set in the same vocabulary.
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
