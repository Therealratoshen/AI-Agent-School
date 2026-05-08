# Mistake Detector - Detect and track mistakes

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime
from shared import (
    timestamp, generate_id, ensure_dir, setup_logging
)

logger = setup_logging(__name__, "./logs/mistake_detector.log")

class MistakeDetector:
    """
    Detect and track mistakes made by the student agent
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        tracking_config = config.get('tracking', {})

        self.log_path = tracking_config.get('log_path', './logs')
        self.repetition_threshold = 3

        ensure_dir(self.log_path)
        self.mistakes_file = os.path.join(self.log_path, "mistakes.json")
        self._load_mistakes()

        logger.info("MistakeDetector initialized")

    def _load_mistakes(self):
        """Load mistakes from file"""
        if os.path.exists(self.mistakes_file):
            try:
                import json
                with open(self.mistakes_file) as f:
                    self.mistakes = json.load(f)
            except Exception:
                self.mistakes = []
        else:
            self.mistakes = []

    def _save_mistakes(self):
        """Save mistakes to file"""
        import json
        ensure_dir(os.path.dirname(self.mistakes_file))
        with open(self.mistakes_file, 'w') as f:
            json.dump(self.mistakes, f, indent=2)

    def log_mistake(self, mistake: str, context: str = "",
                    correct_answer: str = "", severity: str = "medium") -> Dict[str, Any]:
        """Log a new mistake"""
        existing = self._find_mistake(mistake)

        if existing:
            existing['count'] += 1
            existing['last_seen'] = timestamp()

            if existing['count'] >= self.repetition_threshold:
                existing['escalated'] = True
                logger.warning(f"Mistake escalated: {mistake}, count: {existing['count']}")

            self._save_mistakes()

            return {
                "status": "updated",
                "mistake_id": existing['id'],
                "count": existing['count'],
                "escalated": existing.get('escalated', False)
            }

        entry = {
            "id": generate_id("mist_"),
            "mistake": mistake,
            "correct_answer": correct_answer,
            "context": context,
            "severity": severity,
            "count": 1,
            "first_seen": timestamp(),
            "last_seen": timestamp(),
            "escalated": False,
            "learned": False
        }

        self.mistakes.append(entry)
        self._save_mistakes()

        logger.info(f"Mistake logged: {mistake}")

        return {
            "status": "logged",
            "mistake_id": entry['id'],
            "count": 1,
            "escalated": False
        }

    def _find_mistake(self, mistake: str) -> Optional[Dict]:
        """Find existing mistake by content"""
        for m in self.mistakes:
            if m.get('mistake', '').lower() == mistake.lower():
                return m
        return None

    def get_mistakes(self, filter_type: str = "all") -> List[Dict[str, Any]]:
        """Get mistakes, optionally filtered"""
        if filter_type == "escalated":
            return [m for m in self.mistakes if m.get('escalated') and not m.get('learned')]
        elif filter_type == "learned":
            return [m for m in self.mistakes if m.get('learned')]
        elif filter_type == "active":
            return [m for m in self.mistakes if not m.get('learned')]
        return self.mistakes

    def mark_learned(self, mistake_id: str) -> Dict[str, Any]:
        """Mark a mistake as learned"""
        for m in self.mistakes:
            if m.get('id') == mistake_id:
                m['learned'] = True
                m['learned_at'] = timestamp()
                self._save_mistakes()

                logger.info(f"Mistake marked as learned: {mistake_id}")

                return {"status": "marked", "mistake_id": mistake_id}

        return {"status": "error", "message": "Mistake not found"}

    def get_escalated(self) -> List[Dict[str, Any]]:
        """Get escalated mistakes that need attention"""
        return [m for m in self.mistakes if m.get('escalated') and not m.get('learned')]

    def get_statistics(self) -> Dict[str, Any]:
        """Get mistake statistics"""
        total = len(self.mistakes)
        learned = len([m for m in self.mistakes if m.get('learned')])
        escalated = len([m for m in self.mistakes if m.get('escalated')])

        return {
            "total": total,
            "learned": learned,
            "active": total - learned,
            "escalated": escalated,
            "resolution_rate": (learned / total * 100) if total > 0 else 0
        }

    def clear_old(self, days: int = 30) -> Dict[str, Any]:
        """Clear mistakes older than specified days"""
        cutoff = datetime.fromisoformat(timestamp()) - datetime.timedelta(days=days)
        original_count = len(self.mistakes)

        self.mistakes = [
            m for m in self.mistakes
            if datetime.fromisoformat(m.get('first_seen', timestamp())) > cutoff
        ]

        removed = original_count - len(self.mistakes)
        self._save_mistakes()

        logger.info(f"Cleared {removed} old mistakes")

        return {"removed": removed, "remaining": len(self.mistakes)}
