from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.health import get_engine
from app.main import create_app


def test_health_returns_request_id_and_database_status(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    get_settings.cache_clear()
    get_engine.cache_clear()

    client = TestClient(create_app())
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json() == {
        "status": "ok",
        "app": "Test Resource Platform",
        "version": "0.1.0",
        "request_id": "test-request",
        "database": {"status": "ok", "error": None},
    }
