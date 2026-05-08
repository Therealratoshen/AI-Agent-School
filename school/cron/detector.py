# Failure Detector - Detect cron job failures

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from shared import (
    timestamp, generate_id, setup_logging
)

logger = setup_logging(__name__, "./logs/failure_detector.log")

class FailureDetector:
    """
    Detect failures in cron jobs
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        cron_config = config.get('cron', {})

        self.heartbeat_interval = cron_config.get('heartbeat_interval', 300)
        self.grace_periods = cron_config.get('grace_periods', 2)

        self.failure_log_file = "./data/failures.json"
        self._load_failures()

        logger.info("FailureDetector initialized")

    def _load_failures(self):
        """Load failure records"""
        if os.path.exists(self.failure_log_file):
            try:
                import json
                with open(self.failure_log_file) as f:
                    self.failures = json.load(f)
            except Exception:
                self.failures = []
        else:
            self.failures = []

    def _save_failures(self):
        """Save failure records"""
        import json
        os.makedirs(os.path.dirname(self.failure_log_file), exist_ok=True)
        with open(self.failure_log_file, 'w') as f:
            json.dump(self.failures, f, indent=2)

    def detect_failure(self, job_name: str, last_heartbeat: str,
                       current_time: str = None) -> Optional[Dict[str, Any]]:
        """Detect if a job has failed"""
        if current_time is None:
            current_time = timestamp()

        last = datetime.fromisoformat(last_heartbeat)
        current = datetime.fromisoformat(current_time)
        elapsed = (current - last).total_seconds()

        missed_intervals = int(elapsed / self.heartbeat_interval)

        if missed_intervals >= self.grace_periods:
            failure = {
                "id": generate_id("fail_"),
                "job_name": job_name,
                "detected_at": current_time,
                "last_heartbeat": last_heartbeat,
                "elapsed_seconds": elapsed,
                "missed_intervals": missed_intervals,
                "severity": self._get_severity(missed_intervals),
                "status": "detected"
            }

            self.failures.append(failure)
            self._save_failures()

            logger.warning(f"Failure detected: {job_name}, missed {missed_intervals} intervals")

            return failure

        return None

    def _get_severity(self, missed_intervals: int) -> str:
        """Determine severity based on missed intervals"""
        if missed_intervals >= 4:
            return "critical"
        elif missed_intervals >= 3:
            return "high"
        elif missed_intervals >= 2:
            return "medium"
        return "low"

    def get_active_failures(self) -> List[Dict[str, Any]]:
        """Get all active (not resolved) failures"""
        return [f for f in self.failures if f.get('status') != 'resolved']

    def resolve_failure(self, failure_id: str, resolution: str = "") -> Dict[str, Any]:
        """Mark a failure as resolved"""
        for failure in self.failures:
            if failure.get('id') == failure_id:
                failure['status'] = 'resolved'
                failure['resolved_at'] = timestamp()
                failure['resolution'] = resolution
                self._save_failures()

                logger.info(f"Failure resolved: {failure_id}")

                return {"status": "resolved", "failure_id": failure_id}

        return {"status": "error", "message": "Failure not found"}

    def get_failure_history(self, job_name: str = None) -> List[Dict[str, Any]]:
        """Get failure history, optionally filtered by job"""
        if job_name:
            return [f for f in self.failures if f.get('job_name') == job_name]
        return self.failures
