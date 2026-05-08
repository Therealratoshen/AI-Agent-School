# Test Teacher Agent

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.teacher import TeacherAgent
from school.teacher.lessons import LessonManager

@pytest.fixture
def config():
    return {
        "teacher": {
            "name": "TestTeacher",
            "persona": "test",
            "default_topic": "cron_handling"
        },
        "communication": {
            "base_dir": "/tmp/ai-school-test",
            "to_student": "/tmp/ai-school-test/to_student",
            "from_student": "/tmp/ai-school-test/from_student",
            "poll_interval": 1
        }
    }

def test_teacher_init(config):
    teacher = TeacherAgent(config)
    assert teacher.name == "TestTeacher"
    assert teacher.topic == "cron_handling"

def test_enroll_student(config):
    teacher = TeacherAgent(config)
    result = teacher.enroll_student("test-student-1")
    assert result["status"] == "enrolled"
    assert result["student_id"] == "test-student-1"
    assert teacher.student_id == "test-student-1"

def test_deliver_lesson(config):
    teacher = TeacherAgent(config)
    teacher.enroll_student("test-student-1")

    result = teacher.deliver_lesson(1)
    assert result["status"] == "delivered"
    assert result["lesson_number"] == 1

def test_progress(config):
    teacher = TeacherAgent(config)
    teacher.enroll_student("test-student-1")

    progress = teacher.get_progress()
    assert progress["student_id"] == "test-student-1"
    assert progress["status"] == "training"
