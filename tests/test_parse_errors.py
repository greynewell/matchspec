"""Test parsing of malformed SWE-bench task data."""

import json

import pytest

from mcpbr.evaluation import parse_test_list


class TestParseTestList:
    """Test parse_test_list function with various inputs."""

    def test_normal_json_list(self):
        """Test parsing normal JSON list."""
        assert parse_test_list('["test1", "test2"]') == ["test1", "test2"]

    def test_empty_list(self):
        """Test parsing empty list."""
        assert parse_test_list("[]") == []

    def test_python_literal_list(self):
        """Test parsing Python literal list."""
        assert parse_test_list("['test1', 'test2']") == ["test1", "test2"]

    def test_integer_list(self):
        """Test parsing list of integers - should convert to strings."""
        # Integers should be converted to strings for test commands
        result = parse_test_list("[1, 40]")
        assert result == ["1", "40"]
        # Verify all elements are strings
        assert all(isinstance(item, str) for item in result)

    def test_nested_list(self):
        """Test parsing nested list - should convert to strings."""
        result = parse_test_list("[[1, 40]]")
        # Nested lists get converted to their string representation
        assert result == ["[1, 40]"]
        assert all(isinstance(item, str) for item in result)

    def test_unquoted_strings(self):
        """Test parsing unquoted strings (fallback to manual parsing)."""
        result = parse_test_list("[test1, test2]")
        # Fallback parser should extract the strings
        assert result == ["test1", "test2"]

    def test_special_chars_in_test_names(self):
        """Test parsing test names with special characters."""
        # XML-like tags
        assert parse_test_list('["test[/?#]"]') == ["test[/?#]"]
        assert parse_test_list('["<tag>test</tag>"]') == ["<tag>test</tag>"]

    def test_empty_string(self):
        """Test parsing empty string."""
        assert parse_test_list("") == []

    def test_whitespace_only(self):
        """Test parsing whitespace-only string."""
        assert parse_test_list("   ") == []

    def test_malformed_json(self):
        """Test parsing malformed JSON (should fall back gracefully)."""
        # Missing quotes
        result = parse_test_list("[test1, test2]")
        assert result == ["test1", "test2"]

        # Single quotes (valid Python but not JSON)
        result = parse_test_list("['test1', 'test2']")
        assert result == ["test1", "test2"]

    def test_none_values_filtered(self):
        """Test that None values are filtered out."""
        result = parse_test_list('[null, "test1", null, "test2"]')
        assert result == ["test1", "test2"]

    def test_mixed_types_converted_to_strings(self):
        """Test that mixed types are all converted to strings."""
        result = parse_test_list('[1, "test", 2.5, true, false]')
        assert result == ["1", "test", "2.5", "True", "False"]
        assert all(isinstance(item, str) for item in result)

    def test_empty_strings_filtered(self):
        """Test that empty strings are filtered out."""
        result = parse_test_list('["test1", "", "test2", " ", "test3"]')
        # Empty string and whitespace-only string should be filtered
        assert result == ["test1", "test2", "test3"]


class TestIntConversionError:
    """Test scenarios that might cause int() conversion errors."""

    def test_int_conversion_on_list_string(self):
        """Test that calling int() on a list string fails."""
        with pytest.raises(ValueError, match="invalid literal for int"):
            int("[1, 40]")

    def test_parse_test_list_returns_list_of_strings(self):
        """Verify parse_test_list returns list of strings, not integers."""
        result = parse_test_list("[1, 40]")
        assert isinstance(result, list)
        assert result == ["1", "40"]
        # All elements should be strings now
        assert all(isinstance(item, str) for item in result)

        # String "in" operator should work (used by _build_test_command)
        assert "::" not in result[0]  # This would fail if result[0] was an int


class TestProblematicTaskData:
    """Test handling of actual problematic task data patterns."""

    def test_task_with_integer_list_in_fail_to_pass(self):
        """Test task data where FAIL_TO_PASS contains integers."""
        # Simulating problematic task data
        task = {
            "instance_id": "django__django-13112",
            "FAIL_TO_PASS": "[1, 40]",  # This is the problematic case
            "PASS_TO_PASS": "[]",
        }

        # This should not raise an error
        fail_to_pass = parse_test_list(task.get("FAIL_TO_PASS", "[]"))
        assert isinstance(fail_to_pass, list)
        # Integers should be converted to strings
        assert fail_to_pass == ["1", "40"]
        assert all(isinstance(item, str) for item in fail_to_pass)

    def test_task_with_special_chars_in_problem_statement(self):
        """Test task with XML-like tags in problem statement."""
        # Problem statements might contain code examples with tags
        problem_statement = """
        Fix the following issue:
        The code uses [/?#] as a delimiter but it doesn't work.
        Example: <div class="test">content</div>
        """

        # This should be fine - problem statements are just strings
        assert "[/?#]" in problem_statement
        assert "<div" in problem_statement

    def test_json_dumps_with_problematic_data(self):
        """Test JSON serialization of problematic task data."""
        task_def = {
            "instance_id": "test-id",
            "FAIL_TO_PASS": "[1, 40]",  # String representation
            "PASS_TO_PASS": "[]",
        }

        # This should not raise an error
        json_str = json.dumps(task_def, sort_keys=True)
        assert isinstance(json_str, str)

        # Parse it back
        parsed = json.loads(json_str)
        assert parsed["FAIL_TO_PASS"] == "[1, 40]"


class TestStateTrackerHashing:
    """Test that state tracker can handle problematic data."""

    def test_compute_task_hash_with_integer_list(self):
        """Test computing task hash when FAIL_TO_PASS has integers."""
        from mcpbr.state_tracker import compute_task_hash

        task = {
            "instance_id": "django__django-13112",
            "problem_statement": "Fix the bug",
            "repo": "django/django",
            "base_commit": "abc123",
            "FAIL_TO_PASS": "[1, 40]",
            "PASS_TO_PASS": "[]",
        }

        # This should not raise an error
        task_hash = compute_task_hash(task)
        assert isinstance(task_hash, str)
        assert len(task_hash) == 64  # SHA256 hex digest length
