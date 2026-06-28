#!/usr/bin/env python3
"""
Run the Cron Handling benchmark to measure AI agent learning.

Modes:
  baseline   — score with no training (expect ~0%)
  trained    — score from student memory after lessons
  compare    — run teaching demo then show before/after
  validate   — verify benchmark tasks grade correctly (expect 100%)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from school.benchmark import BenchmarkRunner, format_report, format_comparison
from school.benchmark.solver import solve_from_memory, solve_from_lesson_manager


def run_baseline() -> dict:
    runner = BenchmarkRunner()
    result = runner.run_baseline()
    print(format_report(result))
    return result.to_dict()


def run_trained(memory_path: str) -> dict:
    runner = BenchmarkRunner()
    answers = solve_from_memory(memory_path)
    result = runner.run(answers)
    print(format_report(result))
    return result.to_dict()


def run_validate() -> dict:
    runner = BenchmarkRunner()
    answers = solve_from_lesson_manager()
    result = runner.run(answers)
    print(format_report(result))
    if result.percentage < 99:
        print("WARNING: Benchmark validation failed — expected ~100%")
        return result.to_dict()
    print("Benchmark validation OK (all tasks grade correctly)")
    return result.to_dict()


def run_compare(lessons: int = 5) -> dict:
    from scripts.run_teaching_demo import run_demo

    runner = BenchmarkRunner()
    baseline = runner.run_baseline()

    demo = run_demo(lessons_to_complete=lessons, cleanup=False)
    memory_path = demo.get("memory_path")
    if not memory_path:
        print("ERROR: teaching demo did not return memory_path")
        sys.exit(1)

    answers = solve_from_memory(memory_path)
    trained = runner.run(answers, baseline_percentage=baseline.percentage)
    comparison = runner.compare(baseline, trained)

    print(format_comparison(comparison))
    print()
    print(format_report(trained))

    import shutil
    if demo.get("tmpdir"):
        shutil.rmtree(demo["tmpdir"], ignore_errors=True)

    return {
        "demo": demo,
        "comparison": comparison,
        "trained": trained.to_dict(),
        "baseline": baseline.to_dict(),
    }


def main():
    parser = argparse.ArgumentParser(description="AI Agent School — Cron Handling Benchmark")
    parser.add_argument(
        "mode",
        nargs="?",
        default="compare",
        choices=["baseline", "trained", "compare", "validate"],
        help="Benchmark mode (default: compare)",
    )
    parser.add_argument(
        "--memory-path",
        default="./data/student_memory",
        help="Student memory path for 'trained' mode",
    )
    parser.add_argument(
        "--lessons",
        type=int,
        default=5,
        help="Lessons to complete in 'compare' mode (default: 5)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    if args.mode == "baseline":
        result = run_baseline()
    elif args.mode == "trained":
        result = run_trained(args.memory_path)
    elif args.mode == "validate":
        result = run_validate()
    else:
        result = run_compare(lessons=args.lessons)

    if args.json:
        print(json.dumps(result, indent=2))

    passed = (
        result.get("passed")
        or result.get("trained", {}).get("passed")
        or result.get("comparison", {}).get("certified")
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
