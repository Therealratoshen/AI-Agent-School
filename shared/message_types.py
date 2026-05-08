# Shared message types for Teacher <-> Student communication

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

@dataclass
class Message:
    id: str
    type: str
    timestamp: str
    sender: str
    recipient: str
    payload: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(**data)

@dataclass
class LessonContent:
    module_id: str
    title: str
    content: str
    quiz: List[Dict[str, Any]]
    estimated_minutes: int

@dataclass
class QuizQuestion:
    id: str
    question: str
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None

@dataclass
class QuizSubmission:
    lesson_id: str
    answers: Dict[str, str]
    submitted_at: str

@dataclass
class Correction:
    id: str
    mistake: str
    correct_answer: str
    explanation: str
    status: str = "pending"
    attempts: int = 0
    created_at: Optional[str] = None

@dataclass
class ProgressUpdate:
    student_id: str
    lesson_id: str
    status: str
    completed_at: Optional[str] = None
    quiz_score: Optional[float] = None
