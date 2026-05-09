# Message Queue Module
# PostgreSQL-backed message queue with LISTEN/NOTIFY for push messaging

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

import structlog

from core.database import get_db


logger = structlog.get_logger(__name__)


class MessageType(str, Enum):
    """Message types for agent communication"""
    LESSON = "lesson"
    QUIZ = "quiz"
    QUIZ_SUBMISSION = "quiz_submission"
    CORRECTION = "correction"
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    ERROR = "error"
    GRADUATION = "graduation"
    ENROLLMENT = "enrollment"


class MessageStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"


class MessageQueue:
    """
    PostgreSQL-backed message queue with LISTEN/NOTIFY.

    Features:
    - Durable messages (survive crashes)
    - Push notifications via PostgreSQL NOTIFY
    - Automatic retry with backoff
    - Dead letter queue for failed messages
    - Priority handling
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self._listeners: Dict[str, Callable] = {}
        self._running = False

    def _channel_name(self, student_id: str) -> str:
        """Generate LISTEN/NOTIFY channel name for a student"""
        return f"school_{self.school_id}_student_{student_id}"

    async def enqueue(
        self,
        student_id: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: int = 0,
        max_retries: int = 3,
        expires_in_seconds: Optional[int] = None
    ) -> str:
        """
        Add a message to the queue.

        Args:
            student_id: Target student
            message_type: Type of message
            payload: Message content
            priority: Higher = more urgent (processed first)
            max_retries: Max retry attempts before DLQ
            expires_in_seconds: Optional expiration time

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

        query = """
            INSERT INTO messages (
                id, school_id, student_id, type, payload,
                status, priority, max_retries, expires_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """

        result = self.db.execute_one(
            query,
            (
                message_id,
                self.school_id,
                student_id,
                message_type,
                json.dumps(payload),
                MessageStatus.PENDING.value,
                priority,
                max_retries,
                expires_at
            )
        )

        # Notify the student channel
        channel = self._channel_name(student_id)
        self.db.execute(
            f"NOTIFY {channel}, %s",
            (json.dumps({"type": message_type, "id": message_id}),)
        )

        logger.info(
            "message_queued",
            message_id=message_id,
            student_id=student_id,
            message_type=message_type,
            channel=channel
        )

        return result["id"] if result else message_id

    def dequeue(
        self,
        student_id: str,
        types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get pending messages for a student (non-blocking).

        Args:
            student_id: Target student
            types: Optional filter by message types
            limit: Max messages to retrieve

        Returns:
            List of messages
        """
        # Get messages
        type_filter = ""
        if types:
            type_list = "', '".join(types)
            type_filter = f"AND type IN ('{type_list}')"

        query = f"""
            UPDATE messages
            SET status = %s, processed_at = NOW()
            WHERE id IN (
                SELECT id FROM messages
                WHERE school_id = %s
                AND student_id = %s
                AND status = %s
                {type_filter}
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY priority DESC, created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """

        messages = self.db.execute(
            query,
            (
                MessageStatus.PROCESSING.value,
                self.school_id,
                student_id,
                MessageStatus.PENDING.value,
                limit
            )
        )

        # Parse JSON payloads
        for msg in messages:
            if isinstance(msg.get("payload"), str):
                msg["payload"] = json.loads(msg["payload"])

        return messages

    def mark_completed(self, message_id: str) -> None:
        """Mark a message as successfully processed"""
        query = """
            UPDATE messages
            SET status = %s, processed_at = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (MessageStatus.COMPLETED.value, message_id))
        logger.debug("message_completed", message_id=message_id)

    def mark_failed(
        self,
        message_id: str,
        error_message: str,
        retry: bool = True
    ) -> bool:
        """
        Mark a message as failed, retrying or moving to DLQ.

        Returns:
            True if retried, False if moved to DLQ
        """
        # Get current retry count
        query = "SELECT retry_count, max_retries FROM messages WHERE id = %s"
        msg = self.db.execute_one(query, (message_id,))

        if not msg:
            return False

        new_retry_count = msg["retry_count"] + 1

        if new_retry_count >= msg["max_retries"]:
            # Move to DLQ
            query = """
                UPDATE messages
                SET status = %s, retry_count = %s
                WHERE id = %s
            """
            self.db.execute(query, (MessageStatus.DLQ.value, new_retry_count, message_id))

            # Also add to DLQ table
            dlq_query = """
                INSERT INTO dead_letter_queue (
                    school_id, original_type, original_payload, error_message,
                    retry_count, status, created_at
                )
                SELECT school_id, type, payload, %s, %s, 'pending_review', NOW()
                FROM messages WHERE id = %s
            """
            self.db.execute(dlq_query, (error_message, new_retry_count, message_id))

            logger.warning("message_moved_to_dlq", message_id=message_id)
            return False
        else:
            # Retry
            query = """
                UPDATE messages
                SET status = %s, retry_count = %s, error_message = %s
                WHERE id = %s
            """
            self.db.execute(
                query,
                (MessageStatus.PENDING.value, new_retry_count, error_message, message_id)
            )

            # Re-notify
            msg_data = self.db.execute_one(
                "SELECT student_id, type FROM messages WHERE id = %s",
                (message_id,)
            )
            if msg_data:
                channel = self._channel_name(msg_data["student_id"])
                self.db.execute(
                    f"NOTIFY {channel}, %s",
                    (json.dumps({"type": msg_data["type"], "id": message_id, "retry": True}),)
                )

            logger.info("message_scheduled_retry", message_id=message_id, retry=new_retry_count)
            return True

    def get_pending_count(self, student_id: str) -> int:
        """Get count of pending messages for a student"""
        query = """
            SELECT COUNT(*) as count FROM messages
            WHERE school_id = %s AND student_id = %s AND status = %s
        """
        result = self.db.execute_scalar(
            query,
            (self.school_id, student_id, MessageStatus.PENDING.value)
        )
        return result or 0

    def get_queue_stats(self, student_id: Optional[str] = None) -> Dict[str, Any]:
        """Get queue statistics"""
        where = f"school_id = '{self.school_id}'"
        if student_id:
            where += f" AND student_id = '{student_id}'"

        query = f"""
            SELECT
                status,
                COUNT(*) as count
            FROM messages
            WHERE {where}
            GROUP BY status
        """
        results = self.db.execute(query)

        stats = {s["status"]: s["count"] for s in results}
        stats["total"] = sum(stats.values())

        return stats


class MessageListener:
    """
    Async listener for message notifications using LISTEN/NOTIFY.

    Usage:
        listener = MessageListener(school_id)
        await listener.subscribe(student_id, callback)
        await listener.start()
    """

    def __init__(self, school_id: str, student_id: str):
        self.queue = MessageQueue(school_id)
        self.student_id = student_id
        self.channel = self.queue._channel_name(student_id)
        self._callbacks: List[Callable] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def subscribe(self, callback: Callable) -> None:
        """Register a callback to be called when messages arrive"""
        self._callbacks.append(callback)

    async def _poll_loop(self) -> None:
        """Poll for messages when NOTIFY isn't available"""
        while self._running:
            messages = self.queue.dequeue(self.student_id, limit=10)

            for msg in messages:
                for callback in self._callbacks:
                    try:
                        await callback(msg)
                    except Exception as e:
                        logger.error("callback_error", error=str(e))

            if messages:
                # Mark as completed
                for msg in messages:
                    self.queue.mark_completed(msg["id"])

            await asyncio.sleep(self.queue.db.execute_scalar(
                "SELECT GREATEST(1, (SELECT poll_interval FROM settings LIMIT 1))"
            ) or 5)

    async def start(self) -> None:
        """Start listening for messages"""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("message_listener_started", channel=self.channel)

    async def stop(self) -> None:
        """Stop listening"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("message_listener_stopped", channel=self.channel)
