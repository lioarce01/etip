from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://etip:etip@localhost:5432/etip"
    database_url_sync: str = "postgresql+psycopg2://etip:etip@localhost:5432/etip"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "etip_skills"

    # Connector secret encryption (Fernet key — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    connector_encryption_key: str = "kmydWb4KHWgKTGIXSI3wJ-URjbuYKnSiZlCOY4SUmhE="

    # Auth
    jwt_secret: str = "change-me-to-a-32-byte-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # LLM — via LiteLLM (supports OpenAI, Anthropic, Groq, Ollama, etc.)
    # Set the model string to match your provider, e.g.:
    #   "gpt-4o-mini"                    → OpenAI (needs OPENAI_API_KEY)
    #   "claude-haiku-4-5-20251001"      → Anthropic (needs ANTHROPIC_API_KEY)
    #   "groq/llama-3.1-8b-instant"      → Groq (needs GROQ_API_KEY, free tier available)
    #   "ollama/llama3.2"                → Local Ollama (no key needed)
    llm_model: str = "groq/llama-3.3-70b-versatile"  # good free default via Groq
    openai_api_key: str = ""       # for OpenAI / Azure OpenAI
    anthropic_api_key: str = ""    # for Anthropic Claude
    groq_api_key: str = ""         # for Groq (free tier, fast)

    # Embeddings — local OSS via fastembed (no API key, runs on CPU)
    # Options: "BAAI/bge-small-en-v1.5" (fast) | "nomic-ai/nomic-embed-text-v1.5" (quality)
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # ESCO
    esco_api_url: str = "https://ec.europa.eu/esco/api"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
