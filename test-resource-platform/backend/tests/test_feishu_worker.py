from app.integrations.feishu.worker import (
    FeishuWorkerContext,
    handle_card_action_event,
    lark_event_to_card_action,
    lark_event_to_inbound_message,
)


def test_lark_message_event_is_converted_to_inbound_message() -> None:
    event = {
        "event": {
            "sender": {"sender_id": {"open_id": "ou_user"}},
            "message": {
                "message_id": "om_message",
                "chat_id": "oc_chat",
                "message_type": "text",
                "content": '{"text":"/help"}',
            },
        }
    }

    inbound = lark_event_to_inbound_message(7, event)

    assert inbound.feishu_app_id == 7
    assert inbound.message_id == "om_message"
    assert inbound.chat_id == "oc_chat"
    assert inbound.sender_open_id == "ou_user"
    assert inbound.message_type == "text"
    assert inbound.text == "/help"
    assert inbound.raw_event == event


def test_lark_card_action_event_is_converted_to_card_action() -> None:
    event = {
        "header": {"event_id": "evt_card_01"},
        "event": {
            "operator": {"open_id": "ou_user"},
            "action": {
                "value": {
                    "action": "lease",
                    "resource_code": "machine-01",
                    "duration_minutes": 60,
                }
            },
        }
    }

    action = lark_event_to_card_action(7, event)

    assert action.feishu_app_id == 7
    assert action.operator_open_id == "ou_user"
    assert action.action_value["action"] == "lease"
    assert action.action_value["resource_code"] == "machine-01"
    assert action.action_id == "evt_card_01"
    assert action.raw_event == event


def test_card_action_response_wraps_updated_card_as_raw(monkeypatch) -> None:
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def commit(self):
            pass

        def rollback(self):
            pass

    class FakeResult:
        reply_text = "操作完成"
        reply_card = {"header": {"title": {"content": "结果"}}}

    monkeypatch.setattr(
        "app.integrations.feishu.worker.lark_event_to_card_action",
        lambda app_id, event: object(),
    )
    monkeypatch.setattr(
        "app.integrations.feishu.worker.handle_feishu_card_action",
        lambda session, action: FakeResult(),
    )
    context = FeishuWorkerContext(
        app=type("App", (), {"id": 7})(),
        app_secret="secret",
        session_factory=FakeSession,
        cipher=object(),
    )

    response = handle_card_action_event(context, {})

    assert response == {
        "toast": {"type": "success", "content": "操作完成"},
        "card": {
            "type": "raw",
            "data": {"header": {"title": {"content": "结果"}}},
        },
    }
