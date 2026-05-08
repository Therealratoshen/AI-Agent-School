# Teacher Agent - Core teaching logic

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Optional, Dict, Any, List
from datetime import datetime
from shared import (
    generate_id, timestamp, setup_logging,
    MessageType, TrainingStatus, LessonContent
)
from .lessons import LessonManager
from .communicator import FileCommunicator

logger = setup_logging(__name__, "./logs/teacher.log")

class TeacherAgent:
    """
    Teacher Agent - Teaches lessons to Student Agent
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('teacher', {}).get('name', 'Teacher')
        self.persona = config.get('teacher', {}).get('persona', 'patient_mentor')
        self.topic = config.get('teacher', {}).get('default_topic', 'cron_handling')

        self.communicator = FileCommunicator(config)
        self.lesson_manager = LessonManager(self.topic)

        self.student_id: Optional[str] = None
        self.current_lesson_index = 0
        self.training_status = TrainingStatus.ENROLLED
        self.lessons_completed: List[str] = []

        self.prompt = self._build_prompt()
        logger.info(f"Teacher Agent initialized: {self.name}, topic: {self.topic}")

    def _build_prompt(self) -> str:
        return f"""You are an AI Trainer Agent named {self.name}.

Your role is to teach student agents about {self.topic.replace('_', ' ')}.

Teaching Guidelines:
1. Be patient and encouraging
2. Break complex topics into simple steps
3. Provide practical examples
4. Check for understanding before moving on
5. Adapt to the student's learning pace

When a student asks a question:
1. Acknowledge their question
2. Provide a clear, concise answer
3. Give examples where appropriate
4. Ask if they need clarification

Available Courses:
- Cron Handling: Silent Failure Detection
  - Module 1: Cron Fundamentals
  - Module 2: Heartbeat Monitoring
  - Module 3: Silent Failure Detection
  - Module 4: Auto-Recovery
  - Module 5: Hands-on Lab
"""

    def enroll_student(self, student_id: str) -> Dict[str, Any]:
        """Enroll a student for training"""
        self.student_id = student_id
        self.training_status = TrainingStatus.TRAINING
        self.current_lesson_index = 0

        logger.info(f"Enrolled student: {student_id}")

        first_lesson = self.lesson_manager.get_lesson(1)

        return {
            "status": "enrolled",
            "student_id": student_id,
            "teacher": self.name,
            "topic": self.topic,
            "first_lesson": first_lesson,
            "total_lessons": self.lesson_manager.total_lessons()
        }

    def deliver_lesson(self, lesson_number: int) -> Dict[str, Any]:
        """Send a lesson to the student"""
        if not self.student_id:
            return {"status": "error", "message": "No student enrolled"}

        lesson = self.lesson_manager.get_lesson(lesson_number)
        if not lesson:
            return {"status": "error", "message": f"Lesson {lesson_number} not found"}

        message = {
            "type": MessageType.LESSON,
            "sender": self.name,
            "recipient": self.student_id,
            "payload": {
                "lesson": lesson,
                "lesson_number": lesson_number,
                "total_lessons": self.lesson_manager.total_lessons()
            }
        }

        self.communicator.send_to_student(message)

        logger.info(f"Delivered lesson {lesson_number}: {lesson.title}")

        return {
            "status": "delivered",
            "lesson_number": lesson_number,
            "lesson_title": lesson.title
        }

    def deliver_next_lesson(self) -> Dict[str, Any]:
        """Deliver the next lesson in sequence"""
        self.current_lesson_index += 1
        return self.deliver_lesson(self.current_lesson_index)

    def receive_student_response(self) -> Optional[Dict[str, Any]]:
        """Receive and process messages from student"""
        messages = self.communicator.receive_from_student()

        responses = []
        for msg in messages:
            response = self._process_message(msg)
            if response:
                responses.append(response)

        return responses if responses else None

    def _process_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a message from student"""
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type == MessageType.QUIZ_SUBMISSION:
            return self._handle_quiz_submission(payload)
        elif msg_type == MessageType.STATUS:
            return self._handle_status_update(payload)
        elif msg_type == MessageType.ERROR:
            return self._handle_error(payload)

        return None

    def _handle_quiz_submission(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Grade student's quiz submission"""
        lesson_id = payload.get("lesson_id")
        answers = payload.get("answers", {})

        result = self.lesson_manager.grade_quiz(lesson_id, answers)

        if result["passed"]:
            self.lessons_completed.append(lesson_id)
            self.communicator.send_to_student({
                "type": MessageType.QUIZ,
                "sender": self.name,
                "recipient": self.student_id,
                "payload": {
                    "result": result,
                    "next_lesson": self.current_lesson_index + 1
                }
            })
            logger.info(f"Student passed quiz: {lesson_id}")
        else:
            self.communicator.send_to_student({
                "type": MessageType.QUIZ,
                "sender": self.name,
                "recipient": self.student_id,
                "payload": {
                    "result": result,
                    "retry": True
                }
            })
            logger.info(f"Student needs retry: {lesson_id}")

        return result

    def _handle_status_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status update from student"""
        status = payload.get("status")
        logger.info(f"Student status update: {status}")
        return {"received": True, "status": status}

    def _handle_error(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle error from student"""
        error = payload.get("error")
        logger.error(f"Student error: {error}")
        return {"acknowledged": True}

    def correct_mistake(self, mistake_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send correction to student"""
        if not self.student_id:
            return {"status": "error", "message": "No student enrolled"}

        correction = {
            "id": generate_id("corr_"),
            "mistake": mistake_data.get("mistake"),
            "correct_answer": mistake_data.get("correct"),
            "explanation": mistake_data.get("explanation", "This is the correct approach."),
            "created_at": timestamp()
        }

        message = {
            "type": MessageType.CORRECTION,
            "sender": self.name,
            "recipient": self.student_id,
            "payload": correction
        }

        self.communicator.send_to_student(message)

        logger.info(f"Sent correction: {correction['id']}")

        return {
            "status": "corrected",
            "correction_id": correction["id"]
        }

    def get_progress(self) -> Dict[str, Any]:
        """Get training progress"""
        return {
            "student_id": self.student_id,
            "status": self.training_status,
            "current_lesson": self.current_lesson_index,
            "lessons_completed": self.lessons_completed,
            "total_lessons": self.lesson_manager.total_lessons(),
            "progress_percent": (
                len(self.lessons_completed) / self.lesson_manager.total_lessons() * 100
                if self.lesson_manager.total_lessons() > 0 else 0
            )
        }

    def is_production_ready(self) -> bool:
        """Check if student is ready for production"""
        return (
            len(self.lessons_completed) >= self.lesson_manager.total_lessons() and
            self.training_status == TrainingStatus.TRAINING
        )

    def graduate_student(self) -> Dict[str, Any]:
        """Graduate the student - training complete"""
        if not self.is_production_ready():
            return {"status": "error", "message": "Not ready for graduation"}

        self.training_status = TrainingStatus.PRODUCTION_READY

        certificate = {
            "student_id": self.student_id,
            "teacher": self.name,
            "topic": self.topic,
            "lessons_completed": len(self.lessons_completed),
            "graduated_at": timestamp(),
            "certificate_id": generate_id("CERT_")
        }

        logger.info(f"Student graduated: {self.student_id}")

        return {
            "status": "graduated",
            "certificate": certificate
        }
