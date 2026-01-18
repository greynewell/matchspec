"""Tests for configuration loading and validation."""

import tempfile

import pytest

from mcpbr.config import (
    HarnessConfig,
    MCPServerConfig,
    create_default_config,
    load_config,
)
from mcpbr.models import DEFAULT_MODEL


class TestMCPServerConfig:
    """Tests for MCPServerConfig."""

    def test_basic_creation(self) -> None:
        """Test basic config creation."""
        config = MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        )
        assert config.command == "npx"
        assert len(config.args) == 3

    def test_workdir_substitution(self) -> None:
        """Test {workdir} placeholder substitution."""
        config = MCPServerConfig(
            command="python",
            args=["-m", "myserver", "--path", "{workdir}"],
        )
        result = config.get_args_for_workdir("/tmp/test")
        assert result == ["-m", "myserver", "--path", "/tmp/test"]

    def test_empty_env_default(self) -> None:
        """Test that env defaults to empty dict."""
        config = MCPServerConfig(command="echo", args=[])
        assert config.env == {}


class TestHarnessConfig:
    """Tests for HarnessConfig."""

    def test_defaults(self) -> None:
        """Test default values."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(mcp_server=mcp)

        assert config.model == DEFAULT_MODEL
        assert config.provider == "anthropic"
        assert config.agent_harness == "claude-code"
        assert config.benchmark == "swe-bench"
        assert config.agent_prompt is None
        assert config.dataset is None
        assert config.cybergym_level == 1
        assert config.sample_size is None
        assert config.timeout_seconds == 300
        assert config.max_concurrent == 4
        assert config.max_iterations == 10

    def test_agent_prompt_field(self) -> None:
        """Test that agent_prompt can be set."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(
            mcp_server=mcp,
            agent_prompt="Fix this: {problem_statement}",
        )
        assert config.agent_prompt == "Fix this: {problem_statement}"

    def test_max_concurrent_validation(self) -> None:
        """Test that max_concurrent must be at least 1."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="max_concurrent must be at least 1"):
            HarnessConfig(mcp_server=mcp, max_concurrent=0)

    def test_timeout_validation(self) -> None:
        """Test that timeout must be at least 30."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="timeout_seconds must be at least 30"):
            HarnessConfig(mcp_server=mcp, timeout_seconds=10)

    def test_provider_validation(self) -> None:
        """Test that provider must be valid."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="Invalid provider"):
            HarnessConfig(mcp_server=mcp, provider="invalid")

    def test_harness_validation(self) -> None:
        """Test that agent_harness must be valid."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="Invalid agent_harness"):
            HarnessConfig(mcp_server=mcp, agent_harness="invalid")

    def test_benchmark_validation(self) -> None:
        """Test that benchmark must be valid."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="Invalid benchmark"):
            HarnessConfig(mcp_server=mcp, benchmark="invalid")

    def test_benchmark_swebench(self) -> None:
        """Test that benchmark can be set to swe-bench."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(mcp_server=mcp, benchmark="swe-bench")
        assert config.benchmark == "swe-bench"

    def test_benchmark_cybergym(self) -> None:
        """Test that benchmark can be set to cybergym."""
        mcp = MCPServerConfig(command="echo", args=[])
        config = HarnessConfig(mcp_server=mcp, benchmark="cybergym")
        assert config.benchmark == "cybergym"

    def test_cybergym_level_validation_min(self) -> None:
        """Test that cybergym_level must be at least 0."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="cybergym_level must be between 0 and 3"):
            HarnessConfig(mcp_server=mcp, cybergym_level=-1)

    def test_cybergym_level_validation_max(self) -> None:
        """Test that cybergym_level must be at most 3."""
        mcp = MCPServerConfig(command="echo", args=[])
        with pytest.raises(ValueError, match="cybergym_level must be between 0 and 3"):
            HarnessConfig(mcp_server=mcp, cybergym_level=4)

    def test_cybergym_level_valid(self) -> None:
        """Test that cybergym_level can be set to valid values."""
        mcp = MCPServerConfig(command="echo", args=[])
        for level in [0, 1, 2, 3]:
            config = HarnessConfig(mcp_server=mcp, cybergym_level=level)
            assert config.cybergym_level == level


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_yaml(self) -> None:
        """Test loading a valid YAML config."""
        yaml_content = f"""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{{workdir}}"

model: {DEFAULT_MODEL}
provider: anthropic
agent_harness: claude-code
sample_size: 10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = load_config(f.name)

            assert config.mcp_server.command == "npx"
            assert config.sample_size == 10
            assert config.model == DEFAULT_MODEL
            assert config.provider == "anthropic"
            assert config.agent_harness == "claude-code"

    def test_load_nonexistent_file(self) -> None:
        """Test that loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_creates_valid_config(self) -> None:
        """Test that default config is valid."""
        config = create_default_config()

        assert config.mcp_server.command == "npx"
        assert "{workdir}" in config.mcp_server.args
        assert config.model == DEFAULT_MODEL
        assert config.provider == "anthropic"
        assert config.agent_harness == "claude-code"
