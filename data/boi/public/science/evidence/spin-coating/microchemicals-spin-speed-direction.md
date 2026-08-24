---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-evidence",
  "title": "spin-coating: microchemicals-spin-speed-direction",
  "description": "Short, locator-bound authoritative Evidence draft pending Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceEvidence",
    "spin-coating",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:evidence:spin-coating:microchemicals-spin-speed-direction",
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
    "evidence_id": "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
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
      "section": "Influence of the Attained Spin Speed",
      "retrieved_at": "2026-08-25T05:14:00+09:00",
      "exact": true,
      "preservation_status": "checksum_only_no_archived_copy",
      "transcription_method": "agent-reviewed visual/PDF text transcription preserving wording and punctuation"
    },
    "original_text": "If, as usual, the spin-coating of the resist from the substrate continues until it has been stopped by the drying process, the attainable resist film thickness decreases in a good approximation with the reciprocal square root of the spin speed (Fig. 54).",
    "original_text_hash": "sha256:40b4fe4a8c1931dc6fc235fdb77a170a111504c8eca41566186953d6d5687d27",
    "language": "en",
    "reviewed_translation": "통상적으로 레지스트의 스핀 오프가 건조로 멈출 때까지 계속되는 조건에서는, 달성 가능한 막 두께가 스핀 속도의 제곱근 역수에 좋은 근사로 감소한다.",
    "decision_eligibility": "pending_review",
    "access_limitation": "",
    "contextual_limitations": [
      "The approximation does not authorize a numeric recipe, equipment transfer, or extrapolation beyond a qualified process domain."
    ],
    "claim_scope": {
      "schema_version": "0.1",
      "allowed_claims": [
        {
          "claim_family": "spin_coating.spin_speed_thickness_direction.drying_limited_process",
          "purpose": "For a drying-limited photoresist spin-coating process, attainable film thickness decreases approximately with the reciprocal square root of spin speed.",
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
            },
            {
              "key": "thinning_continues_until",
              "operator": "eq",
              "value": "drying_stops_flow"
            }
          ]
        }
      ],
      "forbidden_claim_families": [
        "unbounded_or_unqualified_claims"
      ],
      "limitations": [
        "The approximation does not authorize a numeric recipe, equipment transfer, or extrapolation beyond a qualified process domain."
      ]
    },
    "claim_scope_hash": "sha256:b9e788573d5bb37a51a131c93947bdb0701ba98a1fe54c8e4415a273fb2fa4a2",
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
