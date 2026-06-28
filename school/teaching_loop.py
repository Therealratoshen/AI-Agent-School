# Teaching Loop - Background processor for Teacher <-> Student messages

import threading
import time
from typing import Any, Dict, Optional

from shared import MessageType, setup_logging

logger = setup_logging(__name__, "./logs/teaching_loop.log")


class TeachingLoop:
    """
    Polls the student->teacher message queue and drives the teaching flow.
    """

    def __init__(self, server: Any):
        self.server = server
        self.poll_interval = server.config.get("communication", {}).get("poll_interval", 2)
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Teaching loop started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Teaching loop stopped")

    def _run(self) -> None:
        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Teaching loop error: {e}")
            time.sleep(self.poll_interval)

    def tick(self) -> int:
        """Process one batch of student messages. Returns count processed."""
        messages = self.server.student_receiver.check_for_messages()
        for message in messages:
            self._process_message(message)
        return len(messages)

    def _process_message(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")

        if msg_type in (MessageType.QUIZ_SUBMISSION, MessageType.QUIZ_SUBMISSION.value):
            self._handle_quiz_submission(message)
        elif msg_type in (MessageType.STATUS, MessageType.STATUS.value):
            self._handle_status_update(message)
        elif msg_type in (MessageType.ERROR, MessageType.ERROR.value):
            self._handle_error(message)
        else:
            logger.warning(f"Unhandled message type: {msg_type}")

    def _handle_quiz_submission(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload", {})
        lesson_id = payload.get("lesson_id")
        answers = payload.get("answers", {})

        result = self.server.teacher._handle_quiz_submission(payload)

        if result.get("passed"):
            self.server.progress_tracker.complete_lesson(lesson_id, result["score"])
            logger.info(f"Student passed quiz for {lesson_id}: {result['score']}%")
        else:
            logger.info(f"Student needs retry for {lesson_id}: {result['score']}%")
            for item in result.get("feedback", []):
                if not item.get("correct"):
                    self.server.teacher.correct_mistake({
                        "mistake": item.get("question"),
                        "correct": item.get("correct_answer"),
                        "explanation": item.get("explanation", "Review the lesson and try again."),
                    })

    def _handle_status_update(self, message: Dict[str, Any]) -> None:
        payload = message.get("payload", {})
        logger.info(f"Student status: {payload.get('status')}")

    def _handle_error(self, message: Dict[str, Any]) -> None:
        import json

        payload = message.get("payload", {})
        error = payload.get("error")
        context = payload.get("context", {})
        self.server.mistake_detector.log_mistake(
            mistake=error,
            context=json.dumps(context) if isinstance(context, dict) else str(context),
            severity="high",
        )
        logger.error(f"Student error: {error}")
