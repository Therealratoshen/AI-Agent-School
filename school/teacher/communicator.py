# File-based Communication - Teacher <-> Student

import os
import sys
import glob
import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared import generate_id, timestamp, setup_logging, ensure_dir

logger = setup_logging(__name__, "./logs/communicator.log")

class FileCommunicator:
    """
    File-based communication between Teacher and Student.
    Simple for MVP - can migrate to A2A later.
    """

    def __init__(self, config: Dict[str, Any]):
        comm_config = config.get('communication', {})
        self.base_dir = comm_config.get('base_dir', '/shared/ai-school')
        self.to_student_dir = comm_config.get('to_student', f'{self.base_dir}/to_student')
        self.from_student_dir = comm_config.get('from_student', f'{self.base_dir}/from_student')
        self.poll_interval = comm_config.get('poll_interval', 5)

        self._ensure_directories()
        logger.info(f"FileCommunicator initialized: {self.base_dir}")

    def _ensure_directories(self):
        """Create communication directories if they don't exist"""
        ensure_dir(self.to_student_dir)
        ensure_dir(self.from_student_dir)
        logger.debug(f"Directories ensured: {self.to_student_dir}, {self.from_student_dir}")

    def send_to_student(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to the student"""
        message_id = generate_id("msg_")
        message['id'] = message_id
        message['timestamp'] = timestamp()

        filepath = os.path.join(self.to_student_dir, f"{message_id}.json")

        try:
            with open(filepath, 'w') as f:
                json.dump(message, f, indent=2)
            logger.info(f"Sent message to student: {message_id}, type: {message.get('type')}")
            return {"status": "sent", "message_id": message_id, "file": filepath}
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {"status": "error", "message": str(e)}

    def receive_from_student(self) -> List[Dict[str, Any]]:
        """Receive all messages from student"""
        messages = []
        pattern = os.path.join(self.from_student_dir, "*.json")

        for filepath in glob.glob(pattern):
            try:
                with open(filepath) as f:
                    message = json.load(f)
                    messages.append(message)

                os.remove(filepath)
                logger.debug(f"Received message: {message.get('id')}")
            except Exception as e:
                logger.error(f"Failed to read message file {filepath}: {e}")

        return messages

    def wait_for_response(self, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Wait for a response from student"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = self.receive_from_student()
            if messages:
                return messages[0]
            time.sleep(self.poll_interval)

        logger.warning(f"Timeout waiting for student response after {timeout}s")
        return None

    def get_queue_size(self) -> int:
        """Get number of messages waiting in queue"""
        to_student_count = len(glob.glob(f"{self.to_student_dir}/*.json"))
        from_student_count = len(glob.glob(f"{self.from_student_dir}/*.json"))

        return {
            "to_student": to_student_count,
            "from_student": from_student_count
        }

    def clear_queue(self) -> Dict[str, int]:
        """Clear all pending messages"""
        cleared = {"to_student": 0, "from_student": 0}

        for filepath in glob.glob(f"{self.to_student_dir}/*.json"):
            try:
                os.remove(filepath)
                cleared["to_student"] += 1
            except Exception as e:
                logger.error(f"Failed to remove {filepath}: {e}")

        for filepath in glob.glob(f"{self.from_student_dir}/*.json"):
            try:
                os.remove(filepath)
                cleared["from_student"] += 1
            except Exception as e:
                logger.error(f"Failed to remove {filepath}: {e}")

        logger.info(f"Cleared queues: {cleared}")
        return cleared
