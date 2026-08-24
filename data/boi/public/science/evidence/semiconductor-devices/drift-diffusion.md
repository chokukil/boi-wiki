---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'semiconductor-devices: drift-diffusion'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- semiconductor-devices
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:semiconductor-devices:drift-diffusion
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
  evidence_id: sci-evidence:semiconductor-devices:drift-diffusion
  source_id: sci-source:chenming-hu-devices
  locator:
    medium: pdf
    resource_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    content_hash: sha256:af37b00ce074935c54c88d27af5c8dceac5bc9b900085ef66c1e863b0b291e98
    section: Chapter 2, 2.3 Diffusion Current
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    resolved_url: https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 11
    printed_page: PDF page 12
    hash_scope: retrieved_pdf_bytes
  original_text: In addition to the drift current, there is a second component of current called the diffusion current.
  original_text_hash: sha256:809f9386b483e176d3733fad6d6917837ae76e3effbc47c9bf60c35bc78cd6ca
  language: en
  reviewed_translation: 드리프트 전류 외에 확산 전류라는 두 번째 전류 성분이 있다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The relative contribution requires carrier gradients, fields, material parameters, and boundary conditions.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.semiconductor_devices.drift_diffusion
      purpose: In addition to the drift current, there is a second component of current
        called the diffusion current.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - The relative contribution requires carrier gradients, fields, material parameters,
      and boundary conditions.
  claim_scope_hash: sha256:a8dc33a40096699ec2c84e504811b97b87e1c6ce65d84b22dfa2a7b017825a7d
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
