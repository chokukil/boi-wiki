---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "type": "boi/reference",
  "title": "Independent sealed holdout contract",
  "description": "Non-authorizing operating contract for externally sealed Science Release holdouts",
  "tags": [
    "ScienceVerifier",
    "Holdout",
    "Qualification"
  ],
  "timestamp": "2026-08-25T16:00:00+09:00",
  "boi_id": "boi:public:science:holdout-contract:0.1",
  "visibility": "public",
  "classification": "internal",
  "owner": "science-admin",
  "author": {
    "type": "agent",
    "agent_id": "codex"
  },
  "acl_policy": "acl:public",
  "status": "draft",
  "source_refs": [
    {
      "type": "boi",
      "ref": "boi:public:science:release:0.1.0"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  }
}
---
# Independent sealed holdout contract

This directory contains only the public manifest and audit identity for an
independent holdout. The held-out claims remain in the ACL-controlled external
location named by `external_acl_url`; they are not copied into this repository.

The checked-in `manifest.md` is intentionally pending and grants no authority.
G5 can pass only after the stored manifest is replaced by the closed
`science-holdout/0.1` sealed form and an independent trust resolver confirms its
exact SHA-256 digest and Rule-freeze commit.

A sealed result is bound to all of the following:

- the exact `release_id`;
- the Candidate's `frozen_release_content_hash`, preserved by the later active
  Release;
- a lifecycle-independent `decision_material_digest` recomputed from the
  Release's component identities, component digests, Rule semantic digests, and
  known limitations;
- the complete component digest map and Rule semantic digest map;
- the sealed case-set digest, positive case count, exact result digest, and G5
  `passed` state.

The holdout must be sealed after the Candidate decision material is frozen and
before Admin activation. The independent reviewer must be a human whose
`science.independent_holdout_reviewer` role is resolved by the trusted identity
provider, and must be distinct from every author, approver, and activator.
Locally authored role strings, caller-provided paths, pending manifests,
untrusted digests, changed decision material, self-review, or failing results
all fail closed and cannot issue an operational Rule capability.
