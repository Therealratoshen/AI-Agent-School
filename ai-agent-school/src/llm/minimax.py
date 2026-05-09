# MiniMax LLM Client
# Production-grade client with retry, circuit breaker, and cost tracking

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import pybreaker

from core.config import get_settings


logger = structlog.get_logger(__name__)


class MiniMaxError(Exception):
    """Base exception for MiniMax errors"""
    pass


class MiniMaxRateLimitError(MiniMaxError):
    """Rate limit exceeded"""
    pass


class MiniMaxAPIError(MiniMaxError):
    """API returned an error"""
    pass


class MiniMaxCircuitBreaker:
    """Circuit breaker for MiniMax API calls"""

    def __init__(self):
        self.circuit = pybreaker.CircuitBreaker(
            fail_max=5,
            reset_timeout=60,
            exclude=[MiniMaxRateLimitError]
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function with circuit breaker"""
        try:
            return await self.circuit.call(func, *args, **kwargs)
        except pybreaker.CircuitBreakerError:
            raise MiniMaxError("Circuit breaker is open - service unavailable")
        except Exception as e:
            logger.error("minimax_call_failed", error=str(e))
            raise


class MiniMaxClient:
    """
    Production-grade MiniMax API client.

    Features:
    - Async HTTP requests
    - Automatic retry with exponential backoff
    - Circuit breaker for resilience
    - Token usage tracking
    - Cost estimation
    """

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.minimax.api_key
        self.base_url = settings.minimax.base_url
        self.model = settings.minimax.model
        self.timeout = settings.minimax.timeout

        self.circuit_breaker = MiniMaxCircuitBreaker()
        self._total_tokens_used = 0
        self._total_cost = 0.0

        # Token pricing (approximate, per 1K tokens)
        self._price_per_1k_input = 0.01
        self._price_per_1k_output = 0.03

    @property
    def total_tokens_used(self) -> int:
        return self._total_tokens_used

    @property
    def total_cost(self) -> float:
        return self._total_cost

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request"""
        return (
            (input_tokens / 1000) * self._price_per_1k_input +
            (output_tokens / 1000) * self._price_per_1k_output
        )

    async def _make_request(
        self,
        session: aiohttp.ClientSession,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Make API request with retry logic"""

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
        )
        async def _do_request():
            async with session.post(url, json=payload, headers=headers, timeout=self.timeout) as response:
                if response.status == 429:
                    raise MiniMaxRateLimitError("Rate limit exceeded")
                if response.status >= 400:
                    text = await response.text()
                    raise MiniMaxAPIError(f"API error {response.status}: {text}")

                return await response.json()

        return await _do_request()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Send a chat request to MiniMax.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            Dict with 'content', 'usage', 'model', 'cost' keys
        """
        async with aiohttp.ClientSession() as session:
            try:
                response = await self.circuit_breaker.call(
                    self._make_request,
                    session,
                    messages,
                    temperature,
                    max_tokens
                )

                # Extract response
                content = response["choices"][0]["message"]["content"]
                usage = response.get("usage", {})

                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

                # Track usage
                self._total_tokens_used += total_tokens
                cost = self._estimate_cost(input_tokens, output_tokens)
                self._total_cost += cost

                logger.info(
                    "minimax_request_completed",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=round(cost, 6)
                )

                return {
                    "content": content,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": total_tokens
                    },
                    "model": self.model,
                    "cost": cost
                }

            except pybreaker.CircuitBreakerError:
                logger.error("minimax_circuit_breaker_open")
                raise MiniMaxError("MiniMax service temporarily unavailable")
            except MiniMaxRateLimitError:
                logger.warning("minimax_rate_limited")
                raise
            except Exception as e:
                logger.error("minimax_request_failed", error=str(e))
                raise MiniMaxError(f"MiniMax request failed: {e}")

    # ============================================
    # Teaching-Specific Methods
    # ============================================

    async def analyze_mistake(
        self,
        mistake: str,
        context: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Analyze WHY a mistake happened using LLM.

        Returns:
            Dict with 'root_cause', 'category', 'severity'
        """
        system_prompt = """You are an AI debugging assistant specialized in cron job and agent operations.
Analyze the provided mistake and determine:
1. ROOT CAUSE: Why did this mistake happen?
2. CATEGORY: Is this a syntax error, logic error, environment issue, or knowledge gap?
3. SEVERITY: Is this low (minor), medium (workaround exists), high (blocks progress), or critical (security/safety)?

Respond in JSON format with keys: root_cause, category, severity"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Mistake: {mistake}\nContext: {context}\nHistory: {history}"}
        ]

        response = await self.chat(
            messages,
            temperature=0.3,
            max_tokens=500
        )

        import json
        try:
            result = json.loads(response["content"])
            return result
        except json.JSONDecodeError:
            return {
                "root_cause": response["content"][:200],
                "category": "unknown",
                "severity": "medium"
            }

    async def generate_correction(
        self,
        mistake: str,
        root_cause: str,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate a correction for a mistake.

        Returns:
            Dict with 'correction', 'explanation', 'code_example'
        """
        system_prompt = """You are an AI tutor specialized in cron jobs and agent operations.
Given a mistake and its root cause, generate:
1. CORRECTION: What should be done instead?
2. EXPLANATION: Why is this the correct approach?
3. CODE EXAMPLE: If applicable, show the correct code

Be specific and practical. Respond in JSON format with keys: correction, explanation, code_example"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Mistake: {mistake}\nRoot Cause: {root_cause}\nContext: {context}"}
        ]

        response = await self.chat(
            messages,
            temperature=0.5,
            max_tokens=800
        )

        import json
        try:
            result = json.loads(response["content"])
            return result
        except json.JSONDecodeError:
            return {
                "correction": "Review the correct approach and try again",
                "explanation": response["content"][:200],
                "code_example": None
            }

    async def generate_quiz_feedback(
        self,
        lesson_id: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        is_correct: bool
    ) -> str:
        """
        Generate personalized feedback for a quiz answer.

        Returns:
            String with feedback message
        """
        system_prompt = """You are an encouraging AI tutor.
Provide brief, helpful feedback on a student quiz answer.
- If correct: Acknowledge and briefly reinforce the concept
- If incorrect: Explain why the correct answer is right without being harsh

Keep feedback to 2-3 sentences maximum."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {question}\nStudent Answer: {student_answer}\nCorrect Answer: {correct_answer}\nIs Correct: {is_correct}"}
        ]

        response = await self.chat(
            messages,
            temperature=0.7,
            max_tokens=200
        )

        return response["content"]

    async def assess_progress(
        self,
        student_id: str,
        lessons_completed: int,
        total_lessons: int,
        corrections_learned: int,
        recent_mistakes: int,
        quiz_scores: List[float]
    ) -> Dict[str, Any]:
        """
        Assess if student is ready to graduate.

        Returns:
            Dict with 'ready', 'reason', 'recommendation', 'days_remaining'
        """
        system_prompt = """You are an AI graduation assessor.
Based on the student's training progress, determine if they are ready to graduate.

Consider:
- Completion of all lessons
- Low mistake count
- High quiz scores
- Corrections learned and applied

Respond in JSON format with keys:
- ready: boolean
- reason: string explaining your assessment
- recommendation: "graduate", "continue_training", or "additional_remedial"
- days_remaining: estimated days until ready (if not ready)"""

        avg_score = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""
Student Progress:
- Lessons Completed: {lessons_completed}/{total_lessons}
- Corrections Learned: {corrections_learned}
- Recent Mistakes: {recent_mistakes}
- Average Quiz Score: {avg_score:.1f}%
- Quiz Scores: {quiz_scores}
"""}
        ]

        response = await self.chat(
            messages,
            temperature=0.3,
            max_tokens=300
        )

        import json
        try:
            result = json.loads(response["content"])
            return result
        except json.JSONDecodeError:
            return {
                "ready": False,
                "reason": "Unable to assess",
                "recommendation": "continue_training",
                "days_remaining": 7
            }


# Singleton instance
_minimax_client: Optional[MiniMaxClient] = None


def get_minimax_client() -> MiniMaxClient:
    """Get MiniMax client singleton"""
    global _minimax_client
    if _minimax_client is None:
        _minimax_client = MiniMaxClient()
    return _minimax_client
