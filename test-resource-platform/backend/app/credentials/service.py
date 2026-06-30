from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credentials.crypto import CredentialCipher
from app.credentials.models import CredentialAccessEvent, MachineCredential
from app.credentials.schemas import (
    MachineCredentialSecret,
    MachineCredentialSummary,
    MachineCredentialUpsertRequest,
)
from app.identity.models import User, UserRole
from app.leases.models import LeaseStatus, ResourceLease
from app.resources.models import MachineResource


class MachineNotFoundError(Exception):
    pass


class MachineCredentialNotFoundError(Exception):
    pass


class CredentialNotVisibleError(Exception):
    pass


def upsert_machine_credential(
    session: Session,
    resource_code: str,
    body: MachineCredentialUpsertRequest,
    cipher: CredentialCipher,
) -> MachineCredentialSummary:
    machine = get_machine_by_resource_code(session, resource_code)
    if machine is None:
        raise MachineNotFoundError

    credential = session.scalar(
        select(MachineCredential).where(MachineCredential.machine_id == machine.id)
    )
    if credential is None:
        credential = MachineCredential(machine_id=machine.id)
        session.add(credential)

    credential.ssh_username = body.ssh_username
    credential.encrypted_ssh_password = cipher.encrypt(body.ssh_password)
    credential.bmc_username = body.bmc_username
    credential.encrypted_bmc_password = cipher.encrypt(body.bmc_password)
    session.flush()
    return build_credential_summary(machine, credential)


def view_machine_credential(
    session: Session,
    resource_code: str,
    user: User,
    cipher: CredentialCipher,
) -> MachineCredentialSecret:
    machine = get_machine_by_resource_code(session, resource_code)
    if machine is None:
        raise MachineNotFoundError

    credential = session.scalar(
        select(MachineCredential).where(MachineCredential.machine_id == machine.id)
    )
    if credential is None:
        raise MachineCredentialNotFoundError

    if not can_view_credential(session, machine, user):
        raise CredentialNotVisibleError

    session.add(
        CredentialAccessEvent(
            machine_id=machine.id,
            user_id=user.id,
            access_type="VIEW",
        )
    )
    session.flush()

    return MachineCredentialSecret(
        resource_code=machine.resource_code,
        ssh_username=credential.ssh_username,
        ssh_password=cipher.decrypt(credential.encrypted_ssh_password),
        bmc_username=credential.bmc_username,
        bmc_password=cipher.decrypt(credential.encrypted_bmc_password),
    )


def can_view_credential(session: Session, machine: MachineResource, user: User) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if machine.is_critical:
        return False
    return has_active_lease(session, machine.id, user.id)


def get_machine_by_resource_code(session: Session, resource_code: str) -> MachineResource | None:
    return session.scalar(
        select(MachineResource).where(MachineResource.resource_code == resource_code)
    )


def has_active_lease(session: Session, machine_id: int, user_id: int) -> bool:
    now = datetime.now(UTC)
    lease = session.scalar(
        select(ResourceLease)
        .where(ResourceLease.machine_id == machine_id)
        .where(ResourceLease.user_id == user_id)
        .where(ResourceLease.status == LeaseStatus.ACTIVE)
        .where(ResourceLease.expires_at > now)
    )
    return lease is not None


def build_credential_summary(
    machine: MachineResource,
    credential: MachineCredential,
) -> MachineCredentialSummary:
    return MachineCredentialSummary(
        resource_code=machine.resource_code,
        ssh_username=credential.ssh_username,
        has_ssh_password=credential.encrypted_ssh_password is not None,
        bmc_username=credential.bmc_username,
        has_bmc_password=credential.encrypted_bmc_password is not None,
    )
