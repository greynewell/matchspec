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
    mann_whitney_u,
    permutation_test,
)
from .trends import calculate_moving_average, calculate_trends, detect_trend_direction

__all__ = [
    # Database
    "ResultsDatabase",
    # Trends
    "calculate_moving_average",
    "calculate_trends",
    "detect_trend_direction",
    # Statistical
    "bootstrap_confidence_interval",
    "chi_squared_test",
    "compare_resolution_rates",
    "effect_size_cohens_d",
    "mann_whitney_u",
    "permutation_test",
    # Comparison
    "ComparisonEngine",
    "compare_results_files",
    "format_comparison_table",
    # Error analysis
    "ErrorPatternAnalyzer",
    "identify_flaky_tasks",
    # Anomaly detection
    "detect_anomalies",
    "detect_metric_anomalies",
    # Correlation
    "analyze_metric_correlations",
    "find_strong_correlations",
    "pearson_correlation",
    "spearman_correlation",
    # Difficulty
    "aggregate_difficulty_stats",
    "estimate_difficulty",
    "estimate_task_difficulty_score",
    # A/B testing
    "ABTest",
    "run_ab_test",
    # Leaderboard
    "Leaderboard",
    "generate_leaderboard",
    # Metrics
    "MetricDefinition",
    "MetricsRegistry",
    # Regression detection
    "RegressionDetector",
]
