from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    UNRESPONSIVE = "unresponsive"


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class EnrollmentStatus(str, Enum):
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CertificationStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Agent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    name: str
    persona: str = "default"
    primary_llm: str = "minimax"
    memory_agent_id: Optional[str] = None
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Module(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    content: str
    order: int
    course_id: UUID


class Course(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    topic: str
    difficulty: DifficultyLevel
    token_cost: int
    modules: list[Module] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Enrollment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    course_id: UUID
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED
    progress: int = 0
    current_module: int = 0
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class Certification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    course_id: UUID
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    credential_id: str
    status: CertificationStatus = CertificationStatus.ACTIVE


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    module_id: UUID
    order: int


class TaskSubmission(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    agent_id: UUID
    content: str
    grade: Optional[int] = None
    feedback: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
