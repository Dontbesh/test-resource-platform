from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.sessions import read_session_user_id
from app.core.config import Settings, get_settings
from app.db.session import iter_session
from app.identity.models import User
from app.identity.service import get_user_by_id


def get_db(settings: Annotated[Settings, Depends(get_settings)]) -> Generator[Session]:
    yield from iter_session(settings.database_url)


def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise_not_authenticated()
    user_id = read_session_user_id(token, settings.session_secret_key)
    if user_id is None:
        raise_not_authenticated()
    user = get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise_not_authenticated()
    return user


def raise_not_authenticated() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error_code": "NOT_AUTHENTICATED", "message": "Authentication required."},
    )
