---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'materials: bulk-thin-film'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- materials
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:materials:bulk-thin-film
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
  ref: boi:public:science:source:mit-3-024
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:materials:bulk-thin-film
  source_id: sci-source:mit-3-024
  locator:
    medium: html
    resource_url: https://ocw.mit.edu/courses/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/
    content_hash: sha256:f35a38715b2809e3448f2a4bb9127e230c064b4a4368877a56bb20b1f2ff3015
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/
    resolved_url: https://ocw.mit.edu/courses/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/
    preservation_status: checksum_only_no_archived_copy
    heading: Course Description
    sentence_ordinal: 1
    prefix: Course Description
    suffix: It offers experimental exploration of the electronic, optical and magnetic properties of materials through hands-on
      experimentation and practical materials examples.
    retrieved_resource_hash: sha256:ac4d60b308d2682609876ee5f86d3e12cda9fc68fea3667c14507df7f62370ff
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: This course describes how electronic, optical and magnetic properties of materials originate from their electronic
    and molecular structure and how these properties can be designed for particular applications.
  original_text_hash: sha256:26057f630e8441febde66ca5977ac1e731ed708b40e58fb5a2166ca04bd560a6
  language: en
  reviewed_translation: 이 과목은 재료의 전자·광학·자기 성질이 전자 및 분자 구조에서 어떻게 기원하고 특정 응용에 맞게 설계될 수 있는지를 다룬다.
  decision_eligibility: inactive
  access_limitation: The stored course-scope span does not establish bulk/thin-film equivalence or a directional rule, so
    it is inactive decision context.
  contextual_limitations:
  - This scope statement does not establish a transferable bulk-to-thin-film property relation.
  claim_scope:
    schema_version: '0.1'
    allowed_claims: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This scope statement does not establish a transferable bulk-to-thin-film property
      relation.
  claim_scope_hash: sha256:da37aa3c6b471cb1c839558ef2f7a36ff2a7a530980af681eec0e4bb840b741b
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
