"""Application configuration using Pydantic settings."""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"  # Claude 4.5 Haiku (latest)

    # Chroma Configuration
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    BM25_INDEX_PATH: str = "./bm25_index"
    COLLECTION_NAME: str = "agent_brain_collection"

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

    # Multi-instance Configuration
    AGENT_BRAIN_STATE_DIR: Optional[str] = None  # Override state directory
    AGENT_BRAIN_MODE: str = "project"  # "project" or "shared"

    # GraphRAG Configuration (Feature 113)
    ENABLE_GRAPH_INDEX: bool = False  # Master switch for graph indexing
    GRAPH_STORE_TYPE: str = "simple"  # "simple" (in-memory) or "kuzu" (persistent)
    GRAPH_INDEX_PATH: str = "./graph_index"  # Path for graph persistence
    GRAPH_EXTRACTION_MODEL: str = "claude-haiku-4-5"  # Model for entity extraction
    GRAPH_MAX_TRIPLETS_PER_CHUNK: int = 10  # Max triplets per document chunk
    GRAPH_USE_CODE_METADATA: bool = True  # Use AST metadata for code entities
    GRAPH_USE_LLM_EXTRACTION: bool = True  # Use LLM for additional extraction
    GRAPH_TRAVERSAL_DEPTH: int = 2  # Depth for graph traversal in queries
    GRAPH_RRF_K: int = 60  # Reciprocal Rank Fusion constant for multi-retrieval

    # Job Queue Configuration (Feature 115)
    AGENT_BRAIN_MAX_QUEUE: int = 100  # Max pending jobs in queue
    AGENT_BRAIN_JOB_TIMEOUT: int = 7200  # Job timeout in seconds (2 hours)
    AGENT_BRAIN_MAX_RETRIES: int = 3  # Max retries for failed jobs
    AGENT_BRAIN_CHECKPOINT_INTERVAL: int = 50  # Progress checkpoint every N files

    # Reranking Configuration (Feature 123)
    ENABLE_RERANKING: bool = False  # Off by default
    RERANKER_PROVIDER: str = "sentence-transformers"  # or "ollama"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_TOP_K_MULTIPLIER: int = 10  # Retrieve top_k * this for Stage 1
    RERANKER_MAX_CANDIDATES: int = 100  # Cap on Stage 1 candidates
    # Note: CrossEncoder.rank() handles batching internally, no batch_size config needed

    model_config = SettingsConfigDict(
        env_file=[
            ".env",  # Current directory
            Path(__file__).parent.parent.parent / ".env",  # Project root
            Path(__file__).parent.parent / ".env",  # agent-brain-server directory
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


def load_project_config(state_dir: Path) -> dict[str, Any]:
    """Load project configuration from state directory.

    Precedence: CLI flags > env vars > project config > defaults

    Args:
        state_dir: Path to the state directory containing config.json.

    Returns:
        Dictionary of configuration values from config.json, or empty dict.
    """
    config_path = state_dir / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load project config from {config_path}: {e}")
    return {}
