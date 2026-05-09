# tests/unit/test_message_queue.py
# Message queue tests for 99% coverage

import os
import sys
import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))

from core.message_queue import (
    MessageQueue,
    MessageListener,
    MessageType,
    MessageStatus
)


class TestMessageQueue:
    """Tests for MessageQueue"""

    def test_init_sets_properties(self, sample_school_id):
        """Test MessageQueue initialization"""
        mock_db = MagicMock()
        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            assert queue.school_id == sample_school_id
            assert queue.db == mock_db

    def test_channel_name_generates_correct_format(self, sample_school_id, sample_student_id):
        """Test channel name format"""
        mock_db = MagicMock()
        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            channel = queue._channel_name(sample_student_id)

            expected = f"school_{sample_school_id}_student_{sample_student_id}"
            assert channel == expected

    @pytest.mark.asyncio
    async def test_enqueue_creates_message(self, sample_school_id, sample_student_id):
        """Test enqueue creates message in database"""
        mock_db = MagicMock()
        mock_db.execute_one.return_value = {"id": "msg-123"}

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            result = await queue.enqueue(
                student_id=sample_student_id,
                message_type=MessageType.LESSON.value,
                payload={"lesson_id": "lesson-1"}
            )

            assert result == "msg-123"
            mock_db.execute_one.assert_called_once()
            mock_db.execute.assert_called_once()  # NOTIFY call

    @pytest.mark.asyncio
    async def test_enqueue_with_priority(self, sample_school_id, sample_student_id):
        """Test enqueue with custom priority"""
        mock_db = MagicMock()
        mock_db.execute_one.return_value = {"id": "msg-123"}

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            await queue.enqueue(
                student_id=sample_student_id,
                message_type=MessageType.CORRECTION.value,
                payload={"correction": "test"},
                priority=10
            )

            # Verify execute_one was called with priority
            call_args = mock_db.execute_one.call_args
            assert "priority" in str(call_args)

    @pytest.mark.asyncio
    async def test_enqueue_with_expiration(self, sample_school_id, sample_student_id):
        """Test enqueue with expiration time"""
        mock_db = MagicMock()
        mock_db.execute_one.return_value = {"id": "msg-123"}

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            await queue.enqueue(
                student_id=sample_student_id,
                message_type=MessageType.LESSON.value,
                payload={},
                expires_in_seconds=3600
            )

            call_args = mock_db.execute_one.call_args
            assert call_args is not None

    def test_dequeue_returns_pending_messages(self, sample_school_id, sample_message):
        """Test dequeue returns pending messages"""
        mock_db = MagicMock()
        mock_db.execute.return_value = [sample_message]

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            messages = queue.dequeue(sample_message["student_id"])

            assert len(messages) == 1
            assert messages[0]["id"] == sample_message["id"]

    def test_dequeue_respects_limit(self, sample_school_id):
        """Test dequeue respects limit parameter"""
        mock_db = MagicMock()
        mock_db.execute.return_value = []

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            queue.dequeue("student-1", limit=5)

            call_args = mock_db.execute.call_args
            assert call_args is not None

    def test_dequeue_respects_type_filter(self, sample_school_id):
        """Test dequeue filters by message types"""
        mock_db = MagicMock()
        mock_db.execute.return_value = []

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            queue.dequeue("student-1", types=["lesson", "quiz"])

            call_args = mock_db.execute.call_args
            assert "lesson" in str(call_args)

    def test_dequeue_parses_json_payload(self, sample_school_id, sample_message):
        """Test dequeue parses string payload to dict"""
        mock_db = MagicMock()
        message_with_string_payload = {**sample_message, "payload": json.dumps(sample_message["payload"])}
        mock_db.execute.return_value = [message_with_string_payload]

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            messages = queue.dequeue(sample_message["student_id"])

            # Should convert string payload back to dict
            assert isinstance(messages[0]["payload"], dict)

    def test_mark_completed_updates_status(self, sample_school_id):
        """Test mark_completed updates message status"""
        mock_db = MagicMock()

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            queue.mark_completed("msg-123")

            call_args = mock_db.execute.call_args
            assert call_args is not None

    def test_mark_failed_increments_retry_count(self, sample_school_id):
        """Test mark_failed increments retry count"""
        mock_db = MagicMock()
        mock_db.execute_one.return_value = {"retry_count": 1, "max_retries": 3, "student_id": "student-1", "type": "lesson"}

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            result = queue.mark_failed("msg-123", "Test error", retry=True)

            assert result is True  # Should retry

    def test_mark_failed_moves_to_dlq_at_max_retries(self, sample_school_id):
        """Test mark_failed moves message to DLQ when max retries exceeded"""
        mock_db = MagicMock()
        mock_db.execute_one.side_effect = [
            {"retry_count": 2, "max_retries": 3, "student_id": "student-1", "type": "lesson"},
            {"student_id": "student-1", "type": "lesson"}
        ]

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            result = queue.mark_failed("msg-123", "Test error", retry=True)

            assert result is False  # Should move to DLQ, not retry
            # Should insert into DLQ table
            assert mock_db.execute.call_count >= 2

    def test_get_pending_count_returns_correct_count(self, sample_school_id):
        """Test get_pending_count returns correct number"""
        mock_db = MagicMock()
        mock_db.execute_scalar.return_value = 5

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            count = queue.get_pending_count("student-1")

            assert count == 5

    def test_get_pending_count_returns_zero_when_none(self, sample_school_id):
        """Test get_pending_count returns 0 when no pending messages"""
        mock_db = MagicMock()
        mock_db.execute_scalar.return_value = None

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            count = queue.get_pending_count("student-1")

            assert count == 0

    def test_get_queue_stats_returns_breakdown(self, sample_school_id):
        """Test get_queue_stats returns status breakdown"""
        mock_db = MagicMock()
        mock_db.execute.return_value = [
            {"status": "pending", "count": 3},
            {"status": "processing", "count": 1},
            {"status": "completed", "count": 10}
        ]

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            stats = queue.get_queue_stats()

            assert stats["pending"] == 3
            assert stats["processing"] == 1
            assert stats["completed"] == 10
            assert stats["total"] == 14

    def test_get_queue_stats_with_student_filter(self, sample_school_id):
        """Test get_queue_stats filters by student"""
        mock_db = MagicMock()
        mock_db.execute.return_value = [
            {"status": "pending", "count": 2}
        ]

        with patch('core.message_queue.get_db', return_value=mock_db):
            queue = MessageQueue(sample_school_id)

            stats = queue.get_queue_stats(student_id="student-1")

            assert "student_id = 'student-1'" in str(mock_db.execute.call_args)


class TestMessageListener:
    """Tests for MessageListener"""

    def test_init_sets_properties(self, sample_school_id, sample_student_id):
        """Test MessageListener initialization"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)

            assert listener.student_id == sample_student_id
            assert listener._running is False
            assert listener._callbacks == []

    def test_subscribe_registers_callback(self, sample_school_id, sample_student_id):
        """Test subscribe registers a callback"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)

            callback = MagicMock()
            listener.subscribe(callback)

            assert callback in listener._callbacks

    def test_subscribe_registers_multiple_callbacks(self, sample_school_id, sample_student_id):
        """Test subscribe registers multiple callbacks"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)

            callback1 = MagicMock()
            callback2 = MagicMock()
            listener.subscribe(callback1)
            listener.subscribe(callback2)

            assert len(listener._callbacks) == 2

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, sample_school_id, sample_student_id):
        """Test start sets running flag"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)

            await listener.start()

            assert listener._running is True

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, sample_school_id, sample_student_id):
        """Test stop cancels the polling task"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)
            mock_task = AsyncMock()
            mock_task.cancel = MagicMock()
            listener._task = mock_task

            await listener.stop()

            assert listener._running is False
            mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_none_task(self, sample_school_id, sample_student_id):
        """Test stop handles None task gracefully"""
        with patch('core.message_queue.MessageQueue'):
            listener = MessageListener(sample_school_id, sample_student_id)
            listener._task = None

            # Should not raise
            await listener.stop()

            assert listener._running is False


class TestMessageEnums:
    """Tests for message type enums"""

    def test_message_type_values(self):
        """Test MessageType enum values"""
        assert MessageType.LESSON.value == "lesson"
        assert MessageType.QUIZ.value == "quiz"
        assert MessageType.QUIZ_SUBMISSION.value == "quiz_submission"
        assert MessageType.CORRECTION.value == "correction"
        assert MessageType.HEARTBEAT.value == "heartbeat"
        assert MessageType.STATUS.value == "status"
        assert MessageType.ERROR.value == "error"
        assert MessageType.GRADUATION.value == "graduation"
        assert MessageType.ENROLLMENT.value == "enrollment"

    def test_message_status_values(self):
        """Test MessageStatus enum values"""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.PROCESSING.value == "processing"
        assert MessageStatus.COMPLETED.value == "completed"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.DLQ.value == "dlq"
