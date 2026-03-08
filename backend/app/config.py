from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://satellite:satellite@localhost:5432/satellite_agent"
    anthropic_api_key: str = ""
    mapbox_token: str = ""
    imagery_cache_dir: str = "/app/data"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
