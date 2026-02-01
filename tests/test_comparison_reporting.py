"""Tests for comparison mode reporting."""

from io import StringIO

from rich.console import Console

from mcpbr.harness import EvaluationResults, TaskResult
from mcpbr.reporting import print_comparison_summary


class TestComparisonReporting:
    """Tests for comparison reporting output."""

    def test_comparison_summary_output(self):
        """Test comparison summary console output."""
        results = EvaluationResults(
            metadata={"timestamp": "2026-01-30", "config": {}},
            summary={
                "mcp_server_a": {
                    "name": "Task Queries",
                    "total": 10,
                    "resolved": 4,
                    "resolution_rate": 0.4,
                    "cost": 0.50,
                },
                "mcp_server_b": {
                    "name": "Edge Identity",
                    "total": 10,
                    "resolved": 2,
                    "resolution_rate": 0.2,
                    "cost": 0.45,
                },
                "comparison": {
                    "a_vs_b_delta": 2,
                    "a_vs_b_improvement_pct": 100.0,
                    "a_unique_wins": ["task-1", "task-2"],
                    "b_unique_wins": [],
                    "both_wins": ["task-3", "task-4"],
                    "both_fail": ["task-5"],
                },
            },
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp_server_a={"resolved": True},
                    mcp_server_b={"resolved": False},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp_server_a={"resolved": True},
                    mcp_server_b={"resolved": False},
                ),
                TaskResult(
                    instance_id="task-3",
                    mcp_server_a={"resolved": True},
                    mcp_server_b={"resolved": True},
                ),
                TaskResult(
                    instance_id="task-4",
                    mcp_server_a={"resolved": True},
                    mcp_server_b={"resolved": True},
                ),
                TaskResult(
                    instance_id="task-5",
                    mcp_server_a={"resolved": False},
                    mcp_server_b={"resolved": False},
                ),
            ],
        )

        # Capture console output
        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)

        print_comparison_summary(results, console)

        output = string_io.getvalue()
        assert "Side-by-Side MCP Server Comparison" in output
        assert "Task Queries" in output
        assert "Edge Identity" in output
        assert "4/10" in output  # Server A resolved
        assert "2/10" in output  # Server B resolved

    def test_comparison_summary_with_no_unique_wins(self):
        """Test comparison summary when both servers resolve the same tasks."""
        results = EvaluationResults(
            metadata={"timestamp": "2026-01-30", "config": {}},
            summary={
                "mcp_server_a": {
                    "name": "Server A",
                    "total": 2,
                    "resolved": 1,
                    "resolution_rate": 0.5,
                    "cost": 0.10,
                },
                "mcp_server_b": {
                    "name": "Server B",
                    "total": 2,
                    "resolved": 1,
                    "resolution_rate": 0.5,
                    "cost": 0.10,
                },
                "comparison": {
                    "a_vs_b_delta": 0,
                    "a_vs_b_improvement_pct": 0.0,
                    "a_unique_wins": [],
                    "b_unique_wins": [],
                    "both_wins": ["task-1"],
                    "both_fail": ["task-2"],
                },
            },
            tasks=[
                TaskResult(
                    instance_id="task-1",
                    mcp_server_a={"resolved": True},
                    mcp_server_b={"resolved": True},
                ),
                TaskResult(
                    instance_id="task-2",
                    mcp_server_a={"resolved": False},
                    mcp_server_b={"resolved": False},
                ),
            ],
        )

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)

        print_comparison_summary(results, console)

        output = string_io.getvalue()
        # Should not show unique wins sections if lists are empty
        assert "unique wins" not in output.lower() or "0 tasks" in output

    def test_fallback_to_regular_summary(self):
        """Test that non-comparison results fall back to regular print_summary."""
        results = EvaluationResults(
            metadata={"timestamp": "2026-01-30", "config": {}},
            summary={
                "mcp": {
                    "resolved": 5,
                    "total": 10,
                    "rate": 0.5,
                    "total_cost": 1.0,
                    "cost_per_task": 0.1,
                    "cost_per_resolved": 0.2,
                },
                "baseline": {
                    "resolved": 3,
                    "total": 10,
                    "rate": 0.3,
                    "total_cost": 0.5,
                    "cost_per_task": 0.05,
                    "cost_per_resolved": 0.16,
                },
                "improvement": "+66.7%",
            },
            tasks=[],
        )

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)

        # Should not crash and should use regular summary
        print_comparison_summary(results, console)

        output = string_io.getvalue()
        # Should show regular summary, not comparison
        assert "Evaluation Results" in output or "Summary" in output
