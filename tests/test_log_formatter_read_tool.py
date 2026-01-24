"""Tests for log_formatter.py Read tool summarization.

Regression tests for TypeError bug when Read tool uses offset/limit parameters.
"""

import pytest

from mcpbr.log_formatter import FormatterConfig, StreamEventFormatter


class TestReadToolSummarization:
    """Test cases for Read tool input summarization."""

    @pytest.fixture
    def formatter(self):
        """Create a formatter instance for testing."""
        config = FormatterConfig(verbosity=2)  # verbosity >= 2 required for summaries
        return StreamEventFormatter(config)

    def test_read_without_offset_limit(self, formatter):
        """Test Read tool without offset or limit parameters."""
        tool_input = {"file_path": "/workspace/file.py"}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "/workspace/file.py" in summary
        assert "lines" not in summary

    def test_read_with_both_offset_and_limit(self, formatter):
        """Test Read tool with both offset and limit."""
        tool_input = {"file_path": "/workspace/file.py", "offset": 100, "limit": 50}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 100-150" in summary

    def test_read_with_only_offset(self, formatter):
        """Test Read tool with only offset (read to end)."""
        tool_input = {"file_path": "/workspace/file.py", "offset": 100}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 100-..." in summary

    def test_read_with_only_limit(self, formatter):
        """Test Read tool with only limit (read from start).

        This is the case that triggered the original TypeError bug.
        When offset uses default ("") and limit is int, the expression
        offset + limit would fail with "can only concatenate str (not 'int') to str".
        """
        tool_input = {"file_path": "/workspace/file.py", "limit": 50}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 0-50" in summary

    def test_read_with_zero_offset(self, formatter):
        """Test Read tool with explicit offset=0."""
        tool_input = {"file_path": "/workspace/file.py", "offset": 0, "limit": 100}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 0-100" in summary

    def test_read_with_zero_limit(self, formatter):
        """Test Read tool with explicit limit=0 (unbounded)."""
        tool_input = {"file_path": "/workspace/file.py", "offset": 50, "limit": 0}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 50-..." in summary

    def test_read_with_string_offset_limit(self, formatter):
        """Test Read tool when offset/limit are passed as strings.

        The formatter should handle this by converting to int.
        """
        tool_input = {"file_path": "/workspace/file.py", "offset": "100", "limit": "50"}
        summary = formatter._summarize_tool_input("Read", tool_input)

        assert isinstance(summary, str)
        assert "lines 100-150" in summary
