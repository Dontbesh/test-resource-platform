from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.authorization import require_roles
from app.auth.dependencies import get_current_user, get_db
from app.core.config import get_settings
from app.credentials.crypto import CredentialCipher, CredentialEncryptionKeyError
from app.credentials.schemas import (
    MachineCredentialSecret,
    MachineCredentialSummary,
    MachineCredentialUpsertRequest,
)
from app.credentials.service import (
    CredentialNotVisibleError,
    MachineCredentialNotFoundError,
    MachineNotFoundError,
    upsert_machine_credential,
    view_machine_credential,
)
from app.identity.models import User, UserRole

router = APIRouter()
require_credential_maintainer = require_roles(UserRole.ADMIN, UserRole.TSE)


@router.put(
    "/machines/{resource_code}/credentials",
    response_model=MachineCredentialSummary,
)
def configure_machine_credentials(
    resource_code: str,
    body: MachineCredentialUpsertRequest,
    _: Annotated[User, Depends(require_credential_maintainer)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineCredentialSummary:
    try:
        summary = upsert_machine_credential(
            session=session,
            resource_code=resource_code,
            body=body,
            cipher=get_credential_cipher(),
        )
        session.commit()
    except CredentialEncryptionKeyError:
        raise_credential_key_not_configured()
    except MachineNotFoundError:
        raise_machine_not_found()
    return summary


@router.get(
    "/machines/{resource_code}/credentials",
    response_model=MachineCredentialSecret,
)
def get_machine_credentials(
    resource_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> MachineCredentialSecret:
    try:
        secret = view_machine_credential(
            session=session,
            resource_code=resource_code,
            user=current_user,
            cipher=get_credential_cipher(),
        )
        session.commit()
    except CredentialEncryptionKeyError:
        raise_credential_key_not_configured()
    except MachineNotFoundError:
        raise_machine_not_found()
    except MachineCredentialNotFoundError:
        raise_credential_not_found()
    except CredentialNotVisibleError:
        raise_credential_not_visible()
    return secret


def get_credential_cipher() -> CredentialCipher:
    return CredentialCipher(get_settings().credential_encryption_key)


def raise_machine_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "MACHINE_NOT_FOUND", "message": "Machine not found."},
    )


def raise_credential_not_found() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error_code": "MACHINE_CREDENTIAL_NOT_FOUND",
            "message": "Machine credential not found.",
        },
    )


def raise_credential_not_visible() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error_code": "CREDENTIAL_NOT_VISIBLE",
            "message": "Credential is not visible to current user.",
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
