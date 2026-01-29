"""Tests for MCP tool call failure tracking."""

import json

import pytest

from mcpbr.harness import TaskResult, _calculate_mcp_tool_stats
from mcpbr.harnesses import _parse_tool_usage_from_stream


class TestToolFailureTracking:
    """Tests for tool failure tracking functionality."""

    def test_parse_tool_usage_captures_failures(self) -> None:
        """Test that _parse_tool_usage_from_stream captures tool failures."""
        stream_output = """
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_1", "name": "Read"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "File not found", "is_error": true}]}}
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_2", "name": "Bash"}], "usage": {"input_tokens": 120, "output_tokens": 60}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_2", "content": "Command output", "is_error": false}]}}
{"type": "result", "num_turns": 2, "usage": {"input_tokens": 220, "output_tokens": 110}}
        """

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        # Verify successful calls
        assert total_calls == 2
        assert tool_usage == {"Read": 1, "Bash": 1}

        # Verify failures
        assert tool_failures == {"Read": 1}
        assert "Read" in tool_errors
        assert len(tool_errors["Read"]) == 1
        assert "File not found" in tool_errors["Read"][0]

        # Verify tokens and turns
        assert num_turns == 2
        assert tokens_in == 220
        assert tokens_out == 110

    def test_parse_tool_usage_without_failures(self) -> None:
        """Test parsing when all tools succeed."""
        stream_output = """
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_1", "name": "Read"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "File content", "is_error": false}]}}
{"type": "result", "num_turns": 1, "usage": {"input_tokens": 100, "output_tokens": 50}}
        """

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert total_calls == 1
        assert tool_usage == {"Read": 1}
        assert tool_failures == {}
        assert tool_errors == {}

    def test_parse_multiple_failures_same_tool(self) -> None:
        """Test tracking multiple failures for the same tool."""
        stream_output = """
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_1", "name": "Bash"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "Error 1", "is_error": true}]}}
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_2", "name": "Bash"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_2", "content": "Error 2", "is_error": true}]}}
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_3", "name": "Bash"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_3", "content": "Success", "is_error": false}]}}
{"type": "result", "num_turns": 3, "usage": {"input_tokens": 300, "output_tokens": 150}}
        """

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert total_calls == 3
        assert tool_usage == {"Bash": 3}
        assert tool_failures == {"Bash": 2}
        assert "Bash" in tool_errors
        assert len(tool_errors["Bash"]) == 2

    def test_calculate_mcp_tool_stats_empty(self) -> None:
        """Test stats calculation with no results."""
        results: list[TaskResult] = []
        stats = _calculate_mcp_tool_stats(results)

        assert stats["total_tool_calls"] == 0
        assert stats["total_failures"] == 0
        assert stats["failure_rate"] == 0.0
        assert stats["by_tool"] == {}
        assert stats["has_failures"] is False
        assert stats["high_failure_rate"] is False

    def test_calculate_mcp_tool_stats_with_failures(self) -> None:
        """Test stats calculation with mixed success/failure results."""
        results = [
            TaskResult(
                instance_id="task1",
                mcp={
                    "tool_usage": {"Read": 5, "Write": 3},
                    "tool_failures": {"Read": 2},
                    "tool_errors": {"Read": ["Error 1", "Error 2"]},
                },
                baseline=None,
            ),
            TaskResult(
                instance_id="task2",
                mcp={
                    "tool_usage": {"Read": 3, "Bash": 2},
                    "tool_failures": {"Bash": 1},
                    "tool_errors": {"Bash": ["Command failed"]},
                },
                baseline=None,
            ),
        ]

        stats = _calculate_mcp_tool_stats(results)

        # Note: tool_usage values represent TOTAL calls (successful + failed)
        # tool_failures represents only failed calls
        # succeeded = total - failed
        #
        # Aggregated from results:
        # Read: tool_usage = 5+3 = 8 total, tool_failures = 2 → succeeded = 8-2 = 6
        # Write: tool_usage = 3 total, tool_failures = 0 → succeeded = 3-0 = 3
        # Bash: tool_usage = 2 total, tool_failures = 1 → succeeded = 2-1 = 1
        # Grand total: 8+3+2 = 13 total calls, 3 failures
        # Failure rate = 3 / 13 = 23%, which is > 10%
        assert stats["total_tool_calls"] == 13  # Total calls from tool_usage
        assert stats["total_failures"] == 3
        assert stats["failure_rate"] == pytest.approx(3 / 13, rel=0.01)
        assert stats["has_failures"] is True
        assert stats["high_failure_rate"] is True  # 3/13 = 23% > 10%

        # Check per-tool stats
        assert "Read" in stats["by_tool"]
        assert stats["by_tool"]["Read"]["total"] == 8  # tool_usage value, not 10
        assert stats["by_tool"]["Read"]["succeeded"] == 6  # 8 - 2 = 6, not 8
        assert stats["by_tool"]["Read"]["failed"] == 2

        assert "Bash" in stats["by_tool"]
        assert stats["by_tool"]["Bash"]["total"] == 2  # tool_usage value, not 3
        assert stats["by_tool"]["Bash"]["succeeded"] == 1  # 2 - 1 = 1, not 2
        assert stats["by_tool"]["Bash"]["failed"] == 1

    def test_calculate_mcp_tool_stats_high_failure_rate(self) -> None:
        """Test detection of high failure rate (>10%)."""
        results = [
            TaskResult(
                instance_id="task1",
                mcp={
                    "tool_usage": {"Read": 10},
                    "tool_failures": {"Read": 5},  # 50% failure rate
                },
                baseline=None,
            ),
        ]

        stats = _calculate_mcp_tool_stats(results)

        assert stats["total_failures"] == 5
        assert stats["failure_rate"] > 0.1
        assert stats["high_failure_rate"] is True

    def test_error_content_list_format(self) -> None:
        """Test handling of error content as list of blocks."""
        stream_output = """
{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tool_1", "name": "Read"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": [{"text": "Error message here"}], "is_error": true}]}}
{"type": "result", "num_turns": 1, "usage": {"input_tokens": 100, "output_tokens": 50}}
        """

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert tool_failures == {"Read": 1}
        assert "Read" in tool_errors
        assert "Error message here" in tool_errors["Read"][0]

    def test_error_truncation(self) -> None:
        """Test that long error messages are truncated."""
        long_error = "x" * 300
        stream_output = f"""
{{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "id": "tool_1", "name": "Read"}}], "usage": {{"input_tokens": 100, "output_tokens": 50}}}}}}
{{"type": "user", "message": {{"content": [{{"type": "tool_result", "tool_use_id": "tool_1", "content": "{long_error}", "is_error": true}}]}}}}
{{"type": "result", "num_turns": 1, "usage": {{"input_tokens": 100, "output_tokens": 50}}}}
        """

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert tool_failures == {"Read": 1}
        assert "Read" in tool_errors
        # Error should be truncated to 200 chars
        assert len(tool_errors["Read"][0]) == 200

    def test_max_errors_per_tool(self) -> None:
        """Test that only first 5 errors are kept per tool."""
        # Create 6 tool failures for the same tool
        events = []
        for i in range(6):
            assistant_event = {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "id": f"tool_{i}", "name": "Bash"}],
                    "usage": {"input_tokens": 100, "output_tokens": 50},
                },
            }
            user_event = {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"tool_{i}",
                            "content": f"Error {i}",
                            "is_error": True,
                        }
                    ]
                },
            }
            events.append(json.dumps(assistant_event))
            events.append(json.dumps(user_event))

        result_event = {
            "type": "result",
            "num_turns": 6,
            "usage": {"input_tokens": 600, "output_tokens": 300},
        }
        events.append(json.dumps(result_event))

        stream_output = "\n".join(events)

        (
            total_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert tool_failures == {"Bash": 6}
        assert "Bash" in tool_errors
        # Only first 5 errors should be kept
        assert len(tool_errors["Bash"]) == 5
        assert tool_errors["Bash"][0] == "Error 0"
        assert tool_errors["Bash"][4] == "Error 4"
