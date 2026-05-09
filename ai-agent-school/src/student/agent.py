# Student Agent
# Runs on VPS, receives lessons and corrections from AI Agent School
# Supports hot-reload of corrections without restart

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from core.config import get_settings


logger = structlog.get_logger(__name__)


class StudentMemory:
    """
    Manages persistent memory for the student agent.
    Corrections and lessons are stored on disk and survive restarts.
    """

    def __init__(self, memory_path: str = "./memory"):
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)

        self.corrections_file = self.memory_path / "corrections.json"
        self.lessons_file = self.memory_path / "lessons.json"
        self.system_prompt_file = self.memory_path / "system_prompt_additions.txt"
        self.progress_file = self.memory_path / "progress.json"
        self.config_file = self.memory_path / "config.json"

        self._ensure_files()

    def _ensure_files(self):
        """Ensure all memory files exist"""
        for f in [self.corrections_file, self.lessons_file, self.progress_file]:
            if not f.exists():
                f.write_text("{}" if f != self.system_prompt_file else "")

    def load_corrections(self) -> List[Dict[str, Any]]:
        """Load all corrections from disk"""
        try:
            return json.loads(self.corrections_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_correction(self, correction: Dict[str, Any]) -> None:
        """Save a correction to disk"""
        corrections = self.load_corrections()

        # Check for duplicates
        existing_ids = {c.get("correction_id") for c in corrections}
        if correction.get("correction_id") not in existing_ids:
            corrections.append(correction)
            self.corrections_file.write_text(json.dumps(corrections, indent=2))
            logger.info("correction_saved", correction_id=correction.get("correction_id"))

    def get_corrections(self) -> List[Dict[str, Any]]:
        """Get all corrections"""
        return self.load_corrections()

    def mark_correction_applied(self, correction_id: str) -> None:
        """Mark a correction as applied"""
        corrections = self.load_corrections()
        for c in corrections:
            if c.get("correction_id") == correction_id:
                c["applied_at"] = datetime.utcnow().isoformat()
                c["status"] = "applied"
        self.corrections_file.write_text(json.dumps(corrections, indent=2))

    def mark_correction_learned(self, correction_id: str) -> None:
        """Mark a correction as learned"""
        corrections = self.load_corrections()
        for c in corrections:
            if c.get("correction_id") == correction_id:
                c["learned"] = True
                c["learned_at"] = datetime.utcnow().isoformat()
                c["status"] = "learned"
        self.corrections_file.write_text(json.dumps(corrections, indent=2))

    def load_lessons(self) -> Dict[str, Any]:
        """Load all lessons"""
        try:
            return json.loads(self.lessons_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save_lesson(self, lesson: Dict[str, Any]) -> None:
        """Save a lesson to disk"""
        lessons = self.load_lessons()
        lesson_id = lesson.get("lesson_id")
        if lesson_id:
            lessons[lesson_id] = lesson
            self.lessons_file.write_text(json.dumps(lessons, indent=2))

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific lesson"""
        lessons = self.load_lessons()
        return lessons.get(lesson_id)

    def load_progress(self) -> Dict[str, Any]:
        """Load progress"""
        try:
            return json.loads(self.progress_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save_progress(self, progress: Dict[str, Any]) -> None:
        """Save progress"""
        self.progress_file.write_text(json.dumps(progress, indent=2))

    def get_active_corrections(self) -> List[Dict[str, Any]]:
        """Get all corrections that are applied but not yet learned"""
        corrections = self.load_corrections()
        return [
            c for c in corrections
            if c.get("status") == "applied" and not c.get("learned")
        ]


class SystemPromptManager:
    """
    Manages system prompt additions from corrections.
    These are injected into the agent's context for hot-reload behavior.
    """

    def __init__(self, memory: StudentMemory):
        self.memory = memory
        self._lock = threading.Lock()

    def build_additions(self) -> str:
        """Build the system prompt additions from corrections"""
        corrections = self.memory.get_active_corrections()

        if not corrections:
            return ""

        additions = [
            "\n\n# IMPORTANT REMINDERS (Auto-generated from corrections):"
        ]

        for corr in corrections:
            additions.append(f"""
## Correction: {corr.get('mistake', 'Unknown mistake')}
- What was wrong: {corr.get('mistake', '')}
- Correct approach: {corr.get('correction', '')}
- Why: {corr.get('explanation', '')}
""".strip())

        return "\n".join(additions)

    def inject_correction(self, correction: Dict[str, Any]) -> None:
        """
        Inject a new correction into the system prompt.
        This is the HOT RELOAD mechanism - corrections take effect immediately.
        """
        with self._lock:
            # Append to system prompt file
            prompt_addition = f"""

# NEW CORRECTION ({datetime.utcnow().isoformat()}):
## Mistake: {correction.get('mistake', '')}
## Correction: {correction.get('correction', '')}
## Explanation: {correction.get('explanation', '')}
## Verify after: {correction.get('verify_after', 'N/A')}

IMPORTANT: Apply this correction immediately. Do not repeat the mistake.
"""
            with open(self.memory.system_prompt_file, "a") as f:
                f.write(prompt_addition)

            logger.info(
                "correction_injected_into_prompt",
                correction_id=correction.get("correction_id")
            )

    def clear_learned(self) -> None:
        """Clear learned corrections from system prompt"""
        # In production, you might want to archive rather than delete
        # For now, just note that corrections were learned
        logger.info("corrections_learned_cleared")


class StudentAgent:
    """
    Student Agent that runs on the VPS.

    Responsibilities:
    - Poll AI Agent School for messages (lessons, corrections)
    - Store lessons and corrections locally (persistent memory)
    - Apply corrections via system prompt injection (hot reload)
    - Send quiz submissions back to AI Agent School
    - Send heartbeats to indicate health
    - Report mistakes to AI Agent School for correction
    """

    def __init__(
        self,
        memory_path: str = "./memory",
        poll_interval: int = 5
    ):
        self.settings = get_settings()
        self.poll_interval = poll_interval

        # Initialize memory
        self.memory = StudentMemory(memory_path)
        self.prompt_manager = SystemPromptManager(self.memory)

        # State
        self.current_lesson: Optional[Dict[str, Any]] = None
        self.running = False
        self._lock = threading.Lock()

        logger.info("student_agent_initialized", memory_path=memory_path)

    def handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle an incoming message from AI Agent School.

        Message types:
        - lesson: New lesson to learn
        - quiz: Quiz result
        - correction: Correction to apply (HOT RELOAD)
        - graduation: Student has graduated
        """
        msg_type = message.get("type")
        payload = message.get("payload", {})

        logger.info("message_received", type=msg_type)

        if msg_type == "lesson":
            self._handle_lesson(payload)
        elif msg_type == "quiz":
            self._handle_quiz_result(payload)
        elif msg_type == "correction":
            self._handle_correction(payload)
        elif msg_type == "graduation":
            self._handle_graduation(payload)
        else:
            logger.warning("unknown_message_type", type=msg_type)

    def _handle_lesson(self, payload: Dict[str, Any]) -> None:
        """Handle incoming lesson"""
        lesson = {
            "lesson_id": payload.get("lesson_id"),
            "title": payload.get("title"),
            "content": payload.get("content"),
            "module_number": payload.get("module_number"),
            "received_at": datetime.utcnow().isoformat()
        }

        self.memory.save_lesson(lesson)
        self.current_lesson = lesson

        # Update progress
        progress = self.memory.load_progress()
        progress["current_lesson"] = lesson["lesson_id"]
        progress["lessons_received"] = progress.get("lessons_received", []) + [lesson["lesson_id"]]
        self.memory.save_progress(progress)

        logger.info("lesson_received", lesson_id=lesson["lesson_id"])

    def _handle_quiz_result(self, payload: Dict[str, Any]) -> None:
        """Handle quiz result"""
        result = {
            "lesson_id": payload.get("lesson_id"),
            "score": payload.get("score"),
            "passed": payload.get("passed"),
            "correct_count": payload.get("correct_count"),
            "total_count": payload.get("total_count"),
            "feedback": payload.get("feedback"),
            "next_lesson": payload.get("next_lesson"),
            "received_at": datetime.utcnow().isoformat()
        }

        # Save to progress
        progress = self.memory.load_progress()
        progress["quiz_results"] = progress.get("quiz_results", []) + [result]
        if payload.get("passed"):
            progress["lessons_completed"] = progress.get("lessons_completed", []) + [payload.get("lesson_id")]
        self.memory.save_progress(progress)

        logger.info(
            "quiz_result_received",
            lesson_id=payload.get("lesson_id"),
            score=payload.get("score"),
            passed=payload.get("passed")
        )

    def _handle_correction(self, payload: Dict[str, Any]) -> None:
        """
        Handle incoming correction.
        This is the HOT RELOAD mechanism.
        """
        correction = {
            "correction_id": payload.get("correction_id"),
            "mistake": payload.get("mistake"),
            "correction": payload.get("correction"),
            "explanation": payload.get("explanation"),
            "applied_at": payload.get("applied_at"),
            "verify_after": payload.get("verify_after"),
            "status": "received"
        }

        # Save to persistent memory
        self.memory.save_correction(correction)

        # Mark as applied
        self.memory.mark_correction_applied(correction["correction_id"])

        # INJECT INTO SYSTEM PROMPT (HOT RELOAD)
        self.prompt_manager.inject_correction(correction)

        logger.info(
            "correction_received_and_injected",
            correction_id=correction["correction_id"]
        )

    def _handle_graduation(self, payload: Dict[str, Any]) -> None:
        """Handle graduation message"""
        # Save graduation info
        progress = self.memory.load_progress()
        progress["graduated"] = True
        progress["graduation"] = {
            "certificate_id": payload.get("certificate_id"),
            "graduated_at": payload.get("graduated_at"),
            "message": payload.get("message")
        }
        self.memory.save_progress(progress)

        # Clear corrections from prompt (they're now baked in)
        self.prompt_manager.clear_learned()

        logger.info(
            "graduated",
            certificate_id=payload.get("certificate_id")
        )

    def submit_quiz(
        self,
        lesson_id: str,
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Submit quiz answers to AI Agent School.
        Returns the submission result (actual grading happens server-side).
        """
        # In a real implementation, this would send to the message queue
        # For now, just log
        logger.info(
            "quiz_submitted_locally",
            lesson_id=lesson_id,
            answer_count=len(answers)
        )

        return {
            "status": "submitted",
            "lesson_id": lesson_id,
            "answers": answers
        }

    def report_mistake(
        self,
        mistake: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Report a mistake to AI Agent School for correction.
        This triggers the self-correction loop.
        """
        # In a real implementation, this would send to the message queue
        logger.info(
            "mistake_reported_locally",
            mistake=mistake[:100],
            context=context
        )

        return {
            "status": "reported",
            "mistake": mistake
        }

    def get_context_for_agent(self) -> Dict[str, Any]:
        """
        Build context for the AI agent.
        Includes current lesson, corrections, and system prompt additions.
        """
        progress = self.memory.load_progress()
        corrections = self.memory.get_active_corrections()
        prompt_additions = self.prompt_manager.build_additions()

        return {
            "current_lesson": self.current_lesson,
            "progress": progress,
            "active_corrections_count": len(corrections),
            "prompt_additions": prompt_additions,
            "is_graduated": progress.get("graduated", False)
        }

    def run_loop(self, api_base_url: str = "http://localhost:8080") -> None:
        """
        Main polling loop.
        In production, this would use the message queue system.
        """
        self.running = True
        logger.info("student_agent_started", api_base=api_base_url)

        while self.running:
            try:
                # In production, use the message queue to receive messages
                # For now, just process local memory
                progress = self.memory.load_progress()

                if progress.get("graduated"):
                    logger.info("student_graduated_stopping_loop")
                    break

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("student_agent_stopped_by_user")
                break
            except Exception as e:
                logger.error("error_in_student_loop", error=str(e))
                time.sleep(self.poll_interval)

        self.running = False

    def stop(self) -> None:
        """Stop the student agent"""
        self.running = False
        logger.info("student_agent_stop_requested")


class StudentAgentAPI:
    """
    REST API for Student Agent.
    Allows AI Agent School to communicate with the student.
    """

    def __init__(self, agent: StudentAgent):
        self.agent = agent

    def receive_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Receive messages from AI Agent School"""
        for msg in messages:
            self.agent.handle_message(msg)

        return {"status": "received", "count": len(messages)}

    def submit_quiz(self, lesson_id: str, answers: Dict[str, str]) -> Dict[str, Any]:
        """Submit quiz for grading"""
        return self.agent.submit_quiz(lesson_id, answers)

    def report_mistake(self, mistake: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Report a mistake"""
        return self.agent.report_mistake(mistake, context)

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        context = self.agent.get_context_for_agent()
        progress = self.agent.memory.load_progress()

        return {
            "status": "running",
            "graduated": context["is_graduated"],
            "current_lesson": context.get("current_lesson", {}).get("lesson_id"),
            "active_corrections": context["active_corrections_count"],
            "lessons_received": len(progress.get("lessons_received", [])),
            "lessons_completed": len(progress.get("lessons_completed", []))
        }
