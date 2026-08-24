---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: correlation-causation'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:correlation-causation
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
  ref: boi:public:science:source:nist-statistics-handbook
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:common:correlation-causation
  source_id: sci-source:nist-statistics-handbook
  locator:
    medium: html
    resource_url: https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm
    content_hash: sha256:bb8c05ff96594588303e4e5762542872f5cec445b0fb20d144338998393e97f9
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm
    resolved_url: https://www.itl.nist.gov/div898/handbook/ppc/section1/ppc136.htm
    preservation_status: checksum_only_no_archived_copy
    heading: Causality
    sentence_ordinal: 2
    prefix: There is a causal relationship between two variables if a change in the level of one variable causes a change
      in the other variable.
    suffix: When this is the case it is usually because there is a third (possibly unknown) causal factor.
    retrieved_resource_hash: sha256:03ee162ba72d01067ae078f241825516030a683be973a4b52c2da96d62321b12
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: Note that correlation does not imply causality. It is possible for two variables to be associated with each
    other without one of them causing the observed behavior in the other.
  original_text_hash: sha256:d26f2ba0c82816c8808ec01f78d07b89e0ab5034e6c46ae31d48cab9c0d3ed67
  language: en
  reviewed_translation: 상관관계가 인과관계를 뜻하지는 않는다. 두 변수가 연관되어 있어도 한 변수가 다른 변수의 관찰된 거동을 일으키지 않을 수 있다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This does not exclude causation; it rejects inferring causation from correlation alone.
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
