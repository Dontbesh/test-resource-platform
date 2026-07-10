from sqlalchemy.orm import Session

from app.leases.service import list_active_machine_occupancy
from app.resources.models import MachineResource, ResourceAdminStatus, ResourcePool
from app.resources.service import list_machine_resources


def build_free_machines_card(session: Session) -> dict:
    machines = list_free_machines(session)
    elements: list[dict] = []
    if not machines:
        elements.append({"tag": "markdown", "content": "暂无空闲机器。"})
    for machine in machines[:10]:
        elements.append(
            {
                "tag": "markdown",
                "content": (
                    f"**{machine.resource_code}**\n"
                    f"{machine.name} · {machine.resource_type}"
                ),
            }
        )
        elements.append(
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "申请 60 分钟"},
                        "type": "primary",
                        "value": {
                            "action": "lease",
                            "resource_code": machine.resource_code,
                            "duration_minutes": 60,
                            "purpose": "feishu-card",
                        },
                    }
                ],
            }
        )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "空闲机器"},
        },
        "elements": elements,
    }


def list_free_machines(session: Session) -> list[MachineResource]:
    occupancy = list_active_machine_occupancy(session)
    machines = []
    for machine in list_machine_resources(session):
        pool = session.get(ResourcePool, machine.pool_id)
        if (
            pool is not None
            and pool.is_active
            and machine.admin_status == ResourceAdminStatus.ACTIVE
            and machine.id not in occupancy
        ):
            machines.append(machine)
    return machines
