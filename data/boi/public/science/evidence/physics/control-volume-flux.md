---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'physics: control-volume-flux'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- physics
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:physics:control-volume-flux
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
  ref: boi:public:science:source:mit-2-25
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:physics:control-volume-flux
  source_id: sci-source:mit-2-25
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    content_hash: sha256:1fdf4743cd6f8ba3718bdc6029ef7f2721d0a5f1e506c3f86ad78578f5780b31
    section: 2.4 Relation between Material Volumes and Control Volumes
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    resolved_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 11
    printed_page: printed/PDF page 12
    hash_scope: retrieved_pdf_bytes
  original_text: Both forms A and B are valid for arbitrarily moving and deforming control volumes (i.e. control volumes that
    may be expanding, translating, accelerating, or whatever), and for unsteady as well as steady flows.
  original_text_hash: sha256:780658a4237062307dd4b44c9a810564b02a671fcccee8f94a4ea29d06463a0a
  language: en
  reviewed_translation: A형과 B형은 임의로 이동·변형하는 제어체적과 비정상·정상 유동 모두에 유효하다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The equations and sign convention in the source are required before calculating a flux balance.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.physics.control_volume_flux
      purpose: Both forms A and B are valid for arbitrarily moving and deforming control volumes (i.e. control volumes that
        may be expanding, translating, accelerating, or whatever), and for unsteady as well as steady flows.
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - The equations and sign convention in the source are required before calculating a flux balance.
  claim_scope_hash: sha256:1f30794153905b80eb5acf02b52078ef795deed5b5f53a0ef0913fea7966ae03
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
