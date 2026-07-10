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
from app.main import create_app


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
