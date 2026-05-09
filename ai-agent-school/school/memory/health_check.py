# Memory Health Check

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any
from shared import setup_logging

logger = setup_logging(__name__, "./logs/health_check.log")

class MemoryHealthCheck:
    """
    Check memory health and detect issues
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        memory_config = config.get('memory', {})
        self.memory_path = memory_config.get('student_memory_path', '/home/user/openclaw/memory')

    def check(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {
            "path_exists": self._check_path_exists(),
            "readable": self._check_readable(),
            "writable": self._check_writable(),
            "has_corrections": self._check_corrections(),
            "has_lessons": self._check_lessons(),
        }

        all_passed = all(results.values())
        score = sum(results.values()) / len(results) * 100 if all_passed else 0

        return {
            "healthy": all_passed,
            "score": score,
            "checks": results
        }

    def _check_path_exists(self) -> bool:
        """Check if memory path exists"""
        return os.path.exists(self.memory_path)

    def _check_readable(self) -> bool:
        """Check if memory path is readable"""
        try:
            if not os.path.exists(self.memory_path):
                return False
            os.listdir(self.memory_path)
            return True
        except Exception:
            return False

    def _check_writable(self) -> bool:
        """Check if memory path is writable"""
        try:
            test_file = os.path.join(self.memory_path, ".health_check_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception:
            return False

    def _check_corrections(self) -> bool:
        """Check if corrections file exists"""
        corrections_file = os.path.join(self.memory_path, "corrections.json")
        return os.path.exists(corrections_file)

    def _check_lessons(self) -> bool:
        """Check if lessons file exists"""
        lessons_file = os.path.join(self.memory_path, "lessons.json")
        return os.path.exists(lessons_file)

    def get_issues(self) -> list:
        """Get list of issues found"""
        issues = []
        health = self.check()

        if not health["checks"]["path_exists"]:
            issues.append("Memory path does not exist")
        if not health["checks"]["readable"]:
            issues.append("Memory path is not readable")
        if not health["checks"]["writable"]:
            issues.append("Memory path is not writable")
        if not health["checks"]["has_corrections"]:
            issues.append("No corrections file found")
        if not health["checks"]["has_lessons"]:
            issues.append("No lessons file found")

        return issues
