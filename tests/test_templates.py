"""Tests for configuration templates."""

import yaml

from mcpbr.templates import (
    TEMPLATES,
    Template,
    generate_config_yaml,
    get_template,
    get_templates_by_category,
    get_templates_by_tag,
    list_templates,
)


class TestTemplate:
    """Tests for Template dataclass."""

    def test_template_creation(self) -> None:
        """Test creating a template."""
        template = Template(
            id="test",
            name="Test Template",
            description="A test template",
            category="Testing",
            config={"model": "test-model"},
            tags=["test"],
        )

        assert template.id == "test"
        assert template.name == "Test Template"
        assert template.description == "A test template"
        assert template.category == "Testing"
        assert template.config == {"model": "test-model"}
        assert template.tags == ["test"]


class TestListTemplates:
    """Tests for list_templates function."""

    def test_list_returns_all_templates(self) -> None:
        """Test that list_templates returns all templates."""
        templates = list_templates()
        assert len(templates) == len(TEMPLATES)

    def test_list_is_sorted(self) -> None:
        """Test that templates are sorted by category and name."""
        templates = list_templates()
        # Verify sorting
        for i in range(len(templates) - 1):
            curr = templates[i]
            next_t = templates[i + 1]
            assert (curr.category, curr.name) <= (next_t.category, next_t.name)

    def test_list_includes_expected_templates(self) -> None:
        """Test that common templates are included."""
        templates = list_templates()
        template_ids = [t.id for t in templates]

        assert "filesystem" in template_ids
        assert "quick-test" in template_ids
        assert "production" in template_ids


class TestGetTemplate:
    """Tests for get_template function."""

    def test_get_existing_template(self) -> None:
        """Test getting an existing template."""
        template = get_template("filesystem")
        assert template is not None
        assert template.id == "filesystem"
        assert template.name == "Filesystem Server (Basic)"

    def test_get_nonexistent_template(self) -> None:
        """Test getting a nonexistent template returns None."""
        template = get_template("nonexistent")
        assert template is None

    def test_get_all_templates(self) -> None:
        """Test getting each template by ID."""
        for template_id in TEMPLATES.keys():
            template = get_template(template_id)
            assert template is not None
            assert template.id == template_id


class TestGetTemplatesByCategory:
    """Tests for get_templates_by_category function."""

    def test_returns_dict(self) -> None:
        """Test that function returns a dictionary."""
        result = get_templates_by_category()
        assert isinstance(result, dict)

    def test_all_templates_included(self) -> None:
        """Test that all templates are included in the result."""
        result = get_templates_by_category()
        total = sum(len(templates) for templates in result.values())
        assert total == len(TEMPLATES)

    def test_categories_are_correct(self) -> None:
        """Test that templates are in the right categories."""
        result = get_templates_by_category()

        for category, templates in result.items():
            for template in templates:
                assert template.category == category

    def test_expected_categories_exist(self) -> None:
        """Test that expected categories exist."""
        result = get_templates_by_category()

        assert "File Operations" in result
        assert "Testing" in result
        assert "Custom" in result


class TestGetTemplatesByTag:
    """Tests for get_templates_by_tag function."""

    def test_filter_by_tag(self) -> None:
        """Test filtering templates by tag."""
        templates = get_templates_by_tag("basic")
        assert len(templates) > 0
        for template in templates:
            assert "basic" in template.tags

    def test_filter_by_nonexistent_tag(self) -> None:
        """Test filtering by nonexistent tag returns empty list."""
        templates = get_templates_by_tag("nonexistent-tag-xyz")
        assert len(templates) == 0

    def test_filter_by_recommended(self) -> None:
        """Test filtering by recommended tag."""
        templates = get_templates_by_tag("recommended")
        assert len(templates) > 0
        # Check filesystem is recommended
        filesystem_found = any(t.id == "filesystem" for t in templates)
        assert filesystem_found

    def test_filter_by_quick(self) -> None:
        """Test filtering by quick tag."""
        templates = get_templates_by_tag("quick")
        assert len(templates) > 0
        # Quick-test should be in quick templates
        quick_test_found = any(t.id == "quick-test" for t in templates)
        assert quick_test_found


class TestGenerateConfigYaml:
    """Tests for generate_config_yaml function."""

    def test_generate_basic_yaml(self) -> None:
        """Test generating YAML from a template."""
        template = get_template("filesystem")
        assert template is not None

        yaml_str = generate_config_yaml(template)

        # Check that it's valid YAML
        assert yaml_str is not None
        assert len(yaml_str) > 0

        # Check for key sections
        assert "mcp_server:" in yaml_str
        assert "provider:" in yaml_str
        assert "model:" in yaml_str

    def test_yaml_is_valid(self) -> None:
        """Test that generated YAML can be parsed."""
        template = get_template("filesystem")
        assert template is not None

        yaml_str = generate_config_yaml(template)

        # Extract YAML content (skip comments at the top)
        lines = yaml_str.split("\n")
        yaml_content_lines = []
        in_header = True
        for line in lines:
            if in_header and line.strip() and not line.strip().startswith("#"):
                in_header = False
            if not in_header:
                yaml_content_lines.append(line)

        yaml_content = "\n".join(yaml_content_lines)

        # Parse YAML
        config = yaml.safe_load(yaml_content)
        assert isinstance(config, dict)
        assert "mcp_server" in config
        assert "provider" in config
        assert "model" in config

    def test_yaml_contains_template_info(self) -> None:
        """Test that generated YAML contains template metadata."""
        template = get_template("filesystem")
        assert template is not None

        yaml_str = generate_config_yaml(template)

        # Check for template name and description in comments
        assert template.name in yaml_str
        assert template.description in yaml_str

    def test_custom_values_override(self) -> None:
        """Test that custom values override template defaults."""
        template = get_template("filesystem")
        assert template is not None

        custom_values = {
            "sample_size": 50,
            "timeout_seconds": 600,
        }

        yaml_str = generate_config_yaml(template, custom_values)

        # Parse YAML to check values
        lines = yaml_str.split("\n")
        yaml_content_lines = []
        in_header = True
        for line in lines:
            if in_header and line.strip() and not line.strip().startswith("#"):
                in_header = False
            if not in_header:
                yaml_content_lines.append(line)

        yaml_content = "\n".join(yaml_content_lines)
        config = yaml.safe_load(yaml_content)

        assert config["sample_size"] == 50
        assert config["timeout_seconds"] == 600

    def test_all_templates_generate_valid_yaml(self) -> None:
        """Test that all templates can generate valid YAML."""
        for template_id in TEMPLATES.keys():
            template = get_template(template_id)
            assert template is not None

            yaml_str = generate_config_yaml(template)
            assert yaml_str is not None
            assert len(yaml_str) > 0

            # Verify it contains expected content
            assert "mcp_server:" in yaml_str
            assert template.name in yaml_str


class TestTemplateContent:
    """Tests for specific template content."""

    def test_filesystem_template(self) -> None:
        """Test the filesystem template has correct structure."""
        template = get_template("filesystem")
        assert template is not None

        assert template.category == "File Operations"
        assert "filesystem" in template.tags
        assert template.config["mcp_server"]["command"] == "npx"
        assert template.config["benchmark"] == "swe-bench"

    def test_cybergym_templates(self) -> None:
        """Test CyberGym templates have correct benchmark."""
        for template_id in ["cybergym-basic", "cybergym-advanced"]:
            template = get_template(template_id)
            assert template is not None
            assert template.config["benchmark"] == "cybergym"
            assert "cybergym_level" in template.config
            assert "security" in template.tags

    def test_quick_test_template(self) -> None:
        """Test quick-test template has minimal settings."""
        template = get_template("quick-test")
        assert template is not None

        assert template.config["sample_size"] == 1
        assert template.config["max_concurrent"] == 1
        assert "quick" in template.tags

    def test_production_template(self) -> None:
        """Test production template has optimal settings."""
        template = get_template("production")
        assert template is not None

        assert template.config["sample_size"] is None  # Full dataset
        assert template.config["max_concurrent"] >= 4
        assert template.config["timeout_seconds"] >= 600
        assert "production" in template.tags

    def test_custom_templates_have_placeholders(self) -> None:
        """Test custom templates contain placeholders for user to fill."""
        custom_templates = ["custom-python", "custom-node"]

        for template_id in custom_templates:
            template = get_template(template_id)
            assert template is not None
            assert "custom" in template.tags

            # Verify command is set to appropriate runtime
            if template_id == "custom-python":
                assert template.config["mcp_server"]["command"] == "python"
            elif template_id == "custom-node":
                assert template.config["mcp_server"]["command"] == "node"


class TestTemplateValidation:
    """Tests to ensure templates produce valid configurations."""

    def test_all_templates_have_required_fields(self) -> None:
        """Test that all templates have required configuration fields."""
        required_fields = [
            "mcp_server",
            "provider",
            "agent_harness",
            "model",
            "benchmark",
        ]

        for template_id, template in TEMPLATES.items():
            for field in required_fields:
                assert field in template.config, f"Template {template_id} missing {field}"

    def test_all_mcp_servers_have_command(self) -> None:
        """Test that all MCP server configs have a command."""
        for template_id, template in TEMPLATES.items():
            mcp_config = template.config["mcp_server"]
            assert "command" in mcp_config, f"Template {template_id} missing command"
            assert mcp_config["command"], f"Template {template_id} has empty command"

    def test_benchmark_values_are_valid(self) -> None:
        """Test that benchmark values are valid."""
        from mcpbr.config import VALID_BENCHMARKS

        for template_id, template in TEMPLATES.items():
            benchmark = template.config["benchmark"]
            assert (
                benchmark in VALID_BENCHMARKS
            ), f"Template {template_id} has invalid benchmark: {benchmark}"

    def test_cybergym_templates_have_level(self) -> None:
        """Test that CyberGym templates have cybergym_level."""
        for template_id, template in TEMPLATES.items():
            if template.config["benchmark"] == "cybergym":
                assert (
                    "cybergym_level" in template.config
                ), f"CyberGym template {template_id} missing cybergym_level"
                level = template.config["cybergym_level"]
                assert 0 <= level <= 3, f"Template {template_id} has invalid level: {level}"

    def test_template_ids_match_keys(self) -> None:
        """Test that template IDs match their dictionary keys."""
        for key, template in TEMPLATES.items():
            assert template.id == key, f"Template key {key} doesn't match ID {template.id}"

    def test_all_templates_have_metadata(self) -> None:
        """Test that all templates have complete metadata."""
        for template_id, template in TEMPLATES.items():
            assert template.name, f"Template {template_id} missing name"
            assert template.description, f"Template {template_id} missing description"
            assert template.category, f"Template {template_id} missing category"
            assert template.tags, f"Template {template_id} missing tags"
            assert len(template.tags) > 0, f"Template {template_id} has empty tags"
