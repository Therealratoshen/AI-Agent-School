# Student Agent - Runs on your VPS, receives lessons from school

import os
import sys
import json
import time
import argparse
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from shared import (
    MessageType, timestamp, generate_id,
    setup_logging, ensure_dir, read_json, write_json
)

logger = setup_logging(__name__, "./logs/student_agent.log")

class StudentAgent:
    """
    Student Agent - Receives lessons from Teacher and learns
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.comm_config = config.get('communication', {})
        self.base_dir = self.comm_config.get('base_dir', '/shared/ai-school')
        self.to_student_dir = self.comm_config.get('to_student')
        self.from_student_dir = self.comm_config.get('from_student')
        self.poll_interval = self.comm_config.get('poll_interval', 5)

        self.memory_path = config.get('memory', {}).get('student_memory_path', './memory')
        ensure_dir(self.memory_path)

        self.current_lesson = None
        self.learned_corrections = []

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

        if msg_type == MessageType.LESSON:
            self._process_lesson(payload)
        elif msg_type == MessageType.QUIZ:
            self._process_quiz_result(payload)
        elif msg_type == MessageType.CORRECTION:
            self._process_correction(payload)

    def _process_lesson(self, payload: Dict[str, Any]) -> None:
        """Process incoming lesson"""
        lesson = payload.get('lesson', {})
        self.current_lesson = lesson

        self._save_to_memory({
            "type": "lesson",
            "lesson_id": lesson.get('id'),
            "title": lesson.get('title'),
            "content": lesson.get('content'),
            "received_at": timestamp()
        })

        logger.info(f"Lesson received: {lesson.get('title')}")

        self._send_status("lesson_received", {"lesson_id": lesson.get('id')})

    def _process_quiz_result(self, payload: Dict[str, Any]) -> None:
        """Process quiz result from teacher"""
        result = payload.get('result', {})
        next_lesson = payload.get('next_lesson')

        self._save_to_memory({
            "type": "quiz_result",
            "passed": result.get('passed'),
            "score": result.get('score'),
            "feedback": result.get('feedback'),
            "received_at": timestamp()
        })

        logger.info(f"Quiz result: passed={result.get('passed')}, score={result.get('score')}")

        if result.get('passed') and next_lesson:
            logger.info(f"Ready for next lesson: {next_lesson}")

    def _process_correction(self, payload: Dict[str, Any]) -> None:
        """Process correction from teacher"""
        correction = {
            "id": payload.get('id'),
            "mistake": payload.get('mistake'),
            "correct": payload.get('correct_answer'),
            "explanation": payload.get('explanation'),
            "received_at": timestamp()
        }

        self._save_correction(correction)
        self._inject_correction(correction)

        self.learned_corrections.append(correction['id'])

        logger.info(f"Correction received: {correction['id']}")

    def _save_to_memory(self, data: Dict[str, Any]) -> None:
        """Save data to memory"""
        lessons_file = os.path.join(self.memory_path, "lessons.json")
        lessons = read_json(lessons_file, {})

        if data.get('lesson_id'):
            lessons[data['lesson_id']] = data

        write_json(lessons_file, lessons)

    def _save_correction(self, correction: Dict[str, Any]) -> None:
        """Save correction to persistent memory"""
        corrections_file = os.path.join(self.memory_path, "corrections.json")
        corrections = read_json(corrections_file, [])

        corrections.append(correction)
        write_json(corrections_file, corrections)

        logger.info(f"Correction saved to memory: {corrections_file}")

    def _inject_correction(self, correction: Dict[str, Any]) -> None:
        """Inject correction into system prompt for immediate effect"""
        prompt_addition = f"""
IMPORTANT REMINDER:
- Mistake to avoid: {correction['mistake']}
- Correct approach: {correction['correct']}
- Reason: {correction.get('explanation', '')}

Always remember this. Do not repeat this mistake.
"""

        system_prompt_file = os.path.join(self.memory_path, "system_prompt_additions.txt")
        with open(system_prompt_file, 'a') as f:
            f.write(prompt_addition)

        logger.info("Correction injected into system prompt")

    def _send_status(self, status: str, details: Dict[str, Any] = None) -> None:
        """Send status to teacher"""
        ensure_dir(self.from_student_dir)

        message = {
            "type": MessageType.STATUS,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "status": status,
                "details": details or {},
                "timestamp": timestamp()
            }
        }

        filepath = os.path.join(self.from_student_dir, f"{generate_id('status_')}.json")
        with open(filepath, 'w') as f:
            json.dump(message, f, indent=2)

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> None:
        """Submit quiz answers to teacher"""
        ensure_dir(self.from_student_dir)

        message = {
            "type": MessageType.QUIZ_SUBMISSION,
            "sender": "student",
            "recipient": "teacher",
            "payload": {
                "lesson_id": lesson_id,
                "answers": answers,
                "submitted_at": timestamp()
            }
        }

        filepath = os.path.join(self.from_student_dir, f"{generate_id('quiz_')}.json")
        with open(filepath, 'w') as f:
            json.dump(message, f, indent=2)

        logger.info(f"Quiz submitted for lesson: {lesson_id}")

    def send_heartbeat(self, job_name: str) -> None:
        """Record a heartbeat"""
        heartbeat_file = os.path.join(self.memory_path, "heartbeats.json")
        heartbeats = read_json(heartbeat_file, {})

        heartbeats[job_name] = {
            "last_heartbeat": timestamp(),
            "status": "ok"
        }

        write_json(heartbeat_file, heartbeats)

        logger.debug(f"Heartbeat recorded: {job_name}")

    def get_corrections(self) -> list:
        """Get all learned corrections"""
        corrections_file = os.path.join(self.memory_path, "corrections.json")
        return read_json(corrections_file, [])

    def run_loop(self) -> None:
        """Main polling loop"""
        logger.info("Starting Student Agent loop...")

        while True:
            try:
                messages = self.check_for_messages()

                for message in messages:
                    self.process_message(message)

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Student Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in loop: {e}")
                time.sleep(self.poll_interval)

def main():
    parser = argparse.ArgumentParser(description="AI Agent School - Student Agent")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to config file",
        default=None
    )
    args = parser.parse_args()

    config = {
        "communication": {
            "base_dir": "/shared/ai-school",
            "to_student": "/shared/ai-school/to_student",
            "from_student": "/shared/ai-school/from_student",
            "poll_interval": 5
        },
        "memory": {
            "student_memory_path": "./memory"
        }
    }

    agent = StudentAgent(config)
    agent.run_loop()

if __name__ == "__main__":
    main()
