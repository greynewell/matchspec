"""Tests for trial mode functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mcpbr.cli import main


class TestTrialMode:
    """Tests for --trial-mode flag."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config_path(self, tmp_path: Path) -> Path:
        """Create a temporary config file."""
        config_path = tmp_path / "config.yaml"
        config_content = """
model: claude-sonnet-4-5-20250514
provider: anthropic
agent_harness: claude-code
benchmark: swe-bench-verified
sample_size: 1
timeout_seconds: 60
max_concurrent: 1

mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "/tmp"
"""
        config_path.write_text(config_content)
        return config_path

    def test_trial_mode_sets_no_incremental(self, runner, mock_config_path):
        """Test that --trial-mode automatically sets no_incremental."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation to capture the state_tracker parameter
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # Check that trial mode message was printed
            assert "Trial mode enabled:" in result.output
            assert "State caching disabled" in result.output
            assert "Isolated state dir:" in result.output
            assert "Fresh evaluation guaranteed" in result.output

    def test_trial_mode_creates_unique_state_dir(self, runner, mock_config_path):
        """Test that --trial-mode creates unique state directory."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # Check that state directory starts with .mcpbr_trial_
            assert ".mcpbr_trial_" in result.output

    def test_trial_mode_with_other_flags(self, runner, mock_config_path):
        """Test that --trial-mode works with other CLI flags."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                    "-M",  # MCP only
                    "-n",
                    "5",  # Sample size
                ],
                catch_exceptions=False,
            )

            # Should succeed without errors
            assert result.exit_code == 0
            assert "Trial mode enabled:" in result.output

    def test_trial_mode_overrides_no_incremental(self, runner, mock_config_path):
        """Test that --trial-mode takes precedence even if --no-incremental is not specified."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
            patch("mcpbr.cli.StateTracker") as mock_state_tracker,
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            # Mock StateTracker to verify it's not called in trial mode
            mock_tracker = MagicMock()
            mock_state_tracker.return_value = mock_tracker

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # StateTracker should not be instantiated when trial mode is enabled
            # because no_incremental is set to True
            assert result.exit_code == 0
            assert "Trial mode enabled:" in result.output

    def test_trial_mode_state_dir_format(self, runner, mock_config_path):
        """Test that trial mode state directory has correct timestamp format."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # Verify the format matches .mcpbr_trial_YYYYMMDD_HHMMSS_microseconds
            import re

            pattern = r"\.mcpbr_trial_\d{8}_\d{6}_\d{6}"
            assert re.search(pattern, result.output), (
                f"Expected trial state dir pattern in output: {result.output}"
            )

    def test_multiple_trial_runs_create_different_dirs(self, runner, mock_config_path):
        """Test that multiple trial mode runs create different state directories."""
        import time

        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.cli.print_summary"),
        ):
            # Mock the config
            mock_config = MagicMock()
            mock_config.model = "claude-sonnet-4-5-20250514"
            mock_config.provider = "anthropic"
            mock_config.agent_harness = "claude-code"
            mock_config.benchmark = "swe-bench-verified"
            mock_config.sample_size = 1
            mock_config.disable_logs = False
            mock_config.output_dir = None
            mock_config.use_prebuilt_images = True
            mock_config.budget = None
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.summary = {
                "mcp": {"total": 0, "resolved": 0},
                "baseline": {"total": 0, "resolved": 0},
            }
            mock_run.return_value = mock_results

            # Run first trial
            result1 = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # Small delay to ensure different timestamp
            time.sleep(0.01)

            # Run second trial
            result2 = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(mock_config_path),
                    "--trial-mode",
                    "--skip-health-check",
                    "--skip-preflight",
                ],
                catch_exceptions=False,
            )

            # Both should succeed
            assert result1.exit_code == 0
            assert result2.exit_code == 0

            # Both should have trial mode output
            assert "Trial mode enabled:" in result1.output
            assert "Trial mode enabled:" in result2.output

            # Extract state dir from outputs (they should be different)
            import re

            pattern = r"\.mcpbr_trial_\d{8}_\d{6}_\d{6}"
            match1 = re.search(pattern, result1.output)
            match2 = re.search(pattern, result2.output)

            assert match1 is not None
            assert match2 is not None
            assert match1.group() != match2.group(), (
                "Trial runs should create different state directories"
            )
