from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.authorization import require_roles
from app.auth.dependencies import get_db
from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher, CredentialEncryptionKeyError
from app.identity.models import User, UserRole
from app.integrations.feishu.registration import FeishuRegistrationError
from app.integrations.feishu.schemas import (
    FeishuAppPublic,
    FeishuSetupBeginResponse,
    FeishuSetupPollRequest,
    FeishuSetupPollResponse,
    FeishuSetupSaveRequest,
)
from app.integrations.feishu.service import (
    FeishuAppNotFoundError,
    FeishuConnectionCheckError,
    FeishuSetupError,
    FeishuSetupSessionNotFoundError,
    begin_feishu_setup,
    check_feishu_app_connection,
    list_feishu_apps,
    poll_feishu_setup,
    save_feishu_app,
)

router = APIRouter(prefix="/integrations/feishu")
require_feishu_maintainer = require_roles(UserRole.ADMIN, UserRole.TSE)


@router.post(
    "/setup/begin",
    response_model=FeishuSetupBeginResponse,
    status_code=status.HTTP_201_CREATED,
)
def begin_setup(
    current_user: Annotated[User, Depends(require_feishu_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> FeishuSetupBeginResponse:
    try:
        response = begin_feishu_setup(session, current_user)
        session.commit()
        return response
    except (FeishuRegistrationError, FeishuSetupError) as exc:
        session.rollback()
        raise_feishu_setup_failed(str(exc))


@router.post("/setup/poll", response_model=FeishuSetupPollResponse)
def poll_setup(
    body: FeishuSetupPollRequest,
    _: Annotated[User, Depends(require_feishu_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> FeishuSetupPollResponse:
    try:
        response = poll_feishu_setup(session, body.device_code, body.base_url)
        session.commit()
        return response
    except FeishuSetupSessionNotFoundError:
        session.rollback()
        raise_setup_session_not_found()
    except FeishuRegistrationError as exc:
        session.rollback()
        raise_feishu_setup_failed(str(exc))


@router.post(
    "/setup/save",
    response_model=FeishuAppPublic,
    status_code=status.HTTP_201_CREATED,
)
def save_setup(
    body: FeishuSetupSaveRequest,
    current_user: Annotated[User, Depends(require_feishu_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> FeishuAppPublic:
    try:
        app = save_feishu_app(
            session=session,
            body=body,
            user=current_user,
            cipher=CredentialCipher(get_settings().credential_encryption_key),
        )
        session.commit()
        return app
    except CredentialEncryptionKeyError:
        session.rollback()
        raise_credential_key_not_configured()


@router.get("/apps", response_model=list[FeishuAppPublic])
def list_apps(
    _: Annotated[User, Depends(require_feishu_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> list:
    return list_feishu_apps(session)


@router.post("/apps/{app_id}/check-connection", response_model=FeishuAppPublic)
def check_app_connection(
    app_id: int,
    _: Annotated[User, Depends(require_feishu_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> FeishuAppPublic:
    try:
        app = check_feishu_app_connection(
            session=session,
            app_id=app_id,
            cipher=CredentialCipher(get_settings().credential_encryption_key),
        )
        session.commit()
        return app
    except FeishuAppNotFoundError:
        session.rollback()
        raise_feishu_app_not_found()
    except CredentialEncryptionKeyError:
        session.rollback()
        raise_credential_key_not_configured()
    except FeishuConnectionCheckError as exc:
        session.commit()
        raise_feishu_connection_check_failed(str(exc))


def raise_feishu_setup_failed(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"error_code": "FEISHU_SETUP_FAILED", "message": message},
    )


def raise_setup_session_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "FEISHU_SETUP_SESSION_NOT_FOUND",
            "message": "Feishu setup session not found.",
        },
    )


def raise_feishu_app_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "FEISHU_APP_NOT_FOUND",
            "message": "Feishu app not found.",
        },
    )


def raise_feishu_connection_check_failed(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "error_code": "FEISHU_CONNECTION_CHECK_FAILED",
            "message": message,
        },
    )


def raise_credential_key_not_configured() -> None:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "CREDENTIAL_ENCRYPTION_KEY_NOT_CONFIGURED",
            "message": "Credential encryption key is not configured.",
        },
    )
