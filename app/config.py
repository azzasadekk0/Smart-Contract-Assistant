from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = Field(default="openai")
    openai_api_key: str | None = Field(default=None)
    openai_chat_model: str = Field(default="gpt-4o-mini")
    hf_model_name: str = Field(default="google/flan-t5-base")

    embedding_provider: str = Field(default="openai")
    embedding_model_name: str = Field(default="text-embedding-3-small")

    vector_backend: str = Field(default="chroma")
    vector_store_dir: str = Field(default="data/vectorstore")

    chunk_size: int = Field(default=900)
    chunk_overlap: int = Field(default=120)
    top_k: int = Field(default=4)
    citation_top_n: int = Field(default=3)

    guardrail_min_relevance: float = Field(default=0.2)
    max_query_chars: int = Field(default=2000)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()