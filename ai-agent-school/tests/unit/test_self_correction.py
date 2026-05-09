# tests/unit/test_self_correction.py
# Self-Correction Engine tests for 99% coverage

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))


class TestMistakeRepository:
    """Tests for MistakeRepository"""

    def test_find_similar_returns_existing_mistake(self, sample_mistake):
        """Test find_similar returns existing similar mistake"""
        with patch('core.database.get_db'):
            from teacher.self_correction import MistakeRepository
            repo = MistakeRepository()

            repo.db.execute_one.return_value = sample_mistake

            result = repo.find_similar(sample_mistake["student_id"], "Wrong cron syntax")

            assert result is not None
            assert result["id"] == sample_mistake["id"]

    def test_find_similar_returns_none_when_not_found(self):
        """Test find_similar returns None when no similar mistake exists"""
        with patch('core.database.get_db'):
            from teacher.self_correction import MistakeRepository
            repo = MistakeRepository()

            repo.db.execute_one.return_value = None

            result = repo.find_similar("student-123", "Unknown mistake")

            assert result is None

    def test_increment_count_updates_mistake(self, sample_mistake_id):
        """Test increment_count increases the count"""
        with patch('core.database.get_db'):
            from teacher.self_correction import MistakeRepository
            repo = MistakeRepository()

            repo.db.execute.return_value = None

            repo.increment_count(sample_mistake_id)

            repo.db.execute.assert_called_once()


class TestCorrectionRepository:
    """Tests for CorrectionRepository"""

    def test_get_pending_verification_returns_pending(self, sample_correction):
        """Test get_pending_verification returns corrections pending verification"""
        with patch('core.database.get_db'):
            from teacher.self_correction import CorrectionRepository
            repo = CorrectionRepository()

            repo.db.execute.return_value = [sample_correction]

            result = repo.get_pending_verification(sample_correction["student_id"])

            assert len(result) == 1
            assert result[0]["id"] == sample_correction["id"]

    def test_get_pending_verification_returns_empty_when_none(self):
        """Test get_pending_verification returns empty list when none pending"""
        with patch('core.database.get_db'):
            from teacher.self_correction import CorrectionRepository
            repo = CorrectionRepository()

            repo.db.execute.return_value = []

            result = repo.get_pending_verification("student-123")

            assert len(result) == 0

    def test_mark_verified_updates_status_success(self, sample_correction_id):
        """Test mark_verified updates status to verified"""
        with patch('core.database.get_db'):
            from teacher.self_correction import CorrectionRepository
            repo = CorrectionRepository()

            repo.db.execute.return_value = None

            repo.mark_verified(sample_correction_id, True)

            repo.db.execute.assert_called_once()

    def test_mark_verified_updates_status_failed(self, sample_correction_id):
        """Test mark_verified updates status to failed"""
        with patch('core.database.get_db'):
            from teacher.self_correction import CorrectionRepository
            repo = CorrectionRepository()

            repo.db.execute.return_value = None

            repo.mark_verified(sample_correction_id, False)

            repo.db.execute.assert_called_once()


class TestSelfCorrectionEngine:
    """Tests for SelfCorrectionEngine"""

    def test_engine_initializes_correctly(self, sample_school_id, mock_minimax_client):
        """Test engine initializes with correct school_id"""
        with patch('core.database.get_db'), \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue'), \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()
            mock_get_minimax.return_value = mock_minimax_client

            mock_mistake_repo = MagicMock()
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)

            assert engine.school_id == sample_school_id
            assert engine.verification_window_hours == 24
            assert engine.escalation_threshold == 3

    @pytest.mark.asyncio
    async def test_detect_and_correct_existing_mistake_increments_count(
        self, sample_school_id, sample_student_id, sample_mistake
    ):
        """Test detect_and_correct increments existing mistake"""
        with patch('core.database.get_db'), \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue'), \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()

            mock_minimax = MagicMock()
            mock_minimax.analyze_mistake = AsyncMock(return_value={
                "root_cause": "Test",
                "category": "test",
                "severity": "medium"
            })
            mock_minimax.generate_correction = AsyncMock(return_value={
                "correction": "Test correction",
                "explanation": "Test explanation",
                "code_example": None
            })
            mock_get_minimax.return_value = mock_minimax

            mock_mistake_repo = MagicMock()
            mock_mistake_repo.find_similar.return_value = sample_mistake
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.mistake_repo = mock_mistake_repo
            engine.correction_repo = mock_correction_repo

            result = await engine.detect_and_correct(
                student_id=sample_student_id,
                mistake="Wrong cron syntax */5",
                context={"command": "test"},
                severity="medium"
            )

            assert result["status"] == "existing_incremented"
            assert result["count"] == 2
            mock_mistake_repo.increment_count.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_and_correct_creates_new_mistake(
        self, sample_school_id, sample_student_id
    ):
        """Test detect_and_correct creates new mistake and correction"""
        with patch('core.database.get_db'), \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue') as mock_queue_cls, \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()

            mock_minimax = MagicMock()
            mock_minimax.analyze_mistake = AsyncMock(return_value={
                "root_cause": "Test root cause",
                "category": "test",
                "severity": "medium"
            })
            mock_minimax.generate_correction = AsyncMock(return_value={
                "correction": "Test correction",
                "explanation": "Test explanation",
                "code_example": "*/5 * * * *"
            })
            mock_get_minimax.return_value = mock_minimax

            mock_queue = MagicMock()
            mock_queue.enqueue = AsyncMock()
            mock_queue_cls.return_value = mock_queue

            mock_mistake_repo = MagicMock()
            mock_mistake_repo.find_similar.return_value = None
            mock_mistake_repo.create.return_value = {
                "id": "mistake-123",
                "student_id": sample_student_id
            }
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo.create.return_value = {
                "id": "correction-123",
                "student_id": sample_student_id
            }
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.mistake_repo = mock_mistake_repo
            engine.correction_repo = mock_correction_repo

            result = await engine.detect_and_correct(
                student_id=sample_student_id,
                mistake="Wrong cron syntax",
                context={"command": "test"},
                severity="high"
            )

            assert result["status"] == "correction_injected"
            assert result["mistake_id"] == "mistake-123"
            assert result["correction_id"] == "correction-123"

    @pytest.mark.asyncio
    async def test_detect_and_correct_handles_minimax_analysis_failure(
        self, sample_school_id, sample_student_id
    ):
        """Test detect_and_correct handles MiniMax analysis failure gracefully"""
        from llm.minimax import MiniMaxError

        with patch('core.database.get_db'), \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue') as mock_queue_cls, \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()

            mock_minimax = MagicMock()
            mock_minimax.analyze_mistake = AsyncMock(side_effect=MiniMaxError("API failed"))
            mock_minimax.generate_correction = AsyncMock(return_value={
                "correction": "Fallback correction",
                "explanation": "Fallback explanation",
                "code_example": None
            })
            mock_get_minimax.return_value = mock_minimax

            mock_queue = MagicMock()
            mock_queue.enqueue = AsyncMock()
            mock_queue_cls.return_value = mock_queue

            mock_mistake_repo = MagicMock()
            mock_mistake_repo.find_similar.return_value = None
            mock_mistake_repo.create.return_value = {"id": "mistake-123"}
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo.create.return_value = {"id": "correction-123"}
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.mistake_repo = mock_mistake_repo
            engine.correction_repo = mock_correction_repo

            result = await engine.detect_and_correct(
                student_id=sample_student_id,
                mistake="Test mistake",
                context={},
                severity="medium"
            )

            assert result["status"] == "correction_injected"
            assert result["analysis"]["root_cause"] == "Analysis unavailable"

    @pytest.mark.asyncio
    async def test_detect_and_correct_handles_minimax_correction_failure(
        self, sample_school_id, sample_student_id
    ):
        """Test detect_and_correct handles MiniMax correction generation failure"""
        from llm.minimax import MiniMaxError

        with patch('core.database.get_db'), \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue') as mock_queue_cls, \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()

            mock_minimax = MagicMock()
            mock_minimax.analyze_mistake = AsyncMock(return_value={
                "root_cause": "Test root cause",
                "category": "test",
                "severity": "medium"
            })
            mock_minimax.generate_correction = AsyncMock(side_effect=MiniMaxError("API failed"))
            mock_get_minimax.return_value = mock_minimax

            mock_queue = MagicMock()
            mock_queue.enqueue = AsyncMock()
            mock_queue_cls.return_value = mock_queue

            mock_mistake_repo = MagicMock()
            mock_mistake_repo.find_similar.return_value = None
            mock_mistake_repo.create.return_value = {"id": "mistake-123"}
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo.create.return_value = {"id": "correction-123"}
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.mistake_repo = mock_mistake_repo
            engine.correction_repo = mock_correction_repo

            result = await engine.detect_and_correct(
                student_id=sample_student_id,
                mistake="Test mistake",
                context={},
                severity="medium"
            )

            assert result["correction"]["correction"] == "Review the correct approach and try again"

    def test_get_active_corrections(self, sample_school_id, sample_student_id, sample_correction):
        """Test get_active_corrections returns non-learned corrections"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue'), \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()
            mock_db.execute.return_value = [sample_correction]
            mock_get_db.return_value = mock_db
            mock_get_minimax.return_value = MagicMock()

            mock_mistake_repo = MagicMock()
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.db = mock_db

            result = engine.get_active_corrections(sample_student_id)

            assert len(result) == 1
            assert result[0]["id"] == sample_correction["id"]

    def test_mark_learned(self, sample_school_id, sample_correction_id):
        """Test mark_learned updates correction status"""
        with patch('core.database.get_db') as mock_get_db, \
             patch('teacher.self_correction.get_minimax_client') as mock_get_minimax, \
             patch('core.message_queue.MessageQueue'), \
             patch('teacher.self_correction.MistakeRepository') as mock_mistake_repo_cls, \
             patch('teacher.self_correction.CorrectionRepository') as mock_correction_repo_cls:

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_get_minimax.return_value = MagicMock()

            mock_mistake_repo = MagicMock()
            mock_mistake_repo_cls.return_value = mock_mistake_repo

            mock_correction_repo = MagicMock()
            mock_correction_repo_cls.return_value = mock_correction_repo

            from teacher.self_correction import SelfCorrectionEngine
            engine = SelfCorrectionEngine(sample_school_id)
            engine.db = mock_db

            engine.mark_learned(sample_correction_id)

            mock_db.execute.assert_called_once()


class TestSelfCorrectionService:
    """Tests for SelfCorrectionService"""

    @pytest.mark.asyncio
    async def test_report_mistake_calls_engine(self, sample_school_id, sample_student_id):
        """Test report_mistake calls the engine"""
        with patch('teacher.self_correction.SelfCorrectionEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.detect_and_correct = AsyncMock(return_value={
                "status": "correction_injected",
                "mistake_id": "mistake-123",
                "correction_id": "correction-123"
            })
            mock_engine.escalation_threshold = 3
            mock_engine_cls.return_value = mock_engine

            from teacher.self_correction import SelfCorrectionService
            service = SelfCorrectionService(sample_school_id)
            service.engine = mock_engine

            result = await service.report_mistake(
                student_id=sample_student_id,
                mistake="Test mistake",
                context={"test": True},
                severity="medium"
            )

            assert result["status"] == "correction_injected"
            mock_engine.detect_and_correct.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_verification_cycle(self, sample_school_id, sample_student_id):
        """Test run_verification_cycle calls engine verification"""
        with patch('teacher.self_correction.SelfCorrectionEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.verify_corrections = AsyncMock(return_value={
                "verified": 2,
                "failed": 0,
                "pending": 1
            })
            mock_engine_cls.return_value = mock_engine

            from teacher.self_correction import SelfCorrectionService
            service = SelfCorrectionService(sample_school_id)
            service.engine = mock_engine

            result = await service.run_verification_cycle(sample_student_id)

            assert result["verified"] == 2
            mock_engine.verify_corrections.assert_called_once()

    def test_get_corrections(self, sample_school_id, sample_student_id):
        """Test get_corrections returns active corrections"""
        with patch('teacher.self_correction.SelfCorrectionEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.get_active_corrections.return_value = [
                {"id": "correction-1"},
                {"id": "correction-2"}
            ]
            mock_engine_cls.return_value = mock_engine

            from teacher.self_correction import SelfCorrectionService
            service = SelfCorrectionService(sample_school_id)
            service.engine = mock_engine

            result = service.get_corrections(sample_student_id)

            assert len(result) == 2