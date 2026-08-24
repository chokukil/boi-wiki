---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'materials: phase-transformation'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- materials
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:materials:phase-transformation
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
  ref: boi:public:science:source:mit-3-012
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:materials:phase-transformation
  source_id: sci-source:mit-3-012
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/3-012-fundamentals-of-materials-science-fall-2005/69147da16e467a72cfa145c1d13f644f_lec05t.pdf
    content_hash: sha256:6d6e62a627c1aae150ad486ea75183ea7723f1f9a8ee3012cdc9a73d5a7c5433
    section: Lecture 5 — Phase transitions of metastable and unstable materials
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/3-012-fundamentals-of-materials-science-fall-2005/69147da16e467a72cfa145c1d13f644f_lec05t.pdf
    resolved_url: https://ocw.mit.edu/courses/3-012-fundamentals-of-materials-science-fall-2005/69147da16e467a72cfa145c1d13f644f_lec05t.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 9
    printed_page: PDF page 10
    hash_scope: retrieved_pdf_bytes
  original_text: Liquids can be supercooled- cooled to temperatures below their equilibrium freezing points. Likewise, solids
    can be superheated- heated to temperatures above the melting point. Such phases are unstable or metastable and will readily
    transform to the equilibrium state.
  original_text_hash: sha256:a2ba6b32ff19b146c827a6b1347ecc288b7f513699ba3e06b729a9672493cb0a
  language: en
  reviewed_translation: 액체는 평형 어는점 아래로 과냉각될 수 있고 고체는 녹는점 위로 과열될 수 있다. 이런 상은 불안정하거나 준안정해 평형 상태로 쉽게 변환한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Kinetic barriers and timescale determine whether transformation occurs in a particular case.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.materials.phase_transformation
      purpose: Liquids can be supercooled- cooled to temperatures below their equilibrium
        freezing points. Likewise, solids can be superheated- heated to temperatures
        above the melting point. Such phases are unstable or metastable and will readily
        transform to the equilibrium state.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Kinetic barriers and timescale determine whether transformation occurs in a particular
      case.
  claim_scope_hash: sha256:94f685a1df408f9aa3496a8850fd5f8ba92b0bf6ce43fc28d9c27abfc5d2828a
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
