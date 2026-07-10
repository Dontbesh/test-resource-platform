from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.integrations.feishu.registration import (
    FeishuRegistrationError,
    registration_call,
)


def test_registration_call_returns_json_from_http_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout: int):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(b'{"error":"authorization_pending"}'),
        )

    monkeypatch.setattr("app.integrations.feishu.registration.urlopen", fake_urlopen)

    response = registration_call(
        "https://accounts.feishu.cn",
        "poll",
        {"device_code": "device-001"},
    )

    assert response == {"error": "authorization_pending"}


def test_registration_call_rejects_invalid_json_from_http_error(monkeypatch) -> None:
    def fake_urlopen(request, timeout: int):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(b"not-json"),
        )

    monkeypatch.setattr("app.integrations.feishu.registration.urlopen", fake_urlopen)

    with pytest.raises(FeishuRegistrationError):
        registration_call(
            "https://accounts.feishu.cn",
            "poll",
            {"device_code": "device-001"},
        )
