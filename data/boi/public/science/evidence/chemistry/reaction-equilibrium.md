---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'chemistry: reaction-equilibrium'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- chemistry
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:chemistry:reaction-equilibrium
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
  ref: boi:public:science:source:mit-5-111
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:chemistry:reaction-equilibrium
  source_id: sci-source:mit-5-111
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    content_hash: sha256:b4f3acdc101c11a99d079fcf68c4cee4f79576eaa6de00ba8b822259c49b7369
    section: Lecture Summary 19 — Meaning of K
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    resolved_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 2
    printed_page: PDF page 3
    hash_scope: retrieved_pdf_bytes
    transcription_method: manual verification against the rendered PDF; the source rendering "K = is" is retained verbatim
  original_text: K = is the equilibrium constant. It has the same form as Q, but only uses the amounts of products and reactants
    at equilibrium.
  original_text_hash: sha256:58372fc42d88ec04a728829489c4c6cdcf29f47d1580757e5b37d7499f80828d
  language: en
  reviewed_translation: K는 평형상수다. Q와 같은 형식을 갖지만 평형에서의 생성물과 반응물 양만 사용한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Activities, standard states, and the balanced reaction remain necessary for quantitative use.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.chemistry.reaction_equilibrium
      purpose: K = is the equilibrium constant. It has the same form as Q, but only uses
        the amounts of products and reactants at equilibrium.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Activities, standard states, and the balanced reaction remain necessary for quantitative
      use.
  claim_scope_hash: sha256:137bed48aef7679022772cba58deca4e53c17cb0f78dd9081ae2a3a4e0f797bb
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
