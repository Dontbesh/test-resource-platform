import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FEISHU_ACCOUNTS_BASE_URL = "https://accounts.feishu.cn"
LARK_ACCOUNTS_BASE_URL = "https://accounts.larksuite.com"


class FeishuRegistrationError(Exception):
    pass


def registration_call(
    base_url: str,
    action: str,
    params: dict[str, str] | None = None,
) -> dict:
    form = {"action": action}
    if params:
        form.update(params)
    data = urlencode(form).encode("utf-8")
    request = Request(
        f"{base_url}/oauth/v1/app/registration",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(1024 * 1024)
    except URLError as exc:
        raise FeishuRegistrationError(str(exc)) from exc
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise FeishuRegistrationError("Failed to decode Feishu registration response.") from exc
