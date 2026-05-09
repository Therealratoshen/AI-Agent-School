# Progress Tracker - Track student learning progress

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime
from shared import (
    timestamp, generate_id, ensure_dir,
    read_json, write_json, setup_logging
)
import json

logger = setup_logging(__name__, "./logs/progress.log")

class ProgressTracker:
    """
    Track student progress through lessons
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        self.progress_file = os.path.join(data_dir, "progress.json")
        self._ensure_data_dir()
        self._load_progress()

    def _ensure_data_dir(self):
        """Create data directory if needed"""
        ensure_dir(self.data_dir)

    def _load_progress(self):
        """Load progress from file"""
        self.progress = read_json(self.progress_file, {
            "student_id": None,
            "enrolled_at": None,
            "lessons_completed": [],
            "current_lesson": 1,
            "quiz_results": {},
            "corrections_received": [],
            "status": "not_started",
            "last_activity": None
        })

    def _save_progress(self):
        """Save progress to file"""
        self.progress['last_activity'] = timestamp()
        write_json(self.progress_file, self.progress)

    def enroll(self, student_id: str, topic: str) -> Dict[str, Any]:
        """Record student enrollment"""
        self.progress = {
            "student_id": student_id,
            "topic": topic,
            "enrolled_at": timestamp(),
            "lessons_completed": [],
            "current_lesson": 1,
            "quiz_results": {},
            "corrections_received": [],
            "status": "enrolled",
            "last_activity": timestamp()
        }
        self._save_progress()

        logger.info(f"Student enrolled: {student_id}")

        return {"status": "enrolled", "student_id": student_id}

    def start_training(self) -> None:
        """Mark training as started"""
        self.progress['status'] = 'training'
        self._save_progress()

    def complete_lesson(self, lesson_id: str, quiz_score: float) -> Dict[str, Any]:
        """Record lesson completion"""
        if lesson_id not in self.progress['lessons_completed']:
            self.progress['lessons_completed'].append(lesson_id)

        self.progress['quiz_results'][lesson_id] = {
            "score": quiz_score,
            "completed_at": timestamp()
        }

        self.progress['current_lesson'] += 1
        self._save_progress()

        logger.info(f"Lesson completed: {lesson_id}, score: {quiz_score}")

        return {
            "status": "completed",
            "lesson_id": lesson_id,
            "score": quiz_score,
            "total_completed": len(self.progress['lessons_completed'])
        }

    def add_correction(self, correction: Dict[str, Any]) -> None:
        """Record a correction received"""
        self.progress['corrections_received'].append({
            **correction,
            "received_at": timestamp()
        })
        self._save_progress()

        logger.info(f"Correction recorded: {correction.get('id')}")

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress"""
        return {
            "student_id": self.progress.get('student_id'),
            "status": self.progress.get('status'),
            "lessons_completed": len(self.progress.get('lessons_completed', [])),
            "current_lesson": self.progress.get('current_lesson'),
            "quiz_results": self.progress.get('quiz_results', {}),
            "corrections_count": len(self.progress.get('corrections_received', [])),
            "enrolled_at": self.progress.get('enrolled_at'),
            "last_activity": self.progress.get('last_activity')
        }

    def get_percent_complete(self, total_lessons: int) -> float:
        """Get percentage of lessons completed"""
        if total_lessons == 0:
            return 0
        return len(self.progress.get('lessons_completed', [])) / total_lessons * 100

    def is_ready_for_graduation(self, total_lessons: int, min_score: float = 70) -> bool:
        """Check if student is ready to graduate"""
        if len(self.progress.get('lessons_completed', [])) < total_lessons:
            return False

        for result in self.progress.get('quiz_results', {}).values():
            if result.get('score', 0) < min_score:
                return False

        return True
