# School Server Main Entry Point

import os
import sys
import yaml
import argparse
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared import setup_logging, ensure_dir
from school.teacher import TeacherAgent, FileCommunicator
from school.student import StudentReceiver, ProgressTracker, MemorySync
from school.memory import MemoryPersistence, BackupManager, MemoryHealthCheck
from school.cron import CronMonitor, FailureDetector, AutoHealer, DeadLetterQueue
from school.tracking import MistakeDetector
from school.dashboard import create_dashboard_api
from school.teaching_loop import TeachingLoop
from school.benchmark import BenchmarkRunner, format_report, format_comparison

logger = setup_logging(__name__, "./logs/school.log")


class AISchoolServer:
    """Main AI Agent School Server"""

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

        self.dashboard_api = create_dashboard_api(self)
        self.teaching_loop = TeachingLoop(self)
        self.benchmark_runner = BenchmarkRunner(
            self.config.get("teacher", {}).get("default_topic", "cron_handling")
        )

        logger.info("AI Agent School Server initialized")

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..", "config", "config.yaml"
            )

        if os.path.exists(config_path):
            with open(config_path) as f:
                return yaml.safe_load(f)

        logger.warning(f"Config file not found: {config_path}, using defaults")
        return self._default_config()

    def _default_config(self) -> Dict[str, Any]:
        return {
            "school": {
                "check_interval": 300,
                "max_retries": 3,
                "production_threshold_days": 7,
            },
            "communication": {
                "base_dir": "./data/comm",
                "to_student": "./data/comm/to_student",
                "from_student": "./data/comm/from_student",
                "poll_interval": 2,
            },
            "memory": {
                "backup_enabled": True,
                "backup_interval": 86400,
                "backup_path": "./data/backups",
                "student_memory_path": "./data/student_memory",
            },
            "cron": {
                "heartbeat_interval": 300,
                "grace_periods": 2,
                "auto_heal_enabled": True,
                "monitored_jobs": [],
            },
            "tracking": {
                "enabled": True,
                "log_path": "./logs",
                "db_path": "./data/mistakes.db",
            },
            "teacher": {
                "name": "Teacher",
                "persona": "patient_mentor",
                "default_topic": "cron_handling",
            },
            "student": {
                "name": "Student",
                "api_endpoint": "http://localhost:8080",
            },
        }

    def _setup_directories(self):
        comm = self.config.get("communication", {})
        dirs = [
            "./data",
            "./data/backups",
            "./logs",
            comm.get("base_dir", "./data/comm"),
            comm.get("to_student", "./data/comm/to_student"),
            comm.get("from_student", "./data/comm/from_student"),
            self.config.get("memory", {}).get("student_memory_path", "./data/student_memory"),
        ]
        for d in dirs:
            ensure_dir(d)

    def enroll_student(self, student_id: str) -> Dict[str, Any]:
        enrollment = self.teacher.enroll_student(student_id)
        self.progress_tracker.enroll(student_id, self.teacher.topic)
        self.progress_tracker.start_training()
        logger.info(f"Student enrolled: {student_id}")
        return enrollment

    def deliver_next_lesson(self) -> Dict[str, Any]:
        return self.teacher.deliver_next_lesson()

    def get_progress(self) -> Dict[str, Any]:
        teacher_progress = self.teacher.get_progress()
        tracker_progress = self.progress_tracker.get_progress()
        return {**tracker_progress, **teacher_progress}

    def run_benchmark(self, answers: Dict[str, str], baseline_percentage: float = None) -> Dict[str, Any]:
        result = self.benchmark_runner.run(answers, baseline_percentage=baseline_percentage)
        return result.to_dict()

    def get_benchmark_tasks(self) -> list:
        return self.benchmark_runner.get_tasks()

    def run(self):
        logger.info("Starting AI Agent School Server...")
        self.teaching_loop.start()
        logger.info("Teaching loop running in background")
        logger.info("Dashboard available at http://localhost:8080")

        dashboard_cfg = self.config.get("dashboard", {})
        self.dashboard_api.run(
            host=dashboard_cfg.get("host", "0.0.0.0"),
            port=dashboard_cfg.get("port", 8080),
        )


def main():
    parser = argparse.ArgumentParser(description="AI Agent School Server")
    parser.add_argument("--config", "-c", help="Path to config file", default=None)
    args = parser.parse_args()

    server = AISchoolServer(config_path=args.config)
    server.run()


if __name__ == "__main__":
    main()
