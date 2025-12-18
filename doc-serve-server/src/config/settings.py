"""Application configuration using Pydantic settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    DEBUG: bool = False

    # OpenAI Configuration
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS: int = 3072

    # Anthropic Configuration
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-5-haiku-20241022"

    # Chroma Configuration
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    COLLECTION_NAME: str = "doc_serve_collection"

    # Chunking Configuration
    DEFAULT_CHUNK_SIZE: int = 512
    DEFAULT_CHUNK_OVERLAP: int = 50
    MAX_CHUNK_SIZE: int = 2048
    MIN_CHUNK_SIZE: int = 128

    # Query Configuration
    DEFAULT_TOP_K: int = 5
    MAX_TOP_K: int = 50
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.7

    # Rate Limiting
    EMBEDDING_BATCH_SIZE: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
