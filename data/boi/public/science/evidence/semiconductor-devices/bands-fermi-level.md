---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: bands-fermi-level'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:bands-fermi-level
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
  evidence_id: sci-evidence:semiconductor-devices:bands-fermi-level
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch1-3.pdf
    content_hash: sha256:a2b23190ac7efbe97868a470ee796c848730fb5374790bc4d162f16fef4d897d
    section: Chapter 1, 1.7 Fermi Function
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch1-3.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch1-3.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 16
    printed_page: PDF page 17
    hash_scope: retrieved_pdf_bytes
  original_text: EF is called the Fermi energy or the Fermi level. f(E) is the probability of a state at energy E being occupied
    by an electron.
  original_text_hash: sha256:a95c9ab1196e8d319ffa27f9184d4d4624e67327b19b1011a52347093df8d0e8
  language: en
  reviewed_translation: EF를 페르미 에너지 또는 페르미 준위라 한다. f(E)는 에너지 E의 상태를 전자가 점유할 확률이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The occupation probability depends on the full Fermi function and its temperature assumptions.
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
