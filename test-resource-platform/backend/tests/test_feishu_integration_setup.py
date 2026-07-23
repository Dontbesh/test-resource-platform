from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.bootstrap.admin import ensure_database_schema, ensure_initial_admin
from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher
from app.db.session import get_engine, get_session_factory
from app.integrations.feishu.client import FeishuBotInfo
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuBindingCode,
    FeishuSetupSession,
    FeishuSetupStatus,
    FeishuUserBinding,
)
from app.integrations.feishu.worker import FeishuWorkerState, feishu_worker_manager
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


def test_app_lifespan_restores_and_stops_saved_feishu_worker(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "feishu_restore.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", TEST_FERNET_KEY)
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    settings = get_settings()
    ensure_database_schema(settings)
    session_factory = get_session_factory(settings.database_url)
    with session_factory() as session:
        ensure_initial_admin(session, settings)
        app = FeishuApp(
            name="lab assistant",
            platform_type="FEISHU",
            app_id="cli_restore",
            encrypted_app_secret=CredentialCipher(TEST_FERNET_KEY).encrypt("sec_restore") or "",
            created_by_user_id=1,
        )
        session.add(app)
        session.commit()
        app_id = app.id

    events: list[tuple[str, str]] = []

    class FakeRuntime:
        def start(self) -> None:
            events.append(("start", "cli_restore"))

        def stop(self) -> None:
            events.append(("stop", "cli_restore"))

    feishu_worker_manager.stop_all()
    monkeypatch.setattr(
        feishu_worker_manager,
        "runtime_factory",
        lambda context: FakeRuntime(),
    )

    with TestClient(create_app()):
        status = feishu_worker_manager.status(app_id)
        assert status.state == FeishuWorkerState.RUNNING
        assert events == [("start", "cli_restore")]

    assert feishu_worker_manager.status(app_id).state == FeishuWorkerState.STOPPED
    assert events == [("start", "cli_restore"), ("stop", "cli_restore")]


def test_admin_can_begin_feishu_setup_and_persist_session(client, monkeypatch) -> None:
    calls: list[tuple[str, dict[str, str]]] = []
    long_device_code = "v1:" + ("x" * 700)

    def fake_registration_call(base_url: str, action: str, params: dict[str, str] | None):
        calls.append((action, params or {}))
        if action == "init":
            return {"supported_auth_methods": ["client_secret"]}
        return {
            "device_code": long_device_code,
            "verification_uri_complete": "https://open.feishu.cn/qr/device-001",
            "interval": 3,
            "expires_in": 3600,
        }

    monkeypatch.setattr(
        "app.integrations.feishu.service.registration_call",
        fake_registration_call,
    )
    login(client, "admin", "Admin@123456")

    response = client.post("/api/v1/integrations/feishu/setup/begin")

    assert response.status_code == 201
    body = response.json()
    assert body["device_code"] == long_device_code
    assert body["qr_url"] == "https://open.feishu.cn/qr/device-001"
    assert body["interval"] == 3
    assert body["expires_in"] == 3600
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
        assert setup.device_code == long_device_code
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


def test_save_feishu_app_starts_worker_automatically(client, monkeypatch) -> None:
    events: list[tuple[str, str]] = []

    class FakeRuntime:
        def start(self) -> None:
            events.append(("start", "cli_auto_start"))

        def stop(self) -> None:
            events.append(("stop", "cli_auto_start"))

    monkeypatch.setattr(
        feishu_worker_manager,
        "runtime_factory",
        lambda context: FakeRuntime(),
    )
    login(client, "admin", "Admin@123456")

    response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "auto-start assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_auto_start",
            "app_secret": "sec_auto_start",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "CONNECTED"
    assert events == [("start", "cli_auto_start")]


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


def test_admin_can_check_feishu_app_connection(client, monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake_fetch_feishu_bot_info(platform_type, app_id: str, app_secret: str):
        seen["platform_type"] = platform_type
        seen["app_id"] = app_id
        seen["app_secret"] = app_secret
        return FeishuBotInfo(open_id="ou_bot", app_name="资源助手")

    monkeypatch.setattr(
        "app.integrations.feishu.service.fetch_feishu_bot_info",
        fake_fetch_feishu_bot_info,
    )
    login(client, "admin", "Admin@123456")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_check",
            "app_secret": "sec_check",
        },
    )
    app_id = save_response.json()["id"]

    response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/check-connection")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CONNECTED"
    assert body["bot_open_id"] == "ou_bot"
    assert body["last_connected_at"] is not None
    assert body["last_error"] is None
    assert seen == {
        "platform_type": "FEISHU",
        "app_id": "cli_check",
        "app_secret": "sec_check",
    }


def test_admin_can_start_and_stop_feishu_worker(client, monkeypatch) -> None:
    events: list[tuple[str, str, str | None]] = []

    class FakeRuntime:
        def __init__(self, app_id: str, app_secret: str) -> None:
            self.app_id = app_id
            self.app_secret = app_secret

        def start(self) -> None:
            events.append(("start", self.app_id, self.app_secret))

        def stop(self) -> None:
            events.append(("stop", self.app_id, None))

    def fake_runtime_factory(context):
        return FakeRuntime(context.app.app_id, context.app_secret)

    from app.integrations.feishu import worker as feishu_worker

    feishu_worker.feishu_worker_manager.stop_all()
    monkeypatch.setattr(
        feishu_worker.feishu_worker_manager,
        "runtime_factory",
        fake_runtime_factory,
    )
    login(client, "admin", "Admin@123456")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_worker",
            "app_secret": "sec_worker",
        },
    )
    app_id = save_response.json()["id"]

    start_response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/start")
    stop_response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/stop")

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "CONNECTED"
    assert start_response.json()["last_connected_at"] is not None
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "DISCONNECTED"
    assert events == [
        ("start", "cli_worker", "sec_worker"),
        ("stop", "cli_worker", None),
    ]


def test_start_feishu_worker_records_runtime_error(client, monkeypatch) -> None:
    class FailingRuntime:
        def start(self) -> None:
            raise RuntimeError("websocket refused")

        def stop(self) -> None:
            raise AssertionError("stop should not be called")

    def fake_runtime_factory(context):
        return FailingRuntime()

    from app.integrations.feishu import worker as feishu_worker

    feishu_worker.feishu_worker_manager.stop_all()
    monkeypatch.setattr(
        feishu_worker.feishu_worker_manager,
        "runtime_factory",
        fake_runtime_factory,
    )
    login(client, "admin", "Admin@123456")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_worker_fail",
            "app_secret": "sec_worker_fail",
        },
    )
    app_id = save_response.json()["id"]

    response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/start")

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "FEISHU_WORKER_START_FAILED"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        app = session.get(FeishuApp, app_id)
        assert app is not None
        assert app.status == "ERROR"
        assert app.last_error == "websocket refused"


def test_check_feishu_app_connection_records_remote_error(client, monkeypatch) -> None:
    def fake_fetch_feishu_bot_info(platform_type, app_id: str, app_secret: str):
        raise RuntimeError("invalid app secret")

    monkeypatch.setattr(
        "app.integrations.feishu.service.fetch_feishu_bot_info",
        fake_fetch_feishu_bot_info,
    )
    login(client, "admin", "Admin@123456")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_bad",
            "app_secret": "sec_bad",
        },
    )
    app_id = save_response.json()["id"]

    response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/check-connection")

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "FEISHU_CONNECTION_CHECK_FAILED"

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        app = session.get(FeishuApp, app_id)
        assert app is not None
        assert app.status == "ERROR"
        assert app.last_error == "invalid app secret"


def test_te_cannot_check_feishu_app_connection(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    cipher = CredentialCipher(TEST_FERNET_KEY)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        app = FeishuApp(
            name="lab assistant",
            platform_type="FEISHU",
            app_id="cli_forbidden",
            encrypted_app_secret=cipher.encrypt("sec_forbidden") or "",
            created_by_user_id=1,
        )
        session.add(app)
        session.commit()
        app_id = app.id
    client.post("/api/v1/auth/logout")
    login(client, "tester", "Tester@123456")

    response = client.post(f"/api/v1/integrations/feishu/apps/{app_id}/check-connection")

    assert response.status_code == 403


def test_authenticated_user_can_create_feishu_binding_code(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    client.post("/api/v1/auth/logout")
    login(client, "tester", "Tester@123456")

    response = client.post("/api/v1/integrations/feishu/binding-codes")

    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) >= 6
    assert body["expires_at"] is not None

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        binding_code = session.scalar(select(FeishuBindingCode))
        assert binding_code is not None
        assert binding_code.code == body["code"]
        assert binding_code.platform_user.username == "tester"
        assert binding_code.consumed_at is None


def test_admin_can_create_and_list_feishu_user_binding(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_binding",
            "app_secret": "sec_binding",
        },
    )
    app_id = save_response.json()["id"]

    create_response = client.post(
        f"/api/v1/integrations/feishu/apps/{app_id}/bindings",
        json={
            "open_id": "ou_tester",
            "platform_username": "tester",
            "display_name": "Tester Feishu",
        },
    )
    list_response = client.get(f"/api/v1/integrations/feishu/apps/{app_id}/bindings")

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["open_id"] == "ou_tester"
    assert body["display_name"] == "Tester Feishu"
    assert body["platform_user"]["username"] == "tester"
    assert body["platform_user"]["role"] == "TE"
    assert list_response.status_code == 200
    assert list_response.json()[0]["open_id"] == "ou_tester"


def test_create_feishu_user_binding_rejects_unknown_user(client) -> None:
    login(client, "admin", "Admin@123456")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_unknown_binding",
            "app_secret": "sec_unknown_binding",
        },
    )
    app_id = save_response.json()["id"]

    response = client.post(
        f"/api/v1/integrations/feishu/apps/{app_id}/bindings",
        json={
            "open_id": "ou_missing",
            "platform_username": "missing",
            "display_name": None,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "PLATFORM_USER_NOT_FOUND"


def test_create_feishu_user_binding_upserts_existing_open_id(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    save_response = client.post(
        "/api/v1/integrations/feishu/setup/save",
        json={
            "name": "lab assistant",
            "platform_type": "FEISHU",
            "app_id": "cli_binding_upsert",
            "app_secret": "sec_binding_upsert",
        },
    )
    app_id = save_response.json()["id"]

    client.post(
        f"/api/v1/integrations/feishu/apps/{app_id}/bindings",
        json={
            "open_id": "ou_tester",
            "platform_username": "tester",
            "display_name": "Before",
        },
    )
    update_response = client.post(
        f"/api/v1/integrations/feishu/apps/{app_id}/bindings",
        json={
            "open_id": "ou_tester",
            "platform_username": "admin",
            "display_name": "After",
        },
    )

    assert update_response.status_code == 201
    body = update_response.json()
    assert body["display_name"] == "After"
    assert body["platform_user"]["username"] == "admin"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        bindings = list(session.scalars(select(FeishuUserBinding)))
        assert len(bindings) == 1


def test_te_cannot_create_feishu_user_binding(client) -> None:
    login(client, "admin", "Admin@123456")
    create_user(client, "tester", "Tester@123456", "TE")
    cipher = CredentialCipher(TEST_FERNET_KEY)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as session:
        app = FeishuApp(
            name="lab assistant",
            platform_type="FEISHU",
            app_id="cli_binding_forbidden",
            encrypted_app_secret=cipher.encrypt("sec_forbidden") or "",
            created_by_user_id=1,
        )
        session.add(app)
        session.commit()
        app_id = app.id
    client.post("/api/v1/auth/logout")
    login(client, "tester", "Tester@123456")

    response = client.post(
        f"/api/v1/integrations/feishu/apps/{app_id}/bindings",
        json={
            "open_id": "ou_tester",
            "platform_username": "tester",
            "display_name": "Tester",
        },
    )

    assert response.status_code == 403
