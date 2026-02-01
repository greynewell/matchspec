"""Tests for comparison result aggregation."""

import pytest

from mcpbr.harness import TaskResult, _aggregate_comparison_results


class TestComparisonAggregation:
    """Tests for comparison aggregation logic."""

    def test_aggregate_with_one_unique_winner(self):
        """Test aggregation when one server uniquely resolves tasks."""
        results = [
            TaskResult(
                instance_id="task-1",
                mcp_server_a={"resolved": True, "cost": 0.05, "tool_calls": 10},
                mcp_server_b={"resolved": False, "cost": 0.03, "tool_calls": 8},
            ),
            TaskResult(
                instance_id="task-2",
                mcp_server_a={"resolved": True, "cost": 0.04, "tool_calls": 9},
                mcp_server_b={"resolved": False, "cost": 0.02, "tool_calls": 7},
            ),
        ]

        summary = _aggregate_comparison_results(results)

        assert summary["stats_a"]["resolved"] == 2
        assert summary["stats_b"]["resolved"] == 0
        assert summary["a_vs_b_delta"] == 2
        assert len(summary["a_unique_wins"]) == 2
        assert len(summary["b_unique_wins"]) == 0
        assert len(summary["both_wins"]) == 0

    def test_aggregate_with_both_winners(self):
        """Test aggregation when both servers resolve tasks."""
        results = [
            TaskResult(
                instance_id="task-1",
                mcp_server_a={"resolved": True, "cost": 0.05, "tool_calls": 10},
                mcp_server_b={"resolved": True, "cost": 0.03, "tool_calls": 8},
            ),
            TaskResult(
                instance_id="task-2",
                mcp_server_a={"resolved": True, "cost": 0.04, "tool_calls": 9},
                mcp_server_b={"resolved": False, "cost": 0.02, "tool_calls": 7},
            ),
        ]

        summary = _aggregate_comparison_results(results)

        assert summary["stats_a"]["resolved"] == 2
        assert summary["stats_b"]["resolved"] == 1
        assert summary["a_vs_b_delta"] == 1
        assert len(summary["a_unique_wins"]) == 1
        assert len(summary["both_wins"]) == 1

    def test_resolution_rate_calculation(self):
        """Test resolution rate percentage calculation."""
        results = [
            TaskResult(
                instance_id=f"task-{i}",
                mcp_server_a={"resolved": i < 8, "cost": 0.05, "tool_calls": 10},  # 8/10 = 80%
                mcp_server_b={"resolved": i < 4, "cost": 0.03, "tool_calls": 8},  # 4/10 = 40%
            )
            for i in range(10)
        ]

        summary = _aggregate_comparison_results(results)

        assert summary["resolution_rate_a"] == 0.8
        assert summary["resolution_rate_b"] == 0.4
        assert summary["a_vs_b_improvement_pct"] == pytest.approx(100.0)  # 2x better

    def test_aggregate_with_both_failures(self):
        """Test aggregation when both servers fail on tasks."""
        results = [
            TaskResult(
                instance_id="task-1",
                mcp_server_a={"resolved": False, "cost": 0.05, "tool_calls": 10},
                mcp_server_b={"resolved": False, "cost": 0.03, "tool_calls": 8},
            ),
            TaskResult(
                instance_id="task-2",
                mcp_server_a={"resolved": False, "cost": 0.04, "tool_calls": 9},
                mcp_server_b={"resolved": False, "cost": 0.02, "tool_calls": 7},
            ),
        ]

        summary = _aggregate_comparison_results(results)

        assert summary["stats_a"]["resolved"] == 0
        assert summary["stats_b"]["resolved"] == 0
        assert len(summary["both_fail"]) == 2
        assert summary["resolution_rate_a"] == 0.0
        assert summary["resolution_rate_b"] == 0.0

    def test_cost_and_tool_call_aggregation(self):
        """Test that costs and tool calls are properly summed."""
        results = [
            TaskResult(
                instance_id="task-1",
                mcp_server_a={"resolved": True, "cost": 0.05, "tool_calls": 10},
                mcp_server_b={"resolved": True, "cost": 0.03, "tool_calls": 8},
            ),
            TaskResult(
                instance_id="task-2",
                mcp_server_a={"resolved": False, "cost": 0.04, "tool_calls": 9},
                mcp_server_b={"resolved": False, "cost": 0.02, "tool_calls": 7},
            ),
        ]

        summary = _aggregate_comparison_results(results)

        assert summary["stats_a"]["cost"] == pytest.approx(0.09)
        assert summary["stats_b"]["cost"] == pytest.approx(0.05)
        assert summary["stats_a"]["tool_calls"] == 19
        assert summary["stats_b"]["tool_calls"] == 15
