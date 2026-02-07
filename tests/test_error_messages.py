"""Tests for error message accuracy and helpfulness."""

from mcpbr.harness import AgentResult, agent_result_to_dict
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

        # Should indicate Edit was used with call counts
        assert "Edit" in error_msg
        assert "working tree is clean" in error_msg
        assert "reverted" in error_msg
        assert "Edit x2" in error_msg

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

        # Should recognize Write as an edit tool with call counts
        assert "Write" in error_msg
        assert "working tree is clean" in error_msg
        assert "reverted" in error_msg
        assert "Write x3" in error_msg

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


class TestErrorSuppression:
    """Tests that misleading errors are suppressed when a patch was generated."""

    def test_no_changes_error_suppressed_when_patch_generated(self) -> None:
        """Error about 'working tree is clean' should be suppressed when patch exists (#409)."""
        result = AgentResult(
            patch="diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n",
            success=True,
            error="Write tool(s) used (Write x5) but final working tree is clean - "
            "changes were likely reverted during later iterations",
            tokens_input=1000,
            tokens_output=500,
            tool_calls=10,
        )
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")
        assert data["patch_generated"] is True
        assert "error" not in data

    def test_no_changes_error_kept_when_no_patch(self) -> None:
        """Error about 'working tree is clean' should remain when no patch was generated."""
        result = AgentResult(
            patch="",
            success=False,
            error="Write tool(s) used (Write x3) but final working tree is clean - "
            "changes were likely reverted during later iterations",
            tokens_input=1000,
            tokens_output=500,
            tool_calls=10,
        )
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")
        assert data["patch_generated"] is False
        assert "error" in data
        assert "working tree is clean" in data["error"]

    def test_timeout_error_not_suppressed(self) -> None:
        """Timeout errors should never be suppressed, even with a patch."""
        result = AgentResult(
            patch="diff --git a/file.py b/file.py\n",
            success=True,
            error="Evaluation timed out after 300 seconds",
            tokens_input=1000,
            tokens_output=500,
            tool_calls=5,
        )
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")
        assert data["patch_generated"] is True
        assert "error" in data
        assert "timed out" in data["error"]
        assert data["status"] == "timeout"

    def test_old_no_changes_detected_message_suppressed(self) -> None:
        """Legacy 'no changes detected' message should also be suppressed with a patch."""
        result = AgentResult(
            patch="diff --git a/file.py b/file.py\n",
            success=True,
            error="Write tool(s) used but no changes detected - "
            "file may be unchanged or changes were reverted",
            tokens_input=1000,
            tokens_output=500,
            tool_calls=5,
        )
        data = agent_result_to_dict(result, eval_result=None, model_id="claude-sonnet-4-5-20250929")
        assert data["patch_generated"] is True
        assert "error" not in data
