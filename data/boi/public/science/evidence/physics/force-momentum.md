---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'physics: force-momentum'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- physics
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:physics:force-momentum
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
  ref: boi:public:science:source:mit-8-01sc
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:physics:force-momentum
  source_id: sci-source:mit-8-01sc
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter10.pdf
    content_hash: sha256:d6c8907971c0678128defc79ccf8d6e7c7c3c2a44761e7b046794716763eed83
    section: 10.4 Newton’s Second Law for a System of Objects
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter10.pdf
    resolved_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter10.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 6
    printed_page: printed 10-6; PDF page 7
    hash_scope: retrieved_pdf_bytes
    transcription_method: manual verification against the rendered PDF; the excerpt ends at "as" immediately before equation
      (10.4.9), with no invented terminal punctuation
  original_text: We conclude that the external force causes the momentum of the system to change, and we thus restate and
    generalize Newton’s Second Law for a system of objects as
  original_text_hash: sha256:5d80a2f657106aa4cb788eeb4b8b298759c3bbe506689eb74f09b290662be2cc
  language: en
  reviewed_translation: 외력이 계의 운동량을 변화시키므로, 물체 계에 대한 뉴턴의 제2법칙을 다음과 같이 다시 서술하고 일반화한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Applicability requires a defined system and reference frame.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.physics.force_momentum
      purpose: We conclude that the external force causes the momentum of the system
        to change, and we thus restate and generalize Newton’s Second Law for a system
        of objects as
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Applicability requires a defined system and reference frame.
  claim_scope_hash: sha256:df8a86c3056e919c88210f734aea150b2f7b3e0284b4bf30843b4fa16013174f
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
