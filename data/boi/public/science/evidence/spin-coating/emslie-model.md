---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'spin-coating: emslie-model'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- spin-coating
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:spin-coating:emslie-model
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
  ref: boi:public:science:source:emslie-1958
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:spin-coating:emslie-model
  source_id: sci-source:emslie-1958
  locator:
    medium: api_json
    resource_url: https://api.crossref.org/works/10.1063/1.1723300
    content_hash: sha256:3be7fb10cc46979dc0c4f21092ecedb35994cd574bffa14a241738a4ecdab364
    section: Abstract metadata
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://api.crossref.org/works/10.1063/1.1723300
    resolved_url: https://api.crossref.org/works/10.1063/1.1723300
    preservation_status: checksum_only_no_archived_copy
    record_path: message
    field_path: message.abstract
    hash_scope: retrieved_api_response_bytes
  original_text: It is shown that centrifugation of a fluid layer that is initially uniform does not disturb the uniformity
    as the height of the layer is reduced.
  original_text_hash: sha256:c87d8907967596e7b1521971ddb58ec8eead47c94afd71cd514806f73a4e5624
  language: en
  reviewed_translation: 초기에 균일한 유체층을 원심 회전시키면 층 높이가 감소하는 동안 그 균일성이 깨지지 않는다고 제시한다.
  decision_eligibility: inactive
  access_limitation: AIP full text returned HTTP 403. Crossref abstract metadata cannot enter an active decision path without
    lawful full-text locator review.
  contextual_limitations:
  - Only Crossref abstract metadata was inspected by the agent; equations, assumptions, pages, and article context were not available.
  claim_scope:
    schema_version: '0.1'
    allowed_claims: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - Only Crossref abstract metadata was inspected by the agent; equations, assumptions,
      pages, and article context were not available.
  claim_scope_hash: sha256:9acb6b1e25ecd0c95a9d5d1a386f6381b839ca5718b2ae47061ae36e50271f51
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
