from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/ble_db"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@postgres:5432/ble_db"


settings = Settings()
