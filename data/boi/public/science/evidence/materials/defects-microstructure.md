---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'materials: defects-microstructure'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- materials
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:materials:defects-microstructure
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
  ref: boi:public:science:source:mit-3-091sc-2010
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:materials:defects-microstructure
  source_id: sci-source:mit-3-091sc-2010
  locator:
    medium: html
    resource_url: https://ocw.mit.edu/courses/3-091sc-introduction-to-solid-state-chemistry-fall-2010/pages/crystalline-materials/20-line-interface-and-bulk-defects/
    requested_url: https://ocw.mit.edu/courses/3-091sc-introduction-to-solid-state-chemistry-fall-2010/pages/crystalline-materials/20-line-interface-and-bulk-defects/
    resolved_url: https://ocw.mit.edu/courses/3-091sc-introduction-to-solid-state-chemistry-fall-2010/pages/crystalline-materials/20-line-interface-and-bulk-defects/
    content_hash: sha256:78fe6bee12cb5e39b2e587afed1f744747aff4678fcccf0c9b0863cb80355c16
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
    retrieved_resource_hash: sha256:e4771bdba765d4532dbccd551e6d1dff69220286925a908f65c2d7ed2ed23bcc
    heading: Lecture Summary
    sentence_ordinal: 2
    prefix: Two-dimensional defects can occur at the surface of crystals or at internal interfaces between zones with different
      lattice alignments, called grain boundaries.
    suffix: The failure of rivets on the hull of the Titanic is attributed to brittle pockets of slag mixed into the steel,
      based on examination of the microstructure.
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    preservation_status: checksum_only_no_archived_copy
  original_text: Macroscopic clusters of vacancies (voids) weaken metals, while clusters of impurities (precipitates) may
    weaken or strengthen them.
  original_text_hash: sha256:697e762eaaae8e63356a933c7b031ab5dfeeff0c4847862b3bcb81e38269e591
  language: en
  reviewed_translation: 거시적인 공공(vacancy) 군집인 보이드는 금속을 약화시키며, 불순물 군집인 석출물은 금속을 약화시키거나 강화할 수 있다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This is a qualitative materials example. Effect direction depends on defect type and microstructure; it does not supply
    a universal strength model.
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
