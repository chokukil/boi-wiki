---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'materials: diffusion-arrhenius'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- materials
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:materials:diffusion-arrhenius
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
  evidence_id: sci-evidence:materials:diffusion-arrhenius
  source_id: sci-source:mit-3-091
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    content_hash: sha256:ded3970444be9ed9b62f3aef4d90f3ece6687caf336a6894a0b6a17723f6300a
    section: Recitation 26 — Arrhenius relationship
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    resolved_url: https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 1
    printed_page: PDF page 2
    hash_scope: retrieved_pdf_bytes
    equation: D = D₀e^(−Eₐ/(kBT))
    transcription_method: manual visual transcription of the typeset equation; no OCR substitution
  original_text: The energy required for diffusion to occur can be thought of as an activation energy. The diffusion coefficient
    is D = D₀e^(−Eₐ/(kBT)).
  original_text_hash: sha256:5dcaf1d7d06a198aceaaacc838bf5c0231692b6ec6f06ab6062a98cd8c7ea040
  language: en
  reviewed_translation: 확산에 필요한 에너지는 활성화에너지로 볼 수 있으며, 확산계수는 D = D₀e^(−Eₐ/(kBT))의 Arrhenius 관계로 나타낸다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The equation states an Arrhenius model; D₀, Eₐ, mechanism, temperature range, and material phase must be supplied for
    quantitative use.
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
