# Core Configuration
# Production-grade settings management

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    url: str = Field(default="postgresql://postgres:postgres@localhost:5432/ai_school")
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

    class Config:
        env_prefix = "AI_SCHOOL_DB_"


class RedisSettings(BaseSettings):
    """Redis configuration (for caching and Celery)"""
    url: str = Field(default="redis://localhost:6379/0")

    class Config:
        env_prefix = "AI_SCHOOL_REDIS_"


class MiniMaxSettings(BaseSettings):
    """MiniMax LLM configuration"""
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.minimax.chat")
    model: str = Field(default="MiniMax-2.7-highspeed")
    timeout: int = Field(default=60)

    class Config:
        env_prefix = "AI_SCHOOL_MINIMAX_"


class AppSettings(BaseSettings):
    """Application settings"""
    name: str = "AI Agent School"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 4

    # Communication
    poll_interval: int = 5
    message_timeout: int = 300

    # Graduation
    graduation_streak_days: int = 7

    # Cron monitoring
    heartbeat_interval: int = 300
    grace_periods: int = 2
    max_retries: int = 3

    class Config:
        env_prefix = "AI_SCHOOL_"


class Settings(BaseSettings):
    """Combined settings"""
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    minimax: MiniMaxSettings = Field(default_factory=MiniMaxSettings)
    app: AppSettings = Field(default_factory=AppSettings)

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables"""
        return cls(
            database=DatabaseSettings(),
            redis=RedisSettings(),
            minimax=MiniMaxSettings(),
            app=AppSettings()
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings.from_env()
