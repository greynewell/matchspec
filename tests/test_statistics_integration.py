"""Integration tests for comprehensive statistics in reporting."""

import json
import tempfile
from pathlib import Path

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import (
    save_json_results,
    save_markdown_report,
)
from mcpbr.statistics import calculate_comprehensive_statistics


def test_statistics_in_json_output() -> None:
    """Test that comprehensive statistics are included in JSON output."""
    results = EvaluationResults(
        metadata={
            "timestamp": "2026-01-26T12:00:00Z",
            "config": {
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
                "agent_harness": "claude-code",
                "benchmark": "swe-bench",
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 3,
                "timeout_seconds": 300,
                "max_iterations": 10,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            },
        },
        summary={
            "mcp": {
                "resolved": 2,
                "total": 3,
                "rate": 0.667,
                "total_cost": 0.0789,
                "cost_per_task": 0.0263,
                "cost_per_resolved": 0.03945,
            },
            "baseline": {
                "resolved": 1,
                "total": 3,
                "rate": 0.333,
                "total_cost": 0.0543,
                "cost_per_task": 0.0181,
                "cost_per_resolved": 0.0543,
            },
            "improvement": "+100.0%",
        },
        tasks=[
            TaskResult(
                instance_id="task-1",
                mcp={
                    "tokens": {"input": 1000, "output": 5000},
                    "cost": 0.0234,
                    "iterations": 5,
                    "tool_calls": 10,
                    "tool_usage": {"Read": 3, "Write": 2, "Bash": 5},
                    "tool_failures": {"Bash": 1},
                    "resolved": True,
                    "patch_applied": True,
                },
                baseline={
                    "tokens": {"input": 800, "output": 4000},
                    "cost": 0.0180,
                    "iterations": 3,
                    "tool_calls": 5,
                    "resolved": False,
                },
            ),
            TaskResult(
                instance_id="task-2",
                mcp={
                    "tokens": {"input": 1200, "output": 6000},
                    "cost": 0.0255,
                    "iterations": 7,
                    "tool_calls": 15,
                    "tool_usage": {"Read": 5, "Bash": 8, "Grep": 2},
                    "tool_failures": {"Bash": 2},
                    "resolved": True,
                    "patch_applied": True,
                },
                baseline={
                    "tokens": {"input": 1000, "output": 5000},
                    "cost": 0.0200,
                    "iterations": 5,
                    "tool_calls": 8,
                    "resolved": True,
                },
            ),
            TaskResult(
                instance_id="task-3",
                mcp={
                    "tokens": {"input": 1500, "output": 7000},
                    "cost": 0.0300,
                    "iterations": 10,
                    "tool_calls": 20,
                    "tool_usage": {"Read": 8, "Write": 5, "Bash": 6, "Grep": 1},
                    "tool_failures": {"Write": 1, "Bash": 1},
                    "error": "Timeout exceeded",
                    "resolved": False,
                },
                baseline={
                    "tokens": {"input": 900, "output": 4500},
                    "cost": 0.0163,
                    "iterations": 4,
                    "tool_calls": 6,
                    "error": "File not found",
                    "resolved": False,
                },
            ),
        ],
    )

    # Calculate and add comprehensive statistics
    stats = calculate_comprehensive_statistics(results)
    results.summary["comprehensive_stats"] = stats.to_dict()

    # Save to JSON
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "results.json"
        save_json_results(results, output_path)

        # Load and verify
        with open(output_path) as f:
            data = json.load(f)

        # Verify comprehensive_stats is present
        assert "comprehensive_stats" in data["summary"]

        stats_data = data["summary"]["comprehensive_stats"]

        # Verify all major sections are present
        assert "mcp_tokens" in stats_data
        assert "baseline_tokens" in stats_data
        assert "mcp_costs" in stats_data
        assert "baseline_costs" in stats_data
        assert "mcp_tools" in stats_data
        assert "mcp_errors" in stats_data
        assert "baseline_errors" in stats_data
        assert "mcp_iterations" in stats_data
        assert "baseline_iterations" in stats_data

        # Verify token statistics
        assert stats_data["mcp_tokens"]["total_input"] == 3700
        assert stats_data["mcp_tokens"]["total_output"] == 18000
        assert stats_data["mcp_tokens"]["total_tokens"] == 21700

        # Verify cost statistics
        assert stats_data["mcp_costs"]["total_cost"] == 0.0789
        assert stats_data["mcp_costs"]["avg_cost_per_task"] > 0

        # Verify tool statistics
        assert stats_data["mcp_tools"]["total_calls"] == 45  # 10+15+20
        assert stats_data["mcp_tools"]["total_failures"] == 5  # 1+2+2
        assert stats_data["mcp_tools"]["unique_tools_used"] == 4  # Read, Write, Bash, Grep
        assert "Read" in stats_data["mcp_tools"]["per_tool"]
        assert stats_data["mcp_tools"]["per_tool"]["Bash"]["failed"] == 4

        # Verify error statistics
        assert stats_data["mcp_errors"]["total_errors"] == 1
        assert stats_data["baseline_errors"]["total_errors"] == 1
        assert "timeout" in stats_data["mcp_errors"]["error_categories"]

        # Verify iteration statistics
        assert stats_data["mcp_iterations"]["total_iterations"] == 22  # 5+7+10
        assert stats_data["mcp_iterations"]["avg_iterations"] > 0
        assert stats_data["mcp_iterations"]["max_iterations"] == 10


def test_statistics_in_markdown_output() -> None:
    """Test that comprehensive statistics are included in Markdown output."""
    results = EvaluationResults(
        metadata={
            "timestamp": "2026-01-26T12:00:00Z",
            "config": {
                "model": "claude-sonnet-4-5-20250929",
                "provider": "anthropic",
                "agent_harness": "claude-code",
                "benchmark": "swe-bench",
                "dataset": "SWE-bench/SWE-bench_Lite",
                "sample_size": 2,
                "timeout_seconds": 300,
                "max_iterations": 10,
            },
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            },
        },
        summary={
            "mcp": {
                "resolved": 1,
                "total": 2,
                "rate": 0.5,
                "total_cost": 0.05,
                "cost_per_task": 0.025,
                "cost_per_resolved": 0.05,
            },
            "baseline": {
                "resolved": 0,
                "total": 2,
                "rate": 0.0,
                "total_cost": 0.04,
                "cost_per_task": 0.02,
                "cost_per_resolved": None,
            },
            "improvement": "+inf%",
        },
        tasks=[
            TaskResult(
                instance_id="task-1",
                mcp={
                    "tokens": {"input": 1000, "output": 5000},
                    "cost": 0.025,
                    "iterations": 5,
                    "tool_usage": {"Read": 3, "Write": 2},
                    "resolved": True,
                },
                baseline={
                    "tokens": {"input": 800, "output": 4000},
                    "cost": 0.020,
                    "iterations": 3,
                    "resolved": False,
                },
            ),
            TaskResult(
                instance_id="task-2",
                mcp={
                    "tokens": {"input": 1200, "output": 6000},
                    "cost": 0.025,
                    "iterations": 7,
                    "tool_usage": {"Read": 5, "Bash": 3},
                    "tool_failures": {"Bash": 1},
                    "error": "Timeout exceeded",
                    "resolved": False,
                },
                baseline={
                    "tokens": {"input": 900, "output": 4500},
                    "cost": 0.020,
                    "iterations": 4,
                    "error": "File not found",
                    "resolved": False,
                },
            ),
        ],
    )

    # Calculate and add comprehensive statistics
    stats = calculate_comprehensive_statistics(results)
    results.summary["comprehensive_stats"] = stats.to_dict()

    # Save to Markdown
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.md"
        save_markdown_report(results, output_path)

        # Load and verify
        content = output_path.read_text()

        # Verify major sections are present
        assert "## Comprehensive Statistics" in content
        assert "### Token Usage" in content
        assert "### Detailed Cost Breakdown" in content
        assert "### Iteration Statistics" in content
        assert "### MCP Tool Usage Statistics" in content
        assert "### Error Analysis" in content

        # Verify token data is in markdown
        assert "Total Input" in content
        assert "Total Output" in content
        assert "1,000" in content or "1000" in content  # Could be formatted either way

        # Verify cost data
        assert "Total Cost" in content
        assert "Avg Cost/Task" in content

        # Verify tool data
        assert "Total Calls" in content
        assert "Failed Calls" in content
        assert "Read" in content  # Most used tool
        assert "Bash" in content

        # Verify error data
        assert "Total Errors" in content
        assert "Timeout Count" in content
        assert "timeout" in content.lower()

        # Verify iteration data
        assert "Total Iterations" in content
        assert "Avg Iterations/Task" in content


def test_empty_statistics_handling() -> None:
    """Test that empty results don't cause errors in statistics."""
    results = EvaluationResults(
        metadata={
            "timestamp": "2026-01-26T12:00:00Z",
            "config": {"model": "test-model"},
            "mcp_server": {"command": "test", "args": []},
        },
        summary={
            "mcp": {"resolved": 0, "total": 0, "rate": 0.0},
            "baseline": {"resolved": 0, "total": 0, "rate": 0.0},
            "improvement": "N/A",
        },
        tasks=[],
    )

    # Calculate statistics (should not raise)
    stats = calculate_comprehensive_statistics(results)
    results.summary["comprehensive_stats"] = stats.to_dict()

    # Save to JSON (should not raise)
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = Path(tmpdir) / "results.json"
        save_json_results(results, json_path)
        assert json_path.exists()

        # Verify structure
        with open(json_path) as f:
            data = json.load(f)
        assert "comprehensive_stats" in data["summary"]

        # Save to Markdown (should not raise)
        md_path = Path(tmpdir) / "report.md"
        save_markdown_report(results, md_path)
        assert md_path.exists()
