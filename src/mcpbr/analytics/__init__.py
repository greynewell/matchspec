"""Analytics module for mcpbr historical results tracking and analysis.

Provides:
- SQLite-based historical results database
- Time-series trend analysis
- Statistical significance testing
- Multi-model comparison engine
- Error pattern analysis and anomaly detection
- Correlation analysis and difficulty estimation
- A/B testing framework
- Leaderboard generation
- Performance regression detection
- Custom metrics registry
"""

from __future__ import annotations

from .ab_testing import ABTest, run_ab_test
from .anomaly import detect_anomalies, detect_metric_anomalies
from .comparison import ComparisonEngine, compare_results_files, format_comparison_table
from .correlation import (
    analyze_metric_correlations,
    find_strong_correlations,
    pearson_correlation,
    spearman_correlation,
)
from .database import ResultsDatabase
from .difficulty import (
    aggregate_difficulty_stats,
    estimate_difficulty,
    estimate_task_difficulty_score,
)
from .error_analysis import ErrorPatternAnalyzer, identify_flaky_tasks
from .leaderboard import Leaderboard, generate_leaderboard
from .metrics import MetricDefinition, MetricsRegistry
from .regression_detector import RegressionDetector
from .statistical import (
    bootstrap_confidence_interval,
    chi_squared_test,
    compare_resolution_rates,
    effect_size_cohens_d,
    interpret_effect_size,
    mann_whitney_u,
    permutation_test,
    wilson_score_interval,
)
from .trends import calculate_moving_average, calculate_trends, detect_trend_direction

__all__ = [
    "ABTest",
    "ComparisonEngine",
    "ErrorPatternAnalyzer",
    "Leaderboard",
    "MetricDefinition",
    "MetricsRegistry",
    "RegressionDetector",
    "ResultsDatabase",
    "aggregate_difficulty_stats",
    "analyze_metric_correlations",
    "bootstrap_confidence_interval",
    "calculate_moving_average",
    "calculate_trends",
    "chi_squared_test",
    "compare_resolution_rates",
    "compare_results_files",
    "detect_anomalies",
    "detect_metric_anomalies",
    "detect_trend_direction",
    "effect_size_cohens_d",
    "estimate_difficulty",
    "estimate_task_difficulty_score",
    "find_strong_correlations",
    "format_comparison_table",
    "generate_leaderboard",
    "identify_flaky_tasks",
    "interpret_effect_size",
    "mann_whitney_u",
    "pearson_correlation",
    "permutation_test",
    "run_ab_test",
    "spearman_correlation",
    "wilson_score_interval",
]
