---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'circuits: electric-power'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- circuits
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:circuits:electric-power
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
  evidence_id: sci-evidence:circuits:electric-power
  source_id: sci-source:mit-6-002
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    content_hash: sha256:b4c453cd2265ef5a94a2a2ce4025078a870b4db9c6d70a2bf3aa7722ecc8fba8
    section: Transcript — Lecture 2, passive sign convention
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    resolved_url: https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 2
    printed_page: PDF page 3
    hash_scope: retrieved_pdf_bytes
  original_text: I'm going to label "i" for that element as a current flowing into the positive terminal. It's just a convention.
    By doing this, it turns out that the power consumed by the element is "vi" is positive.
  original_text_hash: sha256:8219b4ee6b1df98fe458698fb7623b83c861cc65c7527b68a92d94e7dea0dcde
  language: en
  reviewed_translation: 그 소자의 전류 i를 양의 단자로 들어가는 방향으로 정한다. 이는 부호 규약이며, 이 규약에서는 소자가 소비하는 전력 vi가 양수이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This supports only the passive sign convention. Reversing the reference direction changes the algebraic sign; it does
    not change physical power flow.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: circuits.passive_sign_convention.power_positive_when_consumed
      purpose: With current referenced into the positive terminal, positive vi denotes
        consumed power.
      required_conditions:
      - key: sign_convention
        operator: eq
        value: passive
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This supports only the passive sign convention. Reversing the reference direction
      changes the algebraic sign; it does not change physical power flow.
  claim_scope_hash: sha256:8096756a870c65105107eefd489165db85e6457aee637e66a373767ba9f0bed8
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
