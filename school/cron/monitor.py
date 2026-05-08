# Cron Monitor - Monitor cron jobs via heartbeat

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from shared import (
    timestamp, generate_id, ensure_dir,
    setup_logging
)

logger = setup_logging(__name__, "./logs/cron_monitor.log")

class CronMonitor:
    """
    Monitor cron jobs via heartbeat signals
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        cron_config = config.get('cron', {})

        self.heartbeat_interval = cron_config.get('heartbeat_interval', 300)
        self.grace_periods = cron_config.get('grace_periods', 2)
        self.monitored_jobs = cron_config.get('monitored_jobs', [])

        self.heartbeat_file = "./data/heartbeats.json"
        ensure_dir(os.path.dirname(self.heartbeat_file))

        self._load_heartbeats()
        logger.info(f"CronMonitor initialized: {len(self.monitored_jobs)} jobs monitored")

    def _load_heartbeats(self):
        """Load heartbeat records"""
        import json
        if os.path.exists(self.heartbeat_file):
            try:
                with open(self.heartbeat_file) as f:
                    self.heartbeats = json.load(f)
            except Exception:
                self.heartbeats = {}
        else:
            self.heartbeats = {}

    def _save_heartbeats(self):
        """Save heartbeat records"""
        import json
        with open(self.heartbeat_file, 'w') as f:
            json.dump(self.heartbeats, f, indent=2)

    def record_heartbeat(self, job_name: str) -> Dict[str, Any]:
        """Record a heartbeat from a job"""
        self.heartbeats[job_name] = {
            "last_heartbeat": timestamp(),
            "status": "ok",
            "missed_count": 0
        }
        self._save_heartbeats()

        logger.debug(f"Heartbeat recorded: {job_name}")

        return {"status": "recorded", "job": job_name}

    def check_heartbeat(self, job_name: str) -> Dict[str, Any]:
        """Check if a job's heartbeat is healthy"""
        if job_name not in self.heartbeats:
            return {
                "status": "unknown",
                "job": job_name,
                "message": "No heartbeat recorded"
            }

        hb = self.heartbeats[job_name]
        last = datetime.fromisoformat(hb['last_heartbeat'])
        elapsed = (datetime.utcnow() - last).total_seconds()

        if elapsed <= self.heartbeat_interval:
            return {
                "status": "ok",
                "job": job_name,
                "elapsed_seconds": elapsed
            }
        elif elapsed <= self.heartbeat_interval * self.grace_periods:
            return {
                "status": "warning",
                "job": job_name,
                "elapsed_seconds": elapsed,
                "missed_intervals": int(elapsed / self.heartbeat_interval)
            }
        else:
            return {
                "status": "failed",
                "job": job_name,
                "elapsed_seconds": elapsed,
                "missed_intervals": int(elapsed / self.heartbeat_interval),
                "message": "Heartbeat missed - possible silent failure"
            }

    def check_all_jobs(self) -> Dict[str, Any]:
        """Check all monitored jobs"""
        results = {}
        for job in self.monitored_jobs:
            job_name = job['name']
            results[job_name] = self.check_heartbeat(job_name)

        return {
            "jobs": results,
            "total": len(self.monitored_jobs),
            "healthy": sum(1 for r in results.values() if r['status'] == 'ok'),
            "warnings": sum(1 for r in results.values() if r['status'] == 'warning'),
            "failed": sum(1 for r in results.values() if r['status'] == 'failed')
        }

    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """Get status for a specific job"""
        if job_name not in self.heartbeats:
            return {"status": "not_monitored", "job": job_name}

        return self.heartbeats[job_name]
