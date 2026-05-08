# Student Receiver - Receives and processes lessons from teacher

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, Optional
from datetime import datetime
from shared import (
    MessageType, timestamp, generate_id,
    setup_logging, ensure_dir
)

logger = setup_logging(__name__, "./logs/student_receiver.log")

class StudentReceiver:
    """
    Receives lessons and messages from Teacher Agent
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.comm_config = config.get('communication', {})
        self.base_dir = self.comm_config.get('base_dir', '/shared/ai-school')
        self.to_student_dir = self.comm_config.get('to_student')
        self.from_student_dir = self.comm_config.get('from_student')

        self._ensure_directories()
        self.teacher_url = config.get('student', {}).get('api_endpoint', 'http://localhost:8000')

        logger.info("StudentReceiver initialized")

    def _ensure_directories(self):
        """Create directories if needed"""
        ensure_dir(self.from_student_dir)

    def check_for_lessons(self) -> list:
        """Check for new lessons from teacher"""
        import glob
        messages = []

        pattern = os.path.join(self.to_student_dir, "*.json")
        for filepath in glob.glob(pattern):
            try:
                import json
                with open(filepath) as f:
                    message = json.load(f)
                    messages.append(message)

                os.remove(filepath)
                logger.info(f"Received lesson: {message.get('type')}")
            except Exception as e:
                logger.error(f"Failed to read lesson: {e}")

        return messages

    def receive_lesson(self, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming lesson"""
        payload = lesson_data.get('payload', {})
        lesson = payload.get('lesson', {})

        return {
            "status": "received",
            "lesson_id": lesson.get('id'),
            "lesson_title": lesson.get('title'),
            "quiz_count": len(lesson.get('quiz', [])),
            "timestamp": timestamp()
        }

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> Dict[str, Any]:
        """Submit quiz answers to teacher"""
        message = {
            "type": MessageType.QUIZ_SUBMISSION,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "lesson_id": lesson_id,
                "answers": answers,
                "submitted_at": timestamp()
            }
        }

        import glob
        filepath = os.path.join(self.from_student_dir, f"{generate_id('quiz_')}.json")
        with open(filepath, 'w') as f:
            import json
            json.dump(message, f, indent=2)

        logger.info(f"Quiz submitted for lesson: {lesson_id}")

        return {
            "status": "submitted",
            "lesson_id": lesson_id,
            "answers_count": len(answers)
        }

    def receive_correction(self, correction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive and acknowledge correction"""
        payload = correction_data.get('payload', {})

        return {
            "status": "correction_received",
            "correction_id": payload.get('id'),
            "mistake": payload.get('mistake'),
            "timestamp": timestamp()
        }

    def send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        """Send status update to teacher"""
        import json

        message = {
            "type": MessageType.STATUS,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "status": status,
                "details": details or {},
                "timestamp": timestamp()
            }
        }

        filepath = os.path.join(self.from_student_dir, f"{generate_id('status_')}.json")
        with open(filepath, 'w') as f:
            json.dump(message, f, indent=2)

    def send_error(self, error: str, context: Dict[str, Any] = None) -> None:
        """Send error to teacher"""
        import json

        message = {
            "type": MessageType.ERROR,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "error": error,
                "context": context or {},
                "timestamp": timestamp()
            }
        }

        filepath = os.path.join(self.from_student_dir, f"{generate_id('error_')}.json")
        with open(filepath, 'w') as f:
            json.dump(message, f, indent=2)

        logger.error(f"Error sent to teacher: {error}")
