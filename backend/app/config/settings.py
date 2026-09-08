"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Enterprise AI Knowledge Assistant"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/enterprise_ai_assistant"

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Storage
    storage_backend: str = "local"
    local_storage_path: str = "./storage"
    max_upload_size_mb: int = 50

    # AWS S3
    aws_s3_bucket: str = ""
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # OCR
    tesseract_cmd: str = ""
    ocr_language: str = "eng"
    min_text_chars_for_ocr: int = 50

    # Allowed file types (extensions)
    allowed_extensions: str = "pdf,docx,pptx,txt,png,jpg,jpeg,tiff,bmp"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Embeddings
    default_embedding_provider: str = "fake"
    embedding_dimension: int = 384
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_api_key: str = ""
    gemini_embedding_model: str = "models/gemini-embedding-001"
    huggingface_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Vector store
    vector_store: str = "memory"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "enterprise_documents"
    chroma_persist_dir: str = "./chroma_db"
    pinecone_api_key: str = ""
    pinecone_index: str = ""
    pinecone_namespace: str = "default"
    search_top_k: int = 5

    # LLM / RAG (Phase 4)
    default_llm_provider: str = "fake"
    openai_llm_model: str = "gpt-4o-mini"
    gemini_llm_model: str = "gemini-2.5-flash"
    claude_llm_model: str = "claude-3-5-sonnet-latest"
    anthropic_api_key: str = ""
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    rag_top_k: int = 5
    # RAG retrieval pipeline: retrieve a wider candidate pool, then rerank it.
    vector_search_top_k: int = Field(default=15, ge=10, le=20)
    rerank_top_k: int = Field(default=5, ge=3, le=5)
    context_min_score: float = Field(default=0.05, ge=0.0, le=1.0)
    context_min_grounding_ratio: float = 0.35
    rag_history_turns: int = 6
    rag_min_similarity: float = 0.0


    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | List[str]) -> str:
        if isinstance(value, list):
            return ",".join(value)
        return value

    @field_validator(
        "gemini_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "qdrant_api_key",
        "pinecone_api_key",
        mode="before",
    )
    @classmethod
    def strip_secrets(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear cached settings (used in tests)."""
    get_settings.cache_clear()
