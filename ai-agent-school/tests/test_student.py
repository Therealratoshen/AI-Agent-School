# Test Student Agent

import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.student.agent import StudentAgent


@pytest.fixture
def config():
    return {
        "communication": {
            "base_dir": "/tmp/ai-school-test",
            "to_student": "/tmp/ai-school-test/to_student",
            "from_student": "/tmp/ai-school-test/from_student",
            "poll_interval": 1
        },
        "memory": {
            "student_memory_path": "/tmp/ai-school-test/memory"
        }
    }


def test_student_init(config):
    """Test student agent initializes correctly"""
    agent = StudentAgent(config)
    assert agent.poll_interval == 1