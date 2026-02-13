"""Tests for cost calculation with cache tokens."""

from mcpbr.harness import agent_result_to_dict
from mcpbr.harnesses import AgentResult, _parse_tool_usage_from_stream


class TestCostExtraction:
    """Test cost extraction from stream-json output."""

    def test_parse_cost_from_result_event(self):
        """Test that total_cost_usd is correctly extracted from result event."""
        # Sample stream-json output with cost information
        stream_output = """
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hello"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "result", "subtype": "success", "num_turns": 1, "usage": {"input_tokens": 100, "output_tokens": 50}, "total_cost_usd": 0.0125}
"""

        (
            _total_tool_calls,
            _tool_usage,
            _tool_failures,
            _tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            _result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert cost_usd == 0.0125
        assert num_turns == 1
        assert tokens_in == 100
        assert tokens_out == 50

    def test_parse_no_cost_from_result_event(self):
        """Test that cost_usd is None when not provided in result event."""
        # Stream output without cost information
        stream_output = """
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hello"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "result", "subtype": "success", "num_turns": 1, "usage": {"input_tokens": 100, "output_tokens": 50}}
"""

        (
            _total_tool_calls,
            _tool_usage,
            _tool_failures,
            _tool_errors,
            num_turns,
            _tokens_in,
            _tokens_out,
            _result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert cost_usd is None
        assert num_turns == 1

    def test_parse_cost_with_cache_tokens(self):
        """Test cost extraction when result includes cache read/creation tokens.

        The total_cost_usd should include costs from:
        - Base input/output tokens
        - Cache creation tokens (write)
        - Cache read tokens (much cheaper than base)
        """
        # Realistic stream output with cache tokens
        # Example: 500 base input, 200 output, 2000 cache creation, 3000 cache read
        # Rough cost: (500 * $3/MTok) + (200 * $15/MTok) + (2000 * $3.75/MTok) + (3000 * $0.30/MTok)
        # = $0.0015 + $0.003 + $0.0075 + $0.0009 = $0.0129
        stream_output = """
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "I'll analyze the code..."}], "usage": {"input_tokens": 500, "output_tokens": 200, "cache_creation_input_tokens": 2000, "cache_read_input_tokens": 3000}}}
{"type": "result", "subtype": "success", "num_turns": 1, "usage": {"input_tokens": 500, "output_tokens": 200}, "total_cost_usd": 0.0129}
"""

        (
            _,
            _,
            _,
            _,
            _num_turns,
            tokens_in,
            tokens_out,
            _,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        # Should extract the total cost which includes cache tokens
        assert cost_usd == 0.0129
        # Note: tokens_in/tokens_out only show base tokens, not cache tokens
        assert tokens_in == 500
        assert tokens_out == 200


class TestAgentResult:
    """Test AgentResult cost_usd field."""

    def test_agent_result_with_cost(self):
        """Test AgentResult correctly stores cost_usd."""
        result = AgentResult(
            patch="diff --git...",
            success=True,
            tokens_input=1000,
            tokens_output=500,
            cost_usd=0.0225,
        )

        assert result.cost_usd == 0.0225
        assert result.success is True
        assert result.tokens_input == 1000
        assert result.tokens_output == 500

    def test_agent_result_without_cost(self):
        """Test AgentResult defaults to None when cost not provided."""
        result = AgentResult(
            patch="",
            success=False,
            error="Something failed",
        )

        assert result.cost_usd is None
        assert result.success is False

    def test_agent_result_zero_cost(self):
        """Test AgentResult can store zero cost (e.g., cached-only request)."""
        result = AgentResult(
            patch="",
            success=True,
            cost_usd=0.0,
        )

        assert result.cost_usd == 0.0


class TestAgentResultToDict:
    """Test cost serialization in agent_result_to_dict."""

    def test_uses_cost_usd_when_available(self):
        """Test that agent_result_to_dict prefers cost_usd over recalculation."""
        result = AgentResult(
            patch="diff --git...",
            success=True,
            tokens_input=1000,
            tokens_output=500,
            # Cost from API includes cache tokens: $0.025
            cost_usd=0.025,
        )

        # Convert to dict
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        # Should use the API cost, not recalculate
        # If it recalculated from base tokens only, it would be much lower (~$0.0105)
        assert data["cost"] == 0.025
        assert data["patch_generated"] is True
        assert data["tokens"]["input"] == 1000
        assert data["tokens"]["output"] == 500

    def test_fallback_to_calculation_when_no_cost(self):
        """Test that agent_result_to_dict falls back to calculation when cost_usd is None."""
        result = AgentResult(
            patch="",
            success=False,
            tokens_input=1000,
            tokens_output=500,
            cost_usd=None,  # Explicitly None (e.g., older result format)
        )

        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        # Should calculate cost from base tokens
        # Sonnet 4.5: ~$3/MTok input + ~$15/MTok output
        # = (1000 * $3/M) + (500 * $15/M) = $0.003 + $0.0075 = $0.0105
        assert "cost" in data
        expected_cost = (1000 * 0.003 / 1000) + (500 * 0.015 / 1000)
        assert abs(data["cost"] - expected_cost) < 0.0001

    def test_cost_usd_zero_is_used(self):
        """Test that zero cost is used, not treated as None."""
        result = AgentResult(
            patch="",
            success=True,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
        )

        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        # Should use the zero cost from API, not try to recalculate
        assert data["cost"] == 0.0

    def test_preserves_other_fields(self):
        """Test that cost handling doesn't affect other fields."""
        result = AgentResult(
            patch="diff --git...",
            success=True,
            error=None,
            tokens_input=500,
            tokens_output=250,
            iterations=3,
            tool_calls=10,
            tool_usage={"Read": 5, "Edit": 3},
            tool_failures={"Bash": 1},
            tool_errors={"Bash": ["Command not found"]},
            cost_usd=0.0125,
        )

        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        assert data["patch_generated"] is True
        assert data["tokens"]["input"] == 500
        assert data["tokens"]["output"] == 250
        assert data["iterations"] == 3
        assert data["tool_calls"] == 10
        assert data["tool_usage"] == {"Read": 5, "Edit": 3}
        assert data["tool_failures"] == {"Bash": 1}
        assert data["tool_errors"] == {"Bash": ["Command not found"]}
        assert data["cost"] == 0.0125


class TestEndToEndCost:
    """Integration tests for full cost flow."""

    def test_full_flow_with_cache_tokens(self):
        """Test complete flow: stream parsing → AgentResult → dict serialization."""
        # Simulate a real stream output with cache tokens
        stream_output = """
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "Read", "input": {}}], "usage": {"input_tokens": 800, "output_tokens": 100, "cache_creation_input_tokens": 5000, "cache_read_input_tokens": 1200}}}
{"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "file contents"}]}}
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}], "usage": {"input_tokens": 900, "output_tokens": 150, "cache_read_input_tokens": 5000}}}
{"type": "result", "subtype": "success", "num_turns": 2, "usage": {"input_tokens": 1700, "output_tokens": 250}, "total_cost_usd": 0.0312}
"""

        # Parse stream
        (
            total_tool_calls,
            tool_usage,
            _tool_failures,
            _tool_errors,
            num_turns,
            tokens_in,
            tokens_out,
            _result_subtype,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        # Create AgentResult
        result = AgentResult(
            patch="diff --git...",
            success=True,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            iterations=num_turns,
            tool_calls=total_tool_calls,
            tool_usage=tool_usage,
            cost_usd=cost_usd,
        )

        # Verify AgentResult
        assert result.cost_usd == 0.0312
        assert result.tokens_input == 1700
        assert result.tokens_output == 250
        assert result.iterations == 2

        # Convert to dict
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        # Verify final output uses API cost (includes cache tokens)
        assert data["cost"] == 0.0312
        # Without cache tokens, cost would be much lower:
        # (1700 * $3/M) + (250 * $15/M) = $0.0051 + $0.00375 = $0.00885
        # With cache tokens included in total_cost_usd: $0.0312 (3.5x higher)

    def test_backward_compatibility(self):
        """Test that old results without cost_usd still work."""
        # Simulate old stream output without total_cost_usd
        stream_output = """
{"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hello"}], "usage": {"input_tokens": 100, "output_tokens": 50}}}
{"type": "result", "subtype": "success", "num_turns": 1, "usage": {"input_tokens": 100, "output_tokens": 50}}
"""

        # Parse stream (should return None for cost)
        (
            _,
            _tool_usage,
            _,
            _,
            _num_turns,
            tokens_in,
            tokens_out,
            _,
            cost_usd,
        ) = _parse_tool_usage_from_stream(stream_output)

        assert cost_usd is None

        # Create AgentResult without cost
        result = AgentResult(
            patch="",
            success=True,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_usd=cost_usd,  # None
        )

        # Convert to dict (should calculate cost)
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")

        # Should have calculated cost
        assert "cost" in data
        assert data["cost"] > 0
