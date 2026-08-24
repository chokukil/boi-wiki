from __future__ import annotations

from fastapi.testclient import TestClient


def test_main_application_registers_science_verifier_routes(boi_app_module) -> None:
    paths = {route.path for route in boi_app_module.app.routes}

    assert "/api/science/interpret" in paths
    assert "/api/science/verify-document" in paths
    assert "/api/science/reports/{report_id}/export" in paths


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
