---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: equilibrium'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:equilibrium
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
  ref: boi:public:science:source:mit-5-111
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:common:equilibrium
  source_id: sci-source:mit-5-111
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    content_hash: sha256:b4f3acdc101c11a99d079fcf68c4cee4f79576eaa6de00ba8b822259c49b7369
    section: Lecture Summary 19 — Chemical equilibrium
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    resolved_url: https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/a025a709ae3fa3312b5fbdc0ed7a49b1_lecnotes19.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 1
    printed_page: PDF page 2
    hash_scope: retrieved_pdf_bytes
  original_text: Chemical reactions reach a state of dynamic equilibrium in which the rates of forward and reverse reactions
    are equal and there is no net change in composition.
  original_text_hash: sha256:97e70ef9240cceb46a035411487ff8fa762fab61dc7a8f01f1171daf58e3db72
  language: en
  reviewed_translation: 화학 반응은 정반응과 역반응 속도가 같고 조성의 순변화가 없는 동적 평형 상태에 도달한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This chemical-equilibrium statement does not imply zero microscopic activity or universal equilibrium.
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
