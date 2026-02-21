from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql+asyncpg://cloudcost:localdev@localhost:5432/cloudcost"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    FIRST_ADMIN_EMAIL: str = ""
    FIRST_ADMIN_PASSWORD: str = ""

    # -- Azure Cost Management -----------------------------------------
    AZURE_SUBSCRIPTION_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_SUBSCRIPTION_SCOPE: str = ""  # Computed: /subscriptions/{AZURE_SUBSCRIPTION_ID}
    MOCK_AZURE: bool = False  # Set True for local dev without real Azure credentials


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
