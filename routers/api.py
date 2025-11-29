from fastapi import APIRouter
from routers.endpoints.ble import router as ble_router

router = APIRouter()

router.include_router(ble_router)