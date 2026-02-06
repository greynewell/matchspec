"""Prometheus metrics formatting and file export.

Produces metrics in the Prometheus exposition format for scraping or file-based
consumption.
"""

from pathlib import Path
from typing import Any


def format_metric(
    name: str,
    value: int | float,
    labels: dict[str, str] | None = None,
    help_text: str | None = None,
    metric_type: str | None = None,
) -> str:
    """Format a single metric in Prometheus exposition format.

    Args:
        name: Metric name (e.g., 'mcpbr_resolution_rate').
        value: Metric value.
        labels: Optional label key-value pairs.
        help_text: Optional HELP line text.
        metric_type: Optional TYPE line (gauge, counter, histogram, summary).

    Returns:
        Formatted Prometheus metric string.
    """
    lines = []

    if help_text:
        lines.append(f"# HELP {name} {help_text}")

    if metric_type:
        lines.append(f"# TYPE {name} {metric_type}")

    if labels:
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        lines.append(f"{name}{{{label_str}}} {value}")
    else:
        lines.append(f"{name} {value}")

    return "\n".join(lines)


def export_metrics(
    results: dict[str, Any],
    output_path: Path | None = None,
) -> str:
    """Export evaluation results as Prometheus metrics.

    Args:
        results: Evaluation results dictionary with metadata and summary.
        output_path: Optional file path to write metrics to.

    Returns:
        Complete Prometheus exposition format string.
    """
    config = results.get("metadata", {}).get("config", {})
    labels = {
        "benchmark": config.get("benchmark", "unknown"),
        "model": config.get("model", "unknown"),
    }

    mcp = results.get("summary", {}).get("mcp", {})
    baseline = results.get("summary", {}).get("baseline", {})

    # Group all samples per metric family (Prometheus spec requires contiguous families)
    metric_families = [
        ("mcpbr_resolution_rate", "Task resolution rate", "gauge", "rate"),
        ("mcpbr_tasks_total", "Total tasks evaluated", "gauge", "total"),
        ("mcpbr_tasks_resolved", "Tasks resolved successfully", "gauge", "resolved"),
        ("mcpbr_total_cost", "Total cost in USD", "gauge", "total_cost"),
    ]

    lines = []
    for metric_name, help_text, metric_type, key in metric_families:
        mcp_labels = {**labels, "agent": "mcp"}
        mcp_sample = format_metric(
            metric_name,
            mcp.get(key, 0),
            labels=mcp_labels,
            help_text=help_text,
            metric_type=metric_type,
        )
        if baseline:
            bl_labels = {**labels, "agent": "baseline"}
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(bl_labels.items()))
            bl_sample = f"{metric_name}{{{label_str}}} {baseline.get(key, 0)}"
            lines.append(mcp_sample + "\n" + bl_sample)
        else:
            lines.append(mcp_sample)

    output = "\n\n".join(lines) + "\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)

    return output
