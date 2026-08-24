---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: quantity-unit-dimension'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:quantity-unit-dimension
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
  evidence_id: sci-evidence:common:quantity-unit-dimension
  source_id: sci-source:bipm-si-brochure-9-v4-01
  locator:
    medium: pdf
    resource_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    content_hash: sha256:1122cf38e25b23d780a30607c68f7350b2b6d1f9970a89947aaa87a45ecbb20a
    section: 2.3.3 Dimensions of quantities
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    resolved_url: https://www.bipm.org/documents/20126/41483022/SI-Brochure-9.pdf/fcf090b2-04e6-88cc-1149-c3e029ad8232?download=true
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 133
    printed_page: printed 132; PDF page 134
    hash_scope: retrieved_pdf_bytes
  original_text: Physical quantities can be organized in a system of dimensions, where the system used is decided by convention.
    Each of the seven base quantities used in the SI is regarded as having its own dimension.
  original_text_hash: sha256:0ff0685ae817a8ef57fb5ba3823895b803e8def0f5a6700aa8f3244165520192
  language: en
  reviewed_translation: 물리량은 관례로 정한 차원 체계로 구성할 수 있으며, SI의 일곱 기본량은 각각 고유한 차원을 갖는 것으로 본다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This defines the SI dimensional framework; it does not by itself validate a proposed equation.
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
