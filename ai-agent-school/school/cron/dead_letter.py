# Dead Letter Queue - Handle unrecoverable jobs

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List
from shared import (
    timestamp, generate_id, setup_logging
)

logger = setup_logging(__name__, "./logs/dead_letter.log")

class DeadLetterQueue:
    """
    Queue for jobs that failed beyond recovery
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dlq_file = "./data/dead_letter_queue.json"
        self._load_dlq()

        logger.info("DeadLetterQueue initialized")

    def _load_dlq(self):
        """Load DLQ from file"""
        if os.path.exists(self.dlq_file):
            try:
                import json
                with open(self.dlq_file) as f:
                    self.queue = json.load(f)
            except Exception:
                self.queue = []
        else:
            self.queue = []

    def _save_dlq(self):
        """Save DLQ to file"""
        import json
        os.makedirs(os.path.dirname(self.dlq_file), exist_ok=True)
        with open(self.dlq_file, 'w') as f:
            json.dump(self.queue, f, indent=2)

    def add(self, job_name: str, reason: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Add a job to the DLQ"""
        entry = {
            "id": generate_id("dlq_"),
            "job_name": job_name,
            "reason": reason,
            "context": context or {},
            "added_at": timestamp(),
            "status": "pending_review",
            "reviewed": False
        }

        self.queue.append(entry)
        self._save_dlq()

        logger.warning(f"Job added to DLQ: {job_name}, reason: {reason}")

        return {"status": "added", "dlq_id": entry['id']}

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending DLQ entries"""
        return [e for e in self.queue if not e.get('reviewed')]

    def mark_reviewed(self, dlq_id: str, action: str) -> Dict[str, Any]:
        """Mark a DLQ entry as reviewed"""
        for entry in self.queue:
            if entry.get('id') == dlq_id:
                entry['reviewed'] = True
                entry['review_action'] = action
                entry['reviewed_at'] = timestamp()
                self._save_dlq()

                logger.info(f"DLQ entry reviewed: {dlq_id}, action: {action}")

                return {"status": "reviewed", "dlq_id": dlq_id}

        return {"status": "error", "message": "Entry not found"}

    def retry(self, dlq_id: str) -> Dict[str, Any]:
        """Retry a job from DLQ"""
        for entry in self.queue:
            if entry.get('id') == dlq_id:
                entry['retry_count'] = entry.get('retry_count', 0) + 1
                entry['last_retry_at'] = timestamp()
                self._save_dlq()

                logger.info(f"DLQ entry retry scheduled: {dlq_id}")

                return {
                    "status": "retry_scheduled",
                    "dlq_id": dlq_id,
                    "retry_count": entry['retry_count']
                }

        return {"status": "error", "message": "Entry not found"}

    def remove(self, dlq_id: str) -> Dict[str, Any]:
        """Remove entry from DLQ"""
        original_len = len(self.queue)
        self.queue = [e for e in self.queue if e.get('id') != dlq_id]

        if len(self.queue) < original_len:
            self._save_dlq()
            logger.info(f"DLQ entry removed: {dlq_id}")
            return {"status": "removed", "dlq_id": dlq_id}

        return {"status": "error", "message": "Entry not found"}

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all DLQ entries"""
        return self.queue

    def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics"""
        pending = len(self.get_pending())
        reviewed = len([e for e in self.queue if e.get('reviewed')])

        return {
            "total": len(self.queue),
            "pending_review": pending,
            "reviewed": reviewed
        }
