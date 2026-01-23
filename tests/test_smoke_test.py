"""Tests for smoke test functionality."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mcpbr.smoke_test import SmokeTestResult, SmokeTestRunner


class TestSmokeTestResult:
    """Test SmokeTestResult dataclass."""

    def test_create_passed_result(self):
        """Test creating a passed test result."""
        result = SmokeTestResult(
            name="Test Check", passed=True, message="Check passed", details="Additional info"
        )

        assert result.name == "Test Check"
        assert result.passed is True
        assert result.message == "Check passed"
        assert result.details == "Additional info"
        assert result.error is None

    def test_create_failed_result(self):
        """Test creating a failed test result."""
        result = SmokeTestResult(
            name="Test Check",
            passed=False,
            message="Check failed",
            error="Error details",
        )

        assert result.passed is False
        assert result.error == "Error details"


class TestSmokeTestRunner:
    """Test SmokeTestRunner class."""

    @pytest.fixture
    def temp_config(self, tmp_path: Path) -> Path:
        """Create a temporary config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
  env: {}

provider: anthropic
agent_harness: claude-code
model: sonnet
benchmark: swe-bench
dataset: SWE-bench/SWE-bench_Lite
sample_size: 1
timeout_seconds: 300
max_concurrent: 1
max_iterations: 10
"""
        )
        return config_path

    @pytest.fixture
    def invalid_config(self, tmp_path: Path) -> Path:
        """Create an invalid config file."""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text(
            """
# Missing required mcp_server section
provider: anthropic
"""
        )
        return config_path

    async def test_config_validation_success(self, temp_config: Path):
        """Test successful configuration validation."""
        runner = SmokeTestRunner(temp_config)
        await runner._test_config_validation()

        assert len(runner.results) == 1
        assert runner.results[0].passed is True
        assert runner.results[0].name == "Configuration Validation"

    async def test_config_validation_failure(self, invalid_config: Path):
        """Test configuration validation with errors."""
        runner = SmokeTestRunner(invalid_config)
        await runner._test_config_validation()

        assert len(runner.results) == 1
        assert runner.results[0].passed is False
        assert runner.results[0].name == "Configuration Validation"
        assert runner.results[0].error is not None

    async def test_config_validation_file_not_found(self, tmp_path: Path):
        """Test configuration validation with missing file."""
        nonexistent = tmp_path / "nonexistent.yaml"
        runner = SmokeTestRunner(nonexistent)
        await runner._test_config_validation()

        assert len(runner.results) == 1
        assert runner.results[0].passed is False

    @patch("docker.from_env")
    async def test_docker_availability_success(self, mock_docker, temp_config: Path):
        """Test successful Docker connectivity check."""
        # Mock Docker client
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"Containers": 5, "Images": 10}
        mock_docker.return_value = mock_client

        runner = SmokeTestRunner(temp_config)
        await runner._test_docker_availability()

        assert len(runner.results) == 1
        assert runner.results[0].passed is True
        assert runner.results[0].name == "Docker Availability"
        assert "Containers: 5" in runner.results[0].details
        assert "Images: 10" in runner.results[0].details

    @patch("docker.from_env")
    async def test_docker_availability_failure(self, mock_docker, temp_config: Path):
        """Test Docker connectivity check when Docker is not available."""
        from docker.errors import DockerException

        mock_docker.side_effect = DockerException("Cannot connect to Docker daemon")

        runner = SmokeTestRunner(temp_config)
        await runner._test_docker_availability()

        assert len(runner.results) == 1
        assert runner.results[0].passed is False
        assert runner.results[0].name == "Docker Availability"
        assert runner.results[0].error is not None

    @patch("mcpbr.smoke_test.Anthropic")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-12345"})
    async def test_anthropic_api_success(self, mock_anthropic_class, temp_config: Path):
        """Test successful Anthropic API connectivity check."""
        # Mock Anthropic client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.id = "msg_test123"

        # Make client.messages.create return the mock response
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        runner = SmokeTestRunner(temp_config)
        await runner._test_anthropic_api()

        assert len(runner.results) == 1
        assert runner.results[0].passed is True
        assert runner.results[0].name == "Anthropic API"
        assert "msg_test123" in runner.results[0].details

    async def test_anthropic_api_no_key(self, temp_config: Path):
        """Test Anthropic API check when API key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            runner = SmokeTestRunner(temp_config)
            await runner._test_anthropic_api()

            assert len(runner.results) == 1
            assert runner.results[0].passed is False
            assert runner.results[0].name == "Anthropic API"
            assert "not set" in runner.results[0].message

    @patch("mcpbr.smoke_test.Anthropic")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-12345"})
    async def test_anthropic_api_authentication_error(
        self, mock_anthropic_class, temp_config: Path
    ):
        """Test Anthropic API check with authentication error."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("authentication_error: Invalid API key")
        mock_anthropic_class.return_value = mock_client

        runner = SmokeTestRunner(temp_config)
        await runner._test_anthropic_api()

        assert len(runner.results) == 1
        assert runner.results[0].passed is False
        assert "Check that ANTHROPIC_API_KEY is valid" in runner.results[0].details

    @patch("mcpbr.smoke_test.Anthropic")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-12345"})
    async def test_anthropic_api_rate_limit(self, mock_anthropic_class, temp_config: Path):
        """Test Anthropic API check with rate limit (should still pass)."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("rate limit exceeded")
        mock_anthropic_class.return_value = mock_client

        runner = SmokeTestRunner(temp_config)
        await runner._test_anthropic_api()

        assert len(runner.results) == 1
        assert runner.results[0].passed is True  # Rate limit means API is working
        assert "rate limited" in runner.results[0].message.lower()

    async def test_mcp_server_config_success(self, temp_config: Path):
        """Test successful MCP server configuration check."""
        runner = SmokeTestRunner(temp_config)
        await runner._test_mcp_server_config()

        assert len(runner.results) == 1
        assert runner.results[0].passed is True
        assert runner.results[0].name == "MCP Server Health Check"
        assert (
            "npx" in runner.results[0].details or "executable" in runner.results[0].details.lower()
        )

    async def test_mcp_server_config_failure(self, tmp_path: Path):
        """Test MCP server configuration check with missing config."""
        config_path = tmp_path / "bad_config.yaml"
        config_path.write_text(
            """
provider: anthropic
# Missing mcp_server section
"""
        )

        runner = SmokeTestRunner(config_path)
        await runner._test_mcp_server_config()

        assert len(runner.results) == 1
        assert runner.results[0].passed is False

    @patch("docker.from_env")
    @patch("mcpbr.smoke_test.Anthropic")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-12345"})
    async def test_run_all_tests(self, mock_anthropic_class, mock_docker, temp_config: Path):
        """Test running all smoke tests together."""
        # Mock Docker
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {"Containers": 0, "Images": 0}
        mock_docker.return_value = mock_client

        # Mock Anthropic
        mock_api_client = Mock()
        mock_response = Mock()
        mock_response.id = "msg_test"
        mock_api_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_api_client

        runner = SmokeTestRunner(temp_config)
        results = await runner.run_all_tests()

        # Should have 4 test results
        assert len(results) == 4

        # All tests should pass
        assert all(r.passed for r in results)

        # Check test names
        test_names = [r.name for r in results]
        assert "Configuration Validation" in test_names
        assert "Docker Availability" in test_names
        assert "Anthropic API" in test_names
        assert "MCP Server Health Check" in test_names

    def test_get_summary_all_passed(self, temp_config: Path):
        """Test summary when all tests pass."""
        runner = SmokeTestRunner(temp_config)
        runner.results = [
            SmokeTestResult(name="Test 1", passed=True, message="OK"),
            SmokeTestResult(name="Test 2", passed=True, message="OK"),
            SmokeTestResult(name="Test 3", passed=True, message="OK"),
        ]

        summary = runner.get_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 3
        assert summary["failed"] == 0
        assert summary["success_rate"] == 1.0
        assert summary["all_passed"] is True

    def test_get_summary_some_failed(self, temp_config: Path):
        """Test summary when some tests fail."""
        runner = SmokeTestRunner(temp_config)
        runner.results = [
            SmokeTestResult(name="Test 1", passed=True, message="OK"),
            SmokeTestResult(name="Test 2", passed=False, message="Failed", error="Error"),
            SmokeTestResult(name="Test 3", passed=True, message="OK"),
        ]

        summary = runner.get_summary()

        assert summary["total"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["success_rate"] == pytest.approx(0.666, rel=0.01)
        assert summary["all_passed"] is False

    def test_get_summary_empty(self, temp_config: Path):
        """Test summary with no results."""
        runner = SmokeTestRunner(temp_config)
        runner.results = []

        summary = runner.get_summary()

        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["success_rate"] == 0
        assert summary["all_passed"] is False
