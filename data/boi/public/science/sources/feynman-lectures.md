---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-source
title: The Feynman Lectures on Physics
description: Science Verifier v0.1 draft source record with retrieval and access provenance
tags:
- ScienceVerifier
- ScienceSource
timestamp: '2026-08-25T02:45:00+09:00'
boi_id: boi:public:science:source:feynman-lectures
visibility: public
classification: internal
owner: science-admin
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
- type: url
  ref: https://www.feynmanlectures.caltech.edu/
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  source_id: sci-source:feynman-lectures
  source_role: physics_reference
  title: The Feynman Lectures on Physics
  authors:
  - Richard P. Feynman
  - Robert B. Leighton
  - Matthew Sands
  edition_or_version: Official online edition; access response retrieved 2026-08-25
  original_url: https://www.feynmanlectures.caltech.edu/
  doi_url: ''
  retrieved_at: '2026-08-25T02:45:00+09:00'
  content_hash: sha256:f573075b71c32dd5a627feee7df17c43668ad219bc13299ba0e243717a90b83f
  hash_scope: access_response_not_source_body
  retrieval_status: access_limited
  access_note: Official Caltech site returned an automated-access block. The checksum covers that response, not the lectures;
    no decision evidence is derived.
  license_note: The website terms and copyright apply; no lecture text is copied.
  curation_actor:
    type: agent
    agent_id: codex
  curated_at: '2026-08-25T03:26:00+09:00'
  release_eligibility: blocked_pending_authorized_admin_review
  requested_url: https://www.feynmanlectures.caltech.edu/
  resolved_url: https://www.feynmanlectures.caltech.edu/
  preservation_status: checksum_only_no_archived_copy
  preservation_ref: ''
  retrieval_actor:
    type: agent
    agent_id: codex
---

# Source record

This agent-curated draft records retrieval identity, access limits, and licensing context. It is not decision evidence and cannot enter an active release until an authorized Admin review event is recorded.
