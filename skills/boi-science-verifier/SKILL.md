---
name: boi-science-verifier
description: Use when a user asks to scientifically fact check a document, passage, or claim through BoI Science Verifier, including ambiguity review, evidence inspection, or report export.
---

# BoI Science Verifier

BoI, not the client Agent, owns scientific verdicts. The Agent helps the user inspect the claim, interpretation, explanation, and evidence without upgrading or rewriting BoI's result.

Read `harness/science-verification-harness.md` before verifying.

## Verification contract

1. Call `science_interpret` with the exact document. Keep returned claim spans, bindings, `ontology_refs`, and Release identity unchanged.
2. When BoI marks **결과가 달라지는 모호성**, show the affected span and alternatives. Get **명시적 사용자 확인**, then call `science_interpretation_confirm`. Set `user_confirmed: true` only for that immediate user action and preserve the authenticated actor; never infer or manufacture confirmation. Re-run only the affected claim. Never choose the likely meaning for the user.
3. Call `science_verify_document`; use `science_verify_claim` only when resuming one claim.
4. Render BoI's annotations in the document. Red underline/shading is only for a deterministic `VIOLATION`; a pending ambiguity is purple dotted, not red.
5. Show the scientific explanation and 1–2 source links under every verdict/explanation, including non-corrections. Use `science_evidence_get` for the expanded **원문**, translation, `locator`, source URL, applicability, and integrity state. Accept eligibility only from the API contract; an unknown or unverifiable state stops that result.
6. Call `science_report_get` before presenting a final report. Preserve its `release`, component digests, quote hashes, and `report_digest`. Use `science_report_export` for the exact Markdown or PDF packet.

## Verdict boundary

Return exactly the BoI verdict:

- `VIOLATION`
- `CONSISTENT`
- `INSUFFICIENT_INFORMATION`
- `OUTSIDE_VALIDITY_DOMAIN`
- `EMPIRICAL_VERIFICATION_REQUIRED`

**BoI가 반환한 Verdict를 변경하지 않는다.** `CONSISTENT` means no conflict was found under the selected Release, rules, evidence, bindings, and conditions. It does not mean **참·안전·승인** or recommend an operational change.

If interpretation, active Release, Evidence, locator, or report integrity cannot be verified, stop the affected result and say `verification unavailable`. Do not complete the Truth Path with an Agent guess, **자체 지식으로 Citation**, a web citation, or a familiar formula. External research may be submitted only as a separate curation proposal. **Agent 기억으로 대체하지 않는다.**

## Result shape

Keep verification primary:

- annotated document
- correction card with verdict and sufficient scientific explanation
- always-visible source links
- expandable interpretation path and Evidence source text
- immutable report/export link

Do not add an aggregate truth score, hidden recommendation, or unsupported certainty.
