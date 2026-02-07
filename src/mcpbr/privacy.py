"""Privacy controls for benchmark results.

Provides configurable PII redaction, data retention policies, and field
exclusion for benchmark output. Supports multiple redaction levels from
no redaction to strict PII scrubbing with custom patterns.
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class RedactionLevel(Enum):
    """Level of PII redaction to apply to benchmark results.

    Attributes:
        NONE: No redaction is performed.
        BASIC: Redacts emails, API keys, and IP addresses.
        STRICT: Redacts all PII patterns including phone numbers,
            credit cards, SSNs, plus any custom patterns.
    """

    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"


@dataclass
class PrivacyConfig:
    """Configuration for privacy controls.

    Attributes:
        redaction_level: How aggressively to redact PII from results.
        custom_patterns: Additional regex patterns to redact in STRICT mode.
        exclude_fields: Field names to strip entirely from result dicts.
        data_retention_days: How long to keep results in days. None means forever.
        anonymize_task_ids: Whether to replace real task IDs with SHA256 hash prefixes.
        opt_out_analytics: Whether to disable all telemetry and analytics collection.
    """

    redaction_level: RedactionLevel = RedactionLevel.BASIC
    custom_patterns: list[str] = field(default_factory=list)
    exclude_fields: list[str] = field(default_factory=list)
    data_retention_days: int | None = None
    anonymize_task_ids: bool = False
    opt_out_analytics: bool = False


# Built-in PII detection patterns, ordered from most common to most specific.
# BASIC mode uses the first 4 patterns; STRICT mode uses all of them.
_PII_PATTERNS: list[str] = [
    # --- BASIC patterns (indices 0-3) ---
    # Email addresses
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    # API keys (generic prefixed secrets)
    r"(?:sk|pk|api|key|token|secret|password)[-_]?[a-zA-Z0-9]{20,}",
    # IPv4 addresses
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    # IPv6 addresses (full and abbreviated forms like ::1, fe80::1, 2001:db8::1)
    r"(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}",
    # --- STRICT patterns (indices 4+) ---
    # Credit card numbers: 16 digits with optional separators (Visa, Mastercard, Discover)
    r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    # Credit card numbers: 15 digits with optional separators (American Express)
    r"\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b",
    # Social Security Numbers (with dashes)
    r"\b\d{3}-\d{2}-\d{4}\b",
    # Social Security Numbers (without dashes, excluding invalid prefixes)
    r"\b(?!000|666|9\d\d)\d{3}(?!00)\d{2}(?!0000)\d{4}\b",
    # Phone numbers (US format, with optional country code and various separators)
    r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    # Phone numbers (international format: +CC followed by subscriber number groups)
    r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b",
]

# Number of patterns used in BASIC redaction mode
_BASIC_PATTERN_COUNT = 4


class PiiRedactor:
    """Redacts personally identifiable information from text and data structures.

    Compiles regex patterns based on the configured redaction level and
    applies them to strings and nested dictionaries.

    Args:
        config: Privacy configuration controlling redaction behavior.
    """

    def __init__(self, config: PrivacyConfig) -> None:
        """Initialize PiiRedactor with compiled patterns.

        Args:
            config: Privacy configuration controlling redaction behavior.
        """
        self._config = config
        self._compiled_patterns: list[re.Pattern[str]] = []

        if config.redaction_level == RedactionLevel.BASIC:
            raw_patterns = _PII_PATTERNS[:_BASIC_PATTERN_COUNT]
        elif config.redaction_level == RedactionLevel.STRICT:
            raw_patterns = _PII_PATTERNS + config.custom_patterns
        else:
            raw_patterns = []

        self._compiled_patterns = [re.compile(p) for p in raw_patterns]

    def redact(self, text: str, replacement: str = "[REDACTED]") -> str:
        """Apply all configured PII patterns to redact sensitive data from text.

        Args:
            text: The input string to redact.
            replacement: The string to substitute for matched patterns.

        Returns:
            The text with all PII patterns replaced by the replacement string.
        """
        result = text
        for pattern in self._compiled_patterns:
            result = pattern.sub(replacement, result)
        return result

    def redact_dict(self, data: dict, replacement: str = "[REDACTED]") -> dict:
        """Recursively redact string values in a dictionary.

        Removes any keys listed in the config's exclude_fields, then applies
        PII pattern redaction to all remaining string values. Nested dicts
        and lists are processed recursively.

        Args:
            data: The dictionary to redact.
            replacement: The string to substitute for matched patterns.

        Returns:
            A new dictionary with excluded fields removed and PII redacted.
        """
        result: dict[str, Any] = {}
        exclude = set(self._config.exclude_fields)

        for key, value in data.items():
            if key in exclude:
                continue
            result[key] = self._redact_value(value, replacement)

        return result

    def _redact_value(self, value: Any, replacement: str) -> Any:
        """Redact a single value, recursing into dicts and lists.

        Args:
            value: The value to redact.
            replacement: The string to substitute for matched patterns.

        Returns:
            The redacted value.
        """
        if isinstance(value, str):
            return self.redact(value, replacement)
        if isinstance(value, dict):
            return self.redact_dict(value, replacement)
        if isinstance(value, list):
            return [self._redact_value(item, replacement) for item in value]
        return value

    def anonymize_id(self, task_id: str) -> str:
        """Anonymize a task ID by replacing it with a SHA256 hash prefix.

        If anonymize_task_ids is disabled in the config, returns the
        original task ID unchanged.

        Args:
            task_id: The task identifier to anonymize.

        Returns:
            The first 12 characters of the SHA256 hex digest if anonymization
            is enabled, otherwise the original task_id.
        """
        if not self._config.anonymize_task_ids:
            return task_id
        return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12]


class DataRetentionPolicy:
    """Enforces data retention limits based on age.

    Determines whether stored results have exceeded the configured
    retention period and should be purged.

    Args:
        retention_days: Number of days to retain data. None means no expiry.
    """

    def __init__(self, retention_days: int | None = None) -> None:
        """Initialize DataRetentionPolicy.

        Args:
            retention_days: Number of days to retain data. None means forever.
        """
        self._retention_days = retention_days

    def is_expired(self, timestamp: str) -> bool:
        """Check whether an ISO 8601 timestamp is older than the retention period.

        If no retention period is configured, data never expires.

        Args:
            timestamp: ISO 8601 formatted timestamp to check.

        Returns:
            True if the timestamp is older than the retention period, False otherwise.
        """
        if self._retention_days is None:
            return False

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        ts = datetime.fromisoformat(timestamp)

        # Ensure timezone-aware comparison
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        return ts < cutoff

    def get_expiry_date(self) -> str | None:
        """Calculate the cutoff date before which data should be purged.

        Returns:
            ISO 8601 string of the cutoff date, or None if no retention is configured.
        """
        if self._retention_days is None:
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        return cutoff.isoformat()


def apply_privacy_controls(data: dict, config: PrivacyConfig) -> dict:
    """Apply all privacy controls to a result dictionary.

    Convenience function that creates a PiiRedactor from the given config
    and applies both PII redaction and field exclusion in a single call.

    Args:
        data: The result dictionary to process.
        config: Privacy configuration controlling what to redact and exclude.

    Returns:
        A new dictionary with privacy controls applied.
    """
    redactor = PiiRedactor(config)
    return redactor.redact_dict(data)
