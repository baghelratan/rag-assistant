"""
Application configuration using pydantic-settings.
All settings can be overridden via environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # LLM API Keys
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")

    # Storage paths
    CHROMA_PERSIST_DIR: str = Field(default="./data/chroma", description="ChromaDB persistence directory")
    BM25_INDEX_DIR: str = Field(default="./data/bm25", description="BM25 index storage directory")
    SESSION_DB_PATH: str = Field(default="./data/sessions.db", description="SQLite session database path")
    CACHE_DIR: str = Field(default="./data/cache", description="Disk cache directory")

    # Model configuration
    EMBED_MODEL: str = Field(default="all-MiniLM-L6-v2", description="Sentence transformer embedding model")
    RERANKER_MODEL: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Cross-encoder reranker model"
    )

    # Chunking settings
    CHUNK_SIZE: int = Field(default=512, description="Maximum characters per chunk")
    CHUNK_OVERLAP: int = Field(default=64, description="Overlap between consecutive chunks")

    # Retrieval settings
    TOP_K_RETRIEVAL: int = Field(default=20, description="Number of candidates retrieved before reranking")
    TOP_K_RERANK: int = Field(default=5, description="Number of results after reranking")
    MAX_QUERY_LENGTH: int = Field(default=2000, description="Maximum allowed query length in characters")

    # Rate limiting
    RATE_LIMIT: str = Field(default="60/minute", description="Rate limit string for slowapi")

    # LLM settings
    PRIMARY_LLM: str = Field(default="gemini", description="Primary LLM provider: 'gemini' or 'openai'")
    GEMINI_MODEL: str = Field(default="gemini-1.5-flash", description="Gemini model name")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Quality thresholds
    HALLUCINATION_THRESHOLD: float = Field(
        default=0.6,
        description="Score below which a response is flagged as potential hallucination"
    )

    # Server settings
    CORS_ORIGINS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Application metadata
    APP_NAME: str = Field(default="RAG Assistant API", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        dirs = [
            self.CHROMA_PERSIST_DIR,
            self.BM25_INDEX_DIR,
            self.CACHE_DIR,
            os.path.dirname(self.SESSION_DB_PATH) if os.path.dirname(self.SESSION_DB_PATH) else ".",
        ]
        for d in dirs:
            if d:
                os.makedirs(d, exist_ok=True)


settings = Settings()
