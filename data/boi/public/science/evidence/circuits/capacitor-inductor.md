---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: capacitor-inductor'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:capacitor-inductor
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
  evidence_id: sci-evidence:circuits:capacitor-inductor
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/a3802171092cec5e967ba4f084b79de6_6_0022007L015a.pdf
    content_hash: sha256:62a9423232448971a486c1bc097def4140fd7efa676d41a9df1cce38549331dd
    section: Transcript — Lecture 15a
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/a3802171092cec5e967ba4f084b79de6_6_0022007L015a.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/a3802171092cec5e967ba4f084b79de6_6_0022007L015a.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 1
    printed_page: PDF page 2
    hash_scope: retrieved_pdf_bytes
  original_text: And the state variable for an inductor was the current while that for a capacitor was the capacitor voltage.
  original_text_hash: sha256:6e40abe7a05c033b74a8c1713522cc290e09bf7b3eafa39ad97556c8415fc85e
  language: en
  reviewed_translation: 인덕터의 상태변수는 전류이고 커패시터의 상태변수는 커패시터 전압이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This does not provide constitutive equations, initial conditions, or parasitic limits.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.circuits.capacitor_inductor
      purpose: And the state variable for an inductor was the current while that for a capacitor was the capacitor voltage.
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This does not provide constitutive equations, initial conditions, or parasitic limits.
  claim_scope_hash: sha256:55d14934b0a79770485265a3890e22accf593f545dde3389a41138e35d21eeda
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
