from fastapi import APIRouter

from routers.endpoints.ble import router as ble_router
from routers.endpoints.gateway import router as gateway_router
from routers.endpoints.map import router as map_router

router = APIRouter()

router.include_router(ble_router)
router.include_router(gateway_router, prefix="/gateway")
router.include_router(map_router, prefix="/map", tags=["map"])
