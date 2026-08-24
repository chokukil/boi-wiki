---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'spin-coating: vendor-spin-time-guidance'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- spin-coating
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:spin-coating:vendor-spin-time-guidance
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
  ref: boi:public:science:source:merck-az-125nxt-01-24
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:spin-coating:vendor-spin-time-guidance
  source_id: sci-source:merck-az-125nxt-01-24
  locator:
    medium: pdf
    resource_url: https://www.microchemicals.com/dokumente/datenblaetter/tds/merck/en/tds_az_125nxt_serie.pdf
    requested_url: https://www.microchemicals.com/dokumente/datenblaetter/tds/merck/en/tds_az_125nxt_serie.pdf
    resolved_url: https://www.microchemicals.com/dokumente/datenblaetter/tds/merck/en/tds_az_125nxt_serie.pdf
    content_hash: sha256:61b72e69a722c8abe495648809448f003c769165cf42a5405c4d7359f311efcb
    hash_scope: retrieved_pdf_bytes
    pdf_page_index: 9
    printed_page: PDF page 10
    section: COATING GUIDELINES
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    preservation_status: checksum_only_no_archived_copy
    sentence_label: spin-time guidance immediately above the spin curves
  original_text: Due to the slow drying characteristics of thick resists like AZ 125nXT, films will continue to thin with
    extended spin times.
  original_text_hash: sha256:1554ccbca1d7cc4a24c10c1b9ee6b1e461cf827fade78d1e160e2478214a1378
  language: en
  reviewed_translation: AZ 125nXT 같은 후막 레지스트는 건조가 느리므로 스핀 시간이 길어지면 막이 계속 얇아진다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Product-scoped to AZ 125nXT revision 01/24. This prose supports a spin-time statement only and supplies no RPM-to-thickness
    direction or recipe authorization.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: spin_coating.spin_time_thinning.product_scoped
      purpose: For the cited AZ 125nXT document, extended spin time is associated with
        continued thinning.
      required_conditions:
      - key: product_family
        operator: eq
        value: AZ 125nXT
      - key: source_revision
        operator: eq
        value: 01/24
    forbidden_claim_families:
    - spin_coating.rpm_thickness_direction
    - spin_coating.spin_speed_thickness_direction
    limitations:
    - Product-scoped to AZ 125nXT revision 01/24. This prose supports a spin-time statement
      only and supplies no RPM-to-thickness direction or recipe authorization.
  claim_scope_hash: sha256:76ba741670e239be16a398ec50aaea3c6267159f0ef572f17963513510dfc306
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
