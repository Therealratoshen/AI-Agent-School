# Test Cron Monitor

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cron.monitor import CronMonitor, AutoHealer


@pytest.fixture
def school_id():
    return "00000000-0000-0000-0000-000000000001"


def test_cron_monitor_init(school_id):
    """Test CronMonitor initializes correctly"""
    monitor = CronMonitor(school_id)
    assert monitor.school_id == school_id
    assert monitor.heartbeat_interval == 300
    assert monitor.grace_periods == 2


def test_record_heartbeat(school_id):
    """Test heartbeat recording"""
    monitor = CronMonitor(school_id)
    monitor.db.execute_one.return_value = {
        "id": "job-123",
        "name": "test-job",
        "status": "ok",
        "last_heartbeat": None
    }

    result = monitor.receive_heartbeat("job-123", "ok")

    assert result["status"] == "recorded" or result["status"] == "ok"


def test_auto_healer_init():
    """Test AutoHealer initializes correctly"""
    config = {"cron": {"base_delay": 5, "max_delay": 300}}
    healer = AutoHealer(config)
    assert healer.auto_heal_enabled == True
    assert healer.max_retries == 3


def test_exponential_backoff_delay():
    """Test exponential backoff calculation"""
    config = {"cron": {"base_delay": 5, "max_delay": 300}}
    healer = AutoHealer.__new__(AutoHealer)
    healer.base_delay = 5
    healer.max_delay = 300

    assert healer.exponential_backoff_delay(0) == 5
    assert healer.exponential_backoff_delay(1) == 10
    assert healer.exponential_backoff_delay(2) == 20
    assert healer.exponential_backoff_delay(3) == 40
    assert healer.exponential_backoff_delay(10) == 300