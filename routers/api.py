from fastapi import APIRouter

from routers.endpoints.ble import router as ble_router
from routers.endpoints.gateway import router as gateway_router

router = APIRouter()

router.include_router(ble_router)
router.include_router(gateway_router, prefix="/gateway")
