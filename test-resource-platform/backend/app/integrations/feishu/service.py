from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credentials.crypto import CredentialCipher
from app.identity.models import User
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuAppStatus,
    FeishuPlatformType,
    FeishuSetupSession,
    FeishuSetupStatus,
)
from app.integrations.feishu.registration import (
    FEISHU_ACCOUNTS_BASE_URL,
    LARK_ACCOUNTS_BASE_URL,
    registration_call,
)
from app.integrations.feishu.schemas import (
    FeishuSetupBeginResponse,
    FeishuSetupPollResponse,
    FeishuSetupSaveRequest,
)


class FeishuSetupError(Exception):
    pass


class FeishuSetupSessionNotFoundError(Exception):
    pass


def begin_feishu_setup(session: Session, user: User) -> FeishuSetupBeginResponse:
    init_response = registration_call(FEISHU_ACCOUNTS_BASE_URL, "init", None)
    raise_if_remote_error(init_response, "feishu init")

    supported_methods = init_response.get("supported_auth_methods") or []
    if supported_methods and "client_secret" not in supported_methods:
        raise FeishuSetupError("Feishu registration does not support client_secret auth.")

    begin_response = registration_call(
        FEISHU_ACCOUNTS_BASE_URL,
        "begin",
        {
            "archetype": "PersonalAgent",
            "auth_method": "client_secret",
            "request_user_info": "open_id",
        },
    )
    raise_if_remote_error(begin_response, "feishu begin")

    device_code = str(begin_response.get("device_code") or "")
    qr_url = str(begin_response.get("verification_uri_complete") or "")
    interval = int(begin_response.get("interval") or 5)
    expires_in = int(begin_response.get("expire_in") or 600)
    if not device_code or not qr_url:
        raise FeishuSetupError("Feishu begin response is incomplete.")

    expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
    setup = FeishuSetupSession(
        device_code=device_code,
        qr_url=qr_url,
        base_url=FEISHU_ACCOUNTS_BASE_URL,
        status=FeishuSetupStatus.PENDING,
        interval_seconds=interval,
        expires_at=expires_at,
        created_by_user_id=user.id,
    )
    session.add(setup)
    session.flush()

    return FeishuSetupBeginResponse(
        id=setup.id,
        device_code=device_code,
        qr_url=qr_url,
        interval=interval,
        expires_in=expires_in,
        expires_at=expires_at,
    )


def poll_feishu_setup(
    session: Session,
    device_code: str,
    base_url: str | None = None,
) -> FeishuSetupPollResponse:
    setup = session.scalar(
        select(FeishuSetupSession).where(FeishuSetupSession.device_code == device_code)
    )
    if setup is None:
        raise FeishuSetupSessionNotFoundError

    effective_base_url = base_url or setup.base_url or FEISHU_ACCOUNTS_BASE_URL
    poll_response = registration_call(
        effective_base_url,
        "poll",
        {"device_code": setup.device_code},
    )

    user_info = poll_response.get("user_info") or {}
    tenant_brand = str(user_info.get("tenant_brand") or "").lower()
    if tenant_brand == "lark" and effective_base_url != LARK_ACCOUNTS_BASE_URL:
        setup.base_url = LARK_ACCOUNTS_BASE_URL
        session.flush()
        return FeishuSetupPollResponse(
            status=FeishuSetupStatus.PENDING,
            base_url=LARK_ACCOUNTS_BASE_URL,
        )

    result = FeishuSetupPollResponse(
        status=FeishuSetupStatus.PENDING,
        base_url=effective_base_url,
    )
    client_id = str(poll_response.get("client_id") or "")
    client_secret = str(poll_response.get("client_secret") or "")
    if client_id and client_secret:
        platform = FeishuPlatformType.LARK if tenant_brand == "lark" else FeishuPlatformType.FEISHU
        setup.status = FeishuSetupStatus.COMPLETED
        setup.base_url = effective_base_url
        session.flush()
        return FeishuSetupPollResponse(
            status=FeishuSetupStatus.COMPLETED,
            base_url=effective_base_url,
            app_id=client_id,
            app_secret=client_secret,
            platform=platform,
            owner_open_id=user_info.get("open_id"),
        )

    error_code = str(poll_response.get("error") or "")
    if error_code in {"", "authorization_pending"}:
        return result
    if error_code == "slow_down":
        result.slow_down = True
        return result
    if error_code == "access_denied":
        setup.status = FeishuSetupStatus.DENIED
        session.flush()
        result.status = FeishuSetupStatus.DENIED
        return result
    if error_code == "expired_token":
        setup.status = FeishuSetupStatus.EXPIRED
        session.flush()
        result.status = FeishuSetupStatus.EXPIRED
        return result

    error_description = str(poll_response.get("error_description") or "")
    setup.status = FeishuSetupStatus.ERROR
    setup.error = f"{error_code}: {error_description}".strip(": ")
    session.flush()
    result.status = FeishuSetupStatus.ERROR
    result.error = setup.error
    return result


def save_feishu_app(
    session: Session,
    body: FeishuSetupSaveRequest,
    user: User,
    cipher: CredentialCipher,
) -> FeishuApp:
    app = session.scalar(select(FeishuApp).where(FeishuApp.app_id == body.app_id))
    if app is None:
        app = FeishuApp(
            name=body.name or default_app_name(body.platform_type),
            platform_type=body.platform_type,
            app_id=body.app_id,
            encrypted_app_secret=cipher.encrypt(body.app_secret) or "",
            owner_open_id=body.owner_open_id,
            tenant_brand=body.tenant_brand,
            status=FeishuAppStatus.CONFIGURED,
            created_by_user_id=user.id,
        )
        session.add(app)
    else:
        app.name = body.name or app.name
        app.platform_type = body.platform_type
        app.encrypted_app_secret = cipher.encrypt(body.app_secret) or ""
        app.owner_open_id = body.owner_open_id
        app.tenant_brand = body.tenant_brand
        app.status = FeishuAppStatus.CONFIGURED
        app.last_error = None
    session.flush()
    return app


def list_feishu_apps(session: Session) -> list[FeishuApp]:
    return list(session.scalars(select(FeishuApp).order_by(FeishuApp.id)))


def raise_if_remote_error(response: dict, action: str) -> None:
    error = response.get("error")
    if not error:
        return
    description = response.get("error_description") or ""
    raise FeishuSetupError(f"{action}: {error}: {description}")


def default_app_name(platform_type: FeishuPlatformType) -> str:
    if platform_type == FeishuPlatformType.FEISHU:
        return "Feishu Resource Assistant"
    return "Lark Resource Assistant"
