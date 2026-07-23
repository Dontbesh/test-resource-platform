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


def handle_assistant_message(
    session: Session,
    user: User,
    text: str,
    client: LlmClient,
) -> str:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Current platform user: {user.username}; role: {user.role}.",
        },
        {"role": "user", "content": text},
    ]

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
                return content.strip()
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
            except (KeyError, TypeError, AssistantToolError) as exc:
                raise AssistantError(str(exc)) from exc
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result,
                }
            )

    raise AssistantError("LLM tool call limit exceeded.")
