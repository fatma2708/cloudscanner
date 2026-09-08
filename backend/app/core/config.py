"""Application settings loaded from environment variables.

All settings are documented in the root ``.env.example``. Pydantic-settings
handles validation and typing so misconfiguration fails fast at startup.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for CloudPilot AI backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    app_name: str = "CloudPilot AI API"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # --- Database ---
    # Defaults to SQLite so the API runs with zero configuration for local
    # demos/tests. Set DATABASE_URL to PostgreSQL in production (see docker-compose).
    database_url: str = "sqlite:///./cloudpilot.db"

    # --- Auth ---
    jwt_secret: str = "dev-only-secret-change-me-before-production-32b"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    # --- Storage ---
    storage_root: str = "./storage"

    # --- LLM ---
    llm_provider: str = "huggingface"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # --- HuggingFace (Inference Providers / dedicated endpoint) ---
    hf_api_key: str = ""
    hf_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    hf_base_url: str = "https://router.huggingface.co/v1"

    # --- CRIM (advisory ML classification layer) ---
    # Path to the frozen, validated CRIM-v4.2 joblib artifact. Relative to the
    # backend working directory (the repository root), never user-controlled.
    crim_model_path: str = "models/crim_v4_2/cloudpilot_risk_intelligence_crim_v4_2.joblib"
    # Probabilistic threshold below which the ML layer abstains instead of
    # forcing a category. Matches the CRIM-v4.2 validation recommendation.
    crim_confidence_threshold: float = 0.70
    crim_model_name: str = "CRIM-v4.2"
    crim_model_version: str = "v4.2"

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, value: str) -> list[str]:
        """Split the comma separated CORS origins into a list."""
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool | str:
        """Accept conventional deployment labels used by hosting environments."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production"}:
                return False
            if normalized in {"development", "debug"}:
                return True
        return value

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_hf(self) -> bool:
        return bool(self.hf_api_key)

    @property
    def has_any_llm(self) -> bool:
        return self.has_openai or self.has_anthropic or self.has_gemini or self.has_hf


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
