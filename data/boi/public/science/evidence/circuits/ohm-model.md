---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: ohm-model'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:ohm-model
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
  evidence_id: sci-evidence:circuits:ohm-model
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/00c8847c48604169f00d53e0a46a4061_6_0022007L01.pdf
    content_hash: sha256:8190acbf2ce7b75f5170c56d13257da49356a533aa1a0661c2531eb7a373a7d9
    section: Transcript — Lecture 1
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/00c8847c48604169f00d53e0a46a4061_6_0022007L01.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/00c8847c48604169f00d53e0a46a4061_6_0022007L01.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 2
    printed_page: PDF page 3
    hash_scope: retrieved_pdf_bytes
  original_text: numbers can be codified by Ohm's law, for example, V is equal to RI, the voltage current, relates to the
    resistance of the object.
  original_text_hash: sha256:77f9866e3013f286378d0d2227faaeaa56ab9c751c30d8829d47e5a0f103d3e1
  language: en
  reviewed_translation: 수치 관계는 예를 들어 V = RI인 옴의 법칙으로 표현할 수 있으며, 전압과 전류를 물체의 저항과 연결한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This transcript sentence presents the resistor abstraction; it is not valid for every nonlinear or time-varying element.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.circuits.ohm_model
      purpose: numbers can be codified by Ohm's law, for example, V is equal to RI,
        the voltage current, relates to the resistance of the object.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This transcript sentence presents the resistor abstraction; it is not valid for
      every nonlinear or time-varying element.
  claim_scope_hash: sha256:0c75960364e9d1c8428674b423cdb47d64c8a043a7f981693cb24747d34cd770
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
