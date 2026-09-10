from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Bacchus CRM Engine"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "dev_secret_key_needs_replacement_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Provisioned Admin Account
    SUPERADMIN_EMAIL: str = "admin@bacchusspirits.com"
    SUPERADMIN_PASSWORD: str = "Admin@123"

    # Database Parameters (Postgres 16 on Docker Port 5433)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "niyaz2004"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "bacchus_crm_db"

    # Redis Parameters (Port 6379)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    @computed_field
    def ASYNC_DATABASE_URL(self) -> str:
        # If DATABASE_URL is provided in environment, sanitize it for asyncpg
        import os
        raw_url = os.getenv("DATABASE_URL")
        if raw_url:
            cleaned = raw_url
            if cleaned.startswith("postgresql://"):
                cleaned = cleaned.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif cleaned.startswith("postgres://"):
                cleaned = cleaned.replace("postgres://", "postgresql+asyncpg://", 1)
            cleaned = cleaned.replace("sslmode=require", "ssl=require")
            if "&channel_binding=" in cleaned:
                cleaned = cleaned.split("&channel_binding=")[0]
            return cleaned

        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()