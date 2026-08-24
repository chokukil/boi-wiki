---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'spin-coating: vendor-spin-curve-observation'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- spin-coating
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:spin-coating:vendor-spin-curve-observation
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
  evidence_id: sci-evidence:spin-coating:vendor-spin-curve-observation
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
    figure: Unnumbered spin curve under COATING GUIDELINES
    visual_transcription_scope: axis labels and legend labels only
  original_text: Film Thickness (µm) Spin Speed (rpm) AZ 125nXT-10 B AZ 125nXT-7 B
  original_text_hash: sha256:7c156fb15f79237d9172fd263bc232e5a42ef78a7838d884d4f594313280bbe0
  language: en
  reviewed_translation: 막 두께(µm)-스핀 속도(rpm) 그래프에는 AZ 125nXT-10 B와 AZ 125nXT-7 B 두 계열이 표시되어 있다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - Product-scoped to AZ 125nXT revision 01/24 and the displayed figure; it is not a universal spin-coating law.
  - The pinned exact span records only axis and series labels; it does not assert curve direction, numeric data points, range,
    or recipe.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.spin_coating.vendor_figure_labels
      purpose: Film Thickness (µm) Spin Speed (rpm) AZ 125nXT-10 B AZ 125nXT-7 B
      required_conditions: []
    forbidden_claim_families:
    - spin_coating.rpm_thickness_direction
    - spin_coating.numeric_curve_or_recipe
    - unbounded_or_unqualified_claims
    limitations:
    - Product-scoped to AZ 125nXT revision 01/24 and the displayed figure; it is not
      a universal spin-coating law.
    - The pinned exact span records only axis and series labels; it does not assert
      curve direction, numeric data points, range, or recipe.
  claim_scope_hash: sha256:4387e1b8ce07b9fa276619b852c0f36dd88c240c67f1c7935615df67f09211c2
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
  evidence_kind: figure_observation
  figure_observation:
    x_axis:
      label: Spin Speed
      unit: rpm
    y_axis:
      label: Film Thickness
      unit: µm
    series_labels:
    - AZ 125nXT-10 B
    - AZ 125nXT-7 B
    extraction_method: manual visual transcription of axis and legend labels from PDF page 10; no curve interpretation or
      digitization
    review_method: agent visual transcription pending authorized Admin review
    limits:
    - the exact span stores labels only
    - no curve direction, range, individual point, interpolation, or extrapolation is asserted
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
