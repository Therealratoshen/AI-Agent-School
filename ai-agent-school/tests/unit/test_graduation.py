# tests/unit/test_graduation.py
# Graduation Monitor tests for 99% coverage

import os
import sys
import json
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))


class TestGraduationMonitor:
    """Tests for GraduationMonitor"""

    def test_monitor_initializes_correctly(self, sample_school_id, mock_settings):
        """Test monitor initializes with correct settings"""
        with patch('core.database.get_db'), \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)

            assert monitor.school_id == sample_school_id
            assert monitor.graduation_streak_days == 7

    def test_get_today_failures_returns_mistakes(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _get_today_failures returns mistake failures"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute.return_value = [
                {"type": "mistake", "id": "mistake-1"},
                {"type": "mistake", "id": "mistake-2"}
            ]

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._get_today_failures(sample_student_id, date.today())

            assert len(result) == 2

    def test_get_today_lesson_completion(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _get_today_lesson_completion returns lesson ID"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = {"lesson_id": "lesson-123"}

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._get_today_lesson_completion(sample_student_id, date.today())

            assert result == "lesson-123"

    def test_get_today_lesson_completion_returns_none_when_no_lesson(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _get_today_lesson_completion returns None when no lesson"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = None

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._get_today_lesson_completion(sample_student_id, date.today())

            assert result is None

    def test_get_today_mistakes(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _get_today_mistakes returns count"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_scalar.return_value = 5

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._get_today_mistakes(sample_student_id, date.today())

            assert result == 5

    def test_get_today_corrections(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _get_today_corrections returns count"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_scalar.return_value = 3

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._get_today_corrections(sample_student_id, date.today())

            assert result == 3

    def test_update_failure_streak_increments_streak(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test update_failure_streak increments streak on failure-free day"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_scalar.return_value = 3

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor.update_failure_streak(sample_student_id)

            assert result["streak_days"] == 3
            assert result["days_remaining"] == 4
            assert result["graduated"] == False

    def test_update_failure_streak_triggers_graduation(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test update_failure_streak triggers graduation at 7 days"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_scalar.return_value = 7

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            with patch.object(monitor, '_trigger_graduation', return_value=True):
                result = monitor.update_failure_streak(sample_student_id)

                assert result["graduated"] == True

    def test_trigger_graduation_success(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _trigger_graduation successfully graduates student"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue') as mock_queue_cls:

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.side_effect = [
                {
                    "id": sample_student_id,
                    "name": "Test Student",
                    "status": "training",
                    "failure_streak": 7
                },
                {
                    "training_days": 7,
                    "total_mistakes": 10,
                    "corrections_learned": 8
                }
            ]
            mock_db.execute_scalar.return_value = 5

            mock_queue = MagicMock()
            mock_queue.enqueue = AsyncMock()
            mock_queue_cls.return_value = mock_queue

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db
            monitor.queue = mock_queue

            result = monitor._trigger_graduation(sample_student_id)

            assert result == True

    def test_trigger_graduation_student_not_found(
        self, sample_school_id, mock_settings
    ):
        """Test _trigger_graduation returns False when student not found"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = None

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._trigger_graduation("nonexistent-id")

            assert result == False

    def test_trigger_graduation_already_graduated(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test _trigger_graduation returns False when already graduated"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = {
                "id": sample_student_id,
                "name": "Test Student",
                "status": "graduated",
                "failure_streak": 7
            }

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor._trigger_graduation(sample_student_id)

            assert result == False

    def test_get_graduation_status(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test get_graduation_status returns complete status"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = {
                "id": sample_student_id,
                "name": "Test Student",
                "status": "training",
                "failure_streak": 3,
                "graduated_at": None
            }
            mock_db.execute.return_value = [
                {"date": date.today(), "had_failure": False, "mistake_count": 0}
            ]

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor.get_graduation_status(sample_student_id)

            assert result["student_id"] == sample_student_id
            assert result["status"] == "training"
            assert result["failure_streak"] == 3
            assert result["days_remaining"] == 4
            assert result["graduated"] == False

    def test_get_graduation_status_student_not_found(
        self, sample_school_id, mock_settings
    ):
        """Test get_graduation_status returns error for missing student"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.graduation.get_settings', return_value=mock_settings), \
             patch('core.message_queue.MessageQueue'):

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            mock_db.execute_one.return_value = None

            from teacher.graduation import GraduationMonitor
            monitor = GraduationMonitor(sample_school_id)
            monitor.db = mock_db

            result = monitor.get_graduation_status("nonexistent-id")

            assert "error" in result


class TestGraduationService:
    """Tests for GraduationService"""

    def test_service_initializes(self, sample_school_id, mock_settings):
        """Test service initializes with monitor"""
        with patch('teacher.graduation.GraduationMonitor') as mock_monitor_cls:
            mock_monitor = MagicMock()
            mock_monitor_cls.return_value = mock_monitor

            from teacher.graduation import GraduationService
            service = GraduationService(sample_school_id)

            assert service.school_id == sample_school_id

    def test_check_student_calls_monitor(
        self, sample_school_id, sample_student_id, mock_settings
    ):
        """Test check_student calls monitor get_graduation_status"""
        with patch('teacher.graduation.GraduationMonitor') as mock_monitor_cls:
            mock_monitor = MagicMock()
            mock_monitor.get_graduation_status.return_value = {
                "student_id": sample_student_id,
                "status": "training"
            }
            mock_monitor_cls.return_value = mock_monitor

            from teacher.graduation import GraduationService
            service = GraduationService(sample_school_id)

            result = service.check_student(sample_student_id)

            assert result["student_id"] == sample_student_id
            mock_monitor.get_graduation_status.assert_called_once_with(sample_student_id)

    def test_run_all_daily_checks(self, sample_school_id, mock_settings):
        """Test run_all_daily_checks runs checks for all students"""
        with patch('teacher.graduation.GraduationMonitor') as mock_monitor_cls, \
             patch('core.database.get_db') as mock_get_db:

            mock_db = MagicMock()
            mock_db.execute.return_value = [
                {"id": "student-1"},
                {"id": "student-2"}
            ]
            mock_get_db.return_value = mock_db

            mock_monitor = MagicMock()
            mock_monitor.run_daily_check.return_value = {
                "student_id": "student-1",
                "graduated": False
            }
            mock_monitor_cls.return_value = mock_monitor

            from teacher.graduation import GraduationService
            service = GraduationService(sample_school_id)
            service.db = mock_db

            result = service.run_all_daily_checks()

            assert len(result) == 2

    def test_get_all_graduation_status(self, sample_school_id, mock_settings):
        """Test get_all_graduation_status returns all student statuses"""
        with patch('teacher.graduation.GraduationMonitor') as mock_monitor_cls, \
             patch('teacher.graduation.get_db') as mock_get_db:

            mock_db = MagicMock()
            students = [
                {"id": "student-1", "name": "Student 1", "status": "training", "failure_streak": 2},
                {"id": "student-2", "name": "Student 2", "status": "graduated", "failure_streak": 7}
            ]
            mock_db.execute.return_value = students
            mock_get_db.return_value = mock_db

            mock_monitor = MagicMock()
            mock_monitor.get_graduation_status.side_effect = [
                {"student_id": "student-1", "status": "training", "graduated": False},
                {"student_id": "student-2", "status": "graduated", "graduated": True}
            ]
            mock_monitor_cls.return_value = mock_monitor

            from teacher.graduation import GraduationService
            service = GraduationService(sample_school_id)
            service.db = mock_db

            result = service.get_all_graduation_status()

            assert len(result) == 2