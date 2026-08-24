---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'spin-coating: meyerhofer-model'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- spin-coating
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:spin-coating:meyerhofer-model
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
  ref: boi:public:science:source:meyerhofer-1978
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:spin-coating:meyerhofer-model
  source_id: sci-source:meyerhofer-1978
  locator:
    medium: api_json
    resource_url: https://api.crossref.org/works/10.1063/1.325357
    content_hash: sha256:f5e25717581ac173950db3fc4404de4256d43372309ff0effe56444c399b400e
    section: Abstract metadata
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://api.crossref.org/works/10.1063/1.325357
    resolved_url: https://api.crossref.org/works/10.1063/1.325357
    preservation_status: checksum_only_no_archived_copy
    record_path: message
    field_path: message.abstract
    hash_scope: retrieved_api_response_bytes
  original_text: A model is presented for the description of thin films prepared from solution by spinning. Using only the
    centrifugal force, linear shear forces, and uniform evaporation of the solvent, the thickness of the film and the time
    of drying can be calculated as functions of the various processing parameters.
  original_text_hash: sha256:d236033f0611e6de36ecf89d9f62d95f41a4d560a9a015f4be855ab12d9c6dc4
  language: en
  reviewed_translation: 용액을 회전 도포해 만든 박막을 설명하는 모델을 제시한다. 원심력, 선형 전단력, 균일한 용매 증발만을 사용해 막 두께와 건조 시간을 여러 공정 변수의 함수로 계산할 수 있다고
    설명한다.
  decision_eligibility: inactive
  access_limitation: AIP full text returned HTTP 403. Crossref abstract metadata cannot enter an active decision path without
    lawful full-text locator review.
  contextual_limitations:
  - Only Crossref abstract metadata was inspected by the agent; the article equations, fit range, and experimental context were not.
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
