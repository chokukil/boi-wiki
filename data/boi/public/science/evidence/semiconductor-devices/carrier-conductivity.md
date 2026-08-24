---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: carrier-conductivity'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:carrier-conductivity
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
  evidence_id: sci-evidence:semiconductor-devices:carrier-conductivity
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    content_hash: sha256:af37b00ce074935c54c88d27af5c8dceac5bc9b900085ef66c1e863b0b291e98
    section: Chapter 2, 2.2 Drift, equation (2.2.14)
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 9
    printed_page: printed page 44; PDF page 10
    hash_scope: retrieved_pdf_bytes
    equation: σ = qnµn + qpµp
    transcription_method: manual visual transcription of the typeset equation; symbols preserved
  original_text: The quantity in the parentheses is the conductivity, σ, of the semiconductor. σ = qnµn + qpµp
  original_text_hash: sha256:a7f286856b6d4fc93a51bd0d52a3888674e44d3b74a23e7901f9e68529c2e925
  language: en
  reviewed_translation: 괄호 안의 양은 반도체의 전도도 σ이며, σ = qnµn + qpµp이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This low-field drift conductivity relation requires carrier concentrations and mobilities under the model conditions;
    it is not a universal high-field transport law.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: semiconductor.low_field_carrier_conductivity
      purpose: The cited low-field relation expresses conductivity as σ = qnµn + qpµp.
      required_conditions:
      - Carrier concentrations and mobilities must correspond to the modeled state.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This low-field drift conductivity relation requires carrier concentrations and mobilities under the model conditions;
      it is not a universal high-field transport law.
  claim_scope_hash: sha256:29ac6a33e8003691c5e50fd9859e21f3c895ee1f6f843e619110930a8057cf13
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
