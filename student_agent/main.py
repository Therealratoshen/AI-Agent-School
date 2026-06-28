# Student Agent - connects via file bus OR MCP (local/cloud)

import os
import sys
import json
import time
import argparse
import yaml
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared import (
    MessageType, timestamp, generate_id,
    setup_logging, ensure_dir, read_json, write_json
)
from student_agent.connector import get_connector, StudentConnector, MCPConnector

logger = setup_logging(__name__, "./logs/student_agent.log")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)

    root = os.path.dirname(os.path.dirname(__file__))
    default_path = os.path.join(root, "config", "config.yaml")
    if os.path.exists(default_path):
        with open(default_path) as f:
            return yaml.safe_load(f)

    return {
        "communication": {
            "method": "file",
            "base_dir": "./data/comm",
            "to_student": "./data/comm/to_student",
            "from_student": "./data/comm/from_student",
            "poll_interval": 2,
        },
        "memory": {"student_memory_path": "./data/student_memory"},
        "mcp": {"base_url": "http://localhost:8080/api/mcp"},
    }


class StudentAgent:
    """
    Student Agent — learns from Teacher via file bus or MCP.

    Connection modes (config communication.method):
      - file      → local JSON files in ./data/comm/
      - mcp       → HTTP MCP to local school (localhost:8080/api/mcp)
      - cloud_mcp → HTTP MCP to shortcutsistem.com (set mcp.base_url)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_path = config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        self.poll_interval = config.get("communication", {}).get("poll_interval", 2)
        ensure_dir(self.memory_path)

        self.connector: StudentConnector = get_connector(config)
        self.current_lesson: Optional[Dict[str, Any]] = None
        self.learned_corrections: List[str] = []
        self.auto_submit_quiz = config.get("student", {}).get("auto_submit_quiz", False)
        self.current_lesson_number = 0

        logger.info(f"Student Agent initialized (mode={self.connector.mode})")

    def check_for_messages(self) -> list:
        return self.connector.poll_messages()

    def process_message(self, message: Dict[str, Any]) -> None:
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type in (MessageType.LESSON, MessageType.LESSON.value, "lesson"):
            self._process_lesson(payload)
        elif msg_type in (MessageType.QUIZ, MessageType.QUIZ.value, "quiz"):
            self._process_quiz_result(payload)
        elif msg_type in (MessageType.CORRECTION, MessageType.CORRECTION.value, "correction"):
            self._process_correction(payload)
        elif msg_type in (MessageType.GRADUATION, "graduation"):
            self._process_graduation(payload)

    def _process_lesson(self, payload: Dict[str, Any]) -> None:
        lesson = payload.get("lesson", {})
        self.current_lesson = lesson
        self.current_lesson_number = payload.get("lesson_number", self.current_lesson_number)

        self._save_to_memory({
            "type": "lesson",
            "lesson_id": lesson.get("id"),
            "title": lesson.get("title"),
            "content": lesson.get("content"),
            "received_at": timestamp(),
        })

        logger.info(f"Lesson received: {lesson.get('title')}")
        self.connector.send_status("lesson_received", {"lesson_id": lesson.get("id")})

        if self.auto_submit_quiz and lesson.get("quiz"):
            answers = self._build_quiz_answers(lesson)
            self.submit_quiz(lesson.get("id"), answers)

    def _build_quiz_answers(self, lesson: Dict[str, Any]) -> Dict[str, str]:
        answers = {}
        for question in lesson.get("quiz", []):
            q_id = question.get("id")
            correct = question.get("correct_answer")
            if q_id and correct:
                answers[q_id] = correct
        return answers

    def _process_quiz_result(self, payload: Dict[str, Any]) -> None:
        result = payload.get("result", payload)
        next_lesson = payload.get("next_lesson")

        self._save_to_memory({
            "type": "quiz_result",
            "passed": result.get("passed"),
            "score": result.get("score"),
            "feedback": result.get("feedback"),
            "received_at": timestamp(),
        })

        logger.info(f"Quiz result: passed={result.get('passed')}, score={result.get('score')}")
        if result.get("passed") and next_lesson:
            logger.info(f"Ready for next lesson: {next_lesson}")

    def _process_correction(self, payload: Dict[str, Any]) -> None:
        correction = {
            "id": payload.get("id") or payload.get("correction_id"),
            "mistake": payload.get("mistake"),
            "correct": payload.get("correct_answer") or payload.get("correction"),
            "explanation": payload.get("explanation"),
            "received_at": timestamp(),
        }
        self._save_correction(correction)
        self._inject_correction(correction)
        self.learned_corrections.append(correction["id"])
        logger.info(f"Correction received: {correction['id']}")

    def _process_graduation(self, payload: Dict[str, Any]) -> None:
        write_json(os.path.join(self.memory_path, "graduation.json"), payload)
        logger.info(f"Graduated! Certificate: {payload.get('certificate_id')}")

    def _save_to_memory(self, data: Dict[str, Any]) -> None:
        lessons_file = os.path.join(self.memory_path, "lessons.json")
        lessons = read_json(lessons_file, {})
        if data.get("lesson_id"):
            lessons[data["lesson_id"]] = data
        write_json(lessons_file, lessons)

    def _save_correction(self, correction: Dict[str, Any]) -> None:
        corrections_file = os.path.join(self.memory_path, "corrections.json")
        corrections = read_json(corrections_file, [])
        corrections.append(correction)
        write_json(corrections_file, corrections)

    def _inject_correction(self, correction: Dict[str, Any]) -> None:
        prompt_addition = f"""
IMPORTANT REMINDER:
- Mistake to avoid: {correction['mistake']}
- Correct approach: {correction['correct']}
- Reason: {correction.get('explanation', '')}

Always remember this. Do not repeat this mistake.
"""
        with open(os.path.join(self.memory_path, "system_prompt_additions.txt"), "a") as f:
            f.write(prompt_addition)

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        self.connector.submit_quiz(lesson_id, answers)
        logger.info(f"Quiz submitted for lesson: {lesson_id}")

    def chat_with_teacher(self, message: str) -> Dict[str, Any]:
        """Ask the Teacher a question (MCP mode only)."""
        if isinstance(self.connector, MCPConnector):
            return self.connector.chat(message)
        return {"response": "Chat requires MCP mode. Set communication.method to 'mcp'."}

    def get_corrections(self) -> list:
        return read_json(os.path.join(self.memory_path, "corrections.json"), [])

    def tick(self) -> int:
        messages = self.check_for_messages()
        for message in messages:
            self.process_message(message)
        return len(messages)

    def get_state(self) -> Dict[str, Any]:
        lessons = read_json(os.path.join(self.memory_path, "lessons.json"), {})
        return {
            "connection_mode": self.connector.mode,
            "current_lesson": self.current_lesson.get("id") if self.current_lesson else None,
            "lessons_learned": list(lessons.keys()),
            "corrections_count": len(self.get_corrections()),
            "memory_path": self.memory_path,
        }

    def answer_benchmark(self, topic: str = "cron_handling") -> Dict[str, str]:
        from school.benchmark.solver import solve_from_memory
        return solve_from_memory(self.memory_path, topic)

    def run_learning_loop(self, max_lessons: int = 5) -> Dict[str, Any]:
        """Complete up to max_lessons via any connection mode."""
        lessons_done = 0
        for _ in range(max_lessons * 30):
            self.tick()
            state = self.get_state()
            lessons_done = len(state["lessons_learned"])
            if lessons_done >= max_lessons:
                break
            time.sleep(self.poll_interval)

        if isinstance(self.connector, MCPConnector):
            try:
                bench = self.connector.client.run_benchmark(self.answer_benchmark())
                grad = self.connector.client.check_graduation()
                return {"state": self.get_state(), "benchmark": bench, "graduation": grad}
            except Exception as e:
                logger.warning(f"MCP benchmark/graduation check: {e}")

        return {"state": self.get_state()}

    def run_loop(self) -> None:
        logger.info(f"Starting Student Agent loop (mode={self.connector.mode})...")
        while True:
            try:
                self.tick()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("Student Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in loop: {e}")
                time.sleep(self.poll_interval)


def main():
    parser = argparse.ArgumentParser(description="AI Agent School - Student Agent")
    parser.add_argument("--config", "-c", help="Path to config file", default=None)
    parser.add_argument("--mode", choices=["file", "mcp", "cloud_mcp"], help="Connection mode")
    parser.add_argument("--mcp-url", help="MCP base URL (e.g. http://localhost:8080/api/mcp)")
    parser.add_argument("--api-key", help="MCP API key (or set AI_SCHOOL_API_KEY)")
    parser.add_argument("--agent-id", default="student-agent", help="Agent ID for MCP registration")
    parser.add_argument("--auto-submit-quiz", action="store_true")
    parser.add_argument("--learn", type=int, metavar="N", help="Complete N lessons then exit")
    parser.add_argument("--chat", metavar="MSG", help="Send one message to Teacher (MCP mode)")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.mode:
        config.setdefault("communication", {})["method"] = args.mode
    if args.mcp_url:
        config.setdefault("mcp", {})["base_url"] = args.mcp_url
    if args.api_key:
        config.setdefault("mcp", {})["api_key"] = args.api_key
    if args.agent_id:
        config.setdefault("mcp", {})["agent_id"] = args.agent_id
    if args.auto_submit_quiz:
        config.setdefault("student", {})["auto_submit_quiz"] = True

    agent = StudentAgent(config)

    if args.chat:
        result = agent.chat_with_teacher(args.chat)
        print(json.dumps(result, indent=2))
        return

    if args.learn:
        result = agent.run_learning_loop(max_lessons=args.learn)
        print(json.dumps(result, indent=2))
        return

    agent.run_loop()


if __name__ == "__main__":
    main()
