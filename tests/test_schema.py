"""Tests for JSON Schema generation and validation."""

import json
import tempfile
from pathlib import Path

from mcpbr.schema import (
    add_schema_comment,
    generate_json_schema,
    generate_schema_docs,
    get_schema_for_yaml_ls,
    get_schema_url,
    print_schema_info,
    save_schema,
    validate_against_schema,
)


class TestGenerateJsonSchema:
    """Tests for generate_json_schema function."""

    def test_generates_valid_json_schema(self) -> None:
        """Test that generated schema is valid JSON Schema."""
        schema = generate_json_schema()

        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_has_metadata(self) -> None:
        """Test that schema includes required metadata."""
        schema = generate_json_schema()

        assert "$id" in schema
        assert "title" in schema
        assert "description" in schema
        assert "mcpbr" in schema["title"].lower()

    def test_schema_has_properties(self) -> None:
        """Test that schema includes configuration properties."""
        schema = generate_json_schema()

        assert "properties" in schema
        properties = schema["properties"]

        # Check for required top-level properties
        assert "mcp_server" in properties
        assert "provider" in properties
        assert "agent_harness" in properties
        assert "model" in properties
        assert "benchmark" in properties

    def test_schema_has_mcp_server_properties(self) -> None:
        """Test that mcp_server has required nested properties."""
        schema = generate_json_schema()

        mcp_server = schema["properties"]["mcp_server"]
        # Check direct structure
        if "properties" in mcp_server or "allOf" in mcp_server or "$ref" in mcp_server:
            assert True
        # Check anyOf structure (for Optional fields in Pydantic)
        elif "anyOf" in mcp_server:
            # Find the non-null option in anyOf
            refs = [opt for opt in mcp_server["anyOf"] if "$ref" in opt or "properties" in opt]
            assert len(refs) > 0, "mcp_server anyOf should contain $ref or properties"
        else:
            assert False, f"mcp_server has unexpected structure: {mcp_server.keys()}"

    def test_schema_has_examples(self) -> None:
        """Test that schema includes example configurations."""
        schema = generate_json_schema()

        assert "examples" in schema
        assert len(schema["examples"]) > 0
        assert isinstance(schema["examples"][0], dict)

    def test_schema_url_is_correct(self) -> None:
        """Test that schema $id points to correct URL."""
        schema = generate_json_schema()

        assert "greynewell.github.io" in schema["$id"]
        assert "mcpbr" in schema["$id"]
        assert schema["$id"].endswith(".json")


class TestSaveSchema:
    """Tests for save_schema function."""

    def test_saves_schema_to_file(self) -> None:
        """Test that schema is saved correctly to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "schema.json"
            save_schema(output_path)

            assert output_path.exists()
            assert output_path.is_file()

    def test_saved_schema_is_valid_json(self) -> None:
        """Test that saved schema is valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "schema.json"
            save_schema(output_path)

            with open(output_path) as f:
                data = json.load(f)

            assert isinstance(data, dict)
            assert "$schema" in data

    def test_creates_parent_directories(self) -> None:
        """Test that parent directories are created if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "schema.json"
            save_schema(output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_overwrites_existing_file(self) -> None:
        """Test that existing file is overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "schema.json"

            # Create initial file
            output_path.write_text("old content")

            # Save schema
            save_schema(output_path)

            # Check new content
            content = output_path.read_text()
            assert "old content" not in content
            assert "$schema" in content


class TestGetSchemaUrl:
    """Tests for get_schema_url function."""

    def test_returns_valid_url(self) -> None:
        """Test that URL is valid and accessible."""
        url = get_schema_url()

        assert url.startswith("https://")
        assert "greynewell.github.io" in url
        assert url.endswith(".json")

    def test_url_is_consistent(self) -> None:
        """Test that URL is consistent across calls."""
        url1 = get_schema_url()
        url2 = get_schema_url()

        assert url1 == url2


class TestAddSchemaComment:
    """Tests for add_schema_comment function."""

    def test_adds_schema_comment_to_yaml(self) -> None:
        """Test that schema comment is added to YAML."""
        yaml_content = """
mcp_server:
  command: npx
  args:
    - test
"""
        result = add_schema_comment(yaml_content)

        assert "yaml-language-server" in result
        assert "$schema=" in result
        assert yaml_content.strip() in result

    def test_preserves_existing_content(self) -> None:
        """Test that existing content is preserved."""
        yaml_content = """# This is a comment
mcp_server:
  command: npx
"""
        result = add_schema_comment(yaml_content)

        assert "# This is a comment" in result
        assert "mcp_server:" in result
        assert "command: npx" in result

    def test_does_not_duplicate_comment(self) -> None:
        """Test that comment is not added if already present."""
        yaml_content = """# yaml-language-server: $schema=https://example.com/schema.json

mcp_server:
  command: npx
"""
        result = add_schema_comment(yaml_content)

        # Should return unchanged
        assert result == yaml_content

    def test_comment_is_at_top(self) -> None:
        """Test that comment is added at the very top."""
        yaml_content = """mcp_server:
  command: npx
"""
        result = add_schema_comment(yaml_content)

        lines = result.split("\n")
        assert "yaml-language-server" in lines[0]


class TestValidateAgainstSchema:
    """Tests for validate_against_schema function."""

    def test_validates_correct_config(self) -> None:
        """Test that valid config passes validation."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "test"],
            },
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "model": "claude-sonnet-4-5-20250514",
        }

        is_valid, errors = validate_against_schema(config)
        assert is_valid
        assert len(errors) == 0

    def test_rejects_invalid_provider(self) -> None:
        """Test that invalid provider is rejected."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "test"],
            },
            "provider": "invalid-provider",
        }

        is_valid, errors = validate_against_schema(config)
        assert not is_valid
        assert len(errors) > 0

    def test_rejects_missing_required_field(self) -> None:
        """Test that missing required field is rejected."""
        config = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-5-20250514",
        }

        is_valid, errors = validate_against_schema(config)
        assert not is_valid
        assert len(errors) > 0

    def test_rejects_invalid_type(self) -> None:
        """Test that wrong type is rejected."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "test"],
            },
            "provider": "anthropic",
            "timeout_seconds": "not-a-number",
        }

        is_valid, errors = validate_against_schema(config)
        assert not is_valid
        assert len(errors) > 0

    def test_accepts_optional_fields(self) -> None:
        """Test that optional fields are accepted."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "test"],
            },
            "provider": "anthropic",
            "sample_size": 10,
            "timeout_seconds": 600,
            "max_concurrent": 8,
        }

        is_valid, errors = validate_against_schema(config)
        assert is_valid
        assert len(errors) == 0


class TestGetSchemaForYamlLs:
    """Tests for get_schema_for_yaml_ls function."""

    def test_returns_valid_schema(self) -> None:
        """Test that YAML-LS schema is valid."""
        schema = get_schema_for_yaml_ls()

        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "properties" in schema

    def test_includes_yaml_ls_enhancements(self) -> None:
        """Test that schema includes YAML-LS specific enhancements."""
        schema = get_schema_for_yaml_ls()

        # Should have same basic structure as regular schema
        assert "mcp_server" in schema["properties"]


class TestGenerateSchemaDocs:
    """Tests for generate_schema_docs function."""

    def test_generates_markdown_docs(self) -> None:
        """Test that Markdown documentation is generated."""
        docs = generate_schema_docs()

        assert isinstance(docs, str)
        assert len(docs) > 0

    def test_docs_include_title(self) -> None:
        """Test that docs include a title."""
        docs = generate_schema_docs()

        assert "# Configuration Schema" in docs or "Configuration" in docs

    def test_docs_include_properties(self) -> None:
        """Test that docs describe properties."""
        docs = generate_schema_docs()

        # Should mention key properties
        assert "mcp_server" in docs
        assert "provider" in docs

    def test_docs_include_schema_url(self) -> None:
        """Test that docs include schema URL."""
        docs = generate_schema_docs()

        url = get_schema_url()
        assert url in docs

    def test_docs_show_required_fields(self) -> None:
        """Test that docs indicate required fields."""
        docs = generate_schema_docs()

        # Should indicate which fields are required
        assert "required" in docs.lower() or "optional" in docs.lower()


class TestPrintSchemaInfo:
    """Tests for print_schema_info function."""

    def test_returns_readable_summary(self) -> None:
        """Test that summary is readable."""
        info = print_schema_info()

        assert isinstance(info, str)
        assert len(info) > 0

    def test_includes_schema_url(self) -> None:
        """Test that summary includes schema URL."""
        info = print_schema_info()

        url = get_schema_url()
        assert url in info

    def test_lists_properties(self) -> None:
        """Test that summary lists properties."""
        info = print_schema_info()

        assert "mcp_server" in info
        assert "provider" in info

    def test_indicates_required_fields(self) -> None:
        """Test that summary indicates required fields."""
        info = print_schema_info()

        assert "required" in info.lower() or "optional" in info.lower()


class TestSchemaIntegration:
    """Integration tests for schema functionality."""

    def test_schema_validates_example_config(self) -> None:
        """Test that schema validates its own examples."""
        schema = generate_json_schema()

        examples = schema.get("examples", [])
        assert len(examples) > 0

        # Validate first example
        example = examples[0]
        is_valid, errors = validate_against_schema(example)
        assert is_valid, f"Schema example is invalid: {errors}"

    def test_saved_schema_can_be_loaded(self) -> None:
        """Test that saved schema can be loaded and used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "schema.json"
            save_schema(output_path)

            # Load schema
            with open(output_path) as f:
                loaded_schema = json.load(f)

            # Verify it's the same
            original_schema = generate_json_schema()
            assert loaded_schema["$schema"] == original_schema["$schema"]
            assert loaded_schema["$id"] == original_schema["$id"]

    def test_annotated_yaml_includes_correct_url(self) -> None:
        """Test that annotated YAML has correct schema URL."""
        yaml_content = "mcp_server:\n  command: test\n"
        annotated = add_schema_comment(yaml_content)

        url = get_schema_url()
        assert url in annotated

    def test_schema_round_trip(self) -> None:
        """Test schema generation, save, load, and validate cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate and save
            output_path = Path(tmpdir) / "schema.json"
            save_schema(output_path)

            # Load
            with open(output_path) as f:
                loaded = json.load(f)

            # Validate an example against loaded schema
            example = loaded["examples"][0]
            is_valid, errors = validate_against_schema(example)
            assert is_valid
