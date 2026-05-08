# School Server Main Entry Point

import os
import sys
import yaml
import argparse
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(__file__))

from shared import setup_logging, ensure_dir
from school.teacher import TeacherAgent, FileCommunicator
from school.student import StudentReceiver, ProgressTracker, MemorySync
from school.memory import MemoryPersistence, BackupManager, MemoryHealthCheck
from school.cron import CronMonitor, FailureDetector, AutoHealer, DeadLetterQueue
from school.tracking import MistakeDetector
from school.dashboard import create_dashboard_api

logger = setup_logging(__name__, "./logs/school.log")

class AISchoolServer:
    """
    Main AI Agent School Server
    """

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self._setup_directories()

        self.teacher = TeacherAgent(self.config)
        self.student_receiver = StudentReceiver(self.config)
        self.progress_tracker = ProgressTracker("./data")
        self.memory_sync = MemorySync(self.config)
        self.memory_persistence = MemoryPersistence(self.config)
        self.backup_manager = BackupManager(self.config)
        self.memory_health = MemoryHealthCheck(self.config)
        self.cron_monitor = CronMonitor(self.config)
        self.failure_detector = FailureDetector(self.config)
        self.auto_healer = AutoHealer(self.config)
        self.dead_letter_queue = DeadLetterQueue(self.config)
        self.mistake_detector = MistakeDetector(self.config)

        self.dashboard_api = create_dashboard_api(self.config)

        logger.info("AI Agent School Server initialized")

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from file"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..", "config", "config.yaml"
            )

        if os.path.exists(config_path):
            with open(config_path) as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "school": {
                "check_interval": 300,
                "max_retries": 3,
                "production_threshold_days": 7
            },
            "communication": {
                "base_dir": "/shared/ai-school",
                "to_student": "/shared/ai-school/to_student",
                "from_student": "/shared/ai-school/from_student",
                "poll_interval": 5
            },
            "memory": {
                "backup_enabled": True,
                "backup_interval": 86400,
                "backup_path": "./data/backups",
                "student_memory_path": "/home/user/openclaw/memory"
            },
            "cron": {
                "heartbeat_interval": 300,
                "grace_periods": 2,
                "auto_heal_enabled": True,
                "monitored_jobs": []
            },
            "tracking": {
                "enabled": True,
                "log_path": "./logs",
                "db_path": "./data/mistakes.db"
            },
            "teacher": {
                "name": "Teacher",
                "persona": "patient_mentor",
                "default_topic": "cron_handling"
            },
            "student": {
                "name": "Student",
                "api_endpoint": "http://localhost:8081"
            }
        }

    def _setup_directories(self):
        """Create necessary directories"""
        dirs = [
            "./data",
            "./data/backups",
            "./logs",
            self.config.get("communication", {}).get("base_dir", "/shared/ai-school"),
        ]
        for d in dirs:
            ensure_dir(d)

    def enroll_student(self, student_id: str) -> Dict[str, Any]:
        """Enroll a new student"""
        enrollment = self.teacher.enroll_student(student_id)
        self.progress_tracker.enroll(student_id, self.teacher.topic)
        self.progress_tracker.start_training()

        logger.info(f"Student enrolled: {student_id}")

        return enrollment

    def deliver_next_lesson(self) -> Dict[str, Any]:
        """Deliver next lesson to student"""
        return self.teacher.deliver_next_lesson()

    def check_communication(self) -> None:
        """Check for messages from student"""
        messages = self.student_receiver.check_for_lessons()

        for message in messages:
            msg_type = message.get("type")

            if msg_type == "quiz_submission":
                self._handle_quiz_submission(message)
            elif msg_type == "status":
                self._handle_status_update(message)
            elif msg_type == "error":
                self._handle_error(message)

    def _handle_quiz_submission(self, message: Dict[str, Any]) -> None:
        """Handle quiz submission from student"""
        payload = message.get("payload", {})
        lesson_id = payload.get("lesson_id")
        answers = payload.get("answers", {})

        result = self.teacher.lesson_manager.grade_quiz(lesson_id, answers)

        if result["passed"]:
            self.progress_tracker.complete_lesson(lesson_id, result["score"])

        self.student_receiver.submit_quiz(lesson_id, answers)

    def _handle_status_update(self, message: Dict[str, Any]) -> None:
        """Handle status update"""
        payload = message.get("payload", {})
        logger.info(f"Status update: {payload.get('status')}")

    def _handle_error(self, message: Dict[str, Any]) -> None:
        """Handle error from student"""
        payload = message.get("payload", {})
        error = payload.get("error")

        self.mistake_detector.log_mistake(
            mistake=error,
            context=payload.get("context", {}),
            severity="high"
        )

        logger.error(f"Student error: {error}")

    def run_memory_check(self) -> None:
        """Run memory health check"""
        health = self.memory_health.check()

        if not health["healthy"]:
            issues = self.memory_health.get_issues()
            logger.warning(f"Memory issues detected: {issues}")

            if self.config.get("memory", {}).get("backup_enabled"):
                self.backup_manager.create_backup(
                    self.config.get("memory", {}).get("student_memory_path")
                )

    def run_cron_check(self) -> None:
        """Check cron job health"""
        status = self.cron_monitor.check_all_jobs()

        for job_name, job_status in status.get("jobs", {}).items():
            if job_status["status"] == "failed":
                job_config = self._get_job_config(job_name)
                self.auto_healer.attempt_heal(job_name, job_config)

    def _get_job_config(self, job_name: str) -> Dict[str, Any]:
        """Get job configuration"""
        jobs = self.config.get("cron", {}).get("monitored_jobs", [])
        for job in jobs:
            if job.get("name") == job_name:
                return job
        return {}

    def run(self):
        """Run the school server"""
        logger.info("Starting AI Agent School Server...")
        logger.info("Dashboard available at http://localhost:8080")

        self.dashboard_api.run(
            host="0.0.0.0",
            port=8080
        )

def main():
    parser = argparse.ArgumentParser(description="AI Agent School Server")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to config file",
        default=None
    )
    args = parser.parse_args()

    server = AISchoolServer(config_path=args.config)
    server.run()

if __name__ == "__main__":
    main()
