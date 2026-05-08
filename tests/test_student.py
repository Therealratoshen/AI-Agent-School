# Test Student Agent

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from student_agent.main import StudentAgent

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
    agent = StudentAgent(config)
    assert agent.poll_interval == 1
