"""Test git diff detection for new files (issue #327)."""

import subprocess
from pathlib import Path

import pytest

from mcpbr.harnesses import _get_git_diff


class TestGitDiffNewFiles:
    """Tests for git diff detection of new files created by MCP."""

    @pytest.mark.asyncio
    async def test_detects_new_files_in_git_diff(self, tmp_path: Path) -> None:
        """Test that _get_git_diff captures newly created files.

        Reproduces issue #327 where HumanEval's solution.py (new file)
        is not detected because git diff uses --diff-filter=M.
        """
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial file and commit
        initial_file = tmp_path / "README.md"
        initial_file.write_text("# Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create NEW file (simulating MCP filesystem write)
        solution_file = tmp_path / "solution.py"
        solution_file.write_text('def hello():\n    return "Hello, World!"\n')

        # Stage the new file
        subprocess.run(["git", "add", "solution.py"], cwd=tmp_path, check=True, capture_output=True)

        # Get git diff (ASYNC call)
        diff_output = await _get_git_diff(str(tmp_path))

        # Assertions
        assert diff_output, "Git diff should return output for staged new file"
        assert "solution.py" in diff_output, "Diff should include the new file solution.py"
        assert "def hello():" in diff_output, "Diff should show the file contents"
        assert "+def hello():" in diff_output or "new file" in diff_output.lower(), (
            "Diff should indicate this is a new file"
        )

    @pytest.mark.asyncio
    async def test_detects_modified_files_in_git_diff(self, tmp_path: Path) -> None:
        """Test that _get_git_diff still captures modified files."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial file and commit
        initial_file = tmp_path / "README.md"
        initial_file.write_text("# Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify existing file
        initial_file.write_text("# Updated Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)

        # Get diff (ASYNC)
        diff_output = await _get_git_diff(str(tmp_path))

        # Should still capture modifications
        assert diff_output, "Git diff should return output for modified file"
        assert "README.md" in diff_output, "Diff should include the modified file"
        assert "-# Test Repo" in diff_output or "+# Updated Test Repo" in diff_output, (
            "Diff should show the file changes"
        )

    @pytest.mark.asyncio
    async def test_git_diff_with_both_new_and_modified(self, tmp_path: Path) -> None:
        """Test git diff with both new files and modifications.

        When modified files exist, the filter is applied (showing only modifications).
        This is intentional behavior to exclude agent-created test files and artifacts.
        """
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial file and commit
        initial_file = tmp_path / "README.md"
        initial_file.write_text("# Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Modify existing file
        initial_file.write_text("# Updated Test Repo\n")

        # Add new file (this would be filtered out when modifications exist)
        solution_file = tmp_path / "solution.py"
        solution_file.write_text('def hello():\n    return "Hello, World!"\n')

        # Stage both files
        subprocess.run(
            ["git", "add", "README.md", "solution.py"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Get diff (ASYNC)
        diff_output = await _get_git_diff(str(tmp_path))

        # When modified files exist, only they should appear (filtered behavior)
        assert diff_output, "Git diff should return output for modified file"
        assert "README.md" in diff_output, "Diff should include modified file"
        # New files are intentionally filtered out when modifications exist
        # This prevents agent-created test files from being included in patches

    @pytest.mark.asyncio
    async def test_git_diff_empty_when_nothing_staged(self, tmp_path: Path) -> None:
        """Test that git diff returns empty when nothing is staged."""
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create initial file and commit
        initial_file = tmp_path / "README.md"
        initial_file.write_text("# Test Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Don't stage anything - just get the diff
        diff_output = await _get_git_diff(str(tmp_path))

        # Should return empty string
        assert diff_output == "", "Git diff should be empty when nothing is staged"
