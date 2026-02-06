"""Audit logging for mcpbr.

Provides tamper-evident audit logging with HMAC chain integrity verification,
configurable event filtering, and export to JSON and CSV formats.
"""

import csv
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class AuditAction(Enum):
    """Types of auditable actions in the system."""

    CONFIG_LOADED = "config_loaded"
    CONFIG_VALIDATED = "config_validated"
    BENCHMARK_STARTED = "benchmark_started"
    BENCHMARK_COMPLETED = "benchmark_completed"
    BENCHMARK_FAILED = "benchmark_failed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_SKIPPED = "task_skipped"
    RESULT_SAVED = "result_saved"
    RESULT_EXPORTED = "result_exported"
    DATA_ACCESSED = "data_accessed"
    DATA_DELETED = "data_deleted"


@dataclass
class AuditEvent:
    """A single audit log event.

    Attributes:
        timestamp: ISO 8601 timestamp of when the event occurred.
        action: The type of action that was performed.
        actor: Who performed the action (e.g., "system", "user", "benchmark-runner").
        resource: What was acted on (e.g., "config.yaml", "task-123").
        result: Outcome of the action, typically "success" or "failure".
        details: Additional context about the event.
        event_id: Unique UUID identifying this event.
        checksum: HMAC for tamper detection, computed after creation.
    """

    timestamp: str
    action: AuditAction
    actor: str
    resource: str
    result: str
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    checksum: str = ""


@dataclass
class AuditConfig:
    """Configuration for audit logging.

    Attributes:
        enabled: Whether audit logging is active.
        log_file: Path to the audit log file. None means no file output.
        events: Which event types to log. A list of AuditAction names, or
            ["all"] to log every action type.
        tamper_proof: Whether to compute HMAC chain checksums for integrity.
        retention_days: Number of days to retain audit events. None means
            no retention limit.
    """

    enabled: bool = False
    log_file: str | None = None
    events: list[str] = field(default_factory=lambda: ["all"])
    tamper_proof: bool = True
    retention_days: int | None = None


def load_audit_log(path: Path) -> list[AuditEvent]:
    """Load audit events from a JSON file.

    Reads a JSON array of serialized audit events and reconstructs
    them as AuditEvent instances.

    Args:
        path: Path to the JSON audit log file.

    Returns:
        List of AuditEvent instances loaded from the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    data = json.loads(path.read_text())
    events: list[AuditEvent] = []
    for entry in data:
        events.append(
            AuditEvent(
                timestamp=entry["timestamp"],
                action=AuditAction(entry["action"]),
                actor=entry["actor"],
                resource=entry["resource"],
                result=entry["result"],
                details=entry.get("details", {}),
                event_id=entry["event_id"],
                checksum=entry.get("checksum", ""),
            )
        )
    return events


class AuditLogger:
    """Audit logger with HMAC chain integrity and configurable event filtering.

    Records audit events with optional tamper-evident checksums that form a
    hash chain. Each event's checksum incorporates the previous event's
    checksum, making it possible to detect any modification or deletion of
    events in the log.

    Args:
        config: Audit configuration controlling behavior.
    """

    def __init__(self, config: AuditConfig) -> None:
        """Initialize the audit logger.

        Args:
            config: AuditConfig controlling which events are logged,
                whether tamper-proof checksums are computed, and where
                events are persisted.
        """
        self._config = config
        self._events: list[AuditEvent] = []
        self._hmac_key: bytes = hashlib.sha256(
            json.dumps(asdict(config), sort_keys=True).encode()
        ).digest()
        self._last_checksum: str = ""

    def log(
        self,
        action: AuditAction,
        resource: str,
        result: str = "success",
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Create and store an audit event.

        Builds an AuditEvent, optionally computes its HMAC checksum as part
        of the hash chain, and appends it to the internal event list. If a
        log_file is configured, the event is also written to disk.

        Args:
            action: The type of action being audited.
            resource: Identifier of the resource acted upon.
            result: Outcome string, typically "success" or "failure".
            actor: Who performed the action.
            details: Optional dictionary of additional context.

        Returns:
            The created AuditEvent (with checksum populated if tamper_proof
            is enabled).
        """
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            actor=actor,
            resource=resource,
            result=result,
            details=details if details is not None else {},
        )

        if not self._should_log(action):
            return event

        if self._config.tamper_proof:
            event.checksum = self._compute_checksum(event)
            self._last_checksum = event.checksum

        self._events.append(event)

        if self._config.log_file is not None:
            self._write_to_file(event)

        return event

    def _compute_checksum(self, event: AuditEvent) -> str:
        """Compute an HMAC-SHA256 checksum for an event.

        The checksum covers the event's core data fields and the previous
        event's checksum, forming a hash chain that enables tamper detection.

        Args:
            event: The audit event to compute a checksum for.

        Returns:
            Hex-encoded HMAC-SHA256 digest string.
        """
        payload = (
            f"{event.timestamp}|{event.action.value}|{event.actor}|"
            f"{event.resource}|{event.result}|{event.event_id}|"
            f"{json.dumps(event.details, sort_keys=True)}|"
            f"{self._last_checksum}"
        )
        return hmac.new(self._hmac_key, payload.encode(), hashlib.sha256).hexdigest()

    def get_events(self, action: AuditAction | None = None) -> list[AuditEvent]:
        """Retrieve stored audit events, optionally filtered by action type.

        Args:
            action: If provided, only return events matching this action.
                If None, return all events.

        Returns:
            List of matching AuditEvent instances.
        """
        if action is None:
            return list(self._events)
        return [e for e in self._events if e.action == action]

    def export_json(self, path: Path) -> None:
        """Export all audit events to a JSON file.

        Writes the complete event list as a JSON array. Each event is
        serialized with its action stored as the enum value string.

        Args:
            path: File path to write the JSON output to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = []
        for event in self._events:
            entry = asdict(event)
            entry["action"] = event.action.value
            serialized.append(entry)
        path.write_text(json.dumps(serialized, indent=2))

    def export_csv(self, path: Path) -> None:
        """Export all audit events to a CSV file.

        Writes one row per event with columns: event_id, timestamp, action,
        actor, resource, result, details, checksum. The details dictionary
        is serialized as a JSON string.

        Args:
            path: File path to write the CSV output to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "event_id",
            "timestamp",
            "action",
            "actor",
            "resource",
            "result",
            "details",
            "checksum",
        ]
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for event in self._events:
                writer.writerow(
                    {
                        "event_id": event.event_id,
                        "timestamp": event.timestamp,
                        "action": event.action.value,
                        "actor": event.actor,
                        "resource": event.resource,
                        "result": event.result,
                        "details": json.dumps(event.details, sort_keys=True),
                        "checksum": event.checksum,
                    }
                )

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Verify the HMAC chain integrity of all stored events.

        Recomputes each event's checksum using the hash chain and compares
        it to the stored checksum. Any mismatch indicates tampering or
        corruption.

        Returns:
            A tuple of (valid, errors) where valid is True if all checksums
            match, and errors is a list of human-readable error descriptions
            for any mismatches found.
        """
        errors: list[str] = []

        if not self._config.tamper_proof:
            return True, []

        previous_checksum = ""
        for i, event in enumerate(self._events):
            payload = (
                f"{event.timestamp}|{event.action.value}|{event.actor}|"
                f"{event.resource}|{event.result}|{event.event_id}|"
                f"{json.dumps(event.details, sort_keys=True)}|"
                f"{previous_checksum}"
            )
            expected = hmac.new(self._hmac_key, payload.encode(), hashlib.sha256).hexdigest()

            if event.checksum != expected:
                errors.append(
                    f"Event {i} ({event.event_id}): checksum mismatch — "
                    f"expected {expected}, got {event.checksum}"
                )

            previous_checksum = event.checksum

        return len(errors) == 0, errors

    def _should_log(self, action: AuditAction) -> bool:
        """Check if an action type should be logged based on configuration.

        Args:
            action: The action type to check.

        Returns:
            True if the action should be logged, False otherwise.
        """
        if not self._config.enabled:
            return False
        if "all" in self._config.events:
            return True
        return action.name in self._config.events

    def _write_to_file(self, event: AuditEvent) -> None:
        """Append a single event to the configured log file as JSON.

        Args:
            event: The audit event to write.
        """
        log_path = Path(self._config.log_file)  # type: ignore[arg-type]
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = asdict(event)
        entry["action"] = event.action.value
        with log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
