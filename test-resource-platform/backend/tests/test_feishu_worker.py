from app.integrations.feishu.worker import lark_event_to_inbound_message


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
