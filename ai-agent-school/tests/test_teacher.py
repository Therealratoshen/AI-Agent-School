# Test Teacher Agent

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.teacher.agent import TeacherAgent


@pytest.fixture
def school_id():
    return "00000000-0000-0000-0000-000000000001"


def test_teacher_init(school_id):
    """Test teacher agent initializes correctly"""
    teacher = TeacherAgent(school_id)
    assert teacher.school_id == school_id


def test_enroll_student(school_id):
    """Test student enrollment creates student"""
    teacher = TeacherAgent(school_id)
    teacher.db.execute_one.return_value = {
        "id": "test-student-1",
        "school_id": school_id,
        "name": "test-student-1",
        "status": "enrolled"
    }
    teacher.db.execute.return_value = []

    result = teacher.enroll_student("test-student-1")

    assert result["status"] == "enrolled"
    assert result["student_id"] == "test-student-1"
    assert teacher.student_id == "test-student-1"


def test_deliver_lesson(school_id):
    """Test lesson delivery"""
    teacher = TeacherAgent(school_id)
    teacher.db.execute_one.return_value = {
        "id": "test-student-1",
        "school_id": school_id,
        "name": "test-student-1",
        "status": "training"
    }
    teacher.db.execute.return_value = []

    teacher.enroll_student("test-student-1")

    result = teacher.deliver_lesson(1)
    assert result["status"] == "delivered"
    assert result["lesson_number"] == 1


def test_progress(school_id):
    """Test progress retrieval"""
    teacher = TeacherAgent(school_id)
    teacher.db.execute_one.return_value = {
        "id": "test-student-1",
        "school_id": school_id,
        "name": "test-student-1",
        "status": "training"
    }
    teacher.db.execute.return_value = []

    teacher.enroll_student("test-student-1")

    progress = teacher.get_progress()
    assert progress["student_id"] == "test-student-1"
    assert progress["status"] == "training"