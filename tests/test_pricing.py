"""Tests for pricing module."""

import pytest

from mcpbr.pricing import (
    calculate_cost,
    calculate_cost_effectiveness,
    calculate_cost_per_resolved,
    format_cost,
    get_model_pricing,
)


class TestGetModelPricing:
    """Tests for get_model_pricing function."""

    def test_get_sonnet_pricing(self) -> None:
        """Test getting pricing for Sonnet model."""
        pricing = get_model_pricing("claude-sonnet-4-5-20250929")
        assert pricing is not None
        assert pricing.model_id == "claude-sonnet-4-5-20250929"
        assert pricing.provider == "Anthropic"
        assert pricing.input_price_per_mtok == 3.00
        assert pricing.output_price_per_mtok == 15.00

    def test_get_opus_pricing(self) -> None:
        """Test getting pricing for Opus model."""
        pricing = get_model_pricing("claude-opus-4-5-20251101")
        assert pricing is not None
        assert pricing.model_id == "claude-opus-4-5-20251101"
        assert pricing.input_price_per_mtok == 5.00
        assert pricing.output_price_per_mtok == 25.00

    def test_get_haiku_pricing(self) -> None:
        """Test getting pricing for Haiku model."""
        pricing = get_model_pricing("claude-haiku-4-5-20251001")
        assert pricing is not None
        assert pricing.model_id == "claude-haiku-4-5-20251001"
        assert pricing.input_price_per_mtok == 1.00
        assert pricing.output_price_per_mtok == 5.00

    def test_get_alias_pricing(self) -> None:
        """Test getting pricing for model alias."""
        pricing = get_model_pricing("sonnet")
        assert pricing is not None
        assert pricing.model_id == "sonnet"
        assert pricing.input_price_per_mtok == 3.00
        assert pricing.output_price_per_mtok == 15.00

    def test_get_unknown_model(self) -> None:
        """Test getting pricing for unknown model."""
        pricing = get_model_pricing("unknown-model")
        assert pricing is None


class TestCalculateCost:
    """Tests for calculate_cost function."""

    def test_calculate_sonnet_cost(self) -> None:
        """Test calculating cost for Sonnet model."""
        # 1 million input, 1 million output
        cost = calculate_cost("claude-sonnet-4-5-20250929", 1_000_000, 1_000_000)
        assert cost is not None
        # $3.00 input + $15.00 output = $18.00
        assert cost == pytest.approx(18.00, abs=0.01)

    def test_calculate_haiku_cost(self) -> None:
        """Test calculating cost for Haiku model."""
        # 500k input, 200k output
        cost = calculate_cost("claude-haiku-4-5-20251001", 500_000, 200_000)
        assert cost is not None
        # $0.50 input + $1.00 output = $1.50
        assert cost == pytest.approx(1.50, abs=0.01)

    def test_calculate_opus_cost(self) -> None:
        """Test calculating cost for Opus model."""
        # 100k input, 50k output
        cost = calculate_cost("claude-opus-4-5-20251101", 100_000, 50_000)
        assert cost is not None
        # $0.50 input + $1.25 output = $1.75
        assert cost == pytest.approx(1.75, abs=0.01)

    def test_calculate_cost_with_caching(self) -> None:
        """Test calculating cost with prompt caching."""
        # Sonnet with caching
        cost = calculate_cost(
            "claude-sonnet-4-5-20250929",
            input_tokens=1_000_000,
            output_tokens=500_000,
            cache_creation_tokens=500_000,
            cache_read_tokens=200_000,
        )
        assert cost is not None
        # $3.00 input + $7.50 output + $1.875 cache creation + $0.06 cache read
        # = $12.435
        assert cost == pytest.approx(12.435, abs=0.01)

    def test_calculate_cost_zero_tokens(self) -> None:
        """Test calculating cost with zero tokens."""
        cost = calculate_cost("claude-sonnet-4-5-20250929", 0, 0)
        assert cost is not None
        assert cost == 0.0

    def test_calculate_cost_unknown_model(self) -> None:
        """Test calculating cost for unknown model."""
        cost = calculate_cost("unknown-model", 1_000_000, 1_000_000)
        assert cost is None

    def test_calculate_small_token_count(self) -> None:
        """Test calculating cost with small token count."""
        # 100 input, 500 output tokens for Sonnet
        cost = calculate_cost("claude-sonnet-4-5-20250929", 100, 500)
        assert cost is not None
        # $0.0003 input + $0.0075 output = $0.0078
        assert cost == pytest.approx(0.0078, abs=0.0001)


class TestFormatCost:
    """Tests for format_cost function."""

    def test_format_large_cost(self) -> None:
        """Test formatting large cost values."""
        assert format_cost(100.50) == "$100.50"
        assert format_cost(1.23) == "$1.23"

    def test_format_small_cost(self) -> None:
        """Test formatting small cost values."""
        assert format_cost(0.0078) == "$0.0078"
        assert format_cost(0.0001) == "$0.0001"

    def test_format_zero_cost(self) -> None:
        """Test formatting zero cost."""
        assert format_cost(0.0) == "$0.00"

    def test_format_none_cost(self) -> None:
        """Test formatting None cost."""
        assert format_cost(None) == "N/A"


class TestCalculateCostPerResolved:
    """Tests for calculate_cost_per_resolved function."""

    def test_calculate_cost_per_resolved(self) -> None:
        """Test calculating cost per resolved task."""
        cost_per = calculate_cost_per_resolved(10.0, 5)
        assert cost_per is not None
        assert cost_per == 2.0

    def test_calculate_cost_per_resolved_one_task(self) -> None:
        """Test calculating cost per resolved with one task."""
        cost_per = calculate_cost_per_resolved(5.0, 1)
        assert cost_per is not None
        assert cost_per == 5.0

    def test_calculate_cost_per_resolved_zero_resolved(self) -> None:
        """Test calculating cost per resolved with zero resolved."""
        cost_per = calculate_cost_per_resolved(10.0, 0)
        assert cost_per is None


class TestCalculateCostEffectiveness:
    """Tests for calculate_cost_effectiveness function."""

    def test_calculate_cost_effectiveness_improvement(self) -> None:
        """Test cost effectiveness when MCP improves results."""
        metrics = calculate_cost_effectiveness(
            mcp_cost=20.0,
            baseline_cost=15.0,
            mcp_resolved=10,
            baseline_resolved=5,
        )

        assert metrics["mcp_cost_per_resolved"] == 2.0
        assert metrics["baseline_cost_per_resolved"] == 3.0
        # Additional 5 resolutions for $5 more = $1 per additional
        assert metrics["cost_per_additional_resolution"] == 1.0

    def test_calculate_cost_effectiveness_no_improvement(self) -> None:
        """Test cost effectiveness when MCP doesn't improve results."""
        metrics = calculate_cost_effectiveness(
            mcp_cost=20.0,
            baseline_cost=15.0,
            mcp_resolved=5,
            baseline_resolved=5,
        )

        assert metrics["mcp_cost_per_resolved"] == 4.0
        assert metrics["baseline_cost_per_resolved"] == 3.0
        # No additional resolutions
        assert metrics["cost_per_additional_resolution"] is None

    def test_calculate_cost_effectiveness_baseline_worse(self) -> None:
        """Test cost effectiveness when baseline performs worse."""
        metrics = calculate_cost_effectiveness(
            mcp_cost=10.0,
            baseline_cost=20.0,
            mcp_resolved=8,
            baseline_resolved=2,
        )

        assert metrics["mcp_cost_per_resolved"] == 1.25
        assert metrics["baseline_cost_per_resolved"] == 10.0
        # Additional 6 resolutions for -$10 (savings) = -$1.67 per additional
        assert metrics["cost_per_additional_resolution"] == pytest.approx(-1.67, abs=0.01)

    def test_calculate_cost_effectiveness_zero_resolved(self) -> None:
        """Test cost effectiveness when nothing is resolved."""
        metrics = calculate_cost_effectiveness(
            mcp_cost=10.0,
            baseline_cost=10.0,
            mcp_resolved=0,
            baseline_resolved=0,
        )

        assert metrics["mcp_cost_per_resolved"] is None
        assert metrics["baseline_cost_per_resolved"] is None
        assert metrics["cost_per_additional_resolution"] is None
