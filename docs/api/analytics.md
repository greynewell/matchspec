---
faq:
  - q: "How do I store and query historical benchmark results?"
    a: "Use ResultsDatabase, a SQLite-backed storage class. Call store_run() to save evaluation results, list_runs() to query them with filters, and get_trends() to retrieve time-series data for trend analysis."
  - q: "How do I compare results across multiple models?"
    a: "Use ComparisonEngine. Add labeled result sets with add_results(), then call compare() to get summary tables, pairwise comparisons, rankings, and unique win analysis. Use get_cost_performance_frontier() for Pareto-optimal models."
  - q: "How do I detect performance regressions?"
    a: "Use RegressionDetector. Call detect(current, baseline) to compare resolution rate, cost, latency, and token usage. It performs chi-squared significance testing and reports per-task regressions."
  - q: "What statistical tests are available?"
    a: "The analytics module provides chi_squared_test, bootstrap_confidence_interval, effect_size_cohens_d, mann_whitney_u, and permutation_test -- all implemented in pure Python with no external dependencies."
---

# Analytics API Reference

The `mcpbr.analytics` package provides comprehensive statistical analysis, historical tracking, and comparison tools for benchmark results. All calculations use only the Python standard library -- no NumPy or SciPy required.

```python
from mcpbr.analytics import (
    ResultsDatabase,
    ComparisonEngine,
    RegressionDetector,
    ABTest,
    Leaderboard,
    MetricsRegistry,
)
```

---

## ResultsDatabase

SQLite-backed persistent storage for evaluation runs and per-task results.

::: mcpbr.analytics.ResultsDatabase
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - store_run
        - get_run
        - list_runs
        - get_task_results
        - delete_run
        - get_trends
        - cleanup
        - close

### Usage

```python
from mcpbr.analytics import ResultsDatabase

# Open or create database (context manager supported)
with ResultsDatabase("my_results.db") as db:
    # Store a run
    run_id = db.store_run(results_data)

    # Query runs
    runs = db.list_runs(limit=10, benchmark="swe-bench-verified")
    run = db.get_run(run_id)

    # Get per-task results
    task_results = db.get_task_results(run_id)

    # Get trend data for charting
    trends = db.get_trends(benchmark="swe-bench-verified", model="sonnet")

    # Clean up old data
    deleted = db.cleanup(max_age_days=90)
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `store_run(results_data)` | `int` | Store evaluation results, returns run ID |
| `get_run(run_id)` | `dict \| None` | Retrieve a specific run by ID |
| `list_runs(limit, benchmark, model, provider)` | `list[dict]` | List runs with optional filtering |
| `get_task_results(run_id)` | `list[dict]` | Get per-task results for a run |
| `delete_run(run_id)` | `bool` | Delete a run and its task results |
| `get_trends(benchmark, model, limit)` | `list[dict]` | Get time-series trend data |
| `cleanup(max_age_days)` | `int` | Delete runs older than max_age_days |
| `close()` | `None` | Close the database connection |

### Database Schema

The database has two tables:

**runs** -- One row per evaluation run:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-incremented primary key |
| `timestamp` | TEXT | ISO 8601 timestamp |
| `benchmark` | TEXT | Benchmark name |
| `model` | TEXT | Model identifier |
| `provider` | TEXT | Provider name |
| `resolution_rate` | REAL | Overall resolution rate |
| `total_cost` | REAL | Total cost in USD |
| `total_tasks` | INTEGER | Number of tasks evaluated |
| `resolved_tasks` | INTEGER | Number of tasks resolved |
| `metadata_json` | TEXT | Full metadata as JSON |

**task_results** -- One row per task per run:

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | INTEGER | Foreign key to runs |
| `instance_id` | TEXT | Task identifier |
| `resolved` | INTEGER | 1 if resolved, 0 otherwise |
| `cost` | REAL | Task cost in USD |
| `tokens_input` | INTEGER | Input tokens used |
| `tokens_output` | INTEGER | Output tokens used |
| `runtime_seconds` | REAL | Task runtime |
| `error` | TEXT | Error message if failed |

---

## Statistical Tests

Pure Python implementations of common statistical tests for comparing benchmark results.

### chi_squared_test()

Compare two proportions (resolution rates) using a 2x2 chi-squared test.

```python
from mcpbr.analytics import chi_squared_test

result = chi_squared_test(
    success_a=45, total_a=100,
    success_b=60, total_b=100,
)
print(f"Chi2: {result['chi2']:.4f}")
print(f"p-value: {result['p_value']:.4f}")
print(f"Significant: {result['significant']}")
print(f"Effect size (phi): {result['effect_size']:.3f}")
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `success_a` | `int` | Successes in group A |
| `total_a` | `int` | Total observations in group A |
| `success_b` | `int` | Successes in group B |
| `total_b` | `int` | Total observations in group B |
| `significance_level` | `float` | Alpha threshold (default: 0.05) |

**Returns:** `dict` with `chi2`, `p_value`, `significant`, `effect_size` (phi coefficient).

### bootstrap_confidence_interval()

Bootstrap confidence interval for a metric.

```python
from mcpbr.analytics import bootstrap_confidence_interval

ci = bootstrap_confidence_interval(
    values=[0.85, 0.90, 0.78, 0.92, 0.88, 0.82],
    confidence=0.95,
    n_bootstrap=1000,
)
print(f"Mean: {ci['mean']:.3f}")
print(f"95% CI: [{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}]")
print(f"Std Error: {ci['std_error']:.4f}")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `values` | `list[float]` | (required) | Observed metric values |
| `confidence` | `float` | `0.95` | Confidence level |
| `n_bootstrap` | `int` | `1000` | Number of resamples |

**Returns:** `dict` with `mean`, `ci_lower`, `ci_upper`, `std_error`.

### effect_size_cohens_d()

Cohen's d effect size between two groups.

```python
from mcpbr.analytics import effect_size_cohens_d

d = effect_size_cohens_d(
    group_a=[0.85, 0.90, 0.88, 0.92],
    group_b=[0.70, 0.75, 0.72, 0.68],
)
print(f"Cohen's d: {d:.3f}")
# Interpretation: |d| < 0.2 negligible, 0.2-0.5 small, 0.5-0.8 medium, >= 0.8 large
```

### mann_whitney_u()

Non-parametric Mann-Whitney U test for comparing two independent samples.

```python
from mcpbr.analytics import mann_whitney_u

result = mann_whitney_u(
    group_a=[0.85, 0.90, 0.88, 0.92, 0.87],
    group_b=[0.70, 0.75, 0.72, 0.68, 0.74],
)
print(f"U: {result['u_statistic']:.1f}, p={result['p_value']:.4f}")
print(f"Significant: {result['significant']}")
```

### permutation_test()

Permutation test for difference in means between two groups.

```python
from mcpbr.analytics import permutation_test

result = permutation_test(
    group_a=[0.85, 0.90, 0.88],
    group_b=[0.70, 0.75, 0.72],
    n_permutations=5000,
)
print(f"Observed diff: {result['observed_diff']:.4f}")
print(f"p-value: {result['p_value']:.4f}")
```

### compare_resolution_rates()

Comprehensive comparison of two result sets with chi-squared testing, effect sizes, and a human-readable summary.

```python
from mcpbr.analytics import compare_resolution_rates

comparison = compare_resolution_rates(
    results_a={"resolved": 45, "total": 100, "name": "Server A"},
    results_b={"resolved": 38, "total": 100, "name": "Server B"},
)
print(comparison["summary"])
# "Server A (45.0%) vs Server B (38.0%): Server A is 7.0pp higher.
#  Difference is not significant (p=0.3123, phi=0.072)."
```

---

## ComparisonEngine

Compare evaluation results across multiple models with summary tables, rankings, Pareto frontiers, and pairwise analysis.

::: mcpbr.analytics.ComparisonEngine
    options:
      show_root_heading: true
      show_source: false
      members:
        - add_results
        - compare
        - get_cost_performance_frontier
        - get_winner_analysis

### Usage

```python
from mcpbr.analytics import ComparisonEngine

engine = ComparisonEngine()
engine.add_results("claude-sonnet", sonnet_results)
engine.add_results("gpt-4o", gpt4o_results)
engine.add_results("gemini-2.0-flash", gemini_results)

# Full comparison
comparison = engine.compare()
print(comparison["models"])          # ["claude-sonnet", "gpt-4o", "gemini-2.0-flash"]
print(comparison["summary_table"])   # Per-model summary metrics
print(comparison["rankings"])        # by_rate, by_cost_efficiency, by_speed
print(comparison["unique_wins"])     # Tasks only one model resolved
print(comparison["pairwise"])        # All pairwise comparisons

# Pareto-optimal models (cost vs resolution rate)
frontier = engine.get_cost_performance_frontier()
for point in frontier:
    print(f"{point['label']}: rate={point['rate']:.1%}, cost=${point['cost']:.2f}")

# Winner on each metric
winners = engine.get_winner_analysis()
for metric, info in winners.items():
    print(f"{metric}: {info['winner']} ({info['value']})")
```

### Convenience Functions

```python
from mcpbr.analytics import compare_results_files, format_comparison_table

# Compare JSON result files directly
comparison = compare_results_files(
    ["results_sonnet.json", "results_gpt4o.json"],
    labels=["Claude Sonnet", "GPT-4o"],
)

# Format as ASCII table
print(format_comparison_table(comparison))
```

---

## RegressionDetector

Detect performance regressions between evaluation runs across multiple dimensions.

::: mcpbr.analytics.RegressionDetector
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - detect
        - format_report

### Usage

```python
from mcpbr.analytics import RegressionDetector

detector = RegressionDetector(threshold=0.05, significance_level=0.05)
result = detector.detect(current_results, baseline_results)

# Check overall status
if result["overall_status"] == "fail":
    print("REGRESSION DETECTED!")
elif result["overall_status"] == "warning":
    print("Warning: potential issues")
else:
    print("All clear")

# Inspect specific regressions
print(result["score_regression"])     # Resolution rate analysis
print(result["cost_regression"])      # Cost change analysis
print(result["latency_regression"])   # Latency change analysis
print(result["token_regression"])     # Token usage change analysis
print(result["task_regressions"])     # Per-task regressions
print(result["task_improvements"])    # Per-task improvements

# Human-readable report
print(detector.format_report())
```

### Detection Thresholds

| Dimension | Regression Threshold | Description |
|-----------|---------------------|-------------|
| Resolution rate | > 5pp decrease + statistically significant | Chi-squared test at alpha=0.05 |
| Cost | > 20% increase | Percentage increase in total cost |
| Latency | > 25% increase | Percentage increase in average runtime |
| Token usage | > 25% increase | Percentage increase in average tokens |

### Overall Status

| Status | Meaning |
|--------|---------|
| `"pass"` | No regressions detected |
| `"warning"` | Cost, latency, or token regression; or per-task regressions |
| `"fail"` | Statistically significant resolution rate regression |

---

## ABTest

A/B testing framework for comparing two MCP server configurations.

::: mcpbr.analytics.ABTest
    options:
      show_root_heading: true
      show_source: false
      members:
        - __init__
        - add_control
        - add_treatment
        - analyze
        - format_report

### Usage

```python
from mcpbr.analytics import ABTest

test = ABTest(
    name="Filesystem v2 vs v1",
    control_label="v1 (current)",
    treatment_label="v2 (candidate)",
)
test.add_control(results_v1)
test.add_treatment(results_v2)

analysis = test.analyze()
print(f"Winner: {analysis['winner']}")
print(f"Rate difference: {analysis['rate_difference']:+.4f}")
print(f"Significant: {analysis['statistical_significance']['significant']}")
print(f"Recommendation: {analysis['recommendation']}")

# Formatted report
print(test.format_report())
```

### Quick A/B Test

```python
from mcpbr.analytics import run_ab_test

result = run_ab_test(results_a, results_b, test_name="Quick Comparison")
print(result["winner"])
print(result["recommendation"])
```

---

## Leaderboard

Generate ranked leaderboards from multiple evaluation results.

::: mcpbr.analytics.Leaderboard
    options:
      show_root_heading: true
      show_source: false
      members:
        - add_entry
        - generate
        - format_table
        - format_markdown

### Usage

```python
from mcpbr.analytics import Leaderboard

lb = Leaderboard()
lb.add_entry("Claude Sonnet", results_sonnet)
lb.add_entry("GPT-4o", results_gpt4o)
lb.add_entry("Gemini Flash", results_gemini)

# Generate sorted leaderboard
entries = lb.generate(sort_by="resolution_rate")
for entry in entries:
    print(f"#{entry['rank']} {entry['label']}: {entry['resolution_rate']:.1%}")

# ASCII table output
print(lb.format_table(sort_by="resolution_rate"))

# Markdown table (for GitHub/docs)
print(lb.format_markdown(sort_by="resolution_rate"))
```

### Sort Keys

| Key | Direction | Description |
|-----|-----------|-------------|
| `resolution_rate` | Higher is better | Fraction of tasks resolved |
| `resolved` | Higher is better | Absolute number of resolved tasks |
| `total_cost` | Lower is better | Total cost in USD |
| `cost_per_resolved` | Lower is better | Cost per resolved task |
| `avg_tokens` | Lower is better | Average tokens per task |
| `avg_runtime` | Lower is better | Average runtime per task |

### Quick Leaderboard

```python
from mcpbr.analytics import generate_leaderboard

entries = generate_leaderboard([
    ("Claude Sonnet", results_sonnet),
    ("GPT-4o", results_gpt4o),
], sort_by="resolution_rate")
```

---

## MetricsRegistry

Registry of metric definitions with built-in defaults and support for custom metrics.

::: mcpbr.analytics.MetricsRegistry
    options:
      show_root_heading: true
      show_source: false
      members:
        - register
        - calculate_all
        - get_metric
        - list_metrics

### Built-in Metrics

| Metric | Unit | Higher is Better | Description |
|--------|------|-------------------|-------------|
| `resolution_rate` | ratio | Yes | Fraction of tasks resolved |
| `cost_per_resolution` | USD | No | Total cost / resolved count |
| `avg_tokens_per_task` | tokens | No | Average total tokens per task |
| `tool_failure_rate` | ratio | No | Tool failures / total tool calls |
| `efficiency_score` | score | No | resolution_rate / (total_cost + 0.01) |

### Usage

```python
from mcpbr.analytics import MetricsRegistry, MetricDefinition

registry = MetricsRegistry()

# Calculate all built-in metrics
metrics = registry.calculate_all(results_data)
print(f"Resolution rate: {metrics['resolution_rate']:.1%}")
print(f"Efficiency: {metrics['efficiency_score']:.2f}")

# Register a custom metric
registry.register(MetricDefinition(
    name="cost_per_token",
    description="Average cost per 1000 tokens",
    unit="USD/1k tokens",
    calculate=lambda data: (
        sum(t.get("mcp", {}).get("cost", 0) for t in data.get("tasks", [])) /
        max(sum(
            t.get("mcp", {}).get("tokens", {}).get("input", 0) +
            t.get("mcp", {}).get("tokens", {}).get("output", 0)
            for t in data.get("tasks", [])
        ), 1) * 1000
    ),
    higher_is_better=False,
))

# List all registered metrics
print(registry.list_metrics())
```

---

## TrendAnalysis

Time-series trend analysis for evaluation results.

### calculate_trends()

Calculate trend information from a list of run summaries.

```python
from mcpbr.analytics import calculate_trends

# runs from ResultsDatabase.get_trends()
trends = calculate_trends(runs)
print(f"Direction: {trends['direction']}")  # "improving", "declining", "stable"
print(trends["resolution_rate_trend"])      # [{timestamp, rate}, ...]
print(trends["cost_trend"])                 # [{timestamp, cost}, ...]
print(trends["moving_averages"])            # 3-point moving averages
```

### detect_trend_direction()

Determine whether a series of values is improving, declining, or stable using linear regression.

```python
from mcpbr.analytics import detect_trend_direction

direction = detect_trend_direction([0.40, 0.42, 0.45, 0.48, 0.50])
print(direction)  # "improving"
```

### calculate_moving_average()

Compute a simple moving average over a list of values.

```python
from mcpbr.analytics import calculate_moving_average

ma = calculate_moving_average([0.40, 0.42, 0.45, 0.48, 0.50], window=3)
# [None, None, 0.4233..., 0.45, 0.4766...]
```

---

## AnomalyDetection

Statistical methods to identify outlier values in benchmark metrics.

### detect_anomalies()

Detect anomalous values using z-score, IQR, or MAD methods.

```python
from mcpbr.analytics import detect_anomalies

anomalies = detect_anomalies(
    values=[0.5, 0.6, 0.55, 0.58, 5.0, 0.52],
    method="zscore",    # "zscore", "iqr", or "mad"
    threshold=2.0,
)
for a in anomalies:
    print(f"Index {a['index']}: value={a['value']}, score={a['score']:.2f}")
```

| Method | Description | Threshold Meaning |
|--------|-------------|-------------------|
| `zscore` | Z-score exceeds threshold | Number of standard deviations |
| `iqr` | IQR fence method | Fence multiplier (commonly 1.5) |
| `mad` | Median absolute deviation | Number of MADs |

### detect_metric_anomalies()

Run anomaly detection across standard benchmark metrics (cost, tokens, runtime, iterations).

```python
from mcpbr.analytics import detect_metric_anomalies

anomalies = detect_metric_anomalies(results_data)
print(f"Cost anomalies: {len(anomalies['cost'])}")
print(f"Token anomalies: {len(anomalies['tokens'])}")
print(f"Runtime anomalies: {len(anomalies['runtime'])}")
print(f"Iteration anomalies: {len(anomalies['iterations'])}")
```

---

## CorrelationAnalysis

Compute correlations between evaluation metrics.

### pearson_correlation()

Compute the Pearson correlation coefficient between two sequences.

```python
from mcpbr.analytics import pearson_correlation

result = pearson_correlation(
    x=[100, 200, 300, 400, 500],
    y=[0.5, 1.1, 1.4, 2.0, 2.5],
)
print(f"r = {result['r']:.3f}, R^2 = {result['r_squared']:.3f}, p = {result['p_value']:.4f}")
```

### spearman_correlation()

Compute the Spearman rank correlation (non-parametric, handles non-linear relationships).

```python
from mcpbr.analytics import spearman_correlation

result = spearman_correlation(x=[1, 2, 3, 4, 5], y=[5, 6, 7, 8, 7])
```

### analyze_metric_correlations()

Compute all pairwise Pearson correlations between standard metrics extracted from results.

```python
from mcpbr.analytics import analyze_metric_correlations, find_strong_correlations

correlations = analyze_metric_correlations(results_data)
# Correlations between: cost, tokens_input, tokens_output, iterations,
#                        runtime_seconds, tool_calls

# Filter for strong correlations
strong = find_strong_correlations(correlations, threshold=0.7)
for c in strong:
    print(f"{c['pair']}: r={c['r']:.3f} ({c['direction']})")
```

---

## ErrorPatternAnalyzer

Analyze error patterns across benchmark results with clustering, temporal analysis, and recommendations.

::: mcpbr.analytics.ErrorPatternAnalyzer
    options:
      show_root_heading: true
      show_source: false
      members:
        - analyze
        - cluster_errors

### Usage

```python
from mcpbr.analytics import ErrorPatternAnalyzer

analyzer = ErrorPatternAnalyzer()
analysis = analyzer.analyze(task_results)

print(f"Total errors: {analysis['total_errors']}")

# Error clusters (grouped by similarity)
for cluster in analysis["error_clusters"]:
    print(f"  {cluster['category']}: {cluster['count']}x - {cluster['pattern'][:80]}")

# Temporal patterns
if analysis["temporal_patterns"]["increasing"]:
    print("Warning: errors increasing over iterations")

# Tool-error correlation
for tool, rate in analysis["tool_error_correlation"].items():
    if rate > 0.3:
        print(f"  High error rate tool: {tool} ({rate:.0%})")

# Actionable recommendations
for rec in analysis["recommendations"]:
    print(f"  - {rec}")
```

### Error Categories

The analyzer automatically categorizes errors into:

| Category | Pattern Keywords |
|----------|-----------------|
| `timeout` | timeout, timed out, deadline |
| `authentication` | auth, unauthorized, 401, 403 |
| `rate_limit` | rate limit, 429, throttle |
| `connection` | connection, refused, DNS, network |
| `validation` | invalid, validation, schema, parse |
| `permission` | permission, denied, access |
| `unknown` | Everything else |

### identify_flaky_tasks()

Identify tasks with inconsistent outcomes across multiple runs.

```python
from mcpbr.analytics import identify_flaky_tasks

flaky = identify_flaky_tasks([results_run1, results_run2, results_run3])
for task in flaky:
    if task["flaky"]:
        print(f"{task['instance_id']}: pass_rate={task['pass_rate']:.0%} over {task['run_count']} runs")
```

---

## DifficultyEstimation

Estimate per-task difficulty based on resolution rates, resource usage, and runtime.

### estimate_difficulty()

Score each task's difficulty on a 0-1 scale.

```python
from mcpbr.analytics import estimate_difficulty, aggregate_difficulty_stats

difficulties = estimate_difficulty(results_data)
for d in difficulties[:5]:
    print(f"{d['instance_id']}: {d['difficulty_level']} ({d['difficulty_score']:.2f})")

# Aggregate statistics
stats = aggregate_difficulty_stats(difficulties)
print(f"Distribution: {stats['distribution']}")
print(f"Avg difficulty: {stats['avg_difficulty']:.2f}")
print(f"Hardest tasks: {[t['instance_id'] for t in stats['hardest_tasks']]}")
```

### Difficulty Levels

| Score Range | Level |
|-------------|-------|
| 0.00 - 0.25 | easy |
| 0.25 - 0.50 | medium |
| 0.50 - 0.75 | hard |
| 0.75 - 1.00 | very_hard |

### estimate_task_difficulty_score()

Score a single task's difficulty given its metrics and run averages.

```python
from mcpbr.analytics import estimate_task_difficulty_score

score = estimate_task_difficulty_score(
    resolved=False,
    cost=0.15,
    tokens=50000,
    iterations=8,
    runtime=250.0,
    avg_cost=0.10,
    avg_tokens=30000,
    avg_iterations=5,
    avg_runtime=180.0,
)
print(f"Difficulty: {score:.2f}")  # Higher = harder
```
