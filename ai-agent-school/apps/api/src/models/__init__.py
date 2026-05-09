from datetime import datetime
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class AgentStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    UNRESPONSIVE = "unresponsive"


class DifficultyLevel(PyEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class EnrollmentStatus(PyEnum):
    ENROLLED = "enrolled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CertificationStatus(PyEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    persona = Column(String(255), default="default")
    primary_llm = Column(String(50), default="minimax")
    memory_agent_id = Column(String(255), nullable=True)
    status = Column(Enum(AgentStatus), default=AgentStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollments = relationship("Enrollment", back_populates="agent")
    certifications = relationship("Certification", back_populates="agent")


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    topic = Column(String(100), nullable=False)
    difficulty = Column(Enum(DifficultyLevel), nullable=False)
    token_cost = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    modules = relationship("Module", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")
    certifications = relationship("Certification", back_populates="course")


class Module(Base):
    __tablename__ = "modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)

    course = relationship("Course", back_populates="modules")
    tasks = relationship("Task", back_populates="module")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)

    module = relationship("Module", back_populates="tasks")
    submissions = relationship("TaskSubmission", back_populates="task")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    status = Column(Enum(EnrollmentStatus), default=EnrollmentStatus.ENROLLED)
    progress = Column(Integer, default=0)
    current_module = Column(Integer, default=0)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    grade = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="submissions")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow)
    credential_id = Column(String(255), nullable=False, unique=True)
    status = Column(Enum(CertificationStatus), default=CertificationStatus.ACTIVE)

    agent = relationship("Agent", back_populates="certifications")
    course = relationship("Course", back_populates="certifications")


class CronJob(Base):
    __tablename__ = "cron_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    name = Column(String(255), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    command = Column(Text, nullable=False)
    last_run = Column(DateTime, nullable=True)
    last_status = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
