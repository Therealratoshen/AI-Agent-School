# Student connectors — file bus or MCP (local/cloud)

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from shared import MessageType, generate_id, timestamp, ensure_dir, setup_logging
from student_agent.mcp_client import MCPClient, MCPError

logger = setup_logging(__name__)


class StudentConnector(ABC):
    """How the student agent connects to the Teacher."""

    @abstractmethod
    def poll_messages(self) -> List[Dict[str, Any]]:
        """Return incoming messages in standard format."""

    @abstractmethod
    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        pass

    @abstractmethod
    def send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        pass

    @property
    @abstractmethod
    def mode(self) -> str:
        pass


class FileConnector(StudentConnector):
    """Local file-bus connection (./data/comm/)."""

    def __init__(self, config: Dict[str, Any]):
        comm = config.get("communication", {})
        self.to_student_dir = comm.get("to_student", "./data/comm/to_student")
        self.from_student_dir = comm.get("from_student", "./data/comm/from_student")
        ensure_dir(self.to_student_dir)
        ensure_dir(self.from_student_dir)

    @property
    def mode(self) -> str:
        return "file"

    def poll_messages(self) -> List[Dict[str, Any]]:
        import glob
        import json

        messages = []
        for filepath in glob.glob(f"{self.to_student_dir}/*.json"):
            try:
                with open(filepath) as f:
                    messages.append(json.load(f))
                import os
                os.remove(filepath)
            except Exception as e:
                logger.error(f"FileConnector read error: {e}")
        return messages

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        import json
        import os

        message = {
            "type": MessageType.QUIZ_SUBMISSION,
            "sender": "student",
            "recipient": "teacher",
            "payload": {"lesson_id": lesson_id, "answers": answers, "submitted_at": timestamp()},
        }
        filepath = os.path.join(self.from_student_dir, f"{generate_id('quiz_')}.json")
        with open(filepath, "w") as f:
            json.dump(message, f, indent=2)

    def send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        import json
        import os

        message = {
            "type": MessageType.STATUS,
            "sender": "student",
            "recipient": "teacher",
            "payload": {"status": status, "details": details or {}, "timestamp": timestamp()},
        }
        filepath = os.path.join(self.from_student_dir, f"{generate_id('status_')}.json")
        with open(filepath, "w") as f:
            json.dump(message, f, indent=2)


class MCPConnector(StudentConnector):
    """
    MCP HTTP connection — works with cloud OR local /api/mcp server.
  Tracks lesson progress and converts MCP responses to internal messages.
    """

    LESSON_IDS = {1: "cron_01", 2: "cron_02", 3: "cron_03", 4: "cron_04", 5: "cron_05"}

    def __init__(self, config: Dict[str, Any]):
        mcp_cfg = config.get("mcp", {})
        memory_path = config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        self.client = MCPClient(
            base_url=mcp_cfg.get("base_url"),
            api_key=mcp_cfg.get("api_key"),
            agent_id=mcp_cfg.get("agent_id", config.get("student", {}).get("name", "student-agent")),
            agent_name=mcp_cfg.get("agent_name", "Student Agent"),
            credentials_path=f"{memory_path}/mcp_credentials.json",
        )
        self.course_id = mcp_cfg.get("course_id", "cron_handling")
        self._current_lesson_number = 0
        self._pending_messages: List[Dict[str, Any]] = []
        self._enrolled = False

    @property
    def mode(self) -> str:
        return "mcp"

    def _ensure_ready(self) -> None:
        if not self._enrolled:
            self.client.ensure_enrolled(self.course_id)
            self._enrolled = True
            self._fetch_lesson(1)

    def _fetch_lesson(self, lesson_number: int) -> None:
        try:
            lesson = self.client.get_lesson(lesson_number)
        except MCPError as e:
            logger.error(f"Failed to fetch lesson {lesson_number}: {e}")
            return

        if lesson.get("error"):
            return

        quiz = []
        for q in lesson.get("quiz", {}).get("questions", []):
            quiz.append({
                "id": q.get("question_id"),
                "question": q.get("text"),
                "options": q.get("options"),
            })
        answers_key = lesson.get("quiz", {}).get("answers_key", {})
        for q in quiz:
            q["correct_answer"] = answers_key.get(q["id"])

        self._pending_messages.append({
            "type": MessageType.LESSON,
            "payload": {
                "lesson": {
                    "id": lesson.get("lesson_id"),
                    "title": lesson.get("title"),
                    "content": lesson.get("content"),
                    "quiz": quiz,
                },
                "lesson_number": lesson_number,
            },
        })
        self._current_lesson_number = lesson_number

    def poll_messages(self) -> List[Dict[str, Any]]:
        self._ensure_ready()
        messages = self._pending_messages[:]
        self._pending_messages.clear()
        return messages

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        lesson_number = self._current_lesson_number or 1
        for num, lid in self.LESSON_IDS.items():
            if lid == lesson_id:
                lesson_number = num
                break

        try:
            result = self.client.submit_quiz(lesson_number, answers)
        except MCPError as e:
            logger.error(f"MCP quiz submit failed: {e}")
            return

        self._pending_messages.append({
            "type": MessageType.QUIZ,
            "payload": {
                "result": {
                    "passed": result.get("passed"),
                    "score": result.get("score"),
                    "feedback": result.get("feedback"),
                },
                "next_lesson": result.get("next_lesson"),
            },
        })

        if result.get("passed") and result.get("next_lesson"):
            self._fetch_lesson(result["next_lesson"])

    def send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        logger.debug(f"MCP status: {status} {details}")

    def chat(self, message: str) -> Dict[str, Any]:
        self._ensure_ready()
        return self.client.chat(message)


def get_connector(config: Dict[str, Any]) -> StudentConnector:
    """Factory — pick connector from config."""
    mode = config.get("communication", {}).get("method", "file")
    if mode in ("mcp", "local_mcp", "cloud_mcp"):
        return MCPConnector(config)
    return FileConnector(config)
