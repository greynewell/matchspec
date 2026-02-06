"""Badge generation for evaluation results.

Generates shields.io badge markdown from evaluation results.
"""

from typing import Any
from urllib.parse import quote


def generate_badge(label: str, value: str, color: str) -> str:
    """Generate a shields.io badge markdown string.

    Args:
        label: Badge label (left side).
        value: Badge value (right side).
        color: Badge color (e.g. "brightgreen", "red", "blue").

    Returns:
        Markdown image string for the badge.
    """
    encoded_label = quote(label.replace("-", "--"))
    encoded_value = quote(value.replace("-", "--"))
    url = f"https://img.shields.io/badge/{encoded_label}-{encoded_value}-{color}"
    return f"![{label}: {value}]({url})"


def get_badge_color(rate: float) -> str:
    """Get badge color based on resolution rate thresholds.

    Args:
        rate: Resolution rate (0.0 to 1.0).

    Returns:
        Color string for shields.io badge.
    """
    if rate >= 0.5:
        return "brightgreen"
    elif rate >= 0.3:
        return "yellow"
    else:
        return "red"


def generate_badges_from_results(results: dict[str, Any]) -> list[str]:
    """Generate badge markdown list from evaluation results.

    Args:
        results: Evaluation results dictionary with metadata and summary.

    Returns:
        List of markdown badge strings.
    """
    config = results.get("metadata", {}).get("config", {})
    mcp = results.get("summary", {}).get("mcp", {})

    benchmark = config.get("benchmark", "unknown")
    model = config.get("model", "unknown")
    rate = mcp.get("rate", 0)
    resolved = mcp.get("resolved", 0)
    total = mcp.get("total", 0)
    cost = mcp.get("total_cost", 0)

    rate_color = get_badge_color(rate)

    badges = [
        generate_badge("Benchmark", benchmark, "blue"),
        generate_badge("Model", model, "purple"),
        generate_badge("Resolution Rate", f"{rate:.0%}", rate_color),
        generate_badge("Resolved", f"{resolved}/{total}", rate_color),
    ]

    if cost:
        badges.append(generate_badge("Cost", f"${cost:.2f}", "informational"))

    return badges
