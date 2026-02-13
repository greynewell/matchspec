"""Tests for the interactive tutorial system."""

import json
from pathlib import Path

import pytest

from mcpbr.tutorial import (
    TUTORIALS,
    Tutorial,
    TutorialEngine,
    TutorialProgress,
    TutorialStep,
)


def _cli_has_tutorial_command() -> bool:
    """Check if the 'tutorial' command is registered in the CLI."""
    try:
        from mcpbr.cli import main

        return "tutorial" in (main.commands or {})
    except Exception:
        return False


cli_tutorial_available = pytest.mark.skipif(
    not _cli_has_tutorial_command(),
    reason="CLI tutorial commands not yet registered in cli.py",
)


# ---------------------------------------------------------------------------
# TutorialStep tests
# ---------------------------------------------------------------------------


class TestTutorialStep:
    """Tests for the TutorialStep dataclass."""

    def test_defaults(self) -> None:
        """Test default values are set correctly."""
        step = TutorialStep(id="s1", title="Step 1", content="Do something")
        assert step.id == "s1"
        assert step.title == "Step 1"
        assert step.content == "Do something"
        assert step.hint is None
        assert step.validation is None
        assert step.action == "info"

    def test_all_fields(self) -> None:
        """Test creating a step with all fields specified."""
        step = TutorialStep(
            id="check",
            title="Check Docker",
            content="Run docker info",
            hint="Install Docker first",
            validation="command_runs:docker info",
            action="check",
        )
        assert step.hint == "Install Docker first"
        assert step.validation == "command_runs:docker info"
        assert step.action == "check"

    def test_action_types(self) -> None:
        """Test that all expected action types can be set."""
        for action in ("info", "prompt", "check"):
            step = TutorialStep(id="x", title="X", content="X", action=action)
            assert step.action == action


# ---------------------------------------------------------------------------
# Tutorial tests
# ---------------------------------------------------------------------------


class TestTutorial:
    """Tests for the Tutorial dataclass."""

    def test_defaults(self) -> None:
        """Test tutorial with default empty steps."""
        t = Tutorial(
            id="test",
            title="Test Tutorial",
            description="A test",
            difficulty="beginner",
            estimated_minutes=5,
        )
        assert t.steps == []

    def test_with_steps(self) -> None:
        """Test tutorial with steps provided."""
        steps = [
            TutorialStep(id="s1", title="First", content="Do first"),
            TutorialStep(id="s2", title="Second", content="Do second"),
        ]
        t = Tutorial(
            id="multi",
            title="Multi-step",
            description="Has steps",
            difficulty="intermediate",
            estimated_minutes=10,
            steps=steps,
        )
        assert len(t.steps) == 2
        assert t.steps[0].id == "s1"
        assert t.steps[1].id == "s2"


# ---------------------------------------------------------------------------
# TutorialProgress tests
# ---------------------------------------------------------------------------


class TestTutorialProgress:
    """Tests for the TutorialProgress dataclass."""

    def test_defaults(self) -> None:
        """Test default progress values."""
        p = TutorialProgress(tutorial_id="getting-started")
        assert p.tutorial_id == "getting-started"
        assert p.current_step == 0
        assert p.completed_steps == []
        assert p.started_at == ""
        assert p.completed_at is None

    def test_custom_values(self) -> None:
        """Test progress with custom values."""
        p = TutorialProgress(
            tutorial_id="config",
            current_step=3,
            completed_steps=["s1", "s2", "s3"],
            started_at="2025-01-15T10:00:00+00:00",
            completed_at="2025-01-15T10:30:00+00:00",
        )
        assert p.current_step == 3
        assert len(p.completed_steps) == 3
        assert p.completed_at is not None


# ---------------------------------------------------------------------------
# Built-in TUTORIALS data integrity tests
# ---------------------------------------------------------------------------


class TestBuiltinTutorials:
    """Tests for the built-in tutorial data."""

    def test_all_four_tutorials_exist(self) -> None:
        """Test that all four expected tutorials are defined."""
        expected = {"getting-started", "configuration", "benchmarks", "analytics"}
        assert set(TUTORIALS.keys()) == expected

    def test_tutorial_ids_match_keys(self) -> None:
        """Test that each tutorial's id matches its dict key."""
        for key, tutorial in TUTORIALS.items():
            assert tutorial.id == key, f"Tutorial key '{key}' != id '{tutorial.id}'"

    def test_all_tutorials_have_steps(self) -> None:
        """Test that every tutorial has at least one step."""
        for tid, tutorial in TUTORIALS.items():
            assert len(tutorial.steps) > 0, f"Tutorial '{tid}' has no steps"

    def test_all_steps_have_unique_ids(self) -> None:
        """Test that step IDs are unique within each tutorial."""
        for tid, tutorial in TUTORIALS.items():
            step_ids = [s.id for s in tutorial.steps]
            assert len(step_ids) == len(set(step_ids)), f"Tutorial '{tid}' has duplicate step IDs"

    def test_all_tutorials_have_valid_difficulty(self) -> None:
        """Test that difficulty is one of the expected values."""
        valid = {"beginner", "intermediate", "advanced"}
        for tid, tutorial in TUTORIALS.items():
            assert tutorial.difficulty in valid, (
                f"Tutorial '{tid}' has invalid difficulty: {tutorial.difficulty}"
            )

    def test_all_tutorials_have_positive_estimated_minutes(self) -> None:
        """Test that estimated_minutes is positive."""
        for tid, tutorial in TUTORIALS.items():
            assert tutorial.estimated_minutes > 0, (
                f"Tutorial '{tid}' has non-positive estimated_minutes"
            )

    def test_all_tutorials_have_descriptions(self) -> None:
        """Test that every tutorial has a non-empty description."""
        for tid, tutorial in TUTORIALS.items():
            assert tutorial.description, f"Tutorial '{tid}' has empty description"

    def test_all_tutorials_have_titles(self) -> None:
        """Test that every tutorial has a non-empty title."""
        for tid, tutorial in TUTORIALS.items():
            assert tutorial.title, f"Tutorial '{tid}' has empty title"

    def test_step_content_is_nonempty(self) -> None:
        """Test that all steps have non-empty content."""
        for tid, tutorial in TUTORIALS.items():
            for step in tutorial.steps:
                assert step.content, f"Step '{step.id}' in tutorial '{tid}' has empty content"

    def test_step_titles_are_nonempty(self) -> None:
        """Test that all steps have non-empty titles."""
        for tid, tutorial in TUTORIALS.items():
            for step in tutorial.steps:
                assert step.title, f"Step '{step.id}' in tutorial '{tid}' has empty title"

    def test_getting_started_step_count(self) -> None:
        """Test getting-started tutorial has expected number of steps."""
        t = TUTORIALS["getting-started"]
        assert len(t.steps) == 9

    def test_configuration_step_count(self) -> None:
        """Test configuration tutorial has expected number of steps."""
        t = TUTORIALS["configuration"]
        assert len(t.steps) == 9

    def test_benchmarks_step_count(self) -> None:
        """Test benchmarks tutorial has expected number of steps."""
        t = TUTORIALS["benchmarks"]
        assert len(t.steps) == 9

    def test_analytics_step_count(self) -> None:
        """Test analytics tutorial has expected number of steps."""
        t = TUTORIALS["analytics"]
        assert len(t.steps) == 9

    def test_getting_started_has_check_steps(self) -> None:
        """Test that getting-started has validation check steps."""
        t = TUTORIALS["getting-started"]
        check_steps = [s for s in t.steps if s.action == "check"]
        assert len(check_steps) >= 2, "Expected at least 2 check steps"

    def test_getting_started_docker_check(self) -> None:
        """Test that getting-started has a Docker check step."""
        t = TUTORIALS["getting-started"]
        docker_step = next((s for s in t.steps if s.id == "check-docker"), None)
        assert docker_step is not None
        assert docker_step.validation == "command_runs:docker info"
        assert docker_step.action == "check"

    def test_getting_started_mcpbr_check(self) -> None:
        """Test that getting-started has an mcpbr install check step."""
        t = TUTORIALS["getting-started"]
        mcpbr_step = next((s for s in t.steps if s.id == "check-mcpbr"), None)
        assert mcpbr_step is not None
        assert mcpbr_step.validation == "command_runs:mcpbr --version"


# ---------------------------------------------------------------------------
# TutorialEngine initialization tests
# ---------------------------------------------------------------------------


class TestTutorialEngineInit:
    """Tests for TutorialEngine initialization."""

    def test_default_progress_dir(self) -> None:
        """Test that default progress_dir is ~/.mcpbr/tutorials/."""
        engine = TutorialEngine()
        expected = Path.home() / ".mcpbr" / "tutorials"
        assert engine.progress_dir == expected

    def test_custom_progress_dir(self, tmp_path: Path) -> None:
        """Test using a custom progress directory."""
        custom = tmp_path / "my_progress"
        engine = TutorialEngine(progress_dir=custom)
        assert engine.progress_dir == custom


# ---------------------------------------------------------------------------
# TutorialEngine.list_tutorials tests
# ---------------------------------------------------------------------------


class TestListTutorials:
    """Tests for the list_tutorials method."""

    def test_returns_all_tutorials(self) -> None:
        """Test that list_tutorials returns all 4 built-in tutorials."""
        engine = TutorialEngine()
        tutorials = engine.list_tutorials()
        assert len(tutorials) == 4

    def test_returns_tutorial_objects(self) -> None:
        """Test that list_tutorials returns Tutorial instances."""
        engine = TutorialEngine()
        tutorials = engine.list_tutorials()
        for t in tutorials:
            assert isinstance(t, Tutorial)

    def test_tutorial_ids(self) -> None:
        """Test that list_tutorials includes all expected IDs."""
        engine = TutorialEngine()
        ids = {t.id for t in engine.list_tutorials()}
        assert ids == {"getting-started", "configuration", "benchmarks", "analytics"}


# ---------------------------------------------------------------------------
# TutorialEngine.get_tutorial tests
# ---------------------------------------------------------------------------


class TestGetTutorial:
    """Tests for the get_tutorial method."""

    def test_valid_id(self) -> None:
        """Test retrieving a tutorial by valid ID."""
        engine = TutorialEngine()
        t = engine.get_tutorial("getting-started")
        assert t is not None
        assert t.id == "getting-started"
        assert t.title == "Getting Started with mcpbr"

    def test_invalid_id(self) -> None:
        """Test that an invalid ID returns None."""
        engine = TutorialEngine()
        assert engine.get_tutorial("nonexistent") is None

    def test_all_known_ids(self) -> None:
        """Test that all known IDs are retrievable."""
        engine = TutorialEngine()
        for tid in ("getting-started", "configuration", "benchmarks", "analytics"):
            assert engine.get_tutorial(tid) is not None


# ---------------------------------------------------------------------------
# TutorialEngine.start_tutorial tests
# ---------------------------------------------------------------------------


class TestStartTutorial:
    """Tests for the start_tutorial method."""

    def test_creates_progress(self, tmp_path: Path) -> None:
        """Test that starting a tutorial creates progress."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        assert progress.tutorial_id == "getting-started"
        assert progress.current_step == 0
        assert progress.completed_steps == []
        assert progress.started_at != ""
        assert progress.completed_at is None

    def test_saves_progress_file(self, tmp_path: Path) -> None:
        """Test that starting creates a progress JSON file."""
        engine = TutorialEngine(progress_dir=tmp_path)
        engine.start_tutorial("getting-started")
        progress_file = tmp_path / "getting-started.json"
        assert progress_file.exists()

    def test_resumes_existing_progress(self, tmp_path: Path) -> None:
        """Test that start_tutorial resumes existing progress."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        progress = engine.complete_step(progress, "welcome")

        # Start again - should resume
        resumed = engine.start_tutorial("getting-started")
        assert "welcome" in resumed.completed_steps
        assert resumed.current_step == progress.current_step

    def test_invalid_tutorial_id_raises(self, tmp_path: Path) -> None:
        """Test that an invalid tutorial_id raises ValueError."""
        engine = TutorialEngine(progress_dir=tmp_path)
        with pytest.raises(ValueError, match="Unknown tutorial"):
            engine.start_tutorial("nonexistent")


# ---------------------------------------------------------------------------
# TutorialEngine.save_progress / get_progress round-trip tests
# ---------------------------------------------------------------------------


class TestProgressPersistence:
    """Tests for save_progress and get_progress round-trip."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Test that saved progress can be loaded back correctly."""
        engine = TutorialEngine(progress_dir=tmp_path)
        original = TutorialProgress(
            tutorial_id="configuration",
            current_step=3,
            completed_steps=["config-formats", "mcp-server-config", "model-provider-selection"],
            started_at="2025-06-01T12:00:00+00:00",
            completed_at=None,
        )
        engine.save_progress(original)

        loaded = engine.get_progress("configuration")
        assert loaded is not None
        assert loaded.tutorial_id == original.tutorial_id
        assert loaded.current_step == original.current_step
        assert loaded.completed_steps == original.completed_steps
        assert loaded.started_at == original.started_at
        assert loaded.completed_at == original.completed_at

    def test_get_progress_no_file(self, tmp_path: Path) -> None:
        """Test that get_progress returns None when no file exists."""
        engine = TutorialEngine(progress_dir=tmp_path)
        assert engine.get_progress("getting-started") is None

    def test_get_progress_corrupt_json(self, tmp_path: Path) -> None:
        """Test that get_progress returns None for corrupt JSON."""
        engine = TutorialEngine(progress_dir=tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        corrupt_file = tmp_path / "getting-started.json"
        corrupt_file.write_text("{not valid json!!!")
        assert engine.get_progress("getting-started") is None

    def test_get_progress_missing_keys(self, tmp_path: Path) -> None:
        """Test that get_progress returns None for JSON with missing keys."""
        engine = TutorialEngine(progress_dir=tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        bad_file = tmp_path / "getting-started.json"
        bad_file.write_text(json.dumps({"foo": "bar"}))
        assert engine.get_progress("getting-started") is None

    def test_creates_progress_dir(self, tmp_path: Path) -> None:
        """Test that save_progress creates the directory if needed."""
        nested = tmp_path / "deep" / "nested" / "dir"
        engine = TutorialEngine(progress_dir=nested)
        progress = TutorialProgress(
            tutorial_id="test",
            started_at="2025-01-01T00:00:00+00:00",
        )
        engine.save_progress(progress)
        assert nested.exists()
        assert (nested / "test.json").exists()

    def test_overwrites_existing_progress(self, tmp_path: Path) -> None:
        """Test that save_progress overwrites existing file."""
        engine = TutorialEngine(progress_dir=tmp_path)
        p1 = TutorialProgress(
            tutorial_id="getting-started",
            current_step=0,
            started_at="2025-01-01T00:00:00+00:00",
        )
        engine.save_progress(p1)

        p2 = TutorialProgress(
            tutorial_id="getting-started",
            current_step=5,
            completed_steps=["a", "b", "c", "d", "e"],
            started_at="2025-01-01T00:00:00+00:00",
        )
        engine.save_progress(p2)

        loaded = engine.get_progress("getting-started")
        assert loaded is not None
        assert loaded.current_step == 5
        assert len(loaded.completed_steps) == 5


# ---------------------------------------------------------------------------
# TutorialEngine.complete_step tests
# ---------------------------------------------------------------------------


class TestCompleteStep:
    """Tests for the complete_step method."""

    def test_marks_step_completed(self, tmp_path: Path) -> None:
        """Test that complete_step adds step to completed_steps."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        progress = engine.complete_step(progress, "welcome")
        assert "welcome" in progress.completed_steps

    def test_advances_current_step(self, tmp_path: Path) -> None:
        """Test that complete_step advances current_step to next incomplete."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        # Complete first step
        progress = engine.complete_step(progress, "welcome")
        # Current step should now point to step index 1
        assert progress.current_step == 1

    def test_no_duplicate_completion(self, tmp_path: Path) -> None:
        """Test that completing the same step twice doesn't duplicate."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        progress = engine.complete_step(progress, "welcome")
        progress = engine.complete_step(progress, "welcome")
        assert progress.completed_steps.count("welcome") == 1

    def test_completes_tutorial(self, tmp_path: Path) -> None:
        """Test that completing all steps sets completed_at."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        tutorial = engine.get_tutorial("getting-started")
        assert tutorial is not None

        for step in tutorial.steps:
            progress = engine.complete_step(progress, step.id)

        assert progress.completed_at is not None
        assert progress.current_step == len(tutorial.steps)

    def test_saves_progress_on_complete(self, tmp_path: Path) -> None:
        """Test that complete_step persists the updated progress."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        engine.complete_step(progress, "welcome")

        # Reload from disk
        loaded = engine.get_progress("getting-started")
        assert loaded is not None
        assert "welcome" in loaded.completed_steps

    def test_complete_steps_out_of_order(self, tmp_path: Path) -> None:
        """Test completing steps in non-sequential order."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        tutorial = engine.get_tutorial("getting-started")
        assert tutorial is not None

        # Complete step 3 first (skipping 0, 1, 2)
        third_step_id = tutorial.steps[2].id
        progress = engine.complete_step(progress, third_step_id)
        assert third_step_id in progress.completed_steps
        # current_step should point to first incomplete (step 0)
        assert progress.current_step == 0


# ---------------------------------------------------------------------------
# TutorialEngine.reset_tutorial tests
# ---------------------------------------------------------------------------


class TestResetTutorial:
    """Tests for the reset_tutorial method."""

    def test_deletes_progress_file(self, tmp_path: Path) -> None:
        """Test that reset_tutorial removes the progress file."""
        engine = TutorialEngine(progress_dir=tmp_path)
        engine.start_tutorial("getting-started")
        progress_file = tmp_path / "getting-started.json"
        assert progress_file.exists()

        engine.reset_tutorial("getting-started")
        assert not progress_file.exists()

    def test_get_progress_returns_none_after_reset(self, tmp_path: Path) -> None:
        """Test that progress is gone after reset."""
        engine = TutorialEngine(progress_dir=tmp_path)
        engine.start_tutorial("getting-started")
        engine.reset_tutorial("getting-started")
        assert engine.get_progress("getting-started") is None

    def test_reset_nonexistent_no_error(self, tmp_path: Path) -> None:
        """Test that resetting a tutorial with no progress doesn't error."""
        engine = TutorialEngine(progress_dir=tmp_path)
        # Should not raise
        engine.reset_tutorial("getting-started")

    def test_can_restart_after_reset(self, tmp_path: Path) -> None:
        """Test that a tutorial can be started fresh after reset."""
        engine = TutorialEngine(progress_dir=tmp_path)
        progress = engine.start_tutorial("getting-started")
        engine.complete_step(progress, "welcome")
        engine.reset_tutorial("getting-started")

        new_progress = engine.start_tutorial("getting-started")
        assert new_progress.completed_steps == []
        assert new_progress.current_step == 0


# ---------------------------------------------------------------------------
# TutorialEngine.validate_step tests
# ---------------------------------------------------------------------------


class TestValidateStep:
    """Tests for the validate_step method."""

    def test_none_validation_passes(self) -> None:
        """Test that a step with no validation always passes."""
        engine = TutorialEngine()
        step = TutorialStep(id="x", title="X", content="X", validation=None)
        success, msg = engine.validate_step(step)
        assert success is True
        assert msg == ""

    def test_file_exists_valid(self, tmp_path: Path) -> None:
        """Test file_exists validation with an existing file."""
        engine = TutorialEngine()
        test_file = tmp_path / "test.yaml"
        test_file.write_text("test: true")

        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation=f"file_exists:{test_file}",
        )
        success, msg = engine.validate_step(step)
        assert success is True
        assert msg == ""

    def test_file_exists_missing(self, tmp_path: Path) -> None:
        """Test file_exists validation with a missing file."""
        engine = TutorialEngine()
        missing = tmp_path / "nonexistent.yaml"

        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation=f"file_exists:{missing}",
        )
        success, msg = engine.validate_step(step)
        assert success is False
        assert "File not found" in msg

    def test_command_runs_success(self) -> None:
        """Test command_runs validation with a command that succeeds."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation="command_runs:true",
            action="check",
        )
        success, msg = engine.validate_step(step)
        assert success is True
        assert msg == ""

    def test_command_runs_failure(self) -> None:
        """Test command_runs validation with a command that fails."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation="command_runs:false",
            action="check",
        )
        success, msg = engine.validate_step(step)
        assert success is False
        assert "Command failed" in msg

    def test_command_runs_nonexistent(self) -> None:
        """Test command_runs validation with a nonexistent command."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation="command_runs:this_command_definitely_does_not_exist_12345",
            action="check",
        )
        success, _msg = engine.validate_step(step)
        assert success is False

    def test_unknown_validation_type(self) -> None:
        """Test that an unknown validation type fails."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation="unknown_type:value",
        )
        success, msg = engine.validate_step(step)
        assert success is False
        assert "Unknown validation type" in msg

    def test_file_exists_directory(self, tmp_path: Path) -> None:
        """Test that file_exists also works for directories."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation=f"file_exists:{tmp_path}",
        )
        success, _msg = engine.validate_step(step)
        assert success is True

    def test_command_runs_echo(self) -> None:
        """Test command_runs with an echo command."""
        engine = TutorialEngine()
        step = TutorialStep(
            id="x",
            title="X",
            content="X",
            validation="command_runs:echo hello",
            action="check",
        )
        success, _msg = engine.validate_step(step)
        assert success is True


# ---------------------------------------------------------------------------
# CLI tutorial commands tests
# ---------------------------------------------------------------------------


@cli_tutorial_available
class TestCLITutorialList:
    """Tests for the CLI 'tutorial list' command."""

    def test_tutorial_list_output(self) -> None:
        """Test that tutorial list shows all tutorials."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "list"])
        assert result.exit_code == 0
        assert "Getting Started" in result.output
        assert "Configuration" in result.output
        assert "Benchmarks" in result.output or "benchmarks" in result.output
        assert "Analytics" in result.output or "analytics" in result.output

    def test_tutorial_list_shows_difficulty(self) -> None:
        """Test that tutorial list includes difficulty labels."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "list"])
        assert result.exit_code == 0
        assert "beginner" in result.output.lower()
        assert "intermediate" in result.output.lower()
        assert "advanced" in result.output.lower()


@cli_tutorial_available
class TestCLITutorialStart:
    """Tests for the CLI 'tutorial start' command."""

    def test_start_valid_tutorial(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test starting a valid tutorial."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        monkeypatch.setenv("MCPBR_TUTORIAL_DIR", str(tmp_path))
        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "start", "getting-started"], input="\n" * 20)
        assert result.exit_code == 0
        assert "Getting Started" in result.output or "Welcome" in result.output

    def test_start_invalid_tutorial(self) -> None:
        """Test starting a nonexistent tutorial."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "start", "nonexistent"])
        assert result.exit_code != 0 or "not found" in result.output.lower()

    def test_start_with_reset(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test starting a tutorial with --reset flag."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        monkeypatch.setenv("MCPBR_TUTORIAL_DIR", str(tmp_path))
        runner = CliRunner()
        # Start once
        runner.invoke(main, ["tutorial", "start", "getting-started"], input="\n" * 20)
        # Start with reset
        result = runner.invoke(
            main, ["tutorial", "start", "getting-started", "--reset"], input="\n" * 20
        )
        assert result.exit_code == 0


@cli_tutorial_available
class TestCLITutorialProgress:
    """Tests for the CLI 'tutorial progress' command."""

    def test_progress_output(self) -> None:
        """Test that progress command runs without error."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "progress"])
        assert result.exit_code == 0


@cli_tutorial_available
class TestCLITutorialReset:
    """Tests for the CLI 'tutorial reset' command."""

    def test_reset_valid_tutorial(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resetting a tutorial."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        monkeypatch.setenv("MCPBR_TUTORIAL_DIR", str(tmp_path))
        runner = CliRunner()
        # Start first to create progress
        runner.invoke(main, ["tutorial", "start", "getting-started"], input="\n" * 20)
        # Reset
        result = runner.invoke(main, ["tutorial", "reset", "getting-started"])
        assert result.exit_code == 0

    def test_reset_nonexistent_tutorial(self) -> None:
        """Test resetting a nonexistent tutorial shows appropriate message."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["tutorial", "reset", "nonexistent"])
        # Should handle gracefully
        assert result.exit_code == 0 or "not found" in result.output.lower()
