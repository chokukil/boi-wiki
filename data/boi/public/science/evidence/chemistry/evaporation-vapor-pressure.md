---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'chemistry: evaporation-vapor-pressure'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- chemistry
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:chemistry:evaporation-vapor-pressure
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
  evidence_id: sci-evidence:chemistry:evaporation-vapor-pressure
  source_id: sci-source:chem1-virtual-textbook
  locator:
    medium: html
    resource_url: https://www.chem1.com/acad/webtext/states/changes.html
    content_hash: sha256:b9d69f868f61c6473b552ad74ec119691f7fb34066d69b43ef988dd1cae16c55
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chem1.com/acad/webtext/states/changes.html
    resolved_url: https://www.chem1.com/acad/webtext/states/changes.html
    preservation_status: checksum_only_no_archived_copy
    heading: Escaping tendency from a phase
    sentence_ordinal: 2
    prefix: “vapor pressure” of the liquid or solid.
    suffix: Note carefully that if the container is left open to the air, it is unlikely that many of the molecules in the
      vapor phase will return to the liquid phase.
    retrieved_resource_hash: sha256:2c1d6544d6edd0218edc835ceedbdb865639795d8ab6dd9ada021dc9d4ce981c
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: The vapor pressure is a direct measure of the escaping tendency of molecules from a condensed state of matter.
  original_text_hash: sha256:dbce87703720dbd37d2cd451ccf39ea5547984ae233724116e1ae2a6aca8e281
  language: en
  reviewed_translation: 증기압은 응축상에서 분자가 벗어나려는 경향을 직접 나타낸다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This does not alone determine an evaporation rate in an open, flowing process.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.chemistry.evaporation_vapor_pressure
      purpose: The vapor pressure is a direct measure of the escaping tendency of molecules from a condensed state of matter.
      required_conditions:
      - Authorized Admin review is still required before any active release use.
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This does not alone determine an evaporation rate in an open, flowing process.
  claim_scope_hash: sha256:23ab2ee4cf68d6709329a80f98ad0e804d88df4c43fe26162ee1210f1ab29744
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
