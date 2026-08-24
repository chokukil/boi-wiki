---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: series-parallel'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:series-parallel
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
  evidence_id: sci-evidence:circuits:series-parallel
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    content_hash: sha256:b4c453cd2265ef5a94a2a2ce4025078a870b4db9c6d70a2bf3aa7722ecc8fba8
    section: Transcript — Lecture 2
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 9
    printed_page: PDF page 10
    hash_scope: retrieved_pdf_bytes
  original_text: the conductances in parallel add, and resistances in series add.
  original_text_hash: sha256:6806a696e288816d1721a0b4a130155003eb7c99bc42dc2cf6b3d9b5ef980852
  language: en
  reviewed_translation: 병렬에서는 컨덕턴스가 더해지고 직렬에서는 저항이 더해진다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This assumes the lumped resistive network abstraction and the stated topology.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.circuits.series_parallel
      purpose: the conductances in parallel add, and resistances in series add.
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This assumes the lumped resistive network abstraction and the stated topology.
  claim_scope_hash: sha256:f39ef2bf7a085fce1f49b31f9d6d5ba6c76eb9f31975a2db5665c015525b0197
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
