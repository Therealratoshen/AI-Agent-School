from typing import Optional
from datetime import datetime, timedelta
import asyncio


class NoReplyHandler:
    def __init__(
        self,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_delays: list[int] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delays = retry_delays or [30, 60, 120]

    async def wait_for_reply(self, task_id: str) -> bool:
        for attempt in range(self.max_retries):
            delay = self.retry_delays[attempt] if attempt < len(self.retry_delays) else self.retry_delays[-1]
            await asyncio.sleep(delay)
            if await self._check_for_reply(task_id):
                return True
        return False

    async def _check_for_reply(self, task_id: str) -> bool:
        raise NotImplementedError

    async def handle_no_reply(self, context: dict) -> dict:
        return {
            "status": "escalated",
            "reason": "no_reply",
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
        }


class SilentFailureDetector:
    def __init__(
        self,
        heartbeat_interval: int = 300,
        grace_periods: int = 2,
    ):
        self.heartbeat_interval = heartbeat_interval
        self.grace_periods = grace_periods

    def check_heartbeat(self, last_heartbeat: Optional[datetime], expected_interval: int) -> dict:
        if last_heartbeat is None:
            return {"status": "unknown", "message": "No heartbeat recorded"}

        now = datetime.utcnow()
        elapsed = (now - last_heartbeat).total_seconds()
        expected_next = expected_interval

        if elapsed <= expected_next:
            return {"status": "healthy", "elapsed": elapsed}

        missed_intervals = int(elapsed / expected_next)

        if missed_intervals >= self.grace_periods:
            return {
                "status": "failed",
                "elapsed": elapsed,
                "missed_intervals": missed_intervals,
                "message": "Silent failure detected - job may have crashed",
            }

        return {
            "status": "warning",
            "elapsed": elapsed,
            "missed_intervals": missed_intervals,
            "message": "Heartbeat missed - monitor closely",
        }

    def should_auto_restart(self, failure_count: int, max_retries: int = 3) -> bool:
        return failure_count < max_retries


class CronJobMonitor:
    def __init__(
        self,
        detector: SilentFailureDetector,
        no_reply_handler: NoReplyHandler,
    ):
        self.detector = detector
        self.no_reply_handler = no_reply_handler

    async def monitor_job(self, job_id: str, last_heartbeat: datetime) -> dict:
        result = self.detector.check_heartbeat(last_heartbeat, self.detector.heartbeat_interval)

        if result["status"] == "failed":
            escalation = await self.no_reply_handler.handle_no_reply({
                "job_id": job_id,
                "failure": result,
            })
            return {**result, "escalation": escalation}

        return result
