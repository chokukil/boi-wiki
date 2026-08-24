---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'chemistry: amount-concentration'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- chemistry
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:chemistry:amount-concentration
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
  evidence_id: sci-evidence:chemistry:amount-concentration
  source_id: sci-source:chem1-virtual-textbook
  locator:
    medium: html
    resource_url: https://www.chem1.com/acad/webtext/solut/solut-1.html
    content_hash: sha256:f40fc5c0ec0afb3ebb34d21bc2eab905c3675348bf432503256d2fe94eea0013
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://www.chem1.com/acad/webtext/solut/solut-1.html
    resolved_url: https://www.chem1.com/acad/webtext/solut/solut-1.html
    preservation_status: checksum_only_no_archived_copy
    heading: 'Molarity: mole/volume basis'
    sentence_ordinal: 2
    prefix: This is the method most used by chemists to express concentration, and it is the one most important for you to
      master.
    suffix: The important point to remember is that the volume of the solution is different from the volume of the solvent;
    retrieved_resource_hash: sha256:53dd0dd0907cbc911738b1fe0a4a1268bb22ec4c562077d687389486f80f7c1d
    hash_scope: utf8_sha256_prefix_lf_original_lf_suffix
  original_text: Molar concentration (molarity) is the number of moles of solute per liter of solution.
  original_text_hash: sha256:cc6e5355ca7ec415eee52ffffb29d2591a01e1e5f78d8ba0416fb38a3b5c11f3
  language: en
  reviewed_translation: 몰농도(몰러리티)는 용액 1리터당 용질의 몰수다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This defines molarity; it is not a definition of every concentration convention.
  claim_scope:
    schema_version: '0.1'
    allowed_claims:
    - claim_family: locator_bound.chemistry.amount_concentration
      purpose: Molar concentration (molarity) is the number of moles of solute per liter
        of solution.
      required_conditions: []
    forbidden_claim_families:
    - unbounded_or_unqualified_claims
    limitations:
    - This defines molarity; it is not a definition of every concentration convention.
  claim_scope_hash: sha256:bc9aa27c6f74f140d80b665094cf71a1df1e6969259b49d9b093499d95f2aaf8
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
