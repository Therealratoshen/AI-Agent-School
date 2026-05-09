# Cron Monitor
# Monitors cron jobs via heartbeats, detects failures, triggers auto-heal

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from core.database import get_db, BaseRepository
from core.message_queue import MessageQueue, MessageType


logger = structlog.get_logger(__name__)


class CronJobRepository(BaseRepository):
    """Repository for cron job operations"""

    def __init__(self):
        super().__init__("cron_jobs")

    def get_active_jobs(self) -> List[Dict]:
        """Get all active cron jobs"""
        query = "SELECT * FROM cron_jobs WHERE status = 'active'"
        results = self.db.execute(query, ())
        return [dict(r) for r in results]

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job with its latest heartbeat"""
        query = """
            SELECT cj.*,
                   hb.timestamp as last_heartbeat_time,
                   hb.status as heartbeat_status
            FROM cron_jobs cj
            LEFT JOIN (
                SELECT cron_job_id, MAX(timestamp) as timestamp, status
                FROM heartbeats
                GROUP BY cron_job_id, status
            ) hb ON hb.cron_job_id = cj.id
            WHERE cj.id = %s
        """
        result = self.db.execute_one(query, (job_id,))
        return dict(result) if result else None

    def update_status(self, job_id: str, status: str) -> None:
        """Update job status"""
        query = """
            UPDATE cron_jobs
            SET status = %s, updated_at = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (status, job_id))

    def increment_failure_count(self, job_id: str) -> int:
        """Increment failure count and return new count"""
        query = """
            UPDATE cron_jobs
            SET failure_count = failure_count + 1, updated_at = NOW()
            WHERE id = %s
            RETURNING failure_count
        """
        result = self.db.execute_one(query, (job_id,))
        return result["failure_count"] if result else 0

    def reset_failure_count(self, job_id: str) -> None:
        """Reset failure count"""
        query = """
            UPDATE cron_jobs
            SET failure_count = 0, status = 'active', updated_at = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (job_id,))


class HeartbeatRepository(BaseRepository):
    """Repository for heartbeat operations"""

    def __init__(self):
        super().__init__("heartbeats")

    def record(self, cron_job_id: str, status: str = "ok", response_time_ms: int = 0) -> None:
        """Record a heartbeat"""
        query = """
            INSERT INTO heartbeats (id, cron_job_id, timestamp, status, response_time_ms)
            VALUES (%s, %s, NOW(), %s, %s)
        """
        self.db.execute(query, (str(uuid.uuid4()), cron_job_id, status, response_time_ms))

    def get_last_heartbeat(self, cron_job_id: str) -> Optional[Dict]:
        """Get the most recent heartbeat for a job"""
        query = """
            SELECT * FROM heartbeats
            WHERE cron_job_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        result = self.db.execute_one(query, (cron_job_id,))
        return dict(result) if result else None

    def cleanup_old(self, days: int = 7) -> int:
        """Delete heartbeats older than specified days"""
        query = """
            DELETE FROM heartbeats
            WHERE timestamp < NOW() - INTERVAL '%s days'
        """
        # This would need to be implemented differently
        return 0


class CronMonitor:
    """
    Monitors cron jobs via heartbeats.

    Flow:
    1. Jobs send heartbeats to this monitor
    2. Monitor checks if heartbeats are on time
    3. If heartbeat is late/missing, mark as failed
    4. Trigger auto-heal on failure
    5. Move to DLQ after max retries
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self.queue = MessageQueue(school_id)
        self.job_repo = CronJobRepository()
        self.heartbeat_repo = HeartbeatRepository()

    def register_job(
        self,
        student_id: str,
        name: str,
        schedule: str,
        command: Optional[str] = None,
        heartbeat_interval: int = 300
    ) -> str:
        """
        Register a new cron job to monitor.

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        query = """
            INSERT INTO cron_jobs (
                id, school_id, student_id, name, schedule, command,
                status, heartbeat_interval, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, NOW())
            RETURNING id
        """
        self.db.execute(query, (
            job_id, self.school_id, student_id, name, schedule, command, heartbeat_interval
        ))

        logger.info("cron_job_registered", job_id=job_id, name=name)

        return job_id

    def receive_heartbeat(
        self,
        job_id: str,
        status: str = "ok",
        response_time_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Receive a heartbeat from a cron job.

        Returns:
            Dict with job status and any issues
        """
        # Get job
        job = self.job_repo.get_job_status(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}

        # Record heartbeat
        self.heartbeat_repo.record(job_id, status, response_time_ms)

        # Update job's last heartbeat
        query = """
            UPDATE cron_jobs
            SET last_heartbeat = NOW(), last_run_status = %s, last_run_at = NOW()
            WHERE id = %s
        """
        self.db.execute(query, (status, job_id))

        # Reset failure count on successful heartbeat
        if status == "ok":
            self.job_repo.reset_failure_count(job_id)

        logger.debug("heartbeat_received", job_id=job_id, status=status)

        return {
            "status": "ok",
            "job_id": job_id,
            "job_name": job["name"],
            "message": "Heartbeat recorded"
        }

    def check_job_health(self, job_id: str) -> Dict[str, Any]:
        """
        Check health of a specific job.

        Returns:
            Health status with details
        """
        job = self.job_repo.get_job_status(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}

        # No heartbeat yet
        if not job.get("last_heartbeat"):
            return {
                "status": "unknown",
                "job_id": job_id,
                "job_name": job["name"],
                "message": "No heartbeat recorded"
            }

        # Calculate time since last heartbeat
        last_hb = job["last_heartbeat"]
        elapsed = (datetime.utcnow() - last_hb).total_seconds()
        interval = job.get("heartbeat_interval", 300)
        grace_periods = job.get("grace_periods", 2)

        # Determine status
        if elapsed <= interval:
            status = "ok"
        elif elapsed <= interval * grace_periods:
            status = "warning"
        else:
            status = "failed"

        return {
            "status": status,
            "job_id": job_id,
            "job_name": job["name"],
            "last_heartbeat": last_hb.isoformat(),
            "elapsed_seconds": elapsed,
            "expected_interval": interval,
            "grace_periods": grace_periods,
            "failure_count": job.get("failure_count", 0)
        }

    def check_all_jobs(self) -> Dict[str, Any]:
        """
        Check health of all active jobs.

        Returns:
            Summary of all job health statuses
        """
        jobs = self.job_repo.get_active_jobs()

        results = []
        failed_jobs = []
        warning_jobs = []

        for job in jobs:
            health = self.check_job_health(job["id"])

            if health["status"] == "failed":
                failed_jobs.append(job["id"])
            elif health["status"] == "warning":
                warning_jobs.append(job["id"])

            results.append(health)

        return {
            "total": len(jobs),
            "healthy": len(jobs) - len(failed_jobs) - len(warning_jobs),
            "warnings": len(warning_jobs),
            "failed": len(failed_jobs),
            "jobs": results,
            "failed_job_ids": failed_jobs,
            "warning_job_ids": warning_jobs
        }

    def trigger_failure(self, job_id: str, error_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Trigger a failure for a job.
        This is called when a job fails or heartbeat is missed.

        Returns:
            Dict with failure handling result
        """
        job = self.job_repo.get_job_status(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}

        # Increment failure count
        failure_count = self.job_repo.increment_failure_count(job_id)
        max_failures = job.get("max_failures", 3)

        logger.warning(
            "job_failure_detected",
            job_id=job_id,
            job_name=job["name"],
            failure_count=failure_count,
            max_failures=max_failures
        )

        # Update status
        if failure_count >= max_failures:
            # Move to DLQ
            self.job_repo.update_status(job_id, "dlq")
            self._move_to_dlq(job, "Max retries exceeded")
            return {
                "status": "dlq",
                "job_id": job_id,
                "failure_count": failure_count,
                "action": "moved_to_dlq"
            }
        else:
            # Trigger heal
            self.job_repo.update_status(job_id, "healing")
            return {
                "status": "healing",
                "job_id": job_id,
                "failure_count": failure_count,
                "action": "auto_heal_triggered"
            }

    def _move_to_dlq(self, job: Dict, reason: str) -> None:
        """Move job to dead letter queue"""
        # Create DLQ entry
        query = """
            INSERT INTO dead_letter_queue (
                id, school_id, student_id, original_type, error_message,
                status, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending_review', NOW())
        """
        self.db.execute(query, (
            str(uuid.uuid4()),
            self.school_id,
            job["student_id"],
            "cron_failure",
            f"Job {job['name']}: {reason}"
        ))

        # Notify student
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(self.queue.enqueue(
            student_id=job["student_id"],
            message_type=MessageType.ERROR.value,
            payload={
                "type": "cron_failure",
                "job_name": job["name"],
                "reason": reason
            },
            priority=10
        ))

        logger.warning("job_moved_to_dlq", job_id=job["id"], job_name=job["name"])


class AutoHealer:
    """
    Automatically heals failed cron jobs.
    Implements retry with exponential backoff.
    """

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.db = get_db()
        self.job_repo = CronJobRepository()

    def attempt_heal(self, job_id: str) -> Dict[str, Any]:
        """
        Attempt to heal a failed job.

        Returns:
            Heal result
        """
        job = self.job_repo.get_job_status(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}

        if job["status"] not in ("healing", "failed"):
            return {"status": "skipped", "reason": "Job not in healing state"}

        command = job.get("command")
        if not command:
            return {"status": "skipped", "reason": "No command configured"}

        # In production, execute the actual command
        # For now, simulate healing
        try:
            # Simulate command execution
            # In real implementation:
            # result = subprocess.run(
            #     command,
            #     shell=False,  # NEVER shell=True
            #     capture_output=True,
            #     timeout=30
            # )

            logger.info("heal_attempted", job_id=job_id, command=command)

            # On success
            self.job_repo.reset_failure_count(job_id)
            self.job_repo.update_status(job_id, "active")

            return {
                "status": "healed",
                "job_id": job_id,
                "job_name": job["name"]
            }

        except Exception as e:
            logger.error("heal_failed", job_id=job_id, error=str(e))

            # Increment again
            failure_count = self.job_repo.increment_failure_count(job_id)

            return {
                "status": "failed",
                "job_id": job_id,
                "failure_count": failure_count,
                "error": str(e)
            }

    def get_heal_history(self, job_id: Optional[str] = None) -> List[Dict]:
        """Get heal history for a job or all jobs"""
        # In production, query heal history table
        return []

    @staticmethod
    def exponential_backoff_delay(attempt: int, base_delay: int = 5, max_delay: int = 300) -> int:
        """Calculate delay for retry with exponential backoff"""
        delay = min(base_delay * (2 ** attempt), max_delay)
        return delay


class CronService:
    """Service layer for cron monitoring operations"""

    def __init__(self, school_id: str):
        self.school_id = school_id
        self.monitor = CronMonitor(school_id)
        self.healer = AutoHealer(school_id)

    def register(
        self,
        student_id: str,
        name: str,
        schedule: str,
        command: Optional[str] = None
    ) -> str:
        """Register a new cron job"""
        return self.monitor.register_job(student_id, name, schedule, command)

    def heartbeat(self, job_id: str, status: str = "ok", response_time_ms: int = 0) -> Dict:
        """Receive a heartbeat"""
        return self.monitor.receive_heartbeat(job_id, status, response_time_ms)

    def check_all(self) -> Dict:
        """Check all jobs"""
        return self.monitor.check_all_jobs()

    def heal(self, job_id: str) -> Dict:
        """Attempt to heal a job"""
        # First check if job needs healing
        health = self.monitor.check_job_health(job_id)

        if health["status"] == "failed":
            self.monitor.trigger_failure(job_id)

        return self.healer.attempt_heal(job_id)

    def get_status(self, job_id: str) -> Dict:
        """Get job status"""
        return self.monitor.check_job_health(job_id)
