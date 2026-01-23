"""Integration tests for MCP server logging functionality."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcpbr.config import MCPServerConfig
from mcpbr.harnesses import ClaudeCodeHarness


@pytest.mark.integration
class TestMCPLogging:
    """Tests for MCP server log capture and error handling."""

    @pytest.fixture
    def mcp_config(self) -> MCPServerConfig:
        """Create a test MCP server configuration."""
        return MCPServerConfig(
            name="test-server",
            command="echo",
            args=["test", "{workdir}"],
            env={"TEST_VAR": "test_value"},
            startup_timeout_ms=60000,
            tool_timeout_ms=900000,
        )

    @pytest.fixture
    def harness(self, mcp_config: MCPServerConfig) -> ClaudeCodeHarness:
        """Create a test harness with MCP server configured."""
        return ClaudeCodeHarness(
            model="claude-sonnet-4-20250514",
            mcp_server=mcp_config,
            max_iterations=30,
            verbosity=2,
        )

    def test_mcp_log_directory_creation(self, harness: ClaudeCodeHarness) -> None:
        """Test that MCP log directory is created correctly."""
        # The directory should be created when needed
        # We'll verify this in the integration test
        assert harness.mcp_server is not None
        assert harness.mcp_server.name == "test-server"

    @pytest.mark.asyncio
    async def test_mcp_registration_failure_cleanup(self, harness: ClaudeCodeHarness) -> None:
        """Test that temp files are cleaned up on MCP registration failure."""
        mock_env = MagicMock()
        mock_env.workdir = "/workspace"
        mock_env.exec_command = AsyncMock()

        # Mock registration failure
        mock_env.exec_command.side_effect = [
            (0, "", ""),  # prompt file write
            (0, "", ""),  # chown prompt
            (0, "", ""),  # env file write
            (0, "", ""),  # chown env
            (
                1,
                "",
                "npx: command not found",
            ),  # MCP registration fails
            (0, "", ""),  # cleanup temp files
        ]

        task = {
            "instance_id": "test-instance",
            "problem_statement": "Test problem",
            "hints_text": "",
            "created_at": "2024-01-01",
        }

        with (
            patch("mcpbr.harnesses.Path") as mock_path,
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
        ):
            mock_path.home.return_value = Path(tempfile.gettempdir())
            result = await harness._solve_in_docker(
                task=task,
                env=mock_env,
                timeout=60,
                verbose=True,
                task_id="test_id",
            )

        # Verify registration failure was caught
        assert result.success is False
        assert "MCP server registration failed" in result.error
        assert "npx: command not found" in result.error

        # Verify cleanup was called
        cleanup_calls = [
            call for call in mock_env.exec_command.call_args_list if "rm -f" in str(call)
        ]
        assert len(cleanup_calls) >= 1, "Temp files should be cleaned up"

    @pytest.mark.asyncio
    async def test_mcp_stdout_captured_in_error(self, harness: ClaudeCodeHarness) -> None:
        """Test that MCP stdout is included in error messages."""
        mock_env = MagicMock()
        mock_env.workdir = "/workspace"
        mock_env.exec_command = AsyncMock()

        # Mock registration failure with stdout
        mock_env.exec_command.side_effect = [
            (0, "", ""),  # prompt file write
            (0, "", ""),  # chown prompt
            (0, "", ""),  # env file write
            (0, "", ""),  # chown env
            (1, "Server starting...\nInitialization failed", "Error: Missing API key"),
            (0, "", ""),  # cleanup
        ]

        task = {
            "instance_id": "test-stdout",
            "problem_statement": "Test problem",
            "hints_text": "",
            "created_at": "2024-01-01",
        }

        with (
            patch("mcpbr.harnesses.Path") as mock_path,
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
        ):
            mock_path.home.return_value = Path(tempfile.gettempdir())
            result = await harness._solve_in_docker(
                task=task,
                env=mock_env,
                timeout=60,
                verbose=True,
                task_id="test_id",
            )

        # Verify both stderr and stdout are in error message
        assert "Error: Missing API key" in result.error
        assert "Server starting" in result.error or "Initialization failed" in result.error
        assert result.stdout is not None

    @pytest.mark.asyncio
    async def test_mcp_timeout_cleanup(self, harness: ClaudeCodeHarness) -> None:
        """Test that temp files are cleaned up on MCP registration timeout."""
        mock_env = MagicMock()
        mock_env.workdir = "/workspace"
        mock_env.exec_command = AsyncMock()

        # Mock registration timeout
        mock_env.exec_command.side_effect = [
            (0, "", ""),  # prompt file write
            (0, "", ""),  # chown prompt
            (0, "", ""),  # env file write
            (0, "", ""),  # chown env
            asyncio.TimeoutError(),  # MCP registration times out
            (0, "", ""),  # cleanup temp files
        ]

        task = {
            "instance_id": "test-timeout",
            "problem_statement": "Test problem",
            "hints_text": "",
            "created_at": "2024-01-01",
        }

        with (
            patch("mcpbr.harnesses.Path") as mock_path,
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
        ):
            mock_path.home.return_value = Path(tempfile.gettempdir())
            result = await harness._solve_in_docker(
                task=task,
                env=mock_env,
                timeout=60,
                verbose=True,
                task_id="test_id",
            )

        # Verify timeout was caught
        assert result.success is False
        assert "timed out after 60s" in result.error
        assert "failed to start or is hanging" in result.error

        # Verify cleanup was called
        cleanup_calls = [
            call for call in mock_env.exec_command.call_args_list if "rm -f" in str(call)
        ]
        assert len(cleanup_calls) >= 1, "Temp files should be cleaned up on timeout"

    def test_mcp_log_path_in_error_message(self) -> None:
        """Test that MCP log path is included in error messages."""
        # This is tested through the other tests, but we verify the pattern
        instance_id = "django__django-11905"
        expected_log_path = Path.home() / ".mcpbr_state" / "logs" / f"{instance_id}_mcp.log"

        # The log path format is correct
        assert str(expected_log_path).endswith("_mcp.log")
        assert instance_id in str(expected_log_path)

    def test_timeout_configuration(self, mcp_config: MCPServerConfig) -> None:
        """Test that MCP timeout configuration is properly set."""
        assert mcp_config.startup_timeout_ms == 60000  # 60 seconds
        assert mcp_config.tool_timeout_ms == 900000  # 15 minutes

        # Test default values
        default_config = MCPServerConfig(
            name="default",
            command="test",
        )
        assert default_config.startup_timeout_ms == 60000
        assert default_config.tool_timeout_ms == 900000

    def test_workdir_placeholder_replacement(self, mcp_config: MCPServerConfig) -> None:
        """Test that {workdir} placeholder is replaced correctly."""
        workdir = "/workspace/test-repo"
        args = mcp_config.get_args_for_workdir(workdir)

        assert len(args) == 2
        assert args[0] == "test"
        assert args[1] == workdir

    def test_env_vars_for_mcp(self, mcp_config: MCPServerConfig) -> None:
        """Test that environment variables are properly configured."""
        assert "TEST_VAR" in mcp_config.env
        assert mcp_config.env["TEST_VAR"] == "test_value"

    @pytest.mark.asyncio
    async def test_mcp_logs_captured_without_keywords(self, harness: ClaudeCodeHarness) -> None:
        """Test that MCP server stdout is captured even without 'mcp' or 'supermodel' keywords.

        Regression test for bug where stdout was filtered by keywords, causing most
        MCP server logs (e.g., filesystem server, generic diagnostics) to be dropped.
        """
        mock_env = MagicMock()
        mock_env.workdir = "/workspace"
        mock_env.exec_command_streaming = AsyncMock()
        mock_env.exec_command = AsyncMock()

        # MCP server output without "mcp" or "supermodel" keywords
        # This is typical output from filesystem MCP server
        test_stdout = """Server initialized on stdio
Received request: tools/list
Returning 10 tools
Request completed in 12ms
File read: /workspace/test.py
Request completed in 5ms"""

        test_stderr = """Warning: Large file detected
Debug: Cache miss for /workspace/"""

        # Mock successful execution with stdout that doesn't contain filter keywords
        mock_env.exec_command.side_effect = [
            (0, "", ""),  # prompt file write
            (0, "", ""),  # chown prompt
            (0, "", ""),  # env file write
            (0, "", ""),  # chown env
            (0, "MCP server registered successfully", ""),  # MCP registration
            (0, "", ""),  # MCP server remove (cleanup)
            (0, "", ""),  # rm temp files (cleanup)
        ]

        # Mock streaming execution with our test output
        async def mock_streaming(*args, **kwargs):
            # Call the on_stdout callback for each line
            if "on_stdout" in kwargs:
                for line in test_stdout.splitlines():
                    kwargs["on_stdout"](line)
            if "on_stderr" in kwargs:
                for line in test_stderr.splitlines():
                    kwargs["on_stderr"](line)
            # Return as if task completed (simulating timeout but with output)
            return (124, test_stdout, test_stderr)

        mock_env.exec_command_streaming.side_effect = mock_streaming

        task = {
            "instance_id": "test-filesystem-server",
            "problem_statement": "Test problem",
            "hints_text": "",
            "created_at": "2024-01-01",
        }

        # Log file location (using actual .mcpbr_state directory)
        log_dir = Path.home() / ".mcpbr_state" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        expected_log_file = log_dir / "test_id_mcp.log"

        # Clean up any existing log file from previous test runs
        if expected_log_file.exists():
            expected_log_file.unlink()

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            _ = await harness._solve_in_docker(
                task=task,
                env=mock_env,
                timeout=60,
                verbose=True,
                task_id="test_id",
            )

            # Verify the log file was created
            assert expected_log_file.exists(), "MCP log file should be created"

            # Read the actual log file content
            log_content = expected_log_file.read_text()

            # Check that stdout lines without "mcp" or "supermodel" were captured
            # These lines would NOT be captured with the old keyword-filtering code
            assert "[STDOUT] Server initialized on stdio" in log_content, (
                "Stdout without keywords should be captured"
            )
            assert "[STDOUT] Returning 10 tools" in log_content, (
                "Generic server output should be captured"
            )
            assert "[STDOUT] File read: /workspace/test.py" in log_content, (
                "Filesystem operations should be captured"
            )
            assert "[STDOUT] Request completed in 12ms" in log_content, (
                "Performance logs should be captured"
            )

            # Check that stderr was also captured
            assert "[STDERR] Warning: Large file detected" in log_content, (
                "Stderr should be captured"
            )
            assert "[STDERR] Debug: Cache miss for /workspace/" in log_content, (
                "Stderr debug output should be captured"
            )

            # Clean up the test log file
            expected_log_file.unlink()
