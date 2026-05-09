# Teacher Agent
# AI Teacher that delivers lessons, grades quizzes, and manages student training

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from core.database import get_db, BaseRepository
from core.message_queue import MessageQueue, MessageType
from llm.minimax import get_minimax_client, MiniMaxError
from teacher.self_correction import SelfCorrectionService
from teacher.graduation import GraduationService


logger = structlog.get_logger(__name__)


class LessonRepository(BaseRepository):
    """Repository for lesson operations"""

    def __init__(self):
        super().__init__("lessons")

    def get_by_topic(self, school_id: str, topic: str) -> List[Dict]:
        """Get all lessons for a topic, ordered by module number"""
        query = """
            SELECT * FROM lessons
            WHERE school_id = %s AND topic = %s
            ORDER BY module_number ASC
        """
        results = self.db.execute(query, (school_id, topic))
        return [dict(r) for r in results]

    def get_quizzes(self, lesson_id: str) -> List[Dict]:
        """Get all quizzes for a lesson"""
        query = "SELECT * FROM quizzes WHERE lesson_id = %s"
        results = self.db.execute(query, (lesson_id,))
        return [dict(r) for r in results]


class QuizResultRepository(BaseRepository):
    """Repository for quiz results"""

    def __init__(self):
        super().__init__("quiz_results")


class TeacherAgent:
    """
    AI Teacher Agent that:
    - Enrolls students
    - Delivers lessons
    - Grades quizzes with LLM feedback
    - Triggers corrections for mistakes
    - Manages graduation
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self.queue = MessageQueue(school_id)
        self.minimax = get_minimax_client()
        self.self_correction = SelfCorrectionService(school_id)
        self.graduation = GraduationService(school_id)
        self.lesson_repo = LessonRepository()
        self.quiz_repo = QuizResultRepository()

    def enroll_student(self, name: str, topic: str = "cron_handling") -> Dict[str, Any]:
        """
        Enroll a new student.

        Args:
            name: Student name/identifier
            topic: Course topic (default: cron_handling)

        Returns:
            Enrollment result with student info
        """
        # Create student record
        student_data = {
            "school_id": self.school_id,
            "name": name,
            "status": "enrolled",
            "current_lesson": 0
        }

        student = self._create_student(student_data)
        student_id = student["id"]

        logger.info("student_enrolled", student_id=student_id, name=name)

        # Get first lesson
        lessons = self.lesson_repo.get_by_topic(self.school_id, topic)
        if lessons:
            first_lesson = lessons[0]
            # Send first lesson
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self._deliver_lesson(student_id, first_lesson))

        # Update status to training
        self.db.execute(
            "UPDATE students SET status = 'training' WHERE id = %s",
            (student_id,)
        )

        return {
            "status": "enrolled",
            "student_id": student_id,
            "name": name,
            "topic": topic,
            "first_lesson": lessons[0] if lessons else None,
            "total_lessons": len(lessons)
        }

    def _create_student(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new student record"""
        student_id = str(uuid.uuid4())
        query = """
            INSERT INTO students (id, school_id, name, status, enrolled_at)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING *
        """
        result = self.db.execute_one(
            query,
            (student_id, data["school_id"], data["name"], data["status"])
        )
        return dict(result)

    async def _deliver_lesson(self, student_id: str, lesson: Dict[str, Any]) -> None:
        """Deliver a lesson to a student"""
        # Get quizzes for this lesson
        quizzes = self.lesson_repo.get_quizzes(lesson["id"])

        payload = {
            "lesson_id": lesson["id"],
            "title": lesson["title"],
            "content": lesson["content"],
            "module_number": lesson["module_number"],
            "estimated_minutes": lesson["estimated_minutes"],
            "quiz_count": len(quizzes)
        }

        await self.queue.enqueue(
            student_id=student_id,
            message_type=MessageType.LESSON.value,
            payload=payload,
            priority=5
        )

        logger.info("lesson_delivered", student_id=student_id, lesson_id=lesson["id"])

    def deliver_next_lesson(self, student_id: str) -> Dict[str, Any]:
        """
        Deliver the next lesson in sequence.

        Returns:
            Result with next lesson info
        """
        # Get student's current lesson
        student = self.db.execute_one(
            "SELECT * FROM students WHERE id = %s",
            (student_id,)
        )
        if not student:
            return {"status": "error", "message": "Student not found"}

        # Get all lessons for topic
        topic = "cron_handling"  # Default topic
        lessons = self.lesson_repo.get_by_topic(self.school_id, topic)

        # Find next lesson
        current = student.get("current_lesson", 0)
        next_lesson = None
        for lesson in lessons:
            if lesson["module_number"] > current:
                next_lesson = lesson
                break

        if not next_lesson:
            return {
                "status": "completed",
                "message": "All lessons completed",
                "student_id": student_id
            }

        # Update current lesson
        self.db.execute(
            "UPDATE students SET current_lesson = %s WHERE id = %s",
            (next_lesson["module_number"], student_id)
        )

        # Deliver lesson
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self._deliver_lesson(student_id, next_lesson))

        return {
            "status": "delivered",
            "lesson": next_lesson,
            "student_id": student_id
        }

    async def grade_quiz(
        self,
        student_id: str,
        lesson_id: str,
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Grade a quiz submission and provide LLM-generated feedback.

        Args:
            student_id: Student who submitted
            lesson_id: Lesson being tested
            answers: Dict of question_id -> answer

        Returns:
            Grading result with score and feedback
        """
        # Get quizzes for this lesson
        quizzes = self.lesson_repo.get_quizzes(lesson_id)

        if not quizzes:
            return {"status": "error", "message": "No quiz found for lesson"}

        # Grade each answer
        correct_count = 0
        total_count = len(quizzes)
        feedback_items = []

        for quiz in quizzes:
            question_id = quiz["question_id"]
            student_answer = answers.get(question_id, "").strip()
            correct_answer = quiz["correct_answer"]

            is_correct = student_answer.lower() == correct_answer.lower()

            if is_correct:
                correct_count += 1
            else:
                # Generate LLM feedback for incorrect answer
                try:
                    feedback = await self.minimax.generate_quiz_feedback(
                        lesson_id=lesson_id,
                        question=quiz["question"],
                        student_answer=student_answer,
                        correct_answer=correct_answer,
                        is_correct=False
                    )
                except MiniMaxError:
                    feedback = f"The correct answer is: {correct_answer}"

                feedback_items.append({
                    "question_id": question_id,
                    "question": quiz["question"],
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "is_correct": False,
                    "feedback": feedback
                })

                # Report mistake
                await self.self_correction.report_mistake(
                    student_id=student_id,
                    mistake=f"Wrong answer to: {quiz['question']}",
                    context={
                        "lesson_id": lesson_id,
                        "question_id": question_id,
                        "student_answer": student_answer,
                        "correct_answer": correct_answer
                    },
                    severity="medium"
                )

        # Calculate score
        score = (correct_count / total_count * 100) if total_count > 0 else 0
        passed = score >= 70

        # Save quiz result
        quiz_result = {
            "student_id": student_id,
            "lesson_id": lesson_id,
            "score": score,
            "correct_count": correct_count,
            "total_count": total_count,
            "answers": json.dumps(answers),
            "llm_generated": True,
            "llm_model": self.minimax.model
        }
        self.quiz_repo.create(quiz_result)

        # Send result to student
        result_payload = {
            "lesson_id": lesson_id,
            "score": score,
            "passed": passed,
            "correct_count": correct_count,
            "total_count": total_count,
            "feedback": feedback_items if feedback_items else None,
            "next_lesson": None if passed else None
        }

        if passed:
            # Get next lesson for next_lesson
            next_result = self.deliver_next_lesson(student_id)
            if next_result.get("status") == "delivered":
                result_payload["next_lesson"] = next_result["lesson"]

        await self.queue.enqueue(
            student_id=student_id,
            message_type=MessageType.QUIZ.value,
            payload=result_payload,
            priority=5
        )

        logger.info(
            "quiz_graded",
            student_id=student_id,
            lesson_id=lesson_id,
            score=score,
            passed=passed
        )

        return {
            "status": "graded",
            "score": score,
            "passed": passed,
            "correct_count": correct_count,
            "total_count": total_count
        }

    def get_student_progress(self, student_id: str) -> Dict[str, Any]:
        """Get student progress"""
        student = self.db.execute_one(
            "SELECT * FROM students WHERE id = %s",
            (student_id,)
        )
        if not student:
            return {"error": "Student not found"}

        # Get quiz results
        query = """
            SELECT qr.*, l.title as lesson_title
            FROM quiz_results qr
            JOIN lessons l ON qr.lesson_id = l.id
            WHERE qr.student_id = %s
            ORDER BY qr.submitted_at DESC
        """
        quiz_results = self.db.execute(query, (student_id,))

        # Get graduation status
        grad_status = self.graduation.get_graduation_status(student_id)

        return {
            "student_id": student_id,
            "name": student["name"],
            "status": student["status"],
            "current_lesson": student["current_lesson"],
            "enrolled_at": student["enrolled_at"],
            "graduated_at": student["graduated_at"],
            "quiz_results": [dict(r) for r in quiz_results],
            "graduation": grad_status
        }

    def get_all_students(self) -> List[Dict[str, Any]]:
        """Get all students"""
        query = "SELECT id, name, status, current_lesson, enrolled_at FROM students"
        results = self.db.execute(query, ())
        return [dict(r) for r in results]


class TeacherService:
    """High-level service for teacher operations"""

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.agent = TeacherAgent(school_id)

    def enroll(self, name: str, topic: str = "cron_handling") -> Dict[str, Any]:
        """Enroll a new student"""
        return self.agent.enroll_student(name, topic)

    def deliver_next(self, student_id: str) -> Dict[str, Any]:
        """Deliver next lesson"""
        return self.agent.deliver_next_lesson(student_id)

    async def submit_quiz(
        self,
        student_id: str,
        lesson_id: str,
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Submit quiz for grading"""
        return await self.agent.grade_quiz(student_id, lesson_id, answers)

    def get_progress(self, student_id: str) -> Dict[str, Any]:
        """Get student progress"""
        return self.agent.get_student_progress(student_id)

    def get_all_students(self) -> List[Dict[str, Any]]:
        """Get all students"""
        return self.agent.get_all_students()

    def get_graduation_status(self, student_id: str) -> Dict[str, Any]:
        """Get graduation status"""
        return self.graduation.get_graduation_status(student_id)
