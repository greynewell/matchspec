"""Integration tests for comparison mode."""

import os

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig
from mcpbr.harness import run_evaluation


@pytest.mark.integration
@pytest.mark.asyncio
async def test_comparison_mode_evaluation():
    """Test full evaluation in comparison mode."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    config = HarnessConfig(
        comparison_mode=True,
        mcp_server_a=MCPServerConfig(
            name="Filesystem A",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        mcp_server_b=MCPServerConfig(
            name="Filesystem B",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        agent_harness="claude-code",
        benchmark="swe-bench-lite",
        sample_size=1,
        timeout_seconds=300,
        max_iterations=5,
    )

    results = await run_evaluation(
        config=config,
        run_mcp=True,
        run_baseline=False,
        verbose=True,
    )

    assert results is not None
    assert len(results.tasks) == 1

    task = results.tasks[0]
    assert task.mcp_server_a is not None
    assert task.mcp_server_b is not None
    assert "comparison" in results.summary
    assert "mcp_server_a" in results.summary
    assert "mcp_server_b" in results.summary

    # Verify comparison statistics are present
    comp = results.summary["comparison"]
    assert "a_vs_b_delta" in comp
    assert "a_vs_b_improvement_pct" in comp
    assert "a_unique_wins" in comp
    assert "b_unique_wins" in comp
    assert "both_wins" in comp
    assert "both_fail" in comp


@pytest.mark.integration
@pytest.mark.asyncio
async def test_comparison_mode_with_different_servers():
    """Test comparison mode with two different MCP servers."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")

    config = HarnessConfig(
        comparison_mode=True,
        mcp_server_a=MCPServerConfig(
            name="Filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        mcp_server_b=MCPServerConfig(
            name="Memory (no MCP)",
            command="echo",  # Dummy command that does nothing
            args=[""],
        ),
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        agent_harness="claude-code",
        benchmark="swe-bench-lite",
        sample_size=1,
        timeout_seconds=300,
        max_iterations=5,
    )

    results = await run_evaluation(
        config=config,
        run_mcp=True,
        run_baseline=False,
        verbose=True,
    )

    assert results is not None
    assert len(results.tasks) == 1

    # Verify metadata includes both server configs
    assert "mcp_server_a" in results.metadata
    assert "mcp_server_b" in results.metadata
    assert results.metadata["mcp_server_a"]["name"] == "Filesystem"
    assert results.metadata["mcp_server_b"]["name"] == "Memory (no MCP)"
