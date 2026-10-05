from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent AI Agent Platform"
    app_version: str = "0.1.0"

    # LLM configuration
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"

    # Database configuration
    database_url: str = (
        "postgresql+psycopg://ai_agent:ai_agent@localhost:5432/ai_agent"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
