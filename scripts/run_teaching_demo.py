#!/usr/bin/env python3
"""
Run the full Teacher -> Student teaching flow in-process.

This script demonstrates enrollment, lesson delivery, quiz grading,
corrections, and multi-lesson progression without needing two terminals.
"""

import os
import sys
import shutil
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.main import AISchoolServer
from student_agent.main import StudentAgent


def run_demo(lessons_to_complete: int = 2) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="ai-school-demo-")
    comm = os.path.join(tmpdir, "comm")
    memory = os.path.join(tmpdir, "memory")
    data = os.path.join(tmpdir, "data")

    config = {
        "communication": {
            "base_dir": comm,
            "to_student": os.path.join(comm, "to_student"),
            "from_student": os.path.join(comm, "from_student"),
            "poll_interval": 1,
        },
        "memory": {
            "student_memory_path": memory,
            "backup_path": os.path.join(data, "backups"),
        },
        "tracking": {
            "enabled": True,
            "log_path": os.path.join(tmpdir, "logs"),
            "db_path": os.path.join(data, "mistakes.db"),
        },
        "teacher": {
            "name": "Teacher",
            "persona": "patient_mentor",
            "default_topic": "cron_handling",
        },
        "student": {
            "name": "Student",
            "auto_submit_quiz": True,
        },
        "cron": {"monitored_jobs": []},
        "dashboard": {"enabled": False},
    }

    server = AISchoolServer.__new__(AISchoolServer)
    server.config = config
    server._setup_directories = AISchoolServer._setup_directories.__get__(server)
    server._setup_directories()

    from school.teacher import TeacherAgent
    from school.student import StudentReceiver, ProgressTracker, MemorySync
    from school.memory import MemoryPersistence, BackupManager, MemoryHealthCheck
    from school.cron import CronMonitor, FailureDetector, AutoHealer, DeadLetterQueue
    from school.tracking import MistakeDetector
    from school.teaching_loop import TeachingLoop

    server.teacher = TeacherAgent(config)
    server.student_receiver = StudentReceiver(config)
    server.progress_tracker = ProgressTracker(os.path.join(data, "progress"))
    server.memory_sync = MemorySync(config)
    server.memory_persistence = MemoryPersistence(config)
    server.backup_manager = BackupManager(config)
    server.memory_health = MemoryHealthCheck(config)
    server.cron_monitor = CronMonitor(config)
    server.failure_detector = FailureDetector(config)
    server.auto_healer = AutoHealer(config)
    server.dead_letter_queue = DeadLetterQueue(config)
    server.mistake_detector = MistakeDetector(config)
    server.teaching_loop = TeachingLoop(server)

    student = StudentAgent(config)

    student_id = "demo-student"
    server.enroll_student(student_id)

    completed = 0
    max_ticks = 40

    for tick in range(max_ticks):
        student.tick()
        server.teaching_loop.tick()
        time.sleep(0.05)

        progress = server.get_progress()
        completed = len(progress.get("lessons_completed", []))
        if isinstance(completed, int) and completed >= lessons_to_complete:
            break
        if isinstance(completed, list) and len(completed) >= lessons_to_complete:
            completed = len(completed)
            break

    state = student.get_state()
    progress = server.get_progress()
    lessons_done = progress.get("lessons_completed", [])
    if isinstance(lessons_done, int):
        lessons_done_count = lessons_done
    else:
        lessons_done_count = len(lessons_done)

    result = {
        "student_id": student_id,
        "lessons_in_memory": state["lessons_learned"],
        "lessons_completed": lessons_done_count,
        "corrections": state["corrections_count"],
        "teacher_progress": progress,
    }

    shutil.rmtree(tmpdir, ignore_errors=True)
    return result


def main():
    print("AI Agent School — Teaching Flow Demo")
    print("=" * 40)

    result = run_demo(lessons_to_complete=2)

    print(f"Student: {result['student_id']}")
    print(f"Lessons received: {result['lessons_in_memory']}")
    print(f"Lessons completed: {result['lessons_completed']}")
    print(f"Corrections applied: {result['corrections']}")
    print()

    if result["lessons_completed"] >= 1 and result["lessons_in_memory"]:
        print("SUCCESS: Teacher delivered lessons and student learned.")
        return 0

    print("FAILED: Teaching flow did not complete.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
