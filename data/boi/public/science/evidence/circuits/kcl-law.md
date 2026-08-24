---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: kcl-law'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:kcl-law
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
  evidence_id: sci-evidence:circuits:kcl-law
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    content_hash: sha256:b4c453cd2265ef5a94a2a2ce4025078a870b4db9c6d70a2bf3aa7722ecc8fba8
    section: Transcript — Lecture 2, Kirchhoff laws
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 2
    printed_page: PDF page 3
    hash_scope: retrieved_pdf_bytes
    sentence_label: KCL definition
  original_text: if I take any node of the circuit and sum up all the currents going into that node, they will all net sum
    to zero.
  original_text_hash: sha256:7589d29e989dc6aa1f5649690cb273ee9f3a2af231a4fc8008e2232836daf2e7
  language: en
  reviewed_translation: 회로의 임의의 노드로 들어가는 모든 전류를 합하면 그 순합은 0이 된다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The transcript uses currents directed into the node; another sign convention requires algebraically consistent signs.
  - The zero-sum node rule is bound to a lumped-matter model with no net node-charge accumulation over the modeled timescale.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: circuits.kcl.algebraic_current_sum_zero
      purpose: The algebraic sum of currents at a node is zero under a consistent direction convention.
      required_conditions:
      - Current reference directions are explicit and consistent.
      - The lumped-matter circuit approximation applies.
      - No net charge accumulation occurs at the node over the modeled timescale.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - The transcript uses currents directed into the node; another sign convention requires algebraically consistent signs.
    - The zero-sum node rule is bound to a lumped-matter model with no net node-charge accumulation over the modeled timescale.
  claim_scope_hash: sha256:584a8362a336e857edc9088a9ce0b74e8396830ee76b32b5845cb0d3185caacd
  supports_knowledge: []
  translation:
    status: agent_draft_pending_admin_review
    permission_status: not_assessed
    original_controls: true
    actor:
      type: agent
      agent_id: codex
  curation_actor:
    type: agent
    agent_id: codex
  curated_at: '2026-08-25T03:26:00+09:00'
  release_eligibility: blocked_pending_authorized_admin_review
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
