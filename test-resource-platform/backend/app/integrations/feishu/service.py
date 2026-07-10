import secrets
import string
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credentials.crypto import CredentialCipher, CredentialDecryptionError
from app.db.session import get_session_factory
from app.identity.models import User
from app.identity.service import get_user_by_username
from app.integrations.feishu.client import FeishuClientError, fetch_feishu_bot_info
from app.integrations.feishu.models import (
    FeishuApp,
    FeishuAppStatus,
    FeishuBindingCode,
    FeishuPlatformType,
    FeishuSetupSession,
    FeishuSetupStatus,
    FeishuUserBinding,
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
    FeishuUserBindingCreateRequest,
)
from app.integrations.feishu.worker import (
    FeishuWorkerManager,
    FeishuWorkerStartError,
    feishu_worker_manager,
)


class FeishuSetupError(Exception):
    pass


class FeishuSetupSessionNotFoundError(Exception):
    pass


class FeishuAppNotFoundError(Exception):
    pass


class FeishuConnectionCheckError(Exception):
    pass


class FeishuPlatformUserNotFoundError(Exception):
    pass


class FeishuBindingNotFoundError(Exception):
    pass


class FeishuWorkerError(Exception):
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
    expires_in = int(begin_response.get("expires_in") or begin_response.get("expire_in") or 600)
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


def create_feishu_binding_code(session: Session, user: User) -> FeishuBindingCode:
    for _ in range(5):
        code = generate_binding_code()
        existing = session.scalar(select(FeishuBindingCode).where(FeishuBindingCode.code == code))
        if existing is None:
            binding_code = FeishuBindingCode(code=code, platform_user_id=user.id)
            session.add(binding_code)
            session.flush()
            return binding_code
    raise FeishuSetupError("Failed to generate unique Feishu binding code.")


def check_feishu_app_connection(
    session: Session,
    app_id: int,
    cipher: CredentialCipher,
) -> FeishuApp:
    app = session.get(FeishuApp, app_id)
    if app is None:
        raise FeishuAppNotFoundError

    try:
        app_secret = cipher.decrypt(app.encrypted_app_secret) or ""
    except CredentialDecryptionError as exc:
        app.status = FeishuAppStatus.ERROR
        app.last_error = "Failed to decrypt Feishu app secret."
        session.flush()
        raise FeishuConnectionCheckError(app.last_error) from exc

    try:
        bot_info = fetch_feishu_bot_info(app.platform_type, app.app_id, app_secret)
    except (FeishuClientError, RuntimeError) as exc:
        app.status = FeishuAppStatus.ERROR
        app.last_error = str(exc)
        session.flush()
        raise FeishuConnectionCheckError(app.last_error) from exc

    app.bot_open_id = bot_info.open_id
    app.status = FeishuAppStatus.CONNECTED
    app.last_connected_at = datetime.now(UTC)
    app.last_error = None
    session.flush()
    return app


def start_feishu_app_worker(
    session: Session,
    app_id: int,
    cipher: CredentialCipher,
    database_url: str,
    manager: FeishuWorkerManager = feishu_worker_manager,
) -> FeishuApp:
    app = session.get(FeishuApp, app_id)
    if app is None:
        raise FeishuAppNotFoundError

    try:
        app_secret = cipher.decrypt(app.encrypted_app_secret) or ""
    except CredentialDecryptionError as exc:
        app.status = FeishuAppStatus.ERROR
        app.last_error = "Failed to decrypt Feishu app secret."
        session.flush()
        raise FeishuWorkerError(app.last_error) from exc

    try:
        manager.start(
            app=app,
            app_secret=app_secret,
            session_factory=get_session_factory(database_url),
            cipher=cipher,
        )
    except FeishuWorkerStartError as exc:
        app.status = FeishuAppStatus.ERROR
        app.last_error = str(exc)
        session.flush()
        raise FeishuWorkerError(app.last_error) from exc

    app.status = FeishuAppStatus.CONNECTED
    app.last_connected_at = datetime.now(UTC)
    app.last_error = None
    session.flush()
    return app


def stop_feishu_app_worker(
    session: Session,
    app_id: int,
    manager: FeishuWorkerManager = feishu_worker_manager,
) -> FeishuApp:
    app = session.get(FeishuApp, app_id)
    if app is None:
        raise FeishuAppNotFoundError

    manager.stop(app_id)
    app.status = FeishuAppStatus.DISCONNECTED
    app.last_error = None
    session.flush()
    return app


def list_feishu_user_bindings(session: Session, app_id: int) -> list[FeishuUserBinding]:
    app = session.get(FeishuApp, app_id)
    if app is None:
        raise FeishuAppNotFoundError
    return list(
        session.scalars(
            select(FeishuUserBinding)
            .where(FeishuUserBinding.feishu_app_id == app_id)
            .order_by(FeishuUserBinding.id)
        )
    )


def create_or_update_feishu_user_binding(
    session: Session,
    app_id: int,
    body: FeishuUserBindingCreateRequest,
) -> FeishuUserBinding:
    app = session.get(FeishuApp, app_id)
    if app is None:
        raise FeishuAppNotFoundError
    platform_user = get_user_by_username(session, body.platform_username)
    if platform_user is None or not platform_user.is_active:
        raise FeishuPlatformUserNotFoundError

    binding = session.scalar(
        select(FeishuUserBinding).where(
            FeishuUserBinding.feishu_app_id == app_id,
            FeishuUserBinding.open_id == body.open_id,
        )
    )
    if binding is None:
        binding = FeishuUserBinding(
            feishu_app_id=app_id,
            platform_user_id=platform_user.id,
            open_id=body.open_id,
            display_name=body.display_name,
        )
        session.add(binding)
    else:
        binding.platform_user_id = platform_user.id
        binding.display_name = body.display_name
    session.flush()
    return binding


def delete_feishu_user_binding(session: Session, binding_id: int) -> None:
    binding = session.get(FeishuUserBinding, binding_id)
    if binding is None:
        raise FeishuBindingNotFoundError
    session.delete(binding)
    session.flush()


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


def generate_binding_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "-".join(
        "".join(secrets.choice(alphabet) for _ in range(3))
        for _ in range(2)
    )
