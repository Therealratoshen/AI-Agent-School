# Shared constants and message types

from enum import Enum

class MessageType(str, Enum):
    LESSON = "lesson"
    QUIZ = "quiz"
    QUIZ_SUBMISSION = "quiz_submission"
    CORRECTION = "correction"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_RESPONSE = "heartbeat_response"
    ENROLLMENT = "enrollment"
    PROGRESS = "progress"
    STATUS = "status"
    ERROR = "error"

class TrainingStatus(str, Enum):
    ENROLLED = "enrolled"
    TRAINING = "training"
    PAUSED = "paused"
    PRODUCTION_READY = "production_ready"
    STOPPED = "stopped"
    FAILED = "failed"

class MistakeSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CorrectionStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    VERIFIED = "verified"
    LEARNED = "learned"
    FAILED = "failed"

DEFAULT_CONFIG = {
    "school_check_interval": 300,
    "communication_poll_interval": 5,
    "heartbeat_interval": 300,
    "grace_periods": 2,
    "production_threshold_days": 7,
    "max_correction_attempts": 3,
}

LESSON_STATUS = {
    "NOT_STARTED": "not_started",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "NEEDS_REVIEW": "needs_review",
}
