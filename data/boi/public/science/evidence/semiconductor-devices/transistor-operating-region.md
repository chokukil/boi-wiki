---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: transistor-operating-region'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:transistor-operating-region
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
  evidence_id: sci-evidence:semiconductor-devices:transistor-operating-region
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch6-1.pdf
    content_hash: sha256:0aaf4ceecfc9f17d2e0d3162a4061472a949e83f65feedaebab3e0fc16c1c226
    section: Chapter 6 — MOSFET IV characteristics
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch6-1.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch6-1.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 16
    printed_page: PDF page 17
    hash_scope: retrieved_pdf_bytes
  original_text: The part of the IV curves with Vds << Vdsat is the linear region, and the part with Vds > Vdsat is the saturation
    region.
  original_text_hash: sha256:1269bb0655cde1365274af4227cc388ae618ae72dfb5d6b8e28b7e8c13651fff
  language: en
  reviewed_translation: IV 곡선에서 Vds가 Vdsat보다 매우 작은 부분은 선형 영역이고, Vds가 Vdsat보다 큰 부분은 포화 영역이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The named regions use the model and Vdsat definition in the source; short-channel effects can alter behavior.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.semiconductor_devices.transistor_operating_region
      purpose: The part of the IV curves with Vds << Vdsat is the linear region, and the part with Vds > Vdsat is the saturation
        region.
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - The named regions use the model and Vdsat definition in the source; short-channel effects can alter behavior.
  claim_scope_hash: sha256:30202bc9f448ae726f0f102084e46e5d190ea714661fdf5fa66b66403b1228be
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
