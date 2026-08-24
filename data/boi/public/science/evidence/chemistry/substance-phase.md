---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'chemistry: substance-phase'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- chemistry
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:chemistry:substance-phase
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
  evidence_id: sci-evidence:chemistry:substance-phase
  source_id: sci-source:chem1-virtual-textbook
  locator:
    medium: html
    resource_url: https://www.chem1.com/acad/webtext/pre/pre-1.html
    content_hash: sha256:5b0bdfaf7cee85c905ba2ecd3d00b7200de7cec5b059c7ba746135eb09334061
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chem1.com/acad/webtext/pre/pre-1.html
    resolved_url: https://www.chem1.com/acad/webtext/pre/pre-1.html
    preservation_status: checksum_only_no_archived_copy
    heading: Phases
    sentence_ordinal: 2
    prefix: To take this further, we first need to define "uniformity" in a more precise way, and this takes us to the concept
      of phases.
    suffix: A volume of water, a chunk of ice, a grain of sand, a piece of copper— each of these constitutes a single phase,
      and by the above definition, is said to be homogeneous.
    retrieved_resource_hash: sha256:6de75ebe0a6d699c7623e5346c6e80a566048ef1ba46a99701ec391a68814e38
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: A phase is a region of matter that possesses uniform intensive properties throughout its volume.
  original_text_hash: sha256:9ffc0ca5bc5697c30aac3bd829dbd48daf7ed0479e77a714ce2f505f36d39aaf
  language: en
  reviewed_translation: 상은 그 부피 전체에서 균일한 세기 성질을 갖는 물질 영역이다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - The operational boundary of a phase can depend on the property and observation scale.
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
