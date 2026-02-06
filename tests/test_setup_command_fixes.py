"""Tests for setup_command bug fixes (#386, #387, #388) and workspace retry (#405).

Bug #386: setup_command runs as root but agent runs as mcpbr user
Bug #387: setup_command may execute before workspace is fully populated
Bug #388: setup_command failures are silent unless --verbose is used
Bug #405: Retry empty workspace after Docker copy
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_container(exec_results=None):
    """Create a mock Docker container with configurable exec_run results.

    Args:
        exec_results: List of (exit_code, stdout_bytes, stderr_bytes) tuples.
            Each call to exec_run pops the next result. If None, defaults to
            a single successful result.
    """
    container = MagicMock()
    if exec_results is None:
        exec_results = [(0, b"ok", b"")]

    call_count = {"n": 0}

    def _exec_run(cmd, **kwargs):
        idx = min(call_count["n"], len(exec_results) - 1)
        call_count["n"] += 1
        exit_code, stdout, stderr = exec_results[idx]
        result = MagicMock()
        result.exit_code = exit_code
        result.output = (stdout, stderr)
        return result

    container.exec_run = _exec_run
    return container


def _make_task_env(container, claude_cli_installed=True):
    """Create a TaskEnvironment-like object for testing."""
    from mcpbr.docker_env import TaskEnvironment

    return TaskEnvironment(
        container=container,
        workdir="/workspace",
        host_workdir="/tmp/test",
        instance_id="test-instance",
        uses_prebuilt=True,
        claude_cli_installed=claude_cli_installed,
    )


# ===========================================================================
# Bug #386: exec_command user parameter
# ===========================================================================


class TestExecCommandUserParam:
    """exec_command must pass user= through to container.exec_run."""

    @pytest.mark.asyncio
    async def test_exec_command_passes_user_to_exec_run(self):
        """When user is specified, it should be forwarded to exec_run."""
        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"hello", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        exit_code, stdout, stderr = await env.exec_command(
            "echo hello",
            timeout=5,
            user="mcpbr",
        )

        assert exit_code == 0
        assert stdout == "hello"

        # Verify user= was passed to the underlying exec_run
        call_kwargs = container.exec_run.call_args
        assert call_kwargs.kwargs.get("user") == "mcpbr" or call_kwargs[1].get("user") == "mcpbr"

    @pytest.mark.asyncio
    async def test_exec_command_default_user_is_empty(self):
        """When no user is specified, user= should be empty string (container default)."""
        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        await env.exec_command("ls", timeout=5)

        call_kwargs = container.exec_run.call_args
        user_val = call_kwargs.kwargs.get("user") or call_kwargs[1].get("user", "")
        assert user_val == ""

    @pytest.mark.asyncio
    async def test_exec_command_user_none_is_empty(self):
        """Explicitly passing user=None should result in empty string."""
        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        await env.exec_command("ls", timeout=5, user=None)

        call_kwargs = container.exec_run.call_args
        user_val = call_kwargs.kwargs.get("user") or call_kwargs[1].get("user", "")
        assert user_val == ""


# ===========================================================================
# Bug #386: run_setup_command runs as mcpbr user
# ===========================================================================


class TestSetupCommandRunsAsMcpbrUser:
    """run_setup_command should execute as mcpbr user in Docker mode."""

    @pytest.mark.asyncio
    async def test_setup_command_uses_mcpbr_user_in_docker(self):
        """When claude_cli_installed=True, setup_command runs as mcpbr user."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="npm run precache",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"done", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container, claude_cli_installed=True)

        await harness.run_setup_command(env, verbose=False)

        # Verify user="mcpbr" was passed
        call_kwargs = container.exec_run.call_args
        user_val = call_kwargs.kwargs.get("user") or call_kwargs[1].get("user", "")
        assert user_val == "mcpbr"

    @pytest.mark.asyncio
    async def test_setup_command_no_user_without_cli(self):
        """When claude_cli_installed=False, setup_command runs as default user."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="npm run precache",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"done", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container, claude_cli_installed=False)

        await harness.run_setup_command(env, verbose=False)

        # Verify user="" (empty = container default, i.e. root)
        call_kwargs = container.exec_run.call_args
        user_val = call_kwargs.kwargs.get("user") or call_kwargs[1].get("user", "")
        assert user_val == ""

    @pytest.mark.asyncio
    async def test_no_setup_command_is_noop(self):
        """When no setup_command is configured, run_setup_command does nothing."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        container.exec_run = MagicMock()

        env = _make_task_env(container)

        await harness.run_setup_command(env, verbose=False)

        # exec_run should never be called
        container.exec_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_mcp_server_is_noop(self):
        """When no mcp_server is configured, run_setup_command does nothing."""
        from mcpbr.harnesses import ClaudeCodeHarness

        harness = ClaudeCodeHarness()

        container = MagicMock()
        container.exec_run = MagicMock()

        env = _make_task_env(container)

        await harness.run_setup_command(env, verbose=False)

        container.exec_run.assert_not_called()


# ===========================================================================
# Bug #387: Workspace verification after copy
# ===========================================================================


class TestWorkspaceVerification:
    """_copy_repo_to_workspace should verify workspace is populated."""

    @pytest.mark.asyncio
    async def test_copy_repo_calls_sync(self):
        """After copying, a sync command should be issued."""
        container = MagicMock()

        # Track all commands passed to exec_run
        commands_run = []

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            commands_run.append(cmd_str)
            result = MagicMock()
            result.exit_code = 0
            # Return "3" for the wc -l check (non-empty workspace)
            if "wc -l" in cmd_str:
                result.output = (b"3", b"")
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"  # Pre-copy state

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)
        await manager._copy_repo_to_workspace(env)

        # Verify sync was called
        sync_calls = [c for c in commands_run if c.strip() == "/bin/bash -c sync"]
        assert len(sync_calls) == 1, f"Expected 1 sync call, got {len(sync_calls)}: {commands_run}"

    @pytest.mark.asyncio
    async def test_copy_repo_verifies_files_exist(self):
        """After copying, workspace should be checked for files."""
        container = MagicMock()

        commands_run = []

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            commands_run.append(cmd_str)
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                result.output = (b"5", b"")
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)
        await manager._copy_repo_to_workspace(env)

        # Verify file count check was performed
        find_calls = [c for c in commands_run if "find /workspace" in c and "wc -l" in c]
        assert len(find_calls) == 1

    @pytest.mark.asyncio
    @patch("asyncio.sleep", return_value=None)
    async def test_copy_repo_raises_on_empty_workspace(self, _mock_sleep):
        """If workspace is empty after all retries, a RuntimeError should be raised."""
        container = MagicMock()

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                result.output = (b"0", b"")  # Empty workspace!
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)

        with pytest.raises(RuntimeError, match="appears empty after copy"):
            await manager._copy_repo_to_workspace(env)

    @pytest.mark.asyncio
    async def test_copy_repo_sets_workdir_on_success(self):
        """On successful copy + verify, workdir should be set to /workspace."""
        container = MagicMock()

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                result.output = (b"10", b"")
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)
        await manager._copy_repo_to_workspace(env)

        assert env.workdir == "/workspace"

    @pytest.mark.asyncio
    @patch("asyncio.sleep", return_value=None)
    async def test_copy_repo_succeeds_after_sync_retry(self, mock_sleep):
        """If workspace is empty initially but populated after sync retry, succeed."""
        container = MagicMock()

        wc_call_count = {"n": 0}

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                wc_call_count["n"] += 1
                if wc_call_count["n"] == 1:
                    result.output = (b"0", b"")  # First check: empty
                else:
                    result.output = (b"3", b"")  # Second check: populated
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)
        await manager._copy_repo_to_workspace(env)

        assert env.workdir == "/workspace"
        mock_sleep.assert_awaited_once_with(2)

    @pytest.mark.asyncio
    @patch("asyncio.sleep", return_value=None)
    async def test_copy_repo_succeeds_after_full_copy_retry(self, mock_sleep):
        """If workspace is empty after sync retry but populated after full copy retry."""
        container = MagicMock()

        wc_call_count = {"n": 0}

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                wc_call_count["n"] += 1
                if wc_call_count["n"] <= 2:
                    result.output = (b"0", b"")  # First two checks: empty
                else:
                    result.output = (b"5", b"")  # Third check: populated
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)
        await manager._copy_repo_to_workspace(env)

        assert env.workdir == "/workspace"
        # Verify sleep was called during sync retry phase
        mock_sleep.assert_awaited_once_with(2)

    @pytest.mark.asyncio
    @patch("asyncio.sleep", return_value=None)
    async def test_copy_repo_raises_after_all_retries_exhausted(self, mock_sleep):
        """If workspace is empty after all retries, RuntimeError should be raised."""
        container = MagicMock()

        def _exec_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            result = MagicMock()
            result.exit_code = 0
            if "wc -l" in cmd_str:
                result.output = (b"0", b"")  # Always empty
            else:
                result.output = (b"", b"")
            return result

        container.exec_run = _exec_run

        env = _make_task_env(container)
        env.workdir = "/testbed"

        from mcpbr.docker_env import DockerEnvironmentManager

        manager = DockerEnvironmentManager.__new__(DockerEnvironmentManager)

        with pytest.raises(RuntimeError, match="appears empty after copy"):
            await manager._copy_repo_to_workspace(env)

        # Verify sleep was called (sync retry phase)
        mock_sleep.assert_awaited_once_with(2)


# ===========================================================================
# Bug #388: Setup command failures should always warn
# ===========================================================================


class TestSetupCommandWarnings:
    """setup_command failures must always produce visible warnings."""

    @pytest.mark.asyncio
    async def test_failure_prints_warning_without_verbose(self):
        """A failing setup_command should print a warning even without --verbose."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="bad-command --wrong-flag",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 1
        result_mock.output = (b"", b"command not found: bad-command")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        # Capture console output
        console_output = []
        harness._console = MagicMock()
        harness._console.print = MagicMock(side_effect=lambda msg: console_output.append(msg))

        await harness.run_setup_command(env, verbose=False)

        # Warning should be printed even without verbose
        assert any("Setup command exited with code 1" in msg for msg in console_output), (
            f"Expected warning about exit code, got: {console_output}"
        )

    @pytest.mark.asyncio
    async def test_failure_does_not_show_stderr_without_verbose(self):
        """Stderr details should only appear in verbose mode."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="bad-command",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 1
        result_mock.output = (b"", b"some detailed error output")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        console_output = []
        harness._console = MagicMock()
        harness._console.print = MagicMock(side_effect=lambda msg: console_output.append(msg))

        await harness.run_setup_command(env, verbose=False)

        # Stderr details should NOT appear without verbose
        assert not any("some detailed error output" in msg for msg in console_output), (
            f"Stderr should not appear without verbose: {console_output}"
        )

    @pytest.mark.asyncio
    async def test_failure_shows_stderr_with_verbose(self):
        """Stderr details should appear when verbose=True."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="bad-command",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 127
        result_mock.output = (b"", b"command not found: bad-command")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        console_output = []
        harness._console = MagicMock()
        harness._console.print = MagicMock(side_effect=lambda msg: console_output.append(msg))

        await harness.run_setup_command(env, verbose=True)

        # Both warning and stderr should appear
        assert any("Setup command exited with code 127" in msg for msg in console_output)
        assert any("command not found" in msg for msg in console_output)

    @pytest.mark.asyncio
    async def test_success_is_quiet_without_verbose(self):
        """A successful setup_command should produce no output without verbose."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="echo ok",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"ok", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        console_output = []
        harness._console = MagicMock()
        harness._console.print = MagicMock(side_effect=lambda msg: console_output.append(msg))

        await harness.run_setup_command(env, verbose=False)

        # No output on success without verbose
        assert len(console_output) == 0

    @pytest.mark.asyncio
    async def test_success_shows_checkmark_with_verbose(self):
        """A successful setup_command should show a checkmark with verbose."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="echo ok",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 0
        result_mock.output = (b"ok", b"")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)

        console_output = []
        harness._console = MagicMock()
        harness._console.print = MagicMock(side_effect=lambda msg: console_output.append(msg))

        await harness.run_setup_command(env, verbose=True)

        # Should show both "Running setup command" and success checkmark
        assert any("Setup command completed" in msg for msg in console_output)

    @pytest.mark.asyncio
    async def test_failure_is_non_fatal(self):
        """A failing setup_command should not raise an exception."""
        from mcpbr.config import MCPServerConfig
        from mcpbr.harnesses import ClaudeCodeHarness

        mcp_config = MCPServerConfig(
            name="test-server",
            command="node",
            args=["server.js"],
            setup_command="exit 1",
        )

        harness = ClaudeCodeHarness(mcp_server=mcp_config)

        container = MagicMock()
        result_mock = MagicMock()
        result_mock.exit_code = 1
        result_mock.output = (b"", b"error")
        container.exec_run = MagicMock(return_value=result_mock)

        env = _make_task_env(container)
        harness._console = MagicMock()

        # Should not raise — failures are non-fatal
        await harness.run_setup_command(env, verbose=False)
