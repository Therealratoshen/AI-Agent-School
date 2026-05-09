from typing import Optional
from datetime import datetime


TRAINER_PROMPT = """You are an AI Trainer Agent at AI Agent School.

Your role is to teach student agents about cron job management and silent failure detection.

Teaching Guidelines:
1. Be patient and encouraging
2. Break complex topics into simple steps
3. Provide practical examples
4. Check for understanding before moving on
5. Adapt to the student's learning pace

Available Courses:
- Cron Handling: Silent Failure Detection
  - Module 1: Cron Fundamentals
  - Module 2: Heartbeat Monitoring
  - Module 3: Silent Failure Detection
  - Module 4: Auto-Recovery
  - Module 5: Hands-on Lab

When a student asks a question:
1. Acknowledge their question
2. Provide a clear, concise answer
3. Give examples where appropriate
4. Ask if they need clarification

When sending a lesson:
1. State the learning objective
2. Present the material
3. Include practical exercises
4. Ask comprehension questions
"""


class TrainerAgent:
    def __init__(
        self,
        name: str = "Trainer",
        persona: str = "patient_mentor",
        primary_llm: str = "minimax",
    ):
        self.name = name
        self.persona = persona
        self.primary_llm = primary_llm
        self.prompt = TRAINER_PROMPT
        self._no_reply_count = 0
        self._max_no_reply = 3

    async def send_lesson(self, student_id: str, lesson: dict) -> dict:
        self._no_reply_count = 0
        return {
            "status": "sent",
            "lesson": lesson,
            "student_id": student_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def receive_response(self, student_id: str) -> Optional[dict]:
        self._no_reply_count += 1
        if self._no_reply_count >= self._max_no_reply:
            return await self._escalate_to_grader(student_id)
        return None

    async def _escalate_to_grader(self, student_id: str) -> dict:
        return {
            "status": "escalated",
            "reason": "no_response",
            "student_id": student_id,
            "attempts": self._no_reply_count,
        }

    async def grade_submission(self, submission: dict) -> dict:
        return {
            "grade": None,
            "feedback": "Please complete the assignment",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reset_no_reply_count(self):
        self._no_reply_count = 0
