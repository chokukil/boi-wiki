---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'physics: work-energy-power'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- physics
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:physics:work-energy-power
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
  evidence_id: sci-evidence:physics:work-energy-power
  source_id: sci-source:mit-8-01sc
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf
    content_hash: sha256:a6bf0626b4c9446a7b6aec206024b90f611403eb059a8dd7ffc45fe1a98fec00
    section: 13.6 Work-Kinetic Energy Theorem
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf
    resolved_url: https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 16
    printed_page: printed 13-16; PDF page 17
    hash_scope: retrieved_pdf_bytes
  original_text: the work done by the applied force on an object is identically equal to the change in kinetic energy of the
    object.
  original_text_hash: sha256:a89023544a44dc493b7d3bd17bf459fd113b891c82e1051049cee3b60a44d361
  language: en
  reviewed_translation: 물체에 가한 힘이 한 일은 그 물체의 운동에너지 변화와 동일하다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This span states the work–kinetic-energy theorem; separate definitions are needed for power and multi-energy balances.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.physics.work_energy_power
      purpose: the work done by the applied force on an object is identically equal
        to the change in kinetic energy of the object.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This span states the work–kinetic-energy theorem; separate definitions are needed
      for power and multi-energy balances.
  claim_scope_hash: sha256:b0ad6297d6084cc3943e15f50e4832ef1bf2bbd0d587067ee5d8c3327e71dce7
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
