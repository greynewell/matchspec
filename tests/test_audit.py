"""Tests for audit logging module."""

# ruff: noqa: N801

import csv
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcpbr.audit import (
    AuditAction,
    AuditConfig,
    AuditEvent,
    AuditLogger,
    load_audit_log,
    load_audit_log_jsonl,
)


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_config_loaded_value(self) -> None:
        """Test CONFIG_LOADED enum value."""
        assert AuditAction.CONFIG_LOADED.value == "config_loaded"

    def test_config_validated_value(self) -> None:
        """Test CONFIG_VALIDATED enum value."""
        assert AuditAction.CONFIG_VALIDATED.value == "config_validated"

    def test_benchmark_started_value(self) -> None:
        """Test BENCHMARK_STARTED enum value."""
        assert AuditAction.BENCHMARK_STARTED.value == "benchmark_started"

    def test_benchmark_completed_value(self) -> None:
        """Test BENCHMARK_COMPLETED enum value."""
        assert AuditAction.BENCHMARK_COMPLETED.value == "benchmark_completed"

    def test_benchmark_failed_value(self) -> None:
        """Test BENCHMARK_FAILED enum value."""
        assert AuditAction.BENCHMARK_FAILED.value == "benchmark_failed"

    def test_task_started_value(self) -> None:
        """Test TASK_STARTED enum value."""
        assert AuditAction.TASK_STARTED.value == "task_started"

    def test_task_completed_value(self) -> None:
        """Test TASK_COMPLETED enum value."""
        assert AuditAction.TASK_COMPLETED.value == "task_completed"

    def test_task_failed_value(self) -> None:
        """Test TASK_FAILED enum value."""
        assert AuditAction.TASK_FAILED.value == "task_failed"

    def test_task_skipped_value(self) -> None:
        """Test TASK_SKIPPED enum value."""
        assert AuditAction.TASK_SKIPPED.value == "task_skipped"

    def test_result_saved_value(self) -> None:
        """Test RESULT_SAVED enum value."""
        assert AuditAction.RESULT_SAVED.value == "result_saved"

    def test_result_exported_value(self) -> None:
        """Test RESULT_EXPORTED enum value."""
        assert AuditAction.RESULT_EXPORTED.value == "result_exported"

    def test_data_accessed_value(self) -> None:
        """Test DATA_ACCESSED enum value."""
        assert AuditAction.DATA_ACCESSED.value == "data_accessed"

    def test_data_deleted_value(self) -> None:
        """Test DATA_DELETED enum value."""
        assert AuditAction.DATA_DELETED.value == "data_deleted"

    def test_all_enum_members_count(self) -> None:
        """Test that the enum has the expected number of members."""
        assert len(AuditAction) == 17


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating an AuditEvent with all fields specified."""
        event = AuditEvent(
            timestamp="2024-01-15T10:30:00+00:00",
            action=AuditAction.BENCHMARK_STARTED,
            actor="user",
            resource="config.yaml",
            result="success",
            details={"model": "claude-sonnet-4-5-20250929"},
            event_id="abc-123",
            checksum="deadbeef",
        )
        assert event.timestamp == "2024-01-15T10:30:00+00:00"
        assert event.action == AuditAction.BENCHMARK_STARTED
        assert event.actor == "user"
        assert event.resource == "config.yaml"
        assert event.result == "success"
        assert event.details == {"model": "claude-sonnet-4-5-20250929"}
        assert event.event_id == "abc-123"
        assert event.checksum == "deadbeef"

    def test_event_id_auto_generated(self) -> None:
        """Test that event_id is automatically set when not provided."""
        event = AuditEvent(
            timestamp="2024-01-15T10:30:00+00:00",
            action=AuditAction.CONFIG_LOADED,
            actor="system",
            resource="config.yaml",
            result="success",
        )
        assert event.event_id != ""
        assert len(event.event_id) > 0

    def test_event_id_is_unique(self) -> None:
        """Test that auto-generated event_ids are unique across instances."""
        event1 = AuditEvent(
            timestamp="2024-01-15T10:30:00+00:00",
            action=AuditAction.CONFIG_LOADED,
            actor="system",
            resource="config.yaml",
            result="success",
        )
        event2 = AuditEvent(
            timestamp="2024-01-15T10:30:01+00:00",
            action=AuditAction.CONFIG_LOADED,
            actor="system",
            resource="config.yaml",
            result="success",
        )
        assert event1.event_id != event2.event_id

    def test_defaults(self) -> None:
        """Test default values for optional fields."""
        event = AuditEvent(
            timestamp="2024-01-15T10:30:00+00:00",
            action=AuditAction.TASK_STARTED,
            actor="system",
            resource="task-1",
            result="success",
        )
        assert event.details == {}
        assert event.checksum == ""


class TestAuditConfig:
    """Tests for AuditConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that AuditConfig has the expected default values."""
        config = AuditConfig()
        assert config.enabled is False
        assert config.log_file is None
        assert config.events == ["all"]
        assert config.tamper_proof is True
        assert config.retention_days is None

    def test_custom_values(self) -> None:
        """Test creating AuditConfig with custom values."""
        config = AuditConfig(
            enabled=True,
            log_file="/tmp/audit.log",
            events=["CONFIG_LOADED", "BENCHMARK_STARTED"],
            tamper_proof=False,
            retention_days=30,
        )
        assert config.enabled is True
        assert config.log_file == "/tmp/audit.log"
        assert config.events == ["CONFIG_LOADED", "BENCHMARK_STARTED"]
        assert config.tamper_proof is False
        assert config.retention_days == 30

    def test_enabled_true(self) -> None:
        """Test setting enabled to True explicitly."""
        config = AuditConfig(enabled=True)
        assert config.enabled is True

    def test_events_list_independent(self) -> None:
        """Test that default events lists are independent across instances."""
        config1 = AuditConfig()
        config2 = AuditConfig()
        config1.events.append("EXTRA")
        assert "EXTRA" not in config2.events


class TestHMACKeyHandling:
    """Tests for HMAC key security fixes (#419)."""

    def test_explicit_hmac_key_parameter(self) -> None:
        """Test that AuditLogger accepts an explicit hmac_key parameter."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        secret_key = os.urandom(32)
        logger = AuditLogger(config, hmac_key=secret_key)

        event = logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        assert event is not None
        assert event.checksum != ""

        # Verify integrity works with the explicit key
        valid, errors = logger.verify_integrity()
        assert valid is True
        assert errors == []

    def test_hmac_key_from_environment_variable(self) -> None:
        """Test that MCPBR_AUDIT_HMAC_KEY env var is used when no explicit key given."""
        import base64

        secret = os.urandom(32)
        encoded = base64.b64encode(secret).decode()

        config = AuditConfig(enabled=True, tamper_proof=True)
        with patch.dict(os.environ, {"MCPBR_AUDIT_HMAC_KEY": encoded}):
            logger = AuditLogger(config)

        event = logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        assert event is not None
        assert event.checksum != ""

        # Key should match what we provided via env var
        assert logger._hmac_key == secret

    def test_no_key_generates_random(self) -> None:
        """Test that when no explicit key and no env var, a random key is generated."""
        config = AuditConfig(enabled=True, tamper_proof=True)

        with patch.dict(os.environ, {}, clear=False):
            # Ensure env var is NOT set
            os.environ.pop("MCPBR_AUDIT_HMAC_KEY", None)
            logger1 = AuditLogger(config)
            logger2 = AuditLogger(config)

        # Two loggers with same config should get DIFFERENT random keys
        assert logger1._hmac_key != logger2._hmac_key

    def test_random_key_not_derived_from_config(self) -> None:
        """Test that the default key is NOT deterministically derived from config."""
        config = AuditConfig(enabled=True, tamper_proof=True)

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCPBR_AUDIT_HMAC_KEY", None)
            logger = AuditLogger(config)

        # The old behavior derived the key from config via sha256.
        # Verify we do NOT get that deterministic value.
        import hashlib
        from dataclasses import asdict

        old_deterministic_key = hashlib.sha256(
            json.dumps(asdict(config), sort_keys=True).encode()
        ).digest()
        assert logger._hmac_key != old_deterministic_key

    def test_explicit_key_overrides_env_var(self) -> None:
        """Test that explicit hmac_key parameter takes priority over env var."""
        import base64

        env_secret = os.urandom(32)
        explicit_secret = os.urandom(32)
        encoded = base64.b64encode(env_secret).decode()

        config = AuditConfig(enabled=True, tamper_proof=True)
        with patch.dict(os.environ, {"MCPBR_AUDIT_HMAC_KEY": encoded}):
            logger = AuditLogger(config, hmac_key=explicit_secret)

        assert logger._hmac_key == explicit_secret
        assert logger._hmac_key != env_secret


class TestVerifyIntegrityChaining:
    """Tests for verify_integrity chaining on recomputed checksums (#419).

    When verify_integrity chains on the recomputed expected checksum (not the
    stored one), tampering with event DATA causes a cascade: the recomputed
    checksum for the tampered event differs from the original, and since all
    subsequent events were chained on the original checksum, they also fail.
    """

    def test_tampered_data_in_middle_invalidates_all_subsequent(self) -> None:
        """Test that modifying event data at index 1 of 5 causes events 1-4 to fail."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        for i in range(5):
            logger.log(action=AuditAction.CONFIG_LOADED, resource=f"r{i}")

        # Tamper with the second event's DATA (not just checksum)
        logger._events[1].resource = "TAMPERED"

        valid, errors = logger.verify_integrity()
        assert valid is False
        # The tampered event AND all subsequent events should fail because
        # chaining on recomputed expected checksums means the altered expected
        # value for event 1 cascades through events 2, 3, 4
        assert len(errors) == 4  # events 1, 2, 3, 4 all fail

        # Verify error messages reference the correct event indices
        error_indices = []
        for error in errors:
            idx = int(error.split("Event ")[1].split(" ")[0])
            error_indices.append(idx)
        assert error_indices == [1, 2, 3, 4]

    def test_tampered_data_in_first_event_invalidates_all(self) -> None:
        """Test that modifying event[0] data causes ALL events to fail verification."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        for i in range(3):
            logger.log(action=AuditAction.CONFIG_LOADED, resource=f"r{i}")

        # Tamper with the first event's data
        logger._events[0].resource = "TAMPERED"

        valid, errors = logger.verify_integrity()
        assert valid is False
        assert len(errors) == 3  # All events should fail

    def test_tampered_checksum_only_affects_that_event(self) -> None:
        """Test that replacing only a checksum (not data) flags just that event.

        When chaining on recomputed expected checksums, changing a stored
        checksum without touching data only causes a mismatch for that single
        event. The recomputed expected checksum is still the correct one, so
        subsequent events verify against the correct chain.
        """
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        for i in range(3):
            logger.log(action=AuditAction.CONFIG_LOADED, resource=f"r{i}")

        # Tamper with only the checksum of event 1 (not its data)
        logger._events[1].checksum = "tampered_value"

        valid, errors = logger.verify_integrity()
        assert valid is False
        assert len(errors) == 1
        assert "Event 1" in errors[0]

    def test_tampered_last_event_data_only_affects_last(self) -> None:
        """Test that tampering the last event's data only reports one error."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        for i in range(3):
            logger.log(action=AuditAction.CONFIG_LOADED, resource=f"r{i}")

        # Tamper with only the last event's data
        logger._events[2].resource = "TAMPERED"

        valid, errors = logger.verify_integrity()
        assert valid is False
        assert len(errors) == 1
        assert "Event 2" in errors[0]


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_log_creates_event(self) -> None:
        """Test that log() creates and returns an AuditEvent."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        event = logger.log(
            action=AuditAction.CONFIG_LOADED,
            resource="config.yaml",
        )

        assert isinstance(event, AuditEvent)
        assert event.action == AuditAction.CONFIG_LOADED
        assert event.resource == "config.yaml"
        assert event.result == "success"
        assert event.actor == "system"

    def test_log_disabled_returns_none(self) -> None:
        """Test that logging when disabled returns None."""
        config = AuditConfig(enabled=False)
        logger = AuditLogger(config)

        event = logger.log(
            action=AuditAction.CONFIG_LOADED,
            resource="config.yaml",
        )

        assert event is None
        assert len(logger.get_events()) == 0

    def test_log_with_details(self) -> None:
        """Test that details dict is passed through to the event."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        details = {"model": "gpt-4", "token_count": 1500}
        event = logger.log(
            action=AuditAction.BENCHMARK_STARTED,
            resource="benchmark-1",
            details=details,
        )

        assert event.details == details
        assert event.details["model"] == "gpt-4"
        assert event.details["token_count"] == 1500

    def test_log_with_custom_actor_and_result(self) -> None:
        """Test logging with custom actor and result values."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        event = logger.log(
            action=AuditAction.BENCHMARK_FAILED,
            resource="benchmark-1",
            result="failure",
            actor="benchmark-runner",
        )

        assert event.actor == "benchmark-runner"
        assert event.result == "failure"

    def test_get_events_no_filter(self) -> None:
        """Test that get_events() returns all events when no filter is applied."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")
        logger.log(action=AuditAction.TASK_COMPLETED, resource="task-1")

        events = logger.get_events()
        assert len(events) == 3

    def test_get_events_with_filter(self) -> None:
        """Test that get_events() filters by action type correctly."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")
        logger.log(action=AuditAction.CONFIG_LOADED, resource="config2.yaml")
        logger.log(action=AuditAction.TASK_COMPLETED, resource="task-1")

        config_events = logger.get_events(action=AuditAction.CONFIG_LOADED)
        assert len(config_events) == 2
        for e in config_events:
            assert e.action == AuditAction.CONFIG_LOADED

    def test_get_events_filter_returns_empty(self) -> None:
        """Test that filtering for an absent action returns an empty list."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")

        events = logger.get_events(action=AuditAction.DATA_DELETED)
        assert events == []

    def test_get_events_returns_copy(self) -> None:
        """Test that get_events returns a copy, not the internal list."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        events = logger.get_events()
        events.clear()

        assert len(logger.get_events()) == 1

    def test_should_log_all(self) -> None:
        """Test that events=['all'] logs all action types."""
        config = AuditConfig(enabled=True, events=["all"])
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="r2")
        logger.log(action=AuditAction.TASK_FAILED, resource="r3")
        logger.log(action=AuditAction.DATA_DELETED, resource="r4")

        assert len(logger.get_events()) == 4

    def test_should_log_specific_events(self) -> None:
        """Test that only explicitly listed event types are logged."""
        config = AuditConfig(
            enabled=True,
            events=["CONFIG_LOADED", "BENCHMARK_STARTED"],
        )
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="r2")
        logger.log(action=AuditAction.TASK_FAILED, resource="r3")
        logger.log(action=AuditAction.DATA_DELETED, resource="r4")

        events = logger.get_events()
        assert len(events) == 2
        actions = {e.action for e in events}
        assert actions == {AuditAction.CONFIG_LOADED, AuditAction.BENCHMARK_STARTED}

    def test_export_json(self) -> None:
        """Test that export_json creates a valid JSON file with all events."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            logger.export_json(path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["action"] == "config_loaded"
            assert data[0]["resource"] == "config.yaml"
            assert data[1]["action"] == "benchmark_started"
            assert "event_id" in data[0]
            assert "timestamp" in data[0]
            assert "checksum" in data[0]

    def test_export_json_creates_parent_dirs(self) -> None:
        """Test that export_json creates parent directories if needed."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)
        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "audit.json"
            logger.export_json(path)
            assert path.exists()

    def test_export_csv(self) -> None:
        """Test that export_csv creates a valid CSV file with headers and data."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(
            action=AuditAction.BENCHMARK_COMPLETED,
            resource="bench-1",
            details={"score": 95},
        )
        logger.log(
            action=AuditAction.RESULT_SAVED,
            resource="results.json",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.csv"
            logger.export_csv(path)

            assert path.exists()
            with path.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            expected_headers = {
                "event_id",
                "timestamp",
                "action",
                "actor",
                "resource",
                "result",
                "details",
                "checksum",
            }
            assert set(rows[0].keys()) == expected_headers
            assert rows[0]["action"] == "benchmark_completed"
            assert rows[0]["resource"] == "bench-1"
            assert rows[1]["action"] == "result_saved"

    def test_export_csv_details_is_json(self) -> None:
        """Test that the details column in CSV is a valid JSON string."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        logger.log(
            action=AuditAction.TASK_COMPLETED,
            resource="task-1",
            details={"duration": 5.2, "retries": 0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.csv"
            logger.export_csv(path)

            with path.open() as f:
                reader = csv.DictReader(f)
                row = next(reader)

            details = json.loads(row["details"])
            assert details["duration"] == 5.2
            assert details["retries"] == 0

    def test_export_csv_creates_parent_dirs(self) -> None:
        """Test that export_csv creates parent directories if needed."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)
        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "deep" / "audit.csv"
            logger.export_csv(path)
            assert path.exists()

    def test_verify_integrity_valid(self) -> None:
        """Test that integrity verification passes for unmodified events."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")
        logger.log(action=AuditAction.TASK_COMPLETED, resource="task-1")

        valid, errors = logger.verify_integrity()
        assert valid is True
        assert errors == []

    def test_verify_integrity_tampered(self) -> None:
        """Test that integrity verification detects a tampered checksum."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")

        # Tamper with the first event's checksum
        logger._events[0].checksum = "tampered_value"

        valid, errors = logger.verify_integrity()
        assert valid is False
        assert len(errors) >= 1
        assert "checksum mismatch" in errors[0]

    def test_verify_integrity_tampered_cascades(self) -> None:
        """Test that tampering with event data causes downstream verification failures."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="r2")
        logger.log(action=AuditAction.TASK_COMPLETED, resource="r3")

        # Tamper with the first event's data (not just checksum)
        logger._events[0].resource = "TAMPERED"

        valid, errors = logger.verify_integrity()
        assert valid is False
        # Tampering the first event's data should cascade to affect later
        # verifications because chaining on recomputed expected checksums
        # means the altered expected value propagates through the chain
        assert len(errors) >= 2

    def test_verify_integrity_no_tamper_proof(self) -> None:
        """Test that verify_integrity returns valid when tamper_proof is disabled."""
        config = AuditConfig(enabled=True, tamper_proof=False)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")

        valid, errors = logger.verify_integrity()
        assert valid is True
        assert errors == []

    def test_log_writes_to_file(self) -> None:
        """Test that events are written to disk when log_file is configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "audit.log")
            config = AuditConfig(enabled=True, log_file=log_file)
            logger = AuditLogger(config)

            logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
            logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")

            log_path = Path(log_file)
            assert log_path.exists()

            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 2

            entry1 = json.loads(lines[0])
            assert entry1["action"] == "config_loaded"
            assert entry1["resource"] == "config.yaml"

            entry2 = json.loads(lines[1])
            assert entry2["action"] == "benchmark_started"

    def test_log_writes_to_file_creates_parent_dirs(self) -> None:
        """Test that log_file writing creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "nested" / "dir" / "audit.log")
            config = AuditConfig(enabled=True, log_file=log_file)
            logger = AuditLogger(config)

            logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")

            assert Path(log_file).exists()

    def test_checksum_chain(self) -> None:
        """Test that each event's checksum depends on the previous event's checksum."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="r2")
        logger.log(action=AuditAction.TASK_COMPLETED, resource="r3")

        events = logger.get_events()
        # Each event should have a non-empty checksum
        for event in events:
            assert event.checksum != ""

        # All checksums should be distinct (different events produce different hashes)
        checksums = [e.checksum for e in events]
        assert len(set(checksums)) == 3

    def test_checksum_empty_without_tamper_proof(self) -> None:
        """Test that checksums are empty when tamper_proof is disabled."""
        config = AuditConfig(enabled=True, tamper_proof=False)
        logger = AuditLogger(config)

        event = logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        assert event.checksum == ""

    def test_export_json_empty_logger(self) -> None:
        """Test that export_json works when no events have been logged."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            logger.export_json(path)

            data = json.loads(path.read_text())
            assert data == []

    def test_export_csv_empty_logger(self) -> None:
        """Test that export_csv works when no events have been logged."""
        config = AuditConfig(enabled=True)
        logger = AuditLogger(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.csv"
            logger.export_csv(path)

            with path.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert rows == []


class TestLoadAuditLog:
    """Tests for load_audit_log function."""

    def test_load_from_json_file(self) -> None:
        """Test loading audit events from a JSON file."""
        events_data = [
            {
                "timestamp": "2024-01-15T10:30:00+00:00",
                "action": "config_loaded",
                "actor": "system",
                "resource": "config.yaml",
                "result": "success",
                "details": {},
                "event_id": "evt-001",
                "checksum": "abc123",
            },
            {
                "timestamp": "2024-01-15T10:31:00+00:00",
                "action": "benchmark_started",
                "actor": "user",
                "resource": "bench-1",
                "result": "success",
                "details": {"model": "gpt-4"},
                "event_id": "evt-002",
                "checksum": "def456",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            path.write_text(json.dumps(events_data))

            loaded = load_audit_log(path)

            assert len(loaded) == 2
            assert isinstance(loaded[0], AuditEvent)
            assert loaded[0].action == AuditAction.CONFIG_LOADED
            assert loaded[0].actor == "system"
            assert loaded[0].resource == "config.yaml"
            assert loaded[0].event_id == "evt-001"
            assert loaded[0].checksum == "abc123"
            assert loaded[1].action == AuditAction.BENCHMARK_STARTED
            assert loaded[1].details == {"model": "gpt-4"}

    def test_load_empty_list(self) -> None:
        """Test loading from a JSON file containing an empty array."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            path.write_text("[]")

            loaded = load_audit_log(path)
            assert loaded == []

    def test_load_missing_optional_fields(self) -> None:
        """Test loading events with missing optional fields uses defaults."""
        events_data = [
            {
                "timestamp": "2024-01-15T10:30:00+00:00",
                "action": "task_started",
                "actor": "system",
                "resource": "task-1",
                "result": "success",
                "event_id": "evt-001",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            path.write_text(json.dumps(events_data))

            loaded = load_audit_log(path)
            assert loaded[0].details == {}
            assert loaded[0].checksum == ""

    def test_load_nonexistent_file_raises(self) -> None:
        """Test that loading from a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_audit_log(Path("/tmp/nonexistent_audit_file_xyz.json"))

    def test_load_invalid_json_raises(self) -> None:
        """Test that loading invalid JSON raises JSONDecodeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("not valid json {{{")

            with pytest.raises(json.JSONDecodeError):
                load_audit_log(path)


class TestLoadAuditLogJsonl:
    """Tests for load_audit_log_jsonl function."""

    def test_load_jsonl_from_file(self) -> None:
        """Test loading audit events from a JSONL file."""
        lines = [
            json.dumps(
                {
                    "timestamp": "2024-01-15T10:30:00+00:00",
                    "action": "config_loaded",
                    "actor": "system",
                    "resource": "config.yaml",
                    "result": "success",
                    "details": {},
                    "event_id": "evt-001",
                    "checksum": "abc123",
                }
            ),
            json.dumps(
                {
                    "timestamp": "2024-01-15T10:31:00+00:00",
                    "action": "benchmark_started",
                    "actor": "user",
                    "resource": "bench-1",
                    "result": "success",
                    "details": {"model": "gpt-4"},
                    "event_id": "evt-002",
                    "checksum": "def456",
                }
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"
            path.write_text("\n".join(lines) + "\n")

            loaded = load_audit_log_jsonl(path)

            assert len(loaded) == 2
            assert loaded[0].action == AuditAction.CONFIG_LOADED
            assert loaded[0].event_id == "evt-001"
            assert loaded[1].action == AuditAction.BENCHMARK_STARTED
            assert loaded[1].details == {"model": "gpt-4"}

    def test_load_jsonl_empty_file(self) -> None:
        """Test loading from an empty JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.jsonl"
            path.write_text("")

            loaded = load_audit_log_jsonl(path)
            assert loaded == []

    def test_load_jsonl_round_trip_with_logger(self) -> None:
        """Test that events written by AuditLogger can be loaded by load_audit_log_jsonl."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "audit.jsonl")
            config = AuditConfig(enabled=True, log_file=log_file, tamper_proof=True)
            logger = AuditLogger(config)

            logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
            logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")

            loaded = load_audit_log_jsonl(Path(log_file))
            assert len(loaded) == 2
            assert loaded[0].action == AuditAction.CONFIG_LOADED
            assert loaded[1].action == AuditAction.BENCHMARK_STARTED
            assert loaded[0].checksum != ""
            assert loaded[1].checksum != ""

    def test_load_jsonl_nonexistent_file_raises(self) -> None:
        """Test that loading from a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_audit_log_jsonl(Path("/tmp/nonexistent_jsonl_xyz.jsonl"))


class TestAuditIntegration:
    """Integration tests for the full audit workflow."""

    def test_full_workflow_log_export_load_verify(self) -> None:
        """Test the complete workflow: create logger, log events, export, load, verify."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        # Log several events
        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(
            action=AuditAction.BENCHMARK_STARTED,
            resource="bench-1",
            actor="benchmark-runner",
            details={"model": "claude-sonnet-4-5-20250929"},
        )
        logger.log(
            action=AuditAction.TASK_COMPLETED,
            resource="task-1",
            details={"duration_ms": 1200},
        )
        logger.log(
            action=AuditAction.BENCHMARK_COMPLETED,
            resource="bench-1",
            details={"total_tasks": 10, "passed": 8},
        )

        # Verify integrity before export
        valid, errors = logger.verify_integrity()
        assert valid is True
        assert errors == []

        # Export to JSON and load back
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "audit.json"
            logger.export_json(json_path)

            loaded_events = load_audit_log(json_path)
            assert len(loaded_events) == 4
            assert loaded_events[0].action == AuditAction.CONFIG_LOADED
            assert loaded_events[1].action == AuditAction.BENCHMARK_STARTED
            assert loaded_events[1].details["model"] == "claude-sonnet-4-5-20250929"
            assert loaded_events[2].action == AuditAction.TASK_COMPLETED
            assert loaded_events[3].action == AuditAction.BENCHMARK_COMPLETED

    def test_export_json_and_csv_consistency(self) -> None:
        """Test that JSON and CSV exports contain the same event data."""
        config = AuditConfig(enabled=True, tamper_proof=True)
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
        logger.log(action=AuditAction.TASK_FAILED, resource="task-1", result="failure")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "audit.json"
            csv_path = Path(tmpdir) / "audit.csv"
            logger.export_json(json_path)
            logger.export_csv(csv_path)

            json_data = json.loads(json_path.read_text())
            with csv_path.open() as f:
                csv_rows = list(csv.DictReader(f))

            assert len(json_data) == len(csv_rows) == 2

            for json_entry, csv_row in zip(json_data, csv_rows):
                assert json_entry["event_id"] == csv_row["event_id"]
                assert json_entry["action"] == csv_row["action"]
                assert json_entry["resource"] == csv_row["resource"]
                assert json_entry["result"] == csv_row["result"]

    def test_filtered_logging_then_export(self) -> None:
        """Test that only filtered events appear in exports."""
        config = AuditConfig(
            enabled=True,
            events=["CONFIG_LOADED", "RESULT_SAVED"],
            tamper_proof=True,
        )
        logger = AuditLogger(config)

        logger.log(action=AuditAction.CONFIG_LOADED, resource="r1")
        logger.log(action=AuditAction.BENCHMARK_STARTED, resource="r2")
        logger.log(action=AuditAction.RESULT_SAVED, resource="r3")
        logger.log(action=AuditAction.DATA_DELETED, resource="r4")

        # Only CONFIG_LOADED and RESULT_SAVED should be stored
        events = logger.get_events()
        assert len(events) == 2

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"
            logger.export_json(path)

            data = json.loads(path.read_text())
            assert len(data) == 2
            assert data[0]["action"] == "config_loaded"
            assert data[1]["action"] == "result_saved"

    def test_log_to_file_then_verify(self) -> None:
        """Test logging to file and verifying integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "audit.log")
            config = AuditConfig(enabled=True, log_file=log_file, tamper_proof=True)
            logger = AuditLogger(config)

            logger.log(action=AuditAction.CONFIG_LOADED, resource="config.yaml")
            logger.log(action=AuditAction.BENCHMARK_STARTED, resource="bench-1")
            logger.log(action=AuditAction.BENCHMARK_COMPLETED, resource="bench-1")

            # Verify in-memory integrity
            valid, errors = logger.verify_integrity()
            assert valid is True

            # Verify file was written
            log_path = Path(log_file)
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 3

            # Each line should be valid JSON
            for line in lines:
                entry = json.loads(line)
                assert "event_id" in entry
                assert "action" in entry
                assert "checksum" in entry
