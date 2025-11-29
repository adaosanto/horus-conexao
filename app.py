from fastapi import FastAPI
from routers.api import router
from settings import settings

app = FastAPI(
    title="BLE API",
    description="API para gerenciamento de tags BLE",
    version="1.0.0"
)

app.include_router(router)