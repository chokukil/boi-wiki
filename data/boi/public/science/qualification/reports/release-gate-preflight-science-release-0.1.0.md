---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "type": "boi/report",
  "title": "Science Release 0.1.0 public preflight",
  "description": "Automated candidate-only G0..G4 preflight; no human approval or activation",
  "tags": [
    "ScienceVerifier",
    "Qualification",
    "ReleaseCandidate"
  ],
  "timestamp": "2026-08-25T16:00:00+09:00",
  "boi_id": "boi:public:science:qualification-report:release-0.1.0-preflight",
  "visibility": "public",
  "classification": "internal",
  "owner": "science-admin",
  "author": {
    "type": "agent",
    "agent_id": "science-qualification-runner"
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
  "science_qualification": {
    "release_id": "sci-release:0.1.0",
    "release_digest": "sha256:1dc6775741d7e1b9258ec91b48980e13995b561240e2a54b83e37f3912476bc7",
    "result_digest": "sha256:3e1a08b7fea4ff6809592338d09e3a12b207480fec780dfc54d0a35f753e56a7",
    "lifecycle": "release_candidate",
    "public_case_count": 440,
    "activation_eligible": false
  }
}
---
# Science Release 0.1.0 public preflight

> Candidate qualification only. This report is not a human review, approval, or active Science Release.

- Release ID: `sci-release:0.1.0`
- Release digest: `sha256:1dc6775741d7e1b9258ec91b48980e13995b561240e2a54b83e37f3912476bc7`
- Result digest: `sha256:3e1a08b7fea4ff6809592338d09e3a12b207480fec780dfc54d0a35f753e56a7`
- Lifecycle: `release_candidate`
- Public cases: 440
- activation_eligible: false

## Release gates

- G0 | PASS | Schema, IDs, references, immutable component digests, and candidate lifecycle are valid.
- G1 | PASS | Source/Evidence hashes and locator structures are internally reproducible.
- G2 | PASS | Every public decision remains inside release-pinned Knowledge and Evidence.
- G3 | PASS | All 440 public cases match their expected verdict or ambiguity gate.
- G4 | PASS | Repeated public qualification is byte-stable.
- G5 | PENDING | Independent sealed holdout is not commissioned.
- G6 | PENDING | Web/REST/MCP/explanation/export parity must be established by the authoritative post-integration checker; caller assertions cannot pass this gate.
- G7 | PENDING | Authorized human Admin review and activation must be resolved from the operational audit store; caller assertions cannot pass this gate.

## Failure inventory

- Missed violations: 0
- False-red: 0
- Wrong interpretations: 0
- Validity/range errors: 0
- Unsupported-scope errors: 0
- Broken Evidence locators: 0
- Ungrounded explanation facts: 0
- Nondeterministic cases: 0

## Case results

| Case | Kind | Rule | Expected | Actual | Deterministic |
|---|---|---|---|---|---|
| sci-case:chemistry:001:clear_violation | clear_violation | sci-rule:chemistry:001 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:chemistry:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:chemistry:001:empirical_verification_required | empirical_verification_required | sci-rule:chemistry:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:chemistry:001:false_red_prevention | false_red_prevention | sci-rule:chemistry:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:001:in_scope_consistency | in_scope_consistency | sci-rule:chemistry:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:001:missing_required_condition | missing_required_condition | sci-rule:chemistry:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:001:negation | negation | sci-rule:chemistry:001 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:001:outside_validity_domain | outside_validity_domain | sci-rule:chemistry:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:chemistry:001:paraphrase | paraphrase | sci-rule:chemistry:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:001:unit_variation | unit_variation | sci-rule:chemistry:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:002:clear_violation | clear_violation | sci-rule:chemistry:002 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:chemistry:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:chemistry:002:empirical_verification_required | empirical_verification_required | sci-rule:chemistry:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:chemistry:002:false_red_prevention | false_red_prevention | sci-rule:chemistry:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:002:in_scope_consistency | in_scope_consistency | sci-rule:chemistry:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:002:missing_required_condition | missing_required_condition | sci-rule:chemistry:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:002:negation | negation | sci-rule:chemistry:002 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:002:outside_validity_domain | outside_validity_domain | sci-rule:chemistry:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:chemistry:002:paraphrase | paraphrase | sci-rule:chemistry:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:002:unit_variation | unit_variation | sci-rule:chemistry:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:003:clear_violation | clear_violation | sci-rule:chemistry:003 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:chemistry:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:chemistry:003:empirical_verification_required | empirical_verification_required | sci-rule:chemistry:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:chemistry:003:false_red_prevention | false_red_prevention | sci-rule:chemistry:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:003:in_scope_consistency | in_scope_consistency | sci-rule:chemistry:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:003:missing_required_condition | missing_required_condition | sci-rule:chemistry:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:003:negation | negation | sci-rule:chemistry:003 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:003:outside_validity_domain | outside_validity_domain | sci-rule:chemistry:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:chemistry:003:paraphrase | paraphrase | sci-rule:chemistry:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:003:unit_variation | unit_variation | sci-rule:chemistry:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:004:clear_violation | clear_violation | sci-rule:chemistry:004 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:chemistry:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:chemistry:004:empirical_verification_required | empirical_verification_required | sci-rule:chemistry:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:chemistry:004:false_red_prevention | false_red_prevention | sci-rule:chemistry:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:004:in_scope_consistency | in_scope_consistency | sci-rule:chemistry:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:004:missing_required_condition | missing_required_condition | sci-rule:chemistry:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:004:negation | negation | sci-rule:chemistry:004 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:004:outside_validity_domain | outside_validity_domain | sci-rule:chemistry:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:chemistry:004:paraphrase | paraphrase | sci-rule:chemistry:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:004:unit_variation | unit_variation | sci-rule:chemistry:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:005:clear_violation | clear_violation | sci-rule:chemistry:005 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:chemistry:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:chemistry:005:empirical_verification_required | empirical_verification_required | sci-rule:chemistry:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:chemistry:005:false_red_prevention | false_red_prevention | sci-rule:chemistry:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:005:in_scope_consistency | in_scope_consistency | sci-rule:chemistry:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:005:missing_required_condition | missing_required_condition | sci-rule:chemistry:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:chemistry:005:negation | negation | sci-rule:chemistry:005 | VIOLATION | VIOLATION | yes |
| sci-case:chemistry:005:outside_validity_domain | outside_validity_domain | sci-rule:chemistry:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:chemistry:005:paraphrase | paraphrase | sci-rule:chemistry:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:chemistry:005:unit_variation | unit_variation | sci-rule:chemistry:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:001:clear_violation | clear_violation | sci-rule:circuits:001 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:001:empirical_verification_required | empirical_verification_required | sci-rule:circuits:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:001:false_red_prevention | false_red_prevention | sci-rule:circuits:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:001:in_scope_consistency | in_scope_consistency | sci-rule:circuits:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:001:missing_required_condition | missing_required_condition | sci-rule:circuits:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:001:negation | negation | sci-rule:circuits:001 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:001:outside_validity_domain | outside_validity_domain | sci-rule:circuits:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:001:paraphrase | paraphrase | sci-rule:circuits:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:001:unit_variation | unit_variation | sci-rule:circuits:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:002:clear_violation | clear_violation | sci-rule:circuits:002 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:002:empirical_verification_required | empirical_verification_required | sci-rule:circuits:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:002:false_red_prevention | false_red_prevention | sci-rule:circuits:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:002:in_scope_consistency | in_scope_consistency | sci-rule:circuits:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:002:missing_required_condition | missing_required_condition | sci-rule:circuits:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:002:negation | negation | sci-rule:circuits:002 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:002:outside_validity_domain | outside_validity_domain | sci-rule:circuits:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:002:paraphrase | paraphrase | sci-rule:circuits:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:002:unit_variation | unit_variation | sci-rule:circuits:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:003:clear_violation | clear_violation | sci-rule:circuits:003 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:003:empirical_verification_required | empirical_verification_required | sci-rule:circuits:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:003:false_red_prevention | false_red_prevention | sci-rule:circuits:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:003:in_scope_consistency | in_scope_consistency | sci-rule:circuits:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:003:missing_required_condition | missing_required_condition | sci-rule:circuits:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:003:negation | negation | sci-rule:circuits:003 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:003:outside_validity_domain | outside_validity_domain | sci-rule:circuits:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:003:paraphrase | paraphrase | sci-rule:circuits:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:003:unit_variation | unit_variation | sci-rule:circuits:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:004:clear_violation | clear_violation | sci-rule:circuits:004 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:004:empirical_verification_required | empirical_verification_required | sci-rule:circuits:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:004:false_red_prevention | false_red_prevention | sci-rule:circuits:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:004:in_scope_consistency | in_scope_consistency | sci-rule:circuits:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:004:missing_required_condition | missing_required_condition | sci-rule:circuits:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:004:negation | negation | sci-rule:circuits:004 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:004:outside_validity_domain | outside_validity_domain | sci-rule:circuits:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:004:paraphrase | paraphrase | sci-rule:circuits:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:004:unit_variation | unit_variation | sci-rule:circuits:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:005:clear_violation | clear_violation | sci-rule:circuits:005 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:005:empirical_verification_required | empirical_verification_required | sci-rule:circuits:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:005:false_red_prevention | false_red_prevention | sci-rule:circuits:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:005:in_scope_consistency | in_scope_consistency | sci-rule:circuits:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:005:missing_required_condition | missing_required_condition | sci-rule:circuits:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:005:negation | negation | sci-rule:circuits:005 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:005:outside_validity_domain | outside_validity_domain | sci-rule:circuits:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:005:paraphrase | paraphrase | sci-rule:circuits:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:005:unit_variation | unit_variation | sci-rule:circuits:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:006:clear_violation | clear_violation | sci-rule:circuits:006 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:006:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:circuits:006 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:circuits:006:empirical_verification_required | empirical_verification_required | sci-rule:circuits:006 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:circuits:006:false_red_prevention | false_red_prevention | sci-rule:circuits:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:006:in_scope_consistency | in_scope_consistency | sci-rule:circuits:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:006:missing_required_condition | missing_required_condition | sci-rule:circuits:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:circuits:006:negation | negation | sci-rule:circuits:006 | VIOLATION | VIOLATION | yes |
| sci-case:circuits:006:outside_validity_domain | outside_validity_domain | sci-rule:circuits:006 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:circuits:006:paraphrase | paraphrase | sci-rule:circuits:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:circuits:006:unit_variation | unit_variation | sci-rule:circuits:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:001:clear_violation | clear_violation | sci-rule:common:001 | VIOLATION | VIOLATION | yes |
| sci-case:common:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:001:empirical_verification_required | empirical_verification_required | sci-rule:common:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:001:false_red_prevention | false_red_prevention | sci-rule:common:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:001:in_scope_consistency | in_scope_consistency | sci-rule:common:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:001:missing_required_condition | missing_required_condition | sci-rule:common:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:001:negation | negation | sci-rule:common:001 | VIOLATION | VIOLATION | yes |
| sci-case:common:001:outside_validity_domain | outside_validity_domain | sci-rule:common:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:001:paraphrase | paraphrase | sci-rule:common:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:001:unit_variation | unit_variation | sci-rule:common:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:002:clear_violation | clear_violation | sci-rule:common:002 | VIOLATION | VIOLATION | yes |
| sci-case:common:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:002:empirical_verification_required | empirical_verification_required | sci-rule:common:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:002:false_red_prevention | false_red_prevention | sci-rule:common:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:002:in_scope_consistency | in_scope_consistency | sci-rule:common:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:002:missing_required_condition | missing_required_condition | sci-rule:common:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:002:negation | negation | sci-rule:common:002 | VIOLATION | VIOLATION | yes |
| sci-case:common:002:outside_validity_domain | outside_validity_domain | sci-rule:common:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:002:paraphrase | paraphrase | sci-rule:common:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:002:unit_variation | unit_variation | sci-rule:common:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:003:clear_violation | clear_violation | sci-rule:common:003 | VIOLATION | VIOLATION | yes |
| sci-case:common:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:003:empirical_verification_required | empirical_verification_required | sci-rule:common:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:003:false_red_prevention | false_red_prevention | sci-rule:common:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:003:in_scope_consistency | in_scope_consistency | sci-rule:common:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:003:missing_required_condition | missing_required_condition | sci-rule:common:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:003:negation | negation | sci-rule:common:003 | VIOLATION | VIOLATION | yes |
| sci-case:common:003:outside_validity_domain | outside_validity_domain | sci-rule:common:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:003:paraphrase | paraphrase | sci-rule:common:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:003:unit_variation | unit_variation | sci-rule:common:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:004:clear_violation | clear_violation | sci-rule:common:004 | VIOLATION | VIOLATION | yes |
| sci-case:common:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:004:empirical_verification_required | empirical_verification_required | sci-rule:common:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:004:false_red_prevention | false_red_prevention | sci-rule:common:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:004:in_scope_consistency | in_scope_consistency | sci-rule:common:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:004:missing_required_condition | missing_required_condition | sci-rule:common:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:004:negation | negation | sci-rule:common:004 | VIOLATION | VIOLATION | yes |
| sci-case:common:004:outside_validity_domain | outside_validity_domain | sci-rule:common:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:004:paraphrase | paraphrase | sci-rule:common:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:004:unit_variation | unit_variation | sci-rule:common:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:005:clear_violation | clear_violation | sci-rule:common:005 | VIOLATION | VIOLATION | yes |
| sci-case:common:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:005:empirical_verification_required | empirical_verification_required | sci-rule:common:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:005:false_red_prevention | false_red_prevention | sci-rule:common:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:005:in_scope_consistency | in_scope_consistency | sci-rule:common:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:005:missing_required_condition | missing_required_condition | sci-rule:common:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:005:negation | negation | sci-rule:common:005 | VIOLATION | VIOLATION | yes |
| sci-case:common:005:outside_validity_domain | outside_validity_domain | sci-rule:common:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:005:paraphrase | paraphrase | sci-rule:common:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:005:unit_variation | unit_variation | sci-rule:common:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:006:clear_violation | clear_violation | sci-rule:common:006 | VIOLATION | VIOLATION | yes |
| sci-case:common:006:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:006 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:006:empirical_verification_required | empirical_verification_required | sci-rule:common:006 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:006:false_red_prevention | false_red_prevention | sci-rule:common:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:006:in_scope_consistency | in_scope_consistency | sci-rule:common:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:006:missing_required_condition | missing_required_condition | sci-rule:common:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:006:negation | negation | sci-rule:common:006 | VIOLATION | VIOLATION | yes |
| sci-case:common:006:outside_validity_domain | outside_validity_domain | sci-rule:common:006 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:006:paraphrase | paraphrase | sci-rule:common:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:006:unit_variation | unit_variation | sci-rule:common:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:007:clear_violation | clear_violation | sci-rule:common:007 | VIOLATION | VIOLATION | yes |
| sci-case:common:007:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:007 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:007:empirical_verification_required | empirical_verification_required | sci-rule:common:007 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:007:false_red_prevention | false_red_prevention | sci-rule:common:007 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:007:in_scope_consistency | in_scope_consistency | sci-rule:common:007 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:007:missing_required_condition | missing_required_condition | sci-rule:common:007 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:007:negation | negation | sci-rule:common:007 | VIOLATION | VIOLATION | yes |
| sci-case:common:007:outside_validity_domain | outside_validity_domain | sci-rule:common:007 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:007:paraphrase | paraphrase | sci-rule:common:007 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:007:unit_variation | unit_variation | sci-rule:common:007 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:008:clear_violation | clear_violation | sci-rule:common:008 | VIOLATION | VIOLATION | yes |
| sci-case:common:008:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:008 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:008:empirical_verification_required | empirical_verification_required | sci-rule:common:008 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:008:false_red_prevention | false_red_prevention | sci-rule:common:008 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:008:in_scope_consistency | in_scope_consistency | sci-rule:common:008 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:008:missing_required_condition | missing_required_condition | sci-rule:common:008 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:008:negation | negation | sci-rule:common:008 | VIOLATION | VIOLATION | yes |
| sci-case:common:008:outside_validity_domain | outside_validity_domain | sci-rule:common:008 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:008:paraphrase | paraphrase | sci-rule:common:008 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:008:unit_variation | unit_variation | sci-rule:common:008 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:009:clear_violation | clear_violation | sci-rule:common:009 | VIOLATION | VIOLATION | yes |
| sci-case:common:009:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:009 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:009:empirical_verification_required | empirical_verification_required | sci-rule:common:009 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:009:false_red_prevention | false_red_prevention | sci-rule:common:009 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:009:in_scope_consistency | in_scope_consistency | sci-rule:common:009 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:009:missing_required_condition | missing_required_condition | sci-rule:common:009 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:009:negation | negation | sci-rule:common:009 | VIOLATION | VIOLATION | yes |
| sci-case:common:009:outside_validity_domain | outside_validity_domain | sci-rule:common:009 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:009:paraphrase | paraphrase | sci-rule:common:009 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:009:unit_variation | unit_variation | sci-rule:common:009 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:010:clear_violation | clear_violation | sci-rule:common:010 | VIOLATION | VIOLATION | yes |
| sci-case:common:010:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:010 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:010:empirical_verification_required | empirical_verification_required | sci-rule:common:010 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:010:false_red_prevention | false_red_prevention | sci-rule:common:010 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:010:in_scope_consistency | in_scope_consistency | sci-rule:common:010 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:010:missing_required_condition | missing_required_condition | sci-rule:common:010 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:010:negation | negation | sci-rule:common:010 | VIOLATION | VIOLATION | yes |
| sci-case:common:010:outside_validity_domain | outside_validity_domain | sci-rule:common:010 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:010:paraphrase | paraphrase | sci-rule:common:010 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:010:unit_variation | unit_variation | sci-rule:common:010 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:011:clear_violation | clear_violation | sci-rule:common:011 | VIOLATION | VIOLATION | yes |
| sci-case:common:011:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:011 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:011:empirical_verification_required | empirical_verification_required | sci-rule:common:011 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:011:false_red_prevention | false_red_prevention | sci-rule:common:011 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:011:in_scope_consistency | in_scope_consistency | sci-rule:common:011 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:011:missing_required_condition | missing_required_condition | sci-rule:common:011 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:011:negation | negation | sci-rule:common:011 | VIOLATION | VIOLATION | yes |
| sci-case:common:011:outside_validity_domain | outside_validity_domain | sci-rule:common:011 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:011:paraphrase | paraphrase | sci-rule:common:011 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:011:unit_variation | unit_variation | sci-rule:common:011 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:012:clear_violation | clear_violation | sci-rule:common:012 | VIOLATION | VIOLATION | yes |
| sci-case:common:012:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:common:012 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:common:012:empirical_verification_required | empirical_verification_required | sci-rule:common:012 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:common:012:false_red_prevention | false_red_prevention | sci-rule:common:012 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:012:in_scope_consistency | in_scope_consistency | sci-rule:common:012 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:012:missing_required_condition | missing_required_condition | sci-rule:common:012 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:common:012:negation | negation | sci-rule:common:012 | VIOLATION | VIOLATION | yes |
| sci-case:common:012:outside_validity_domain | outside_validity_domain | sci-rule:common:012 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:common:012:paraphrase | paraphrase | sci-rule:common:012 | CONSISTENT | CONSISTENT | yes |
| sci-case:common:012:unit_variation | unit_variation | sci-rule:common:012 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:001:clear_violation | clear_violation | sci-rule:materials:001 | VIOLATION | VIOLATION | yes |
| sci-case:materials:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:materials:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:materials:001:empirical_verification_required | empirical_verification_required | sci-rule:materials:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:materials:001:false_red_prevention | false_red_prevention | sci-rule:materials:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:001:in_scope_consistency | in_scope_consistency | sci-rule:materials:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:001:missing_required_condition | missing_required_condition | sci-rule:materials:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:001:negation | negation | sci-rule:materials:001 | VIOLATION | VIOLATION | yes |
| sci-case:materials:001:outside_validity_domain | outside_validity_domain | sci-rule:materials:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:materials:001:paraphrase | paraphrase | sci-rule:materials:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:001:unit_variation | unit_variation | sci-rule:materials:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:002:clear_violation | clear_violation | sci-rule:materials:002 | VIOLATION | VIOLATION | yes |
| sci-case:materials:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:materials:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:materials:002:empirical_verification_required | empirical_verification_required | sci-rule:materials:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:materials:002:false_red_prevention | false_red_prevention | sci-rule:materials:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:002:in_scope_consistency | in_scope_consistency | sci-rule:materials:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:002:missing_required_condition | missing_required_condition | sci-rule:materials:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:002:negation | negation | sci-rule:materials:002 | VIOLATION | VIOLATION | yes |
| sci-case:materials:002:outside_validity_domain | outside_validity_domain | sci-rule:materials:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:materials:002:paraphrase | paraphrase | sci-rule:materials:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:002:unit_variation | unit_variation | sci-rule:materials:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:003:clear_violation | clear_violation | sci-rule:materials:003 | VIOLATION | VIOLATION | yes |
| sci-case:materials:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:materials:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:materials:003:empirical_verification_required | empirical_verification_required | sci-rule:materials:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:materials:003:false_red_prevention | false_red_prevention | sci-rule:materials:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:003:in_scope_consistency | in_scope_consistency | sci-rule:materials:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:003:missing_required_condition | missing_required_condition | sci-rule:materials:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:003:negation | negation | sci-rule:materials:003 | VIOLATION | VIOLATION | yes |
| sci-case:materials:003:outside_validity_domain | outside_validity_domain | sci-rule:materials:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:materials:003:paraphrase | paraphrase | sci-rule:materials:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:003:unit_variation | unit_variation | sci-rule:materials:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:004:clear_violation | clear_violation | sci-rule:materials:004 | VIOLATION | VIOLATION | yes |
| sci-case:materials:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:materials:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:materials:004:empirical_verification_required | empirical_verification_required | sci-rule:materials:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:materials:004:false_red_prevention | false_red_prevention | sci-rule:materials:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:004:in_scope_consistency | in_scope_consistency | sci-rule:materials:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:004:missing_required_condition | missing_required_condition | sci-rule:materials:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:004:negation | negation | sci-rule:materials:004 | VIOLATION | VIOLATION | yes |
| sci-case:materials:004:outside_validity_domain | outside_validity_domain | sci-rule:materials:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:materials:004:paraphrase | paraphrase | sci-rule:materials:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:004:unit_variation | unit_variation | sci-rule:materials:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:005:clear_violation | clear_violation | sci-rule:materials:005 | VIOLATION | VIOLATION | yes |
| sci-case:materials:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:materials:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:materials:005:empirical_verification_required | empirical_verification_required | sci-rule:materials:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:materials:005:false_red_prevention | false_red_prevention | sci-rule:materials:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:005:in_scope_consistency | in_scope_consistency | sci-rule:materials:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:005:missing_required_condition | missing_required_condition | sci-rule:materials:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:materials:005:negation | negation | sci-rule:materials:005 | VIOLATION | VIOLATION | yes |
| sci-case:materials:005:outside_validity_domain | outside_validity_domain | sci-rule:materials:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:materials:005:paraphrase | paraphrase | sci-rule:materials:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:materials:005:unit_variation | unit_variation | sci-rule:materials:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:001:clear_violation | clear_violation | sci-rule:physics:001 | VIOLATION | VIOLATION | yes |
| sci-case:physics:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:physics:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:physics:001:empirical_verification_required | empirical_verification_required | sci-rule:physics:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:physics:001:false_red_prevention | false_red_prevention | sci-rule:physics:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:001:in_scope_consistency | in_scope_consistency | sci-rule:physics:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:001:missing_required_condition | missing_required_condition | sci-rule:physics:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:001:negation | negation | sci-rule:physics:001 | VIOLATION | VIOLATION | yes |
| sci-case:physics:001:outside_validity_domain | outside_validity_domain | sci-rule:physics:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:physics:001:paraphrase | paraphrase | sci-rule:physics:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:001:unit_variation | unit_variation | sci-rule:physics:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:002:clear_violation | clear_violation | sci-rule:physics:002 | VIOLATION | VIOLATION | yes |
| sci-case:physics:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:physics:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:physics:002:empirical_verification_required | empirical_verification_required | sci-rule:physics:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:physics:002:false_red_prevention | false_red_prevention | sci-rule:physics:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:002:in_scope_consistency | in_scope_consistency | sci-rule:physics:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:002:missing_required_condition | missing_required_condition | sci-rule:physics:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:002:negation | negation | sci-rule:physics:002 | VIOLATION | VIOLATION | yes |
| sci-case:physics:002:outside_validity_domain | outside_validity_domain | sci-rule:physics:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:physics:002:paraphrase | paraphrase | sci-rule:physics:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:002:unit_variation | unit_variation | sci-rule:physics:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:003:clear_violation | clear_violation | sci-rule:physics:003 | VIOLATION | VIOLATION | yes |
| sci-case:physics:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:physics:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:physics:003:empirical_verification_required | empirical_verification_required | sci-rule:physics:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:physics:003:false_red_prevention | false_red_prevention | sci-rule:physics:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:003:in_scope_consistency | in_scope_consistency | sci-rule:physics:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:003:missing_required_condition | missing_required_condition | sci-rule:physics:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:003:negation | negation | sci-rule:physics:003 | VIOLATION | VIOLATION | yes |
| sci-case:physics:003:outside_validity_domain | outside_validity_domain | sci-rule:physics:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:physics:003:paraphrase | paraphrase | sci-rule:physics:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:003:unit_variation | unit_variation | sci-rule:physics:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:004:clear_violation | clear_violation | sci-rule:physics:004 | VIOLATION | VIOLATION | yes |
| sci-case:physics:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:physics:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:physics:004:empirical_verification_required | empirical_verification_required | sci-rule:physics:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:physics:004:false_red_prevention | false_red_prevention | sci-rule:physics:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:004:in_scope_consistency | in_scope_consistency | sci-rule:physics:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:004:missing_required_condition | missing_required_condition | sci-rule:physics:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:004:negation | negation | sci-rule:physics:004 | VIOLATION | VIOLATION | yes |
| sci-case:physics:004:outside_validity_domain | outside_validity_domain | sci-rule:physics:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:physics:004:paraphrase | paraphrase | sci-rule:physics:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:004:unit_variation | unit_variation | sci-rule:physics:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:005:clear_violation | clear_violation | sci-rule:physics:005 | VIOLATION | VIOLATION | yes |
| sci-case:physics:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:physics:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:physics:005:empirical_verification_required | empirical_verification_required | sci-rule:physics:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:physics:005:false_red_prevention | false_red_prevention | sci-rule:physics:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:005:in_scope_consistency | in_scope_consistency | sci-rule:physics:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:005:missing_required_condition | missing_required_condition | sci-rule:physics:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:physics:005:negation | negation | sci-rule:physics:005 | VIOLATION | VIOLATION | yes |
| sci-case:physics:005:outside_validity_domain | outside_validity_domain | sci-rule:physics:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:physics:005:paraphrase | paraphrase | sci-rule:physics:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:physics:005:unit_variation | unit_variation | sci-rule:physics:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:001:clear_violation | clear_violation | sci-rule:semiconductor-devices:001 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:001:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:001:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:001:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:001:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:001:negation | negation | sci-rule:semiconductor-devices:001 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:001:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:001:paraphrase | paraphrase | sci-rule:semiconductor-devices:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:001:unit_variation | unit_variation | sci-rule:semiconductor-devices:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:002:clear_violation | clear_violation | sci-rule:semiconductor-devices:002 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:002:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:002:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:002:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:002:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:002:negation | negation | sci-rule:semiconductor-devices:002 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:002:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:002:paraphrase | paraphrase | sci-rule:semiconductor-devices:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:002:unit_variation | unit_variation | sci-rule:semiconductor-devices:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:003:clear_violation | clear_violation | sci-rule:semiconductor-devices:003 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:003:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:003:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:003:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:003:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:003:negation | negation | sci-rule:semiconductor-devices:003 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:003:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:003:paraphrase | paraphrase | sci-rule:semiconductor-devices:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:003:unit_variation | unit_variation | sci-rule:semiconductor-devices:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:004:clear_violation | clear_violation | sci-rule:semiconductor-devices:004 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:004:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:004:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:004:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:004:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:004:negation | negation | sci-rule:semiconductor-devices:004 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:004:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:004:paraphrase | paraphrase | sci-rule:semiconductor-devices:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:004:unit_variation | unit_variation | sci-rule:semiconductor-devices:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:005:clear_violation | clear_violation | sci-rule:semiconductor-devices:005 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:005:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:005:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:005:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:005:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:005:negation | negation | sci-rule:semiconductor-devices:005 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:005:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:005:paraphrase | paraphrase | sci-rule:semiconductor-devices:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:005:unit_variation | unit_variation | sci-rule:semiconductor-devices:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:006:clear_violation | clear_violation | sci-rule:semiconductor-devices:006 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:006:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:semiconductor-devices:006 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:semiconductor-devices:006:empirical_verification_required | empirical_verification_required | sci-rule:semiconductor-devices:006 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:semiconductor-devices:006:false_red_prevention | false_red_prevention | sci-rule:semiconductor-devices:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:006:in_scope_consistency | in_scope_consistency | sci-rule:semiconductor-devices:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:006:missing_required_condition | missing_required_condition | sci-rule:semiconductor-devices:006 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:semiconductor-devices:006:negation | negation | sci-rule:semiconductor-devices:006 | VIOLATION | VIOLATION | yes |
| sci-case:semiconductor-devices:006:outside_validity_domain | outside_validity_domain | sci-rule:semiconductor-devices:006 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:semiconductor-devices:006:paraphrase | paraphrase | sci-rule:semiconductor-devices:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:semiconductor-devices:006:unit_variation | unit_variation | sci-rule:semiconductor-devices:006 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:001:clear_violation | clear_violation | sci-rule:spin-coating:001 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:001:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:spin-coating:001 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:spin-coating:001:empirical_verification_required | empirical_verification_required | sci-rule:spin-coating:001 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:spin-coating:001:false_red_prevention | false_red_prevention | sci-rule:spin-coating:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:001:in_scope_consistency | in_scope_consistency | sci-rule:spin-coating:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:001:missing_required_condition | missing_required_condition | sci-rule:spin-coating:001 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:001:negation | negation | sci-rule:spin-coating:001 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:001:outside_validity_domain | outside_validity_domain | sci-rule:spin-coating:001 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:spin-coating:001:paraphrase | paraphrase | sci-rule:spin-coating:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:001:unit_variation | unit_variation | sci-rule:spin-coating:001 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:002:clear_violation | clear_violation | sci-rule:spin-coating:002 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:002:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:spin-coating:002 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:spin-coating:002:empirical_verification_required | empirical_verification_required | sci-rule:spin-coating:002 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:spin-coating:002:false_red_prevention | false_red_prevention | sci-rule:spin-coating:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:002:in_scope_consistency | in_scope_consistency | sci-rule:spin-coating:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:002:missing_required_condition | missing_required_condition | sci-rule:spin-coating:002 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:002:negation | negation | sci-rule:spin-coating:002 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:002:outside_validity_domain | outside_validity_domain | sci-rule:spin-coating:002 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:spin-coating:002:paraphrase | paraphrase | sci-rule:spin-coating:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:002:unit_variation | unit_variation | sci-rule:spin-coating:002 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:003:clear_violation | clear_violation | sci-rule:spin-coating:003 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:003:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:spin-coating:003 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:spin-coating:003:empirical_verification_required | empirical_verification_required | sci-rule:spin-coating:003 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:spin-coating:003:false_red_prevention | false_red_prevention | sci-rule:spin-coating:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:003:in_scope_consistency | in_scope_consistency | sci-rule:spin-coating:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:003:missing_required_condition | missing_required_condition | sci-rule:spin-coating:003 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:003:negation | negation | sci-rule:spin-coating:003 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:003:outside_validity_domain | outside_validity_domain | sci-rule:spin-coating:003 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:spin-coating:003:paraphrase | paraphrase | sci-rule:spin-coating:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:003:unit_variation | unit_variation | sci-rule:spin-coating:003 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:004:clear_violation | clear_violation | sci-rule:spin-coating:004 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:004:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:spin-coating:004 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:spin-coating:004:empirical_verification_required | empirical_verification_required | sci-rule:spin-coating:004 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:spin-coating:004:false_red_prevention | false_red_prevention | sci-rule:spin-coating:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:004:in_scope_consistency | in_scope_consistency | sci-rule:spin-coating:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:004:missing_required_condition | missing_required_condition | sci-rule:spin-coating:004 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:004:negation | negation | sci-rule:spin-coating:004 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:004:outside_validity_domain | outside_validity_domain | sci-rule:spin-coating:004 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:spin-coating:004:paraphrase | paraphrase | sci-rule:spin-coating:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:004:unit_variation | unit_variation | sci-rule:spin-coating:004 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:005:clear_violation | clear_violation | sci-rule:spin-coating:005 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:005:decision_changing_ambiguity | decision_changing_ambiguity | sci-rule:spin-coating:005 | AMBIGUITY_GATE | AMBIGUITY_GATE | yes |
| sci-case:spin-coating:005:empirical_verification_required | empirical_verification_required | sci-rule:spin-coating:005 | EMPIRICAL_VERIFICATION_REQUIRED | EMPIRICAL_VERIFICATION_REQUIRED | yes |
| sci-case:spin-coating:005:false_red_prevention | false_red_prevention | sci-rule:spin-coating:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:005:in_scope_consistency | in_scope_consistency | sci-rule:spin-coating:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:005:missing_required_condition | missing_required_condition | sci-rule:spin-coating:005 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | yes |
| sci-case:spin-coating:005:negation | negation | sci-rule:spin-coating:005 | VIOLATION | VIOLATION | yes |
| sci-case:spin-coating:005:outside_validity_domain | outside_validity_domain | sci-rule:spin-coating:005 | OUTSIDE_VALIDITY_DOMAIN | OUTSIDE_VALIDITY_DOMAIN | yes |
| sci-case:spin-coating:005:paraphrase | paraphrase | sci-rule:spin-coating:005 | CONSISTENT | CONSISTENT | yes |
| sci-case:spin-coating:005:unit_variation | unit_variation | sci-rule:spin-coating:005 | CONSISTENT | CONSISTENT | yes |

## Component digest inventory

The exact component map remains in the Release manifest; this report lists one digest per pinned object.

- `sci-evidence:chemistry:amount-concentration` — `sha256:61b31d09c34669364ca64b25acab41c860f5c3847889de9b525a04c9e0b6cb90`
- `sci-evidence:chemistry:catalyst-kinetics` — `sha256:6045edf0f3572f32079809b40988d1bf261fd9cf760af4a2049f38fdf7e12dc0`
- `sci-evidence:chemistry:evaporation-vapor-pressure` — `sha256:40844cc195bc701164022806a8d4a40b638c5682e5b41555ca0a38ebded375eb`
- `sci-evidence:chemistry:reaction-equilibrium` — `sha256:d32362890677475280e6ad1797d8845f33867a61aa022aa69e78e6b653f14136`
- `sci-evidence:chemistry:substance-phase` — `sha256:b6ca5c3fd38390780a6747a95a2a00c76f0c71b97e7d3080c5692cccf6056b26`
- `sci-evidence:circuits:capacitor-inductor` — `sha256:9e8d1365d378059cec8d2c74a1de927a5e5767da5bf1f9314988c91159b13a32`
- `sci-evidence:circuits:electric-power` — `sha256:fee666ed105c321fefba9d91a80fd20c6873313fe5c97e39e0aff3de7654e5ab`
- `sci-evidence:circuits:kcl-law` — `sha256:cf51fd055e49927b11b66e0e534b11c6109b4b87ca1b0775ff79ca390aa22962`
- `sci-evidence:circuits:kvl-law` — `sha256:3fb7e681d5cb647d112356caaafccc8fe21aed62580f03758fb88febecbaf91b`
- `sci-evidence:circuits:measurement-loading` — `sha256:ba470b8a1c4bb5203d12a82db1dbfae280731e20e09e3c0d7dff6ef18c049a3f`
- `sci-evidence:circuits:ohm-model` — `sha256:9bce31fa3b6dfe0981f445e0596813377aa09ec981bc997cd6ebaa7046b007f8`
- `sci-evidence:circuits:series-parallel` — `sha256:36e24384fe575f380f8b697d2a81ea3edfb986d4ca65accc34031f44d0ed4f51`
- `sci-evidence:common:accuracy-precision` — `sha256:1b90c5cddea0414aca9459f8be0555e195b8edceebf331a07d6a847347cae184`
- `sci-evidence:common:celsius-kelvin` — `sha256:172a3a1430538653af46de7da169f46e4bc02d530e8383e466c5b677e28af3e3`
- `sci-evidence:common:correlation-causation` — `sha256:48a267566dce9c4e09c13bf1ba6e5b1ab838893cd5aba8aa5dd2be21b6b72bdb`
- `sci-evidence:common:equilibrium` — `sha256:5fcea6d0982efbb27ddef65d3100feec53d9cdc9c89515034d5fd4471e736b7c`
- `sci-evidence:common:measurand-result` — `sha256:9bd097c2e104996c44e455823412717851c147c8ab7423e6db9e0b3490e265e8`
- `sci-evidence:common:model-validity` — `sha256:86fd9809a2303fdef33fa551f9af669ab1508060b8e3a0a99ae5b04990b9d2f7`
- `sci-evidence:common:quantity-unit-dimension` — `sha256:7551edb0c96009c8e48870e13841f47bc6d132bc033571b3b16678b09ff4496e`
- `sci-evidence:common:repeatability-reproducibility` — `sha256:d2fbfd998ad4bb7ebf815ae19351a852fa6f581ebf238fd2a71dfbdcd8ca9c8e`
- `sci-evidence:common:steady-state` — `sha256:2dc9a73eb4ae1e55f4b3b60803ce577d95f25411d1f7c5e162a1c00d8e0e05e2`
- `sci-evidence:common:system-balance` — `sha256:bf07fd6976ced3391c5883c8a1b317cd17da5c5f8bf14c009ae1ac70a5aa82fc`
- `sci-evidence:common:uncertainty-error` — `sha256:ca938af37ab290fcccd618ebbb618f5aa828cc985eefc10f2f233caa9f6cf14b`
- `sci-evidence:materials:bulk-thin-film` — `sha256:cf132fb2679d13fa72fa41379e8a0a04532418c4f38dfb0c9dcd4d156689ba0b`
- `sci-evidence:materials:defects-microstructure` — `sha256:8b4649948f6daee530fcbbdfc02a6dbe38aac5cf9194a3c7f0bc9ef86872b3b5`
- `sci-evidence:materials:diffusion-arrhenius` — `sha256:6179ca39a0a0ea9fe50623a689383281c4bc8d232ce07a3718637b98bfdc7c71`
- `sci-evidence:materials:nist-thin-film-bulk-difference` — `sha256:2480c5c115e51a0fea9d742c490b200faf8e327ef1cc83591a0f86168dba6929`
- `sci-evidence:materials:phase-transformation` — `sha256:d7c7ea27add46f04e331c6fac714871ab2f5e63d605e0318a81c1f3d36f5d338`
- `sci-evidence:materials:structure-grain` — `sha256:0db1f65ab042cf75ea2aa27f0cb0af04cf515be56b3e5ee483ad5e2cfbbedffc`
- `sci-evidence:physics:control-volume-flux` — `sha256:8d90904b26f2ec521954f66852dac12d9a2d99fea1c1a46ccc7e7547f371af2b`
- `sci-evidence:physics:force-momentum` — `sha256:19ace042556e87a88561a0dd9a445c22e0862592efb2b78ace28537edca6498a`
- `sci-evidence:physics:rotation-angular-speed` — `sha256:70be09a826799b51d64bfbcdb03c69ab88e612b7882900849e510de77b1367a0`
- `sci-evidence:physics:viscosity-flow` — `sha256:653462b613d2c23b452182645ee0870d12cc2de5a6edbd613046b4f057c7722a`
- `sci-evidence:physics:work-energy-power` — `sha256:a8963aa86fa9cb4108bf4c7893437e800f87ab2301b1efd557db21aaea66484b`
- `sci-evidence:semiconductor-devices:bands-fermi-level` — `sha256:9d385b83b0383002caa97be84c81e2d2a5c2e6c3770e012b36ea101f1331e2f2`
- `sci-evidence:semiconductor-devices:carrier-conductivity` — `sha256:b9b6b568baa5f168fc5defe85da1206c207e8fac2a2a29bb32b041fc1ada1ce5`
- `sci-evidence:semiconductor-devices:drift-diffusion` — `sha256:b9848754b6aed5c792bc0d67223f7fd35e2ae58f99670b1fd6be410654c8c253`
- `sci-evidence:semiconductor-devices:mos-capacitor` — `sha256:8c833e045cbf0356e3d1f7a28a5b0bcc900bc60ee572a13a376908f47b01f666`
- `sci-evidence:semiconductor-devices:mos-gate-ideal-model` — `sha256:87172ed044fa87a07cc9ad1b993b78ed0efa02304865ba3fc6f4c527dd15d049`
- `sci-evidence:semiconductor-devices:mos-gate-real-leakage` — `sha256:a43a411bc6b68318a6710a668f53dfea1cb6186a400cc19d5440f16e6b7b8222`
- `sci-evidence:semiconductor-devices:pn-junction` — `sha256:8de2179b04996f2d09a9cafd17a7e53d0a191b7d57289b695433652a93a5c9d7`
- `sci-evidence:semiconductor-devices:transistor-operating-region` — `sha256:09bd5f6efadffc18c7dc767b0c5cfaf4fac0e13e93f0b1505d9fb82c093bc64e`
- `sci-evidence:spin-coating:emslie-model` — `sha256:6c3e6d70896275089c8e301697d5fffed1f1282179f2236ccce09ce7d1eda0ef`
- `sci-evidence:spin-coating:meyerhofer-model` — `sha256:1e7eb103734b550b8bc17f30ab6653a9ae25729654b0c0fb47dee6b930c857a5`
- `sci-evidence:spin-coating:microchemicals-equipment-influence` — `sha256:de38130569988283d535d4fa6c471fecae29e075a8ae7615c90860d63ca0e6f7`
- `sci-evidence:spin-coating:microchemicals-film-state-change` — `sha256:3555d31f5f6996e65374ceead588f10bcd8ecceec911f02f3cdaf09f8dce161b`
- `sci-evidence:spin-coating:microchemicals-spin-mechanism` — `sha256:2485cb164b53e1388841178c48f2db595c14766f1d3e28cfefa5436272e61ac6`
- `sci-evidence:spin-coating:microchemicals-spin-speed-direction` — `sha256:a43a9b1721afc9870f7587310e7a10bec272058d36d1af281e43f500f089c02d`
- `sci-evidence:spin-coating:vendor-spin-curve-observation` — `sha256:149d15ace5bd6d0e2d536296adce75e72913103bf0b6989fe8712f227372d57c`
- `sci-evidence:spin-coating:vendor-spin-time-guidance` — `sha256:366ad4e6fb96f61c1ef4072ecbe20415d7dbe9c513d4e03de10964cc2e86172f`
- `sci-matrix:chemistry:001` — `sha256:8bfb5e66210bc74d4d8e838ad4db400c8e999c5c18d6df28f7f6d597df89b96b`
- `sci-matrix:chemistry:002` — `sha256:df065419bb770d4a24d4b08a61eb208493a20eec00d2e015d2ecc1084d6331b0`
- `sci-matrix:chemistry:003` — `sha256:204fa04f7229df2c70c068f5a77da4ab786eb38a36b98eebbf91778cac1f6dab`
- `sci-matrix:chemistry:004` — `sha256:64965a3f0e1c3e7a1331246b7be66319ef93939e2b419bf7a96c4a92f5167c5c`
- `sci-matrix:chemistry:005` — `sha256:08b6a9f5fcc55001cb1f5cb868978aee7aa134acb46d228950ab2d2621cc65e2`
- `sci-matrix:circuits:001` — `sha256:f1c5a086e2fb917602733031143a27a1ddd5b041913c07ff01637267a7fa1e5b`
- `sci-matrix:circuits:002` — `sha256:725bddd341e047282f3b4d298d5e4cc9d7ec068c72ce5c49badac40e44571682`
- `sci-matrix:circuits:003` — `sha256:76bbc7f92460d8cbe96e3a095cffe63c635b1570035c49eb9919005771669b99`
- `sci-matrix:circuits:004` — `sha256:c71186d6283fa10c769acc0f4ca458b263c530ab2cbaef3d4cc1d30880c53fb3`
- `sci-matrix:circuits:005` — `sha256:9bf8d9b32854d333a4cbc9a9cf358a6e0cf6179b01597fa5a33e604e702df18f`
- `sci-matrix:circuits:006` — `sha256:65759e40a7a8e945cdc35567902710552cfb27ed9b98cdc00466b28b677a1a67`
- `sci-matrix:common:001` — `sha256:2abc3c234cf30c8737a800a6c4aa63eb66f5ddce2e62a0729d357b0f0de5e679`
- `sci-matrix:common:002` — `sha256:2417dd8c3790651d622c0744f680579d69b49aea6ea3228d059d137bcc214562`
- `sci-matrix:common:003` — `sha256:b9df3b2d30cb4b090aca0712ce4b8e9e803c2929b1b9f93da4e48d1fe89a02d2`
- `sci-matrix:common:004` — `sha256:15a57b96110e7066f25bcc6c23b70ad2c84f708e531d3813c9ba5bcfd208d1f8`
- `sci-matrix:common:005` — `sha256:3a236c34f5534737b8b4bb1650674ba4baa4f463296af861323e5dcdc488b932`
- `sci-matrix:common:006` — `sha256:fa79e41d6cc0d828f59ea43274e85b5c4b231dab6e525a3d0faa6515a301befc`
- `sci-matrix:common:007` — `sha256:dfe8d3ac0412207e48d0b69369937994d775f9a63ddc1aa5d555c1d921da5eaa`
- `sci-matrix:common:008` — `sha256:76820962eece71ad021f28a767289b6be6a6018e6465b1d5da5b8bbc958e8c1f`
- `sci-matrix:common:009` — `sha256:3ba6a66aa0061891652fd2962b120ca27a6529accbd8ef30b9497e58e24dae1f`
- `sci-matrix:common:010` — `sha256:798ecff49e57f23f7ac640c9f90212997a3573e30b3960020edb36988b23f6bf`
- `sci-matrix:common:011` — `sha256:f74157f011b7cb44f62ff11ba63768a7c5f36178928a08d35403ac2bff124b32`
- `sci-matrix:common:012` — `sha256:993e55b565087390d65219f404bd7d92a747c925eb8ba1c263adaa126efe4ad1`
- `sci-matrix:materials:001` — `sha256:29eeea34433187598ac73551917114b6804fc28092627455a5f6dd67300d3a36`
- `sci-matrix:materials:002` — `sha256:c899d399e2d6837bad13797bf11052f3555c03836db21a84bd0ad6dea96e9a05`
- `sci-matrix:materials:003` — `sha256:9772353c5c6089e0d8264fd304e599820de2302f729eea12891984e0ec43baac`
- `sci-matrix:materials:004` — `sha256:7a0759638b9da53f15dfdcc137a978eed21fc7066ebbd63f1113dae495d2fdf9`
- `sci-matrix:materials:005` — `sha256:5e25fee980bf24c207965fdb681e51acedf44cd756528925c7b883954ebeae9e`
- `sci-matrix:physics:001` — `sha256:931fede847e28064af7d90b4a8c2b9250ec2e5ad1db3186963eae44bdde6af55`
- `sci-matrix:physics:002` — `sha256:3375d3749692f262c766a4a8c10a4e7fc076dbeb7c8396728c5b76e146a0da9f`
- `sci-matrix:physics:003` — `sha256:a2212d9b29380a5c24c8e4ff2174cc1bdadac9666a245b91d6bc07a662caf780`
- `sci-matrix:physics:004` — `sha256:ca1555fb0f11211d14cdf5938984d1b9da52003a12ca082547392e7858b2b6d9`
- `sci-matrix:physics:005` — `sha256:328c658b6da5845836424c910fc0928fd0d52c097bf7c5e24f152e33efcfbf98`
- `sci-matrix:semiconductor-devices:001` — `sha256:9f99a79a3bf3e8602bf5fc4dce50bf6554b126ef4620cdeb0bafde4b1350c089`
- `sci-matrix:semiconductor-devices:002` — `sha256:d360b68dbacaec2bd4427e7647a9abe7d8abc7e0fd24e6dcd3241a9392dbaafb`
- `sci-matrix:semiconductor-devices:003` — `sha256:038dc7ee3fca18a01775e53b98fa6deb29be497c9af633ee43dc4b07dcbc51d5`
- `sci-matrix:semiconductor-devices:004` — `sha256:e1f5f1bb5e2c4a5ad654eb54706c4b02f4e1a193e0b265d3f02c9da11a6de54e`
- `sci-matrix:semiconductor-devices:005` — `sha256:1ba5fdadda86c8dc7e10cc772ff27983c2a929a44ebcc7c3941a6a2376a24797`
- `sci-matrix:semiconductor-devices:006` — `sha256:ea8bcb026c794abf7f0fdb39508db1d4e6daf940a2ccde93e551332284478e61`
- `sci-matrix:spin-coating:001` — `sha256:1ddb5eb7a2f7ce39a32524f5b5c5368b131c82c22fee9f26906657d2fc3d2a86`
- `sci-matrix:spin-coating:002` — `sha256:dd247094c577a517a5de28b45f69262704755fa257885d79e2d9177d39e5dba9`
- `sci-matrix:spin-coating:003` — `sha256:d7fefab171e4d79949c097ef3366351f891d8229187ba944b36b47282031b097`
- `sci-matrix:spin-coating:004` — `sha256:5683183bcc8d69ac0fa7aaf794f6db45ef58c12f8691736101d04175cb4643ab`
- `sci-matrix:spin-coating:005` — `sha256:75a9437d05ddd35d55f6c035a5300e43273eadd70e771e5132e7285a70da3f8b`
- `sci-pack:chemical-principles/0.1.0` — `sha256:4c9d6fbfdd8e7cd291f8f2f53850061941c17ad3e967cacc1d46421158969028`
- `sci-pack:circuit-principles/0.1.0` — `sha256:8aa5c73ac0167c479cdbde8a3d53e805230a20950987786a360798f7b6de9e55`
- `sci-pack:materials-science/0.1.0` — `sha256:35ff675227cdb2d078ff205f8dbf5781574eb89ed00b92308df87c926d766768`
- `sci-pack:physical-principles/0.1.0` — `sha256:dd1f7185e75e4479b7523ff80f17b99104d6d3b58005d71a4e3c04ad972e80fe`
- `sci-pack:science-foundation/0.1.0` — `sha256:1c1780bdf0c8205ddc281e1e33af2b46c7761b8e8869e6f518f71e8d7a8be19a`
- `sci-pack:semiconductor-devices/0.1.0` — `sha256:3767f6aaf3c5a42b7726d38a28a35264c059a5bbfc561e72fc539d56f60ce979`
- `sci-pack:spin-coating/0.1.0` — `sha256:c5dac83ff4f1fa5466f12e41d435ab62835b495a7446f8244bafef619b8587aa`
- `sci-rule:chemistry:001` — `sha256:bee150e96ba02538b0c3f5ee9c618df867054706e9747e7d507be0ebf984c1f5`
- `sci-rule:chemistry:002` — `sha256:b53736f72884b518fe3e084e07ee194ca6ddf6b94e58e37ce2a157de9dc1ddeb`
- `sci-rule:chemistry:003` — `sha256:1185eb450c186f0fbd2db96841631cd22f347cebfda3f1cb71642300863df009`
- `sci-rule:chemistry:004` — `sha256:da3cf63473d4f7c905ed0cd1adad0fbfbbc6996632b52d0146d92cc0b6b694ca`
- `sci-rule:chemistry:005` — `sha256:aa85b55d7ba8fe4b8bc7fd4acea6315eb051d089a68c80197ac164192f9c2e71`
- `sci-rule:circuits:001` — `sha256:fc3bc8a2dd3e1a5b90bd5ff13f42d420e464aca8422d0bed2b1433660e0f1dae`
- `sci-rule:circuits:002` — `sha256:fbdc1c3dcd5c6a9311426a84bfe045cc71ad2ba8e6da2177a0a33b28d91fe7df`
- `sci-rule:circuits:003` — `sha256:afc499dbda371be57b915ca9fb1eb2727ea666848962e6e142535bd662ff59a4`
- `sci-rule:circuits:004` — `sha256:f0a2177446cff3c016353ebab8287f3b70017ad6459ef92a3bebe6a5d7a0fa7c`
- `sci-rule:circuits:005` — `sha256:d49056e2f3570e827df41c4d2698e53cb7bf624723366925bd8b1f16a93c0612`
- `sci-rule:circuits:006` — `sha256:b53d1312f89b90e49768b112ca3a09fbf1f4966750e90befaf37104b7e51b447`
- `sci-rule:common:001` — `sha256:b16c893b551378cd9aea69c232a4f8f7e5884fbbf69dbb1c20735178379e4ef0`
- `sci-rule:common:002` — `sha256:29bee3b277e1baf5e41fbeba8384337c11e10464b3d45e47b47594503d8748eb`
- `sci-rule:common:003` — `sha256:1ca2085717962f94a247b64865297c20662299b22e822124562dc6735400fcb6`
- `sci-rule:common:004` — `sha256:c275d2f1eae9bf66ef4b2faafdc15c810ba7080544a3b66677507926642935c3`
- `sci-rule:common:005` — `sha256:d23369427a521598e9338d03f5b1e5d572da2ac5283a4907c0bfcd8ac230b100`
- `sci-rule:common:006` — `sha256:40a0f1fd6618b550735f09bacc48592100a2742839a3e637643f4cccb04b71aa`
- `sci-rule:common:007` — `sha256:17114476ef8185408f3e599ef1a82e664eeca85aaf95cf9b3792fbe461550506`
- `sci-rule:common:008` — `sha256:70a33b732ada1901c2c42facd1bd18337508af4b00172c6a76fbb02fde4aa79e`
- `sci-rule:common:009` — `sha256:2d37859883fb5bb59c901e43ac6467e217140ea1109608d700d136a86cc34562`
- `sci-rule:common:010` — `sha256:f0a4093cb17ef7d3a51f96bf570cc18b6e7763f70fde75d093f01c8f930dd162`
- `sci-rule:common:011` — `sha256:2198668bb5d48250d39ff34fd7759906643a77ec19687c4eacd08869bfaa15c8`
- `sci-rule:common:012` — `sha256:13f7e010ab5d9690c5de8b26eca6367927594c1521910aba1aae34ba643d4d18`
- `sci-rule:materials:001` — `sha256:98cb58616e5b48ebbc5ad17ec14155369d2d565301a0b83ab8e73c1a813e51dd`
- `sci-rule:materials:002` — `sha256:bf22cc3e0bd62f7f9a1910d8348f6c39a5cd2f202b6b78ed4973fb13628366bc`
- `sci-rule:materials:003` — `sha256:032b95175ccb16e358462cf80cd21ecce9a8e01beff73212a0e73a19d67d128d`
- `sci-rule:materials:004` — `sha256:660f50409cc007db1e34c1d321c5f1fddcd532b6499bd527776ea0fda3f1818d`
- `sci-rule:materials:005` — `sha256:1e7f4bf1dd71852f28d13885bba446b27d6f84dbe5c90744b3b1212814a3ca8a`
- `sci-rule:physics:001` — `sha256:1c8bd2b3c80b97759c42f8fd6e558e0f22665b332090aa1e7358e6371e137da5`
- `sci-rule:physics:002` — `sha256:73b17380b1acceb37da63d2c2ee8d4747ed073d270a55d652dd0b47bf79a6186`
- `sci-rule:physics:003` — `sha256:0127daab36c1a709bc29f89ebb8722fbd8388cee0d4eead916dd23e23c2f7caf`
- `sci-rule:physics:004` — `sha256:cf1c0691500f7fd5dad037b0dc36419ffff6832847450ec3f71f6165ed28f857`
- `sci-rule:physics:005` — `sha256:aa07ec901abbcce09602c6b23eecbdd0129de8979d32fef45f91109ffb3bff88`
- `sci-rule:semiconductor-devices:001` — `sha256:b9b3fa736942915f6e29988c16f9d212018da6eaf73b8f2e763a06369185e4eb`
- `sci-rule:semiconductor-devices:002` — `sha256:cd1ad48fc9a1a25720915557b2ca21f17fca9bf3cbf38f4437c62859a2361b83`
- `sci-rule:semiconductor-devices:003` — `sha256:aca726c4aaa937d77aabaf49480fbc2776941c16e8a7ec9f51aea8550028b49e`
- `sci-rule:semiconductor-devices:004` — `sha256:2437f982bbfef22d0c157f78e09286bac3e1bfb604df84fcd766857cc476279a`
- `sci-rule:semiconductor-devices:005` — `sha256:3b464fd3b2e5a92081679d8e620822b8ba6363e318290792b965587bcbee2cc1`
- `sci-rule:semiconductor-devices:006` — `sha256:8bebed87672bf5befa5096db639470efe999e486877512018bd8b60e613c1ef4`
- `sci-rule:spin-coating:001` — `sha256:1a2811aa00cbd6b5c4045d46b70b15709b2db63e4aada32795f2c9fbb3e6567d`
- `sci-rule:spin-coating:002` — `sha256:068ac1dfb2c6887d1ccce657b4fc800b1d4bf79da671798521f04b42b99df37f`
- `sci-rule:spin-coating:003` — `sha256:89b123d96159dead2c1d85f571300044faccb4c3898f0a4d970b10b2660eccac`
- `sci-rule:spin-coating:004` — `sha256:fcc6262d580c1863edf244eac6ace40173052230362cd9144766debf3986092b`
- `sci-rule:spin-coating:005` — `sha256:7c7137c0292600f73243b8a062c4003e442a2f602e52ced14234969b44e1dbde`
- `sci-source:all-about-circuits` — `sha256:eac843d8866eaa06bc64ab50655efcd1b17aa5b977bd39a82309787a0868e2eb`
- `sci-source:bipm-si-brochure-9-v4-01` — `sha256:811adc1907a5a4482e174c2c390236077f9bd330d566590a909f037c9b8fb2e7`
- `sci-source:chem1-virtual-textbook` — `sha256:e8a02b240ffad488899188eefbeeb40ac8eb54b2e55ab6911253a0efda93380b`
- `sci-source:chenming-hu-devices` — `sha256:e5f06055b64596f90a7170a09f413e121d525b0f02082cf37e92e31dce1f1d7c`
- `sci-source:emslie-1958` — `sha256:6d7f6cae278981d98b0503ab6bf4b5f8e5e2f112c84a0dd4ba84750a140051a1`
- `sci-source:feynman-lectures` — `sha256:00ddb0a77572453f0921f1944d95bcc9e79addb35297141e4ddaa2766f4f5a7e`
- `sci-source:iupac-gold-book` — `sha256:67daa2f7c126f221bcac04aab57d6277fe4a3b5ee8e53d09c5730641a9962b20`
- `sci-source:jcgm-vim-3-2012` — `sha256:407d14fd3b8ee56cb41eb6e0b4337fe0bba31b6fd198053deb10841482d132f0`
- `sci-source:merck-az-125nxt-01-24` — `sha256:b2133a8d59487407cdbf01215a08759ce40dfc7fe492fdea295afbc9c373b200`
- `sci-source:meyerhofer-1978` — `sha256:6b5e601dcafb21618afdd7c76a5d326ba47d8f3eda3d6fcc59605b2f195ce654`
- `sci-source:microchemicals-spin-coating-photoresist` — `sha256:72386b819a8f92ffb2a77a5165b2e3dc1e2d3ae65914ddbb710e970567c8705c`
- `sci-source:mit-2-25` — `sha256:d6b08d4340f34e5faaf5123b2da650eff2d43d3c2371035b1e605a1df1dd5b74`
- `sci-source:mit-3-012` — `sha256:ec40b5004cdef4bf0bb2b93dc21f467c236d5e4ee9f76f26c9d9e96421f75b79`
- `sci-source:mit-3-024` — `sha256:fb38205bff8f7e226705709970ffe7fa455d4eb816704aa5f3b8c65001fdd705`
- `sci-source:mit-3-091` — `sha256:88aab6a0c4836d86494d390cd1f6632a060e5a17f125b93ae2897fd3ab99e26d`
- `sci-source:mit-3-091sc-2010` — `sha256:1c1f6196bea1c93a0a9b91472e151d653af18d15272698958a5a14bba57e4a96`
- `sci-source:mit-5-111` — `sha256:96ec63adcc30dbe6eeb29295ac4e6fabb7250884768220d1a6e491bec93e0ad7`
- `sci-source:mit-6-002` — `sha256:d3929b344854b4430227534e1567f455cf3da4b0eab78914b2416e7857f5450d`
- `sci-source:mit-6-012` — `sha256:04882b5b6f94eea6c66d8b16af125f99c21056b35913f63d60ca31edd123fe3e`
- `sci-source:mit-8-01sc` — `sha256:36f9aba3a2bd7e744f86dc07865fbbf0274efbac6d25c73bc7925547a2d3a701`
- `sci-source:nasa-std-7009b` — `sha256:4c11dab12611e0a687e878d9f30193a4bd374d845e3f9f09a432140af8db58e9`
- `sci-source:nist-statistics-handbook` — `sha256:e74602f67fdf1f7e48355793447c42715375a1fd574e1d055eea15df1093117e`
- `sci-source:nist-tn-1297` — `sha256:c50c8fb4b9583376a50e093b1032fe9bb2d94d19e8b2e2738a19d54b6036c35c`
- `sci-source:nistir-5851-1997` — `sha256:fc1c40fb4b87641aa2c7d7118d10c861884e55ef764ac6469b72064d62232606`
- `sci:binding:common:accuracy` — `sha256:9440ed9554e949b4981dedcb423ab9a42853bb82686a62a4cb9796d54869eb0c`
- `sci:binding:common:association` — `sha256:1160d97b115a619d94da02ee63ac09eb5f1f17d2c872c4b63810fc1fe7b36472`
- `sci:binding:common:causation` — `sha256:afb49efe6908bafacfcacf546b94e9dac4ce5d727abc5735aa4b9c109a9db8cb`
- `sci:binding:common:correlation` — `sha256:977859106234736a75aa705c290533894a7bcad32b33e7c6efe10348b7888634`
- `sci:binding:common:dimension` — `sha256:44635ce589442b440a1ed2dbf11fc78f327cbd8e202e1eb18be2a60e586320ec`
- `sci:binding:common:equilibrium` — `sha256:a6760255f1ad7f092c3d2eeadf64c8ba02a61516024167760e3f0a02a1941fd6`
- `sci:binding:common:measurement-error` — `sha256:0d12f4a474ab0a8ba9db37284ed55148d7d2f0f860dda1426ee2f01b916c3606`
- `sci:binding:common:measurement-uncertainty` — `sha256:ad9d313c7121bc454731445ec9737c3efd2b71c3baaf860332754e4c2f439228`
- `sci:binding:common:model` — `sha256:b949178be1dfe5d58dc403e9e26d387e3a036f84f5842291bd2e05297fe5d7e9`
- `sci:binding:common:precision` — `sha256:4ef403210f61fd9b977f312a6b7be5709fd53a9e1980578f65f2d2b607e9db3a`
- `sci:binding:common:quantity` — `sha256:8fba82af9695f7e3bdf91b78d840f57213b95b26114b4c562f1cb6833fe133ba`
- `sci:binding:common:steady-state` — `sha256:cd98ac5d8e4f055404537c68f81aea9c1c0a81cb1dcd31227189dcf89f80bbb0`
- `sci:binding:common:unit` — `sha256:02645695020d70ce0e5ac85520cd01a7b00a3693bd318319add71e8f06b498c8`
- `sci:binding:domain:angular-speed` — `sha256:2482e3ad2f554802263401364a8b23f9947fe521bd9e7970a6deae21424177d2`
- `sci:binding:domain:bulk-property` — `sha256:d7561d0bc927d2807b6585a5ad51f1042fcbc72cb14a423dfa282d12c5fb4751`
- `sci:binding:domain:catalyst` — `sha256:41a35485e64fa4947035abd2252a2a2e450129c1da1cfc55d4ff8307847e02f6`
- `sci:binding:domain:conductivity` — `sha256:cd651031c7e40aef327242ce6bb71fb2dba4ee09559b1694b0dbb59998b979b5`
- `sci:binding:domain:electric-power` — `sha256:2dffb92dcb82d1dc64ee894a9af3e89a669040ab5d45020de5b18ef088065be1`
- `sci:binding:domain:equilibrium-constant` — `sha256:0be8e4286ebd51438add7be648cf709e1d1e51340b9e9deecdf203684654f11f`
- `sci:binding:domain:film-thickness` — `sha256:9a1b3d040da1ff035a7774de8b049242e7b38154d34b3c812448d9a4de4e58fc`
- `sci:binding:domain:mobility` — `sha256:db265fdb981a1c7c375038d2ffcb7dc65947f90161148f15deea78304443ba6b`
- `sci:binding:domain:photoresist` — `sha256:f24b9444e170d17c2bcd3055e272b9691305e392f4930e7d91ac8aff5bec231c`
- `sci:binding:domain:resistance` — `sha256:8ef618b186110acd1377d9060dad9f8a24678876f0c8ab20a3970c711797c3b0`
- `sci:binding:domain:semiconductor` — `sha256:b6d7219d3bf8c033fd703df43f9d3a368e4d88709bcd515dc3e86b4833411312`
- `sci:binding:domain:spin-speed` — `sha256:411b586f91d77875dd0bda4e1bd6fa8eda7740089053a08431d37c9b620d55b6`
- `sci:binding:domain:thin-film-property` — `sha256:f528eedc5a4a2705399e38639523533bd3e2a3a2e9ff3c45c707f92a11f3c993`
- `sci:binding:domain:viscosity` — `sha256:75572cd72a162169f8ec5463c386a98d38eb67b8e2cca00890af7228bea2166a`
- `sci:chemistry:001` — `sha256:d1a8b4bd3f1f0848db65325abd1430305c92fa49994055a21755e187c710a138`
- `sci:chemistry:002` — `sha256:148d8e8a36c0c71a03721676cf5e04ef056e2265a7a4f8e86b9a6b99a5d7abbb`
- `sci:chemistry:003` — `sha256:54ecf554ab9b78a2cb89b3afb7d2320f9bf12b9777f45e8e822f785ef823fa02`
- `sci:chemistry:004` — `sha256:f73a60e7d21f603bf9bb2c6bd80f613f9b76af5aed1e16330cc4d2d9eb9f8051`
- `sci:chemistry:005` — `sha256:8ed2efe8ce538018ffac0e2e75350eec119b9adb0c8ac73188156783392c2e92`
- `sci:circuits:001` — `sha256:80e2725afeb238ddd5bc795f4a9d78d8dec30a1822fe397691118f4d2d26fb88`
- `sci:circuits:002` — `sha256:9ebf23ef526a1eb698b7f5e702d0727aa88db154abad50ec52cca57cdaa3a80e`
- `sci:circuits:003` — `sha256:bb6d42bcffafd561bc8f37ba35978b1afc8825715166e9590083c09417b55f4a`
- `sci:circuits:004` — `sha256:96c214c3514a27dda79f8f20cc55ee8e6d74b2e6953aa237866176b23f007403`
- `sci:circuits:005` — `sha256:da6d8b56d518de86ae32859c31b919d18f940d12ddb6d370f7030df1c4f2ed74`
- `sci:circuits:006` — `sha256:dd771b33af4a278c42f1f6250f2e029a364d3edf03b6cac6e0ca31a0fdedb8fb`
- `sci:common:001` — `sha256:2f78912126cfbe295a2a4f27db569e34cc4c43bd614488d419c446d926d7d6e4`
- `sci:common:002` — `sha256:2cede1c590dda6f950041b07493949ab6ebbc4f387cd3415bd6282557611bfbd`
- `sci:common:003` — `sha256:46bcac0ac5800e9f1821170496e224e336b49d48df32bc35be5a32bd827f5231`
- `sci:common:004` — `sha256:55a3953ba6c6b575720f5d36f7358465c029e9e8ec1b5e0bad4667c70af3298f`
- `sci:common:005` — `sha256:019dae099e6c01494e7e46de936ae0ecd07af8124603d411d99efc27b28dc449`
- `sci:common:006` — `sha256:22dbac35d5d6287821fade0e3165c789516f0e7db34c3d2c640eb768c5f3f259`
- `sci:common:007` — `sha256:eece8656ea79f1569a828109d558fd60e28ed789ad1811028f5b53083b71e2a1`
- `sci:common:008` — `sha256:b6c36985644a39b83be383239336912df65fa31e9f3e5bb2d8f6ba5d6bb519fc`
- `sci:common:009` — `sha256:bcb61704a16a447d58713a2b40ef717baa8eb996b330d58ee2fb351598575ae1`
- `sci:common:010` — `sha256:7143c7173cdcebe2db8b86e126f4ef347ba57753682ee4ac724ff0884e0094cc`
- `sci:common:011` — `sha256:f8055c2ebe523d0b5e88d5d44e7cd5f22e7a3111be5f4f9da0678e4dce4a9808`
- `sci:common:012` — `sha256:eb07fb127e53b357ebba6ac45aaf6154ce7d6d4f8e15aaed6c3df5e4983a60d4`
- `sci:materials:001` — `sha256:b2bb1da4e38e0372978d861dd468f62471dc41dfa387131dc4c8bd5da06b4f6e`
- `sci:materials:002` — `sha256:a34595850b880ffdeb46a279f9d37867b24010983bea961782234d11f9cbdde1`
- `sci:materials:003` — `sha256:86509dd70237cea07401f670cd7d6a031680dc8c6ccf40850af108b00cdd0dbc`
- `sci:materials:004` — `sha256:ed02c4900003940cfdd7a7d5996848f0b79d583fd12ef50ffee7a91f93635806`
- `sci:materials:005` — `sha256:b304188c644c97afe0afc3d8cada223e8ef54e4190e1e4033261c66e077fdee3`
- `sci:physics:001` — `sha256:39a7d5461f71a59398fb10ee5e9afbfbd8ecdb8d26aedae54aacdc10fccae2ba`
- `sci:physics:002` — `sha256:5f244f3bc969ee997e8385110f5c535629b79bef154644bc3b3b6cea8cea4c47`
- `sci:physics:003` — `sha256:e4ccf01c9b8ba22fe8c0abe64ee1cac240e0f043bc2ad16446a8c4da18be080e`
- `sci:physics:004` — `sha256:a0a32e1567d61fef4bb1b054cb2c3276d19851e87daa38ab55cfefa1bf1b7ee4`
- `sci:physics:005` — `sha256:08f9f13eb5a255aa506263cc6f65c7eaf6df57320781d43d633c3ca13a32812d`
- `sci:semiconductor-devices:001` — `sha256:26face5b96540daa86daba2d7da93559f5eac4b460f1a7ead8ed509025752dfe`
- `sci:semiconductor-devices:002` — `sha256:cdea82fed732a90ba02140efe66b85e79fc7b5361065d5fafc2bd46289ecc776`
- `sci:semiconductor-devices:003` — `sha256:ba301ee40bf1343a3df6013d307ade95341dbece39d7bff812941089c682bc51`
- `sci:semiconductor-devices:004` — `sha256:eb33f3322fe4cffe81cddb5073c7300ebcf8cae8a4c8e73cac6bf21c2a9f6615`
- `sci:semiconductor-devices:005` — `sha256:2942acef7ef7941724daa02285102d081e9cb4cbabc24934f5d1902f2171cfc1`
- `sci:semiconductor-devices:006` — `sha256:7b0905a8dfeb121beb46ee6f550ac8bdf3bf3f3a33c19c9d58ae509aa0fa3773`
- `sci:spin-coating:001` — `sha256:3b01ab635d5a84058f5c9b281f16ad700abdf3d90f792b2eb44fd834086ce694`
- `sci:spin-coating:002` — `sha256:f9180bf884086245ac5a6d06e4506e5c7b7f5caebc4feccd702db3b7b8cf9356`
- `sci:spin-coating:003` — `sha256:9a8841961066049590d377ae10f7b1291b72afd6e100bb7d3d946944477b4f8d`
- `sci:spin-coating:004` — `sha256:376ee4bab73579968dc47b230b36a5d7699534078bc42a4fad2437061673cb71`
- `sci:spin-coating:005` — `sha256:5ed5415091c4070276cf151f797cc15ea6ea61ae55a2d546ce66a311a1c1fd3b`
