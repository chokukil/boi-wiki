---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'materials: structure-grain'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- materials
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:materials:structure-grain
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
  evidence_id: sci-evidence:materials:structure-grain
  source_id: sci-source:mit-3-091
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/0b96d759a9e98ced8c3611f19dc742d0_MIT3_091F18_GB7.pdf
    content_hash: sha256:95e027cf777fbc47c1d1a6287e80fdf34dee5c62bf7e9f258af01de1cac13043
    section: Goodie Bag 7 — Question 1
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/0b96d759a9e98ced8c3611f19dc742d0_MIT3_091F18_GB7.pdf
    resolved_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/0b96d759a9e98ced8c3611f19dc742d0_MIT3_091F18_GB7.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 1
    printed_page: PDF page 2
    hash_scope: retrieved_pdf_bytes
  original_text: Identify one 0D defect (vacancy), one 1D defect (line), one 2D defect (grain boundary – actually appears
    in 1D here).
  original_text_hash: sha256:5fb1d088efa88338ed76abdc95a08ea11f277d3df63289295076d0fba11f977b
  language: en
  reviewed_translation: 0차원 결함인 공공, 1차원 결함인 선, 2차원 결함인 결정립계를 각각 하나씩 식별한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This teaching-model classification does not quantify a grain-size/property relation.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.materials.structure_grain
      purpose: Identify one 0D defect (vacancy), one 1D defect (line), one 2D defect (grain boundary – actually appears in 1D
        here).
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This teaching-model classification does not quantify a grain-size/property relation.
  claim_scope_hash: sha256:2f1318b9ef8b9d9aa5e77c154655ecc798ce4bda5597f6412f9f55955e79f305
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
