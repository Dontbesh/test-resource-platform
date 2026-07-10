import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.credentials.crypto import CredentialCipher
from app.integrations.feishu.messages import (
    FeishuCardAction,
    FeishuInboundMessage,
    dispatch_feishu_inbound_message,
    handle_feishu_card_action,
)
from app.integrations.feishu.models import FeishuApp


class FeishuWorkerState(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class FeishuWorkerStartError(Exception):
    pass


class FeishuWorkerRuntime(Protocol):
    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@dataclass(frozen=True)
class FeishuWorkerContext:
    app: FeishuApp
    app_secret: str
    session_factory: Callable[[], Session]
    cipher: CredentialCipher


@dataclass(frozen=True)
class FeishuWorkerStatus:
    app_id: int
    state: FeishuWorkerState
    last_error: str | None = None


@dataclass
class _WorkerRecord:
    runtime: FeishuWorkerRuntime
    state: FeishuWorkerState
    last_error: str | None = None


class FeishuWorkerManager:
    def __init__(
        self,
        runtime_factory: Callable[[FeishuWorkerContext], FeishuWorkerRuntime]
        | None = None,
    ) -> None:
        self.runtime_factory = runtime_factory or create_feishu_websocket_runtime
        self._workers: dict[int, _WorkerRecord] = {}
        self._lock = threading.RLock()

    def start(
        self,
        app: FeishuApp,
        app_secret: str,
        session_factory: Callable[[], Session],
        cipher: CredentialCipher,
    ) -> FeishuWorkerStatus:
        with self._lock:
            current = self._workers.get(app.id)
            if current and current.state == FeishuWorkerState.RUNNING:
                return FeishuWorkerStatus(app_id=app.id, state=current.state)

            context = FeishuWorkerContext(
                app=app,
                app_secret=app_secret,
                session_factory=session_factory,
                cipher=cipher,
            )
            runtime = self.runtime_factory(context)
            try:
                runtime.start()
            except Exception as exc:
                error = str(exc)
                self._workers[app.id] = _WorkerRecord(
                    runtime=runtime,
                    state=FeishuWorkerState.ERROR,
                    last_error=error,
                )
                raise FeishuWorkerStartError(error) from exc

            self._workers[app.id] = _WorkerRecord(
                runtime=runtime,
                state=FeishuWorkerState.RUNNING,
            )
            return FeishuWorkerStatus(app_id=app.id, state=FeishuWorkerState.RUNNING)

    def stop(self, app_id: int) -> FeishuWorkerStatus:
        with self._lock:
            record = self._workers.pop(app_id, None)
        if record is not None:
            record.runtime.stop()
        return FeishuWorkerStatus(app_id=app_id, state=FeishuWorkerState.STOPPED)

    def status(self, app_id: int) -> FeishuWorkerStatus:
        with self._lock:
            record = self._workers.get(app_id)
            if record is None:
                return FeishuWorkerStatus(app_id=app_id, state=FeishuWorkerState.STOPPED)
            return FeishuWorkerStatus(
                app_id=app_id,
                state=record.state,
                last_error=record.last_error,
            )

    def stop_all(self) -> None:
        with self._lock:
            records = list(self._workers.items())
            self._workers.clear()
        for _, record in records:
            record.runtime.stop()


class FeishuSdkWebSocketRuntime:
    def __init__(self, context: FeishuWorkerContext) -> None:
        self.context = context
        self._client: Any | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        lark = import_lark_sdk()
        handler = build_lark_event_handler(lark, self.context)
        client = create_lark_ws_client(
            lark,
            self.context.app.app_id,
            self.context.app_secret,
            handler,
        )
        self._client = client
        self._thread = threading.Thread(
            target=self._run_client,
            name=f"feishu-ws-{self.context.app.id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        client = self._client
        if client is None:
            return
        stop = getattr(client, "stop", None)
        if callable(stop):
            stop()

    def _run_client(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            client.start()
        except Exception:
            # The API status is updated by explicit start checks; runtime reconnect
            # policy is owned by the SDK for this first integration slice.
            return


def create_feishu_websocket_runtime(context: FeishuWorkerContext) -> FeishuWorkerRuntime:
    return FeishuSdkWebSocketRuntime(context)


def import_lark_sdk():
    try:
        import lark_oapi as lark  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Feishu WebSocket SDK is not installed. Install lark-oapi.") from exc
    return lark


def build_lark_event_handler(lark, context: FeishuWorkerContext):
    builder_factory = getattr(lark, "EventDispatcherHandler", None)
    if builder_factory is None:
        raise RuntimeError("lark-oapi EventDispatcherHandler is unavailable.")
    builder = builder_factory.builder("", "")
    register = getattr(builder, "register_p2_im_message_receive_v1", None)
    if not callable(register):
        raise RuntimeError("lark-oapi message receive registration is unavailable.")

    def handle_message(event) -> None:
        inbound = lark_event_to_inbound_message(context.app.id, event)
        with context.session_factory() as session:
            try:
                dispatch_feishu_inbound_message(session, inbound, context.cipher)
                session.commit()
            except Exception:
                session.rollback()
                raise

    builder = register(handle_message)
    card_register = getattr(builder, "register_p2_card_action_trigger", None)
    if callable(card_register):
        builder = card_register(lambda event: handle_card_action_event(context, event))
    return builder.build()


def handle_card_action_event(context: FeishuWorkerContext, event: Any) -> dict:
    action = lark_event_to_card_action(context.app.id, event)
    with context.session_factory() as session:
        try:
            result = handle_feishu_card_action(session, action)
            session.commit()
            return {"toast": {"type": "success", "content": result.reply_text or "操作完成"}}
        except Exception:
            session.rollback()
            raise


def create_lark_ws_client(lark, app_id: str, app_secret: str, event_handler):
    ws = getattr(lark, "ws", None)
    client_class = getattr(ws, "Client", None) if ws is not None else None
    if client_class is None:
        raise RuntimeError("lark-oapi WebSocket client is unavailable.")
    return client_class(app_id, app_secret, event_handler=event_handler)


def lark_event_to_inbound_message(feishu_app_id: int, event: Any) -> FeishuInboundMessage:
    message = get_nested(event, "event", "message")
    sender = get_nested(event, "event", "sender", "sender_id")
    raw_event = to_event_dict(event)
    message_id = str(get_value(message, "message_id") or "")
    chat_id = str(get_value(message, "chat_id") or "")
    sender_open_id = str(get_value(sender, "open_id") or "")
    message_type = str(get_value(message, "message_type") or "")
    content = get_value(message, "content")
    text = extract_text_content(content)
    if not message_id or not chat_id or not sender_open_id:
        raise RuntimeError("Feishu message event is incomplete.")
    return FeishuInboundMessage(
        feishu_app_id=feishu_app_id,
        message_id=message_id,
        chat_id=chat_id,
        sender_open_id=sender_open_id,
        message_type=message_type,
        text=text,
        raw_event=raw_event,
    )


def lark_event_to_card_action(feishu_app_id: int, event: Any) -> FeishuCardAction:
    raw_event = to_event_dict(event)
    operator = get_nested(event, "event", "operator")
    action = get_nested(event, "event", "action")
    action_value = get_value(action, "value")
    operator_open_id = str(get_value(operator, "open_id") or "")
    if not operator_open_id:
        raise RuntimeError("Feishu card action event does not contain operator open_id.")
    if not isinstance(action_value, dict):
        raise RuntimeError("Feishu card action event does not contain action value.")
    return FeishuCardAction(
        feishu_app_id=feishu_app_id,
        operator_open_id=operator_open_id,
        action_value=action_value,
        raw_event=raw_event,
    )


def extract_text_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, dict):
        return str(content.get("text") or "")
    if not isinstance(content, str):
        return str(content)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content
    if isinstance(parsed, dict):
        return str(parsed.get("text") or "")
    return content


def get_nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        current = get_value(current, key)
        if current is None:
            return None
    return current


def get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def to_event_dict(event: Any) -> dict:
    if isinstance(event, dict):
        return event
    if hasattr(event, "model_dump"):
        dumped = event.model_dump()
        return dumped if isinstance(dumped, dict) else {"event": dumped}
    if hasattr(event, "to_dict"):
        dumped = event.to_dict()
        return dumped if isinstance(dumped, dict) else {"event": dumped}
    return {"event": repr(event)}


feishu_worker_manager = FeishuWorkerManager()
