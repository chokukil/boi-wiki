---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: measurement-loading'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:measurement-loading
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
  ref: boi:public:science:source:mit-6-002
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:circuits:measurement-loading
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/992c85451e40984a2b3a6f4878bb1a76_lab_handout.pdf
    content_hash: sha256:4b81410c8e1aba21fd399521e0be424e694ecd4cd17b11b5915889052e9338f0
    section: Lab Equipment Handout — High Z vs. 50 Ohm modes
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/992c85451e40984a2b3a6f4878bb1a76_lab_handout.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/992c85451e40984a2b3a6f4878bb1a76_lab_handout.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 7
    printed_page: PDF page 8
    hash_scope: retrieved_pdf_bytes
  original_text: This interaction between the oscilloscope and an external circuit is termed circuit loading.
  original_text_hash: sha256:75654fcc1d4059d2065dd33df98dc0603a0e92c3f713a02be3ef2fd908e70655
  language: en
  reviewed_translation: 오실로스코프와 외부 회로 사이의 이러한 상호작용을 회로 로딩이라 한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Whether loading is negligible depends on source and instrument impedances and frequency.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.circuits.measurement_loading
      purpose: This interaction between the oscilloscope and an external circuit is
        termed circuit loading.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Whether loading is negligible depends on source and instrument impedances and
      frequency.
  claim_scope_hash: sha256:e6a160896ba4cca8e804a3ced7f3c639930808897e8633846be9be4cada3557d
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
