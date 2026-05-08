# Memory Persistence - Ensure corrections and lessons persist

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, Optional
from shared import (
    timestamp, generate_id, ensure_dir,
    read_json, write_json, setup_logging
)

logger = setup_logging(__name__, "./logs/memory.log")

class MemoryPersistence:
    """
    Ensure memory persists between sessions
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        memory_config = config.get('memory', {})
        self.backup_enabled = memory_config.get('backup_enabled', True)
        self.backup_interval = memory_config.get('backup_interval', 86400)
        self.backup_path = memory_config.get('backup_path', './data/backups')
        self.verify_writes = memory_config.get('verify_writes', True)
        self.student_memory_path = memory_config.get('student_memory_path', '/home/user/openclaw/memory')

        ensure_dir(self.backup_path)
        logger.info(f"MemoryPersistence initialized: backup_enabled={self.backup_enabled}")

    def save_correction(self, mistake: str, correct_answer: str,
                        explanation: str = "") -> Dict[str, Any]:
        """Save a correction to persistent memory"""
        corrections_file = os.path.join(self.student_memory_path, "corrections.json")

        corrections = read_json(corrections_file, [])

        correction = {
            "id": generate_id("corr_"),
            "mistake": mistake,
            "correct": correct_answer,
            "explanation": explanation,
            "saved_at": timestamp(),
            "learned": False
        }

        corrections.append(correction)

        if self.verify_writes:
            write_json(corrections_file, corrections)
            if not self._verify_write(corrections_file, correction):
                return {"status": "error", "message": "Write verification failed"}
        else:
            write_json(corrections_file, corrections)

        logger.info(f"Correction saved: {correction['id']}")

        return {
            "status": "saved",
            "correction_id": correction['id'],
            "total_corrections": len(corrections)
        }

    def _verify_write(self, filepath: str, expected: Dict) -> bool:
        """Verify write succeeded"""
        try:
            data = read_json(filepath, [])
            return any(c.get('id') == expected['id'] for c in data)
        except Exception:
            return False

    def load_corrections(self) -> list:
        """Load all saved corrections"""
        corrections_file = os.path.join(self.student_memory_path, "corrections.json")
        return read_json(corrections_file, [])

    def mark_learned(self, correction_id: str) -> Dict[str, Any]:
        """Mark a correction as learned"""
        corrections_file = os.path.join(self.student_memory_path, "corrections.json")
        corrections = read_json(corrections_file, [])

        for corr in corrections:
            if corr.get('id') == correction_id:
                corr['learned'] = True
                corr['learned_at'] = timestamp()
                write_json(corrections_file, corrections)
                logger.info(f"Correction marked as learned: {correction_id}")
                return {"status": "marked", "correction_id": correction_id}

        return {"status": "error", "message": "Correction not found"}

    def save_lesson(self, lesson_id: str, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save lesson content to memory"""
        lessons_file = os.path.join(self.student_memory_path, "lessons.json")

        lessons = read_json(lessons_file, {})

        lessons[lesson_id] = {
            **lesson_data,
            "saved_at": timestamp()
        }

        write_json(lessons_file, lessons)

        logger.info(f"Lesson saved: {lesson_id}")

        return {"status": "saved", "lesson_id": lesson_id}

    def load_lessons(self) -> Dict[str, Any]:
        """Load all saved lessons"""
        lessons_file = os.path.join(self.student_memory_path, "lessons.json")
        return read_json(lessons_file, {})

    def check_health(self) -> Dict[str, Any]:
        """Check memory health"""
        if not os.path.exists(self.student_memory_path):
            return {
                "healthy": False,
                "error": "Memory path does not exist",
                "score": 0
            }

        try:
            files = os.listdir(self.student_memory_path)
            corrections = self.load_corrections()

            score = min(100, 50 + (len(corrections) * 5))

            return {
                "healthy": True,
                "score": score,
                "files": len(files),
                "corrections_count": len(corrections),
                "path": self.student_memory_path
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "score": 0
            }

    def recover(self) -> Dict[str, Any]:
        """Attempt to recover from corruption"""
        logger.warning("Attempting memory recovery...")

        backup_dir = os.path.join(self.backup_path, "auto_backup")
        ensure_dir(backup_dir)

        try:
            if os.path.exists(self.student_memory_path):
                import shutil
                bad_backup = os.path.join(backup_dir, f"corrupted_{timestamp().replace(':', '-')}")
                shutil.move(self.student_memory_path, bad_backup)

            ensure_dir(self.student_memory_path)

            logger.info("Recovery complete")

            return {
                "status": "recovered",
                "old_path": bad_backup if 'bad_backup' in dir() else None
            }
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            return {"status": "error", "message": str(e)}
