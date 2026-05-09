# Auto-Healer - Automatically heal failed cron jobs

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List
from shared import (
    timestamp, generate_id, setup_logging
)

logger = setup_logging(__name__, "./logs/healer.log")

class AutoHealer:
    """
    Automatically heal failed cron jobs
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        cron_config = config.get('cron', {})

        self.auto_heal_enabled = cron_config.get('auto_heal_enabled', True)
        self.max_retries = 3

        self.heal_log_file = "./data/heals.json"
        self._load_heal_log()

        logger.info(f"AutoHealer initialized: enabled={self.auto_heal_enabled}")

    def _load_heal_log(self):
        """Load heal history"""
        if os.path.exists(self.heal_log_file):
            try:
                import json
                with open(self.heal_log_file) as f:
                    self.heal_history = json.load(f)
            except Exception:
                self.heal_history = []
        else:
            self.heal_history = []

    def _save_heal_log(self):
        """Save heal history"""
        import json
        os.makedirs(os.path.dirname(self.heal_log_file), exist_ok=True)
        with open(self.heal_log_file, 'w') as f:
            json.dump(self.heal_history, f, indent=2)

    def attempt_heal(self, job_name: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to heal a failed job"""
        if not self.auto_heal_enabled:
            return {"status": "disabled", "job": job_name}

        retry_count = self._get_retry_count(job_name)

        if retry_count >= self.max_retries:
            logger.warning(f"Max retries exceeded for {job_name}, moving to DLQ")
            return {
                "status": "max_retries_exceeded",
                "job": job_name,
                "retries": retry_count,
                "action": "dlq"
            }

        heal_result = self._execute_heal(job_name, job_config)

        self._record_heal_attempt(job_name, heal_result)

        if heal_result.get('success'):
            logger.info(f"Successfully healed: {job_name}")
            return {
                "status": "healed",
                "job": job_name,
                "method": heal_result.get('method'),
                "retries": retry_count + 1
            }
        else:
            logger.error(f"Heal failed for {job_name}: {heal_result.get('error')}")
            return {
                "status": "failed",
                "job": job_name,
                "error": heal_result.get('error'),
                "retries": retry_count + 1
            }

    def _execute_heal(self, job_name: str, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute heal command"""
        command = job_config.get('command')

        if not command:
            return {"success": False, "error": "No command configured"}

        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "method": "command_execution",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_retry_count(self, job_name: str) -> int:
        """Get number of heal attempts for job"""
        count = 0
        for attempt in reversed(self.heal_history):
            if attempt.get('job_name') == job_name and attempt.get('status') == 'healed':
                break
            if attempt.get('job_name') == job_name:
                count += 1
        return count

    def _record_heal_attempt(self, job_name: str, result: Dict[str, Any]):
        """Record a heal attempt"""
        self.heal_history.append({
            "id": generate_id("heal_"),
            "job_name": job_name,
            "attempted_at": timestamp(),
            "status": "healed" if result.get('success') else "failed",
            "method": result.get('method'),
            "error": result.get('error')
        })
        self._save_heal_log()

    def get_heal_history(self, job_name: str = None) -> List[Dict[str, Any]]:
        """Get heal history"""
        if job_name:
            return [h for h in self.heal_history if h.get('job_name') == job_name]
        return self.heal_history

    def exponential_backoff_delay(self, attempt: int) -> int:
        """Calculate delay for retry with exponential backoff"""
        base_delay = 5
        return min(base_delay * (2 ** attempt), 300)
