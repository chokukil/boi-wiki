---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: mos-gate-real-leakage'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:mos-gate-real-leakage
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
  evidence_id: sci-evidence:semiconductor-devices:mos-gate-real-leakage
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch7.pdf
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch7.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch7.pdf
    content_hash: sha256:757664105fef5191d9a6b3c91f8af7724e7c3400d3076b7a2108d15b4b4e224f
    hash_scope: retrieved_pdf_bytes
    pdf_page_index: 11
    printed_page: printed page 270; PDF page 12
    section: Chapter 7, 7.4 Gate Dielectric Scaling and Gate Leakage
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    preservation_status: checksum_only_no_archived_copy
  original_text: For SiO2 films thinner than 1.5 nm, tunneling leakage current becomes the most serious limiting factor.
  original_text_hash: sha256:dc0ae0375875529d4d18601b2a415396767a2d9aaf01f7ab1163f09c234dc74b
  language: en
  reviewed_translation: SiO2 막이 1.5 nm보다 얇아지면 터널링 누설전류가 가장 심각한 제한 요인이 된다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The stated threshold and limiting mechanism are scoped to the cited SiO2 discussion; material stack, field, area, temperature,
    and device design still matter.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: semiconductor.mos_gate.ultrathin_sio2_tunneling_limit
      purpose: The cited source identifies tunneling leakage as a limiting factor for
        SiO2 below its stated thickness.
      required_conditions:
      - key: gate_dielectric
        operator: eq
        value: SiO2
      - key: oxide_thickness_nm
        operator: lt
        value: 1.5
        unit: nm
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - The stated threshold and limiting mechanism are scoped to the cited SiO2 discussion;
      material stack, field, area, temperature, and device design still matter.
  claim_scope_hash: sha256:c78e1c0cf0673ca59b0f4ae12dd5f722721826ab9eb752289cb5c64792b4f3bd
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
