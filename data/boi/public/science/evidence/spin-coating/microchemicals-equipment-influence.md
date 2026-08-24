---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-evidence",
  "title": "spin-coating: microchemicals-equipment-influence",
  "description": "Short, locator-bound authoritative Evidence draft pending Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceEvidence",
    "spin-coating",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:evidence:spin-coating:microchemicals-equipment-influence",
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
    "evidence_id": "sci-evidence:spin-coating:microchemicals-equipment-influence",
    "source_id": "sci-source:microchemicals-spin-coating-photoresist",
    "locator": {
      "medium": "pdf",
      "resource_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "requested_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "resolved_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
      "content_hash": "sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7",
      "hash_scope": "retrieved_pdf_bytes",
      "pdf_page_index": 2,
      "printed_page": "PDF page 3",
      "section": "Impact of the Equipment",
      "retrieved_at": "2026-08-25T05:14:00+09:00",
      "exact": true,
      "preservation_status": "checksum_only_no_archived_copy",
      "transcription_method": "agent-reviewed visual/PDF text transcription preserving wording and punctuation"
    },
    "original_text": "The equipment itself has a great influence on the coating result:",
    "original_text_hash": "sha256:436248d5f554ac208e70f12fb11a8b1e552f1ec9b41dcc8b2de31b902de6f3b8",
    "language": "en",
    "reviewed_translation": "장비 자체가 코팅 결과에 큰 영향을 준다.",
    "decision_eligibility": "pending_review",
    "access_limitation": "",
    "contextual_limitations": [
      "This sentence establishes equipment influence but does not establish a particular coater's exact thickness or a numeric setting."
    ],
    "claim_scope": {
      "schema_version": "0.1",
      "allowed_claims": [
        {
          "claim_family": "spin_coating.equipment.coating_result_influence",
          "purpose": "Spin-coating equipment can materially influence the coating result, so an exact equipment-specific result cannot be transferred from a general mechanism alone.",
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
        "This sentence establishes equipment influence but does not establish a particular coater's exact thickness or a numeric setting."
      ]
    },
    "claim_scope_hash": "sha256:7388462a108def2292e825ced5b03efcc443e4df852f110b022ab2e9807dedef",
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
