from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Cache TTLs (seconds)
    cache_redirect_ttl: int = 3600  # 1 hour
    cache_stats_ttl: int = 300  # 5 minutes
    cache_user_links_ttl: int = 600  # 10 minutes

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: float = 30.0
    refresh_token_expiration_days: int = 7
    base_url: str = "http://localhost:8000"
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ]
    cookie_secure: bool = True
    log_level: str = "INFO"
    max_request_size: int = 10 * 1024  # 10 KB

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
