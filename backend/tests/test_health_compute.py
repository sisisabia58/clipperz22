from fastapi.testclient import TestClient

from api import app


def test_health_reports_local_compute_when_modal_is_unconfigured(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_COMPUTE", "modal")
    monkeypatch.delenv("MODAL_GPU_BASE_URL", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.setenv("CLIPFORGE_WHISPER_DEVICE", "cpu")

    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["compute"] == "local"
    assert payload["whisper"]["device"] == "cpu"


def test_health_reports_modal_when_endpoint_is_configured(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_COMPUTE", "modal")
    monkeypatch.setenv("MODAL_GPU_BASE_URL", "https://example.modal.run")

    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["compute"] == "modal"
