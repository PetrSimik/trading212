from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- API ---
    t212_api_key: str = Field(..., description="Trading212 API key")
    api_base_url: str = "https://live.trading212.com/api/v0"

    # --- Safety ---
    paper_mode: bool = Field(True, description="When True, no real orders are sent")
    trading_enabled: bool = Field(True, description="Master kill-switch for all order placement")
    max_order_value: float = Field(100.0, description="Hard cap per single order in account currency")

    # --- Storage ---
    db_path: str = Field("/data/trades.db", description="Path to SQLite trade log")

    # --- Logging ---
    log_level: str = "INFO"

    @field_validator("max_order_value")
    @classmethod
    def max_order_value_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("max_order_value must be positive")
        return v

    @field_validator("log_level")
    @classmethod
    def log_level_must_be_valid(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance. Call once; reuse everywhere."""
    return Settings()  # type: ignore[call-arg]
