from sqlalchemy.orm import Session

from app.identity.models import User
from app.leases.models import LeaseStatus
from app.leases.service import list_active_machine_occupancy, list_user_leases
from app.resources.models import MachineResource, ResourceAdminStatus, ResourcePool
from app.resources.service import list_machine_resources


def build_home_card(user: User | None) -> dict:
    binding = f"{user.username} · {user.role}" if user is not None else "尚未绑定平台用户"
    return card(
        "测试资源平台",
        [
            markdown(f"**当前身份：** {binding}\n请选择要进行的操作。"),
            actions(
                button("空闲机器", "show_free_machines", primary=True),
                button("我的租约", "show_my_leases"),
            ),
        ],
        template="blue",
    )


def build_machines_card(
    session: Session,
    *,
    only_free: bool = False,
    resource_codes: set[str] | None = None,
    title: str | None = None,
) -> dict:
    occupancy = list_active_machine_occupancy(session)
    elements: list[dict] = []
    machines = list_machine_resources(session)
    visible_count = 0

    for machine in machines:
        if resource_codes is not None and machine.resource_code not in resource_codes:
            continue
        pool = session.get(ResourcePool, machine.pool_id)
        is_available = machine_is_available(machine, pool, occupancy)
        if only_free and not is_available:
            continue
        visible_count += 1
        status = machine_status(machine, pool, occupancy)
        details = [
            f"**{machine.resource_code} · {machine.name}**",
            f"类型：{machine.resource_type}　状态：{status}",
        ]
        if machine.architecture or machine.os_name:
            details.append(
                f"架构：{machine.architecture or '-'}　系统：{machine.os_name or '-'}"
            )
        elements.append(markdown("\n".join(details)))
        if is_available:
            elements.append(
                actions(
                    button(
                        "占用 60 分钟",
                        "confirm_lease",
                        primary=True,
                        resource_code=machine.resource_code,
                        duration_minutes=60,
                        purpose="feishu-card",
                    )
                )
            )
        if visible_count >= 10:
            break

    if not elements:
        elements.append(markdown("暂无空闲机器。" if only_free else "暂无机器资源。"))
    return card(title or ("空闲机器" if only_free else "机器列表"), elements, template="blue")


def build_free_machines_card(session: Session) -> dict:
    return build_machines_card(session, only_free=True)


def build_my_leases_card(session: Session, user: User) -> dict:
    elements: list[dict] = []
    leases = list_user_leases(session, user)
    for lease in leases[:10]:
        elements.append(
            markdown(
                "\n".join(
                    [
                        f"**{lease.machine.resource_code} · {lease.machine.name}**",
                        f"租约：{lease.lease_id}",
                        f"状态：{lease.status}　到期：{lease.expires_at}",
                        f"用途：{lease.purpose}",
                    ]
                )
            )
        )
        if lease.status == LeaseStatus.ACTIVE:
            elements.append(
                actions(
                    button(
                        "延期 60 分钟",
                        "confirm_extend",
                        lease_id=lease.lease_id,
                        duration_minutes=60,
                    ),
                    button(
                        "释放",
                        "confirm_release",
                        danger=True,
                        lease_id=lease.lease_id,
                    ),
                )
            )
    if not elements:
        elements.append(markdown("你当前没有租约。"))
    return card("我的租约", elements, template="green")


def build_confirmation_card(
    *,
    action: str,
    title: str,
    content: str,
    confirm_label: str,
    danger: bool = False,
    **values: object,
) -> dict:
    return card(
        title,
        [
            markdown(content),
            actions(
                button(
                    confirm_label,
                    action,
                    primary=not danger,
                    danger=danger,
                    **values,
                ),
                button("取消", "cancel"),
            ),
        ],
        template="red" if danger else "orange",
    )


def build_operation_result_card(title: str, content: str, *, success: bool) -> dict:
    return card(
        title,
        [
            markdown(content),
            actions(
                button("我的租约", "show_my_leases", primary=True),
                button("空闲机器", "show_free_machines"),
            ),
        ],
        template="green" if success else "red",
    )


def machine_is_available(
    machine: MachineResource,
    pool: ResourcePool | None,
    occupancy: dict[int, tuple[str, str]],
) -> bool:
    return (
        pool is not None
        and pool.is_active
        and machine.admin_status == ResourceAdminStatus.ACTIVE
        and machine.id not in occupancy
    )


def machine_status(
    machine: MachineResource,
    pool: ResourcePool | None,
    occupancy: dict[int, tuple[str, str]],
) -> str:
    if machine.id in occupancy:
        username, _ = occupancy[machine.id]
        return f"已占用（{username}）"
    if pool is None or not pool.is_active:
        return "资源池已停用"
    if machine.admin_status != ResourceAdminStatus.ACTIVE:
        return f"不可用（{machine.admin_status}）"
    return "空闲"


def card(title: str, elements: list[dict], *, template: str) -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": elements,
    }


def markdown(content: str) -> dict:
    return {"tag": "markdown", "content": content}


def actions(*items: dict) -> dict:
    return {"tag": "action", "actions": list(items)}


def button(
    label: str,
    action: str,
    *,
    primary: bool = False,
    danger: bool = False,
    **values: object,
) -> dict:
    value = {"action": action, **values}
    result = {
        "tag": "button",
        "text": {"tag": "plain_text", "content": label},
        "value": value,
    }
    if danger:
        result["type"] = "danger"
    elif primary:
        result["type"] = "primary"
    return result
