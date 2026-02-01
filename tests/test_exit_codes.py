"""Tests for CLI exit codes.

These tests verify the basic exit code behavior for error scenarios.
Full integration tests for exit codes 0, 2, and 3 require complex mocking
that's better suited for end-to-end tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from mcpbr.cli import main


class TestExitCodes:
    """Tests for exit codes returned by the run command."""

    def test_exit_code_1_invalid_config(self) -> None:
        """Test exit code 1 for invalid configuration."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("invalid: yaml: content: [")

            result = runner.invoke(main, ["run", "-c", str(config_path)])

            assert result.exit_code == 1
            assert "Error loading config" in result.output

    def test_exit_code_1_conflicting_flags(self) -> None:
        """Test exit code 1 when both --mcp-only and --baseline-only are specified."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                """
provider: anthropic
model: claude-sonnet-4-5-20250514
mcp_server:
  command: npx
  args:
    - "@modelcontextprotocol/server-filesystem"
    - /tmp
"""
            )

            result = runner.invoke(main, ["run", "-c", str(config_path), "-M", "-B"])

            assert result.exit_code == 1
            assert "Cannot specify both --mcp-only and --baseline-only" in result.output

    def test_exit_code_130_keyboard_interrupt(self) -> None:
        """Test exit code 130 when evaluation is interrupted by user."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                """
provider: anthropic
model: claude-sonnet-4-5-20250514
mcp_server:
  command: npx
  args:
    - "@modelcontextprotocol/server-filesystem"
    - /tmp
"""
            )

            async def mock_run_evaluation(*args, **kwargs):
                raise KeyboardInterrupt()

            with patch("mcpbr.cli.run_evaluation", side_effect=mock_run_evaluation):
                result = runner.invoke(
                    main, ["run", "-c", str(config_path), "--skip-health-check", "--skip-preflight"]
                )

                assert result.exit_code == 130
                assert "interrupted by user" in result.output
