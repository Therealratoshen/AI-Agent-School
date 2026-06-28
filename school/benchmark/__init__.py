# Benchmark module — measure AI agent learning outcomes

from school.benchmark.runner import BenchmarkRunner, BenchmarkResult
from school.benchmark.tasks import (
    BENCHMARK_PASS_SCORE,
    BENCHMARK_CATEGORY_MIN_SCORE,
    get_benchmark_tasks,
)
from school.benchmark.report import format_report, format_comparison

__all__ = [
    "BenchmarkRunner",
    "BenchmarkResult",
    "BENCHMARK_PASS_SCORE",
    "BENCHMARK_CATEGORY_MIN_SCORE",
    "get_benchmark_tasks",
    "format_report",
    "format_comparison",
]
