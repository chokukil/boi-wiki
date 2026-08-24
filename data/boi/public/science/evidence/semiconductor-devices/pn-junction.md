---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: pn-junction'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:pn-junction
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
  ref: boi:public:science:source:chenming-hu-devices
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:semiconductor-devices:pn-junction
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch4-1.pdf
    content_hash: sha256:8bcaac25567807d8160f2929a3fd61798d7266ac032eb101567776869eed9103
    section: Chapter 4, 4.4 Forward Bias
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch4-1.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch4-1.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 16
    printed_page: PDF page 17
    hash_scope: retrieved_pdf_bytes
  original_text: a forward bias of V reduces the barrier height from φbi to φbi – V. This reduces the drift field and upsets
    the balance between diffusion and drift that exists at zero bias.
  original_text_hash: sha256:ab73caa63aef404d0c1fee85a842c2c7bdf07df6f58d2045e39bd2756f865ea4
  language: en
  reviewed_translation: 순방향 바이어스 V는 장벽 높이를 φbi에서 φbi−V로 낮춘다. 그 결과 드리프트 장이 감소하고 영 바이어스에서의 확산과 드리프트 균형이 깨진다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This statement uses the chapter's idealized junction treatment; high-level injection and nonideal effects are outside
    this span.
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
