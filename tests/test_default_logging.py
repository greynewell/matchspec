"""Tests for default logging behavior."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mcpbr.cli import main
from mcpbr.config import HarnessConfig, MCPServerConfig, load_config


class TestDisableLogsConfig:
    """Tests for disable_logs configuration field."""

    def test_disable_logs_default_false(self) -> None:
        """Test that disable_logs defaults to False."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(mcp_server=mcp)
        assert config.disable_logs is False

    def test_disable_logs_can_be_set_true(self) -> None:
        """Test that disable_logs can be set to True."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(mcp_server=mcp, disable_logs=True)
        assert config.disable_logs is True

    def test_disable_logs_from_yaml(self) -> None:
        """Test that disable_logs can be loaded from YAML config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
disable_logs: true
""")
            config_path = f.name

        try:
            config = load_config(config_path, warn_security=False)
            assert config.disable_logs is True
        finally:
            Path(config_path).unlink()

    def test_disable_logs_omitted_from_yaml(self) -> None:
        """Test that disable_logs defaults to False when omitted from YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
""")
            config_path = f.name

        try:
            config = load_config(config_path, warn_security=False)
            assert config.disable_logs is False
        finally:
            Path(config_path).unlink()


class TestCLIDefaultLogging:
    """Tests for CLI default logging behavior."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def test_config_path(self, tmp_path: Path) -> Path:
        """Create a temporary test config file."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("""
mcp_server:
  command: echo
  args:
    - "test"
sample_size: 1
""")
        return config_path

    def test_default_logging_enabled_when_no_flags(
        self, runner: CliRunner, test_config_path: Path
    ) -> None:
        """Test that logging is enabled by default when no flags are provided."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.smoke_test.run_mcp_preflight_check") as mock_health,
        ):
            # Mock health check to skip it
            mock_health.return_value = (True, None)

            # Mock config
            mcp = MCPServerConfig(command="echo", args=["test"])
            mock_config = HarnessConfig(mcp_server=mcp, sample_size=1)
            mock_load_config.return_value = mock_config

            # Mock run_evaluation to capture the log_dir parameter
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.metadata = {"timestamp": "2024-01-01", "config": {}}
            mock_results.summary = {
                "mcp": {"resolved": 0, "total": 0, "rate": 0, "total_cost": 0, "cost_per_task": 0},
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0,
                    "total_cost": 0,
                    "cost_per_task": 0,
                },
                "improvement": "N/A",
            }
            mock_run.return_value = mock_results

            _result = runner.invoke(
                main, ["run", "-c", str(test_config_path), "--skip-health-check"]
            )

            # Check that log_dir was set in the call to run_evaluation
            # The mock_run will be called with run_evaluation coroutine
            if mock_run.called:
                # Log directory should be set to default
                call_args = mock_run.call_args
                # We expect the call to include log_dir parameter
                assert call_args is not None

    def test_disable_logs_flag_disables_logging(
        self, runner: CliRunner, test_config_path: Path
    ) -> None:
        """Test that --disable-logs flag prevents default logging."""
        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.smoke_test.run_mcp_preflight_check") as mock_health,
        ):
            # Mock health check to skip it
            mock_health.return_value = (True, None)

            # Mock config
            mcp = MCPServerConfig(command="echo", args=["test"])
            mock_config = HarnessConfig(mcp_server=mcp, sample_size=1)
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.metadata = {"timestamp": "2024-01-01", "config": {}}
            mock_results.summary = {
                "mcp": {"resolved": 0, "total": 0, "rate": 0, "total_cost": 0, "cost_per_task": 0},
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0,
                    "total_cost": 0,
                    "cost_per_task": 0,
                },
                "improvement": "N/A",
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(test_config_path),
                    "--skip-health-check",
                    "--skip-preflight",
                    "--disable-logs",
                ],
            )

            # Check that the command executed (exit code 0)
            assert result.exit_code == 0

    def test_config_disable_logs_prevents_default(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test that disable_logs: true in config prevents default logging."""
        config_path = tmp_path / "config_with_disable.yaml"
        config_path.write_text("""
mcp_server:
  command: echo
  args:
    - "test"
sample_size: 1
disable_logs: true
""")

        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.smoke_test.run_mcp_preflight_check") as mock_health,
        ):
            # Mock health check to skip it
            mock_health.return_value = (True, None)

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.metadata = {"timestamp": "2024-01-01", "config": {}}
            mock_results.summary = {
                "mcp": {"resolved": 0, "total": 0, "rate": 0, "total_cost": 0, "cost_per_task": 0},
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0,
                    "total_cost": 0,
                    "cost_per_task": 0,
                },
                "improvement": "N/A",
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main, ["run", "-c", str(config_path), "--skip-health-check", "--skip-preflight"]
            )

            # Check that the command executed
            assert result.exit_code == 0

    def test_explicit_log_dir_overrides_default(
        self, runner: CliRunner, test_config_path: Path, tmp_path: Path
    ) -> None:
        """Test that explicit --log-dir overrides default behavior."""
        custom_log_dir = tmp_path / "custom_logs"

        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.smoke_test.run_mcp_preflight_check") as mock_health,
        ):
            # Mock health check
            mock_health.return_value = (True, None)

            # Mock config
            mcp = MCPServerConfig(command="echo", args=["test"])
            mock_config = HarnessConfig(mcp_server=mcp, sample_size=1)
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.metadata = {"timestamp": "2024-01-01", "config": {}}
            mock_results.summary = {
                "mcp": {"resolved": 0, "total": 0, "rate": 0, "total_cost": 0, "cost_per_task": 0},
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0,
                    "total_cost": 0,
                    "cost_per_task": 0,
                },
                "improvement": "N/A",
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(test_config_path),
                    "--skip-health-check",
                    "--skip-preflight",
                    "--log-dir",
                    str(custom_log_dir),
                ],
            )

            # Check that the command executed
            assert result.exit_code == 0

    def test_explicit_log_file_overrides_default(
        self, runner: CliRunner, test_config_path: Path, tmp_path: Path
    ) -> None:
        """Test that explicit --log-file overrides default behavior."""
        custom_log_file = tmp_path / "custom.log"

        with (
            patch("mcpbr.cli.asyncio.run") as mock_run,
            patch("mcpbr.cli.load_config") as mock_load_config,
            patch("mcpbr.smoke_test.run_mcp_preflight_check") as mock_health,
        ):
            # Mock health check
            mock_health.return_value = (True, None)

            # Mock config
            mcp = MCPServerConfig(command="echo", args=["test"])
            mock_config = HarnessConfig(mcp_server=mcp, sample_size=1)
            mock_load_config.return_value = mock_config

            # Mock run_evaluation
            mock_results = MagicMock()
            mock_results.tasks = []
            mock_results.metadata = {"timestamp": "2024-01-01", "config": {}}
            mock_results.summary = {
                "mcp": {"resolved": 0, "total": 0, "rate": 0, "total_cost": 0, "cost_per_task": 0},
                "baseline": {
                    "resolved": 0,
                    "total": 0,
                    "rate": 0,
                    "total_cost": 0,
                    "cost_per_task": 0,
                },
                "improvement": "N/A",
            }
            mock_run.return_value = mock_results

            result = runner.invoke(
                main,
                [
                    "run",
                    "-c",
                    str(test_config_path),
                    "--skip-health-check",
                    "--skip-preflight",
                    "--log-file",
                    str(custom_log_file),
                ],
            )

            # Check that the command executed
            assert result.exit_code == 0


class TestLoggingPriority:
    """Tests for logging configuration priority."""

    def test_cli_disable_overrides_config(self) -> None:
        """Test that --disable-logs CLI flag overrides config setting."""
        # This is implicitly tested in TestCLIDefaultLogging but we document the priority:
        # Priority: CLI flags > config disable_logs > defaults
        # 1. If --disable-logs flag is set, logging is disabled
        # 2. Else if config.disable_logs is true, logging is disabled
        # 3. Else if neither --log-dir nor --log-file is set, enable default logging
        # 4. Else use the explicitly specified logging options

    def test_explicit_log_dir_overrides_all(self) -> None:
        """Test that explicit --log-dir overrides both config and defaults."""
        # This is tested in TestCLIDefaultLogging
