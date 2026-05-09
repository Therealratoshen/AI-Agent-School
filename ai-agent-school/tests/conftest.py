# conftest.py - Comprehensive test fixtures for 99% coverage

import os
import sys
import json
import uuid
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, Mock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================
# Sample Data Fixtures
# ============================================

@pytest.fixture
def sample_uuid():
    """Generate a sample UUID"""
    return str(uuid.uuid4())


@pytest.fixture
def sample_school_id():
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_school():
    """Sample school data"""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Test School",
        "owner_id": "test-owner",
        "config": {"mode": "single_tenant"},
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_student_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_student(sample_student_id, sample_school_id):
    """Sample student data"""
    return {
        "id": sample_student_id,
        "school_id": sample_school_id,
        "name": "Test Student",
        "status": "training",
        "failure_streak": 0,
        "last_failure_at": None,
        "current_lesson": 0,
        "enrolled_at": datetime.utcnow().isoformat(),
        "graduated_at": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_lesson_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_lesson(sample_lesson_id, sample_school_id):
    """Sample lesson data"""
    return {
        "id": sample_lesson_id,
        "school_id": sample_school_id,
        "topic": "cron_handling",
        "module_number": 1,
        "title": "Cron Fundamentals",
        "content": "# Cron Fundamentals\n\nLearn cron syntax.",
        "estimated_minutes": 30,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_quiz(sample_lesson_id):
    """Sample quiz data"""
    return {
        "id": str(uuid.uuid4()),
        "lesson_id": sample_lesson_id,
        "question_id": "q1",
        "question": "What does */5 mean?",
        "question_type": "multiple_choice",
        "options": json.dumps(["Every 5 hours", "Every 5 minutes", "Every 5 seconds", "Every 5 days"]),
        "correct_answer": "Every 5 minutes",
        "explanation": "*/5 means every 5 units",
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_mistake_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_mistake(sample_mistake_id, sample_student_id):
    """Sample mistake data"""
    return {
        "id": sample_mistake_id,
        "student_id": sample_student_id,
        "mistake": "Wrong cron syntax */5",
        "context": {"command": "*/5 * * * *", "expected": "0 */5 * * *"},
        "severity": "medium",
        "count": 1,
        "first_seen": datetime.utcnow().isoformat(),
        "last_seen": datetime.utcnow().isoformat(),
        "resolved": False,
        "resolved_at": None,
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_correction_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_correction(sample_correction_id, sample_student_id, sample_mistake_id):
    """Sample correction data"""
    return {
        "id": sample_correction_id,
        "student_id": sample_student_id,
        "mistake_id": sample_mistake_id,
        "correction": "Use 0 */5 for every 5 minutes",
        "explanation": "*/5 starts at 0, so 0 */5 means at minute 0 then every 5",
        "root_cause": "Misunderstanding */ syntax",
        "llm_model": "MiniMax-2.7-highspeed",
        "generated_at": datetime.utcnow().isoformat(),
        "applied_at": datetime.utcnow().isoformat(),
        "verified": True,
        "verified_at": datetime.utcnow().isoformat(),
        "verified_by": "auto",
        "learned": False,
        "learned_at": None,
        "retry_count": 0,
        "status": "applied"
    }


@pytest.fixture
def sample_cron_job_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_cron_job(sample_cron_job_id, sample_student_id, sample_school_id):
    """Sample cron job data"""
    return {
        "id": sample_cron_job_id,
        "school_id": sample_school_id,
        "student_id": sample_student_id,
        "name": "test-cron-job",
        "schedule": "*/5 * * * *",
        "command": "echo 'test'",
        "status": "active",
        "last_heartbeat": datetime.utcnow().isoformat(),
        "heartbeat_interval": 300,
        "grace_periods": 2,
        "failure_count": 0,
        "max_failures": 3,
        "last_run_at": datetime.utcnow().isoformat(),
        "last_run_status": "ok",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_message(sample_student_id, sample_school_id):
    """Sample message data"""
    return {
        "id": str(uuid.uuid4()),
        "school_id": sample_school_id,
        "student_id": sample_student_id,
        "type": "lesson",
        "payload": {"lesson_id": "test-lesson", "title": "Test Lesson"},
        "status": "pending",
        "priority": 0,
        "retry_count": 0,
        "max_retries": 3,
        "error_message": None,
        "created_at": datetime.utcnow().isoformat(),
        "processed_at": None,
        "expires_at": None
    }


@pytest.fixture
def sample_quiz_result(sample_student_id, sample_lesson_id):
    """Sample quiz result data"""
    return {
        "id": str(uuid.uuid4()),
        "student_id": sample_student_id,
        "lesson_id": sample_lesson_id,
        "score": 85.0,
        "correct_count": 2,
        "total_count": 2,
        "answers": json.dumps({"q1": "Every 5 minutes", "q2": "0 */5 * * *"}),
        "feedback": "Good job!",
        "llm_generated": True,
        "llm_model": "MiniMax-2.7-highspeed",
        "submitted_at": datetime.utcnow().isoformat()
    }


# ============================================
# Mock Fixtures
# ============================================

@pytest.fixture
def mock_db_cursor():
    """Mock database cursor"""
    cursor = MagicMock()
    cursor.description = [("id",), ("name",)]
    cursor.fetchone.return_value = {"id": "test", "name": "Test"}
    cursor.fetchall.return_value = []
    return cursor


@pytest.fixture
def mock_db_connection(mock_db_cursor):
    """Mock database connection"""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_db_cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    return conn


@pytest.fixture
def mock_db_pool(mock_db_connection):
    """Mock database connection pool"""
    pool = MagicMock()
    pool.getconn.return_value = mock_db_connection
    pool.putconn = MagicMock()
    pool.closeall = MagicMock()
    return pool


@pytest.fixture
def mock_settings():
    """Mock application settings"""
    settings = MagicMock()
    settings.database.url = "postgresql://test:test@localhost:5432/test"
    settings.database.pool_size = 5
    settings.database.max_overflow = 10
    settings.database.echo = False
    settings.redis.url = "redis://localhost:6379/0"
    settings.minimax.api_key = "test_key"
    settings.minimax.base_url = "https://api.minimax.chat"
    settings.minimax.model = "MiniMax-2.7-highspeed"
    settings.minimax.timeout = 30
    settings.app.graduation_streak_days = 7
    settings.app.heartbeat_interval = 300
    settings.app.grace_periods = 2
    settings.app.max_retries = 3
    settings.app.poll_interval = 5
    settings.app.message_timeout = 300
    settings.app.debug = False
    settings.app.host = "0.0.0.0"
    settings.app.port = 8080
    settings.app.workers = 4
    return settings


@pytest.fixture
def mock_minimax_client():
    """Mock MiniMax client"""
    client = MagicMock()
    client.api_key = "test_key"
    client.base_url = "https://api.minimax.chat"
    client.model = "MiniMax-2.7-highspeed"
    client.timeout = 30
    client.total_tokens_used = 0
    client.total_cost = 0.0
    client._price_per_1k_input = 0.01
    client._price_per_1k_output = 0.03

    # Async methods
    client.analyze_mistake = AsyncMock(return_value={
        "root_cause": "Test root cause",
        "category": "test",
        "severity": "medium"
    })
    client.generate_correction = AsyncMock(return_value={
        "correction": "Test correction",
        "explanation": "Test explanation",
        "code_example": "*/5 * * * *"
    })
    client.generate_quiz_feedback = AsyncMock(return_value="Good job!")
    client.assess_progress = AsyncMock(return_value={
        "ready": False,
        "reason": "Test",
        "recommendation": "continue_training",
        "days_remaining": 7
    })
    client.chat = AsyncMock(return_value={
        "content": "Test response",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        },
        "model": "MiniMax-2.7-highspeed",
        "cost": 0.0025
    })

    return client


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session"""
    session = AsyncMock()
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={
        "choices": [{
            "message": {
                "content": "Test response"
            }
        }],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    })
    response.text = AsyncMock(return_value="OK")
    session.post.return_value.__aenter__ = AsyncMock(return_value=response)
    session.post.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run"""
    with patch('subprocess.run') as mock:
        result = MagicMock()
        result.returncode = 0
        result.stdout = "OK"
        result.stderr = ""
        mock.return_value = result
        yield mock


# ============================================
# Temporary File Fixtures
# ============================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_memory_path(temp_dir):
    """Create a temporary memory path for student agent tests"""
    memory_path = os.path.join(temp_dir, "memory")
    os.makedirs(memory_path)
    return memory_path


@pytest.fixture
def temp_corrections_file(temp_memory_path):
    """Create a temporary corrections file"""
    path = os.path.join(temp_memory_path, "corrections.json")
    with open(path, 'w') as f:
        json.dump([], f)
    return path


@pytest.fixture
def temp_lessons_file(temp_memory_path):
    """Create a temporary lessons file"""
    path = os.path.join(temp_memory_path, "lessons.json")
    with open(path, 'w') as f:
        json.dump({}, f)
    return path


@pytest.fixture
def temp_progress_file(temp_memory_path):
    """Create a temporary progress file"""
    path = os.path.join(temp_memory_path, "progress.json")
    with open(path, 'w') as f:
        json.dump({}, f)
    return path


@pytest.fixture
def temp_system_prompt_file(temp_memory_path):
    """Create a temporary system prompt file"""
    path = os.path.join(temp_memory_path, "system_prompt_additions.txt")
    with open(path, 'w') as f:
        f.write("")
    return path


# ============================================
# Async Event Loop Fixture
# ============================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================
# Patch Decorators
# ============================================

def patch_db(func):
    """Decorator to patch database module"""
    return patch('core.database.get_db')

def patch_settings(func):
    """Decorator to patch settings"""
    return patch('core.config.get_settings')

def patch_minimax(func):
    """Decorator to patch MiniMax client"""
    return patch('llm.minimax.get_minimax_client')

def patch_message_queue(func):
    """Decorator to patch message queue"""
    return patch('core.message_queue.get_db')


# ============================================
# Autouse Fixtures for All Tests
# ============================================

@pytest.fixture(autouse=True)
def mock_all_database():
    """Automatically mock database for all tests"""
    mock_db = MagicMock()
    mock_db.execute.return_value = []
    mock_db.execute_one.return_value = None
    mock_db.execute_scalar.return_value = None

    with patch('core.database.get_db', return_value=mock_db):
        yield mock_db


@pytest.fixture(autouse=True)
def mock_all_minimax():
    """Automatically mock MiniMax client for all tests"""
    mock_client = MagicMock()
    mock_client.analyze_mistake = AsyncMock(return_value={
        "root_cause": "Test root cause",
        "category": "test",
        "severity": "medium"
    })
    mock_client.generate_correction = AsyncMock(return_value={
        "correction": "Test correction",
        "explanation": "Test explanation",
        "code_example": "*/5 * * * *"
    })
    mock_client.generate_quiz_feedback = AsyncMock(return_value="Good job!")
    mock_client.assess_progress = AsyncMock(return_value={
        "ready": False,
        "reason": "Test",
        "recommendation": "continue_training",
        "days_remaining": 7
    })
    mock_client.chat = AsyncMock(return_value={
        "content": "Test response",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        },
        "model": "MiniMax-2.7-highspeed",
        "cost": 0.0025
    })

    with patch('llm.minimax.get_minimax_client', return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def mock_message_queue():
    """Automatically mock message queue for all tests"""
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock(return_value="msg-123")

    with patch('core.message_queue.MessageQueue', return_value=mock_queue):
        yield mock_queue
