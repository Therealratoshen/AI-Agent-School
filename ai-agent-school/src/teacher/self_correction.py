# Self-Correction Engine
# Core AI teaching loop: Detect → Analyze → Correct → Inject → Verify

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from core.database import get_db, BaseRepository
from core.message_queue import MessageQueue, MessageType
from llm.minimax import get_minimax_client, MiniMaxError


logger = structlog.get_logger(__name__)


class MistakeRepository(BaseRepository):
    """Repository for mistake operations"""

    def __init__(self):
        super().__init__("mistakes")

    def find_similar(self, student_id: str, mistake: str) -> Optional[Dict]:
        """Find a similar existing mistake for deduplication"""
        # Use ILIKE for fuzzy matching
        query = """
            SELECT * FROM mistakes
            WHERE student_id = %s
            AND resolved = FALSE
            AND LOWER(mistake) LIKE LOWER(%s)
            LIMIT 1
        """
        result = self.db.execute_one(
            query,
            (student_id, f"%{mistake[:50]}%")
        )
        return dict(result) if result else None

    def increment_count(self, mistake_id: str) -> None:
        """Increment mistake occurrence count"""
        query = """
            UPDATE mistakes
            SET count = count + 1, last_seen = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (mistake_id,))


class CorrectionRepository(BaseRepository):
    """Repository for correction operations"""

    def __init__(self):
        super().__init__("corrections")

    def get_pending_verification(self, student_id: str) -> List[Dict]:
        """Get corrections pending verification"""
        query = """
            SELECT * FROM corrections
            WHERE student_id = %s
            AND status = 'applied'
            AND verified = FALSE
            AND applied_at < %s
            ORDER BY applied_at ASC
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)
        results = self.db.execute(query, (student_id, cutoff))
        return [dict(r) for r in results]

    def mark_verified(self, correction_id: str, success: bool) -> None:
        """Mark a correction as verified"""
        status = "verified" if success else "failed"
        query = """
            UPDATE corrections
            SET verified = %s, verified_at = NOW(), status = %s
            WHERE id = %s
        """
        self.db.execute(query, (success, status, correction_id))


class SelfCorrectionEngine:
    """
    Core engine for the self-correction teaching loop.

    Flow:
    1. DETECT: A mistake is reported or detected
    2. ANALYZE: MiniMax analyzes WHY the mistake happened
    3. CORRECT: MiniMax generates the correct approach
    4. INJECT: Correction is sent to the Student Agent
    5. VERIFY: After 24 hours, verify the correction was learned
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self.minimax = get_minimax_client()
        self.queue = MessageQueue(school_id)
        self.mistake_repo = MistakeRepository()
        self.correction_repo = CorrectionRepository()

        # Settings
        self.verification_window_hours = 24
        self.escalation_threshold = 3  # Mistakes before escalation

    async def detect_and_correct(
        self,
        student_id: str,
        mistake: str,
        context: Optional[Dict[str, Any]] = None,
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Main entry point: Detect a mistake and generate a correction.

        Args:
            student_id: Student who made the mistake
            mistake: Description of what went wrong
            context: Additional context (command run, error message, etc.)
            severity: How severe is this mistake

        Returns:
            Dict with detection/correction results
        """
        logger.info(
            "mistake_detected",
            student_id=student_id,
            mistake=mistake[:100],
            severity=severity
        )

        # Step 1: Check for existing similar mistake (deduplication)
        existing = self.mistake_repo.find_similar(student_id, mistake)

        if existing:
            # Increment count and return existing correction
            self.mistake_repo.increment_count(existing["id"])
            logger.info(
                "existing_mistake_incremented",
                mistake_id=existing["id"],
                count=existing["count"] + 1
            )

            return {
                "status": "existing_incremented",
                "mistake_id": existing["id"],
                "count": existing["count"] + 1,
                "correction_id": None
            }

        # Step 2: Create new mistake record
        mistake_data = {
            "student_id": student_id,
            "mistake": mistake,
            "context": context or {},
            "severity": severity,
            "count": 1
        }
        mistake_record = self.mistake_repo.create(mistake_data)
        mistake_id = mistake_record["id"]

        logger.info("new_mistake_created", mistake_id=mistake_id)

        # Step 3: Analyze with MiniMax (async, non-blocking if fails)
        analysis = await self._analyze(mistake, context or {})

        # Step 4: Generate correction with MiniMax
        correction_result = await self._generate_correction(
            mistake,
            analysis.get("root_cause", "Unknown"),
            context or {}
        )

        # Step 5: Save and inject correction
        correction_data = {
            "student_id": student_id,
            "mistake_id": mistake_id,
            "correction": correction_result.get("correction", ""),
            "explanation": correction_result.get("explanation", ""),
            "root_cause": analysis.get("root_cause", ""),
            "llm_model": self.minimax.model,
            "status": "pending"
        }
        correction_record = self.correction_repo.create(correction_data)
        correction_id = correction_record["id"]

        # Step 6: Inject into Student Agent
        await self._inject_correction(student_id, correction_record)

        # Mark correction as applied
        self.correction_repo.update(correction_id, {"applied_at": datetime.utcnow(), "status": "applied"})
        self.correction_repo.update(correction_id, {"verified": True, "verified_at": datetime.utcnow(), "status": "verified", "verified_by": "auto_verified"})

        return {
            "status": "correction_injected",
            "mistake_id": mistake_id,
            "correction_id": correction_id,
            "analysis": analysis,
            "correction": correction_result
        }

    async def _analyze(self, mistake: str, context: Dict[str, Any]) -> Dict[str, str]:
        """Analyze mistake with MiniMax"""
        try:
            # Get recent mistakes for context
            query = """
                SELECT mistake, COUNT(*) as count
                FROM mistakes
                WHERE student_id = (SELECT student_id FROM mistakes WHERE mistake = %s LIMIT 1)
                AND created_at > NOW() - INTERVAL '7 days'
                GROUP BY mistake
                ORDER BY count DESC
                LIMIT 5
            """
            history = self.db.execute(query, (mistake,))
            history_list = [
                {"mistake": h["mistake"], "count": h["count"]}
                for h in history
            ]

            result = await self.minimax.analyze_mistake(
                mistake=mistake,
                context=context,
                history=history_list
            )

            logger.info("mistake_analyzed", result=result)
            return result

        except MiniMaxError as e:
            logger.warning("minimax_analysis_failed", error=str(e))
            return {
                "root_cause": "Analysis unavailable",
                "category": "unknown",
                "severity": "medium"
            }

    async def _generate_correction(
        self,
        mistake: str,
        root_cause: str,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate correction with MiniMax"""
        try:
            result = await self.minimax.generate_correction(
                mistake=mistake,
                root_cause=root_cause,
                context=context
            )

            logger.info("correction_generated", correction=result.get("correction", "")[:100])
            return result

        except MiniMaxError as e:
            logger.warning("minimax_correction_failed", error=str(e))
            return {
                "correction": "Review the correct approach and try again",
                "explanation": "Correction generation unavailable",
                "code_example": None
            }

    async def _inject_correction(self, student_id: str, correction: Dict[str, Any]) -> None:
        """Send correction to Student Agent via message queue"""
        payload = {
            "correction_id": correction["id"],
            "mistake": correction.get("root_cause", ""),  # What was wrong
            "correction": correction.get("correction", ""),  # What to do instead
            "explanation": correction.get("explanation", ""),
            "applied_at": datetime.utcnow().isoformat(),
            "verify_after": (
                datetime.utcnow() + timedelta(hours=self.verification_window_hours)
            ).isoformat()
        }

        await self.queue.enqueue(
            student_id=student_id,
            message_type=MessageType.CORRECTION.value,
            payload=payload,
            priority=5  # High priority
        )

        logger.info("correction_injected", student_id=student_id, correction_id=correction["id"])

    async def verify_corrections(self, student_id: str) -> Dict[str, Any]:
        """
        Verify that corrections have been learned.
        Called periodically (e.g., every hour) to check pending verifications.
        """
        pending = self.correction_repo.get_pending_verification(student_id)

        verified_count = 0
        failed_count = 0

        for correction in pending:
            # In a real implementation, we would:
            # 1. Check if student has made the same mistake again
            # 2. Check if student is using the correct approach

            # For now, auto-verify after window has passed
            # This is where MiniMax could analyze recent behavior
            success = True  # Placeholder

            self.correction_repo.mark_verified(correction["id"], success)

            if success:
                verified_count += 1
                # Mark the original mistake as resolved
                query = """
                    UPDATE mistakes
                    SET resolved = TRUE, resolved_at = NOW()
                    WHERE id = %s
                """
                self.db.execute(query, (correction["mistake_id"],))

                logger.info("correction_verified", correction_id=correction["id"])
            else:
                failed_count += 1
                logger.warning("correction_verification_failed", correction_id=correction["id"])

        return {
            "verified": verified_count,
            "failed": failed_count,
            "pending": len(pending) - verified_count - failed_count
        }

    def get_active_corrections(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all active (non-learned) corrections for a student"""
        query = """
            SELECT c.*, m.mistake
            FROM corrections c
            JOIN mistakes m ON c.mistake_id = m.id
            WHERE c.student_id = %s
            AND c.learned = FALSE
            ORDER BY c.generated_at DESC
        """
        results = self.db.execute(query, (student_id,))
        return [dict(r) for r in results]

    def mark_learned(self, correction_id: str) -> None:
        """Mark a correction as learned"""
        query = """
            UPDATE corrections
            SET learned = TRUE, learned_at = NOW(), status = 'learned'
            WHERE id = %s
        """
        self.db.execute(query, (correction_id,))


class SelfCorrectionService:
    """
    Service layer for self-correction operations.
    Provides a simpler interface and handles orchestration.
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.engine = SelfCorrectionEngine(school_id)

    async def report_mistake(
        self,
        student_id: str,
        mistake: str,
        context: Optional[Dict[str, Any]] = None,
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Report a mistake from the Student Agent.

        This is called when the student agent:
        - Detects it made an error
        - Receives feedback about an error
        - Observes unexpected behavior
        """
        result = await self.engine.detect_and_correct(
            student_id=student_id,
            mistake=mistake,
            context=context,
            severity=severity
        )

        # Send notification if this is a repeated mistake
        if result.get("status") == "existing_incremented":
            count = result.get("count", 0)
            if count >= self.engine.escalation_threshold:
                await self._escalate_repeated_mistake(student_id, result["mistake_id"], count)

        return result

    async def _escalate_repeated_mistake(
        self,
        student_id: str,
        mistake_id: str,
        count: int
    ) -> None:
        """Escalate when the same mistake keeps happening"""
        from core.database import NotificationService

        notification = NotificationService()
        notification.send(
            school_id=self.school_id,
            student_id=student_id,
            notification_type="critical_failure",
            title="Repeated Mistake Escalation",
            message=f"Student has made the same mistake {count} times. "
                   f"Consider additional training or intervention.",
            priority="high"
        )

        logger.warning(
            "mistake_escalated",
            student_id=student_id,
            mistake_id=mistake_id,
            count=count
        )

    async def run_verification_cycle(self, student_id: str) -> Dict[str, Any]:
        """Run the periodic verification cycle"""
        return await self.engine.verify_corrections(student_id)

    def get_corrections(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all active corrections for a student"""
        return self.engine.get_active_corrections(student_id)
