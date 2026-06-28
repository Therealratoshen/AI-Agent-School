# Integration test: Teacher teaches Student end-to-end

import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.teacher import TeacherAgent
from school.student.receiver import StudentReceiver
from school.student.progress import ProgressTracker
from school.teaching_loop import TeachingLoop
from student_agent.main import StudentAgent


@pytest.fixture
def teaching_env():
    tmpdir = tempfile.mkdtemp(prefix="ai-school-test-")
    comm = os.path.join(tmpdir, "comm")
    to_student = os.path.join(comm, "to_student")
    from_student = os.path.join(comm, "from_student")
    memory = os.path.join(tmpdir, "memory")

    config = {
        "communication": {
            "base_dir": comm,
            "to_student": to_student,
            "from_student": from_student,
            "poll_interval": 1,
        },
        "memory": {"student_memory_path": memory},
        "tracking": {
            "log_path": os.path.join(tmpdir, "logs"),
            "db_path": os.path.join(tmpdir, "mistakes.db"),
        },
        "teacher": {
            "name": "TestTeacher",
            "default_topic": "cron_handling",
        },
        "student": {"auto_submit_quiz": True},
        "cron": {"monitored_jobs": []},
    }

    for path in (to_student, from_student, memory):
        os.makedirs(path, exist_ok=True)

    class ServerStub:
        def __init__(self):
            self.config = config
            self.teacher = TeacherAgent(config)
            self.student_receiver = StudentReceiver(config)
            self.progress_tracker = ProgressTracker(os.path.join(tmpdir, "data"))
            self.mistake_detector = __import__(
                "school.tracking.detector", fromlist=["MistakeDetector"]
            ).MistakeDetector(config)

    server = ServerStub()
    server.teaching_loop = TeachingLoop(server)
    student = StudentAgent(config)

    yield server, student, tmpdir


def test_enrollment_delivers_first_lesson(teaching_env):
    server, student, _ = teaching_env
    server.teacher.enroll_student("student-1")

    messages = student.check_for_messages()
    assert len(messages) == 1
    assert messages[0]["type"] == "lesson"

    student.process_message(messages[0])
    assert student.current_lesson is not None
    assert student.current_lesson["id"] == "cron_01"


def test_full_teaching_loop_passes_quiz(teaching_env):
    server, student, _ = teaching_env
    server.teacher.enroll_student("student-1")

    for _ in range(20):
        student.tick()
        server.teaching_loop.tick()
        time.sleep(0.02)

    state = student.get_state()
    progress = server.teacher.get_progress()

    assert "cron_01" in state["lessons_learned"]
    assert "cron_01" in progress["lessons_completed"]
    assert progress["progress_percent"] >= 20


def test_wrong_answer_triggers_correction(teaching_env):
    server, student, _ = teaching_env
    student.auto_submit_quiz = False
    server.teacher.enroll_student("student-1")

    student.tick()
    lesson = student.current_lesson
    assert lesson is not None

    student.submit_quiz(lesson["id"], {"q1": "wrong answer", "q2": "wrong", "q3": "wrong"})
    server.teaching_loop.tick()
    student.tick()

    corrections = student.get_corrections()
    assert len(corrections) >= 1

    prompt_file = os.path.join(student.memory_path, "system_prompt_additions.txt")
    assert os.path.exists(prompt_file)
    assert len(open(prompt_file).read()) > 0


def test_lesson_manager_has_five_lessons():
    from school.teacher.lessons import LessonManager

    manager = LessonManager("cron_handling")
    assert manager.total_lessons() == 5
    assert manager.get_lesson(1).id == "cron_01"
