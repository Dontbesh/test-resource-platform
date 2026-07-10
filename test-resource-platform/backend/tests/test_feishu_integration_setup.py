from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.integrations.feishu.models import FeishuApp, FeishuSetupSession, FeishuSetupStatus
from app.main import create_app

TEST_FERNET_KEY = "P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY="


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "feishu_setup.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", TEST_FERNET_KEY)
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200


def create_user(client: TestClient, username: str, password: str, role: str) -> None:
    response = client.post(
        "/api/v1/users",
        json={"username": username, "password": password, "role": role},
    )
    assert response.status_code == 201


def test_admin_can_begin_feishu_setup_and_persist_session(client, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_registration_call(base_url: str, action: str, params: dict[str, str] | None):
        calls.append((action, params or {}))
        if action == "init":
            return {"supported_auth_methods": ["client_secret"]}
        return {
            "device_code": "device-001",
            "verification_uri_complete": "https://open.feishu.cn/qr/device-001",
            "interval": 3,
            "expire_in": 600,
        }

    monkeypatch.setattr(
        "app.integrations.feishu.service.registration_call",
        fake_registration_call,
    )
    login(client, "admin", "Admin@123456")

    response = client.post("/api/v1/integrations/feishu/setup/begin")

    assert response.status_code == 201
    body = response.json()
    assert body["device_code"] == "device-001"
    assert body["qr_url"] == "https://open.feishu.cn/qr/device-001"
    assert body["interval"] == 3
    assert calls == [
        ("init", {}),
        (
            "begin",
            {
                "archetype": "PersonalAgent",
                "auth_method": "client_secret",
                "request_user_info": "open_id",
            },
        ),
    ]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        setup = session.scalar(select(FeishuSetupSession))
        assert setup is not None
        assert setup.device_code == "device-001"
        assert setup.status == FeishuSetupStatus.PENDING


def test_te_cannot_begin_feishu_setup(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    client.post("/api/v1/auth/logout")
    login(client, "tester", "Tester@123456")

    response = client.post("/api/v1/integrations/feishu/setup/begin")

    assert response.status_code == 403


def test_poll_pending_and_completed_setup(client, monkeypatch) -> None:
    login(client, "admin", "Admin@123456")
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        setup = FeishuSetupSession(
            device_code="device-002",
            qr_url="https://open.feishu.cn/qr/device-002",
            base_url="https://accounts.feishu.cn",
            status=FeishuSetupStatus.PENDING,
            interval_seconds=5,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            created_by_user_id=1,
        )
        session.add(setup)
        session.commit()

    responses = [
        {"error": "authorization_pending"},
        {
            "client_id": "cli_test",
            "client_secret": "sec_test",
            "user_info": {"open_id": "ou_owner", "tenant_brand": "feishu"},
        },
    ]

    def fake_registration_call(base_url: str, action: str, params: dict[str, str] | None):
        assert action == "poll"
        assert params == {"device_code": "device-002"}
        return responses.pop(0)

    monkeypatch.setattr(
        "app.integrations.feishu.service.registration_call",
        fake_registration_call,
    )

    pending_response = client.post(
        "/api/v1/integrations/feishu/setup/poll",
        json={"device_code": "device-002"},
    )
    completed_response = client.post(
        "/api/v1/integrations/feishu/setup/poll",
        json={"device_code": "device-002"},
    )

    assert pending_response.status_code == 200
    assert pending_response.json()["status"] == "PENDING"
    assert completed_response.status_code == 200
    completed_body = completed_response.json()
    assert completed_body["status"] == "COMPLETED"
    assert completed_body["app_id"] == "cli_test"
    assert completed_body["app_secret"] == "sec_test"
    assert completed_body["owner_open_id"] == "ou_owner"


def test_save_feishu_app_encrypts_secret_and_list_does_not_expose_it(client) -> None:
    login(client, "admin", "Admin@123456")

    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_saved",
            "app_secret": "sec_saved",
            "owner_open_id": "ou_owner",
            "tenant_brand": "feishu",
        },
    )
    list_response = client.get("/api/v1/integrations/feishu/apps")

    assert save_response.status_code == 201
    body = save_response.json()
    assert body["name"] == "lab assistant"
    assert body["app_id"] == "cli_saved"
    assert "app_secret" not in body
    assert list_response.status_code == 200
    assert list_response.json()[0]["app_id"] == "cli_saved"
    assert "app_secret" not in list_response.json()[0]

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        app = session.scalar(select(FeishuApp))
        assert app is not None
        assert app.encrypted_app_secret != "sec_saved"
        assert "sec_saved" not in app.encrypted_app_secret


def test_save_feishu_app_requires_encryption_key(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "feishu_no_key.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(create_app()) as no_key_client:
        login(no_key_client, "admin", "Admin@123456")
        response = no_key_client.post(
            "/api/v1/integrations/feishu/setup/save",
            json={
                "platform_type": "FEISHU",
                "app_id": "cli_no_key",
                "app_secret": "sec_no_key",
            },
        )

    assert response.status_code == 500
    assert response.json()["detail"]["error_code"] == "CREDENTIAL_ENCRYPTION_KEY_NOT_CONFIGURED"
