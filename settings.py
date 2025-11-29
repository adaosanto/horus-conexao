
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/ble_db"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@postgres:5432/ble_db"


settings = Settings()