import json

from app.integrations.feishu.client import send_feishu_text_reply
from app.integrations.feishu.models import FeishuPlatformType


class FakeHTTPResponse:
    def __init__(self, body: dict) -> None:
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def test_send_feishu_text_reply_posts_text_reply(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout: int):
        requests.append(request)
        if request.full_url.endswith("/open-apis/auth/v3/tenant_access_token/internal"):
            return FakeHTTPResponse({"code": 0, "tenant_access_token": "tenant-token"})
        return FakeHTTPResponse({"code": 0, "msg": "ok"})

    monkeypatch.setattr("app.integrations.feishu.client.urlopen", fake_urlopen)

    send_feishu_text_reply(
        FeishuPlatformType.FEISHU,
        "cli_test",
        "sec_test",
        "om_test",
        "hello",
    )

    token_request, reply_request = requests
    assert token_request.full_url == (
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    )
    assert json.loads(token_request.data.decode("utf-8")) == {
        "app_id": "cli_test",
        "app_secret": "sec_test",
    }
    assert reply_request.full_url == (
        "https://open.feishu.cn/open-apis/im/v1/messages/om_test/reply"
    )
    assert reply_request.headers["Authorization"] == "Bearer tenant-token"
    assert json.loads(reply_request.data.decode("utf-8")) == {
        "msg_type": "text",
        "content": json.dumps({"text": "hello"}, ensure_ascii=False),
    }
