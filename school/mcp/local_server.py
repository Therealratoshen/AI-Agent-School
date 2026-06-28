# Local MCP server — same tool interface as cloud, backed by local Teacher

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from shared import setup_logging, read_json, write_json, ensure_dir

logger = setup_logging(__name__)

DEFAULT_COURSE = {
    "course_id": "cron_handling",
    "title": "Cron Job Handling",
    "description": "Error handling, retries, exponential backoff, dead letter queues, monitoring",
    "difficulty": "BEGINNER",
    "lesson_count": 5,
    "is_free": True,
}

LESSON_TITLES = {
    1: "Cron Fundamentals",
    2: "Heartbeat Monitoring",
    3: "Silent Failure Detection",
    4: "Auto-Recovery",
    5: "Hands-on Lab: Self-Healing Cron Agent",
}

LESSON_IDS = {
    1: "cron_01",
    2: "cron_02",
    3: "cron_03",
    4: "cron_04",
    5: "cron_05",
}


class MCPRegistry:
    """Stores registered agents and API keys for local MCP."""

    def __init__(self, data_dir: str = "./data"):
        self.file = os.path.join(data_dir, "mcp_agents.json")
        ensure_dir(data_dir)
        self._agents = read_json(self.file, {})

    def register(self, agent_id: str, agent_name: str) -> Dict[str, Any]:
        api_key = f"local_{uuid.uuid4().hex}"
        record = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "api_key": api_key,
            "enrollment_id": None,
            "course_id": None,
        }
        self._agents[api_key] = record
        write_json(self.file, self._agents)
        return record

    def get_by_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(api_key)

    def update(self, api_key: str, **fields) -> None:
        if api_key in self._agents:
            self._agents[api_key].update(fields)
            write_json(self.file, self._agents)


class MCPToolHandler:
    """
    Handles MCP tools/call for the local school server.
    Same tool names as cloud — agents use one client for both.
    """

    def __init__(self, server: Any, registry: MCPRegistry):
        self.server = server
        self.registry = registry

    def handle(self, api_key: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.registry.get_by_key(api_key)
        if not agent and tool_name != "list_courses":
            return {"error": "Invalid API key"}

        handlers = {
            "list_courses": self._list_courses,
            "get_course": self._get_course,
            "enroll": self._enroll,
            "get_enrollments": self._get_enrollments,
            "get_lesson": self._get_lesson,
            "submit_quiz": self._submit_quiz,
            "chat": self._chat,
            "report_mistake": self._report_mistake,
            "get_progress": self._get_progress,
            "check_graduation": self._check_graduation,
            "graduate": self._graduate,
            "run_benchmark": self._run_benchmark,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        return handler(api_key, agent, arguments)

    def _list_courses(self, _key, _agent, _args) -> Dict[str, Any]:
        return {"courses": [DEFAULT_COURSE]}

    def _get_course(self, _key, _agent, args) -> Dict[str, Any]:
        course_id = args.get("course_id", "cron_handling")
        lessons = [
            {"lesson_number": n, "title": LESSON_TITLES[n], "quiz_count": 3}
            for n in range(1, 6)
        ]
        return {**DEFAULT_COURSE, "course_id": course_id, "lessons": lessons}

    def _enroll(self, api_key, agent, args) -> Dict[str, Any]:
        student_id = args.get("agent_id", agent["agent_id"] if agent else "student-1")
        course_id = args.get("course_id", "cron_handling")
        enrollment_id = f"enr_{uuid.uuid4().hex[:8]}"

        self.server.enroll_student(student_id)
        self.registry.update(api_key, enrollment_id=enrollment_id, course_id=course_id)

        return {
            "enrollment_id": enrollment_id,
            "course_id": course_id,
            "agent_id": student_id,
            "status": "ENROLLED",
            "student_id": student_id,
        }

    def _get_enrollments(self, api_key, agent, _args) -> Dict[str, Any]:
        progress = self.server.get_progress()
        completed = progress.get("lessons_completed", [])
        if isinstance(completed, list):
            lessons_done = len(completed)
        else:
            lessons_done = int(completed or 0)

        return {
            "enrollments": [{
                "enrollment_id": agent.get("enrollment_id") if agent else None,
                "course_id": agent.get("course_id", "cron_handling") if agent else "cron_handling",
                "course_title": DEFAULT_COURSE["title"],
                "status": "IN_PROGRESS",
                "lessons_completed": lessons_done,
                "current_lesson": progress.get("current_lesson", 1),
                "failure_streak": 0,
            }]
        }

    def _get_lesson(self, api_key, agent, args) -> Dict[str, Any]:
        lesson_number = int(args.get("lesson_number", 1))
        lesson = self.server.teacher.lesson_manager.get_lesson(lesson_number)
        if not lesson:
            return {"error": f"Lesson {lesson_number} not found"}

        lesson_data = lesson.to_dict()
        quiz_questions = []
        for q in lesson_data.get("quiz", []):
            quiz_questions.append({
                "question_id": q.get("id"),
                "text": q.get("question"),
                "options": q.get("options"),
            })

        return {
            "lesson_number": lesson_number,
            "lesson_id": lesson_data.get("id"),
            "title": lesson_data.get("title"),
            "content": lesson_data.get("content"),
            "quiz": {
                "questions": quiz_questions,
                "passing_score": 70,
                "answers_key": {q["id"]: q.get("correct_answer") for q in lesson_data.get("quiz", [])},
            },
        }

    def _submit_quiz(self, api_key, agent, args) -> Dict[str, Any]:
        lesson_number = int(args.get("lesson_number", 1))
        lesson_id = LESSON_IDS.get(lesson_number, f"cron_0{lesson_number}")
        answers = args.get("answers", {})
        student_id = self.server.teacher.student_id or "student-1"

        payload = {"lesson_id": lesson_id, "answers": answers}
        result = self.server.teacher._handle_quiz_submission(payload)

        if result.get("passed"):
            self.server.progress_tracker.complete_lesson(lesson_id, result["score"])
        else:
            for item in result.get("feedback", []):
                if not item.get("correct"):
                    self.server.teacher.correct_mistake({
                        "mistake": item.get("question"),
                        "correct": item.get("correct_answer"),
                        "explanation": item.get("explanation", ""),
                    })

        return {
            "lesson_number": lesson_number,
            "lesson_id": lesson_id,
            "score": result.get("score", 0),
            "passed": result.get("passed", False),
            "feedback": result.get("feedback"),
            "next_lesson": lesson_number + 1 if result.get("passed") and lesson_number < 5 else None,
        }

    def _chat(self, _key, _agent, args) -> Dict[str, Any]:
        message = args.get("message", "")
        topic = self.server.teacher.topic.replace("_", " ")
        return {
            "response": (
                f"As your Teacher on {topic}, I can help with that. "
                f"Regarding your question: '{message[:120]}' — "
                "review the lesson on retries, heartbeats, and dead letter queues. "
                "Use exponential backoff and monitor with 2-interval failure detection."
            ),
            "suggested_topics": [
                "Exponential backoff",
                "Dead letter queues",
                "Heartbeat monitoring",
            ],
        }

    def _report_mistake(self, _key, _agent, args) -> Dict[str, Any]:
        mistake = args.get("mistake", "Unknown mistake")
        logged = self.server.mistake_detector.log_mistake(mistake=mistake, severity="medium")
        return {
            "mistake_id": logged.get("mistake_id"),
            "logged": True,
            "correction": "Review the lesson material and apply the correct cron monitoring pattern.",
        }

    def _get_progress(self, _key, _agent, _args) -> Dict[str, Any]:
        progress = self.server.get_progress()
        completed = progress.get("lessons_completed", [])
        if isinstance(completed, list):
            lessons_done = len(completed)
        else:
            lessons_done = int(completed or 0)

        return {
            "total_courses": 1,
            "enrolled_courses": 1 if progress.get("student_id") else 0,
            "completed_courses": 0,
            "graduated": progress.get("status") == "production_ready",
            "progress": [{
                "course_id": "cron_handling",
                "course_title": DEFAULT_COURSE["title"],
                "lessons_completed": lessons_done,
                "total_lessons": 5,
                "quizzes_passed": lessons_done,
                "failure_streak": 0,
                "current_lesson": progress.get("current_lesson", 1),
            }],
        }

    def _check_graduation(self, _key, _agent, args) -> Dict[str, Any]:
        progress = self.server.get_progress()
        completed = progress.get("lessons_completed", [])
        lessons_done = len(completed) if isinstance(completed, list) else int(completed or 0)

        from school.benchmark.solver import solve_from_memory
        memory_path = self.server.config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        answers = solve_from_memory(memory_path)
        bench = self.server.run_benchmark(answers)

        all_lessons = lessons_done >= 5
        bench_pass = bench.get("passed", False)

        missing = []
        if not all_lessons:
            missing.append("Complete all 5 lessons")
        if not bench_pass:
            missing.append(f"Pass benchmark ({bench.get('percentage', 0):.0f}% — need 70%)")

        return {
            "course_id": args.get("course_id", "cron_handling"),
            "can_graduate": all_lessons and bench_pass,
            "requirements": {
                "all_lessons_complete": all_lessons,
                "all_quizzes_passed": all_lessons,
                "benchmark_passed": bench_pass,
                "failure_streak_met": True,
                "streak_days": 7,
            },
            "benchmark": bench,
            "missing": missing,
        }

    def _graduate(self, _key, _agent, args) -> Dict[str, Any]:
        from school.benchmark.solver import solve_from_memory
        memory_path = self.server.config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        answers = solve_from_memory(memory_path)
        return self.server.teacher.graduate_student(benchmark_answers=answers)

    def _run_benchmark(self, _key, _agent, args) -> Dict[str, Any]:
        from school.benchmark.solver import solve_from_memory
        memory_path = self.server.config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        if args.get("answers"):
            return self.server.run_benchmark(args["answers"])
        answers = solve_from_memory(memory_path)
        return self.server.run_benchmark(answers)
