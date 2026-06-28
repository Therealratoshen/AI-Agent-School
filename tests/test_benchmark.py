# Benchmark tests — verify grading and learning measurement

import os
import sys
import tempfile
import json

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.benchmark import BenchmarkRunner, format_report
from school.benchmark.grader import grade_task, normalize_cron
from school.benchmark.solver import solve_from_memory, solve_from_lesson_manager
from school.benchmark.tasks import (
    BENCHMARK_PASS_SCORE,
    CRON_HANDLING_BENCHMARK,
)


class TestBenchmarkGrader:
    def test_multiple_choice_correct(self):
        task = CRON_HANDLING_BENCHMARK[0]
        result = grade_task(task, "Every 5 minutes")
        assert result["correct"] is True
        assert result["score"] == 1.0

    def test_multiple_choice_wrong(self):
        task = CRON_HANDLING_BENCHMARK[0]
        result = grade_task(task, "Every 5 hours")
        assert result["correct"] is False

    def test_cron_expression_normalization(self):
        assert normalize_cron("0 15 * * *") == normalize_cron("  0   15  * * *  ")

    def test_cron_expression_grading(self):
        task = next(t for t in CRON_HANDLING_BENCHMARK if t.id == "bench_cron_02")
        result = grade_task(task, "0 15 * * *")
        assert result["correct"] is True

    def test_free_text_required_terms(self):
        task = next(t for t in CRON_HANDLING_BENCHMARK if t.id == "bench_hb_03")
        result = grade_task(task, "Use HTTP ping and a file-based heartbeat")
        assert result["correct"] is True


class TestBenchmarkRunner:
    def test_baseline_is_zero(self):
        runner = BenchmarkRunner()
        result = runner.run_baseline()
        assert result.percentage == 0.0
        assert result.passed is False

    def test_perfect_score_passes(self):
        runner = BenchmarkRunner()
        answers = solve_from_lesson_manager()
        result = runner.run(answers)
        assert result.percentage >= 99.0
        assert result.passed is True
        assert result.to_dict()["certified"] is True

    def test_has_five_categories(self):
        runner = BenchmarkRunner()
        result = runner.run(solve_from_lesson_manager())
        assert len(result.category_scores) == 5

    def test_learning_gain(self):
        runner = BenchmarkRunner()
        baseline = runner.run_baseline()
        trained = runner.run(solve_from_lesson_manager(), baseline_percentage=baseline.percentage)
        assert trained.learning_gain is not None
        assert trained.learning_gain >= 99.0

    def test_partial_training_partial_score(self):
        runner = BenchmarkRunner()
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = os.path.join(tmpdir, "memory")
            os.makedirs(memory)
            lessons = {
                "cron_01": {"lesson_id": "cron_01", "title": "Cron Fundamentals"},
            }
            with open(os.path.join(memory, "lessons.json"), "w") as f:
                json.dump(lessons, f)

            answers = solve_from_memory(memory)
            result = runner.run(answers)
            assert 0 < result.percentage < 100
            assert result.category_scores["cron_fundamentals"]["passed"] is True
            assert result.category_scores["heartbeat_monitoring"]["passed"] is False


class TestBenchmarkReport:
    def test_format_report(self):
        runner = BenchmarkRunner()
        result = runner.run(solve_from_lesson_manager())
        report = format_report(result)
        assert "CRON HANDLING BENCHMARK" in report
        assert "Cron Fundamentals" in report


class TestBenchmarkTaskCoverage:
    def test_task_count(self):
        assert len(CRON_HANDLING_BENCHMARK) >= 18

    def test_all_categories_represented(self):
        categories = {t.category for t in CRON_HANDLING_BENCHMARK}
        assert len(categories) == 5

    def test_pass_threshold(self):
        assert BENCHMARK_PASS_SCORE == 70.0
