import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FEISHU_ACCOUNTS_BASE_URL = "https://accounts.feishu.cn"
LARK_ACCOUNTS_BASE_URL = "https://accounts.larksuite.com"


class FeishuRegistrationError(Exception):
    pass


def _decode_registration_body(body: bytes) -> dict:
    try:
        decoded = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise FeishuRegistrationError(
            "Failed to decode Feishu registration response."
        ) from exc
    if not isinstance(decoded, dict):
        raise FeishuRegistrationError("Feishu registration response is not an object.")
    return decoded


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
    except HTTPError as exc:
        body = exc.read(1024 * 1024)
        if not body:
            raise FeishuRegistrationError(f"Feishu registration HTTP {exc.code}.") from exc
        return _decode_registration_body(body)
    except URLError as exc:
        raise FeishuRegistrationError(str(exc)) from exc
    return _decode_registration_body(body)
