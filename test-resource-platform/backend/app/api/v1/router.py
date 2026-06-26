from fastapi import APIRouter

from app.api.v1 import auth, health, resource_inventory, resource_leases, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(resource_inventory.router, tags=["resource-inventory"])
api_router.include_router(resource_leases.router, tags=["resource-leases"])
