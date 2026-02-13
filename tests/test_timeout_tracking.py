"""Tests for timeout statistics tracking (Issue #297).

Tests verify that when a task times out, the evaluation state still captures:
- iterations performed before timeout
- tool_calls made before timeout
- tool_usage breakdown
- tool_failures that occurred
- status field indicating timeout vs normal completion
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcpbr.harness import _run_mcp_evaluation, agent_result_to_dict
from mcpbr.harnesses import AgentResult, _parse_tool_usage_from_stream


def test_parse_tool_usage_captures_partial_stream():
    """Test that _parse_tool_usage_from_stream extracts stats from partial stdout."""
    # Simulate partial stream-json output from a timed-out execution
    partial_stdout = """
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1","name":"Grep","input":{}}],"usage":{"input_tokens":100,"output_tokens":50}}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1","content":"result"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"2","name":"Read","input":{}}],"usage":{"input_tokens":120,"output_tokens":60}}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"2","content":"file content"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"3","name":"Bash","input":{}}],"usage":{"input_tokens":130,"output_tokens":70}}}
"""

    (
        total_tool_calls,
        tool_usage,
        tool_failures,
        tool_errors,
        num_turns,
        tokens_in,
        tokens_out,
        result_subtype,
        cost_usd,
    ) = _parse_tool_usage_from_stream(partial_stdout)

    # Verify tool call counting
    assert total_tool_calls == 3, f"Expected 3 tool calls, got {total_tool_calls}"
    assert tool_usage == {"Grep": 1, "Read": 1, "Bash": 1}
    assert tokens_in == 350  # 100 + 120 + 130
    assert tokens_out == 180  # 50 + 60 + 70


def test_parse_tool_usage_captures_tool_failures():
    """Test that tool failures are tracked even in partial streams."""
    partial_stdout = """
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1","name":"Grep","input":{}}],"usage":{"input_tokens":100,"output_tokens":50}}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1","is_error":true,"content":"File not found"}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"2","name":"Read","input":{}}],"usage":{"input_tokens":120,"output_tokens":60}}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"2","is_error":true,"content":"Permission denied"}]}}
"""

    (
        total_tool_calls,
        tool_usage,
        tool_failures,
        tool_errors,
        num_turns,
        tokens_in,
        tokens_out,
        result_subtype,
        cost_usd,
    ) = _parse_tool_usage_from_stream(partial_stdout)

    # Verify failure tracking
    assert total_tool_calls == 2
    assert tool_failures == {"Grep": 1, "Read": 1}
    assert "Grep" in tool_errors
    assert "Read" in tool_errors
    assert "File not found" in tool_errors["Grep"][0]
    assert "Permission denied" in tool_errors["Read"][0]


def test_agent_result_to_dict_includes_status_on_timeout():
    """Test that agent_result_to_dict adds status='timeout' when error mentions timeout."""
    result = AgentResult(
        patch="",
        success=False,
        error="Task execution timed out after 600s.",
        tokens_input=1000,
        tokens_output=500,
        iterations=15,
        tool_calls=30,
        tool_usage={"Grep": 10, "Read": 15, "Bash": 5},
        tool_failures={"Bash": 2},
    )

    data = agent_result_to_dict(result, None, "claude-sonnet-4-5-20250929")

    # Verify status field is set
    assert data.get("status") == "timeout", "Expected status='timeout' for timeout error"
    # Verify statistics are preserved
    assert data["iterations"] == 15
    assert data["tool_calls"] == 30
    assert data["tool_usage"] == {"Grep": 10, "Read": 15, "Bash": 5}
    assert data["tool_failures"] == {"Bash": 2}
    assert not data["resolved"]
    assert not data["patch_applied"]


def test_agent_result_to_dict_no_status_on_normal_error():
    """Test that agent_result_to_dict doesn't add status for non-timeout errors."""
    result = AgentResult(
        patch="",
        success=False,
        error="Some other error occurred",
        tokens_input=100,
        tokens_output=50,
        iterations=5,
        tool_calls=10,
    )

    data = agent_result_to_dict(result, None, "claude-sonnet-4-5-20250929")

    # Verify no status field for normal errors
    assert "status" not in data or data.get("status") != "timeout"
    assert data["error"] == "Some other error occurred"


@pytest.mark.asyncio
async def test_run_mcp_evaluation_timeout_fallback():
    """Test that _run_mcp_evaluation timeout handler sets status='timeout'."""
    # Mock config and other dependencies
    config = Mock()
    config.agent_prompt = None
    config.timeout_seconds = 10
    config.model = "claude-sonnet-4-5-20250929"
    config.agent_harness = "claude-code"  # Required field
    config.enable_profiling = False

    benchmark = Mock()
    benchmark.get_prompt_template.return_value = "Test prompt"
    # Docker container methods (kill, remove) are synchronous in docker-py
    mock_container = Mock()
    mock_container.kill = Mock()
    mock_container.remove = Mock()
    mock_env = AsyncMock()
    mock_env.container = mock_container
    mock_env.cleanup = AsyncMock()
    benchmark.create_environment = AsyncMock(return_value=mock_env)

    docker_manager = Mock()

    task = {"instance_id": "test-task", "problem_statement": "Fix the bug"}

    # Mock _create_mcp_agent so the returned agent has run_setup_command
    mock_agent = Mock()
    mock_agent.run_setup_command = AsyncMock()

    # Simulate timeout by raising asyncio.TimeoutError
    with (
        patch("mcpbr.harness._create_mcp_agent", return_value=mock_agent),
        patch("mcpbr.harness.asyncio.wait_for", side_effect=asyncio.TimeoutError),
    ):
        result = await _run_mcp_evaluation(task, config, docker_manager, benchmark, verbose=False)

    # Verify setup_command was called before the timer
    mock_agent.run_setup_command.assert_awaited_once()

    # Verify timeout fallback sets status field
    assert result.get("status") == "timeout"
    assert result.get("error") == "Timeout"
    assert not result["resolved"]
    assert not result["patch_applied"]


@pytest.mark.asyncio
async def test_docker_timeout_captures_partial_stdout():
    """Test that timeout handler logic correctly parses MCP log files.

    This is a simplified test that verifies the key behavior without
    full Docker environment mocking.
    """
    # Create a temporary MCP log file with partial output
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test-task_mcp.log"
        log_content = """[STDOUT] {"type":"assistant","message":{"content":[{"type":"tool_use","id":"1","name":"Grep","input":{}}],"usage":{"input_tokens":100,"output_tokens":50}}}
[STDOUT] {"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"1","content":"result"}]}}
[STDOUT] {"type":"assistant","message":{"content":[{"type":"tool_use","id":"2","name":"Read","input":{}}],"usage":{"input_tokens":120,"output_tokens":60}}}
"""
        log_path.write_text(log_content)

        # Simulate what the timeout handler does: read back the log
        with open(log_path, "r") as f:
            stdout_lines = []
            for line in f:
                if line.startswith("[STDOUT] "):
                    stdout_lines.append(line[9:])  # Strip "[STDOUT] " prefix
            partial_stdout = "".join(stdout_lines)

        # Parse the partial stdout
        (
            total_tool_calls,
            tool_usage,
            tool_failures,
            tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(partial_stdout)

        # Verify that statistics were captured
        assert total_tool_calls == 2
        assert tool_usage == {"Grep": 1, "Read": 1}
        assert tokens_in == 220
        assert tokens_out == 110


def test_timeout_error_message_includes_statistics():
    """Test that timeout error messages mention captured statistics."""
    result = AgentResult(
        patch="",
        success=False,
        error="Task execution timed out after 600s. Agent made 30 tool calls across 15 iterations before timeout.",
        tokens_input=5000,
        tokens_output=2500,
        iterations=15,
        tool_calls=30,
        tool_usage={"Grep": 16, "Read": 8, "Bash": 4, "TodoWrite": 2},
    )

    data = agent_result_to_dict(result, None, "claude-sonnet-4-5-20250929")

    # Verify comprehensive information is available
    assert data["iterations"] == 15
    assert data["tool_calls"] == 30
    assert data["tool_usage"]["Grep"] == 16
    assert data["tokens"]["input"] == 5000
    assert data["tokens"]["output"] == 2500
    assert "30 tool calls" in data["error"]
    assert "15 iterations" in data["error"]


def test_empty_partial_stdout_returns_zeros():
    """Test that parsing empty partial stdout returns zeros gracefully."""
    (
        total_tool_calls,
        tool_usage,
        tool_failures,
        tool_errors,
        num_turns,
        tokens_in,
        tokens_out,
        result_subtype,
        cost_usd,
    ) = _parse_tool_usage_from_stream("")

    assert total_tool_calls == 0
    assert tool_usage == {}
    assert tool_failures == {}
    assert tool_errors == {}
    assert num_turns == 0
    assert tokens_in == 0
    assert tokens_out == 0


def test_malformed_json_handled_gracefully():
    """Test that malformed JSON in partial stdout doesn't crash parsing."""
    partial_stdout = """
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"1","name":"Grep","input":{}}],"usage":{"input_tokens":100,"output_tokens":50}}}
{invalid json here}
{"type":"assistant","message":{"content":[{"type":"tool_use","id":"2","name":"Read","input":{}}],"usage":{"input_tokens":120,"output_tokens":60}}}
"""

    (
        total_tool_calls,
        tool_usage,
        tool_failures,
        tool_errors,
        num_turns,
        tokens_in,
        tokens_out,
        result_subtype,
        cost_usd,
    ) = _parse_tool_usage_from_stream(partial_stdout)

    # Should parse valid lines and skip invalid ones
    assert total_tool_calls == 2
    assert tool_usage == {"Grep": 1, "Read": 1}
    assert tokens_in == 220
