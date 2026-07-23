import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher
from app.db.session import get_engine, get_session_factory
from app.integrations.feishu.messages import (
    FeishuCardAction,
    FeishuInboundMessage,
    dispatch_feishu_inbound_message,
    handle_feishu_card_action,
    handle_feishu_inbound_message,
)
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuBindingCode,
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
        assert result.reply_card is not None
        card_json = json.dumps(result.reply_card, ensure_ascii=False)
        assert "测试资源平台" in card_json
        assert '"action": "show_free_machines"' in card_json
        assert '"action": "show_my_leases"' in card_json

        event = session.scalar(select(FeishuMessageEvent))
        assert event is not None
        assert event.message_id == "om_help"
        assert event.sender_open_id == "ou_user"
        assert event.handled_status == FeishuMessageHandledStatus.REPLIED
        assert json.loads(event.raw_event_json) == {
            "event": {"message": {"message_id": "om_help"}}
        }


def test_unmatched_bound_message_uses_shared_llm_assistant(
    session_factory, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "tool-model")
    get_settings.cache_clear()

    class FakeLlmClient:
        call_count = 0

        def complete(self, messages: list[dict], tools: list[dict]) -> dict:
            self.call_count += 1
            if self.call_count == 1:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-feishu-search",
                            "type": "function",
                            "function": {
                                "name": "search_machines",
                                "arguments": '{"architecture":"x86_64"}',
                            },
                        }
                    ],
                }
            assert "server-feishu-x86" in messages[-1]["content"]
            return {"role": "assistant", "content": "飞书中找到 server-feishu-x86。"}

    monkeypatch.setattr(
        "app.integrations.feishu.messages.create_llm_client",
        lambda settings: FakeLlmClient(),
        raising=False,
    )

    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        machine = create_machine(session, "server-feishu-x86")
        machine.architecture = "x86_64"

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_llm_search", "帮我找一台 x86 机器"),
        )

        assert result.reply_text == "飞书中找到 server-feishu-x86。"
        assert result.reply_card is not None
        card_json = json.dumps(result.reply_card, ensure_ascii=False)
        assert "智能匹配结果" in card_json
        assert "server-feishu-x86" in card_json
        assert '"action": "confirm_lease"' in card_json


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
    sent: list[dict] = []

    def fake_send_feishu_card_reply(platform_type, app_id, app_secret, message_id, card):
        sent.append(
            {
                "platform_type": platform_type,
                "app_id": app_id,
                "app_secret": app_secret,
                "message_id": message_id,
                "card": card,
            }
        )

    monkeypatch.setattr(
        "app.integrations.feishu.messages.send_feishu_card_reply",
        fake_send_feishu_card_reply,
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
        assert "测试资源平台" in json.dumps(sent[0]["card"], ensure_ascii=False)


def test_dispatch_duplicate_message_does_not_send_reply(session_factory, monkeypatch) -> None:
    sent: list[str] = []

    def fake_send_feishu_card_reply(platform_type, app_id, app_secret, message_id, card):
        sent.append(message_id)

    monkeypatch.setattr(
        "app.integrations.feishu.messages.send_feishu_card_reply",
        fake_send_feishu_card_reply,
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


def test_unbound_user_can_bind_with_web_generated_code(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        session.add(FeishuBindingCode(code="ABC123", platform_user_id=1))
        session.flush()

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_bind", "/bind ABC123", sender_open_id="ou_self"),
        )

        assert result.reply_text is not None
        assert "绑定成功" in result.reply_text
        binding = session.scalar(
            select(FeishuUserBinding).where(
                FeishuUserBinding.feishu_app_id == app.id,
                FeishuUserBinding.open_id == "ou_self",
            )
        )
        assert binding is not None
        assert binding.platform_user.username == "admin"
        binding_code = session.scalar(
            select(FeishuBindingCode).where(FeishuBindingCode.code == "ABC123")
        )
        assert binding_code is not None
        assert binding_code.consumed_at is not None


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


def test_free_machine_command_builds_interactive_card(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        create_machine(session, "machine-02")

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_free_card", "/machines free"),
        )

        assert result.reply_text is not None
        assert result.reply_card is not None
        card_json = json.dumps(result.reply_card, ensure_ascii=False)
        assert "空闲机器" in card_json
        assert "machine-01" in card_json
        assert "machine-02" in card_json
        assert '"action": "confirm_lease"' in card_json
        assert '"duration_minutes": 60' in card_json


def test_card_lease_action_requires_confirmation_before_creating_lease(
    session_factory,
) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")

        result = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={
                    "action": "confirm_lease",
                    "resource_code": "machine-01",
                    "duration_minutes": 60,
                    "purpose": "feishu-card",
                },
                raw_event={"event": {"action": {"value": {"action": "lease"}}}},
            ),
        )

        assert result.reply_text is not None
        assert "machine-01" in result.reply_text
        assert "确认" in result.reply_text
        assert result.reply_card is not None
        card_json = json.dumps(result.reply_card, ensure_ascii=False)
        assert '"action": "execute_lease"' in card_json
        assert session.scalar(select(ResourceLease)) is None


def test_confirmed_card_lease_action_creates_lease_for_bound_user(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")

        result = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={
                    "action": "execute_lease",
                    "resource_code": "machine-01",
                    "duration_minutes": 60,
                    "purpose": "feishu-card",
                },
                raw_event={"event": {"action": {"value": {"action": "execute_lease"}}}},
            ),
        )

        assert result.reply_text is not None
        assert "占用成功" in result.reply_text
        assert result.reply_card is not None
        assert "machine-01" in json.dumps(result.reply_card, ensure_ascii=False)
        lease = session.scalar(
            select(ResourceLease).join(MachineResource).where(
                MachineResource.resource_code == "machine-01"
            )
        )
        assert lease is not None
        assert lease.status == LeaseStatus.ACTIVE
        assert lease.user_id == 1


def test_retried_confirmed_card_action_is_deduplicated(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        action = FeishuCardAction(
            feishu_app_id=app.id,
            operator_open_id="ou_user",
            action_id="evt_execute_lease_01",
            action_value={
                "action": "execute_lease",
                "resource_code": "machine-01",
                "duration_minutes": 60,
                "purpose": "feishu-card",
            },
            raw_event={"header": {"event_id": "evt_execute_lease_01"}},
        )

        first = handle_feishu_card_action(session, action)
        second = handle_feishu_card_action(session, action)

        assert first.duplicate is False
        assert second.duplicate is True
        assert second.reply_text == first.reply_text
        assert session.scalar(select(func.count()).select_from(ResourceLease)) == 1


def test_my_leases_command_builds_action_card(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        handle_feishu_inbound_message(
            session,
            inbound(app, "om_lease_for_card", "/lease machine-01 60 debug"),
        )

        result = handle_feishu_inbound_message(
            session,
            inbound(app, "om_my_leases_card", "/my-leases"),
        )

        assert result.reply_card is not None
        card_json = json.dumps(result.reply_card, ensure_ascii=False)
        assert "我的租约" in card_json
        assert "machine-01" in card_json
        assert '"action": "confirm_extend"' in card_json
        assert '"action": "confirm_release"' in card_json


def test_card_extend_and_release_actions_require_confirmation(session_factory) -> None:
    with session_factory() as session:
        app = create_feishu_app(session)
        bind_open_id(session, app)
        create_machine(session, "machine-01")
        handle_feishu_inbound_message(
            session,
            inbound(app, "om_lease_for_actions", "/lease machine-01 60 debug"),
        )
        lease = session.scalar(select(ResourceLease))
        assert lease is not None
        original_expiry = lease.expires_at

        extend_confirmation = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={
                    "action": "confirm_extend",
                    "lease_id": lease.lease_id,
                    "duration_minutes": 60,
                },
                raw_event={},
            ),
        )
        assert lease.expires_at == original_expiry
        assert extend_confirmation.reply_card is not None
        assert '"action": "execute_extend"' in json.dumps(
            extend_confirmation.reply_card, ensure_ascii=False
        )

        extended = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={
                    "action": "execute_extend",
                    "lease_id": lease.lease_id,
                    "duration_minutes": 60,
                },
                raw_event={},
            ),
        )
        assert "延期成功" in (extended.reply_text or "")
        assert lease.expires_at.replace(tzinfo=None) > original_expiry.replace(tzinfo=None)

        release_confirmation = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={"action": "confirm_release", "lease_id": lease.lease_id},
                raw_event={},
            ),
        )
        assert lease.status == LeaseStatus.ACTIVE
        assert release_confirmation.reply_card is not None
        assert '"action": "execute_release"' in json.dumps(
            release_confirmation.reply_card, ensure_ascii=False
        )

        released = handle_feishu_card_action(
            session,
            FeishuCardAction(
                feishu_app_id=app.id,
                operator_open_id="ou_user",
                action_value={"action": "execute_release", "lease_id": lease.lease_id},
                raw_event={},
            ),
        )
        assert "释放成功" in (released.reply_text or "")
        assert lease.status == LeaseStatus.RELEASED


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
