---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: mos-capacitor'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:mos-capacitor
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
  evidence_id: sci-evidence:semiconductor-devices:mos-capacitor
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch5-1.pdf
    content_hash: sha256:df4b86698b17f084d4a92179662a8d780756694b78c664e03118845dc1cbfdd0
    section: Chapter 5 — MOS Capacitor
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch5-1.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch5-1.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 0
    printed_page: PDF page 1
    hash_scope: retrieved_pdf_bytes
  original_text: An MOS capacitor (Fig. 5–1) is made of a semiconductor body or substrate, an insulator film, such as SiO2,
    and a metal electrode called a gate.
  original_text_hash: sha256:7a9e16056ecc80db27d9222509f03820e1ce2e4db89de8bdeff99425d82a8221
  language: en
  reviewed_translation: MOS 커패시터는 반도체 바디 또는 기판, SiO2 같은 절연막, 게이트라 부르는 금속 전극으로 구성된다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This structural definition does not imply ideal zero leakage or specify a C–V regime.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.semiconductor_devices.mos_capacitor
      purpose: An MOS capacitor (Fig. 5–1) is made of a semiconductor body or substrate,
        an insulator film, such as SiO2, and a metal electrode called a gate.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This structural definition does not imply ideal zero leakage or specify a C–V
      regime.
  claim_scope_hash: sha256:cd7c5d70fe9ed1dd689f5488041fd778a836b76b3b1e48c7b04467ac0a93749f
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
