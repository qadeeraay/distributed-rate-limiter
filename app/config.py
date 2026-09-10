from pydantic_settings import BaseSettings
from typing import Optional, Dict


class RateLimitTier(BaseSettings):
    rate: int      # Allowed requests
    window: int    # Window size in seconds


class Settings(BaseSettings):
    APP_NAME: str = "Distributed Rate Limiter Gateway"
    PORT: int = 8002
    DEBUG: bool = False

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1
    REDIS_PASSWORD: Optional[str] = None

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Default Algorithm: "sliding_window" or "token_bucket"
    DEFAULT_ALGORITHM: str = "sliding_window"

    # Circuit Breaker / Fail-Open Resilience
    CIRCUIT_BREAKER_FAIL_OPEN: bool = True
    REDIS_TIMEOUT_SECONDS: float = 0.05  # 50ms timeout to avoid gateway latency spike

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
