# You are writing the configuration module for a FastAPI retail analytics API.

# FILE: app/config.py
# PURPOSE: Pydantic-settings based configuration. All settings read from environment variables
# with defaults. Single Settings instance used throughout the app via dependency injection.

# TECH: Python 3.11, pydantic-settings==2.7.0, pydantic==2.10.3

# IMPLEMENT:

# 1. `class Settings(BaseSettings):`
#    - model_config = SettingsConfigDict(env_file=".env", extra="ignore")
#    - database_url: str = "postgresql+asyncpg://store_user:store_pass@localhost:5432/store_intelligence"
#    - database_url_sync: str = "postgresql+psycopg2://store_user:store_pass@localhost:5432/store_intelligence"
#    - redis_url: str = "redis://localhost:6379/0"
#    - log_level: str = "INFO"
#    - environment: str = "development"
#    - confidence_threshold: float = 0.35
#    - reid_similarity_threshold: float = 0.65
#    - dwell_threshold_seconds: int = 30
#    - pos_correlation_window_minutes: int = 5
#    - queue_spike_threshold: int = 5
#    - queue_critical_threshold: int = 10
#    - conversion_drop_threshold_pct: float = 20.0
#    - conversion_critical_drop_pct: float = 40.0
#    - dead_zone_minutes: int = 30
#    - stale_feed_minutes: int = 10
#    - max_ingest_batch_size: int = 500
#    - store_layout_path: str = "data/store_layout.json"
#    - store_mapping_path: str = "data/store_mapping.json"

# 2. `@lru_cache def get_settings() -> Settings:`
#    - Return Settings()

# 3. Module-level: `settings = get_settings()`

# IMPORTS NEEDED: pydantic_settings (BaseSettings, SettingsConfigDict), functools (lru_cache)

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://store_user:store_pass@localhost:5432/store_intelligence"
    database_url_sync: str = "postgresql+psycopg2://store_user:store_pass@localhost:5432/store_intelligence"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    environment: str = "development"
    confidence_threshold: float = 0.35
    reid_similarity_threshold: float = 0.65
    dwell_threshold_seconds: int = 30
    pos_correlation_window_minutes: int = 5
    queue_spike_threshold: int = 5
    queue_critical_threshold: int = 10
    conversion_drop_threshold_pct: float = 20.0
    conversion_critical_drop_pct: float = 40.0
    dead_zone_minutes: int = 30
    stale_feed_minutes: int = 10
    max_ingest_batch_size: int = 500
    store_layout_path: str = "data/store_layout.json"
    store_mapping_path: str = "data/store_mapping.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
