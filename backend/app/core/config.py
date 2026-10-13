from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent AI Agent Platform"
    app_version: str = "0.1.0"

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    database_url: str = (
        "postgresql+psycopg://ai_agent:ai_agent@localhost:5432/ai_agent"
    )

    # Required: no insecure fallback secret.
    jwt_secret_key: str

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if value == "CHANGE_THIS_SECRET_KEY":
            raise ValueError("The default JWT secret is not allowed.")
        if len(value) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must contain at least 32 characters."
            )
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
