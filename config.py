"""
Configuration management for Ripple.
All secrets and environment variables are loaded here.
"""
import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    falkordb_host: str = Field(default_factory=lambda: os.getenv("FALKORDB_HOST", "localhost"))
    falkordb_port: int = Field(default_factory=lambda: int(os.getenv("FALKORDB_PORT", "6380")))
    falkordb_username: str = Field(default_factory=lambda: os.getenv("FALKORDB_USERNAME", ""))
    falkordb_password: str = Field(default_factory=lambda: os.getenv("FALKORDB_PASSWORD", ""))
    llm_mode: str = Field(default_factory=lambda: os.getenv("LLM_MODE", "off").lower())
    llm_base_url: str = Field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_api_key: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    api_host: str = Field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    worker_concurrency: int = Field(default_factory=lambda: int(os.getenv("WORKER_CONCURRENCY", "4")))
    lease_duration_sec: int = Field(default_factory=lambda: int(os.getenv("LEASE_DURATION_SEC", "30")))
    reclaim_interval_sec: int = Field(default_factory=lambda: int(os.getenv("RECLAIM_INTERVAL_SEC", "5")))
    random_seed: int = Field(default_factory=lambda: int(os.getenv("RANDOM_SEED", "42")))
    public_mode: bool = Field(default_factory=lambda: os.getenv("PUBLIC_MODE", "0").lower() in ("1", "true", "yes"))
    cors_origins: list[str] = Field(default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()])
    trust_proxy: bool = Field(default_factory=lambda: os.getenv("TRUST_PROXY", "0").lower() in ("1", "true", "yes"))

settings = Settings()
