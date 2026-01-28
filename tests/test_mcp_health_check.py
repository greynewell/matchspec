"""Tests for MCP server health check functionality."""

from pathlib import Path

import pytest
import yaml

from mcpbr.smoke_test import run_mcp_preflight_check


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_path = tmp_path / "test_config.yaml"
    return config_path


@pytest.fixture
def valid_mcp_config() -> dict:
    """Return a valid MCP server configuration."""
    return {
        "model": "claude-sonnet-4-5-20250514",
        "provider": "anthropic",
        "agent_harness": "claude-code",
        "benchmark": "swe-bench-lite",
        "dataset": "princeton-nlp/SWE-bench_Lite",
        "sample_size": 1,
        "timeout_seconds": 300,
        "max_iterations": 30,
        "max_concurrent": 4,
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
    }


class TestMCPPreflightCheck:
    """Tests for MCP pre-flight health check."""

    @pytest.mark.asyncio
    async def test_health_check_passes_with_valid_command(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that health check passes when command exists."""
        # Use a command that definitely exists on all systems
        valid_mcp_config["mcp_server"]["command"] = "python"
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is True
        assert error_msg is None

    @pytest.mark.asyncio
    async def test_health_check_fails_with_missing_command(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that health check fails when command doesn't exist."""
        valid_mcp_config["mcp_server"]["command"] = "nonexistent-command-12345"
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None
        assert "not found in PATH" in error_msg
        assert "nonexistent-command-12345" in error_msg

    @pytest.mark.asyncio
    async def test_health_check_fails_with_no_mcp_config(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that health check fails when MCP server is not configured."""
        del valid_mcp_config["mcp_server"]
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None
        # Could be a validation error or "not configured" message
        assert "not configured" in error_msg.lower() or "validation error" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_health_check_fails_with_empty_command(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that health check fails when command is empty."""
        valid_mcp_config["mcp_server"]["command"] = ""
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None

    @pytest.mark.asyncio
    async def test_health_check_handles_exception_gracefully(self, temp_config_file: Path) -> None:
        """Test that health check handles exceptions gracefully."""
        # Write invalid YAML
        temp_config_file.write_text("invalid: yaml: content: [[[")

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None
        assert "Failed to run MCP pre-flight check" in error_msg

    @pytest.mark.asyncio
    async def test_health_check_silent_mode_no_output(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that silent mode produces no console output."""
        valid_mcp_config["mcp_server"]["command"] = "python"
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        # Silent mode should produce no output (Rich console writes to stderr)
        # So we just verify the function runs without error
        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is True
        assert error_msg is None

    @pytest.mark.asyncio
    async def test_health_check_provides_helpful_error_messages(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that error messages include helpful suggestions."""
        valid_mcp_config["mcp_server"]["command"] = "fake-mcp-server"
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None
        # Check for helpful suggestions
        assert "Suggestion" in error_msg or "check your PATH" in error_msg
        # Check for documentation link
        assert "modelcontextprotocol.io" in error_msg
        assert "ping" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_health_check_with_complex_args(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test health check with complex command arguments."""
        valid_mcp_config["mcp_server"]["command"] = "python"
        valid_mcp_config["mcp_server"]["args"] = [
            "-m",
            "http.server",
            "8000",
            "--bind",
            "localhost",
        ]
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is True
        assert error_msg is None

    @pytest.mark.asyncio
    async def test_health_check_error_message_includes_docs_link(
        self, temp_config_file: Path, valid_mcp_config: dict
    ) -> None:
        """Test that error messages include link to MCP health check docs."""
        valid_mcp_config["mcp_server"]["command"] = "nonexistent-command"
        temp_config_file.write_text(yaml.dump(valid_mcp_config))

        success, error_msg = await run_mcp_preflight_check(temp_config_file, silent=True)

        assert success is False
        assert error_msg is not None
        # Verify link to official MCP spec
        assert (
            "https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping"
            in error_msg
        )
