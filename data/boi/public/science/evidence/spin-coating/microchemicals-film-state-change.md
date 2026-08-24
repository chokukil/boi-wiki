---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-evidence",
  "title": "spin-coating: microchemicals-film-state-change",
  "description": "Short, locator-bound authoritative Evidence draft pending Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceEvidence",
    "spin-coating",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:evidence:spin-coating:microchemicals-film-state-change",
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
      "ref": "boi:public:science:source:microchemicals-spin-coating-photoresist"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "evidence_id": "sci-evidence:spin-coating:microchemicals-film-state-change",
    "source_id": "sci-source:microchemicals-spin-coating-photoresist",
    "locator": {
      "medium": "pdf",
      "resource_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "requested_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "resolved_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "content_hash": "sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7",
      "hash_scope": "retrieved_pdf_bytes",
      "pdf_page_index": 1,
      "printed_page": "PDF page 2",
      "section": "Influence of the Spin Time; Figure 55 caption",
      "retrieved_at": "2026-08-25T05:14:00+09:00",
      "exact": true,
      "preservation_status": "checksum_only_no_archived_copy",
      "transcription_method": "agent-reviewed visual/PDF text transcription preserving wording and punctuation"
    },
    "original_text": "The film thickness measured immediately after spin-coating (black) thins out further which is mainly due to residual solvent evaporating during the spin cycle (inside diagram).",
    "original_text_hash": "sha256:2bc33b5c7878c3e46a7e5c30276454f922dc6b8b6d7eeea3260fe28da7583729",
    "language": "en",
    "reviewed_translation": "스핀 코팅 직후 측정한 막 두께(검은색)는 더 얇아지며, 이는 주로 스핀 사이클 동안 잔류 용매가 증발하기 때문이다(내부 도표).",
    "decision_eligibility": "pending_review",
    "access_limitation": "",
    "contextual_limitations": [
      "The caption does not quantify a universal before/after thickness difference or authorize interchange between measurement states."
    ],
    "claim_scope": {
      "schema_version": "0.1",
      "allowed_claims": [
        {
          "claim_family": "spin_coating.film_thickness.process_state_difference",
          "purpose": "A thickness measured immediately after spin coating can change further as residual solvent evaporates, so the measurement state must remain explicit when thicknesses are compared.",
          "required_conditions": [
            {
              "key": "material_class",
              "operator": "eq",
              "value": "photoresist"
            },
            {
              "key": "process_method",
              "operator": "eq",
              "value": "spin_coating"
            }
          ]
        }
      ],
      "forbidden_claim_families": [
        "unbounded_or_unqualified_claims"
      ],
      "limitations": [
        "The caption does not quantify a universal before/after thickness difference or authorize interchange between measurement states."
      ]
    },
    "claim_scope_hash": "sha256:3f67c91ac21658ab7e3151cbe196652c6332917129890137c5fc9cb924903c90",
    "supports_knowledge": [],
    "translation": {
      "status": "agent_draft_pending_admin_review",
      "permission_status": "not_assessed",
      "original_controls": true,
      "actor": {
        "type": "agent",
        "agent_id": "codex"
      }
    },
    "curation_actor": {
      "type": "agent",
      "agent_id": "codex"
    },
    "curated_at": "2026-08-25T05:14:00+09:00",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Review scope

This exact span remains pending authorized Admin review. Any use is limited to its embedded claim scope and locator.
