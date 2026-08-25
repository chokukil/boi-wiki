---
name: boi-science-verifier
description: Use when a user asks to scientifically fact check a document, passage, or claim through BoI Science Verifier, including ambiguity review, evidence inspection, or report export.
---

# BoI Science Verifier

BoI's active, human-approved Release and deterministic Rule engine—not the Agent—own verdicts. The Agent only proposes a structured Claim interpretation and helps inspect BoI's result.

Read `harness/science-verification-harness.md` before verifying.

Use an **authenticated user bearer** for every Science MCP call. A `service token` authenticates only MCP transport and **사용자 identity가 아니다**; never treat it as a user or role.

## Verification contract

1. Call `science_aliases_detect` with the exact document. Use only exact alias matches returned by BoI when proposing `subject`, `relation`, `object`, conditions, spans, and `ontology_refs`.
2. Submit the structured candidate through `science_claim_submit`. Do not choose a verdict, Rule, Evidence, citation, correction, or Release. BoI re-resolves text spans and validates every concept role and ontology reference. Agent-supplied quantities and conditions need a visible user revision before they become applicability input.
3. When BoI marks **결과가 달라지는 모호성**, show span and alternatives. Get **명시적 사용자 확인**, then call `science_interpretation_confirm`. Set `user_confirmed: true` only for that immediate action; never infer confirmation. Re-run only that claim.
4. Call `science_verify_document`; use `science_verify_claim` only when resuming one claim. The same confirmed Claim and active Release must produce the same result for all clients.
   - For a Wiki local revision, return only server-issued canonical lineage. BoI rechecks source ACL/ref/digest on submit, confirmation, and both verification endpoints; never construct, repair, or reuse `boi:submitted:*` lineage. Missing, malformed, or forged lineage is `verification unavailable`. Raw pasted documents remain owner-only.
5. Render BoI's annotations in the document. Red underline/shading is only for a deterministic `VIOLATION` whose active Rule, satisfied applicability conditions, and exact eligible Evidence locator are present. A pending ambiguity is purple dotted, not red.
6. Show the scientific explanation and 1–2 source links under every verdict/explanation, including non-corrections. Use `science_evidence_get` for the expanded **원문**, translation, `locator`, source URL, applicability, and integrity state. Standalone Evidence lookup is explicitly non-authoritative; accept operational eligibility only from an immutable report's active Release binding and reviewed-source identity. An unknown or unverifiable state stops that result.
7. Call `science_report_get` before presenting a final report. Preserve its `release`, component digests, quote hashes, and `report_digest`. Use `science_report_export` for the exact Markdown or PDF packet.

`science_interpret` is an optional, experimental Qwen adapter for the Web pilot. It is not the default path, authority, or fallback. A connection failure, timeout, empty response, invalid JSON, or schema mismatch produces no Claim, verdict, Evidence, Rule, or red annotation. Continue with deterministic alias detection and user/Agent candidate submission instead of retry-tuning the model. Live Qwen availability, tuning, context size, or a successful response is never a release requirement.

## Verdict boundary

Return exactly the BoI verdict:

- `VIOLATION`
- `CONSISTENT`
- `INSUFFICIENT_INFORMATION`
- `OUTSIDE_VALIDITY_DOMAIN`
- `EMPIRICAL_VERIFICATION_REQUIRED`

**BoI가 반환한 Verdict를 변경하지 않는다.** `CONSISTENT` means no conflict was found under the selected Release, rules, evidence, bindings, and conditions. It does not mean **참·안전·승인** or recommend an operational change.

If interpretation, active Release, Evidence, locator, applicability, or report integrity cannot be verified, stop the affected result and say `verification unavailable`. Draft/pending knowledge and inactive Releases never enter an operational verdict. Do not complete the Truth Path with an Agent guess, **자체 지식으로 Citation**, a web citation, or a familiar formula. External research may be submitted only as a separate curation proposal. **Agent 기억으로 대체하지 않는다.**

`FINAL / VERIFIED` implementation evidence does not make an inactive `release_candidate` operational. Automated G0–G4 Candidate qualification, independent sealed holdout G5, active stored-report parity G6, and human Science Admin review/activation audit G7 are separate claims; do not collapse pending G5–G7 into an activation statement.

## Result shape

Keep verification primary:

- annotated document
- correction card with verdict and sufficient scientific explanation
- always-visible source links
- expandable interpretation path and Evidence source text
- immutable report/export link

Do not add an aggregate truth score, hidden recommendation, or unsupported certainty.
