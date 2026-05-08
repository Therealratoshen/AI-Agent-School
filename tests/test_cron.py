# Test Cron Auto-Heal

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.cron import CronMonitor, FailureDetector, AutoHealer

@pytest.fixture
def config():
    return {
        "cron": {
            "heartbeat_interval": 300,
            "grace_periods": 2,
            "auto_heal_enabled": True,
            "monitored_jobs": [
                {"name": "test-job", "command": "echo test"}
            ]
        }
    }

def test_cron_monitor_init(config):
    monitor = CronMonitor(config)
    assert monitor.heartbeat_interval == 300
    assert monitor.grace_periods == 2

def test_record_heartbeat(config):
    monitor = CronMonitor(config)
    result = monitor.record_heartbeat("test-job")
    assert result["status"] == "recorded"

def test_failure_detector_init(config):
    detector = FailureDetector(config)
    assert detector.heartbeat_interval == 300
    assert detector.grace_periods == 2

def test_auto_healer_init(config):
    healer = AutoHealer(config)
    assert healer.auto_heal_enabled == True
    assert healer.max_retries == 3
