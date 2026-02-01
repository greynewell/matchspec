"""Tests for comprehensive pre-flight validation."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig
from mcpbr.preflight import run_comprehensive_preflight


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = HarnessConfig(
        provider="anthropic",
        agent_harness="claude-code",
        model="claude-sonnet-4-5-20250514",
        benchmark="swe-bench-verified",
        sample_size=10,
        timeout_seconds=300,
        max_iterations=10,
        max_concurrent=4,
        use_prebuilt_images=True,
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        ),
    )
    return config


@pytest.fixture
def config_path(tmp_path):
    """Create a temporary config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("provider: anthropic\n")
    return config_file


def test_preflight_all_checks_pass(mock_config, config_path):
    """Test pre-flight when all checks pass."""
    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        # Mock which (MCP server command exists)
        mock_which.return_value = "/usr/bin/npx"

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Should have no failures
        assert len(failures) == 0

        # Check that we have all expected checks
        check_names = [check.name for check in checks]
        assert "Docker" in check_names
        assert "ANTHROPIC_API_KEY" in check_names
        assert "MCP Server" in check_names
        assert "Config File" in check_names
        assert "Dataset Access" in check_names
        assert "Disk Space" in check_names

        # Verify Docker check passed
        docker_check = next(c for c in checks if c.name == "Docker")
        assert docker_check.status == "✓"
        assert "24.0.7" in docker_check.details


def test_preflight_docker_not_running(mock_config, config_path):
    """Test pre-flight when Docker is not running."""
    import docker.errors

    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
    ):
        # Mock Docker to raise exception
        mock_docker.side_effect = docker.errors.DockerException("Connection refused")

        # Mock which (MCP server command exists)
        mock_which.return_value = "/usr/bin/npx"

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Should have failures
        assert len(failures) > 0
        assert any("Docker" in failure for failure in failures)

        # Verify Docker check failed
        docker_check = next(c for c in checks if c.name == "Docker")
        assert docker_check.status == "✗"


def test_preflight_api_key_missing(mock_config, config_path):
    """Test pre-flight when API key is not set."""
    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch.dict(os.environ, {}, clear=True),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        # Mock which
        mock_which.return_value = "/usr/bin/npx"

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Should have failures
        assert len(failures) > 0
        assert any("ANTHROPIC_API_KEY" in failure for failure in failures)

        # Verify API key check failed
        api_key_check = next(c for c in checks if c.name == "ANTHROPIC_API_KEY")
        assert api_key_check.status == "✗"
        assert "Not set" in api_key_check.details


def test_preflight_mcp_server_not_found(mock_config, config_path):
    """Test pre-flight when MCP server command is not found."""
    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        # Mock which (command not found)
        mock_which.return_value = None

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Should have failures
        assert len(failures) > 0
        assert any("not found in PATH" in failure for failure in failures)

        # Verify MCP server check failed
        mcp_check = next(c for c in checks if c.name == "MCP Server")
        assert mcp_check.status == "✗"
        assert "not found" in mcp_check.details


def test_preflight_api_key_masking(mock_config, config_path):
    """Test that API key is properly masked in output."""
    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-api03-1234567890abcdefXYZ"}),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        # Mock which
        mock_which.return_value = "/usr/bin/npx"

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Verify API key check shows masked key
        api_key_check = next(c for c in checks if c.name == "ANTHROPIC_API_KEY")
        assert api_key_check.status == "✓"
        assert "sk-ant-a" in api_key_check.details  # Shows first part (first 8 chars)
        assert "fXYZ" in api_key_check.details  # Shows last part (last 4 chars)
        assert "..." in api_key_check.details  # Has masking
        # Should not show full key
        assert "1234567890abcdef" not in api_key_check.details


def test_preflight_disk_space_warning(mock_config, config_path):
    """Test pre-flight disk space warning."""
    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch("mcpbr.preflight.shutil.which") as mock_which,
        patch("mcpbr.preflight.shutil.disk_usage") as mock_disk,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        # Mock which
        mock_which.return_value = "/usr/bin/npx"

        # Mock disk usage (low space)
        mock_stat = MagicMock()
        mock_stat.free = 5 * 1024**3  # 5 GB
        mock_disk.return_value = mock_stat

        checks, failures = run_comprehensive_preflight(mock_config, config_path)

        # Should not have critical failures (disk space is warning only)
        assert len(failures) == 0

        # Verify disk space check shows warning
        disk_check = next(c for c in checks if c.name == "Disk Space")
        assert disk_check.status == "⚠"
        assert "5 GB" in disk_check.details
        assert not disk_check.critical


def test_preflight_mcp_server_no_command(config_path):
    """Test pre-flight when MCP server has no command."""
    # Config with MCP server but empty command
    config = HarnessConfig(
        provider="anthropic",
        agent_harness="claude-code",
        model="claude-sonnet-4-5-20250514",
        benchmark="swe-bench-verified",
        sample_size=10,
        timeout_seconds=300,
        max_iterations=10,
        max_concurrent=4,
        use_prebuilt_images=True,
        mcp_server=MCPServerConfig(
            command="",  # Empty command
            args=[],
        ),
    )

    with (
        patch("mcpbr.preflight.docker.from_env") as mock_docker,
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
    ):
        # Mock Docker
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"ServerVersion": "24.0.7"}
        mock_docker.return_value = mock_client

        checks, failures = run_comprehensive_preflight(config, config_path)

        # Should have failures
        assert len(failures) > 0
        assert any("not configured" in failure for failure in failures)

        # Verify MCP server check failed
        mcp_check = next(c for c in checks if c.name == "MCP Server")
        assert mcp_check.status == "✗"
        assert "Not configured" in mcp_check.details
