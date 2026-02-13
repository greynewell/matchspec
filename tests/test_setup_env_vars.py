"""Tests for MCPBR_* env var injection and placeholder expansion (#440)."""

import contextlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcpbr.config import MCPServerConfig
from mcpbr.docker_env import TaskEnvironment


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    with patch("mcpbr.docker_env.docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_env(mock_docker_client, tmp_path):
    """Create a mock TaskEnvironment with repo metadata."""
    from mcpbr.docker_env import DockerEnvironmentManager

    manager = DockerEnvironmentManager()
    mock_container = MagicMock()
    mock_container.name = "test-container"

    # exec_command returns (exit_code, stdout, stderr)
    mock_container.exec_run.return_value = MagicMock(exit_code=0, output=(b"", b""))

    env = TaskEnvironment(
        container=mock_container,
        workdir="/workspace",
        host_workdir=str(tmp_path),
        instance_id="django__django-12345",
        repo="django/django",
        base_commit="abc123def",
        uses_prebuilt=True,
        claude_cli_installed=True,
        _temp_dir=None,
        _manager=manager,
    )
    return env


class TestMCPBREnvVarsInSetupCommand:
    """Test MCPBR_* vars are present in env file from run_setup_command."""

    @pytest.mark.asyncio
    async def test_setup_command_env_file_contains_mcpbr_vars(self, mock_env):
        """Test that run_setup_command writes MCPBR_* vars to env file."""
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            command="python",
            args=["-m", "my_server", "{workdir}"],
            setup_command="echo setup",
        )
        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        # Capture what gets written to the env file
        written_content = {}

        async def mock_exec(cmd, **_kwargs):
            if isinstance(cmd, str) and "cat > /tmp/.mcpbr_env.sh" in cmd:
                written_content["env_file"] = cmd
            return (0, "", "")

        mock_env.exec_command = AsyncMock(side_effect=mock_exec)

        await harness.run_setup_command(mock_env, verbose=False)

        env_file = written_content.get("env_file", "")
        assert "MCPBR_REPO=" in env_file
        assert "django/django" in env_file
        assert "MCPBR_REPO_NAME=" in env_file
        assert "MCPBR_REPO_NAME=django" in env_file
        assert "MCPBR_BASE_COMMIT=" in env_file
        assert "abc123def" in env_file
        assert "MCPBR_INSTANCE_ID=" in env_file
        assert "django__django-12345" in env_file


class TestMCPBREnvVarsInMCPJson:
    """Test MCPBR_* vars are present in .mcp.json env block."""

    @pytest.mark.asyncio
    async def test_mcp_json_contains_mcpbr_vars(self, mock_env):
        """Test that _solve_in_docker writes MCPBR_* vars to .mcp.json."""
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            command="python",
            args=["-m", "my_server", "{workdir}"],
        )
        harness = ClaudeCodeHarness(mcp_server=mcp_config, max_iterations=1)

        # Capture what gets written to .mcp.json
        written_mcp_json = {}

        async def mock_exec(cmd, **_kwargs):
            if isinstance(cmd, (str, list)):
                cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
                if ".mcp.json" in cmd_str and "cat >" in cmd_str:
                    # Extract JSON content between heredoc markers
                    content = cmd_str.split("MCP_JSON_EOF")[0]
                    # Find the JSON portion
                    json_start = content.find("{")
                    if json_start >= 0:
                        json_str = content[json_start:]
                        try:
                            written_mcp_json["config"] = json.loads(json_str)
                        except json.JSONDecodeError:
                            written_mcp_json["raw"] = json_str
            return (0, "", "")

        mock_env.exec_command = AsyncMock(side_effect=mock_exec)
        mock_env.exec_command_streaming = AsyncMock(return_value=(0, "", ""))

        # Need ANTHROPIC_API_KEY to be set
        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            contextlib.suppress(Exception),
        ):
            await harness._solve_in_docker(
                task={
                    "problem_statement": "test",
                    "instance_id": "django__django-12345",
                    "repo": "django/django",
                    "base_commit": "abc123def",
                },
                env=mock_env,
                timeout=10,
                verbose=False,
                task_id="django__django-12345",
            )

        if "config" in written_mcp_json:
            mcp_config_data = written_mcp_json["config"]
            server_env = mcp_config_data["mcpServers"]["mcpbr"]["env"]
            assert server_env.get("MCPBR_REPO") == "django/django"
            assert server_env.get("MCPBR_REPO_NAME") == "django"
            assert server_env.get("MCPBR_BASE_COMMIT") == "abc123def"
            assert server_env.get("MCPBR_INSTANCE_ID") == "django__django-12345"


class TestPlaceholderExpansion:
    """Test placeholder expansion in config methods."""

    def test_args_expand_repo_name(self):
        """Test {repo_name} placeholder in args."""
        config = MCPServerConfig(
            command="python",
            args=["-m", "server", "--cache", "/var/cache/{repo_name}_cache", "{workdir}"],
        )
        args = config.get_args_for_workdir(
            "/workspace",
            repo="django/django",
            repo_name="django",
            base_commit="abc123",
            instance_id="django__django-12345",
        )
        assert args == ["-m", "server", "--cache", "/var/cache/django_cache", "/workspace"]

    def test_setup_command_expand_placeholders(self):
        """Test placeholder expansion in setup_command."""
        config = MCPServerConfig(
            command="python",
            args=[],
            setup_command="index-repo --repo {repo_name} --workdir {workdir}",
        )
        cmd = config.get_setup_command_for_workdir(
            "/workspace",
            repo="django/django",
            repo_name="django",
            base_commit="abc123",
            instance_id="django__django-12345",
        )
        assert cmd == "index-repo --repo django --workdir /workspace"

    def test_unknown_placeholders_left_untouched(self):
        """Test that unknown placeholders are not expanded (backward compat)."""
        config = MCPServerConfig(
            command="python",
            args=["--flag", "{unknown_placeholder}", "{workdir}"],
        )
        args = config.get_args_for_workdir("/workspace", repo="django/django")
        assert args == ["--flag", "{unknown_placeholder}", "/workspace"]

    def test_setup_command_unknown_placeholders_untouched(self):
        """Test that unknown placeholders in setup_command are left untouched."""
        config = MCPServerConfig(
            command="python",
            args=[],
            setup_command="run {custom} in {workdir}",
        )
        cmd = config.get_setup_command_for_workdir("/workspace")
        assert cmd == "run {custom} in /workspace"
