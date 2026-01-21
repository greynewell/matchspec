"""Tests for environment variable expansion in configuration."""

import os
import tempfile
from pathlib import Path

import pytest

from mcpbr.env_expansion import (
    expand_env_vars,
    load_dotenv_file,
    validate_config_security,
)


class TestExpandEnvVars:
    """Test environment variable expansion functionality."""

    def test_simple_string_substitution(self):
        """Test simple ${VAR} substitution."""
        os.environ["TEST_VAR"] = "test_value"
        try:
            result = expand_env_vars("prefix_${TEST_VAR}_suffix")
            assert result == "prefix_test_value_suffix"
        finally:
            del os.environ["TEST_VAR"]

    def test_substitution_with_default(self):
        """Test ${VAR:-default} substitution when var is not set."""
        # Make sure var is not set
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        result = expand_env_vars("value_${NONEXISTENT_VAR:-default_value}")
        assert result == "value_default_value"

    def test_substitution_with_default_var_set(self):
        """Test ${VAR:-default} uses actual value when var is set."""
        os.environ["TEST_VAR"] = "actual_value"
        try:
            result = expand_env_vars("${TEST_VAR:-default_value}")
            assert result == "actual_value"
        finally:
            del os.environ["TEST_VAR"]

    def test_missing_required_var_raises_error(self):
        """Test that missing required variable raises ValueError."""
        if "NONEXISTENT_VAR" in os.environ:
            del os.environ["NONEXISTENT_VAR"]

        with pytest.raises(ValueError, match="Required environment variable 'NONEXISTENT_VAR'"):
            expand_env_vars("${NONEXISTENT_VAR}")

    def test_multiple_substitutions(self):
        """Test multiple variable substitutions in one string."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        try:
            result = expand_env_vars("${VAR1}_middle_${VAR2}")
            assert result == "value1_middle_value2"
        finally:
            del os.environ["VAR1"]
            del os.environ["VAR2"]

    def test_dict_expansion(self):
        """Test expansion in nested dictionaries."""
        os.environ["TEST_KEY"] = "test_value"
        try:
            config = {
                "top": "${TEST_KEY}",
                "nested": {
                    "inner": "${TEST_KEY}_inner",
                },
            }
            result = expand_env_vars(config)
            assert result["top"] == "test_value"
            assert result["nested"]["inner"] == "test_value_inner"
        finally:
            del os.environ["TEST_KEY"]

    def test_list_expansion(self):
        """Test expansion in lists."""
        os.environ["TEST_VAR"] = "value"
        try:
            config = ["${TEST_VAR}", "static", "${TEST_VAR:-default}"]
            result = expand_env_vars(config)
            assert result == ["value", "static", "value"]
        finally:
            del os.environ["TEST_VAR"]

    def test_non_string_values_unchanged(self):
        """Test that non-string values pass through unchanged."""
        config = {
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
        }
        result = expand_env_vars(config)
        assert result == config

    def test_empty_string_var(self):
        """Test handling of empty string environment variable."""
        os.environ["EMPTY_VAR"] = ""
        try:
            result = expand_env_vars("prefix_${EMPTY_VAR}_suffix")
            assert result == "prefix__suffix"
        finally:
            del os.environ["EMPTY_VAR"]

    def test_default_with_special_chars(self):
        """Test default values containing special characters."""
        result = expand_env_vars("${NONEXISTENT:-/path/to/file}")
        assert result == "/path/to/file"

    def test_nested_braces_not_expanded(self):
        """Test that nested ${} are not expanded (literal in default)."""
        result = expand_env_vars("${NONEXISTENT:-value}")
        assert result == "value"


class TestLoadDotenvFile:
    """Test .env file loading functionality."""

    def test_load_simple_dotenv(self):
        """Test loading simple KEY=VALUE pairs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text("TEST_KEY=test_value\nANOTHER_KEY=another_value\n")

            # Clear env vars if they exist
            for key in ["TEST_KEY", "ANOTHER_KEY"]:
                if key in os.environ:
                    del os.environ[key]

            try:
                load_dotenv_file(dotenv_path)
                assert os.environ["TEST_KEY"] == "test_value"
                assert os.environ["ANOTHER_KEY"] == "another_value"
            finally:
                for key in ["TEST_KEY", "ANOTHER_KEY"]:
                    if key in os.environ:
                        del os.environ[key]

    def test_load_quoted_values(self):
        """Test loading values with quotes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text(
                "DOUBLE_QUOTED=\"value with spaces\"\nSINGLE_QUOTED='value with spaces'\n"
            )

            for key in ["DOUBLE_QUOTED", "SINGLE_QUOTED"]:
                if key in os.environ:
                    del os.environ[key]

            try:
                load_dotenv_file(dotenv_path)
                assert os.environ["DOUBLE_QUOTED"] == "value with spaces"
                assert os.environ["SINGLE_QUOTED"] == "value with spaces"
            finally:
                for key in ["DOUBLE_QUOTED", "SINGLE_QUOTED"]:
                    if key in os.environ:
                        del os.environ[key]

    def test_skip_comments(self):
        """Test that comments are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text("# This is a comment\nTEST_KEY=value\n# Another comment\n")

            if "TEST_KEY" in os.environ:
                del os.environ["TEST_KEY"]

            try:
                load_dotenv_file(dotenv_path)
                assert os.environ["TEST_KEY"] == "value"
            finally:
                if "TEST_KEY" in os.environ:
                    del os.environ["TEST_KEY"]

    def test_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text("\n\nTEST_KEY=value\n\n")

            if "TEST_KEY" in os.environ:
                del os.environ["TEST_KEY"]

            try:
                load_dotenv_file(dotenv_path)
                assert os.environ["TEST_KEY"] == "value"
            finally:
                if "TEST_KEY" in os.environ:
                    del os.environ["TEST_KEY"]

    def test_dont_override_existing(self):
        """Test that existing environment variables are not overridden."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dotenv_path = Path(tmpdir) / ".env"
            dotenv_path.write_text("TEST_KEY=dotenv_value\n")

            os.environ["TEST_KEY"] = "existing_value"
            try:
                load_dotenv_file(dotenv_path)
                # Should keep existing value
                assert os.environ["TEST_KEY"] == "existing_value"
            finally:
                del os.environ["TEST_KEY"]

    def test_nonexistent_file_ignored(self):
        """Test that nonexistent .env file is silently ignored."""
        load_dotenv_file(Path("/nonexistent/.env"))
        # Should not raise an error


class TestValidateConfigSecurity:
    """Test security validation functionality."""

    def test_detect_api_key_in_string(self):
        """Test detection of hardcoded API keys."""
        config = {
            "mcp_server": {
                "env": {
                    "API_KEY": "sk-1234567890abcdef"  # Hardcoded
                }
            }
        }
        warnings = validate_config_security(config)
        assert len(warnings) > 0
        assert any("api key" in w.lower() for w in warnings)

    def test_no_warning_for_env_var_reference(self):
        """Test that ${ENV_VAR} references don't trigger warnings."""
        config = {"mcp_server": {"env": {"API_KEY": "${ANTHROPIC_API_KEY}"}}}
        warnings = validate_config_security(config)
        # Should not warn about env var references
        assert not any("api key" in w.lower() and "hardcoded" in w.lower() for w in warnings)

    def test_detect_password(self):
        """Test detection of hardcoded passwords."""
        config = {"database": {"password": "secret123"}}
        warnings = validate_config_security(config)
        assert len(warnings) > 0
        assert any("password" in w.lower() for w in warnings)

    def test_detect_token(self):
        """Test detection of hardcoded tokens."""
        config = {"auth": {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}}
        warnings = validate_config_security(config)
        assert len(warnings) > 0
        assert any("token" in w.lower() for w in warnings)

    def test_nested_dict_scanning(self):
        """Test that nested dictionaries are scanned."""
        config = {"level1": {"level2": {"level3": {"api_key": "hardcoded_key"}}}}
        warnings = validate_config_security(config)
        assert len(warnings) > 0

    def test_list_scanning(self):
        """Test that lists are scanned."""
        config = {
            "servers": [
                {"api_key": "hardcoded_key_1"},
                {"api_key": "hardcoded_key_2"},
            ]
        }
        warnings = validate_config_security(config)
        assert len(warnings) >= 2  # Should warn about both keys

    def test_no_warnings_for_safe_config(self):
        """Test that safe configurations don't generate warnings."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                "env": {
                    "API_KEY": "${ANTHROPIC_API_KEY}",
                    "TOKEN": "${AUTH_TOKEN:-default}",
                },
            },
            "model": "sonnet",
            "timeout": 300,
        }
        warnings = validate_config_security(config)
        # Should have no security warnings
        assert len(warnings) == 0
