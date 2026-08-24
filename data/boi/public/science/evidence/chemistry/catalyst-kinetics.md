---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'chemistry: catalyst-kinetics'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- chemistry
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:chemistry:catalyst-kinetics
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
  ref: boi:public:science:source:chem1-virtual-textbook
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:chemistry:catalyst-kinetics
  source_id: sci-source:chem1-virtual-textbook
  locator:
    medium: html
    resource_url: https://www.chem1.com/acad/webtext/dynamics/dynamics-3.html
    content_hash: sha256:6ff584b285cabdff536de89f2d0bec764643c179c17d8916e56270d3de540f80
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chem1.com/acad/webtext/dynamics/dynamics-3.html
    resolved_url: https://www.chem1.com/acad/webtext/dynamics/dynamics-3.html
    preservation_status: checksum_only_no_archived_copy
    heading: Catalysts can reduce activation energy
    sentence_ordinal: 2
    prefix: In addition, most biochemical processes that occur in living organisms are mediated by enzymes, which are catalysts
      made of proteins.
    suffix: Thus there is a single value of ΔH for the two pathways depicted in the plot on the right.
    retrieved_resource_hash: sha256:480f1868f58389473dfa3c5131821f0ec3d42ff867eb4b1a533b7216261e3a65
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: It is important to understand that a catalyst affects only the kinetics of a reaction; it does not alter
    the thermodynamic tendency for the reaction to occur.
  original_text_hash: sha256:4b99fd9327cd0d4d546d18916aea9ad6d27d569b1488372b1ff16104fb44ec89
  language: en
  reviewed_translation: 촉매는 반응 속도론에만 영향을 주며, 반응이 일어나려는 열역학적 경향 자체를 바꾸지는 않는다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This span distinguishes kinetic effects from thermodynamic tendency; it does not quantify rate, equilibrium composition,
    or catalyst performance.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: chemistry.catalyst_affects_kinetics_not_thermodynamic_tendency
      purpose: A catalyst affects reaction kinetics and does not alter the thermodynamic tendency for the reaction to occur.
      required_conditions:
      - Do not infer numerical rate or equilibrium composition.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This span distinguishes kinetic effects from thermodynamic tendency; it does not quantify rate, equilibrium composition,
      or catalyst performance.
  claim_scope_hash: sha256:11c90874fc14ec2b7b1d7307e4e64e82e76f2db5b8c4858e003ca916852b95f7
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
