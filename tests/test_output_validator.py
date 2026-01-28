"""Tests for output file validation."""

import json
import tempfile
from pathlib import Path

import yaml

from mcpbr.output_validator import validate_output_file


class TestOutputValidator:
    """Tests for output file validation."""

    def test_validate_valid_json_file(self) -> None:
        """Test validation of a valid JSON output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            data = {
                "metadata": {"timestamp": "2026-01-20T12:00:00Z"},
                "summary": {"mcp": {"resolved": 1, "total": 2}},
                "tasks": [
                    {"instance_id": "task-1", "mcp": {"resolved": True}},
                    {"instance_id": "task-2", "mcp": {"resolved": False}},
                ],
            }
            output_path.write_text(json.dumps(data))

            valid, msg = validate_output_file(output_path)

            assert valid is True
            assert "Valid JSON with 2 task(s)" in msg

    def test_validate_valid_yaml_file(self) -> None:
        """Test validation of a valid YAML output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yaml"
            data = {
                "metadata": {"timestamp": "2026-01-20T12:00:00Z"},
                "summary": {"mcp": {"resolved": 1, "total": 2}},
                "tasks": [
                    {"instance_id": "task-1", "mcp": {"resolved": True}},
                    {"instance_id": "task-2", "mcp": {"resolved": False}},
                ],
            }
            with open(output_path, "w") as f:
                yaml.dump(data, f)

            valid, msg = validate_output_file(output_path)

            assert valid is True
            assert "Valid YAML with 2 task(s)" in msg

    def test_validate_missing_file(self) -> None:
        """Test validation when output file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nonexistent.json"

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Output file not created" in msg
            assert str(output_path) in msg

    def test_validate_empty_file(self) -> None:
        """Test validation of an empty output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty.json"
            output_path.write_text("")

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Output file is empty" in msg

    def test_validate_invalid_json(self) -> None:
        """Test validation of a file with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "invalid.json"
            output_path.write_text("{ invalid json }")

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Invalid JSON" in msg

    def test_validate_invalid_yaml(self) -> None:
        """Test validation of a file with invalid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "invalid.yaml"
            output_path.write_text("invalid: yaml: content: [")

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Invalid YAML" in msg

    def test_validate_json_not_object(self) -> None:
        """Test validation when JSON is not an object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "array.json"
            output_path.write_text("[1, 2, 3]")

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Output must be a JSON object" in msg

    def test_validate_missing_tasks_field(self) -> None:
        """Test validation when 'tasks' field is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "no_tasks.json"
            data = {"metadata": {"timestamp": "2026-01-20"}}
            output_path.write_text(json.dumps(data))

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "Output missing 'tasks' field" in msg

    def test_validate_tasks_not_list(self) -> None:
        """Test validation when 'tasks' is not a list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tasks_not_list.json"
            data = {"tasks": "not a list"}
            output_path.write_text(json.dumps(data))

            valid, msg = validate_output_file(output_path)

            assert valid is False
            assert "'tasks' field must be a list" in msg

    def test_validate_empty_tasks_list(self) -> None:
        """Test validation with an empty tasks list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty_tasks.json"
            data = {"tasks": []}
            output_path.write_text(json.dumps(data))

            valid, msg = validate_output_file(output_path)

            assert valid is True
            assert "Valid JSON with 0 task(s)" in msg

    def test_validate_single_task(self) -> None:
        """Test validation with a single task."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "single_task.json"
            data = {"tasks": [{"instance_id": "task-1", "mcp": {"resolved": True}}]}
            output_path.write_text(json.dumps(data))

            valid, msg = validate_output_file(output_path)

            assert valid is True
            assert "Valid JSON with 1 task(s)" in msg

    def test_validate_yaml_with_yml_extension(self) -> None:
        """Test that .yml extension is recognized as YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.yml"
            data = {"tasks": [{"instance_id": "task-1"}]}
            with open(output_path, "w") as f:
                yaml.dump(data, f)

            valid, msg = validate_output_file(output_path)

            assert valid is True
            assert "Valid YAML" in msg

    def test_validate_handles_exceptions(self) -> None:
        """Test that unexpected exceptions are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "results.json"
            # Create a file with valid JSON but with permission issues
            output_path.write_text(json.dumps({"tasks": []}))

            # Make file unreadable (only works on Unix-like systems)
            import sys

            if sys.platform != "win32":
                output_path.chmod(0o000)

                valid, msg = validate_output_file(output_path)

                assert valid is False
                assert "Validation error" in msg

                # Restore permissions for cleanup
                output_path.chmod(0o644)
