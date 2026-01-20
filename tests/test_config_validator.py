"""Tests for configuration validation."""

import os
import tempfile
from pathlib import Path

from mcpbr.config_validator import validate_config


class TestConfigValidator:
    """Tests for ConfigValidator class."""

    def test_valid_yaml_config(self) -> None:
        """Test validation of a valid YAML config."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"

provider: anthropic
agent_harness: claude-code
model: claude-sonnet-4-5-20250514
benchmark: swe-bench
sample_size: 10
timeout_seconds: 300
max_concurrent: 4
max_iterations: 10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert result.valid
            assert not result.has_errors
        finally:
            Path(config_path).unlink()

    def test_missing_file(self) -> None:
        """Test validation of non-existent file."""
        result = validate_config("/nonexistent/config.yaml")

        assert not result.valid
        assert result.has_errors
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].error.lower()

    def test_invalid_yaml_syntax(self) -> None:
        """Test validation of file with YAML syntax errors."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - invalid indentation
   - wrong indent
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            # Should have YAML syntax error
            assert any("syntax" in err.error.lower() for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_missing_mcp_server(self) -> None:
        """Test validation when mcp_server is missing."""
        yaml_content = """
provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("mcp_server" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_missing_command_in_mcp_server(self) -> None:
        """Test validation when mcp_server.command is missing."""
        yaml_content = """
mcp_server:
  args:
    - "test"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("command" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_invalid_provider(self) -> None:
        """Test validation with invalid provider."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: invalid-provider
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("provider" in err.field for err in result.errors)
            assert any("invalid" in err.error.lower() for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_invalid_harness(self) -> None:
        """Test validation with invalid agent_harness."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: anthropic
agent_harness: invalid-harness
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("agent_harness" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_invalid_benchmark(self) -> None:
        """Test validation with invalid benchmark."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: anthropic
benchmark: invalid-benchmark
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("benchmark" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_timeout_too_low(self) -> None:
        """Test validation when timeout is below minimum."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: anthropic
model: claude-sonnet-4-5-20250514
timeout_seconds: 10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("timeout_seconds" in err.field for err in result.errors)
            assert any("30" in err.error for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_max_concurrent_too_low(self) -> None:
        """Test validation when max_concurrent is below minimum."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: anthropic
model: claude-sonnet-4-5-20250514
max_concurrent: 0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("max_concurrent" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_cybergym_level_out_of_range(self) -> None:
        """Test validation when cybergym_level is out of range."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "test"

provider: anthropic
model: claude-sonnet-4-5-20250514
benchmark: cybergym
cybergym_level: 5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("cybergym_level" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_warning_for_missing_workdir_placeholder(self) -> None:
        """Test that a warning is issued when {workdir} is missing from args."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            # Should be valid but have warnings
            assert result.valid
            assert result.has_warnings
            assert any("workdir" in warn.error.lower() for warn in result.warnings)
        finally:
            Path(config_path).unlink()

    def test_warning_for_missing_problem_statement_placeholder(self) -> None:
        """Test that a warning is issued when {problem_statement} is missing from agent_prompt."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
agent_prompt: "Fix this bug now"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            # Should be valid but have warnings
            assert result.valid
            assert result.has_warnings
            assert any("problem_statement" in warn.error.lower() for warn in result.warnings)
        finally:
            Path(config_path).unlink()

    def test_args_not_a_list(self) -> None:
        """Test validation when args is not a list."""
        yaml_content = """
mcp_server:
  command: npx
  args: "not-a-list"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("args" in err.field for err in result.errors)
            assert any("list" in err.error.lower() for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_env_not_a_dict(self) -> None:
        """Test validation when env is not a dictionary."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"
  env: ["not", "a", "dict"]

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("env" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_empty_command(self) -> None:
        """Test validation when command is empty string."""
        yaml_content = """
mcp_server:
  command: ""
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("command" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_empty_model(self) -> None:
        """Test validation when model is empty string."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: ""
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("model" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_numeric_field_wrong_type(self) -> None:
        """Test validation when a numeric field has wrong type."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
timeout_seconds: "not-a-number"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("timeout_seconds" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_multiple_errors(self) -> None:
        """Test validation with multiple errors."""
        yaml_content = """
mcp_server:
  command: ""
  args: "not-a-list"

provider: invalid-provider
agent_harness: invalid-harness
benchmark: invalid-benchmark
model: ""
timeout_seconds: 10
max_concurrent: 0
cybergym_level: 5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            # Should have multiple errors
            assert len(result.errors) >= 5
        finally:
            Path(config_path).unlink()

    def test_warning_for_undefined_env_var(self) -> None:
        """Test that a warning is issued for undefined environment variables."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"
  env:
    MY_VAR: "${UNDEFINED_ENV_VAR}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Make sure the variable is not set
            if "UNDEFINED_ENV_VAR" in os.environ:
                del os.environ["UNDEFINED_ENV_VAR"]

            result = validate_config(config_path)
            # Should be valid but have warnings
            assert result.valid
            assert result.has_warnings
            assert any("UNDEFINED_ENV_VAR" in warn.error for warn in result.warnings)
        finally:
            Path(config_path).unlink()

    def test_no_warning_for_defined_env_var(self) -> None:
        """Test that no warning is issued for defined environment variables."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"
  env:
    MY_VAR: "${DEFINED_ENV_VAR}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Set the variable
            os.environ["DEFINED_ENV_VAR"] = "test-value"

            result = validate_config(config_path)
            assert result.valid
            # Should not have warning about this specific env var
            assert not any("DEFINED_ENV_VAR" in warn.error for warn in result.warnings)
        finally:
            Path(config_path).unlink()
            if "DEFINED_ENV_VAR" in os.environ:
                del os.environ["DEFINED_ENV_VAR"]

    def test_valid_config_with_all_optional_fields(self) -> None:
        """Test validation of config with all optional fields set."""
        yaml_content = """
mcp_server:
  name: my-server
  command: python
  args:
    - "-m"
    - "myserver"
    - "{workdir}"
  env:
    DEBUG: "true"

provider: anthropic
agent_harness: claude-code
benchmark: cybergym
model: claude-sonnet-4-5-20250514
dataset: custom/dataset
agent_prompt: "Fix this: {problem_statement}"
cybergym_level: 2
sample_size: 50
timeout_seconds: 600
max_concurrent: 8
max_iterations: 20
use_prebuilt_images: false
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert result.valid
            assert not result.has_errors
        finally:
            Path(config_path).unlink()

    def test_wrong_file_extension_warning(self) -> None:
        """Test that a warning is issued for unexpected file extensions."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            # Should be valid but have warning about extension
            assert result.has_warnings
            assert any("extension" in warn.error.lower() for warn in result.warnings)
        finally:
            Path(config_path).unlink()

    def test_yml_extension_accepted(self) -> None:
        """Test that .yml extension is accepted."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert result.valid
            # Should not have warning about extension for .yml
            assert not any(
                "extension" in warn.error.lower() and ".yml" in warn.error
                for warn in result.warnings
            )
        finally:
            Path(config_path).unlink()

    def test_empty_name_error(self) -> None:
        """Test validation when name is empty string."""
        yaml_content = """
mcp_server:
  name: ""
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("name" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()

    def test_negative_sample_size_error(self) -> None:
        """Test validation when sample_size is negative."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
sample_size: -5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            result = validate_config(config_path)
            assert not result.valid
            assert result.has_errors
            assert any("sample_size" in err.field for err in result.errors)
        finally:
            Path(config_path).unlink()


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_missing_api_key_warning(self) -> None:
        """Test that a warning is issued when ANTHROPIC_API_KEY is not set."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Temporarily remove the API key
            old_key = os.environ.pop("ANTHROPIC_API_KEY", None)

            result = validate_config(config_path)
            # Should be valid but have warning
            assert result.valid
            assert result.has_warnings
            assert any("ANTHROPIC_API_KEY" in warn.error for warn in result.warnings)
        finally:
            Path(config_path).unlink()
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_valid_api_key_no_warning(self) -> None:
        """Test that no warning is issued for valid API key format."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Set a valid-looking API key
            old_key = os.environ.get("ANTHROPIC_API_KEY")
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-test-key-12345678901234567890"

            result = validate_config(config_path)
            assert result.valid
            # Should not have API key warnings
            assert not any(
                "ANTHROPIC_API_KEY" in warn.error and "format" in warn.error.lower()
                for warn in result.warnings
            )
        finally:
            Path(config_path).unlink()
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_invalid_api_key_format_warning(self) -> None:
        """Test that a warning is issued for invalid API key format."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Set an invalid API key
            old_key = os.environ.get("ANTHROPIC_API_KEY")
            os.environ["ANTHROPIC_API_KEY"] = "invalid-key"

            result = validate_config(config_path)
            assert result.valid
            assert result.has_warnings
            assert any(
                "ANTHROPIC_API_KEY" in warn.error and "format" in warn.error.lower()
                for warn in result.warnings
            )
        finally:
            Path(config_path).unlink()
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_short_api_key_warning(self) -> None:
        """Test that a warning is issued for too-short API keys."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - "{workdir}"

provider: anthropic
model: claude-sonnet-4-5-20250514
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            # Set a too-short API key
            old_key = os.environ.get("ANTHROPIC_API_KEY")
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-short"

            result = validate_config(config_path)
            assert result.valid
            assert result.has_warnings
            assert any("too short" in warn.error.lower() for warn in result.warnings)
        finally:
            Path(config_path).unlink()
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)
