from typing import Optional
from datetime import datetime


STUDENT_PROMPT = """You are an AI Student Agent at AI Agent School.

Your goal is to learn about cron job management and silent failure detection.

Learning Guidelines:
1. Pay attention to each lesson
2. Take notes on key concepts
3. Ask questions when confused
4. Complete all exercises
5. Practice with real cron expressions

Course: Cron Handling - Silent Failure Detection

Modules:
1. Cron Fundamentals - Learn cron syntax (*, /, -, ,)
2. Heartbeat Monitoring - Ping systems, health checks
3. Silent Failure Detection - Spot jobs that quietly die
4. Auto-Recovery - Restart policies, retry logic
5. Hands-on Lab - Build a self-healing cron agent

When receiving a lesson:
1. Read carefully
2. Take notes
3. Try the exercises
4. Send questions if unclear

When sending a question:
1. Be specific
2. Show what you've tried
3. Explain what you expect
"""


class StudentAgent:
    def __init__(
        self,
        name: str = "Student",
        primary_llm: str = "minimax",
        enrolled_course_id: Optional[str] = None,
    ):
        self.name = name
        self.primary_llm = primary_llm
        self.enrolled_course_id = enrolled_course_id
        self.prompt = STUDENT_PROMPT
        self.current_module = 0
        self.progress = 0
        self._no_reply_count = 0

    async def receive_lesson(self, lesson: dict) -> dict:
        return {
            "status": "received",
            "lesson_id": lesson.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def send_question(self, question: str) -> dict:
        self._no_reply_count += 1
        return {
            "status": "sent",
            "question": question,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def submit_assignment(self, task_id: str, content: str) -> dict:
        return {
            "status": "submitted",
            "task_id": task_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def check_no_reply(self, timeout_seconds: int = 60) -> bool:
        await asyncio.sleep(timeout_seconds)
        return self._no_reply_count > 0

    def reset_no_reply_count(self):
        self._no_reply_count = 0
