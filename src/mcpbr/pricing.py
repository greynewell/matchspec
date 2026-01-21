"""Model pricing information and cost calculation utilities.

This module provides pricing data for supported LLM models and utilities for
calculating API costs based on token usage.

Pricing is per million tokens (MTok) and is current as of January 2026.
Prices may change - check official provider documentation for updates:
- Anthropic: https://www.anthropic.com/pricing
"""

from dataclasses import dataclass


@dataclass
class ModelPricing:
    """Pricing information for a model."""

    model_id: str
    provider: str
    input_price_per_mtok: float  # Price per million input tokens
    output_price_per_mtok: float  # Price per million output tokens
    supports_prompt_caching: bool = False
    cache_creation_price_per_mtok: float = 0.0  # If caching supported
    cache_read_price_per_mtok: float = 0.0  # If caching supported
    notes: str = ""


# Model pricing database (as of January 2026)
# Prices are per million tokens (MTok)
MODEL_PRICING: dict[str, ModelPricing] = {
    # Claude 4.5 Series (Latest - 2026)
    "claude-opus-4-5-20251101": ModelPricing(
        model_id="claude-opus-4-5-20251101",
        provider="Anthropic",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=6.25,  # 25% markup on input
        cache_read_price_per_mtok=0.50,  # 90% discount on input
        notes="Most capable Claude 4.5 model",
    ),
    "claude-sonnet-4-5-20250929": ModelPricing(
        model_id="claude-sonnet-4-5-20250929",
        provider="Anthropic",
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=3.75,  # 25% markup on input
        cache_read_price_per_mtok=0.30,  # 90% discount on input
        notes="Balanced performance and cost",
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        model_id="claude-haiku-4-5-20251001",
        provider="Anthropic",
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=1.25,  # 25% markup on input
        cache_read_price_per_mtok=0.10,  # 90% discount on input
        notes="Fastest and most cost-effective",
    ),
    # Aliases - map to their corresponding full model IDs
    "opus": ModelPricing(
        model_id="opus",
        provider="Anthropic",
        input_price_per_mtok=5.00,
        output_price_per_mtok=25.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=6.25,
        cache_read_price_per_mtok=0.50,
        notes="Alias for latest Opus model",
    ),
    "sonnet": ModelPricing(
        model_id="sonnet",
        provider="Anthropic",
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=3.75,
        cache_read_price_per_mtok=0.30,
        notes="Alias for latest Sonnet model",
    ),
    "haiku": ModelPricing(
        model_id="haiku",
        provider="Anthropic",
        input_price_per_mtok=1.00,
        output_price_per_mtok=5.00,
        supports_prompt_caching=True,
        cache_creation_price_per_mtok=1.25,
        cache_read_price_per_mtok=0.10,
        notes="Alias for latest Haiku model",
    ),
}


def get_model_pricing(model_id: str) -> ModelPricing | None:
    """Get pricing information for a model.

    Args:
        model_id: Model identifier (e.g., "claude-sonnet-4-5-20250929" or "sonnet").

    Returns:
        ModelPricing object if found, None otherwise.
    """
    return MODEL_PRICING.get(model_id)


def calculate_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float | None:
    """Calculate the cost of API usage for a model.

    Args:
        model_id: Model identifier.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        cache_creation_tokens: Number of tokens used for cache creation (if applicable).
        cache_read_tokens: Number of tokens read from cache (if applicable).

    Returns:
        Total cost in USD, or None if model pricing is not available.
    """
    pricing = get_model_pricing(model_id)
    if not pricing:
        return None

    # Convert tokens to millions
    input_mtok = input_tokens / 1_000_000
    output_mtok = output_tokens / 1_000_000
    cache_creation_mtok = cache_creation_tokens / 1_000_000
    cache_read_mtok = cache_read_tokens / 1_000_000

    # Calculate costs
    input_cost = input_mtok * pricing.input_price_per_mtok
    output_cost = output_mtok * pricing.output_price_per_mtok
    cache_creation_cost = cache_creation_mtok * pricing.cache_creation_price_per_mtok
    cache_read_cost = cache_read_mtok * pricing.cache_read_price_per_mtok

    total_cost = input_cost + output_cost + cache_creation_cost + cache_read_cost
    return total_cost


def format_cost(cost: float | None) -> str:
    """Format a cost value for display.

    Args:
        cost: Cost in USD, or None if unavailable.

    Returns:
        Formatted cost string (e.g., "$0.0045" or "N/A").
    """
    if cost is None:
        return "N/A"
    if cost == 0.0:
        return "$0.00"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"


def calculate_cost_per_resolved(total_cost: float, resolved_count: int) -> float | None:
    """Calculate cost per resolved task.

    Args:
        total_cost: Total cost in USD.
        resolved_count: Number of resolved tasks.

    Returns:
        Cost per resolved task, or None if no tasks were resolved.
    """
    if resolved_count == 0:
        return None
    return total_cost / resolved_count


def calculate_cost_effectiveness(
    mcp_cost: float,
    baseline_cost: float,
    mcp_resolved: int,
    baseline_resolved: int,
) -> dict[str, float | None]:
    """Calculate cost-effectiveness metrics comparing MCP vs baseline.

    Args:
        mcp_cost: Total cost for MCP runs.
        baseline_cost: Total cost for baseline runs.
        mcp_resolved: Number of tasks resolved by MCP.
        baseline_resolved: Number of tasks resolved by baseline.

    Returns:
        Dictionary with cost-effectiveness metrics:
        - mcp_cost_per_resolved: Cost per resolved task for MCP
        - baseline_cost_per_resolved: Cost per resolved task for baseline
        - cost_per_additional_resolution: Marginal cost per additional task resolved by MCP
    """
    mcp_cost_per = calculate_cost_per_resolved(mcp_cost, mcp_resolved)
    baseline_cost_per = calculate_cost_per_resolved(baseline_cost, baseline_resolved)

    # Calculate marginal cost per additional resolution
    additional_resolutions = mcp_resolved - baseline_resolved
    additional_cost = mcp_cost - baseline_cost
    cost_per_additional = None
    if additional_resolutions > 0:
        cost_per_additional = additional_cost / additional_resolutions

    return {
        "mcp_cost_per_resolved": mcp_cost_per,
        "baseline_cost_per_resolved": baseline_cost_per,
        "cost_per_additional_resolution": cost_per_additional,
    }
