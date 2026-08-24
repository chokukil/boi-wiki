---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'physics: rotation-angular-speed'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- physics
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:physics:rotation-angular-speed
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
  evidence_id: sci-evidence:physics:rotation-angular-speed
  source_id: sci-source:mit-8-01sc
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter6.pdf
    content_hash: sha256:6c6b09ad0f212d4685037e860824e5a4ec6a02ff24c0a7ad205649e36faac152
    section: 6.2 Angular Velocity for Uniform Circular Motion
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter6.pdf
    resolved_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter6.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 3
    printed_page: printed 3; PDF page 4
    hash_scope: retrieved_pdf_bytes
  original_text: The angular speed is the magnitude of the rate of change of angle with respect to time, which we denote by
    the Greek letter ω.
  original_text_hash: sha256:043be2b4d0513ef692ea7a0673196dd92e7de1b0bbb9d2610ee444f445b89a44
  language: en
  reviewed_translation: 각속력은 시간에 대한 각도의 변화율의 크기이며 그리스 문자 ω로 나타낸다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This is a kinematic definition and does not alone determine a coating outcome.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.physics.rotation_angular_speed
      purpose: The angular speed is the magnitude of the rate of change of angle with
        respect to time, which we denote by the Greek letter ω.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This is a kinematic definition and does not alone determine a coating outcome.
  claim_scope_hash: sha256:8b7f2740058ac6063146408f5579fb0a22ea1def9f34c3a6a3401b0df0e39613
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
