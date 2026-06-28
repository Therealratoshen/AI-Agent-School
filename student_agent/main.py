# Student Agent - Receives lessons from Teacher and learns

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
            "base_dir": "./data/comm",
            "to_student": "./data/comm/to_student",
            "from_student": "./data/comm/from_student",
            "poll_interval": 2,
        },
        "memory": {
            "student_memory_path": "./data/student_memory",
        },
    }


class StudentAgent:
    """
    Student Agent - Receives lessons from Teacher and learns
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.comm_config = config.get("communication", {})
        self.base_dir = self.comm_config.get("base_dir", "./data/comm")
        self.to_student_dir = self.comm_config.get("to_student")
        self.from_student_dir = self.comm_config.get("from_student")
        self.poll_interval = self.comm_config.get("poll_interval", 2)

        self.memory_path = config.get("memory", {}).get("student_memory_path", "./data/student_memory")
        ensure_dir(self.memory_path)
        ensure_dir(self.to_student_dir)
        ensure_dir(self.from_student_dir)

        self.current_lesson: Optional[Dict[str, Any]] = None
        self.learned_corrections: List[str] = []
        self.auto_submit_quiz = config.get("student", {}).get("auto_submit_quiz", False)

        logger.info("Student Agent initialized")

    def check_for_messages(self) -> list:
        """Check for new messages from teacher"""
        messages = []
        import glob

        for filepath in glob.glob(os.path.join(self.to_student_dir, "*.json")):
            try:
                with open(filepath) as f:
                    message = json.load(f)
                    messages.append(message)
                os.remove(filepath)
                logger.info(f"Received message: {message.get('type')}")
            except Exception as e:
                logger.error(f"Failed to read message: {e}")

        return messages

    def process_message(self, message: Dict[str, Any]) -> None:
        """Process incoming message from teacher"""
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type in (MessageType.LESSON, MessageType.LESSON.value):
            self._process_lesson(payload)
        elif msg_type in (MessageType.QUIZ, MessageType.QUIZ.value):
            self._process_quiz_result(payload)
        elif msg_type in (MessageType.CORRECTION, MessageType.CORRECTION.value):
            self._process_correction(payload)

    def _process_lesson(self, payload: Dict[str, Any]) -> None:
        """Process incoming lesson"""
        lesson = payload.get("lesson", {})
        self.current_lesson = lesson

        self._save_to_memory({
            "type": "lesson",
            "lesson_id": lesson.get("id"),
            "title": lesson.get("title"),
            "content": lesson.get("content"),
            "received_at": timestamp(),
        })

        logger.info(f"Lesson received: {lesson.get('title')}")
        self._send_status("lesson_received", {"lesson_id": lesson.get("id")})

        if self.auto_submit_quiz and lesson.get("quiz"):
            answers = self._build_quiz_answers(lesson)
            self.submit_quiz(lesson.get("id"), answers)

    def _build_quiz_answers(self, lesson: Dict[str, Any]) -> Dict[str, str]:
        """Build quiz answers from lesson content (for demo/testing)."""
        answers = {}
        for question in lesson.get("quiz", []):
            q_id = question.get("id")
            correct = question.get("correct_answer")
            if q_id and correct:
                answers[q_id] = correct
        return answers

    def _process_quiz_result(self, payload: Dict[str, Any]) -> None:
        """Process quiz result from teacher"""
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
        """Process correction from teacher"""
        correction = {
            "id": payload.get("id"),
            "mistake": payload.get("mistake"),
            "correct": payload.get("correct_answer"),
            "explanation": payload.get("explanation"),
            "received_at": timestamp(),
        }

        self._save_correction(correction)
        self._inject_correction(correction)
        self.learned_corrections.append(correction["id"])
        logger.info(f"Correction received: {correction['id']}")

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
        system_prompt_file = os.path.join(self.memory_path, "system_prompt_additions.txt")
        with open(system_prompt_file, "a") as f:
            f.write(prompt_addition)

    def _send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        ensure_dir(self.from_student_dir)
        message = {
            "type": MessageType.STATUS,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "status": status,
                "details": details or {},
                "timestamp": timestamp(),
            },
        }
        filepath = os.path.join(self.from_student_dir, f"{generate_id('status_')}.json")
        with open(filepath, "w") as f:
            json.dump(message, f, indent=2)

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        ensure_dir(self.from_student_dir)
        message = {
            "type": MessageType.QUIZ_SUBMISSION,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "lesson_id": lesson_id,
                "answers": answers,
                "submitted_at": timestamp(),
            },
        }
        filepath = os.path.join(self.from_student_dir, f"{generate_id('quiz_')}.json")
        with open(filepath, "w") as f:
            json.dump(message, f, indent=2)
        logger.info(f"Quiz submitted for lesson: {lesson_id}")

    def get_corrections(self) -> list:
        corrections_file = os.path.join(self.memory_path, "corrections.json")
        return read_json(corrections_file, [])

    def tick(self) -> int:
        """Process one batch of teacher messages."""
        messages = self.check_for_messages()
        for message in messages:
            self.process_message(message)
        return len(messages)

    def get_state(self) -> Dict[str, Any]:
        lessons = read_json(os.path.join(self.memory_path, "lessons.json"), {})
        corrections = read_json(os.path.join(self.memory_path, "corrections.json"), [])
        return {
            "current_lesson": self.current_lesson.get("id") if self.current_lesson else None,
            "lessons_learned": list(lessons.keys()),
            "corrections_count": len(corrections),
            "memory_path": self.memory_path,
        }

    def run_loop(self) -> None:
        logger.info("Starting Student Agent loop...")
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
    parser.add_argument(
        "--auto-submit-quiz",
        action="store_true",
        help="Automatically submit correct quiz answers when a lesson arrives",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.auto_submit_quiz:
        config.setdefault("student", {})["auto_submit_quiz"] = True

    agent = StudentAgent(config)
    agent.run_loop()


if __name__ == "__main__":
    main()
