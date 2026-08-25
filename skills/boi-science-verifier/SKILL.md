---
name: boi-science-verifier
description: Use when a user asks to scientifically fact check a document, passage, or claim through BoI Science Verifier, including ambiguity review, evidence inspection, or report export.
---

# BoI Science Verifier

BoI's active, human-approved Release and deterministic Rule engine—not the Agent—own verdicts. The Agent submits interpretation proposals and inspects results.

Read `harness/science-verification-harness.md`; for formulas also read `harness/science-equation-knowledge-harness.md`. Use an **authenticated user bearer** for Science MCP. A `service token` authenticates transport only and **사용자 identity가 아니다**.

## Verification contract

1. Call `science_aliases_detect` on the exact document. Propose roles, conditions, spans, and `ontology_refs` only from returned bindings.
2. Call `science_claim_submit`. Never submit verdict, Rule, Evidence, citation, correction, or Release. BoI re-resolves every span and concept role.
   - An **equation claim proposal** may include exact `source span`, parsed expression candidate, each `symbol`'s concept and `quantity kind`, `unit`, condition, `sign`, `reference direction`, and `ontology` refs. It is untrusted. BoI rejects incomplete/overlapping spans, absent symbols, **Agent가 만든 변수**, and **확인되지 않은 단위** or conditions.
   - If `V` could mean `voltage` or `volume` and change the result, show a **purple dotted** ambiguity. Record outcome-neutral notation silently.
3. For **결과가 달라지는 모호성**, show alternatives, get **명시적 사용자 확인**, then call `science_interpretation_confirm` with `user_confirmed: true`. Never infer confirmation; re-run only that claim.
4. Call `science_verify_document`; use `science_verify_claim` only to resume one claim. Wiki revisions use server-issued lineage. Missing/forged lineage or ACL failure is `verification unavailable`.
5. Red underline/shading requires deterministic `VIOLATION`, active Rule, satisfied applicability, and exact eligible Evidence locator. Ambiguity stays purple, never red.
6. Show a sufficient scientific explanation and 1–2 links. Use `science_evidence_get` for expanded **원문**, translation, `locator`, URL, and integrity. Standalone Evidence is not operational authority.
7. Call `science_report_get`; preserve `release`, digests, quote hashes, and `report_digest`. Use `science_report_export` for Markdown/PDF and preserve `export_digest`.

## Equation boundary

Use only a **reviewed Equation** whose `equation_id` is pinned by the active Release. The semantic expression is authoritative; display LaTeX is presentation. `explanation_only` may explain but **판정에 사용하지 않는다**; only evaluator-linked `deterministic_rule` may decide. Never add a formula from memory, invent variables, fill unknown values, or present an empirical fit/approximation as a universal law.

Present stored principle/model, Equation, variable meanings, conditions, Claim mapping, consequence, correction, limits, and Evidence in order. Preserve Equation/Knowledge/Rule/Evidence/Source identities. Web exposes display LaTeX, plain-text fallback, and accessibility reading; Markdown/PDF use the same Equation. Keep scientific `report_digest` separate from rendering `export_digest`. Missing readable fallback means `verification unavailable`, not permission to calculate or recommend a setting.

`science_interpret` is an **optional, experimental** Qwen adapter, never default or fallback. Connection failure, timeout, empty content, invalid JSON, or schema mismatch produces **no Claim, verdict, Evidence, Rule, or red annotation**. Continue via deterministic aliases and User/Agent submission; model availability is not a release gate.

## Verdict and result

Return exactly `VIOLATION`, `CONSISTENT`, `INSUFFICIENT_INFORMATION`, `OUTSIDE_VALIDITY_DOMAIN`, or `EMPIRICAL_VERIFICATION_REQUIRED`. **BoI가 반환한 Verdict를 변경하지 않는다.** `CONSISTENT` means no conflict in the checked scope, not **참·안전·승인**.

If interpretation, active Release, Evidence, locator, applicability, Equation, or report integrity is unverifiable, stop that result. Never fill the Truth Path with **자체 지식으로 Citation**, web citation, familiar formula, or Agent guess. **Agent 기억으로 대체하지 않는다.** Draft/pending objects and inactive Releases stay non-operational; implementation `FINAL / VERIFIED` does not satisfy independent holdout or human Admin activation.

Return an annotated document, correction/explanation card, always-visible sources, expandable interpretation/Evidence, and immutable report/export link. Do not add aggregate truth scores, hidden recommendations, or unsupported certainty.
