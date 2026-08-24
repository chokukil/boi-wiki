---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "type": "boi/report",
  "title": "Science 0.1.0 independent holdout reservation",
  "description": "Non-authorizing manifest for a post-freeze external sealed holdout",
  "tags": [
    "ScienceVerifier",
    "Holdout",
    "Pending"
  ],
  "timestamp": "2026-08-25T16:00:00+09:00",
  "boi_id": "boi:public:science:holdout-manifest:0.1.0",
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
  },
  "science_holdout": {
    "manifest_version": "science-holdout/0.1",
    "release_id": "sci-release:0.1.0",
    "state": "pending_independent_commission",
    "external_acl_url": "boi-private://science-verifier/holdouts/science-release-0.1.0.json",
    "sealed_sha256": null,
    "rule_freeze_commit": null,
    "reviewer_role": "independent_science_reviewer",
    "minimum_cases_per_rule": 2,
    "expected_rule_count": 44,
    "expected_minimum_case_count": 88,
    "required_non_spin_majority": true,
    "required_case_families": [
      "violation",
      "false_red",
      "missing_condition",
      "ambiguity",
      "outside_validity_domain",
      "empirical_verification_required"
    ],
    "domain_distribution": {}
  }
}
---
# Science 0.1.0 independent holdout reservation

The actual holdout claims are not stored in this development tree. After Rule freeze, an independent reviewer writes them to the ACL-controlled external location. This reservation grants no review, approval, qualification, or activation authority.
