import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.assistant.llm import LlmClient, LlmClientError
from app.assistant.tools import ASSISTANT_TOOLS, AssistantToolError, execute_assistant_tool
from app.identity.models import User

SYSTEM_PROMPT = """You are the test resource platform assistant.
Use only the supplied tools for platform data. Never invent machine data, credentials,
permissions, or operation results. This tracer supports read-only machine search only.
Reply in the user's language and keep the answer concise."""


class AssistantError(Exception):
    pass


@dataclass(frozen=True)
class AssistantToolResult:
    name: str
    data: dict


@dataclass(frozen=True)
class AssistantMessageResult:
    text: str
    tool_results: tuple[AssistantToolResult, ...] = field(default_factory=tuple)


def run_assistant_message(
    session: Session,
    user: User,
    text: str,
    client: LlmClient,
) -> AssistantMessageResult:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Current platform user: {user.username}; role: {user.role}.",
        },
        {"role": "user", "content": text},
    ]

    tool_results: list[AssistantToolResult] = []
    for _ in range(3):
        try:
            assistant_message = client.complete(messages, ASSISTANT_TOOLS)
        except LlmClientError as exc:
            raise AssistantError(str(exc)) from exc
        messages.append(assistant_message)
        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            content = assistant_message.get("content")
            if isinstance(content, str) and content.strip():
                return AssistantMessageResult(
                    text=content.strip(),
                    tool_results=tuple(tool_results),
                )
            raise AssistantError("LLM returned an empty assistant response.")

        for tool_call in tool_calls:
            try:
                function = tool_call["function"]
                result = execute_assistant_tool(
                    session=session,
                    name=str(function["name"]),
                    arguments_json=str(function.get("arguments") or "{}"),
                )
                tool_call_id = str(tool_call["id"])
                parsed_result = json.loads(result)
            except (KeyError, TypeError, AssistantToolError) as exc:
                raise AssistantError(str(exc)) from exc
            except json.JSONDecodeError as exc:
                raise AssistantError("Assistant tool returned invalid JSON.") from exc
            tool_results.append(
                AssistantToolResult(name=str(function["name"]), data=parsed_result)
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result,
                }
            )

    raise AssistantError("LLM tool call limit exceeded.")


def handle_assistant_message(
    session: Session,
    user: User,
    text: str,
    client: LlmClient,
) -> str:
    return run_assistant_message(session, user, text, client).text
