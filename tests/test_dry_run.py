"""Tests for dry-run mode evaluation preview."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig
from mcpbr.dry_run import (
    DryRunResult,
    _check_docker_available,
    _check_mcp_server_reachable,
    _estimate_cost,
    _estimate_time,
    _validate_config_from_object,
    dry_run,
    format_dry_run_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_config() -> HarnessConfig:
    """Create a basic HarnessConfig for testing."""
    return HarnessConfig(
        provider="anthropic",
        agent_harness="claude-code",
        model="sonnet",
        benchmark="swe-bench-verified",
        sample_size=5,
        timeout_seconds=300,
        max_iterations=10,
        max_concurrent=4,
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
    )


@pytest.fixture
def comparison_config() -> HarnessConfig:
    """Create a comparison mode HarnessConfig for testing."""
    return HarnessConfig(
        provider="anthropic",
        agent_harness="claude-code",
        model="sonnet",
        benchmark="humaneval",
        sample_size=3,
        timeout_seconds=300,
        max_iterations=10,
        max_concurrent=2,
        comparison_mode=True,
        mcp_server_a=MCPServerConfig(
            name="server_a",
            command="npx",
            args=["-y", "server-a", "{workdir}"],
        ),
        mcp_server_b=MCPServerConfig(
            name="server_b",
            command="uvx",
            args=["server-b", "{workdir}"],
        ),
    )


@pytest.fixture
def mock_benchmark_tasks() -> list[dict]:
    """Create mock benchmark tasks."""
    return [
        {
            "instance_id": "task_001",
            "repo": "test/repo",
            "base_commit": "abc123",
            "problem_statement": "Fix the bug in module X",
        },
        {
            "instance_id": "task_002",
            "repo": "test/repo",
            "base_commit": "def456",
            "problem_statement": "Add feature Y to component Z",
        },
        {
            "instance_id": "task_003",
            "repo": "test/repo",
            "base_commit": "ghi789",
            "problem_statement": "Refactor class W for clarity",
        },
    ]


# ---------------------------------------------------------------------------
# DryRunResult dataclass tests
# ---------------------------------------------------------------------------


class TestDryRunResult:
    """Tests for the DryRunResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating a DryRunResult with all fields."""
        result = DryRunResult(
            benchmark_name="swe-bench-verified",
            total_tasks=10,
            task_ids=["task_1", "task_2"],
            estimated_cost_usd=5.50,
            estimated_time_minutes=30.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={"mcp_server": True},
            warnings=[],
        )

        assert result.benchmark_name == "swe-bench-verified"
        assert result.total_tasks == 10
        assert result.task_ids == ["task_1", "task_2"]
        assert result.estimated_cost_usd == 5.50
        assert result.estimated_time_minutes == 30.0
        assert result.config_valid is True
        assert result.config_errors == []
        assert result.docker_available is True
        assert result.mcp_servers_reachable == {"mcp_server": True}
        assert result.warnings == []

    def test_create_result_with_errors(self) -> None:
        """Test creating a DryRunResult with errors and warnings."""
        result = DryRunResult(
            benchmark_name="humaneval",
            total_tasks=0,
            task_ids=[],
            estimated_cost_usd=None,
            estimated_time_minutes=None,
            config_valid=False,
            config_errors=["Missing API key", "Invalid benchmark"],
            docker_available=False,
            mcp_servers_reachable={"server": False},
            warnings=["Docker not running"],
        )

        assert result.config_valid is False
        assert len(result.config_errors) == 2
        assert result.docker_available is False
        assert result.estimated_cost_usd is None
        assert len(result.warnings) == 1

    def test_default_warnings_empty(self) -> None:
        """Test that warnings default to empty list."""
        result = DryRunResult(
            benchmark_name="test",
            total_tasks=0,
            task_ids=[],
            estimated_cost_usd=None,
            estimated_time_minutes=None,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={},
        )

        assert result.warnings == []


# ---------------------------------------------------------------------------
# Docker check tests
# ---------------------------------------------------------------------------


class TestCheckDockerAvailable:
    """Tests for _check_docker_available function."""

    def test_docker_available(self) -> None:
        """Test when Docker is running."""
        with patch("mcpbr.dry_run.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_docker.return_value = mock_client

            assert _check_docker_available() is True

    def test_docker_not_available(self) -> None:
        """Test when Docker is not running."""
        with patch("mcpbr.dry_run.docker.from_env") as mock_docker:
            mock_docker.side_effect = Exception("Connection refused")

            assert _check_docker_available() is False

    def test_docker_ping_fails(self) -> None:
        """Test when Docker ping fails."""
        with patch("mcpbr.dry_run.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_client.ping.side_effect = Exception("Ping failed")
            mock_docker.return_value = mock_client

            assert _check_docker_available() is False


# ---------------------------------------------------------------------------
# MCP server reachability tests
# ---------------------------------------------------------------------------


class TestCheckMCPServerReachable:
    """Tests for _check_mcp_server_reachable function."""

    def test_command_found(self) -> None:
        """Test when MCP server command is found in PATH."""
        with patch("mcpbr.dry_run.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/npx"

            assert _check_mcp_server_reachable("npx") is True
            mock_which.assert_called_once_with("npx")

    def test_command_not_found(self) -> None:
        """Test when MCP server command is not found in PATH."""
        with patch("mcpbr.dry_run.shutil.which") as mock_which:
            mock_which.return_value = None

            assert _check_mcp_server_reachable("nonexistent-server") is False

    def test_empty_command(self) -> None:
        """Test with empty command string."""
        with patch("mcpbr.dry_run.shutil.which") as mock_which:
            mock_which.return_value = None

            assert _check_mcp_server_reachable("") is False


# ---------------------------------------------------------------------------
# Config validation tests
# ---------------------------------------------------------------------------


class TestValidateConfigFromObject:
    """Tests for _validate_config_from_object function."""

    def test_valid_config_with_api_key(self, basic_config: HarnessConfig) -> None:
        """Test validation with valid config and API key set."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            result = _validate_config_from_object(basic_config)

            assert result.valid is True
            assert len(result.errors) == 0

    def test_valid_config_without_api_key(self, basic_config: HarnessConfig) -> None:
        """Test validation without API key (should warn, not error)."""
        with patch.dict(os.environ, {}, clear=True):
            result = _validate_config_from_object(basic_config)

            # API key missing is a warning, not an error
            assert result.valid is True
            assert len(result.warnings) > 0
            assert any("ANTHROPIC_API_KEY" in w.error for w in result.warnings)


# ---------------------------------------------------------------------------
# Cost estimation tests
# ---------------------------------------------------------------------------


class TestEstimateCost:
    """Tests for _estimate_cost function."""

    def test_estimate_cost_known_model(self) -> None:
        """Test cost estimation with a known model and benchmark."""
        cost = _estimate_cost("sonnet", "swe-bench-verified", 10)

        assert cost is not None
        assert cost > 0

        # Sonnet: $3/MTok input, $15/MTok output
        # SWE-bench: ~50k input, ~10k output per task
        # Per task: (50000/1M * 3) + (10000/1M * 15) = 0.15 + 0.15 = 0.30
        # 10 tasks: ~$3.00
        assert cost == pytest.approx(3.00, abs=0.5)

    def test_estimate_cost_unknown_model(self) -> None:
        """Test cost estimation with an unknown model."""
        cost = _estimate_cost("unknown-model-xyz", "swe-bench-verified", 10)

        assert cost is None

    def test_estimate_cost_zero_tasks(self) -> None:
        """Test cost estimation with zero tasks."""
        cost = _estimate_cost("sonnet", "humaneval", 0)

        assert cost is not None
        assert cost == 0.0

    def test_estimate_cost_haiku_cheaper(self) -> None:
        """Test that Haiku is cheaper than Sonnet for same benchmark."""
        haiku_cost = _estimate_cost("haiku", "swe-bench-verified", 10)
        sonnet_cost = _estimate_cost("sonnet", "swe-bench-verified", 10)

        assert haiku_cost is not None
        assert sonnet_cost is not None
        assert haiku_cost < sonnet_cost

    def test_estimate_cost_opus_most_expensive(self) -> None:
        """Test that Opus is the most expensive model."""
        haiku_cost = _estimate_cost("haiku", "humaneval", 10)
        sonnet_cost = _estimate_cost("sonnet", "humaneval", 10)
        opus_cost = _estimate_cost("opus", "humaneval", 10)

        assert haiku_cost is not None
        assert sonnet_cost is not None
        assert opus_cost is not None
        assert haiku_cost < sonnet_cost < opus_cost

    def test_estimate_cost_unknown_benchmark_uses_defaults(self) -> None:
        """Test that unknown benchmark names fall back to default estimates."""
        cost = _estimate_cost("sonnet", "some-unknown-benchmark", 5)

        # Should still return a value using default tokens
        assert cost is not None
        assert cost > 0

    def test_estimate_cost_scales_with_tasks(self) -> None:
        """Test that cost scales linearly with task count."""
        cost_5 = _estimate_cost("sonnet", "humaneval", 5)
        cost_10 = _estimate_cost("sonnet", "humaneval", 10)

        assert cost_5 is not None
        assert cost_10 is not None
        assert cost_10 == pytest.approx(cost_5 * 2, abs=0.001)


# ---------------------------------------------------------------------------
# Time estimation tests
# ---------------------------------------------------------------------------


class TestEstimateTime:
    """Tests for _estimate_time function."""

    def test_estimate_time_basic(self) -> None:
        """Test basic time estimation."""
        time_min = _estimate_time("swe-bench-verified", 10, 4, 300)

        assert time_min > 0
        # 10 tasks, 4 concurrent, timeout 300s = 5 min cap (< 8 min default)
        # (10/4) * 5 = 12.5 min
        assert time_min == pytest.approx(12.5, abs=1.0)

    def test_estimate_time_single_concurrent(self) -> None:
        """Test time estimation with single concurrency."""
        time_min = _estimate_time("humaneval", 5, 1, 300)

        # 5 tasks, 1 concurrent, ~2 min each = 10 min
        assert time_min == pytest.approx(10.0, abs=1.0)

    def test_estimate_time_high_concurrency(self) -> None:
        """Test time estimation with high concurrency."""
        time_min = _estimate_time("humaneval", 5, 10, 300)

        # 5 tasks, 10 concurrent (capped at 5), ~2 min each = (5/5)*2 = 2 min
        assert time_min == pytest.approx(2.0, abs=0.5)

    def test_estimate_time_zero_tasks(self) -> None:
        """Test time estimation with zero tasks."""
        time_min = _estimate_time("humaneval", 0, 4, 300)

        assert time_min == 0.0

    def test_estimate_time_capped_by_timeout(self) -> None:
        """Test that per-task time is capped by the configured timeout."""
        # SWE-bench default is 8 min per task, but timeout is 60 seconds = 1 min
        time_min = _estimate_time("swe-bench-verified", 4, 4, 60)

        # 4 tasks, 4 concurrent, capped at 1 min = 1 min
        assert time_min == pytest.approx(1.0, abs=0.1)

    def test_estimate_time_unknown_benchmark(self) -> None:
        """Test time estimation with unknown benchmark uses default."""
        time_min = _estimate_time("unknown-benchmark", 6, 2, 600)

        # 6 tasks, 2 concurrent, default 3 min each = (6/2)*3 = 9 min
        assert time_min == pytest.approx(9.0, abs=0.5)


# ---------------------------------------------------------------------------
# dry_run() async function tests
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for the dry_run async function."""

    @pytest.mark.asyncio
    async def test_dry_run_basic(
        self, basic_config: HarnessConfig, mock_benchmark_tasks: list[dict]
    ) -> None:
        """Test basic dry run with all systems available."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks
        mock_benchmark.name = "swe-bench-verified"

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(basic_config)

        assert result.benchmark_name == "swe-bench-verified"
        assert result.total_tasks == 3
        assert result.task_ids == ["task_001", "task_002", "task_003"]
        assert result.docker_available is True
        assert result.config_valid is True
        assert result.estimated_cost_usd is not None
        assert result.estimated_cost_usd > 0
        assert result.estimated_time_minutes is not None
        assert result.estimated_time_minutes > 0

    @pytest.mark.asyncio
    async def test_dry_run_docker_unavailable(
        self, basic_config: HarnessConfig, mock_benchmark_tasks: list[dict]
    ) -> None:
        """Test dry run when Docker is not available."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=False),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(basic_config)

        assert result.docker_available is False
        assert any("Docker" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_mcp_server_not_found(
        self, basic_config: HarnessConfig, mock_benchmark_tasks: list[dict]
    ) -> None:
        """Test dry run when MCP server command is not found."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=False),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(basic_config)

        assert result.mcp_servers_reachable.get("mcpbr") is False
        assert any("not found in PATH" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_no_api_key(
        self, basic_config: HarnessConfig, mock_benchmark_tasks: list[dict]
    ) -> None:
        """Test dry run when API key is not set."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = await dry_run(basic_config)

        assert any("ANTHROPIC_API_KEY" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_benchmark_load_failure(self, basic_config: HarnessConfig) -> None:
        """Test dry run when benchmark loading fails."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.side_effect = RuntimeError("Dataset not available")

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(basic_config)

        assert result.total_tasks == 5  # Falls back to sample_size
        assert result.task_ids == []
        assert any("Failed to load benchmark tasks" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_comparison_mode(
        self,
        comparison_config: HarnessConfig,
        mock_benchmark_tasks: list[dict],
    ) -> None:
        """Test dry run in comparison mode with two MCP servers."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        def mock_reachable(command: str) -> bool:
            return command == "npx"

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch(
                "mcpbr.dry_run._check_mcp_server_reachable",
                side_effect=mock_reachable,
            ),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(comparison_config)

        # Server A (npx) should be reachable, Server B (uvx) should not
        assert result.mcp_servers_reachable.get("server_a") is True
        assert result.mcp_servers_reachable.get("server_b") is False
        assert any("server_b" in w or "uvx" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_budget_warning(self, mock_benchmark_tasks: list[dict]) -> None:
        """Test dry run warns when estimated cost exceeds budget."""
        config = HarnessConfig(
            provider="anthropic",
            agent_harness="claude-code",
            model="opus",  # Most expensive
            benchmark="swe-bench-verified",
            sample_size=100,
            timeout_seconds=300,
            max_iterations=10,
            max_concurrent=4,
            budget=0.01,  # Very low budget
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "server", "{workdir}"],
            ),
        )

        # Create 100 mock tasks
        many_tasks = [
            {
                "instance_id": f"task_{i:03d}",
                "repo": "test/repo",
                "base_commit": f"commit_{i}",
                "problem_statement": f"Problem {i}",
            }
            for i in range(100)
        ]

        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = many_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(config)

        assert any("exceeds budget" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_unknown_model_cost(self, mock_benchmark_tasks: list[dict]) -> None:
        """Test dry run handles unknown model pricing gracefully."""
        config = HarnessConfig(
            provider="anthropic",
            agent_harness="claude-code",
            model="some-custom-model",
            benchmark="humaneval",
            sample_size=5,
            timeout_seconds=300,
            max_iterations=10,
            max_concurrent=4,
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "server", "{workdir}"],
            ),
        )

        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(config)

        assert result.estimated_cost_usd is None
        assert any("pricing unavailable" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_dry_run_verbosity_adds_cost_warning(
        self, basic_config: HarnessConfig, mock_benchmark_tasks: list[dict]
    ) -> None:
        """Test that verbosity >= 1 adds cost accuracy warning."""
        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_benchmark_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(basic_config, verbosity=1)

        assert any("historical averages" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Report formatting tests
# ---------------------------------------------------------------------------


class TestFormatDryRunReport:
    """Tests for format_dry_run_report function."""

    def test_format_success_report(self) -> None:
        """Test formatting a successful dry-run report."""
        result = DryRunResult(
            benchmark_name="swe-bench-verified",
            total_tasks=10,
            task_ids=[f"task_{i}" for i in range(10)],
            estimated_cost_usd=3.50,
            estimated_time_minutes=25.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={"mcp_server": True},
            warnings=[],
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            # Should not raise any exceptions
            format_dry_run_report(result)

    def test_format_failure_report(self) -> None:
        """Test formatting a report with failures."""
        result = DryRunResult(
            benchmark_name="humaneval",
            total_tasks=5,
            task_ids=["task_1", "task_2", "task_3", "task_4", "task_5"],
            estimated_cost_usd=None,
            estimated_time_minutes=10.0,
            config_valid=False,
            config_errors=["Invalid model", "Missing benchmark field"],
            docker_available=False,
            mcp_servers_reachable={"mcp_server": False},
            warnings=["Docker not running", "API key not set"],
        )

        with patch.dict(os.environ, {}, clear=True):
            # Should not raise any exceptions
            format_dry_run_report(result)

    def test_format_report_with_many_tasks(self) -> None:
        """Test formatting a report with many tasks (truncation)."""
        result = DryRunResult(
            benchmark_name="swe-bench-full",
            total_tasks=500,
            task_ids=[f"task_{i:04d}" for i in range(500)],
            estimated_cost_usd=150.0,
            estimated_time_minutes=600.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={"mcp_server": True},
            warnings=[],
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            # Should not raise; only first 10 task IDs displayed
            format_dry_run_report(result)

    def test_format_report_hours_display(self) -> None:
        """Test that time over 60 minutes displays as hours and minutes."""
        result = DryRunResult(
            benchmark_name="swe-bench-full",
            total_tasks=100,
            task_ids=[],
            estimated_cost_usd=50.0,
            estimated_time_minutes=125.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={},
            warnings=[],
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            # Should display "2h 5m" format - should not raise
            format_dry_run_report(result)

    def test_format_report_empty_task_ids(self) -> None:
        """Test formatting a report with no task IDs."""
        result = DryRunResult(
            benchmark_name="custom",
            total_tasks=0,
            task_ids=[],
            estimated_cost_usd=0.0,
            estimated_time_minutes=0.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={},
            warnings=[],
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            # Should not raise
            format_dry_run_report(result)

    def test_format_report_comparison_mode_servers(self) -> None:
        """Test formatting a report with multiple MCP servers."""
        result = DryRunResult(
            benchmark_name="humaneval",
            total_tasks=5,
            task_ids=["task_1", "task_2", "task_3", "task_4", "task_5"],
            estimated_cost_usd=2.0,
            estimated_time_minutes=10.0,
            config_valid=True,
            config_errors=[],
            docker_available=True,
            mcp_servers_reachable={
                "server_a": True,
                "server_b": False,
            },
            warnings=["Server B command not found"],
        )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}):
            # Should display both servers in infrastructure table
            format_dry_run_report(result)


# ---------------------------------------------------------------------------
# Integration-style tests (with more realistic mocking)
# ---------------------------------------------------------------------------


class TestDryRunIntegration:
    """Integration-style tests that exercise the full dry_run flow."""

    @pytest.mark.asyncio
    async def test_full_dry_run_all_passing(self) -> None:
        """Test a complete dry run where everything passes."""
        config = HarnessConfig(
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            benchmark="humaneval",
            sample_size=3,
            timeout_seconds=120,
            max_iterations=5,
            max_concurrent=2,
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "test-server", "{workdir}"],
            ),
        )

        mock_tasks = [
            {"instance_id": f"HumanEval/{i}", "problem_statement": f"Prob {i}"} for i in range(3)
        ]

        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.return_value = mock_tasks

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=True),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=True),
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test1234567890"}),
        ):
            result = await dry_run(config, verbosity=0)

            # Verify all checks pass
            assert result.config_valid is True
            assert result.docker_available is True
            assert all(result.mcp_servers_reachable.values())
            assert result.total_tasks == 3
            assert result.estimated_cost_usd is not None
            assert result.estimated_time_minutes is not None

            # Format the report (should not raise)
            format_dry_run_report(result)

    @pytest.mark.asyncio
    async def test_full_dry_run_everything_failing(self) -> None:
        """Test a complete dry run where everything fails."""
        config = HarnessConfig(
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            benchmark="humaneval",
            sample_size=3,
            timeout_seconds=120,
            max_iterations=5,
            max_concurrent=2,
            mcp_server=MCPServerConfig(
                command="nonexistent-command",
                args=[],
            ),
        )

        mock_benchmark = MagicMock()
        mock_benchmark.load_tasks.side_effect = RuntimeError("Cannot load tasks")

        with (
            patch("mcpbr.dry_run.create_benchmark", return_value=mock_benchmark),
            patch("mcpbr.dry_run._check_docker_available", return_value=False),
            patch("mcpbr.dry_run._check_mcp_server_reachable", return_value=False),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = await dry_run(config, verbosity=0)

            # Verify failure states
            assert result.docker_available is False
            assert result.total_tasks == 3  # Falls back to sample_size
            assert result.task_ids == []
            assert any("Docker" in w for w in result.warnings)
            assert any("ANTHROPIC_API_KEY" in w for w in result.warnings)
            assert any("not found in PATH" in w for w in result.warnings)
            assert any("Failed to load benchmark tasks" in w for w in result.warnings)

            # Format the report (should not raise even with failures)
            format_dry_run_report(result)
