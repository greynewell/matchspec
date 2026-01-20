"""Tests for CLI template commands."""

import tempfile
from pathlib import Path

import yaml
from click.testing import CliRunner

from mcpbr.cli import main
from mcpbr.templates import TEMPLATES


class TestInitCommand:
    """Tests for the init command with templates."""

    def test_init_default_creates_file(self) -> None:
        """Test that init creates a file with default template."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            result = runner.invoke(main, ["init", "-o", str(output_path)])

            assert result.exit_code == 0
            assert output_path.exists()
            assert "Created config at" in result.output

    def test_init_default_uses_filesystem_template(self) -> None:
        """Test that default init uses filesystem template."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            result = runner.invoke(main, ["init", "-o", str(output_path)])

            assert result.exit_code == 0

            # Read and parse the config
            content = output_path.read_text()
            assert "Filesystem Server (Basic)" in content

            # Parse YAML (skip header comments)
            lines = content.split("\n")
            yaml_lines = []
            in_header = True
            for line in lines:
                if in_header and line.strip() and not line.strip().startswith("#"):
                    in_header = False
                if not in_header:
                    yaml_lines.append(line)

            config = yaml.safe_load("\n".join(yaml_lines))
            assert config["mcp_server"]["command"] == "npx"
            assert "@modelcontextprotocol/server-filesystem" in config["mcp_server"]["args"]

    def test_init_with_specific_template(self) -> None:
        """Test init with a specific template."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            result = runner.invoke(main, ["init", "-o", str(output_path), "-t", "quick-test"])

            assert result.exit_code == 0
            assert output_path.exists()

            content = output_path.read_text()
            assert "Quick Test" in content

            # Parse and verify
            lines = content.split("\n")
            yaml_lines = []
            in_header = True
            for line in lines:
                if in_header and line.strip() and not line.strip().startswith("#"):
                    in_header = False
                if not in_header:
                    yaml_lines.append(line)

            config = yaml.safe_load("\n".join(yaml_lines))
            assert config["sample_size"] == 1
            assert config["max_concurrent"] == 1

    def test_init_with_cybergym_template(self) -> None:
        """Test init with CyberGym template."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            result = runner.invoke(
                main, ["init", "-o", str(output_path), "-t", "cybergym-basic"]
            )

            assert result.exit_code == 0

            content = output_path.read_text()
            assert "CyberGym" in content

            lines = content.split("\n")
            yaml_lines = []
            in_header = True
            for line in lines:
                if in_header and line.strip() and not line.strip().startswith("#"):
                    in_header = False
                if not in_header:
                    yaml_lines.append(line)

            config = yaml.safe_load("\n".join(yaml_lines))
            assert config["benchmark"] == "cybergym"
            assert "cybergym_level" in config

    def test_init_with_invalid_template(self) -> None:
        """Test init with invalid template ID."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            result = runner.invoke(
                main, ["init", "-o", str(output_path), "-t", "nonexistent-template"]
            )

            assert result.exit_code != 0
            assert not output_path.exists()
            assert "not found" in result.output

    def test_init_file_already_exists(self) -> None:
        """Test init fails when file already exists."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"
            output_path.write_text("existing content")

            result = runner.invoke(main, ["init", "-o", str(output_path)])

            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_init_list_templates_flag(self) -> None:
        """Test init --list-templates shows templates."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--list-templates"])

        assert result.exit_code == 0
        assert "Available Templates" in result.output
        assert "filesystem" in result.output
        assert "quick-test" in result.output

    def test_init_list_templates_short_flag(self) -> None:
        """Test init -l shows templates."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "-l"])

        assert result.exit_code == 0
        assert "Available Templates" in result.output


class TestTemplatesCommand:
    """Tests for the templates command."""

    def test_templates_lists_all(self) -> None:
        """Test templates command lists all templates."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates"])

        assert result.exit_code == 0
        assert "Available Configuration Templates" in result.output

        # Check for some known templates
        assert "filesystem" in result.output
        assert "quick-test" in result.output
        assert "production" in result.output

    def test_templates_shows_count(self) -> None:
        """Test templates command shows total count."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates"])

        assert result.exit_code == 0
        assert "template(s)" in result.output

    def test_templates_filter_by_category(self) -> None:
        """Test templates command with category filter."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates", "-c", "Testing"])

        assert result.exit_code == 0
        assert "Testing" in result.output
        assert "quick-test" in result.output

    def test_templates_filter_by_tag(self) -> None:
        """Test templates command with tag filter."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates", "--tag", "quick"])

        assert result.exit_code == 0
        assert "quick" in result.output

    def test_templates_filter_by_nonexistent_category(self) -> None:
        """Test templates command with nonexistent category."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates", "-c", "NonexistentCategory"])

        assert result.exit_code == 0
        assert "No templates found" in result.output

    def test_templates_filter_by_nonexistent_tag(self) -> None:
        """Test templates command with nonexistent tag."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates", "--tag", "nonexistent-tag-xyz"])

        assert result.exit_code == 0
        assert "No templates found" in result.output


class TestTemplateIntegration:
    """Integration tests for template workflow."""

    def test_full_workflow_list_and_init(self) -> None:
        """Test full workflow: list templates, then init with one."""
        runner = CliRunner()

        # First, list templates
        list_result = runner.invoke(main, ["templates"])
        assert list_result.exit_code == 0
        assert "filesystem" in list_result.output

        # Then, init with a template
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "config.yaml"

            init_result = runner.invoke(main, ["init", "-o", str(output_path), "-t", "filesystem"])

            assert init_result.exit_code == 0
            assert output_path.exists()

            # Verify the config is valid
            content = output_path.read_text()
            lines = content.split("\n")
            yaml_lines = []
            in_header = True
            for line in lines:
                if in_header and line.strip() and not line.strip().startswith("#"):
                    in_header = False
                if not in_header:
                    yaml_lines.append(line)

            config = yaml.safe_load("\n".join(yaml_lines))
            assert config is not None
            assert "mcp_server" in config

    def test_all_templates_create_valid_configs(self) -> None:
        """Test that all templates create valid, parseable configs."""
        runner = CliRunner()

        for template_id in TEMPLATES.keys():
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / f"{template_id}.yaml"

                result = runner.invoke(main, ["init", "-o", str(output_path), "-t", template_id])

                assert result.exit_code == 0, f"Failed to create config for {template_id}"
                assert output_path.exists(), f"Config file not created for {template_id}"

                # Verify the config is valid YAML
                content = output_path.read_text()
                lines = content.split("\n")
                yaml_lines = []
                in_header = True
                for line in lines:
                    if in_header and line.strip() and not line.strip().startswith("#"):
                        in_header = False
                    if not in_header:
                        yaml_lines.append(line)

                config = yaml.safe_load("\n".join(yaml_lines))
                assert config is not None, f"Invalid YAML for {template_id}"
                assert "mcp_server" in config, f"Missing mcp_server in {template_id}"
                assert "provider" in config, f"Missing provider in {template_id}"
                assert "model" in config, f"Missing model in {template_id}"


class TestTemplatesHelp:
    """Tests for help text and documentation."""

    def test_templates_command_help(self) -> None:
        """Test templates command help text."""
        runner = CliRunner()

        result = runner.invoke(main, ["templates", "--help"])

        assert result.exit_code == 0
        assert "List available configuration templates" in result.output

    def test_init_command_help_mentions_templates(self) -> None:
        """Test init command help mentions templates."""
        runner = CliRunner()

        result = runner.invoke(main, ["init", "--help"])

        assert result.exit_code == 0
        assert "template" in result.output.lower()
        assert "-t" in result.output or "--template" in result.output

    def test_main_help_lists_templates_command(self) -> None:
        """Test main help lists templates command."""
        runner = CliRunner()

        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "templates" in result.output
        assert "List available configuration templates" in result.output or "templates" in result.output
