"""Tests for Claude Code plugin and skills."""

import json
import re
from pathlib import Path

import pytest


class TestPluginManifest:
    """Tests for .claude-plugin/plugin.json."""

    @pytest.fixture
    def plugin_json_path(self) -> Path:
        """Return path to plugin.json."""
        return Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"

    @pytest.fixture
    def pyproject_path(self) -> Path:
        """Return path to pyproject.toml."""
        return Path(__file__).parent.parent / "pyproject.toml"

    def test_plugin_json_exists(self, plugin_json_path: Path) -> None:
        """Test that plugin.json exists."""
        assert plugin_json_path.exists(), "plugin.json should exist"

    def test_plugin_json_valid(self, plugin_json_path: Path) -> None:
        """Test that plugin.json is valid JSON."""
        with open(plugin_json_path) as f:
            data = json.load(f)

        assert isinstance(data, dict), "plugin.json should be a JSON object"

    def test_plugin_json_has_required_fields(self, plugin_json_path: Path) -> None:
        """Test that plugin.json has all required fields."""
        with open(plugin_json_path) as f:
            data = json.load(f)

        required_fields = ["name", "version", "description", "schema_version"]
        for field in required_fields:
            assert field in data, f"plugin.json should have '{field}' field"

    def test_plugin_name(self, plugin_json_path: Path) -> None:
        """Test that plugin name is 'mcpbr'."""
        with open(plugin_json_path) as f:
            data = json.load(f)

        assert data["name"] == "mcpbr", "Plugin name should be 'mcpbr'"

    def test_plugin_version_matches_pyproject(
        self, plugin_json_path: Path, pyproject_path: Path
    ) -> None:
        """Test that plugin version matches pyproject.toml version."""
        # Get version from plugin.json
        with open(plugin_json_path) as f:
            plugin_data = json.load(f)
        plugin_version = plugin_data["version"]

        # Get version from pyproject.toml
        pyproject_content = pyproject_path.read_text()
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_content, re.MULTILINE)
        assert match, "Could not find version in pyproject.toml"
        pyproject_version = match.group(1)

        assert plugin_version == pyproject_version, (
            f"Plugin version ({plugin_version}) should match pyproject.toml version ({pyproject_version}). Run 'make sync-version' to fix."
        )

    def test_plugin_description(self, plugin_json_path: Path) -> None:
        """Test that plugin has a non-empty description."""
        with open(plugin_json_path) as f:
            data = json.load(f)

        description = data.get("description", "")
        assert len(description) > 0, "Plugin should have a description"
        assert "mcpbr" in description.lower(), "Description should mention mcpbr"


class TestSkills:
    """Tests for skills directory and skill files."""

    @pytest.fixture
    def skills_dir(self) -> Path:
        """Return path to skills directory."""
        return Path(__file__).parent.parent / ".claude-plugin" / "skills"

    @pytest.fixture
    def skill_dirs(self, skills_dir: Path) -> list[Path]:
        """Return list of skill directories."""
        return [d for d in skills_dir.iterdir() if d.is_dir()]

    def test_skills_directory_exists(self, skills_dir: Path) -> None:
        """Test that skills directory exists."""
        assert skills_dir.exists(), "skills directory should exist"

    def test_has_skills(self, skill_dirs: list[Path]) -> None:
        """Test that at least one skill exists."""
        assert len(skill_dirs) > 0, "Should have at least one skill"

    def test_expected_skills_exist(self, skills_dir: Path) -> None:
        """Test that expected skills exist."""
        expected_skills = ["mcpbr-eval", "mcpbr-config", "benchmark-swe-lite"]
        for skill in expected_skills:
            skill_path = skills_dir / skill
            assert skill_path.exists(), f"Skill '{skill}' should exist"

    @pytest.mark.parametrize("skill_name", ["mcpbr-eval", "mcpbr-config", "benchmark-swe-lite"])
    def test_skill_has_skill_md(self, skills_dir: Path, skill_name: str) -> None:
        """Test that each skill has a SKILL.md file."""
        skill_path = skills_dir / skill_name / "SKILL.md"
        assert skill_path.exists(), f"Skill '{skill_name}' should have SKILL.md"

    @pytest.mark.parametrize("skill_name", ["mcpbr-eval", "mcpbr-config", "benchmark-swe-lite"])
    def test_skill_md_has_frontmatter(self, skills_dir: Path, skill_name: str) -> None:
        """Test that SKILL.md has valid frontmatter."""
        skill_path = skills_dir / skill_name / "SKILL.md"
        content = skill_path.read_text()

        # Check for frontmatter delimiters
        assert content.startswith("---\n"), f"{skill_name} should start with '---'"

        # Extract frontmatter
        parts = content.split("---\n", 2)
        assert len(parts) >= 3, f"{skill_name} should have complete frontmatter"

        frontmatter = parts[1]
        assert "name:" in frontmatter, f"{skill_name} frontmatter should have 'name'"
        assert "description:" in frontmatter, f"{skill_name} frontmatter should have 'description'"

    @pytest.mark.parametrize("skill_name", ["mcpbr-eval", "mcpbr-config", "benchmark-swe-lite"])
    def test_skill_md_has_instructions(self, skills_dir: Path, skill_name: str) -> None:
        """Test that SKILL.md has an Instructions section."""
        skill_path = skills_dir / skill_name / "SKILL.md"
        content = skill_path.read_text()

        assert "# Instructions" in content, f"{skill_name} should have '# Instructions' section"

    def test_mcpbr_eval_mentions_docker(self, skills_dir: Path) -> None:
        """Test that mcpbr-eval skill mentions Docker requirement."""
        skill_path = skills_dir / "mcpbr-eval" / "SKILL.md"
        content = skill_path.read_text().lower()

        assert "docker" in content, "mcpbr-eval should mention Docker"
        assert "docker ps" in content, "mcpbr-eval should mention 'docker ps' command"

    def test_mcpbr_eval_mentions_workdir(self, skills_dir: Path) -> None:
        """Test that mcpbr-eval skill mentions {workdir} placeholder."""
        skill_path = skills_dir / "mcpbr-eval" / "SKILL.md"
        content = skill_path.read_text()

        assert "{workdir}" in content, "mcpbr-eval should mention {workdir} placeholder"

    def test_mcpbr_config_mentions_workdir(self, skills_dir: Path) -> None:
        """Test that mcpbr-config skill emphasizes {workdir} placeholder."""
        skill_path = skills_dir / "mcpbr-config" / "SKILL.md"
        content = skill_path.read_text()

        assert "{workdir}" in content, "mcpbr-config should mention {workdir} placeholder"
        # Should mention it multiple times since it's critical
        assert content.count("{workdir}") >= 3, (
            "mcpbr-config should emphasize {workdir} multiple times"
        )

    def test_mcpbr_eval_lists_benchmarks(self, skills_dir: Path) -> None:
        """Test that mcpbr-eval skill lists all supported benchmarks."""
        skill_path = skills_dir / "mcpbr-eval" / "SKILL.md"
        content = skill_path.read_text().lower()

        benchmarks = ["swe-bench", "cybergym", "mcptoolbench"]
        for benchmark in benchmarks:
            assert benchmark in content, f"mcpbr-eval should mention {benchmark} benchmark"

    def test_benchmark_swe_lite_has_defaults(self, skills_dir: Path) -> None:
        """Test that benchmark-swe-lite skill has default command."""
        skill_path = skills_dir / "benchmark-swe-lite" / "SKILL.md"
        content = skill_path.read_text()

        # Should mention the default command structure
        assert "mcpbr run" in content, "benchmark-swe-lite should show mcpbr run command"
        assert "SWE-bench" in content or "swe-bench" in content, (
            "benchmark-swe-lite should mention SWE-bench"
        )

    def test_mcpbr_config_has_templates(self, skills_dir: Path) -> None:
        """Test that mcpbr-config skill has example configurations."""
        skill_path = skills_dir / "mcpbr-config" / "SKILL.md"
        content = skill_path.read_text()

        # Should have YAML examples
        assert "```yaml" in content, "mcpbr-config should have YAML examples"
        assert "mcp_server:" in content, "mcpbr-config should show mcp_server config"
        assert "command:" in content, "mcpbr-config should show command field"

    def test_skills_mention_mcpbr_commands(self, skill_dirs: list[Path]) -> None:
        """Test that skills reference actual mcpbr commands."""
        mcpbr_commands = ["mcpbr run", "mcpbr init", "mcpbr models", "mcpbr benchmarks"]

        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text()
                # Each skill should mention at least some mcpbr commands
                found_commands = [cmd for cmd in mcpbr_commands if cmd in content]
                assert len(found_commands) > 0, f"{skill_dir.name} should reference mcpbr commands"


class TestVersionSyncScript:
    """Tests for the version sync script."""

    @pytest.fixture
    def sync_script_path(self) -> Path:
        """Return path to sync_version.py script."""
        return Path(__file__).parent.parent / "scripts" / "sync_version.py"

    def test_sync_script_exists(self, sync_script_path: Path) -> None:
        """Test that sync_version.py script exists."""
        assert sync_script_path.exists(), "sync_version.py script should exist"

    def test_sync_script_is_executable(self, sync_script_path: Path) -> None:
        """Test that sync_version.py is executable."""
        import os

        mode = os.stat(sync_script_path).st_mode
        is_executable = bool(mode & 0o111)
        assert is_executable, "sync_version.py should be executable"

    def test_sync_script_has_shebang(self, sync_script_path: Path) -> None:
        """Test that sync_version.py has proper shebang."""
        content = sync_script_path.read_text()
        assert content.startswith("#!/usr/bin/env python3"), (
            "sync_version.py should have python3 shebang"
        )

    def test_sync_script_has_docstring(self, sync_script_path: Path) -> None:
        """Test that sync_version.py has a docstring."""
        content = sync_script_path.read_text()
        assert '"""' in content, "sync_version.py should have a docstring"


class TestMakefile:
    """Tests for Makefile."""

    @pytest.fixture
    def makefile_path(self) -> Path:
        """Return path to Makefile."""
        return Path(__file__).parent.parent / "Makefile"

    def test_makefile_exists(self, makefile_path: Path) -> None:
        """Test that Makefile exists."""
        assert makefile_path.exists(), "Makefile should exist"

    def test_makefile_has_sync_version(self, makefile_path: Path) -> None:
        """Test that Makefile has sync-version target."""
        content = makefile_path.read_text()
        assert "sync-version:" in content, "Makefile should have sync-version target"

    def test_makefile_has_build(self, makefile_path: Path) -> None:
        """Test that Makefile has build target."""
        content = makefile_path.read_text()
        assert "build:" in content, "Makefile should have build target"

    def test_build_depends_on_sync_version(self, makefile_path: Path) -> None:
        """Test that build target depends on sync-version."""
        content = makefile_path.read_text()
        # Find the build target line and verify it depends on sync-version
        build_line = None
        for line in content.splitlines():
            if line.startswith("build:"):
                build_line = line
                break

        assert build_line is not None, "Makefile should have build target"
        assert "sync-version" in build_line, "Build target should depend on sync-version"


class TestPreCommitConfig:
    """Tests for pre-commit configuration."""

    @pytest.fixture
    def precommit_path(self) -> Path:
        """Return path to .pre-commit-config.yaml."""
        return Path(__file__).parent.parent / ".pre-commit-config.yaml"

    def test_precommit_exists(self, precommit_path: Path) -> None:
        """Test that .pre-commit-config.yaml exists."""
        assert precommit_path.exists(), ".pre-commit-config.yaml should exist"

    def test_precommit_has_sync_version_hook(self, precommit_path: Path) -> None:
        """Test that pre-commit config includes sync-version hook."""
        content = precommit_path.read_text()
        assert "sync-version" in content, ".pre-commit-config.yaml should include sync-version hook"


class TestDocumentation:
    """Tests for documentation updates."""

    @pytest.fixture
    def readme_path(self) -> Path:
        """Return path to README.md."""
        return Path(__file__).parent.parent / "README.md"

    @pytest.fixture
    def contributing_path(self) -> Path:
        """Return path to CONTRIBUTING.md."""
        return Path(__file__).parent.parent / "CONTRIBUTING.md"

    def test_readme_mentions_claude_code(self, readme_path: Path) -> None:
        """Test that README mentions Claude Code integration."""
        content = readme_path.read_text()
        assert "Claude Code" in content, "README should mention Claude Code integration"

    def test_readme_has_claude_code_section(self, readme_path: Path) -> None:
        """Test that README has Claude Code Integration section."""
        content = readme_path.read_text()
        assert "## Claude Code Integration" in content, (
            "README should have Claude Code Integration section"
        )

    def test_readme_mentions_skills(self, readme_path: Path) -> None:
        """Test that README mentions the available skills."""
        content = readme_path.read_text()
        skills = ["run-benchmark", "generate-config", "swe-bench-lite"]
        for skill in skills:
            assert skill in content, f"README should mention {skill} skill"

    def test_contributing_mentions_version_sync(self, contributing_path: Path) -> None:
        """Test that CONTRIBUTING.md mentions version sync."""
        content = contributing_path.read_text()
        assert "sync-version" in content or "sync_version" in content, (
            "CONTRIBUTING.md should mention version sync"
        )

    def test_contributing_mentions_makefile(self, contributing_path: Path) -> None:
        """Test that CONTRIBUTING.md mentions Makefile."""
        content = contributing_path.read_text()
        assert "Makefile" in content or "make " in content, (
            "CONTRIBUTING.md should mention Makefile"
        )

    def test_contributing_mentions_precommit(self, contributing_path: Path) -> None:
        """Test that CONTRIBUTING.md mentions pre-commit hooks."""
        content = contributing_path.read_text()
        assert "pre-commit" in content, "CONTRIBUTING.md should mention pre-commit hooks"
