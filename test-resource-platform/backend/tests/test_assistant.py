import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_path = tmp_path / "assistant.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTO_CREATE_SCHEMA", "true")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "Admin@123456")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200


def test_assistant_reports_missing_llm_configuration(client) -> None:
    login(client)

    response = client.post(
        "/api/v1/assistant/messages",
        json={"text": "有哪些空闲机器？"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error_code": "LLM_NOT_CONFIGURED",
        "message": "LLM assistant is not configured.",
    }


def test_assistant_executes_machine_search_tool_and_returns_final_answer(
    client, monkeypatch
) -> None:
    login(client)
    pool_response = client.post(
        "/api/v1/resource-pools",
        json={"name": "lab-a", "location": "room-1", "network_zone": "test"},
    )
    assert pool_response.status_code == 201
    machine_response = client.post(
        "/api/v1/machines",
        json={
            "resource_code": "server-x86-01",
            "name": "x86 test server",
            "resource_type": "PHYSICAL",
            "pool_id": pool_response.json()["id"],
            "architecture": "x86_64",
            "os_name": "openEuler",
            "tags": ["25g"],
        },
    )
    assert machine_response.status_code == 201
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "tool-model")
    get_settings.cache_clear()

    calls: list[tuple[list[dict], list[dict]]] = []

    class FakeLlmClient:
        def complete(self, messages: list[dict], tools: list[dict]) -> dict:
            calls.append(([dict(message) for message in messages], tools))
            if len(calls) == 1:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-search",
                            "type": "function",
                            "function": {
                                "name": "search_machines",
                                "arguments": (
                                    '{"architecture":"x86_64",'
                                    '"occupancy_status":"FREE"}'
                                ),
                            },
                        }
                    ],
                }
            return {
                "role": "assistant",
                "content": "找到 1 台空闲的 x86_64 机器：server-x86-01。",
            }

    monkeypatch.setattr(
        "app.api.v1.assistant.create_llm_client",
        lambda settings: FakeLlmClient(),
    )

    response = client.post(
        "/api/v1/assistant/messages",
        json={"text": "有没有空闲的 x86 机器？"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "找到 1 台空闲的 x86_64 机器：server-x86-01。"
    }
    assert len(calls) == 2
    assert calls[0][1][0]["function"]["name"] == "search_machines"
    tool_message = calls[1][0][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-search"
    assert "server-x86-01" in tool_message["content"]
    assert "password" not in tool_message["content"].lower()
