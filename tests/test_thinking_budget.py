"""Tests for thinking_budget configuration and extended thinking mode."""

from unittest.mock import patch

import pytest

from mcpbr.config import HarnessConfig
from mcpbr.harness import _create_baseline_agent, _create_mcp_agent
from mcpbr.harnesses import ClaudeCodeHarness, create_harness


class TestThinkingBudgetConfig:
    """Tests for thinking_budget in configuration."""

    def test_thinking_budget_default_none(self):
        """Test that thinking_budget defaults to None."""
        from mcpbr.config import MCPServerConfig

        config = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            mcp_server=MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            ),
        )
        assert config.thinking_budget is None

    def test_thinking_budget_can_be_set(self):
        """Test that thinking_budget can be configured."""
        from mcpbr.config import MCPServerConfig

        config = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=10000,
            mcp_server=MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            ),
        )
        assert config.thinking_budget == 10000

    def test_thinking_budget_various_values(self):
        """Test thinking_budget with various valid values."""
        from mcpbr.config import MCPServerConfig

        mcp_server = MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )

        # Minimum valid value (Anthropic docs: 1024 minimum)
        config1 = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=1024,
            mcp_server=mcp_server,
        )
        assert config1.thinking_budget == 1024

        # Claude Code default (31999)
        config2 = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=31999,
            mcp_server=mcp_server,
        )
        assert config2.thinking_budget == 31999

        # Custom value
        config3 = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=5000,
            mcp_server=mcp_server,
        )
        assert config3.thinking_budget == 5000

    def test_thinking_budget_validation_minimum(self):
        """Test that thinking_budget rejects values below 1024."""
        from mcpbr.config import MCPServerConfig

        mcp_server = MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )

        # Test below minimum
        with pytest.raises(ValueError, match="must be at least 1024 tokens"):
            HarnessConfig(
                benchmark="humaneval",
                provider="anthropic",
                agent_harness="claude-code",
                model="sonnet",
                thinking_budget=1023,  # Below minimum
                mcp_server=mcp_server,
            )

        # Test zero
        with pytest.raises(ValueError, match="must be at least 1024 tokens"):
            HarnessConfig(
                benchmark="humaneval",
                provider="anthropic",
                agent_harness="claude-code",
                model="sonnet",
                thinking_budget=0,
                mcp_server=mcp_server,
            )

        # Test negative
        with pytest.raises(ValueError, match="must be at least 1024 tokens"):
            HarnessConfig(
                benchmark="humaneval",
                provider="anthropic",
                agent_harness="claude-code",
                model="sonnet",
                thinking_budget=-1000,
                mcp_server=mcp_server,
            )

    def test_thinking_budget_validation_maximum(self):
        """Test that thinking_budget rejects values above 31999."""
        from mcpbr.config import MCPServerConfig

        mcp_server = MCPServerConfig(
            name="filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        )

        # Test above maximum
        with pytest.raises(ValueError, match="cannot exceed 31999 tokens"):
            HarnessConfig(
                benchmark="humaneval",
                provider="anthropic",
                agent_harness="claude-code",
                model="sonnet",
                thinking_budget=32000,  # Above maximum
                mcp_server=mcp_server,
            )

        # Test way above maximum
        with pytest.raises(ValueError, match="cannot exceed 31999 tokens"):
            HarnessConfig(
                benchmark="humaneval",
                provider="anthropic",
                agent_harness="claude-code",
                model="sonnet",
                thinking_budget=100000,
                mcp_server=mcp_server,
            )


class TestThinkingBudgetHarnessCreation:
    """Tests for thinking_budget in harness creation."""

    def test_claude_code_harness_accepts_thinking_budget(self):
        """Test that ClaudeCodeHarness accepts thinking_budget parameter."""
        harness = ClaudeCodeHarness(
            model="sonnet",
            thinking_budget=10000,
        )
        assert harness.thinking_budget == 10000

    def test_claude_code_harness_thinking_budget_none_by_default(self):
        """Test that ClaudeCodeHarness thinking_budget is None by default."""
        harness = ClaudeCodeHarness(model="sonnet")
        assert harness.thinking_budget is None

    def test_create_harness_passes_thinking_budget(self):
        """Test that create_harness factory function passes thinking_budget."""
        harness = create_harness(
            "claude-code",
            model="sonnet",
            thinking_budget=10000,
        )
        assert isinstance(harness, ClaudeCodeHarness)
        assert harness.thinking_budget == 10000

    def test_create_harness_thinking_budget_none(self):
        """Test create_harness with no thinking_budget."""
        harness = create_harness(
            "claude-code",
            model="sonnet",
        )
        assert isinstance(harness, ClaudeCodeHarness)
        assert harness.thinking_budget is None

    @patch("mcpbr.harness.create_harness")
    def test_create_mcp_agent_passes_thinking_budget(self, mock_create_harness):
        """Test that _create_mcp_agent passes thinking_budget to harness."""
        from mcpbr.benchmarks import create_benchmark
        from mcpbr.config import MCPServerConfig

        config = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=10000,
            mcp_server=MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            ),
        )
        benchmark = create_benchmark("humaneval")

        _create_mcp_agent(config, benchmark, verbosity=1)

        mock_create_harness.assert_called_once()
        call_kwargs = mock_create_harness.call_args[1]
        assert call_kwargs["thinking_budget"] == 10000

    @patch("mcpbr.harness.create_harness")
    def test_create_baseline_agent_passes_thinking_budget(self, mock_create_harness):
        """Test that _create_baseline_agent passes thinking_budget to harness."""
        from mcpbr.benchmarks import create_benchmark
        from mcpbr.config import MCPServerConfig

        config = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=10000,
            mcp_server=MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            ),
        )
        benchmark = create_benchmark("humaneval")

        _create_baseline_agent(config, benchmark, verbosity=1)

        mock_create_harness.assert_called_once()
        call_kwargs = mock_create_harness.call_args[1]
        assert call_kwargs["thinking_budget"] == 10000


class TestThinkingBudgetEnvironmentVariable:
    """Tests for MAX_THINKING_TOKENS environment variable injection."""

    @pytest.mark.asyncio
    async def test_local_mode_sets_max_thinking_tokens(self):
        """Test that thinking_budget sets MAX_THINKING_TOKENS in local mode."""
        harness = ClaudeCodeHarness(
            model="sonnet",
            thinking_budget=10000,
        )

        task = {
            "instance_id": "test_task",
            "problem_statement": "Test problem",
        }

        # Mock _run_cli_command to capture environment
        captured_env = None

        async def mock_run_cli(cmd, workdir, timeout, env=None, input_text=None):
            nonlocal captured_env
            captured_env = env
            # Return timeout to exit quickly
            return 124, "", "timeout"

        with patch("mcpbr.harnesses._run_cli_command", side_effect=mock_run_cli):
            with patch("mcpbr.harnesses.shutil.which", return_value="/usr/bin/claude"):
                try:
                    await harness.solve(task, "/tmp/test", timeout=1)
                except Exception:
                    pass

        # Verify MAX_THINKING_TOKENS was set in environment
        assert captured_env is not None
        assert "MAX_THINKING_TOKENS" in captured_env
        assert captured_env["MAX_THINKING_TOKENS"] == "10000"

    @pytest.mark.asyncio
    async def test_local_mode_no_env_when_thinking_budget_none(self):
        """Test that no env dict is passed when thinking_budget is None."""
        harness = ClaudeCodeHarness(
            model="sonnet",
            thinking_budget=None,
        )

        task = {
            "instance_id": "test_task",
            "problem_statement": "Test problem",
        }

        # Mock _run_cli_command to capture environment
        captured_env = "not_called"

        async def mock_run_cli(cmd, workdir, timeout, env=None, input_text=None):
            nonlocal captured_env
            captured_env = env
            return 124, "", "timeout"

        with patch("mcpbr.harnesses._run_cli_command", side_effect=mock_run_cli):
            with patch("mcpbr.harnesses.shutil.which", return_value="/usr/bin/claude"):
                try:
                    await harness.solve(task, "/tmp/test", timeout=1)
                except Exception:
                    pass

        # Verify no env dict was passed (should be None)
        assert captured_env is None

    def test_thinking_budget_stored_in_harness(self):
        """Test that thinking_budget is stored in the harness instance."""
        harness1 = ClaudeCodeHarness(model="sonnet", thinking_budget=10000)
        assert harness1.thinking_budget == 10000

        harness2 = ClaudeCodeHarness(model="sonnet", thinking_budget=None)
        assert harness2.thinking_budget is None

        harness3 = ClaudeCodeHarness(model="sonnet")
        assert harness3.thinking_budget is None


class TestThinkingBudgetIntegration:
    """Integration tests for thinking_budget feature."""

    def test_yaml_config_with_thinking_budget(self, tmp_path):
        """Test that thinking_budget can be loaded from YAML config."""
        import yaml

        config_dict = {
            "benchmark": "humaneval",
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": "sonnet",
            "thinking_budget": 10000,
            "mcp_server": {
                "name": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            },
        }

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_dict))

        # Load and parse config
        with open(config_file) as f:
            loaded_dict = yaml.safe_load(f)

        config = HarnessConfig(**loaded_dict)
        assert config.thinking_budget == 10000

    def test_yaml_config_without_thinking_budget(self, tmp_path):
        """Test that config works without thinking_budget (defaults to None)."""
        import yaml

        config_dict = {
            "benchmark": "humaneval",
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": "sonnet",
            "mcp_server": {
                "name": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            },
        }

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_dict))

        # Load and parse config
        with open(config_file) as f:
            loaded_dict = yaml.safe_load(f)

        config = HarnessConfig(**loaded_dict)
        assert config.thinking_budget is None

    def test_thinking_budget_end_to_end_flow(self):
        """Test that thinking_budget flows through the entire stack."""
        from mcpbr.config import MCPServerConfig

        # Create config with thinking_budget
        config = HarnessConfig(
            benchmark="humaneval",
            provider="anthropic",
            agent_harness="claude-code",
            model="sonnet",
            thinking_budget=10000,
            mcp_server=MCPServerConfig(
                name="filesystem",
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            ),
        )

        # Create harness through factory
        from mcpbr.benchmarks import create_benchmark

        benchmark = create_benchmark("humaneval")

        # Create MCP agent
        with patch("mcpbr.harness.create_harness", wraps=create_harness) as mock_create:
            agent = _create_mcp_agent(config, benchmark)

            # Verify create_harness was called with thinking_budget
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["thinking_budget"] == 10000

            # Verify the created harness has thinking_budget set
            assert isinstance(agent, ClaudeCodeHarness)
            assert agent.thinking_budget == 10000
