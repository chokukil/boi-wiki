---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: mos-gate-ideal-model'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:mos-gate-ideal-model
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
  ref: boi:public:science:source:mit-6-012
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:semiconductor-devices:mos-gate-ideal-model
  source_id: sci-source:mit-6-012
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-fall-2009/eeb94eab00ebb62a3fde0eec1484bc08_MIT6_012F09_lec11_gradual.pdf
    requested_url: https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-fall-2009/eeb94eab00ebb62a3fde0eec1484bc08_MIT6_012F09_lec11_gradual.pdf
    resolved_url: https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-fall-2009/eeb94eab00ebb62a3fde0eec1484bc08_MIT6_012F09_lec11_gradual.pdf
    content_hash: sha256:83400b4045076b4f8536e1eac188482369009f47f6607c8e02be211fb16351f4
    hash_scope: retrieved_pdf_bytes
    pdf_page_index: 0
    printed_page: PDF page 1
    section: Gradual Channel Approximation
    equation: iG = 0
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    preservation_status: checksum_only_no_archived_copy
  original_text: Because of the insulating nature of the oxide beneath the gate, we also have iG = 0
  original_text_hash: sha256:c92d0867c6cfc590f6a176a9af90e4f113580f3442f8ee67e9ab3142b7e2d111
  language: en
  reviewed_translation: 게이트 아래 산화막을 절연체로 두는 이 모델에서는 게이트 전류 iG = 0으로 둔다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This is an idealized model assumption tied to an insulating gate oxide; it must not be generalized to all fabricated MOS
    gates.
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
