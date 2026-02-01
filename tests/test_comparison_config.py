"""Tests for comparison mode configuration."""

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig


class TestComparisonConfig:
    """Tests for comparison mode configuration validation."""

    def test_comparison_mode_requires_both_servers(self):
        """Test that comparison mode requires both mcp_server_a and mcp_server_b."""
        with pytest.raises(ValueError, match="requires both mcp_server_a and mcp_server_b"):
            HarnessConfig(
                comparison_mode=True,
                mcp_server_a=MCPServerConfig(command="npx", args=[]),
                # Missing mcp_server_b
            )

    def test_comparison_mode_rejects_single_server(self):
        """Test that comparison mode rejects mcp_server field."""
        with pytest.raises(ValueError, match="use mcp_server_a/b instead"):
            HarnessConfig(
                comparison_mode=True,
                mcp_server=MCPServerConfig(command="npx", args=[]),
                mcp_server_a=MCPServerConfig(command="npx", args=[]),
                mcp_server_b=MCPServerConfig(command="node", args=[]),
            )

    def test_single_server_mode_requires_mcp_server(self):
        """Test that non-comparison mode requires mcp_server."""
        with pytest.raises(ValueError, match="mcp_server required"):
            HarnessConfig(
                comparison_mode=False,
                # Missing mcp_server
            )

    def test_single_server_mode_rejects_comparison_servers(self):
        """Test that single server mode rejects mcp_server_a/b fields."""
        with pytest.raises(ValueError, match="mcp_server_a/b only valid in comparison_mode"):
            HarnessConfig(
                comparison_mode=False,
                mcp_server=MCPServerConfig(command="npx", args=[]),
                mcp_server_a=MCPServerConfig(command="npx", args=[]),
            )

    def test_valid_comparison_config(self):
        """Test valid comparison mode configuration."""
        config = HarnessConfig(
            comparison_mode=True,
            mcp_server_a=MCPServerConfig(
                name="Server A",
                command="npx",
                args=["-y", "server-a"],
            ),
            mcp_server_b=MCPServerConfig(
                name="Server B",
                command="npx",
                args=["-y", "server-b"],
            ),
        )
        assert config.comparison_mode
        assert config.mcp_server_a.name == "Server A"
        assert config.mcp_server_b.name == "Server B"

    def test_backward_compatibility_single_server(self):
        """Test backward compatibility with single server configs."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
        )
        assert not config.comparison_mode
        assert config.mcp_server is not None
        assert config.mcp_server_a is None
        assert config.mcp_server_b is None
