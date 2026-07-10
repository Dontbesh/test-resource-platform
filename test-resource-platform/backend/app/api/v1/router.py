from fastapi import APIRouter

from app.api.v1 import (
    auth,
    connectivity_checks,
    feishu_integration,
    health,
    machine_credentials,
    resource_inventory,
    resource_leases,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(resource_inventory.router, tags=["resource-inventory"])
api_router.include_router(resource_leases.router, tags=["resource-leases"])
api_router.include_router(machine_credentials.router, tags=["machine-credentials"])
api_router.include_router(connectivity_checks.router, tags=["connectivity-checks"])
api_router.include_router(feishu_integration.router, tags=["feishu-integration"])
