---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-evidence",
  "title": "materials: nist-thin-film-bulk-difference",
  "description": "Short, locator-bound authoritative Evidence draft pending Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceEvidence",
    "materials",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:evidence:materials:nist-thin-film-bulk-difference",
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
      "ref": "boi:public:science:source:nistir-5851-1997"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "evidence_id": "sci-evidence:materials:nist-thin-film-bulk-difference",
    "source_id": "sci-source:nistir-5851-1997",
    "locator": {
      "medium": "pdf",
      "resource_url": "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir5851r1997.pdf",
      "requested_url": "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir5851r1997.pdf",
      "resolved_url": "https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir5851r1997.pdf",
      "content_hash": "sha256:7f4e939b3fd4dc621ffd6a534773b08da687d4052b2148c865436ac30b9b854b",
      "hash_scope": "retrieved_pdf_bytes",
      "pdf_page_index": 24,
      "printed_page": "printed page 17; PDF page 25",
      "section": "Micromechanical Measurements — Thin Film Mechanical Properties",
      "retrieved_at": "2026-08-25T05:14:00+09:00",
      "exact": true,
      "preservation_status": "checksum_only_no_archived_copy",
      "transcription_method": "agent-reviewed visual/PDF text transcription preserving wording and punctuation"
    },
    "original_text": "These properties differ from those of bulk material of the same chemical composition due to differences in the deposition conditions.",
    "original_text_hash": "sha256:0b6c4f292aaa42a15355e25a1f0ab700bccf9f450665216e0845b8117044a0b0",
    "language": "en",
    "reviewed_translation": "이러한 박막의 기계적 물성은 증착 조건의 차이 때문에 화학 조성이 같은 벌크 재료의 물성과도 다르다.",
    "decision_eligibility": "pending_review",
    "access_limitation": "",
    "contextual_limitations": [
      "This span does not quantify every thin-film property or predict the direction and magnitude of a particular film's difference."
    ],
    "claim_scope": {
      "schema_version": "0.1",
      "allowed_claims": [
        {
          "claim_family": "materials.thin_film_bulk_property_nontransferability",
          "purpose": "Mechanical properties of thin films can differ from bulk material of the same chemical composition because deposition conditions differ.",
          "required_conditions": [
            {
              "key": "property_class",
              "operator": "eq",
              "value": "mechanical"
            },
            {
              "key": "material_form",
              "operator": "eq",
              "value": "thin_film"
            },
            {
              "key": "comparison_composition",
              "operator": "eq",
              "value": "same"
            }
          ]
        }
      ],
      "forbidden_claim_families": [
        "unbounded_or_unqualified_claims"
      ],
      "limitations": [
        "This span does not quantify every thin-film property or predict the direction and magnitude of a particular film's difference."
      ]
    },
    "claim_scope_hash": "sha256:0058af8531a119403e7eebda85425f5e0d203543433c1ddf1915d38b9da46618",
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
