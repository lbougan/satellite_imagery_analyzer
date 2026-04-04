from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://satellite:satellite@localhost:5432/satellite_agent"
    anthropic_api_key: str = ""
    mapbox_token: str = ""
    imagery_cache_dir: str = "/app/data"
    gfw_api_key: str = ""

    # Area thresholds (km²)
    area_soft_limit_km2: float = 200.0
    area_hard_limit_km2: float = 2000.0

    # Scene comparison limit
    max_comparison_scenes: int = 2

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
