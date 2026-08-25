from __future__ import annotations

from fastapi.testclient import TestClient

from boi_api.app.science.digests import sha256_digest


def _manual_claim_candidate(document: str) -> dict:
    return {
        "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": len(document),
            "exact": document,
            "prefix": "",
            "suffix": "",
        },
        "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "sci:concept:increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [],
            "conditions": [],
            "process_stage": None,
            "material_state": None,
        },
        "ontology_refs": [
            "sci:binding:domain:spin-speed",
            "sci:binding:common:increases",
            "sci:binding:domain:film-thickness",
        ],
        "ambiguity_ids": [],
        "candidate_meanings": [
            {
                "ambiguity_id": None,
                "concept_role": "subject",
                "surface_term": "RPM",
                "ontology_ref": "sci:binding:domain:spin-speed",
                "meaning": "untrusted",
            },
            {
                "ambiguity_id": None,
                "concept_role": "relation",
                "surface_term": "높여야 한다",
                "ontology_ref": "sci:binding:common:increases",
                "meaning": "untrusted",
            },
            {
                "ambiguity_id": None,
                "concept_role": "object",
                "surface_term": "두께",
                "ontology_ref": "sci:binding:domain:film-thickness",
                "meaning": "untrusted",
            },
        ],
        "decision_impact": [],
    }


def test_main_application_registers_science_verifier_routes(boi_app_module) -> None:
    paths = {route.path for route in boi_app_module.app.routes}

    assert "/api/science/interpret" in paths
    assert "/api/science/aliases/detect" in paths
    assert "/api/science/claims/submit" in paths
    assert "/api/science/verify-document" in paths
    assert "/api/science/reports/{report_id}/export" in paths
    validator = (
        boi_app_module.app.state.science_runtime_store._report_authority_validator
    )
    assert validator is not None
    catalog = boi_app_module.app.state.science_catalog
    assert callable(catalog._trusted_clock)
    assert callable(catalog._trusted_holdout_resolver)
    assert boi_app_module.app.state.science_release_manager is not None
    assert boi_app_module.app.state.science_authority_registry is not None


def test_main_release_manager_is_wired_but_current_candidate_stays_unchanged(
    boi_app_module,
) -> None:
    """A missing private G5/G6 authority must block, not disable, activation."""

    catalog = boi_app_module.app.state.science_catalog
    release = catalog.resolve_release("sci-release:0.1.0")
    release_path = catalog._objects["release"][release.release_id].path
    before = release_path.read_bytes()
    request_digest = sha256_digest(
        {
            "operation": "activate",
            "release_id": release.release_id,
            "release_digest": release.content_hash,
        }
    )

    client = TestClient(boi_app_module.app)
    mutation = {
        "release_digest": release.content_hash,
        "request_digest": request_digest,
        "idempotency_key": "main-current-candidate-activation",
    }
    challenge = client.post(
        f"/api/science/admin/releases/{release.release_id}/activate-challenge"
        "?employee_id=100001",
        json=mutation,
    )
    assert challenge.status_code == 200
    response = client.post(
        f"/api/science/admin/releases/{release.release_id}/activate"
        "?employee_id=100001",
        json={
            **mutation,
            "challenge_id": challenge.json()["challenge_id"],
            "user_confirmed": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "science_operational_unavailable"
    assert "manager_unavailable" not in response.text
    assert release_path.read_bytes() == before


def test_main_application_keeps_science_authorization_separate(boi_app_module) -> None:
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/science/interpret?employee_id=100003",
        json={
            "document": "과학 주장",
            "request_id": "main-integration-001",
            "idempotency_key": "main-integration-interpret-001",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "science_access_denied"


def test_main_application_rejects_service_token_only_science_identity(
    boi_app_module,
) -> None:
    client = TestClient(boi_app_module.app)

    response = client.post(
        "/api/science/aliases/detect?employee_id=100001",
        headers={"x-service-token": boi_app_module.SERVICE_TOKEN},
        json={"document": "RPM 증가", "request_id": "service-token-spoof"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "science_access_denied"


def test_invalid_optional_qwen_config_does_not_break_llm_free_routes(
    boi_app_module, monkeypatch
) -> None:
    """Optional adapter configuration must be resolved only by /interpret."""

    boi_app_module.BOI_SCIENCE_EXPERIMENTAL_LLM_ENABLED = True
    for name in (
        "BOI_SCIENCE_LLM_BASE_URL",
        "BOI_SCIENCE_LLM_MODEL",
        "BOI_LLM_BASE_URL",
        "BOI_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(boi_app_module.app)
    document = "RPM을 높여야 한다 두께"

    aliases = client.post(
        "/api/science/aliases/detect?employee_id=100001",
        json={"document": document, "request_id": "invalid-qwen-aliases"},
    )
    user_revision = {
        "document": document,
        "candidate": _manual_claim_candidate(document),
        "idempotency_key": "invalid-qwen-manual-submit",
    }
    challenge = client.post(
        "/api/science/user-revisions/challenge?employee_id=100001",
        json=user_revision,
    )
    assert challenge.status_code == 200
    submitted = client.post(
        "/api/science/user-revisions/commit?employee_id=100001",
        json={
            **user_revision,
            "challenge_id": challenge.json()["challenge_id"],
        },
    )
    interpreted = client.post(
        "/api/science/interpret?employee_id=100001",
        json={
            "document": document,
            "request_id": "invalid-qwen-interpret",
            "idempotency_key": "invalid-qwen-interpret-request",
        },
    )

    assert aliases.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["candidate_claims"][0]["interpretation"]["user_confirmed"] is False
    assert interpreted.status_code == 503
    assert interpreted.json()["detail"] == {
        "code": "science_interpretation_unavailable",
        "diagnostic_code": "invalid_configuration",
        "message": "Scientific interpretation is temporarily unavailable.",
    }
