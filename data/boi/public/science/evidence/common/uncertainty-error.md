---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: uncertainty-error'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:uncertainty-error
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
  evidence_id: sci-evidence:common:uncertainty-error
  source_id: sci-source:jcgm-vim-3-2012
  locator:
    medium: pdf
    resource_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    content_hash: sha256:8a603e99d236a65d771f38b6dcf627953146fe023a5266b3307681ada30f4fe7
    section: 2.26 measurement uncertainty
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    resolved_url: https://www.bipm.org/documents/20126/2071204/JCGM_200_2012.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 40
    printed_page: printed 25; PDF page 41
    hash_scope: retrieved_pdf_bytes
  original_text: measurement uncertainty non-negative parameter characterizing the dispersion of the quantity values being
    attributed to a measurand, based on the information used
  original_text_hash: sha256:59634808518a67404e1a43f1507873c98ba9bed78ffaa5cf2c0960cc167a6ff9
  language: en
  reviewed_translation: 측정불확도는 사용한 정보를 바탕으로 측정대상량에 귀속되는 값들의 분산을 나타내는 음이 아닌 매개변수다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This span defines uncertainty, not measurement error; the two concepts must not be collapsed.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: measurement.uncertainty_definition_only
      purpose: The cited span may support only the VIM definition of measurement uncertainty, not a contrast with measurement
        error.
      required_conditions:
      - Use the cited VIM edition and term locator.
      - Do not infer an error definition absent from this span.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This span defines uncertainty, not measurement error; the two concepts must not be collapsed.
  claim_scope_hash: sha256:361fd944af63bb80696b4ec1f1695c932a011598c3e17eedc916f866facf724d
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
