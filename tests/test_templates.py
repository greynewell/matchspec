"""Tests for MCP server configuration templates."""

import tempfile
from pathlib import Path

import pytest
import yaml

from mcpbr.templates import (
    MCPTemplate,
    apply_template,
    get_template,
    list_templates,
    load_template_from_yaml,
    register_template,
    validate_template,
)


class TestMCPTemplate:
    """Tests for MCPTemplate model."""

    def test_basic_creation(self) -> None:
        """Test basic template creation."""
        template = MCPTemplate(
            id="test",
            name="Test Template",
            description="A test template",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                }
            },
        )
        assert template.id == "test"
        assert template.name == "Test Template"
        assert template.description == "A test template"
        assert not template.requires_api_key
        assert template.env_vars == []

    def test_template_with_api_key(self) -> None:
        """Test template with API key requirement."""
        template = MCPTemplate(
            id="test",
            name="Test",
            description="Test",
            requires_api_key=True,
            env_vars=["TEST_API_KEY"],
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                    "env": {"TEST_API_KEY": "${TEST_API_KEY}"},
                }
            },
        )
        assert template.requires_api_key
        assert "TEST_API_KEY" in template.env_vars


class TestTemplateRegistry:
    """Tests for template registry functions."""

    def test_register_and_get_template(self) -> None:
        """Test registering and retrieving a template."""
        template = MCPTemplate(
            id="test-registry",
            name="Test",
            description="Test",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test"],
                }
            },
        )
        register_template(template)

        retrieved = get_template("test-registry")
        assert retrieved is not None
        assert retrieved.id == "test-registry"

    def test_get_nonexistent_template(self) -> None:
        """Test getting a template that doesn't exist."""
        template = get_template("nonexistent-template-xyz")
        assert template is None

    def test_list_templates(self) -> None:
        """Test listing all templates."""
        templates = list_templates()
        assert isinstance(templates, list)
        # Should include built-in templates
        assert len(templates) > 0

    def test_builtin_templates_exist(self) -> None:
        """Test that built-in templates are loaded."""
        templates = list_templates()
        template_ids = {t.id for t in templates}

        # Check for expected built-in templates
        expected_templates = {
            "filesystem",
            "brave-search",
            "postgres",
            "sqlite",
            "github",
        }
        for expected in expected_templates:
            assert expected in template_ids, f"Template {expected} not found"


class TestLoadTemplateFromYaml:
    """Tests for loading templates from YAML files."""

    def test_load_valid_template(self) -> None:
        """Test loading a valid template from YAML."""
        yaml_content = """
id: test-yaml
name: Test YAML Template
description: A template loaded from YAML
package: "@test/package"
requires_api_key: false
env_vars: []
config:
  mcp_server:
    command: npx
    args:
      - "-y"
      - "@test/package"
  provider: anthropic
  model: sonnet
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            template = load_template_from_yaml(temp_path)
            assert template.id == "test-yaml"
            assert template.name == "Test YAML Template"
            assert template.package == "@test/package"
            assert "mcp_server" in template.config
        finally:
            temp_path.unlink()

    def test_load_nonexistent_file(self) -> None:
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_template_from_yaml(Path("/nonexistent/template.yaml"))

    def test_load_invalid_yaml(self) -> None:
        """Test loading invalid YAML raises error."""
        yaml_content = "not: a: valid: template:"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with pytest.raises(Exception):
                load_template_from_yaml(temp_path)
        finally:
            temp_path.unlink()


class TestApplyTemplate:
    """Tests for applying templates to create config files."""

    def test_apply_basic_template(self) -> None:
        """Test applying a basic template."""
        template = MCPTemplate(
            id="test-apply",
            name="Test Apply",
            description="Test template application",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                    "env": {},
                },
                "provider": "anthropic",
                "model": "sonnet",
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"
            apply_template(template, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify content
            with open(output_path) as f:
                config = yaml.safe_load(f)

            assert "mcp_server" in config
            assert config["mcp_server"]["command"] == "npx"
            assert config["provider"] == "anthropic"

    def test_apply_template_with_overrides(self) -> None:
        """Test applying template with configuration overrides."""
        template = MCPTemplate(
            id="test-override",
            name="Test Override",
            description="Test overrides",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test"],
                },
                "model": "sonnet",
                "sample_size": 10,
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"
            overrides = {"sample_size": 20, "timeout_seconds": 600}
            apply_template(template, output_path, overrides)

            with open(output_path) as f:
                config = yaml.safe_load(f)

            assert config["sample_size"] == 20
            assert config["timeout_seconds"] == 600

    def test_apply_template_file_exists(self) -> None:
        """Test that applying to existing file raises error."""
        template = MCPTemplate(
            id="test-exists",
            name="Test",
            description="Test",
            config={"mcp_server": {"command": "npx", "args": []}},
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            temp_path = Path(f.name)

        try:
            with pytest.raises(FileExistsError):
                apply_template(template, temp_path)
        finally:
            temp_path.unlink()


class TestValidateTemplate:
    """Tests for template validation."""

    def test_validate_valid_template(self) -> None:
        """Test validation of a valid template."""
        template = MCPTemplate(
            id="valid-test",
            name="Valid Template",
            description="A valid template",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": ["-y", "test-server"],
                }
            },
        )

        errors = validate_template(template)
        assert len(errors) == 0

    def test_validate_missing_id(self) -> None:
        """Test validation fails for missing id."""
        template = MCPTemplate(
            id="",
            name="Test",
            description="Test",
            config={
                "mcp_server": {
                    "command": "npx",
                    "args": [],
                }
            },
        )

        errors = validate_template(template)
        assert any("id" in error.lower() for error in errors)

    def test_validate_missing_mcp_server(self) -> None:
        """Test validation fails for missing mcp_server."""
        template = MCPTemplate(
            id="test",
            name="Test",
            description="Test",
            config={"provider": "anthropic"},
        )

        errors = validate_template(template)
        assert any("mcp_server" in error for error in errors)

    def test_validate_missing_command(self) -> None:
        """Test validation fails for missing command."""
        template = MCPTemplate(
            id="test",
            name="Test",
            description="Test",
            config={"mcp_server": {"args": []}},
        )

        errors = validate_template(template)
        assert any("command" in error for error in errors)

    def test_validate_missing_args(self) -> None:
        """Test validation fails for missing args."""
        template = MCPTemplate(
            id="test",
            name="Test",
            description="Test",
            config={"mcp_server": {"command": "npx"}},
        )

        errors = validate_template(template)
        assert any("args" in error for error in errors)


class TestBuiltinTemplates:
    """Tests for built-in templates."""

    def test_filesystem_template(self) -> None:
        """Test filesystem template is valid."""
        template = get_template("filesystem")
        assert template is not None
        assert template.id == "filesystem"
        assert template.name == "Filesystem Server"
        assert not template.requires_api_key
        assert len(template.env_vars) == 0

        # Validate structure
        errors = validate_template(template)
        assert len(errors) == 0

    def test_brave_search_template(self) -> None:
        """Test Brave Search template is valid."""
        template = get_template("brave-search")
        assert template is not None
        assert template.id == "brave-search"
        assert template.requires_api_key
        assert "BRAVE_API_KEY" in template.env_vars

        # Validate structure
        errors = validate_template(template)
        assert len(errors) == 0

    def test_postgres_template(self) -> None:
        """Test PostgreSQL template is valid."""
        template = get_template("postgres")
        assert template is not None
        assert template.id == "postgres"
        assert "POSTGRES_CONNECTION_STRING" in template.env_vars

        # Validate structure
        errors = validate_template(template)
        assert len(errors) == 0

    def test_sqlite_template(self) -> None:
        """Test SQLite template is valid."""
        template = get_template("sqlite")
        assert template is not None
        assert template.id == "sqlite"
        assert not template.requires_api_key

        # Validate structure
        errors = validate_template(template)
        assert len(errors) == 0

    def test_github_template(self) -> None:
        """Test GitHub template is valid."""
        template = get_template("github")
        assert template is not None
        assert template.id == "github"
        assert template.requires_api_key
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in template.env_vars

        # Validate structure
        errors = validate_template(template)
        assert len(errors) == 0

    def test_all_builtin_templates_valid(self) -> None:
        """Test that all built-in templates are valid."""
        templates = list_templates()
        assert len(templates) > 0

        for template in templates:
            errors = validate_template(template)
            assert (
                len(errors) == 0
            ), f"Template {template.id} has validation errors: {errors}"

    def test_builtin_templates_have_required_fields(self) -> None:
        """Test that all built-in templates have required config fields."""
        # Only test known built-in templates
        builtin_ids = [
            "filesystem",
            "brave-search",
            "postgres",
            "sqlite",
            "github",
            "google-maps",
            "slack",
        ]

        for template_id in builtin_ids:
            template = get_template(template_id)
            if template is None:
                continue

            # Check MCP server config
            assert "mcp_server" in template.config
            mcp = template.config["mcp_server"]
            assert "command" in mcp
            assert "args" in mcp

            # Check common fields
            assert "provider" in template.config
            assert "agent_harness" in template.config
            assert "model" in template.config


class TestTemplateIntegration:
    """Integration tests for template system."""

    def test_load_apply_and_load_config(self) -> None:
        """Test full workflow: load template, apply it, load config."""
        from mcpbr.config import load_config

        template = get_template("filesystem")
        assert template is not None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            apply_template(template, config_path)

            # Load the generated config
            config = load_config(config_path)

            # Verify it's valid
            assert config.mcp_server.command == "npx"
            assert config.provider == "anthropic"
            assert config.agent_harness == "claude-code"

    def test_template_with_workdir_placeholder(self) -> None:
        """Test that templates with {workdir} work correctly."""
        template = get_template("filesystem")
        assert template is not None

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yaml"
            apply_template(template, config_path)

            # Load and test workdir substitution
            from mcpbr.config import load_config

            config = load_config(config_path)
            args = config.mcp_server.get_args_for_workdir("/test/path")
            assert "/test/path" in args
