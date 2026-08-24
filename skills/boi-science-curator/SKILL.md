---
name: boi-science-curator
description: Use when proposing, validating, reviewing, or releasing BoI Science Sources, Evidence spans, ontology terms, Knowledge objects, Rules, qualification cases, or Release Candidates.
---

# BoI Science Curator

Scientific curation is **제안만** until the proper human role reviews an exact immutable object. Validation proves contract compliance, not scientific approval.

Use an **authenticated user bearer** for every Science MCP call. A `service token` authenticates only the MCP transport and **사용자 identity가 아니다**; it cannot provide curation or release authority.

Read these before acting:

- `harness/science-source-curation-harness.md`
- `harness/science-knowledge-authoring-harness.md`
- `harness/science-rule-qualification-harness.md`
- `harness/science-verification-harness.md`

## Object path

Build and review each layer separately:

`Source → Evidence → Knowledge → Rule → Qualification → Release Candidate`

1. **Source** records provenance, access/licence facts, authoritative URL, document version, and retrieval digest. It is not truth.
2. **Evidence** is a short exact source span with locator, original text hash, reviewed translation, claim scope, and Source digest. Hash and locator must reproduce.
3. **Knowledge** states one atomic principle, law, mechanism, model, qualified rule, or observation with assumptions, applicability, limitations, ontology links, and EvidenceUse scope.
4. **Rule** encodes only a deterministic consequence licensed by Knowledge and Evidence. Do not turn missing information, association, or an Agent assertion into a contradiction.
5. **Qualification** runs G0–G7 and the required positive, paraphrase, negation, unit, ambiguity, validity, empirical, false-red, and restart/parity cases. Keep case text and expected verdict real and independently reviewable. Do not emit an `aggregate score`.
6. **Release Candidate** pins every exact digest. A passing candidate stays inactive until human review and activation.

Use `science_source_validate`, `science_evidence_validate`, `science_knowledge_validate`, `science_rule_qualify`, and `science_release_validate` at their respective layers before submitting `science_proposal_create` with `user_confirmed: true`. Source validation never validates all spans from that Source. **검증 통과가 승인이라는 뜻은 아니다.** Never cite **inactive Evidence** as decisive Evidence and never route a draft into the active Truth Path.

New and changed objects start as `draft` and move to `pending_review`; tools do not mark them reviewed or active. **자동 활성화하지 않는다.**

## Role boundary

| Role | May review or approve |
|---|---|
| User | Submit feedback and proposals only |
| `science.power_user:<domain>` | In that domain, approve **별칭·용어·해석·개념 연결** proposals into a Release Candidate |
| `science.admin` | Source/Evidence, laws, equations, Knowledge, **법칙·수식·판정 규칙·Evidence**, qualification policy, final Release activation or withdrawal |

A Power User cannot activate a Release or approve law/equation/Rule/Evidence changes. Admin must perform the **최종 Release 활성화**. 작성자나 제출 Agent는 **자신이 만든 제안**을 승인하지 않는다: no `self-approval`, role substitution, service-token approval, or implied consent.

Before Admin approval, **Admin이 원문과 exact object digest를 직접 확인** and confirms Evidence scope, translation, assumptions, applicability, test results, conflicts, and affected verdicts. Activation uses `science_release_activate` only through an authenticated Admin path and immediate explicit confirmation. Withdrawal follows the same identity boundary.

## Failure behavior

Stop at the current layer when URL, locator, hash, translation review, claim scope, authority, role, separation of duties, or exact digest cannot be verified. Preserve the proposal and validation report; do not repair missing support with model memory, generated quotations, or unrelated sources.

External research can discover a Source candidate. It becomes usable only after the complete review path above.
