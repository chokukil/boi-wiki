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
  - Approximate visual ranges are not digitized data and cannot authorize a numeric recipe or extrapolation.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: spin_coating.rpm_thickness_direction.product_scoped_figure_observation
      purpose: Both plotted AZ 125nXT grades show decreasing thickness as spin speed increases across their displayed markers.
      required_conditions:
      - Product scope is AZ 125nXT grades AZ 125nXT-10 B and AZ 125nXT-7 B.
      - Source revision is 01/24.
      - Use is limited to the visually observed plotted marker ranges recorded in figure_observation.
      - No numeric recipe, interpolation, or extrapolation is authorized.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Product-scoped to AZ 125nXT revision 01/24 and the displayed figure; it is not a universal spin-coating law.
    - Approximate visual ranges are not digitized data and cannot authorize a numeric recipe or extrapolation.
  claim_scope_hash: sha256:5e6b5a82b75b24774e1bd6c4e94229408e46bb1d8c628fe84a34d7392346af8b
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
      labeled_tick_range:
        from: 200
        to: 2600
      plot_boundary_extends_beyond_labeled_max: true
    y_axis:
      label: Film Thickness
      unit: µm
      labeled_tick_range:
        from: 0
        to: 120
      plot_boundary_extends_above_labeled_max: true
    series:
    - label: AZ 125nXT-10 B
      visually_observed_plotted_range:
        spin_speed_rpm:
          approximately_from: 600
          approximately_to: 2500
        film_thickness_um:
          approximately_from: 37
          approximately_to: 120
      observed_direction: thickness decreases as spin speed increases across the plotted markers
    - label: AZ 125nXT-7 B
      visually_observed_plotted_range:
        spin_speed_rpm:
          approximately_from: 600
          approximately_to: 2300
        film_thickness_um:
          approximately_from: 15
          approximately_to: 57
      observed_direction: thickness decreases as spin speed increases across the plotted markers
    extraction_method: manual visual inspection of PDF page 10 and its raster rendering; no curve digitization or interpolation
    review_method: agent visual transcription pending authorized Admin review
    limits:
    - axis and series ranges are approximate visual bounds
    - no individual point values are asserted
    - no extrapolation outside plotted markers
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
