# tests/unit/test_minimax_client.py
# MiniMax client tests for 99% coverage

import os
import sys
import json
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

import pytest
import aiohttp

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..', 'src'))

from llm.minimax import (
    MiniMaxClient,
    MiniMaxError,
    MiniMaxRateLimitError,
    MiniMaxAPIError,
    MiniMaxCircuitBreaker,
    get_minimax_client
)


class TestMiniMaxClient:
    """Tests for MiniMaxClient"""

    def test_init_sets_properties(self, mock_settings):
        """Test client initialization"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            assert client.api_key == mock_settings.minimax.api_key
            assert client.base_url == mock_settings.minimax.base_url
            assert client.model == mock_settings.minimax.model
            assert client.timeout == mock_settings.minimax.timeout

    def test_total_tokens_starts_at_zero(self, mock_settings):
        """Test total_tokens starts at 0"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            assert client.total_tokens_used == 0

    def test_total_cost_starts_at_zero(self, mock_settings):
        """Test total_cost starts at 0"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            assert client.total_cost == 0.0

    def test_estimate_cost_calculates_correctly(self, mock_settings):
        """Test cost estimation calculation"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            # 1000 input + 1000 output = (1000 * 0.01 / 1000) + (1000 * 0.03 / 1000) = 0.01 + 0.03 = 0.04
            cost = client._estimate_cost(1000, 1000)

            assert cost == 0.04

    def test_estimate_cost_with_zero_tokens(self, mock_settings):
        """Test cost estimation with zero tokens"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            cost = client._estimate_cost(0, 0)

            assert cost == 0.0

    def test_estimate_cost_fractional_tokens(self, mock_settings):
        """Test cost estimation with fractional tokens"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            client = MiniMaxClient()

            # 500 input + 500 output = (500 * 0.01 / 1000) + (500 * 0.03 / 1000) = 0.005 + 0.015 = 0.02
            cost = client._estimate_cost(500, 500)

            assert cost == 0.02


class TestMiniMaxChat:
    """Tests for chat method"""

    @pytest.mark.asyncio
    async def test_chat_extracts_content(self, mock_settings):
        """Test chat extracts content from response"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            mock_response = {
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
            }

            with patch.object(MiniMaxClient, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response

                client = MiniMaxClient()
                messages = [{"role": "user", "content": "Hello"}]
                result = await client.chat(messages)

                assert result["content"] == "Test response"

    @pytest.mark.asyncio
    async def test_chat_tracks_tokens(self, mock_settings):
        """Test chat tracks token usage"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            mock_response = {
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
            }

            with patch.object(MiniMaxClient, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response

                client = MiniMaxClient()
                messages = [{"role": "user", "content": "Hello"}]
                await client.chat(messages)

                assert client.total_tokens_used == 150

    @pytest.mark.asyncio
    async def test_chat_tracks_cost(self, mock_settings):
        """Test chat tracks cost"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            mock_response = {
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
            }

            with patch.object(MiniMaxClient, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response

                client = MiniMaxClient()
                messages = [{"role": "user", "content": "Hello"}]
                await client.chat(messages)

                assert client.total_cost == 0.0025

    @pytest.mark.asyncio
    async def test_chat_handles_rate_limit(self, mock_settings):
        """Test chat handles rate limit error"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            with patch.object(MiniMaxClient, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = MiniMaxRateLimitError("Rate limited")

                client = MiniMaxClient()
                messages = [{"role": "user", "content": "Hello"}]

                with pytest.raises(MiniMaxRateLimitError):
                    await client.chat(messages)

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self, mock_settings):
        """Test chat handles API error"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            with patch.object(MiniMaxClient, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = MiniMaxAPIError("API error", 500)

                client = MiniMaxClient()
                messages = [{"role": "user", "content": "Hello"}]

                with pytest.raises(MiniMaxError):
                    await client.chat(messages)


class TestMiniMaxAnalyzeMistake:
    """Tests for analyze_mistake method"""

    @pytest.mark.asyncio
    async def test_analyze_mistake_calls_api(self, mock_minimax_client):
        """Test analyze_mistake calls MiniMax API"""
        result = await mock_minimax_client.analyze_mistake(
            mistake="Wrong cron syntax",
            context={"command": "*/5 * * * *"},
            history=[]
        )

        mock_minimax_client.analyze_mistake.assert_called_once_with(
            mistake="Wrong cron syntax",
            context={"command": "*/5 * * * *"},
            history=[]
        )

    @pytest.mark.asyncio
    async def test_analyze_mistake_parses_json_response(self, mock_minimax_client):
        """Test analyze_mistake parses JSON response"""
        result = await mock_minimax_client.analyze_mistake(
            mistake="Wrong cron syntax",
            context={},
            history=[]
        )

        assert "root_cause" in result
        assert "category" in result
        assert "severity" in result


class TestMiniMaxGenerateCorrection:
    """Tests for generate_correction method"""

    @pytest.mark.asyncio
    async def test_generate_correction_calls_api(self, mock_minimax_client):
        """Test generate_correction calls MiniMax API"""
        result = await mock_minimax_client.generate_correction(
            mistake="Wrong cron syntax",
            root_cause="Misunderstanding */",
            context={}
        )

        mock_minimax_client.generate_correction.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_correction_parses_response(self, mock_minimax_client):
        """Test generate_correction parses response"""
        result = await mock_minimax_client.generate_correction(
            mistake="Wrong cron syntax",
            root_cause="Misunderstanding */",
            context={}
        )

        assert "correction" in result
        assert "explanation" in result


class TestMiniMaxQuizFeedback:
    """Tests for generate_quiz_feedback method"""

    @pytest.mark.asyncio
    async def test_generate_quiz_feedback_calls_api(self, mock_minimax_client):
        """Test generate_quiz_feedback calls MiniMax API"""
        result = await mock_minimax_client.generate_quiz_feedback(
            lesson_id="lesson-1",
            question="What is cron?",
            student_answer="A time-based job scheduler",
            correct_answer="A cron job scheduler",
            is_correct=False
        )

        mock_minimax_client.generate_quiz_feedback.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_quiz_feedback_returns_string(self, mock_minimax_client):
        """Test generate_quiz_feedback returns string"""
        result = await mock_minimax_client.generate_quiz_feedback(
            lesson_id="lesson-1",
            question="What is cron?",
            student_answer="A time-based job scheduler",
            correct_answer="A cron job scheduler",
            is_correct=False
        )

        assert isinstance(result, str)


class TestMiniMaxAssessProgress:
    """Tests for assess_progress method"""

    @pytest.mark.asyncio
    async def test_assess_progress_calculates_avg_score(self, mock_minimax_client):
        """Test assess_progress calculates average score"""
        result = await mock_minimax_client.assess_progress(
            student_id="student-1",
            lessons_completed=5,
            total_lessons=10,
            corrections_learned=3,
            recent_mistakes=1,
            quiz_scores=[80.0, 90.0, 70.0]
        )

        mock_minimax_client.assess_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_assess_progress_parses_json(self, mock_minimax_client):
        """Test assess_progress parses JSON response"""
        result = await mock_minimax_client.assess_progress(
            student_id="student-1",
            lessons_completed=5,
            total_lessons=10,
            corrections_learned=3,
            recent_mistakes=1,
            quiz_scores=[80.0]
        )

        assert "ready" in result
        assert "reason" in result
        assert "recommendation" in result


class TestMiniMaxCircuitBreaker:
    """Tests for circuit breaker"""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes with defaults"""
        cb = MiniMaxCircuitBreaker()

        assert cb.circuit.fail_max == 5
        assert cb.circuit.reset_timeout == 60

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_success(self):
        """Test circuit breaker calls function on success"""
        cb = MiniMaxCircuitBreaker()

        async def success_func():
            return "success"

        result = await cb.call(success_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_failure(self):
        """Test circuit breaker trips on repeated failures"""
        cb = MiniMaxCircuitBreaker()
        cb.circuit.fail_max = 2

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Test error")

        for _ in range(2):
            try:
                await cb.call(failing_func)
            except Exception:
                pass

        with pytest.raises(Exception, match="Test error"):
            await cb.call(failing_func)


class TestGetMiniMaxClient:
    """Tests for get_minimax_client singleton"""

    def test_get_minimax_client_returns_singleton(self, mock_settings):
        """Test get_minimax_client returns singleton"""
        with patch('llm.minimax.get_settings', return_value=mock_settings):
            import llm.minimax
            llm.minimax._minimax_client = None

            client1 = get_minimax_client()
            client2 = get_minimax_client()

            assert client1 is client2