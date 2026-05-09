# AI Agent School - FastAPI Application
# Production REST API for the training system

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import get_settings
from core.database import get_db, check_database_health
from teacher.agent import TeacherService
from teacher.graduation import GraduationService
from teacher.self_correction import SelfCorrectionService
from cron.monitor import CronService
from core.message_queue import MessageQueue, MessageType


logger = structlog.get_logger(__name__)

# Settings
settings = get_settings()
SCHOOL_ID = "00000000-0000-0000-0000-000000000001"  # Default school


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("ai_agent_school_starting")
    yield
    logger.info("ai_agent_school_shutting_down")


# FastAPI App
app = FastAPI(
    title="AI Agent School API",
    description="Production API for AI agent training",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services (initialized lazily)
_teacher_service: Optional[TeacherService] = None
_graduation_service: Optional[GraduationService] = None
_self_correction_service: Optional[SelfCorrectionService] = None
_cron_service: Optional[CronService] = None


def get_teacher_service() -> TeacherService:
    global _teacher_service
    if _teacher_service is None:
        _teacher_service = TeacherService(SCHOOL_ID)
    return _teacher_service


def get_graduation_service() -> GraduationService:
    global _graduation_service
    if _graduation_service is None:
        _graduation_service = GraduationService(SCHOOL_ID)
    return _graduation_service


def get_self_correction_service() -> SelfCorrectionService:
    global _self_correction_service
    if _self_correction_service is None:
        _self_correction_service = SelfCorrectionService(SCHOOL_ID)
    return _self_correction_service


def get_cron_service() -> CronService:
    global _cron_service
    if _cron_service is None:
        _cron_service = CronService(SCHOOL_ID)
    return _cron_service


# ============================================
# Pydantic Models
# ============================================

class EnrollRequest(BaseModel):
    name: str
    topic: str = "cron_handling"


class QuizSubmission(BaseModel):
    student_id: str
    lesson_id: str
    answers: Dict[str, str]


class MistakeReport(BaseModel):
    student_id: str
    mistake: str
    context: Optional[Dict[str, Any]] = None
    severity: str = "medium"


class HeartbeatReport(BaseModel):
    job_id: str
    status: str = "ok"
    response_time_ms: int = 0


class CorrectionAcknowledgment(BaseModel):
    correction_id: str
    applied: bool = True


# ============================================
# Health Endpoints
# ============================================

@app.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/ready")
async def readiness_check():
    """Readiness check - includes dependency health"""
    db_health = check_database_health()

    ready = db_health["status"] == "healthy"

    return {
        "status": "ready" if ready else "not_ready",
        "database": db_health,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/live")
async def liveness_check():
    """Liveness check - is the process alive?"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


# ============================================
# Student Management
# ============================================

@app.post("/api/enroll")
async def enroll_student(request: EnrollRequest):
    """Enroll a new student"""
    service = get_teacher_service()
    result = service.enroll(request.name, request.topic)
    return result


@app.get("/api/students")
async def list_students():
    """List all students"""
    service = get_teacher_service()
    return {"students": service.get_all_students()}


@app.get("/api/students/{student_id}")
async def get_student(student_id: str):
    """Get student details"""
    service = get_teacher_service()
    progress = service.get_progress(student_id)

    if "error" in progress:
        raise HTTPException(status_code=404, detail=progress["error"])

    return progress


@app.post("/api/students/{student_id}/lessons/next")
async def deliver_next_lesson(student_id: str):
    """Deliver the next lesson to a student"""
    service = get_teacher_service()
    result = service.deliver_next(student_id)
    return result


# ============================================
# Quiz Management
# ============================================

@app.post("/api/quiz/submit")
async def submit_quiz(submission: QuizSubmission, background_tasks: BackgroundTasks):
    """Submit quiz answers for grading"""
    service = get_teacher_service()

    # Run grading in background
    result = await service.submit_quiz(
        student_id=submission.student_id,
        lesson_id=submission.lesson_id,
        answers=submission.answers
    )

    return result


# ============================================
# Mistake & Correction Management
# ============================================

@app.post("/api/mistakes/report")
async def report_mistake(report: MistakeReport):
    """Report a mistake and trigger correction"""
    service = get_self_correction_service()

    result = await service.report_mistake(
        student_id=report.student_id,
        mistake=report.mistake,
        context=report.context,
        severity=report.severity
    )

    return result


@app.get("/api/students/{student_id}/corrections")
async def get_corrections(student_id: str):
    """Get all active corrections for a student"""
    service = get_self_correction_service()
    corrections = service.get_corrections(student_id)
    return {"corrections": corrections}


@app.post("/api/corrections/{correction_id}/acknowledge")
async def acknowledge_correction(correction_id: str, ack: CorrectionAcknowledgment):
    """Acknowledge a correction (mark as applied/learned)"""
    # In production, this would update the database
    return {
        "status": "acknowledged",
        "correction_id": correction_id,
        "applied": ack.applied
    }


# ============================================
# Graduation
# ============================================

@app.get("/api/students/{student_id}/graduation")
async def get_graduation_status(student_id: str):
    """Get graduation status for a student"""
    service = get_graduation_service()
    status = service.check_student(student_id)
    return status


@app.post("/api/graduation/check")
async def run_graduation_check(student_id: Optional[str] = None):
    """Run graduation check (daily job)"""
    service = get_graduation_service()

    if student_id:
        result = service.monitor.run_daily_check(student_id)
        return result
    else:
        results = service.run_all_daily_checks()
        return {"checks": results}


# ============================================
# Cron Job Monitoring
# ============================================

@app.post("/api/cron/register")
async def register_cron_job(
    student_id: str,
    name: str,
    schedule: str,
    command: Optional[str] = None
):
    """Register a cron job for monitoring"""
    service = get_cron_service()
    job_id = service.register(student_id, name, schedule, command)
    return {"job_id": job_id}


@app.post("/api/cron/heartbeat")
async def receive_heartbeat(heartbeat: HeartbeatReport):
    """Receive a heartbeat from a cron job"""
    service = get_cron_service()
    result = service.heartbeat(heartbeat.job_id, heartbeat.status, heartbeat.response_time_ms)
    return result


@app.get("/api/cron/jobs")
async def list_cron_jobs():
    """List all monitored cron jobs"""
    service = get_cron_service()
    result = service.check_all()
    return result


@app.get("/api/cron/jobs/{job_id}")
async def get_cron_job_status(job_id: str):
    """Get status of a specific cron job"""
    service = get_cron_service()
    status = service.get_status(job_id)
    return status


@app.post("/api/cron/jobs/{job_id}/heal")
async def heal_cron_job(job_id: str):
    """Attempt to heal a failed cron job"""
    service = get_cron_service()
    result = service.heal(job_id)
    return result


# ============================================
# Metrics
# ============================================

@app.get("/api/metrics")
async def get_metrics():
    """Get system metrics"""
    db = get_db()

    # Get counts
    student_count = db.execute_scalar("SELECT COUNT(*) FROM students") or 0
    active_student_count = db.execute_scalar(
        "SELECT COUNT(*) FROM students WHERE status IN ('enrolled', 'training')"
    ) or 0
    graduated_count = db.execute_scalar(
        "SELECT COUNT(*) FROM students WHERE status = 'graduated'"
    ) or 0
    correction_count = db.execute_scalar("SELECT COUNT(*) FROM corrections") or 0
    mistake_count = db.execute_scalar("SELECT COUNT(*) FROM mistakes") or 0

    return {
        "students": {
            "total": student_count,
            "active": active_student_count,
            "graduated": graduated_count
        },
        "corrections": {
            "total": correction_count
        },
        "mistakes": {
            "total": mistake_count
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================
# Dashboard Data
# ============================================

@app.get("/api/dashboard/overview")
async def get_dashboard_overview():
    """Get overview data for dashboard"""
    db = get_db()
    teacher = get_teacher_service()
    graduation = get_graduation_service()

    # Get all students with their status
    students = teacher.get_all_students()

    # Get graduation statuses
    graduation_statuses = []
    for student in students:
        status = graduation.check_student(student["id"])
        graduation_statuses.append(status)

    # Get recent activity
    recentMistakes = db.execute("""
        SELECT m.*, s.name as student_name
        FROM mistakes m
        JOIN students s ON m.student_id = s.id
        ORDER BY m.last_seen DESC
        LIMIT 10
    """)

    recentCorrections = db.execute("""
        SELECT c.*, s.name as student_name
        FROM corrections c
        JOIN students s ON c.student_id = s.id
        ORDER BY c.generated_at DESC
        LIMIT 10
    """)

    return {
        "students": students,
        "graduation_statuses": graduation_statuses,
        "recent_mistakes": [dict(m) for m in recentMistakes],
        "recent_corrections": [dict(c) for c in recentCorrections]
    }


@app.get("/api/dashboard/student/{student_id}")
async def get_student_dashboard(student_id: str):
    """Get detailed dashboard data for a student"""
    db = get_db()
    teacher = get_teacher_service()
    graduation = get_graduation_service()
    self_correction = get_self_correction_service()

    # Get student progress
    progress = teacher.get_progress(student_id)

    # Get graduation status
    grad_status = graduation.check_student(student_id)

    # Get active corrections
    corrections = self_correction.get_corrections(student_id)

    # Get quiz history
    quiz_results = db.execute("""
        SELECT qr.*, l.title as lesson_title
        FROM quiz_results qr
        JOIN lessons l ON qr.lesson_id = l.id
        WHERE qr.student_id = %s
        ORDER BY qr.submitted_at DESC
        LIMIT 20
    """, (student_id,))

    return {
        "progress": progress,
        "graduation": grad_status,
        "corrections": corrections,
        "quiz_results": [dict(q) for q in quiz_results]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.app.debug,
        workers=1 if settings.app.debug else settings.app.workers
    )
