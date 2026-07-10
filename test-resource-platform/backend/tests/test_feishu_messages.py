import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher
from app.db.session import get_engine, get_session_factory
from app.integrations.feishu.messages import (
    FeishuInboundMessage,
    dispatch_feishu_inbound_message,
    handle_feishu_inbound_message,
)
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuMessageEvent,
    FeishuMessageHandledStatus,
    FeishuPlatformType,
    FeishuUserBinding,
)
from app.leases.models import LeaseStatus, ResourceLease
from app.main import create_app
from app.resources.models import MachineResource, ResourcePool, ResourceType


@pytest.fixture
def session_factory(monkeypatch, tmp_path):
    database_path = tmp_path / "feishu_messages.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", "P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY=")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(create_app()):
        yield get_session_factory(get_settings().database_url)


def create_feishu_app(session) -> FeishuApp:
    cipher = CredentialCipher("P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY=")
    app = FeishuApp(
        name="lab assistant",
        platform_type=FeishuPlatformType.FEISHU,
        app_id="cli_messages",
        encrypted_app_secret=cipher.encrypt("sec_messages") or "",
        created_by_user_id=1,
    )
    session.add(app)
    session.flush()
    return app


def inbound(app: FeishuApp, message_id: str, text: str, sender_open_id: str = "ou_user"):
    return FeishuInboundMessage(
        feishu_app_id=app.id,
        message_id=message_id,
        chat_id="oc_chat",
        sender_open_id=sender_open_id,
        message_type="text",
        text=text,
        raw_event={"event": {"message": {"message_id": message_id}}},
    )


def bind_open_id(session, app: FeishuApp, open_id: str = "ou_user") -> None:
    session.add(
        FeishuUserBinding(
            feishu_app_id=app.id,
            platform_user_id=1,
            open_id=open_id,
            display_name="Alice",
        )
    )
    session.flush()


def create_machine(session, resource_code: str, name: str | None = None) -> MachineResource:
    pool = session.scalar(select(ResourcePool).where(ResourcePool.name == "lab"))
    if pool is None:
        pool = ResourcePool(name="lab")
        session.add(pool)
        session.flush()
    machine = MachineResource(
        resource_code=resource_code,
        name=name or resource_code,
        resource_type=ResourceType.PHYSICAL,
        pool_id=pool.id,
    )
    session.add(machine)
    session.flush()
    return machine


def test_help_message_records_event_and_replies(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)

        result = handle_feishu_inbound_message(session, inbound(app, "om_help", "/help"))

        assert result.duplicate is False
        assert result.reply_text is not None
        assert "/whoami" in result.reply_text
        assert "/machines" in result.reply_text

        event = session.scalar(select(FeishuMessageEvent))
        assert event is not None
        assert event.message_id == "om_help"
        assert event.sender_open_id == "ou_user"
        assert event.handled_status == FeishuMessageHandledStatus.REPLIED
        assert json.loads(event.raw_event_json) == {
            "event": {"message": {"message_id": "om_help"}}
        }


def test_message_id_is_deduplicated(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)

        first = handle_feishu_inbound_message(session, inbound(app, "om_dup", "/help"))
        second = handle_feishu_inbound_message(session, inbound(app, "om_dup", "/whoami"))

        count = session.scalar(select(func.count()).select_from(FeishuMessageEvent))
        assert first.duplicate is False
        assert second.duplicate is True
        assert second.reply_text is None
        assert count == 1


def test_whoami_message_reports_binding_status(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        session.add(
            FeishuUserBinding(
                feishu_app_id=app.id,
                platform_user_id=1,
                open_id="ou_bound",
                display_name="Alice",
            )
        )
        session.flush()

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_whoami", "/whoami", sender_open_id="ou_bound"),
        )

        assert result.reply_text is not None
        assert "ou_bound" in result.reply_text
        assert "admin" in result.reply_text
        assert "ADMIN" in result.reply_text


def test_dispatch_message_sends_reply_once(session_factory, monkeypatch) -> None:
    sent: list[dict[str, str]] = []

    def fake_send_feishu_text_reply(platform_type, app_id, app_secret, message_id, text):
        sent.append(
            {
                "platform_type": platform_type,
                "app_id": app_id,
                "app_secret": app_secret,
                "message_id": message_id,
                "text": text,
            }
        )

    monkeypatch.setattr(
        "app.integrations.feishu.messages.send_feishu_text_reply",
        fake_send_feishu_text_reply,
    )
    with session_factory() as session:
        app = create_feishu_app(session)

        result = dispatch_feishu_inbound_message(
            session,
            inbound(app, "om_dispatch", "/help"),
            CredentialCipher("P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY="),
        )

        assert result.reply_sent is True
        assert result.duplicate is False
        assert len(sent) == 1
        assert sent[0]["platform_type"] == "FEISHU"
        assert sent[0]["app_id"] == "cli_messages"
        assert sent[0]["app_secret"] == "sec_messages"
        assert sent[0]["message_id"] == "om_dispatch"
        assert "/whoami" in sent[0]["text"]


def test_dispatch_duplicate_message_does_not_send_reply(session_factory, monkeypatch) -> None:
    sent: list[str] = []

    def fake_send_feishu_text_reply(platform_type, app_id, app_secret, message_id, text):
        sent.append(message_id)

    monkeypatch.setattr(
        "app.integrations.feishu.messages.send_feishu_text_reply",
        fake_send_feishu_text_reply,
    )
    with session_factory() as session:
        app = create_feishu_app(session)
        cipher = CredentialCipher("P4hnnBWP4qB-txrlIG20aQRk0RxEholITHKAcC3atkY=")

        dispatch_feishu_inbound_message(session, inbound(app, "om_once", "/help"), cipher)
        duplicate = dispatch_feishu_inbound_message(
            session,
            inbound(app, "om_once", "/whoami"),
            cipher,
        )

        assert duplicate.duplicate is True
        assert duplicate.reply_sent is False
        assert sent == ["om_once"]


def test_unbound_user_cannot_create_lease_from_feishu(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        create_machine(session, "machine-01")

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_unbound_lease", "/lease machine-01 60 debug"),
        )

        assert result.reply_text is not None
        assert "请先绑定平台用户" in result.reply_text
        assert session.scalar(select(ResourceLease)) is None


def test_bound_user_can_list_free_machines_and_create_lease(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        create_machine(session, "machine-02")
        create_machine(session, "machine-03")
        handle_feishu_inbound_message(
            session,
            inbound(app, "om_lease_existing", "/lease machine-02 30 smoke"),
        )

        free_result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_free", "/machines free"),
        )
        lease_result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_lease", "/lease machine-01 60 debug"),
        )

        assert free_result.reply_text is not None
        assert "machine-01" in free_result.reply_text
        assert "machine-03" in free_result.reply_text
        assert "machine-02" not in free_result.reply_text
        assert lease_result.reply_text is not None
        assert "占用成功" in lease_result.reply_text
        assert "machine-01" in lease_result.reply_text
        lease = session.scalar(
            select(ResourceLease).join(MachineResource).where(
                MachineResource.resource_code == "machine-01"
            )
        )
        assert lease is not None
        assert lease.status == LeaseStatus.ACTIVE
        assert lease.user_id == 1


def test_bound_user_can_list_and_release_own_leases(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        lease_result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_lease_release", "/lease machine-01 60 debug"),
        )
        lease_id = session.scalar(select(ResourceLease.lease_id))

        my_leases = handle_feishu_inbound_message(
            session,
            inbound(app, "om_my_leases", "/my-leases"),
        )
        release_result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_release", f"/release {lease_id}"),
        )

        assert lease_result.reply_text is not None
        assert lease_id is not None
        assert my_leases.reply_text is not None
        assert lease_id in my_leases.reply_text
        assert "machine-01" in my_leases.reply_text
        assert release_result.reply_text is not None
        assert "释放成功" in release_result.reply_text
        lease = session.scalar(select(ResourceLease).where(ResourceLease.lease_id == lease_id))
        assert lease is not None
        assert lease.status == LeaseStatus.RELEASED
