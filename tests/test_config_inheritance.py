"""Tests for configuration inheritance and merging."""

import tempfile
from pathlib import Path

import pytest

from mcpbr.config import load_config
from mcpbr.config_inheritance import (
    CircularInheritanceError,
    ConfigInheritanceError,
    deep_merge,
    load_config_with_inheritance,
    resolve_config_path,
)


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_simple_merge(self) -> None:
        """Test simple merge of two dicts."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test deep merge of nested dicts."""
        base = {"mcp_server": {"command": "npx", "args": ["a", "b"]}, "model": "sonnet"}
        override = {"mcp_server": {"args": ["c", "d"], "env": {"KEY": "value"}}, "timeout": 300}
        result = deep_merge(base, override)

        assert result == {
            "mcp_server": {
                "command": "npx",
                "args": ["c", "d"],  # Lists are replaced, not merged
                "env": {"KEY": "value"},
            },
            "model": "sonnet",
            "timeout": 300,
        }

    def test_list_replacement(self) -> None:
        """Test that lists are replaced, not merged."""
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = deep_merge(base, override)
        assert result == {"items": [4, 5]}

    def test_deep_nested_merge(self) -> None:
        """Test deeply nested dict merging."""
        base = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        override = {"a": {"b": {"c": 10, "f": 4}, "g": 5}}
        result = deep_merge(base, override)

        assert result == {"a": {"b": {"c": 10, "d": 2, "f": 4}, "e": 3, "g": 5}}

    def test_empty_override(self) -> None:
        """Test merge with empty override."""
        base = {"a": 1, "b": 2}
        override = {}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_empty_base(self) -> None:
        """Test merge with empty base."""
        base = {}
        override = {"a": 1, "b": 2}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_none_values(self) -> None:
        """Test that None values override properly."""
        base = {"a": 1, "b": 2}
        override = {"b": None}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": None}


class TestResolveConfigPath:
    """Tests for resolve_config_path function."""

    def test_absolute_path(self) -> None:
        """Test that absolute paths are returned as-is."""
        current = Path("/home/user/config.yaml")
        result = resolve_config_path("/etc/base.yaml", current)
        assert result == "/etc/base.yaml"

    def test_relative_path(self) -> None:
        """Test that relative paths are resolved."""
        current = Path("/home/user/configs/dev.yaml")
        result = resolve_config_path("../base.yaml", current)
        # Check that the path ends with the expected relative structure
        assert Path(result).name == "base.yaml"
        assert Path(result).parent.name == "user"

    def test_relative_path_same_dir(self) -> None:
        """Test relative path in same directory."""
        current = Path("/home/user/config.yaml")
        result = resolve_config_path("./base.yaml", current)
        # Check that the path ends with the expected relative structure
        assert Path(result).name == "base.yaml"
        assert Path(result).parent.name == "user"

    def test_http_url(self) -> None:
        """Test that HTTP URLs are returned as-is."""
        current = Path("/home/user/config.yaml")
        result = resolve_config_path("http://example.com/base.yaml", current)
        assert result == "http://example.com/base.yaml"

    def test_https_url(self) -> None:
        """Test that HTTPS URLs are returned as-is."""
        current = Path("/home/user/config.yaml")
        result = resolve_config_path("https://example.com/base.yaml", current)
        assert result == "https://example.com/base.yaml"


class TestLoadConfigWithInheritance:
    """Tests for load_config_with_inheritance function."""

    def test_no_inheritance(self) -> None:
        """Test loading config without extends field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            result = load_config_with_inheritance(config_path)
            assert result["mcp_server"]["command"] == "npx"
            assert result["model"] == "sonnet"
            assert "extends" not in result

    def test_single_inheritance(self) -> None:
        """Test single level inheritance."""
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
timeout_seconds: 300
""")

            # Create derived config
            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends: ./base.yaml

model: opus
sample_size: 5
""")

            result = load_config_with_inheritance(derived_path)

            # Should have values from base
            assert result["mcp_server"]["command"] == "npx"
            assert result["provider"] == "anthropic"
            assert result["timeout_seconds"] == 300

            # Should override model
            assert result["model"] == "opus"

            # Should add new field
            assert result["sample_size"] == 5

            # extends should be removed
            assert "extends" not in result

    def test_multiple_inheritance_levels(self) -> None:
        """Test multiple levels of inheritance."""
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
timeout_seconds: 300
""")

            # Create intermediate config
            intermediate_path = Path(tmpdir) / "intermediate.yaml"
            intermediate_path.write_text("""
extends: ./base.yaml

model: opus
max_concurrent: 2
""")

            # Create final config
            final_path = Path(tmpdir) / "final.yaml"
            final_path.write_text("""
extends: ./intermediate.yaml

max_concurrent: 4
sample_size: 10
""")

            result = load_config_with_inheritance(final_path)

            # Should have values from base
            assert result["mcp_server"]["command"] == "npx"
            assert result["timeout_seconds"] == 300

            # Should have intermediate override
            assert result["model"] == "opus"

            # Should have final override
            assert result["max_concurrent"] == 4
            assert result["sample_size"] == 10

    def test_multiple_extends_list(self) -> None:
        """Test extending from multiple configs (list syntax)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first base
            base1_path = Path(tmpdir) / "base1.yaml"
            base1_path.write_text("""
mcp_server:
  command: npx

provider: anthropic
model: sonnet
""")

            # Create second base
            base2_path = Path(tmpdir) / "base2.yaml"
            base2_path.write_text("""
agent_harness: claude-code
timeout_seconds: 300
max_concurrent: 2
""")

            # Create derived config extending both
            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends:
  - ./base1.yaml
  - ./base2.yaml

model: opus
sample_size: 5
""")

            result = load_config_with_inheritance(derived_path)

            # Should have values from both bases
            assert result["mcp_server"]["command"] == "npx"
            assert result["provider"] == "anthropic"
            assert result["agent_harness"] == "claude-code"
            assert result["timeout_seconds"] == 300
            assert result["max_concurrent"] == 2

            # Should override model
            assert result["model"] == "opus"

            # Should add new field
            assert result["sample_size"] == 5

    def test_nested_dict_merge(self) -> None:
        """Test that nested dicts are merged properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base with mcp_server config
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  name: filesystem
  command: npx
  args: ["-y", "server"]
  env:
    BASE_VAR: base_value

provider: anthropic
model: sonnet
""")

            # Create derived that adds to mcp_server
            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends: ./base.yaml

mcp_server:
  env:
    NEW_VAR: new_value
    BASE_VAR: overridden

model: opus
""")

            result = load_config_with_inheritance(derived_path)

            # Should merge mcp_server dict
            assert result["mcp_server"]["name"] == "filesystem"
            assert result["mcp_server"]["command"] == "npx"
            assert result["mcp_server"]["args"] == ["-y", "server"]

            # Should merge env dict
            assert result["mcp_server"]["env"]["NEW_VAR"] == "new_value"
            assert result["mcp_server"]["env"]["BASE_VAR"] == "overridden"

            # Should override model
            assert result["model"] == "opus"

    def test_circular_dependency_direct(self) -> None:
        """Test detection of direct circular dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config that extends itself
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: ./config.yaml

model: sonnet
""")

            with pytest.raises(CircularInheritanceError, match="Circular inheritance detected"):
                load_config_with_inheritance(config_path)

    def test_circular_dependency_indirect(self) -> None:
        """Test detection of indirect circular dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create A -> B -> C -> A cycle
            config_a = Path(tmpdir) / "a.yaml"
            config_a.write_text("""
extends: ./b.yaml
value: a
""")

            config_b = Path(tmpdir) / "b.yaml"
            config_b.write_text("""
extends: ./c.yaml
value: b
""")

            config_c = Path(tmpdir) / "c.yaml"
            config_c.write_text("""
extends: ./a.yaml
value: c
""")

            with pytest.raises(CircularInheritanceError, match="Circular inheritance detected"):
                load_config_with_inheritance(config_a)

    def test_missing_extends_file(self) -> None:
        """Test error when extends file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("""
extends: ./nonexistent.yaml

model: sonnet
""")

            with pytest.raises(
                ConfigInheritanceError, match=r"Config file not found.*nonexistent.yaml"
            ):
                load_config_with_inheritance(config_path)

    def test_absolute_path_extends(self) -> None:
        """Test extends with absolute path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base in one location
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx

model: sonnet
""")

            # Create derived in subdirectory with absolute path
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            derived_path = subdir / "derived.yaml"
            derived_path.write_text(f"""
extends: {base_path}

model: opus
""")

            result = load_config_with_inheritance(derived_path)
            assert result["mcp_server"]["command"] == "npx"
            assert result["model"] == "opus"

    def test_relative_path_different_directories(self) -> None:
        """Test extends with relative paths across directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base in configs/
            configs_dir = Path(tmpdir) / "configs"
            configs_dir.mkdir()
            base_path = configs_dir / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx

model: sonnet
""")

            # Create derived in environments/ that references ../configs/base.yaml
            env_dir = Path(tmpdir) / "environments"
            env_dir.mkdir()
            derived_path = env_dir / "dev.yaml"
            derived_path.write_text("""
extends: ../configs/base.yaml

model: opus
sample_size: 5
""")

            result = load_config_with_inheritance(derived_path)
            assert result["mcp_server"]["command"] == "npx"
            assert result["model"] == "opus"
            assert result["sample_size"] == 5

    def test_invalid_yaml_in_base(self) -> None:
        """Test error handling for invalid YAML in base config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
invalid yaml: [unclosed
""")

            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends: ./base.yaml
model: sonnet
""")

            with pytest.raises(ConfigInheritanceError, match="Failed to parse config file"):
                load_config_with_inheritance(derived_path)


class TestLoadConfigIntegration:
    """Integration tests for load_config with inheritance."""

    def test_load_config_with_extends(self) -> None:
        """Test that load_config properly handles extends."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base config
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"

provider: anthropic
agent_harness: claude-code
model: sonnet
timeout_seconds: 300
""")

            # Create derived config
            derived_path = Path(tmpdir) / "dev.yaml"
            derived_path.write_text("""
extends: ./base.yaml

model: opus
sample_size: 5
max_concurrent: 2
""")

            # Load through main load_config function
            config = load_config(derived_path, warn_security=False)

            # Verify inheritance worked
            assert config.mcp_server.command == "npx"
            assert len(config.mcp_server.args) == 3
            assert config.provider == "anthropic"
            assert config.agent_harness == "claude-code"
            assert config.timeout_seconds == 300

            # Verify overrides
            assert config.model == "opus"
            assert config.sample_size == 5
            assert config.max_concurrent == 2

    def test_load_config_with_env_vars_and_extends(self) -> None:
        """Test that env var expansion works with inheritance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            # Create base config
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
  env:
    BASE_KEY: "${BASE_VALUE}"

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            # Create derived config
            derived_path = Path(tmpdir) / "dev.yaml"
            derived_path.write_text("""
extends: ./base.yaml

mcp_server:
  env:
    DEV_KEY: "${DEV_VALUE}"

model: "${MODEL_NAME:-opus}"
sample_size: 5
""")

            # Set environment variables
            os.environ["BASE_VALUE"] = "base_key_value"
            os.environ["DEV_VALUE"] = "dev_key_value"
            # Don't set MODEL_NAME to test default

            try:
                config = load_config(derived_path, warn_security=False)

                # Verify env expansion worked
                assert config.mcp_server.env["BASE_KEY"] == "base_key_value"
                assert config.mcp_server.env["DEV_KEY"] == "dev_key_value"
                assert config.model == "opus"  # Should use default
                assert config.sample_size == 5
            finally:
                # Clean up
                del os.environ["BASE_VALUE"]
                del os.environ["DEV_VALUE"]

    def test_load_config_with_multi_level_inheritance(self) -> None:
        """Test load_config with multiple inheritance levels."""
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
timeout_seconds: 300
max_concurrent: 4
""")

            # Create staging config
            staging_path = Path(tmpdir) / "staging.yaml"
            staging_path.write_text("""
extends: ./base.yaml

model: opus
max_concurrent: 2
""")

            # Create dev config
            dev_path = Path(tmpdir) / "dev.yaml"
            dev_path.write_text("""
extends: ./staging.yaml

sample_size: 1
max_concurrent: 1
""")

            config = load_config(dev_path, warn_security=False)

            # From base
            assert config.mcp_server.command == "npx"
            assert config.timeout_seconds == 300

            # From staging
            assert config.model == "opus"

            # From dev (overrides staging)
            assert config.max_concurrent == 1
            assert config.sample_size == 1

    def test_validation_after_inheritance(self) -> None:
        """Test that validation still works after inheritance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base with valid config
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args: ["-y", "server"]

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            # Create derived with invalid provider
            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends: ./base.yaml

provider: invalid_provider
""")

            # Should raise validation error
            from pydantic import ValidationError

            with pytest.raises(ValidationError, match="Invalid provider"):
                load_config(derived_path, warn_security=False)

    def test_array_override_in_inheritance(self) -> None:
        """Test that arrays are completely replaced in inheritance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base config with args
            base_path = Path(tmpdir) / "base.yaml"
            base_path.write_text("""
mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"

provider: anthropic
agent_harness: claude-code
model: sonnet
""")

            # Create derived that changes args
            derived_path = Path(tmpdir) / "derived.yaml"
            derived_path.write_text("""
extends: ./base.yaml

mcp_server:
  args:
    - "different"
    - "args"
""")

            config = load_config(derived_path, warn_security=False)

            # Args should be completely replaced, not merged
            assert config.mcp_server.args == ["different", "args"]
            assert len(config.mcp_server.args) == 2
