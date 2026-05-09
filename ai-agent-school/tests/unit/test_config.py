# tests/unit/test_config.py
# Configuration tests for 99% coverage

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))


class TestDatabaseSettings:
    """Tests for DatabaseSettings"""

    def test_default_values(self):
        """Test DatabaseSettings default values"""
        from core.config import DatabaseSettings

        settings = DatabaseSettings()

        assert settings.url == "postgresql://postgres:postgres@localhost:5432/ai_school"
        assert settings.pool_size == 10
        assert settings.max_overflow == 20
        assert settings.echo == False

    def test_env_override(self):
        """Test DatabaseSettings environment variable override"""
        with patch.dict(os.environ, {
            "AI_SCHOOL_DB_URL": "postgresql://user:pass@host:5432/db",
            "AI_SCHOOL_DB_POOL_SIZE": "20"
        }):
            from core.config import DatabaseSettings

            settings = DatabaseSettings()

            assert settings.url == "postgresql://user:pass@host:5432/db"
            assert settings.pool_size == 20


class TestRedisSettings:
    """Tests for RedisSettings"""

    def test_default_values(self):
        """Test RedisSettings default values"""
        from core.config import RedisSettings

        settings = RedisSettings()

        assert settings.url == "redis://localhost:6379/0"

    def test_env_override(self):
        """Test RedisSettings environment variable override"""
        with patch.dict(os.environ, {
            "AI_SCHOOL_REDIS_URL": "redis://custom:6379/1"
        }):
            from core.config import RedisSettings

            settings = RedisSettings()

            assert settings.url == "redis://custom:6379/1"


class TestMiniMaxSettings:
    """Tests for MiniMaxSettings"""

    def test_default_values(self):
        """Test MiniMaxSettings default values"""
        from core.config import MiniMaxSettings

        settings = MiniMaxSettings()

        assert settings.api_key == ""
        assert settings.base_url == "https://api.minimax.chat"
        assert settings.model == "MiniMax-2.7-highspeed"
        assert settings.timeout == 60

    def test_env_override(self):
        """Test MiniMaxSettings environment variable override"""
        with patch.dict(os.environ, {
            "AI_SCHOOL_MINIMAX_API_KEY": "test-key-123",
            "AI_SCHOOL_MINIMAX_MODEL": "custom-model"
        }):
            from core.config import MiniMaxSettings

            settings = MiniMaxSettings()

            assert settings.api_key == "test-key-123"
            assert settings.model == "custom-model"


class TestAppSettings:
    """Tests for AppSettings"""

    def test_default_values(self):
        """Test AppSettings default values"""
        from core.config import AppSettings

        settings = AppSettings()

        assert settings.name == "AI Agent School"
        assert settings.version == "1.0.0"
        assert settings.debug == False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.workers == 4
        assert settings.poll_interval == 5
        assert settings.message_timeout == 300
        assert settings.graduation_streak_days == 7
        assert settings.heartbeat_interval == 300
        assert settings.grace_periods == 2
        assert settings.max_retries == 3

    def test_env_override(self):
        """Test AppSettings environment variable override"""
        with patch.dict(os.environ, {
            "AI_SCHOOL_DEBUG": "true",
            "AI_SCHOOL_PORT": "9000",
            "AI_SCHOOL_GRADUATION_STREAK_DAYS": "14"
        }):
            from core.config import AppSettings

            settings = AppSettings()

            assert settings.debug == True
            assert settings.port == 9000
            assert settings.graduation_streak_days == 14


class TestSettings:
    """Tests for combined Settings"""

    def test_default_values(self):
        """Test Settings default values"""
        from core.config import Settings

        settings = Settings()

        assert settings.database.url == "postgresql://postgres:postgres@localhost:5432/ai_school"
        assert settings.redis.url == "redis://localhost:6379/0"
        assert settings.minimax.model == "MiniMax-2.7-highspeed"
        assert settings.app.graduation_streak_days == 7

    def test_from_env(self):
        """Test Settings.from_env creates from environment"""
        with patch.dict(os.environ, {
            "AI_SCHOOL_MINIMAX_API_KEY": "test-key"
        }):
            from core.config import Settings

            settings = Settings.from_env()

            assert settings.minimax.api_key == "test-key"

    def test_nested_settings_access(self):
        """Test Settings nested settings are accessible"""
        from core.config import Settings

        settings = Settings()

        assert settings.database.pool_size == 10
        assert settings.app.port == 8080
        assert settings.minimax.timeout == 60


class TestGetSettings:
    """Tests for get_settings function"""

    def test_returns_singleton(self):
        """Test get_settings returns cached singleton"""
        from core.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_lru_cache_works(self):
        """Test get_settings uses lru_cache"""
        from core.config import get_settings
        import functools

        assert isinstance(get_settings, functools._lru_cache_wrapper)

    def test_cached_after_first_call(self):
        """Test settings are cached after first call"""
        from core.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_settings_immutable_after_cached(self):
        """Test cached settings reflect original values"""
        from core.config import get_settings

        settings = get_settings()

        assert settings.app.name == "AI Agent School"
        assert settings.app.version == "1.0.0"

    def test_clear_cache_resets(self):
        """Test clearing cache works"""
        from core.config import get_settings

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        assert settings1 is not settings2