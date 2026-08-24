---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: steady-state'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:steady-state
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
  ref: boi:public:science:source:mit-3-091
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:common:steady-state
  source_id: sci-source:mit-3-091
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    content_hash: sha256:ded3970444be9ed9b62f3aef4d90f3ece6687caf336a6894a0b6a17723f6300a
    section: Recitation 26 — Steady state diffusion
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    resolved_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 0
    printed_page: PDF page 1
    hash_scope: retrieved_pdf_bytes
  original_text: 'Steady state (time independent) diffusion is described by Fick’s first law:'
  original_text_hash: sha256:e4963053d7d7490eeff63890ee23acc02a550679c3dd94ad92591fd1319b9056
  language: en
  reviewed_translation: 정상 상태, 즉 시간에 무관한 확산은 Fick의 제1법칙으로 기술된다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This is a diffusion-specific steady-state statement, not a claim that every variable or system is at equilibrium.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.common.steady_state
      purpose: 'Steady state (time independent) diffusion is described by Fick’s first law:'
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This is a diffusion-specific steady-state statement, not a claim that every variable or system is at equilibrium.
  claim_scope_hash: sha256:3fea0019cd79a57ed95a5fcecb6de79c13ee9f8ab62344a91ef86fe96df6b6e5
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
