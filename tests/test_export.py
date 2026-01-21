"""Tests for the export CLI command."""

import csv
import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from mcpbr.cli import main


class TestExportCommand:
    """Tests for the export command."""

    @pytest.fixture
    def sample_results_json(self) -> dict:
        """Create sample evaluation results JSON."""
        return {
            "metadata": {
                "timestamp": "2026-01-20T12:00:00Z",
                "config": {"model": "claude-sonnet-4-5-20250929"},
            },
            "summary": {
                "mcp": {"resolved": 1, "total": 2, "rate": 0.5},
                "baseline": {"resolved": 0, "total": 2, "rate": 0.0},
            },
            "tasks": [
                {
                    "instance_id": "task-1",
                    "mcp": {"resolved": True, "tokens": 100},
                    "baseline": {"resolved": False, "tokens": 50},
                },
                {
                    "instance_id": "task-2",
                    "mcp": {"resolved": False, "tokens": 80},
                    "baseline": {"resolved": False, "tokens": 40},
                },
            ],
        }

    def test_export_csv_basic(self, sample_results_json: dict) -> None:
        """Test basic CSV export functionality."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(sample_results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert output_path.exists()
            assert "Exported 2 rows" in result.output

    def test_export_csv_content(self, sample_results_json: dict) -> None:
        """Test that CSV contains correct data."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(sample_results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["instance_id"] == "task-1"
            assert rows[1]["instance_id"] == "task-2"

    def test_export_csv_creates_parent_directories(self, sample_results_json: dict) -> None:
        """Test that parent directories are created if they don't exist."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "subdir" / "nested" / "results.csv"

            input_path.write_text(json.dumps(sample_results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert output_path.exists()
            assert output_path.parent.exists()

    def test_export_csv_handles_different_keys_per_row(self) -> None:
        """Test CSV export with tasks that have different keys."""
        runner = CliRunner()

        results_json = {
            "tasks": [
                {"instance_id": "task-1", "mcp_resolved": True},
                {"instance_id": "task-2", "baseline_resolved": True},
                {"instance_id": "task-3", "mcp_resolved": False, "baseline_resolved": False},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)

            assert fieldnames is not None
            assert "instance_id" in fieldnames
            assert "mcp_resolved" in fieldnames
            assert "baseline_resolved" in fieldnames

            assert len(rows) == 3
            assert rows[0]["mcp_resolved"] == "True"
            assert rows[0]["baseline_resolved"] == ""
            assert rows[1]["mcp_resolved"] == ""
            assert rows[1]["baseline_resolved"] == "True"

    def test_export_csv_fieldnames_sorted(self, sample_results_json: dict) -> None:
        """Test that CSV fieldnames are sorted alphabetically."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(sample_results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

            assert fieldnames is not None
            assert fieldnames == sorted(fieldnames)

    def test_export_csv_empty_tasks(self) -> None:
        """Test export with empty tasks list."""
        runner = CliRunner()

        results_json = {"tasks": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert "No rows to export" in result.output
            assert not output_path.exists()

    def test_export_csv_no_tasks_key(self) -> None:
        """Test export when JSON has no tasks key."""
        runner = CliRunner()

        results_json = {"metadata": {"timestamp": "2026-01-20"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert "No rows to export" in result.output

    def test_export_csv_tasks_not_list(self) -> None:
        """Test export when tasks is not a list."""
        runner = CliRunner()

        results_json = {"tasks": "not a list"}

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 1
            assert "Expected 'tasks' to be a list" in result.output

    def test_export_csv_invalid_json(self) -> None:
        """Test export with invalid JSON file."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text("{ invalid json }")

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 1
            assert "Failed to read JSON" in result.output

    def test_export_csv_nonexistent_input(self) -> None:
        """Test export with non-existent input file."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "nonexistent.json"
            output_path = Path(tmpdir) / "results.csv"

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code != 0

    def test_export_csv_filters_non_dict_tasks(self) -> None:
        """Test that non-dict items in tasks are filtered out."""
        runner = CliRunner()

        results_json = {
            "tasks": [
                {"instance_id": "task-1", "score": 0.8},
                "not a dict",
                {"instance_id": "task-2", "score": 0.9},
                None,
                123,
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert "Exported 2 rows" in result.output

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["instance_id"] == "task-1"
            assert rows[1]["instance_id"] == "task-2"

    def test_export_csv_handles_unicode(self) -> None:
        """Test that CSV export properly handles Unicode characters."""
        runner = CliRunner()

        results_json = {
            "tasks": [
                {"instance_id": "task-1", "description": "Test with unicode"},
                {"instance_id": "task-2", "description": "Chinese characters"},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json, ensure_ascii=False), encoding="utf-8")

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert rows[0]["description"] == "Test with unicode"
            assert rows[1]["description"] == "Chinese characters"

    def test_export_csv_handles_nested_values(self) -> None:
        """Test that CSV export handles nested dict/list values."""
        runner = CliRunner()

        results_json = {
            "tasks": [
                {
                    "instance_id": "task-1",
                    "mcp": {"resolved": True, "tokens": 100},
                    "tags": ["bug", "feature"],
                },
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0

            with open(output_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert "mcp" in reader.fieldnames
            assert "tags" in reader.fieldnames

    def test_export_requires_format_option(self) -> None:
        """Test that --format option is required."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text("{}")

            result = runner.invoke(main, ["export", str(input_path), "-o", str(output_path)])

            assert result.exit_code != 0
            assert "Missing option" in result.output or "required" in result.output.lower()

    def test_export_requires_output_option(self) -> None:
        """Test that --output option is required."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"

            input_path.write_text("{}")

            result = runner.invoke(main, ["export", str(input_path), "-f", "csv"])

            assert result.exit_code != 0
            assert "Missing option" in result.output or "required" in result.output.lower()

    def test_export_help(self) -> None:
        """Test export command help text."""
        runner = CliRunner()

        result = runner.invoke(main, ["export", "--help"])

        assert result.exit_code == 0
        assert "Export" in result.output or "export" in result.output
        assert "--format" in result.output
        assert "--output" in result.output


class TestExportCommandShortFlags:
    """Tests for export command short flags."""

    def test_export_short_flags(self) -> None:
        """Test that short flags work correctly."""
        runner = CliRunner()

        results_json = {
            "tasks": [
                {"instance_id": "task-1", "score": 0.5},
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "results.json"
            output_path = Path(tmpdir) / "results.csv"

            input_path.write_text(json.dumps(results_json))

            result = runner.invoke(
                main, ["export", str(input_path), "-f", "csv", "-o", str(output_path)]
            )

            assert result.exit_code == 0
            assert output_path.exists()
