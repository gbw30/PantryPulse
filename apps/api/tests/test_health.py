from fastapi.testclient import TestClient

from app.main import app


def test_process_liveness_does_not_claim_domain_readiness():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "process"}


def test_unimplemented_solver_is_not_exposed():
    with TestClient(app) as client:
        response = client.post("/api/v1/scenarios/example/plans", json={})
    assert response.status_code == 404
