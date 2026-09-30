"""
Application configuration using Pydantic Settings.
Environment variables are loaded from .env file.
"""
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "KFMS - Knowledge Flow Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database - Primary (metadata storage)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kfms_meta"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # LLM Provider Configuration
    LLM_PROVIDER: str = "ollama"  # 'ollama' or 'groq'

    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_TIMEOUT: int = 120

    # Groq Configuration
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "mixtral-8x7b-32768"
    GROQ_TIMEOUT: int = 60

    # Excel Processing
    EXCEL_UPLOAD_MAX_SIZE_MB: int = 50
    EXCEL_TABLE_TTL_HOURS: int = 24
    # An expired upload is kept this much longer before the scheduler drops it,
    # so a table someone is still analysing does not vanish the moment it expires.
    EXCEL_CLEANUP_GRACE_HOURS: int = 24
    EXCEL_CLEANUP_INTERVAL_HOURS: int = 1

    # Query Execution
    QUERY_RESULT_LIMIT: int = 1000
    QUERY_TIMEOUT: int = 30

    # Security
    FERNET_KEY: str = ""  # Generated on first run if empty
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    def get_database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        return self.DATABASE_URL.replace("+asyncpg", "")


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency injection for settings."""
    return settings
