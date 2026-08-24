---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-evidence",
  "title": "spin-coating: microchemicals-spin-mechanism",
  "description": "Short, locator-bound authoritative Evidence draft pending Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceEvidence",
    "spin-coating",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:evidence:spin-coating:microchemicals-spin-mechanism",
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
    "evidence_id": "sci-evidence:spin-coating:microchemicals-spin-mechanism",
    "source_id": "sci-source:microchemicals-spin-coating-photoresist",
    "locator": {
      "medium": "pdf",
      "resource_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "requested_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "resolved_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "content_hash": "sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7",
      "hash_scope": "retrieved_pdf_bytes",
      "pdf_page_index": 0,
      "printed_page": "PDF page 1",
      "section": "Principle of Spin-coating",
      "retrieved_at": "2026-08-25T05:14:00+09:00",
      "exact": true,
      "preservation_status": "checksum_only_no_archived_copy",
      "transcription_method": "agent-reviewed visual/PDF text transcription preserving wording and punctuation"
    },
    "original_text": "Due to the centrifugal force, the dispensed resist spreads into a uniform resist film of desired film thickness, excess resist is spun off the edge of the substrate. At the same time, a part of the solvent evaporates from the resist film, so that its thinning stopped.",
    "original_text_hash": "sha256:ca8128d6ed35e34e964a4b3b99c2c6aa13f6e7903fb6b41e6411c0dfe946f836",
    "language": "en",
    "reviewed_translation": "원심 작용으로 도포된 레지스트가 퍼지고 여분은 기판 가장자리로 빠져나가며, 동시에 용매 일부가 증발해 막의 추가 박막화가 멈춘다.",
    "decision_eligibility": "pending_review",
    "access_limitation": "",
    "contextual_limitations": [
      "This mechanism span does not provide a numeric recipe, exponent, or equipment-specific film thickness."
    ],
    "claim_scope": {
      "schema_version": "0.1",
      "allowed_claims": [
        {
          "claim_family": "spin_coating.mechanism.centrifugal_spreading_solvent_evaporation",
          "purpose": "Spin coating spreads photoresist and removes excess material while concurrent solvent evaporation contributes to stopping further thinning.",
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
        "This mechanism span does not provide a numeric recipe, exponent, or equipment-specific film thickness."
      ]
    },
    "claim_scope_hash": "sha256:0937143a23646b54748655198bda5f3357e19484093ba343ed3cc772b1f2c81d",
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
