import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.integrations.feishu.models import FeishuPlatformType

OPEN_FEISHU_BASE_URL = "https://open.feishu.cn"
OPEN_LARK_BASE_URL = "https://open.larksuite.com"


class FeishuClientError(Exception):
    pass


@dataclass(frozen=True)
class FeishuBotInfo:
    open_id: str
    app_name: str | None = None


def fetch_feishu_bot_info(
    platform_type: FeishuPlatformType,
    app_id: str,
    app_secret: str,
) -> FeishuBotInfo:
    base_url = open_base_url(platform_type)
    token = fetch_tenant_access_token(base_url, app_id, app_secret)
    response = call_json(
        "GET",
        f"{base_url}/open-apis/bot/v3/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    code = int(response.get("code") or 0)
    if code != 0:
        raise FeishuClientError(remote_error_message(response, "bot info"))
    bot = response.get("bot") or {}
    open_id = str(bot.get("open_id") or "")
    if not open_id:
        raise FeishuClientError("bot info response does not contain bot open_id.")
    app_name = bot.get("app_name")
    return FeishuBotInfo(open_id=open_id, app_name=str(app_name) if app_name else None)


def send_feishu_text_reply(
    platform_type: FeishuPlatformType,
    app_id: str,
    app_secret: str,
    message_id: str,
    text: str,
) -> None:
    base_url = open_base_url(platform_type)
    token = fetch_tenant_access_token(base_url, app_id, app_secret)
    response = call_json(
        "POST",
        f"{base_url}/open-apis/im/v1/messages/{message_id}/reply",
        headers={"Authorization": f"Bearer {token}"},
        body={
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )
    code = int(response.get("code") or 0)
    if code != 0:
        raise FeishuClientError(remote_error_message(response, "message reply"))


def send_feishu_card_reply(
    platform_type: FeishuPlatformType,
    app_id: str,
    app_secret: str,
    message_id: str,
    card: dict,
) -> None:
    base_url = open_base_url(platform_type)
    token = fetch_tenant_access_token(base_url, app_id, app_secret)
    response = call_json(
        "POST",
        f"{base_url}/open-apis/im/v1/messages/{message_id}/reply",
        headers={"Authorization": f"Bearer {token}"},
        body={
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
    )
    code = int(response.get("code") or 0)
    if code != 0:
        raise FeishuClientError(remote_error_message(response, "card reply"))


def fetch_tenant_access_token(base_url: str, app_id: str, app_secret: str) -> str:
    response = call_json(
        "POST",
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        body={"app_id": app_id, "app_secret": app_secret},
    )
    code = int(response.get("code") or 0)
    token = str(response.get("tenant_access_token") or "")
    if code != 0 or not token:
        raise FeishuClientError(remote_error_message(response, "tenant token"))
    return token


def call_json(
    method: str,
    url: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    data = None
    request_headers = headers.copy() if headers else {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read(1024 * 1024)
    except HTTPError as exc:
        response_body = exc.read(1024 * 1024)
        if not response_body:
            raise FeishuClientError(f"Feishu HTTP {exc.code}.") from exc
    except URLError as exc:
        raise FeishuClientError(str(exc)) from exc
    try:
        parsed = json.loads(response_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise FeishuClientError("Failed to decode Feishu response.") from exc
    if not isinstance(parsed, dict):
        raise FeishuClientError("Feishu response is not an object.")
    return parsed


def open_base_url(platform_type: FeishuPlatformType) -> str:
    if platform_type == FeishuPlatformType.LARK:
        return OPEN_LARK_BASE_URL
    return OPEN_FEISHU_BASE_URL


def remote_error_message(response: dict, action: str) -> str:
    code = response.get("code")
    message = response.get("msg") or response.get("message") or "unknown error"
    return f"{action} failed: code={code} msg={message}"
