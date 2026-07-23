from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.assistant.llm import create_llm_client
from app.assistant.schemas import AssistantMessageRequest, AssistantMessageResponse
from app.assistant.service import AssistantError, handle_assistant_message
from app.auth.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.identity.models import User

router = APIRouter(prefix="/assistant")


@router.post("/messages", response_model=AssistantMessageResponse)
def send_assistant_message(
    body: AssistantMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> AssistantMessageResponse:
    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "LLM_NOT_CONFIGURED",
                "message": "LLM assistant is not configured.",
            },
        )
    try:
        response_text = handle_assistant_message(
            session=session,
            user=current_user,
            text=body.text,
            client=create_llm_client(settings),
        )
        session.commit()
        return AssistantMessageResponse(text=response_text)
    except AssistantError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "LLM_ASSISTANT_FAILED",
                "message": str(exc),
            },
        ) from exc
