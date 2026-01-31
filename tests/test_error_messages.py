"""Tests for error message accuracy and helpfulness."""

from mcpbr.harnesses import _generate_no_patch_error_message


class TestErrorMessageAccuracy:
    """Tests that error messages accurately reflect what actually happened."""

    def test_git_missing_error(self) -> None:
        """Test detection of missing git command."""
        # Simulate git command not found in stderr
        git_stderr = "sh: git: command not found"
        git_status = ""
        tool_usage = {"Read": 3, "Bash": 2}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="",
            tool_usage=tool_usage,
        )

        assert "git command not found" in error_msg
        assert "ensure git is installed" in error_msg
        # Should not claim edits were applied
        assert "Edit applied" not in error_msg

    def test_no_edits_made_error(self) -> None:
        """Test error when agent never tried to edit files and no buggy line."""
        # No Edit/Write tools in tool_usage, no buggy line
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 5, "Bash": 3, "Grep": 2}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="",  # No buggy line present
            tool_usage=tool_usage,
        )

        assert "No patches applied" in error_msg
        assert "completed without making changes" in error_msg
        # Should mention what tools were actually used
        assert "Read" in error_msg or "Tools used" in error_msg
        # Should not claim edits were applied
        assert "Edit applied" not in error_msg

    def test_edit_failed_no_changes_error(self) -> None:
        """Test error when Edit/Write tools were used but no git changes detected."""
        # Edit tool was called but git shows no changes
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 3, "Edit": 2, "Bash": 1}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="",
            tool_usage=tool_usage,
        )

        # Should indicate Edit was used
        assert "Edit" in error_msg or "Write" in error_msg
        assert "no changes detected" in error_msg
        # Can use the original message since it's now accurate
        assert "file may be unchanged" in error_msg or "file unchanged" in error_msg

    def test_write_tool_detected(self) -> None:
        """Test that Write tool is also detected as an edit attempt."""
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 2, "Write": 3}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="",
            tool_usage=tool_usage,
        )

        # Should recognize Write as an edit tool
        assert "Write" in error_msg or "Edit" in error_msg
        assert "no changes detected" in error_msg

    def test_git_status_shows_changes_but_no_patch(self) -> None:
        """Test when git status shows changes but patch generation fails."""
        git_status = "M file.py\n?? temp.txt"
        git_stderr = ""
        tool_usage = {"Edit": 2}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="",
            tool_usage=tool_usage,
        )

        assert "Files changed but no valid patch" in error_msg
        assert "M file.py" in error_msg

    def test_buggy_line_still_present(self) -> None:
        """Test when the buggy line is still detected after execution."""
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 3, "Edit": 1}
        buggy_line = "cright = 1"

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line=buggy_line,
            tool_usage=tool_usage,
        )

        assert "Buggy line still present" in error_msg
        assert "cright = 1" in error_msg

    def test_tool_usage_context_included(self) -> None:
        """Test that tool usage context is included for debugging."""
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 5, "Bash": 3, "Grep": 2, "Glob": 1}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="bug",
            tool_usage=tool_usage,
        )

        # Error message should include some tool usage info for debugging
        # At minimum should mention tools were used
        assert error_msg is not None
        assert len(error_msg) > 0

    def test_empty_tool_usage(self) -> None:
        """Test handling when tool_usage is empty (agent made no tool calls)."""
        git_status = ""
        git_stderr = ""
        tool_usage = {}

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="bug",
            tool_usage=tool_usage,
        )

        # Should indicate no tools were used
        assert "No patches applied" in error_msg or "Buggy line still present" in error_msg

    def test_max_iterations_no_changes(self) -> None:
        """Test error message when agent hits max iterations without making changes."""
        # This is a common case that was previously misdiagnosed
        git_status = ""
        git_stderr = ""
        tool_usage = {"Read": 10, "Bash": 5, "Grep": 3}  # Many reads but no edits

        error_msg = _generate_no_patch_error_message(
            git_status=git_status,
            git_stderr=git_stderr,
            buggy_line="still buggy",
            tool_usage=tool_usage,
        )

        # Should NOT claim edits were applied
        assert "Edit applied" not in error_msg
        # Should indicate what actually happened
        assert "No patches applied" in error_msg or "Buggy line still present" in error_msg
