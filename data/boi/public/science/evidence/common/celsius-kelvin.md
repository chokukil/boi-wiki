---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: celsius-kelvin'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:celsius-kelvin
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
  ref: boi:public:science:source:bipm-si-brochure-9-v4-01
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:common:celsius-kelvin
  source_id: sci-source:bipm-si-brochure-9-v4-01
  locator:
    medium: pdf
    resource_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    content_hash: sha256:1122cf38e25b23d780a30607c68f7350b2b6d1f9970a89947aaa87a45ecbb20a
    section: 2.3.1 Base units
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    resolved_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 130
    printed_page: printed 129; PDF page 131
    hash_scope: retrieved_pdf_bytes
  original_text: The unit of Celsius temperature is the degree Celsius, symbol °C, which is by definition equal in magnitude
    to the unit kelvin.
  original_text_hash: sha256:61459c78627bb087a81e87405c3499b2e883cdb55a466f3172fe8254ef3d3a94
  language: en
  reviewed_translation: 섭씨 온도의 단위인 섭씨도(°C)는 정의상 켈빈 단위와 크기가 같다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Equal interval magnitude does not make Celsius and kelvin absolute readings interchangeable; the offset remains relevant.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.common.celsius_kelvin
      purpose: The unit of Celsius temperature is the degree Celsius, symbol °C, which
        is by definition equal in magnitude to the unit kelvin.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Equal interval magnitude does not make Celsius and kelvin absolute readings interchangeable;
      the offset remains relevant.
  claim_scope_hash: sha256:3931d7b0df652bbb234f0cd8880ed9fb15f8488e6d2620debcf2292a7f3a99e8
  supports_knowledge: []
  curation_actor:
    type: agent
    agent_id: codex
  curated_at: '2026-08-25T03:26:00+09:00'
  release_eligibility: blocked_pending_authorized_admin_review
  translation:
    status: agent_draft_pending_admin_review
    permission_status: not_assessed
    original_controls: true
    actor:
      type: agent
      agent_id: codex
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
