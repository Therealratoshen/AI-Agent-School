# Graduation Monitor
# Tracks 7-day failure-free streak and handles automatic graduation

import json
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional

import structlog

from core.database import get_db
from core.message_queue import MessageQueue, MessageType
from core.config import get_settings
from llm.minimax import get_minimax_client


logger = structlog.get_logger(__name__)


class GraduationMonitor:
    """
    Monitors student progress and triggers graduation after 7 failure-free days.

    The 7-day streak works as follows:
    - Every 24 hours, the system checks for any failures in the last 24h
    - If there was a failure, the counter resets to 0
    - If no failures, the counter increments
    - When counter reaches 7, graduation is triggered
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self.queue = MessageQueue(school_id)
        self.settings = get_settings()
        self.graduation_streak_days = self.settings.app.graduation_streak_days

    def record_daily_status(self, student_id: str) -> Dict[str, Any]:
        """
        Record today's status for a student.
        Called once per day (e.g., at midnight).

        Returns:
            Dict with status of the day
        """
        today = date.today()

        # Check for failures today
        failures = self._get_today_failures(student_id, today)

        had_failure = len(failures) > 0

        # Get today's metrics
        lesson_completed = self._get_today_lesson_completion(student_id, today)
        mistake_count = self._get_today_mistakes(student_id, today)
        corrections_applied = self._get_today_corrections(student_id, today)

        # Insert or update daily status
        query = """
            INSERT INTO daily_status (
                student_id, date, had_failure, failure_types,
                lesson_completed, mistake_count, corrections_applied
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (student_id, date)
            DO UPDATE SET
                had_failure = EXCLUDED.had_failure,
                failure_types = EXCLUDED.failure_types,
                lesson_completed = EXCLUDED.lesson_completed,
                mistake_count = EXCLUDED.mistake_count,
                corrections_applied = EXCLUDED.corrections_applied
            RETURNING *
        """

        result = self.db.execute_one(
            query,
            (
                student_id,
                today,
                had_failure,
                json.dumps([f["type"] for f in failures]),
                lesson_completed,
                mistake_count,
                corrections_applied
            )
        )

        logger.info(
            "daily_status_recorded",
            student_id=student_id,
            date=str(today),
            had_failure=had_failure,
            mistake_count=mistake_count
        )

        return dict(result)

    def _get_today_failures(self, student_id: str, today: date) -> List[Dict]:
        """Get all failures for today"""
        query = """
            SELECT 'mistake' as type, id FROM mistakes
            WHERE student_id = %s AND DATE(last_seen) = %s
            UNION ALL
            SELECT 'cron_failure' as type, id FROM cron_jobs
            WHERE student_id = %s AND status = 'failed'
            AND updated_at >= %s
        """
        return self.db.execute(query, (student_id, today, student_id, today))

    def _get_today_lesson_completion(self, student_id: str, today: date) -> Optional[str]:
        """Get lesson completed today, if any"""
        query = """
            SELECT lesson_id FROM quiz_results
            WHERE student_id = %s AND DATE(submitted_at) = %s
            ORDER BY submitted_at DESC
            LIMIT 1
        """
        result = self.db.execute_one(query, (student_id, today))
        return result["lesson_id"] if result else None

    def _get_today_mistakes(self, student_id: str, today: date) -> int:
        """Count mistakes made today"""
        query = """
            SELECT COUNT(*) as count FROM mistakes
            WHERE student_id = %s AND DATE(last_seen) = %s
        """
        result = self.db.execute_scalar(query, (student_id, today))
        return result or 0

    def _get_today_corrections(self, student_id: str, today: date) -> int:
        """Count corrections applied today"""
        query = """
            SELECT COUNT(*) as count FROM corrections
            WHERE student_id = %s AND DATE(applied_at) = %s
        """
        result = self.db.execute_scalar(query, (student_id, today))
        return result or 0

    def update_failure_streak(self, student_id: str) -> Dict[str, Any]:
        """
        Update the failure streak for a student.
        This is the core graduation logic.

        Returns:
            Dict with streak info and graduation status
        """
        # Get consecutive failure-free days
        query = """
            WITH RECURSIVE streak AS (
                SELECT
                    id, student_id, date, had_failure,
                    1 as day_num
                FROM daily_status
                WHERE student_id = %s AND date = CURRENT_DATE

                UNION ALL

                SELECT
                    ds.id, ds.student_id, ds.date, ds.had_failure,
                    s.day_num + 1
                FROM daily_status ds
                JOIN streak s ON ds.student_id = s.student_id
                    AND ds.date = s.date - 1
                WHERE NOT ds.had_failure
            )
            SELECT MAX(day_num) as streak_days
            FROM streak
        """
        result = self.db.execute_scalar(query, (student_id,))
        streak_days = result or 0

        # Update student's failure_streak
        update_query = """
            UPDATE students
            SET failure_streak = %s,
                last_failure_at = CASE
                    WHEN failure_streak > %s THEN last_failure_at
                    ELSE NULL
                END
            WHERE id = %s
            RETURNING failure_streak
        """
        self.db.execute(update_query, (streak_days, streak_days, student_id))

        logger.info(
            "failure_streak_updated",
            student_id=student_id,
            streak_days=streak_days
        )

        # Check for graduation
        graduated = False
        if streak_days >= self.graduation_streak_days:
            graduated = self._trigger_graduation(student_id)

        return {
            "student_id": student_id,
            "streak_days": streak_days,
            "days_remaining": max(0, self.graduation_streak_days - streak_days),
            "graduated": graduated
        }

    def _trigger_graduation(self, student_id: str) -> bool:
        """
        Trigger graduation for a student.
        This is the automatic handover moment.

        Returns:
            True if graduation was successful
        """
        logger.info("graduation_triggered", student_id=student_id)

        # Get student info
        student = self.db.execute_one(
            "SELECT * FROM students WHERE id = %s",
            (student_id,)
        )

        if not student:
            logger.error("graduation_failed_student_not_found", student_id=student_id)
            return False

        if student["status"] == "graduated":
            logger.info("student_already_graduated", student_id=student_id)
            return False

        # Get training statistics
        query = """
            SELECT
                COUNT(DISTINCT date) as training_days,
                COUNT(*) as total_mistakes,
                SUM(CASE WHEN learned THEN 1 ELSE 0 END) as corrections_learned
            FROM mistakes m
            LEFT JOIN corrections c ON c.mistake_id = m.id
            WHERE m.student_id = %s
        """
        stats = self.db.execute_one(query, (student_id,))

        # Get lessons completed
        lessons_completed = self.db.execute_scalar(
            "SELECT COUNT(*) FROM quiz_results WHERE student_id = %s",
            (student_id,)
        ) or 0

        # Generate certificate
        certificate_id = f"CERT-{student_id[:8]}-{datetime.utcnow().strftime('%Y%m%d')}"

        # Update student status
        update_query = """
            UPDATE students
            SET status = 'graduated',
                graduated_at = NOW()
            WHERE id = %s
        """
        self.db.execute(update_query, (student_id,))

        # Create graduation record
        grad_query = """
            INSERT INTO graduations (
                student_id, certificate_id, failure_streak_at_graduation,
                lessons_completed, total_corrections, total_training_days,
                certificate_data, graduated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        self.db.execute(grad_query, (
            student_id,
            certificate_id,
            student["failure_streak"],
            lessons_completed,
            stats["corrections_learned"] or 0,
            stats["training_days"] or 0,
            json.dumps({
                "student_name": student["name"],
                "graduated_at": datetime.utcnow().isoformat(),
                "streak_days": student["failure_streak"]
            })
        ))

        # Send graduation message to student
        graduation_payload = {
            "certificate_id": certificate_id,
            "student_name": student["name"],
            "graduated_at": datetime.utcnow().isoformat(),
            "failure_streak": student["failure_streak"],
            "lessons_completed": lessons_completed,
            "corrections_learned": stats["corrections_learned"] or 0,
            "message": "Congratulations! You are now production ready."
        }

        # Run graduation sync - synchronous for now
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.queue.enqueue(
            student_id=student_id,
            message_type=MessageType.GRADUATION.value,
            payload=graduation_payload,
            priority=10  # Highest priority
        ))

        logger.info(
            "graduation_complete",
            student_id=student_id,
            certificate_id=certificate_id
        )

        return True

    def get_graduation_status(self, student_id: str) -> Dict[str, Any]:
        """
        Get current graduation status for a student.

        Returns:
            Dict with graduation progress
        """
        student = self.db.execute_one(
            "SELECT * FROM students WHERE id = %s",
            (student_id,)
        )

        if not student:
            return {"error": "Student not found"}

        # Get recent daily status
        query = """
            SELECT date, had_failure, mistake_count
            FROM daily_status
            WHERE student_id = %s
            ORDER BY date DESC
            LIMIT 7
        """
        recent = self.db.execute(query, (student_id,))

        return {
            "student_id": student_id,
            "status": student["status"],
            "failure_streak": student["failure_streak"],
            "days_remaining": max(0, self.graduation_streak_days - student["failure_streak"]),
            "graduated": student["status"] == "graduated",
            "graduated_at": student["graduated_at"],
            "recent_days": [dict(r) for r in recent]
        }

    def run_daily_check(self, student_id: str) -> Dict[str, Any]:
        """
        Run the daily graduation check.
        This should be called once per day (e.g., via cron).

        Returns:
            Dict with check results
        """
        # Record today's status
        status = self.record_daily_status(student_id)

        # Update failure streak
        streak = self.update_failure_streak(student_id)

        return {
            "student_id": student_id,
            "date": str(date.today()),
            "had_failure": status.get("had_failure", False),
            "failure_streak": streak["streak_days"],
            "graduated": streak["graduated"],
            "days_remaining": streak["days_remaining"]
        }


class GraduationService:
    """Service layer for graduation operations"""

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.monitor = GraduationMonitor(school_id)

    def check_student(self, student_id: str) -> Dict[str, Any]:
        """Check graduation status for a student"""
        return self.monitor.get_graduation_status(student_id)

    def run_all_daily_checks(self) -> List[Dict[str, Any]]:
        """Run daily checks for all active students"""
        query = """
            SELECT id FROM students
            WHERE status IN ('enrolled', 'training')
        """
        students = self.db.execute(query, ())
        # Fix: ensure db is properly initialized
        from core.database import get_db
        db = get_db()
        students = db.execute(query, ())

        results = []
        for student in students:
            result = self.monitor.run_daily_check(student["id"])
            results.append(result)

        return results

    def get_all_graduation_status(self) -> List[Dict[str, Any]]:
        """Get graduation status for all students"""
        query = "SELECT id, name, status, failure_streak FROM students"
        db = get_db()
        students = db.execute(query, ())

        status_list = []
        for student in students:
            status = self.monitor.get_graduation_status(student["id"])
            status_list.append(status)

        return status_list
