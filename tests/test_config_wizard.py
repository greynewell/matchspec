"""Tests for the interactive configuration wizard."""

from pathlib import Path
from unittest.mock import patch

import click
import yaml

from mcpbr.config import VALID_BENCHMARKS, load_config
from mcpbr.config_wizard import (
    PRESETS,
    ConfigWizard,
    generate_commented_yaml,
    run_wizard,
    validate_config_dict,
)
from mcpbr.models import DEFAULT_MODEL


class TestPresets:
    """Tests for preset configurations."""

    def test_presets_exist(self) -> None:
        """Test that all expected presets are defined."""
        assert "filesystem" in PRESETS
        assert "web-search" in PRESETS
        assert "database" in PRESETS
        assert "custom" in PRESETS

    def test_preset_has_description(self) -> None:
        """Test that every preset has a description."""
        for name, preset in PRESETS.items():
            assert "description" in preset, f"Preset '{name}' missing description"
            assert len(preset["description"]) > 0, f"Preset '{name}' has empty description"

    def test_preset_has_mcp_server_key(self) -> None:
        """Test that every preset has an mcp_server key."""
        for name, preset in PRESETS.items():
            assert "mcp_server" in preset, f"Preset '{name}' missing mcp_server"

    def test_filesystem_preset_config(self) -> None:
        """Test filesystem preset has correct command and args."""
        preset = PRESETS["filesystem"]
        mcp = preset["mcp_server"]
        assert mcp["command"] == "npx"
        assert "{workdir}" in mcp["args"]
        assert "@modelcontextprotocol/server-filesystem" in mcp["args"]

    def test_web_search_preset_config(self) -> None:
        """Test web-search preset has brave search configuration."""
        preset = PRESETS["web-search"]
        mcp = preset["mcp_server"]
        assert mcp["command"] == "npx"
        assert "BRAVE_API_KEY" in mcp["env"]

    def test_database_preset_config(self) -> None:
        """Test database preset has postgres configuration."""
        preset = PRESETS["database"]
        mcp = preset["mcp_server"]
        assert mcp["command"] == "npx"
        assert "${DATABASE_URL}" in mcp["args"]

    def test_custom_preset_has_no_mcp_server(self) -> None:
        """Test custom preset has None for mcp_server."""
        preset = PRESETS["custom"]
        assert preset["mcp_server"] is None

    def test_non_custom_presets_have_mcp_server(self) -> None:
        """Test that all non-custom presets have valid mcp_server dicts."""
        for name, preset in PRESETS.items():
            if name == "custom":
                continue
            mcp = preset["mcp_server"]
            assert isinstance(mcp, dict), f"Preset '{name}' mcp_server should be a dict"
            assert "command" in mcp, f"Preset '{name}' mcp_server missing command"
            assert "args" in mcp, f"Preset '{name}' mcp_server missing args"


class TestValidateConfigDict:
    """Tests for the validate_config_dict function."""

    def test_valid_minimal_config(self) -> None:
        """Test that a minimal valid config passes validation."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "benchmark": "swe-bench-verified",
        }
        errors = validate_config_dict(config)
        assert errors == []

    def test_missing_mcp_server(self) -> None:
        """Test that missing mcp_server is reported."""
        config = {"benchmark": "swe-bench-verified"}
        errors = validate_config_dict(config)
        assert any("mcp_server is required" in e for e in errors)

    def test_mcp_server_not_dict(self) -> None:
        """Test that non-dict mcp_server is reported."""
        config = {"mcp_server": "invalid"}
        errors = validate_config_dict(config)
        assert any("must be a dictionary" in e for e in errors)

    def test_mcp_server_missing_command(self) -> None:
        """Test that mcp_server without command is reported."""
        config = {"mcp_server": {"args": []}}
        errors = validate_config_dict(config)
        assert any("command is required" in e for e in errors)

    def test_invalid_benchmark(self) -> None:
        """Test that invalid benchmark is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "benchmark": "nonexistent-benchmark",
        }
        errors = validate_config_dict(config)
        assert any("Invalid benchmark" in e for e in errors)

    def test_all_valid_benchmarks(self) -> None:
        """Test that all valid benchmarks pass validation."""
        for benchmark in VALID_BENCHMARKS:
            config = {
                "mcp_server": {"command": "npx", "args": []},
                "benchmark": benchmark,
            }
            errors = validate_config_dict(config)
            assert not any("Invalid benchmark" in e for e in errors), (
                f"Benchmark '{benchmark}' should be valid"
            )

    def test_timeout_too_low(self) -> None:
        """Test that timeout below 30 is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "timeout_seconds": 10,
        }
        errors = validate_config_dict(config)
        assert any("timeout_seconds must be at least 30" in e for e in errors)

    def test_timeout_at_minimum(self) -> None:
        """Test that timeout of exactly 30 is valid."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "timeout_seconds": 30,
        }
        errors = validate_config_dict(config)
        assert not any("timeout_seconds" in e for e in errors)

    def test_max_concurrent_zero(self) -> None:
        """Test that max_concurrent of 0 is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "max_concurrent": 0,
        }
        errors = validate_config_dict(config)
        assert any("max_concurrent must be at least 1" in e for e in errors)

    def test_thinking_budget_too_low(self) -> None:
        """Test that thinking_budget below 1024 is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "thinking_budget": 500,
        }
        errors = validate_config_dict(config)
        assert any("thinking_budget must be at least 1024" in e for e in errors)

    def test_thinking_budget_too_high(self) -> None:
        """Test that thinking_budget above 31999 is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "thinking_budget": 50000,
        }
        errors = validate_config_dict(config)
        assert any("thinking_budget cannot exceed 31999" in e for e in errors)

    def test_thinking_budget_valid(self) -> None:
        """Test that a valid thinking_budget passes."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "thinking_budget": 10000,
        }
        errors = validate_config_dict(config)
        assert not any("thinking_budget" in e for e in errors)

    def test_thinking_budget_none(self) -> None:
        """Test that None thinking_budget passes."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "thinking_budget": None,
        }
        errors = validate_config_dict(config)
        assert not any("thinking_budget" in e for e in errors)

    def test_budget_negative(self) -> None:
        """Test that negative budget is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "budget": -5.0,
        }
        errors = validate_config_dict(config)
        assert any("budget must be positive" in e for e in errors)

    def test_budget_zero(self) -> None:
        """Test that zero budget is reported."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "budget": 0,
        }
        errors = validate_config_dict(config)
        assert any("budget must be positive" in e for e in errors)

    def test_budget_positive(self) -> None:
        """Test that positive budget passes."""
        config = {
            "mcp_server": {"command": "npx", "args": []},
            "budget": 10.0,
        }
        errors = validate_config_dict(config)
        assert not any("budget" in e for e in errors)

    def test_default_benchmark_valid(self) -> None:
        """Test that omitting benchmark uses valid default."""
        config = {"mcp_server": {"command": "npx", "args": []}}
        errors = validate_config_dict(config)
        assert not any("benchmark" in e for e in errors)

    def test_multiple_errors(self) -> None:
        """Test that multiple errors are all reported."""
        config = {
            "benchmark": "invalid",
            "timeout_seconds": 5,
            "max_concurrent": 0,
        }
        errors = validate_config_dict(config)
        assert len(errors) >= 3  # mcp_server, benchmark, timeout, max_concurrent


class TestGenerateCommentedYaml:
    """Tests for YAML generation with comments."""

    def test_generates_valid_yaml(self) -> None:
        """Test that generated YAML is parseable."""
        config = {
            "mcp_server": {
                "name": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench-verified",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed is not None
        assert isinstance(parsed, dict)

    def test_contains_header_comments(self) -> None:
        """Test that generated YAML has header comments."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }
        yaml_str = generate_commented_yaml(config)
        assert "# mcpbr" in yaml_str
        assert "# Generated by the interactive configuration wizard" in yaml_str
        assert "ANTHROPIC_API_KEY" in yaml_str

    def test_contains_inline_comments(self) -> None:
        """Test that generated YAML has inline comments for fields."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench-verified",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        }
        yaml_str = generate_commented_yaml(config)
        assert "# Model ID" in yaml_str
        assert "# Benchmark to run" in yaml_str
        assert "# Number of tasks" in yaml_str
        assert "# Timeout" in yaml_str
        assert "# Maximum concurrent" in yaml_str
        assert "# Maximum agent iterations" in yaml_str

    def test_mcp_server_section(self) -> None:
        """Test that MCP server section is correctly generated."""
        config = {
            "mcp_server": {
                "name": "my-server",
                "command": "python",
                "args": ["-m", "myserver"],
                "env": {"API_KEY": "${API_KEY}"},
            },
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["mcp_server"]["name"] == "my-server"
        assert parsed["mcp_server"]["command"] == "python"
        assert parsed["mcp_server"]["args"] == ["-m", "myserver"]
        assert parsed["mcp_server"]["env"]["API_KEY"] == "${API_KEY}"

    def test_null_sample_size(self) -> None:
        """Test that null sample_size is serialized correctly."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
            "sample_size": None,
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["sample_size"] is None

    def test_integer_sample_size(self) -> None:
        """Test that integer sample_size is serialized correctly."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
            "sample_size": 25,
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["sample_size"] == 25

    def test_thinking_budget_included(self) -> None:
        """Test that thinking_budget is included when set."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
            "thinking_budget": 10000,
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["thinking_budget"] == 10000
        assert "# Extended thinking" in yaml_str

    def test_thinking_budget_excluded_when_not_set(self) -> None:
        """Test that thinking_budget is not included when not in config."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }
        yaml_str = generate_commented_yaml(config)
        assert "thinking_budget" not in yaml_str

    def test_budget_included(self) -> None:
        """Test that budget is included when set."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
            "budget": 50.0,
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["budget"] == 50.0

    def test_budget_excluded_when_not_set(self) -> None:
        """Test that budget is not included when not in config."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }
        yaml_str = generate_commented_yaml(config)
        assert "budget:" not in yaml_str

    def test_startup_timeout_included(self) -> None:
        """Test that startup_timeout_ms is included when set in mcp_server."""
        config = {
            "mcp_server": {
                "name": "test",
                "command": "echo",
                "args": [],
                "env": {},
                "startup_timeout_ms": 120000,
            },
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["mcp_server"]["startup_timeout_ms"] == 120000

    def test_setup_command_included(self) -> None:
        """Test that setup_command is included when set in mcp_server."""
        config = {
            "mcp_server": {
                "name": "test",
                "command": "echo",
                "args": [],
                "env": {},
                "setup_command": "pip install deps",
            },
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["mcp_server"]["setup_command"] == "pip install deps"

    def test_empty_env_serialized(self) -> None:
        """Test that empty env is serialized as empty dict."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["mcp_server"]["env"] == {}

    def test_default_values_applied(self) -> None:
        """Test that default values are applied for missing fields."""
        config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["provider"] == "anthropic"
        assert parsed["agent_harness"] == "claude-code"
        assert parsed["model"] == DEFAULT_MODEL
        assert parsed["benchmark"] == "swe-bench-verified"
        assert parsed["timeout_seconds"] == 300
        assert parsed["max_concurrent"] == 4
        assert parsed["max_iterations"] == 10

    def test_generated_yaml_loadable_by_load_config(self, tmp_path: Path) -> None:
        """Test that generated YAML can be loaded by mcpbr.config.load_config."""
        config = {
            "mcp_server": {
                "name": "filesystem",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
                "env": {},
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench-verified",
            "sample_size": 10,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        }
        yaml_str = generate_commented_yaml(config)
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml_str)

        loaded = load_config(str(config_file), warn_security=False)
        assert loaded.mcp_server.command == "npx"
        assert loaded.model == DEFAULT_MODEL
        assert loaded.benchmark == "swe-bench-verified"
        assert loaded.sample_size == 10
        assert loaded.timeout_seconds == 300

    def test_tool_timeout_included(self) -> None:
        """Test that tool_timeout_ms is included when set in mcp_server."""
        config = {
            "mcp_server": {
                "name": "test",
                "command": "echo",
                "args": [],
                "env": {},
                "tool_timeout_ms": 300000,
            },
        }
        yaml_str = generate_commented_yaml(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["mcp_server"]["tool_timeout_ms"] == 300000


class TestConfigWizard:
    """Tests for the ConfigWizard class."""

    def test_wizard_init(self) -> None:
        """Test that wizard initializes with empty config."""
        wizard = ConfigWizard()
        assert wizard.config == {}

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_select_preset_filesystem(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test selecting the filesystem preset."""
        mock_prompt.return_value = 1  # First preset (filesystem)
        wizard = ConfigWizard()
        wizard._select_preset()
        assert wizard.config["mcp_server"]["command"] == "npx"
        assert "@modelcontextprotocol/server-filesystem" in wizard.config["mcp_server"]["args"]

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_select_preset_web_search(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test selecting the web-search preset."""
        mock_prompt.return_value = 2  # Second preset (web-search)
        wizard = ConfigWizard()
        wizard._select_preset()
        assert "BRAVE_API_KEY" in wizard.config["mcp_server"]["env"]

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_select_preset_database(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test selecting the database preset."""
        mock_prompt.return_value = 3  # Third preset (database)
        wizard = ConfigWizard()
        wizard._select_preset()
        assert "${DATABASE_URL}" in wizard.config["mcp_server"]["args"]

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_select_preset_custom(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test selecting the custom preset."""
        # First call selects preset 4 (custom), subsequent calls configure the server
        mock_prompt.side_effect = [
            4,  # Select custom preset
            "my-server",  # Server name
            "python",  # Command
            "-m myserver",  # Args
        ]
        mock_confirm.return_value = False  # No env vars
        wizard = ConfigWizard()
        wizard._select_preset()
        assert wizard.config["mcp_server"]["command"] == "python"
        assert wizard.config["mcp_server"]["args"] == ["-m", "myserver"]

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_model_default(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring model with default selection."""
        mock_prompt.return_value = DEFAULT_MODEL
        wizard = ConfigWizard()
        wizard._configure_model()
        assert wizard.config["model"] == DEFAULT_MODEL

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_model_custom(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring model with a specific model ID."""
        mock_prompt.return_value = "claude-opus-4-5-20251101"
        wizard = ConfigWizard()
        wizard._configure_model()
        assert wizard.config["model"] == "claude-opus-4-5-20251101"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_model_unknown_accepted(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that unknown model is accepted when user confirms."""
        mock_prompt.return_value = "unknown-model-123"
        mock_confirm.return_value = True  # Accept unknown model
        wizard = ConfigWizard()
        wizard._configure_model()
        assert wizard.config["model"] == "unknown-model-123"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_model_unknown_rejected(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that unknown model falls back to default when rejected."""
        mock_prompt.return_value = "unknown-model-123"
        mock_confirm.return_value = False  # Reject unknown model
        wizard = ConfigWizard()
        wizard._configure_model()
        assert wizard.config["model"] == DEFAULT_MODEL

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_benchmark_default(self, mock_echo: object, mock_prompt: object) -> None:
        """Test configuring benchmark with default selection."""
        mock_prompt.return_value = "swe-bench-verified"
        wizard = ConfigWizard()
        wizard._configure_benchmark()
        assert wizard.config["benchmark"] == "swe-bench-verified"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_benchmark_custom(self, mock_echo: object, mock_prompt: object) -> None:
        """Test configuring benchmark with a specific selection."""
        mock_prompt.return_value = "humaneval"
        wizard = ConfigWizard()
        wizard._configure_benchmark()
        assert wizard.config["benchmark"] == "humaneval"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_mcp_servers_stdio(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring MCP server with stdio connection."""
        mock_prompt.side_effect = [
            1,  # stdio connection type
            "test",  # Server name
            60000,  # Startup timeout
            900000,  # Tool timeout
        ]
        mock_confirm.return_value = False  # No setup command
        wizard = ConfigWizard()
        wizard.config["mcp_server"] = {"name": "test", "command": "echo", "args": []}
        wizard._configure_mcp_servers()
        assert wizard.config["mcp_server"]["name"] == "test"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_mcp_servers_sse(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring MCP server with SSE connection."""
        mock_prompt.side_effect = [
            2,  # SSE connection type
            "http://localhost:8080/events",  # SSE URL
            "my-sse-server",  # Server name
            60000,  # Startup timeout
            900000,  # Tool timeout
        ]
        mock_confirm.return_value = False  # No setup command
        wizard = ConfigWizard()
        wizard.config["mcp_server"] = {"name": "test", "command": "echo", "args": []}
        wizard._configure_mcp_servers()
        assert "http://localhost:8080/events" in wizard.config["mcp_server"]["args"]
        assert wizard.config["mcp_server"]["name"] == "my-sse-server"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_mcp_servers_with_setup(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring MCP server with a setup command."""
        mock_prompt.side_effect = [
            1,  # stdio connection type
            "test",  # Server name
            60000,  # Startup timeout
            900000,  # Tool timeout
            "pip install -r req.txt",  # Setup command
        ]
        mock_confirm.return_value = True  # Yes to setup command
        wizard = ConfigWizard()
        wizard.config["mcp_server"] = {"name": "test", "command": "echo", "args": []}
        wizard._configure_mcp_servers()
        assert wizard.config["mcp_server"]["setup_command"] == "pip install -r req.txt"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_mcp_servers_custom_timeouts(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring MCP server with custom timeouts."""
        mock_prompt.side_effect = [
            1,  # stdio connection type
            "test",  # Server name
            120000,  # Custom startup timeout
            300000,  # Custom tool timeout
        ]
        mock_confirm.return_value = False  # No setup command
        wizard = ConfigWizard()
        wizard.config["mcp_server"] = {"name": "test", "command": "echo", "args": []}
        wizard._configure_mcp_servers()
        assert wizard.config["mcp_server"]["startup_timeout_ms"] == 120000
        assert wizard.config["mcp_server"]["tool_timeout_ms"] == 300000

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_skip(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test skipping advanced configuration applies defaults."""
        mock_confirm.return_value = False  # Skip advanced
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["provider"] == "anthropic"
        assert wizard.config["agent_harness"] == "claude-code"
        assert wizard.config["sample_size"] == 10
        assert wizard.config["timeout_seconds"] == 300
        assert wizard.config["max_concurrent"] == 4
        assert wizard.config["max_iterations"] == 10

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_custom_values(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring advanced settings with custom values."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "20",  # Sample size
            600,  # Timeout
            8,  # Max concurrent
            15,  # Max iterations
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["sample_size"] == 20
        assert wizard.config["timeout_seconds"] == 600
        assert wizard.config["max_concurrent"] == 8
        assert wizard.config["max_iterations"] == 15

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_full_dataset(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring advanced settings with 'all' for sample size."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "all",  # Full dataset
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["sample_size"] is None

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_with_thinking(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring advanced settings with thinking budget."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            True,  # Enable thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
            15000,  # Thinking budget
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["thinking_budget"] == 15000

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_with_budget(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test configuring advanced settings with budget cap."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            True,  # Set budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
            25.0,  # Budget
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["budget"] == 25.0

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_invalid_sample_size(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that invalid sample size input falls back to default."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "invalid",  # Bad sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["sample_size"] == 10

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_timeout_clamped(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that timeout below minimum is clamped to 30."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            5,  # Too low timeout
            4,  # Max concurrent
            10,  # Max iterations
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["timeout_seconds"] == 30

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_thinking_clamped_low(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that thinking budget below minimum is clamped to 1024."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            True,  # Enable thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
            500,  # Too low thinking budget
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["thinking_budget"] == 1024

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_thinking_clamped_high(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that thinking budget above maximum is clamped to 31999."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            True,  # Enable thinking
            False,  # No budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
            100000,  # Too high thinking budget
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert wizard.config["thinking_budget"] == 31999

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_configure_advanced_negative_budget_skipped(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test that negative budget is not stored."""
        mock_confirm.side_effect = [
            True,  # Configure advanced
            False,  # No thinking
            True,  # Set budget
        ]
        mock_prompt.side_effect = [
            "10",  # Sample size
            300,  # Timeout
            4,  # Max concurrent
            10,  # Max iterations
            -5.0,  # Negative budget
        ]
        wizard = ConfigWizard()
        wizard._configure_advanced()
        assert "budget" not in wizard.config

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_full_wizard_run(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test running the full wizard end-to-end."""
        mock_prompt.side_effect = [
            1,  # Preset: filesystem
            DEFAULT_MODEL,  # Model
            "swe-bench-verified",  # Benchmark
            1,  # stdio connection
            "filesystem",  # Server name
            60000,  # Startup timeout
            900000,  # Tool timeout
        ]
        mock_confirm.side_effect = [
            False,  # No setup command
            False,  # Skip advanced
        ]
        wizard = ConfigWizard()
        config = wizard.run()
        assert "mcp_server" in config
        assert config["model"] == DEFAULT_MODEL
        assert config["benchmark"] == "swe-bench-verified"
        assert config["provider"] == "anthropic"
        assert config["sample_size"] == 10

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_generate_config_writes_file(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object, tmp_path: Path
    ) -> None:
        """Test that _generate_config writes a valid YAML file."""
        wizard = ConfigWizard()
        wizard.config = {
            "mcp_server": {
                "name": "test",
                "command": "echo",
                "args": ["hello"],
                "env": {},
            },
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench-verified",
            "sample_size": 5,
            "timeout_seconds": 300,
            "max_concurrent": 4,
            "max_iterations": 10,
        }

        output_file = tmp_path / "output.yaml"
        wizard._generate_config(output_file)

        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0
        parsed = yaml.safe_load(content)
        assert parsed["mcp_server"]["command"] == "echo"
        assert parsed["model"] == DEFAULT_MODEL

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_generate_config_creates_parent_dirs(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object, tmp_path: Path
    ) -> None:
        """Test that _generate_config creates parent directories."""
        wizard = ConfigWizard()
        wizard.config = {
            "mcp_server": {"name": "test", "command": "echo", "args": [], "env": {}},
        }

        output_file = tmp_path / "nested" / "dir" / "output.yaml"
        wizard._generate_config(output_file)

        assert output_file.exists()


class TestRunWizard:
    """Tests for the run_wizard entry point."""

    @patch("mcpbr.config_wizard.ConfigWizard")
    @patch("mcpbr.config_wizard.click.echo")
    @patch("mcpbr.config_wizard.click.confirm")
    def test_run_wizard_writes_file(
        self, mock_confirm: object, mock_echo: object, mock_wizard_class: object, tmp_path: Path
    ) -> None:
        """Test that run_wizard writes a config file."""
        mock_instance = mock_wizard_class.return_value
        mock_instance.run.return_value = {
            "mcp_server": {
                "name": "test",
                "command": "echo",
                "args": [],
                "env": {},
            },
            "model": DEFAULT_MODEL,
            "benchmark": "swe-bench-verified",
            "sample_size": 10,
            "provider": "anthropic",
            "agent_harness": "claude-code",
        }

        output_path = tmp_path / "wizard_output.yaml"

        # Mock _generate_config to actually write
        def mock_generate(path: Path) -> str:
            yaml_str = generate_commented_yaml(mock_instance.run.return_value)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml_str)
            return yaml_str

        mock_instance._generate_config.side_effect = mock_generate

        run_wizard(output_path)

        assert output_path.exists()
        parsed = yaml.safe_load(output_path.read_text())
        assert parsed["model"] == DEFAULT_MODEL

    @patch("mcpbr.config_wizard.ConfigWizard")
    @patch("mcpbr.config_wizard.click.echo")
    def test_run_wizard_handles_abort(
        self, mock_echo: object, mock_wizard_class: object, tmp_path: Path
    ) -> None:
        """Test that run_wizard handles user abort gracefully."""
        mock_instance = mock_wizard_class.return_value
        mock_instance.run.side_effect = click.Abort()

        output_path = tmp_path / "wizard_output.yaml"
        run_wizard(output_path)

        assert not output_path.exists()

    @patch("mcpbr.config_wizard.ConfigWizard")
    @patch("mcpbr.config_wizard.click.echo")
    def test_run_wizard_handles_eof(
        self, mock_echo: object, mock_wizard_class: object, tmp_path: Path
    ) -> None:
        """Test that run_wizard handles EOFError gracefully."""
        mock_instance = mock_wizard_class.return_value
        mock_instance.run.side_effect = EOFError()

        output_path = tmp_path / "wizard_output.yaml"
        run_wizard(output_path)

        assert not output_path.exists()

    @patch("mcpbr.config_wizard.ConfigWizard")
    @patch("mcpbr.config_wizard.click.echo")
    @patch("mcpbr.config_wizard.click.confirm")
    def test_run_wizard_validation_errors_abort(
        self, mock_confirm: object, mock_echo: object, mock_wizard_class: object, tmp_path: Path
    ) -> None:
        """Test that run_wizard shows validation errors and can abort."""
        mock_instance = mock_wizard_class.return_value
        mock_instance.run.return_value = {
            # Missing mcp_server = validation error
            "benchmark": "invalid-benchmark",
        }
        mock_confirm.return_value = False  # Don't write anyway

        output_path = tmp_path / "wizard_output.yaml"
        run_wizard(output_path)

        # Should not have called _generate_config since user aborted
        mock_instance._generate_config.assert_not_called()


class TestCustomMcpServerPrompt:
    """Tests for custom MCP server configuration prompts."""

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_custom_server_with_env_vars(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test custom server with environment variables."""
        mock_prompt.side_effect = [
            4,  # Custom preset
            "api-server",  # Server name
            "uvx",  # Command
            "my-server --port 8080",  # Args
            "API_KEY",  # First env var name
            "secret123",  # First env var value
            "",  # Empty name to finish
        ]
        mock_confirm.side_effect = [
            True,  # Yes, add env vars
        ]
        wizard = ConfigWizard()
        wizard._select_preset()
        assert wizard.config["mcp_server"]["name"] == "api-server"
        assert wizard.config["mcp_server"]["command"] == "uvx"
        assert wizard.config["mcp_server"]["args"] == ["my-server", "--port", "8080"]
        assert wizard.config["mcp_server"]["env"]["API_KEY"] == "secret123"

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_custom_server_empty_args(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test custom server with empty args string."""
        mock_prompt.side_effect = [
            4,  # Custom preset
            "simple",  # Server name
            "my-cmd",  # Command
            "",  # Empty args
        ]
        mock_confirm.return_value = False  # No env vars
        wizard = ConfigWizard()
        wizard._select_preset()
        assert wizard.config["mcp_server"]["args"] == []

    @patch("mcpbr.config_wizard.click.prompt")
    @patch("mcpbr.config_wizard.click.confirm")
    @patch("mcpbr.config_wizard.click.echo")
    def test_custom_server_multiple_env_vars(
        self, mock_echo: object, mock_confirm: object, mock_prompt: object
    ) -> None:
        """Test custom server with multiple environment variables."""
        mock_prompt.side_effect = [
            4,  # Custom preset
            "multi-env",  # Server name
            "node",  # Command
            "server.js",  # Args
            "KEY1",  # First env var name
            "val1",  # First env var value
            "KEY2",  # Second env var name
            "val2",  # Second env var value
            "",  # Empty name to finish
        ]
        mock_confirm.side_effect = [
            True,  # Yes, add env vars
        ]
        wizard = ConfigWizard()
        wizard._select_preset()
        assert wizard.config["mcp_server"]["env"]["KEY1"] == "val1"
        assert wizard.config["mcp_server"]["env"]["KEY2"] == "val2"
