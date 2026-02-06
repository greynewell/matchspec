"""Tests for reproducibility module."""

# ruff: noqa: N801

import json
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcpbr.reproducibility import (
    EnvironmentSnapshot,
    ReproducibilityConfig,
    ReproducibilityReport,
    capture_environment,
    generate_reproducibility_report,
    load_report,
    save_report,
    set_global_seed,
)


class TestEnvironmentSnapshot:
    """Tests for EnvironmentSnapshot dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating an EnvironmentSnapshot with all fields specified."""
        snapshot = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
            packages={"pytest": "8.0.0", "ruff": "0.4.0"},
            env_vars={"PYTHONHASHSEED": "42"},
            global_seed=42,
        )
        assert snapshot.python_version == "3.11.5"
        assert snapshot.platform == "Darwin"
        assert snapshot.platform_version == "23.5.0"
        assert snapshot.mcpbr_version == "0.5.0"
        assert snapshot.timestamp == "2024-06-01T12:00:00+00:00"
        assert snapshot.packages == {"pytest": "8.0.0", "ruff": "0.4.0"}
        assert snapshot.env_vars == {"PYTHONHASHSEED": "42"}
        assert snapshot.global_seed == 42

    def test_default_packages_is_empty_dict(self) -> None:
        """Test that packages defaults to an empty dict."""
        snapshot = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        assert snapshot.packages == {}

    def test_default_env_vars_is_empty_dict(self) -> None:
        """Test that env_vars defaults to an empty dict."""
        snapshot = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        assert snapshot.env_vars == {}

    def test_default_global_seed_is_none(self) -> None:
        """Test that global_seed defaults to None."""
        snapshot = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        assert snapshot.global_seed is None

    def test_defaults_do_not_share_mutable_state(self) -> None:
        """Test that default dicts are independent across instances."""
        snap_a = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        snap_b = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        snap_a.packages["new_pkg"] = "1.0"
        assert "new_pkg" not in snap_b.packages


class TestReproducibilityConfig:
    """Tests for ReproducibilityConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that all defaults match expected values."""
        config = ReproducibilityConfig()
        assert config.global_seed is None
        assert config.record_environment is True
        assert config.lock_file is None
        assert config.deterministic_mode is False

    def test_custom_global_seed(self) -> None:
        """Test setting a custom global seed."""
        config = ReproducibilityConfig(global_seed=12345)
        assert config.global_seed == 12345

    def test_custom_record_environment(self) -> None:
        """Test disabling record_environment."""
        config = ReproducibilityConfig(record_environment=False)
        assert config.record_environment is False

    def test_custom_lock_file(self) -> None:
        """Test setting a custom lock file path."""
        config = ReproducibilityConfig(lock_file="/tmp/repro.lock")
        assert config.lock_file == "/tmp/repro.lock"

    def test_custom_deterministic_mode(self) -> None:
        """Test enabling deterministic mode."""
        config = ReproducibilityConfig(deterministic_mode=True)
        assert config.deterministic_mode is True

    def test_all_custom_values(self) -> None:
        """Test creating config with all custom values."""
        config = ReproducibilityConfig(
            global_seed=99,
            record_environment=False,
            lock_file="/tmp/lock.json",
            deterministic_mode=True,
        )
        assert config.global_seed == 99
        assert config.record_environment is False
        assert config.lock_file == "/tmp/lock.json"
        assert config.deterministic_mode is True


class TestReproducibilityReport:
    """Tests for ReproducibilityReport dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating a ReproducibilityReport with all fields."""
        config = ReproducibilityConfig(global_seed=42)
        environment = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        report = ReproducibilityReport(
            config=config,
            environment=environment,
            checksum="abc123",
            warnings=["some warning"],
        )
        assert report.config is config
        assert report.environment is environment
        assert report.checksum == "abc123"
        assert report.warnings == ["some warning"]

    def test_default_checksum_is_empty(self) -> None:
        """Test that checksum defaults to an empty string."""
        config = ReproducibilityConfig()
        environment = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        report = ReproducibilityReport(config=config, environment=environment)
        assert report.checksum == ""

    def test_default_warnings_is_empty_list(self) -> None:
        """Test that warnings defaults to an empty list."""
        config = ReproducibilityConfig()
        environment = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        report = ReproducibilityReport(config=config, environment=environment)
        assert report.warnings == []

    def test_warnings_do_not_share_mutable_state(self) -> None:
        """Test that default warning lists are independent across instances."""
        config = ReproducibilityConfig()
        env = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        report_a = ReproducibilityReport(config=config, environment=env)
        report_b = ReproducibilityReport(config=config, environment=env)
        report_a.warnings.append("new warning")
        assert "new warning" not in report_b.warnings


class TestCaptureEnvironment:
    """Tests for capture_environment function."""

    def test_returns_environment_snapshot(self) -> None:
        """Test that capture_environment returns an EnvironmentSnapshot."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert isinstance(snapshot, EnvironmentSnapshot)

    def test_python_version_is_set(self) -> None:
        """Test that the python_version field is populated."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert snapshot.python_version
        assert len(snapshot.python_version) > 0

    def test_platform_is_set(self) -> None:
        """Test that the platform field is populated."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert snapshot.platform
        assert snapshot.platform in ("Darwin", "Linux", "Windows")

    def test_platform_version_is_set(self) -> None:
        """Test that the platform_version field is populated."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert snapshot.platform_version
        assert len(snapshot.platform_version) > 0

    def test_mcpbr_version_matches_arg(self) -> None:
        """Test that mcpbr_version matches the provided argument."""
        snapshot = capture_environment(mcpbr_version="1.2.3")
        assert snapshot.mcpbr_version == "1.2.3"

    def test_timestamp_is_iso_format(self) -> None:
        """Test that the timestamp is valid ISO 8601 format."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        # Should parse without error
        parsed = datetime.fromisoformat(snapshot.timestamp)
        assert parsed.tzinfo is not None

    def test_timestamp_is_recent(self) -> None:
        """Test that the timestamp is close to the current time."""
        before = datetime.now(timezone.utc)
        snapshot = capture_environment(mcpbr_version="0.5.0")
        after = datetime.now(timezone.utc)
        parsed = datetime.fromisoformat(snapshot.timestamp)
        assert before <= parsed <= after

    def test_with_seed_parameter(self) -> None:
        """Test that seed is recorded in the snapshot when provided."""
        snapshot = capture_environment(mcpbr_version="0.5.0", seed=42)
        assert snapshot.global_seed == 42

    def test_without_seed_parameter(self) -> None:
        """Test that global_seed is None when no seed is provided."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert snapshot.global_seed is None

    def test_packages_is_dict(self) -> None:
        """Test that packages field is a dict."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert isinstance(snapshot.packages, dict)

    def test_env_vars_is_dict(self) -> None:
        """Test that env_vars field is a dict."""
        snapshot = capture_environment(mcpbr_version="0.5.0")
        assert isinstance(snapshot.env_vars, dict)


class TestSetGlobalSeed:
    """Tests for set_global_seed function."""

    def test_sets_pythonhashseed_env_var(self) -> None:
        """Test that set_global_seed sets the PYTHONHASHSEED environment variable."""
        original = os.environ.get("PYTHONHASHSEED")
        try:
            set_global_seed(12345)
            assert os.environ["PYTHONHASHSEED"] == "12345"
        finally:
            if original is not None:
                os.environ["PYTHONHASHSEED"] = original
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_sets_random_seed_deterministic(self) -> None:
        """Test that set_global_seed produces deterministic random output."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            set_global_seed(42)
            values_a = [random.random() for _ in range(10)]

            set_global_seed(42)
            values_b = [random.random() for _ in range(10)]

            assert values_a == values_b
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_different_seeds_produce_different_output(self) -> None:
        """Test that different seeds produce different random output."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            set_global_seed(42)
            values_a = [random.random() for _ in range(10)]

            set_global_seed(99)
            values_b = [random.random() for _ in range(10)]

            assert values_a != values_b
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_seed_zero(self) -> None:
        """Test that seed 0 is a valid seed value."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            set_global_seed(0)
            assert os.environ["PYTHONHASHSEED"] == "0"
            # Should produce deterministic output
            set_global_seed(0)
            val_a = random.random()
            set_global_seed(0)
            val_b = random.random()
            assert val_a == val_b
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)


class TestGenerateReproducibilityReport:
    """Tests for generate_reproducibility_report function."""

    def test_returns_complete_report(self) -> None:
        """Test that the returned report has all fields populated."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            config = ReproducibilityConfig(global_seed=42)
            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
            assert isinstance(report, ReproducibilityReport)
            assert report.config is config
            assert isinstance(report.environment, EnvironmentSnapshot)
            assert report.checksum
            assert isinstance(report.warnings, list)
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_checksum_is_non_empty(self) -> None:
        """Test that the checksum is a non-empty hex string."""
        config = ReproducibilityConfig()
        report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
        assert len(report.checksum) == 64  # SHA256 hex digest is 64 chars
        assert all(c in "0123456789abcdef" for c in report.checksum)

    def test_warnings_when_deterministic_mode_without_seed(self) -> None:
        """Test that warnings are raised for deterministic mode without a seed."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ.pop("PYTHONHASHSEED", None)
            config = ReproducibilityConfig(deterministic_mode=True, global_seed=None)
            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
            assert len(report.warnings) >= 1
            warning_text = " ".join(report.warnings)
            assert "global_seed" in warning_text or "PYTHONHASHSEED" in warning_text
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_warning_about_pythonhashseed_unset(self) -> None:
        """Test that a specific warning is raised when PYTHONHASHSEED is not set."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            os.environ.pop("PYTHONHASHSEED", None)
            config = ReproducibilityConfig(deterministic_mode=True, global_seed=None)
            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
            hashseed_warnings = [w for w in report.warnings if "PYTHONHASHSEED" in w]
            assert len(hashseed_warnings) >= 1
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_no_warnings_when_properly_configured(self) -> None:
        """Test that no warnings are raised when deterministic mode is properly set up."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            config = ReproducibilityConfig(deterministic_mode=True, global_seed=42)
            # generate_reproducibility_report calls set_global_seed which sets PYTHONHASHSEED
            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
            assert report.warnings == []
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_no_warnings_when_deterministic_mode_off(self) -> None:
        """Test that no warnings are raised when deterministic mode is disabled."""
        config = ReproducibilityConfig(deterministic_mode=False)
        report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
        assert report.warnings == []

    def test_environment_mcpbr_version_matches(self) -> None:
        """Test that the environment snapshot has the correct mcpbr_version."""
        config = ReproducibilityConfig()
        report = generate_reproducibility_report(config, mcpbr_version="9.9.9")
        assert report.environment.mcpbr_version == "9.9.9"

    def test_seed_applied_to_environment(self) -> None:
        """Test that the global seed is recorded in the environment snapshot."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            config = ReproducibilityConfig(global_seed=777)
            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")
            assert report.environment.global_seed == 777
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)


class TestSaveAndLoadReport:
    """Tests for save_report and load_report functions."""

    def _make_report(self) -> ReproducibilityReport:
        """Create a sample report for testing."""
        config = ReproducibilityConfig(
            global_seed=42,
            record_environment=True,
            lock_file="/tmp/test.lock",
            deterministic_mode=True,
        )
        environment = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
            packages={"pytest": "8.0.0"},
            env_vars={"PYTHONHASHSEED": "42"},
            global_seed=42,
        )
        return ReproducibilityReport(
            config=config,
            environment=environment,
            checksum="a1b2c3d4e5f6",
            warnings=["test warning"],
        )

    def test_save_creates_file(self) -> None:
        """Test that save_report creates a file at the specified path."""
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            assert path.exists()

    def test_save_creates_valid_json(self) -> None:
        """Test that save_report writes valid JSON."""
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            data = json.loads(path.read_text())
            assert "config" in data
            assert "environment" in data
            assert "checksum" in data
            assert "warnings" in data

    def test_round_trip_preserves_data(self) -> None:
        """Test that saving and loading a report preserves all data."""
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            loaded = load_report(path)

            assert loaded.config.global_seed == report.config.global_seed
            assert loaded.config.record_environment == report.config.record_environment
            assert loaded.config.lock_file == report.config.lock_file
            assert loaded.config.deterministic_mode == report.config.deterministic_mode
            assert loaded.environment.python_version == report.environment.python_version
            assert loaded.environment.platform == report.environment.platform
            assert loaded.environment.platform_version == report.environment.platform_version
            assert loaded.environment.mcpbr_version == report.environment.mcpbr_version
            assert loaded.environment.timestamp == report.environment.timestamp
            assert loaded.environment.packages == report.environment.packages
            assert loaded.environment.env_vars == report.environment.env_vars
            assert loaded.environment.global_seed == report.environment.global_seed
            assert loaded.checksum == report.checksum
            assert loaded.warnings == report.warnings

    def test_load_recreates_correct_types(self) -> None:
        """Test that load_report returns correctly typed objects."""
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            loaded = load_report(path)

            assert isinstance(loaded, ReproducibilityReport)
            assert isinstance(loaded.config, ReproducibilityConfig)
            assert isinstance(loaded.environment, EnvironmentSnapshot)
            assert isinstance(loaded.checksum, str)
            assert isinstance(loaded.warnings, list)

    def test_save_creates_parent_dirs(self) -> None:
        """Test that save_report creates parent directories if they do not exist."""
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "report.json"
            save_report(report, path)
            assert path.exists()

    def test_load_nonexistent_file_raises(self) -> None:
        """Test that loading a nonexistent file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"
            with pytest.raises(FileNotFoundError):
                load_report(path)

    def test_load_invalid_json_raises(self) -> None:
        """Test that loading invalid JSON raises json.JSONDecodeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("not valid json {{{")
            with pytest.raises(json.JSONDecodeError):
                load_report(path)

    def test_round_trip_with_none_seed(self) -> None:
        """Test round-trip when global_seed is None."""
        config = ReproducibilityConfig(global_seed=None)
        env = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Linux",
            platform_version="5.15.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
            global_seed=None,
        )
        report = ReproducibilityReport(config=config, environment=env, checksum="deadbeef")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            loaded = load_report(path)
            assert loaded.config.global_seed is None
            assert loaded.environment.global_seed is None

    def test_round_trip_with_empty_warnings(self) -> None:
        """Test round-trip when warnings list is empty."""
        config = ReproducibilityConfig()
        env = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        report = ReproducibilityReport(config=config, environment=env, checksum="abcdef")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            loaded = load_report(path)
            assert loaded.warnings == []


class TestReproducibilityIntegration:
    """Integration tests for the full reproducibility workflow."""

    def test_full_workflow(self) -> None:
        """Test config -> capture -> report -> save -> load -> verify checksum."""
        original_hashseed = os.environ.get("PYTHONHASHSEED")
        try:
            config = ReproducibilityConfig(
                global_seed=42,
                record_environment=True,
                deterministic_mode=True,
            )

            report = generate_reproducibility_report(config, mcpbr_version="0.5.0")

            assert isinstance(report, ReproducibilityReport)
            assert report.checksum
            assert report.warnings == []
            assert report.environment.global_seed == 42
            assert report.environment.mcpbr_version == "0.5.0"

            with tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "integration_report.json"
                save_report(report, path)
                loaded = load_report(path)

                assert loaded.checksum == report.checksum
                assert loaded.config.global_seed == 42
                assert loaded.config.deterministic_mode is True
                assert loaded.environment.mcpbr_version == "0.5.0"
                assert loaded.environment.global_seed == 42
                assert loaded.warnings == []
        finally:
            if original_hashseed is not None:
                os.environ["PYTHONHASHSEED"] = original_hashseed
            else:
                os.environ.pop("PYTHONHASHSEED", None)

    def test_deterministic_report_checksums_stable(self) -> None:
        """Test that reports with the same environment produce the same checksum."""
        config = ReproducibilityConfig()
        env = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
            packages={"pytest": "8.0.0"},
            env_vars={"PYTHONHASHSEED": "42"},
            global_seed=42,
        )

        from mcpbr.reproducibility import _compute_checksum

        checksum_a = _compute_checksum(config, env)
        checksum_b = _compute_checksum(config, env)
        assert checksum_a == checksum_b

    def test_different_environments_produce_different_checksums(self) -> None:
        """Test that different environment snapshots produce different checksums."""
        config = ReproducibilityConfig()
        env_a = EnvironmentSnapshot(
            python_version="3.11.5",
            platform="Darwin",
            platform_version="23.5.0",
            mcpbr_version="0.5.0",
            timestamp="2024-06-01T12:00:00+00:00",
        )
        env_b = EnvironmentSnapshot(
            python_version="3.12.0",
            platform="Linux",
            platform_version="5.15.0",
            mcpbr_version="0.6.0",
            timestamp="2024-07-01T12:00:00+00:00",
        )

        from mcpbr.reproducibility import _compute_checksum

        checksum_a = _compute_checksum(config, env_a)
        checksum_b = _compute_checksum(config, env_b)
        assert checksum_a != checksum_b

    def test_workflow_without_deterministic_mode(self) -> None:
        """Test the workflow with deterministic mode disabled and no seed."""
        config = ReproducibilityConfig(
            deterministic_mode=False,
            global_seed=None,
        )
        report = generate_reproducibility_report(config, mcpbr_version="0.5.0")

        assert report.warnings == []
        assert report.checksum
        assert report.environment.global_seed is None

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_report(report, path)
            loaded = load_report(path)
            assert loaded.checksum == report.checksum
