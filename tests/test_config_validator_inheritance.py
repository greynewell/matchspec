"""Tests for config validator with inheritance support."""

import tempfile
from pathlib import Path

from mcpbr.config_validator import validate_config


class TestConfigValidatorWithExtends:
    """Test config validator with extends field."""

    def test_extends_string_valid(self) -> None:
        """Test that extends with string value is valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base config
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            # Create config with extends
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: ./base.yaml

model: opus
""")

            result = validate_config(config_path)
            # Should be valid even without mcp_server since it uses extends
            assert result.valid

    def test_extends_list_valid(self) -> None:
        """Test that extends with list value is valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base configs
            base1_path = Path(tmpdir) / "base1.yaml"
            base1_path.write_text("""
mcp_server:
  command: npx

provider: anthropic
""")

            base2_path = Path(tmpdir) / "base2.yaml"
            base2_path.write_text("""
agent_harness: claude-code
model: sonnet
""")

            # Create config with extends list
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends:
  - ./base1.yaml
  - ./base2.yaml

sample_size: 5
""")

            result = validate_config(config_path)
            assert result.valid

    def test_extends_invalid_type(self) -> None:
        """Test that extends with invalid type produces error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: 123

mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            result = validate_config(config_path)
            assert not result.valid
            assert any("extends" in error.field for error in result.errors)

    def test_extends_list_with_invalid_item(self) -> None:
        """Test that extends list with non-string item produces error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends:
  - ./base.yaml
  - 123

mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            result = validate_config(config_path)
            assert not result.valid
            assert any("extends" in error.field for error in result.errors)

    def test_config_without_mcp_server_but_with_extends(self) -> None:
        """Test that config without mcp_server is allowed if it has extends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base with mcp_server
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            # Create config that only extends and overrides model
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: ./base.yaml

model: opus
sample_size: 5
""")

            result = validate_config(config_path)
            # Should be valid because extends is present
            assert result.valid

    def test_config_without_mcp_server_and_no_extends(self) -> None:
        """Test that config without mcp_server and no extends produces error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            result = validate_config(config_path)
            # Should have error about missing mcp_server
            assert not result.valid
            assert any("mcp_server" in error.field for error in result.errors)

    def test_extends_url(self) -> None:
        """Test that extends with URL is accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: https://example.com/base.yaml

model: opus
""")

            result = validate_config(config_path)
            # Validator doesn't actually fetch the URL, so it should pass validation
            # (the actual loading will happen in load_config)
            assert result.valid

    def test_extends_with_complete_config(self) -> None:
        """Test that extends works alongside a complete config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
timeout_seconds: 300
max_concurrent: 4
""")

            # Create config that has both extends and full config
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: ./base.yaml

mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            result = validate_config(config_path)
            assert result.valid
