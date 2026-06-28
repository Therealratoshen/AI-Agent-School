# Benchmark report formatting

from typing import Any, Dict

from school.benchmark.runner import BenchmarkResult


CATEGORY_LABELS = {
    "cron_fundamentals": "Cron Fundamentals",
    "heartbeat_monitoring": "Heartbeat Monitoring",
    "silent_failure_detection": "Silent Failure Detection",
    "auto_recovery": "Auto-Recovery",
    "production_patterns": "Production Patterns",
}


def format_report(result: BenchmarkResult) -> str:
    """Human-readable benchmark report."""
    lines = [
        "=" * 50,
        "AI AGENT SCHOOL — CRON HANDLING BENCHMARK",
        "=" * 50,
        f"Topic:        {result.topic}",
        f"Score:        {result.total_score:.0f}/{result.max_score:.0f} ({result.percentage:.1f}%)",
        f"Pass (≥70%):  {'YES' if result.passed else 'NO'}",
        f"Certified:    {'YES' if result.to_dict()['certified'] else 'NO'}",
    ]

    if result.baseline_percentage is not None:
        lines.append(f"Baseline:     {result.baseline_percentage:.1f}%")
    if result.learning_gain is not None:
        lines.append(f"Learning gain: +{result.learning_gain:.1f}%")

    lines.extend(["", "Category Breakdown:", "-" * 50])

    for cat, data in result.category_scores.items():
        label = CATEGORY_LABELS.get(cat, cat)
        status = "PASS" if data["passed"] else "FAIL"
        lines.append(
            f"  {label:<30} {data['percentage']:>5.1f}%  "
            f"({data['tasks_correct']}/{data['tasks_total']}) [{status}]"
        )

    failed = [r for r in result.task_results if not r["correct"]]
    if failed:
        lines.extend(["", "Areas to improve:", "-" * 50])
        for r in failed[:5]:
            lines.append(f"  • {r['question'][:60]}...")
            lines.append(f"    → {r['feedback']}")

    lines.append("=" * 50)
    return "\n".join(lines)


def format_comparison(comparison: Dict[str, Any]) -> str:
    lines = [
        "=" * 50,
        "BENCHMARK COMPARISON — BEFORE vs AFTER TRAINING",
        "=" * 50,
        f"Before training:  {comparison['baseline_percentage']:.1f}%",
        f"After training:   {comparison['trained_percentage']:.1f}%",
        f"Learning gain:    +{comparison['learning_gain']:.1f}%",
        f"Certified:        {'YES' if comparison['certified'] else 'NO'}",
        "",
        "Per-category improvement:",
    ]
    for cat, data in comparison["category_improvements"].items():
        label = CATEGORY_LABELS.get(cat, cat)
        lines.append(f"  {label:<30} {data['before']:>5.1f}% → {data['after']:>5.1f}% (+{data['gain']:.1f}%)")
    lines.append("=" * 50)
    return "\n".join(lines)
