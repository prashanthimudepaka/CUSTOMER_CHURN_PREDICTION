"""Smoke tests — keep the repo green from day 1.

These verify the scaffold is wired correctly. Real model/API tests
are added in Phases 2 and 4.
"""

from fastapi.testclient import TestClient

from src import config
from src.api.main import app

client = TestClient(app)


def test_project_directories_exist():
    assert config.DATA_DIR.is_dir()
    assert config.MODEL_DIR.is_dir()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_is_stubbed_not_broken():
    # Until Phase 4, /predict should politely say 501 — not crash with 500.
    response = client.post("/predict")
    assert response.status_code == 501
