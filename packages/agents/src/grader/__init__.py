from typing import Optional
from datetime import datetime


GRADER_PROMPT = """You are an AI Grader Agent at AI Agent School.

Your role is to evaluate student agent performance and provide feedback.

Evaluation Criteria:
1. Lesson comprehension
2. Assignment completion
3. Practical application
4. Code quality (for coding tasks)
5. Understanding of silent failure detection

Grading Scale:
- 90-100: Excellent - Exceeds expectations
- 80-89: Good - Meets all requirements
- 70-79: Satisfactory - Meets basic requirements
- 60-69: Needs Improvement - Missing some elements
- Below 60: Insufficient - Requires resubmission

When grading:
1. Review the submission carefully
2. Check against requirements
3. Provide specific feedback
4. Suggest improvements
5. Decide if resubmission needed

Escalation Handling:
When a trainer escalates due to no response:
1. Attempt to contact the student
2. Evaluate if student is still active
3. Report status to the system
"""


class GraderAgent:
    def __init__(
        self,
        name: str = "Grader",
        primary_llm: str = "minimax",
    ):
        self.name = name
        self.primary_llm = primary_llm
        self.prompt = GRADER_PROMPT

    async def grade_submission(self, submission: dict, criteria: dict) -> dict:
        content = submission.get("content", "")
        task_requirements = criteria.get("requirements", [])

        score = 70
        feedback_parts = []

        for req in task_requirements:
            if req.lower() in content.lower():
                feedback_parts.append(f"✓ Covers: {req}")
            else:
                feedback_parts.append(f"✗ Missing: {req}")
                score -= 10

        return {
            "grade": max(0, min(100, score)),
            "feedback": "\n".join(feedback_parts),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def evaluate_student_status(self, student_id: str, trainer_escalation: dict) -> dict:
        return {
            "student_id": student_id,
            "status": "unresponsive",
            "escalation_reason": trainer_escalation.get("reason"),
            "attempts": trainer_escalation.get("attempts", 0),
            "recommendation": "contact_owner" if trainer_escalation.get("attempts", 0) >= 3 else "retry",
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def check_course_completion(self, student_id: str, course_modules: list) -> dict:
        return {
            "student_id": student_id,
            "modules_completed": 0,
            "total_modules": len(course_modules),
            "completion_rate": 0.0,
            "eligible_for_certification": False,
        }
