"""Prompt security scanning for detecting injection attacks in benchmark tasks.

Scans benchmark task prompts for common prompt injection patterns, jailbreak
attempts, and other adversarial inputs. Configurable via YAML with support
for custom patterns and allowlists.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SecurityAction(str, Enum):
    """Action to take when a security finding is detected."""

    AUDIT = "audit"
    WARN = "warn"
    BLOCK = "block"


class FindingSeverity(str, Enum):
    """Severity level of a security finding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityFinding:
    """A single security finding from scanning a prompt.

    Attributes:
        pattern_name: Name of the detection pattern that matched.
        severity: Severity level of the finding.
        matched_text: The text that matched the pattern.
        location: Where in the task the match was found (e.g., "problem_statement").
        description: Human-readable description of the finding.
        task_id: ID of the task containing the finding.
    """

    pattern_name: str
    severity: FindingSeverity
    matched_text: str
    location: str
    description: str
    task_id: str = ""


@dataclass
class ScanResult:
    """Result of scanning a single task for security issues.

    Attributes:
        task_id: ID of the scanned task.
        findings: List of security findings.
        action_taken: The action that was taken (audit/warn/block).
        blocked: Whether the task was blocked from execution.
    """

    task_id: str
    findings: list[SecurityFinding] = field(default_factory=list)
    action_taken: SecurityAction = SecurityAction.AUDIT
    blocked: bool = False

    @property
    def has_findings(self) -> bool:
        """Whether any findings were detected."""
        return len(self.findings) > 0

    @property
    def max_severity(self) -> FindingSeverity | None:
        """Highest severity among all findings, or None if no findings."""
        if not self.findings:
            return None
        severity_order = [
            FindingSeverity.LOW,
            FindingSeverity.MEDIUM,
            FindingSeverity.HIGH,
            FindingSeverity.CRITICAL,
        ]
        max_idx = -1
        for finding in self.findings:
            idx = severity_order.index(finding.severity)
            if idx > max_idx:
                max_idx = idx
        return severity_order[max_idx]


@dataclass
class PromptSecurityConfig:
    """Configuration for prompt security scanning.

    Attributes:
        enabled: Whether scanning is enabled.
        scan_level: Scan level — "full" checks all patterns,
            "minimal" only checks HIGH and CRITICAL.
        action: What to do when findings are detected.
        custom_patterns: Additional regex patterns to check, as list of
            dicts with keys: name, pattern, severity, description.
        allowlist_patterns: Regex patterns for text that should be
            exempted from findings (e.g., legitimate security discussions).
    """

    enabled: bool = True
    scan_level: str = "full"
    action: SecurityAction = SecurityAction.WARN
    custom_patterns: list[dict[str, str]] = field(default_factory=list)
    allowlist_patterns: list[str] = field(default_factory=list)


@dataclass
class _DetectionPattern:
    """Internal detection pattern definition."""

    name: str
    pattern: str
    severity: FindingSeverity
    description: str


# Built-in detection patterns for common prompt injection techniques
INJECTION_PATTERNS: list[_DetectionPattern] = [
    _DetectionPattern(
        name="ignore_previous_instructions",
        pattern=r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions",
        severity=FindingSeverity.HIGH,
        description="Attempts to override system/prior instructions",
    ),
    _DetectionPattern(
        name="new_identity",
        pattern=r"(?i)you\s+are\s+now\s+(?:a|an|the)\b",
        severity=FindingSeverity.HIGH,
        description="Attempts to assign a new identity to the model",
    ),
    _DetectionPattern(
        name="system_prompt_leak",
        pattern=r"(?i)(?:reveal|show|display|print|output|repeat)\s+"
        r"(?:your\s+)?(?:system\s+prompt|instructions|initial\s+prompt)",
        severity=FindingSeverity.MEDIUM,
        description="Attempts to extract system prompt content",
    ),
    _DetectionPattern(
        name="jailbreak_prefix",
        pattern=r"(?i)\b(?:DAN|STAN|DUDE|AIM)\b.*(?:mode|prompt|jailbreak)",
        severity=FindingSeverity.HIGH,
        description="Known jailbreak prefix pattern (DAN/STAN/DUDE/AIM)",
    ),
    _DetectionPattern(
        name="role_play_injection",
        pattern=r"(?i)(?:pretend|act\s+as\s+if|imagine)\s+you\s+(?:are|have)\s+"
        r"(?:no\s+(?:restrictions|rules|limits|filters)|unlimited)",
        severity=FindingSeverity.MEDIUM,
        description="Role-play injection to bypass safety guidelines",
    ),
    _DetectionPattern(
        name="base64_injection",
        pattern=r"(?i)(?:decode|execute|run|eval)\s+(?:this\s+)?base64",
        severity=FindingSeverity.MEDIUM,
        description="Attempts to inject via base64-encoded content",
    ),
    _DetectionPattern(
        name="unicode_obfuscation",
        pattern=r"[\u200b\u200c\u200d\ufeff\u00ad]",
        severity=FindingSeverity.MEDIUM,
        description="Contains zero-width or invisible unicode characters",
    ),
    _DetectionPattern(
        name="shell_injection",
        pattern=r"(?i)(?:curl|wget|bash|sh)\s+(?:-[a-z]\s+)*https?://",
        severity=FindingSeverity.HIGH,
        description="Shell command injection pattern (curl/wget/bash with URL)",
    ),
    _DetectionPattern(
        name="shell_reverse_shell",
        pattern=r"(?i)(?:bash\s+-i\s+>(?:&|/dev/tcp)|nc\s+-[a-z]*e\s|"
        r"python[23]?\s+-c\s+['\"]import\s+(?:socket|os|subprocess))",
        severity=FindingSeverity.CRITICAL,
        description="Reverse shell attempt detected",
    ),
    _DetectionPattern(
        name="delimiter_injection",
        pattern=r"(?:<\|system\|>|<<SYS>>|<\|im_start\|>|\[INST\])",
        severity=FindingSeverity.HIGH,
        description="Prompt delimiter injection (system/instruction markers)",
    ),
]


class PromptSecurityScanner:
    """Scanner for detecting prompt injection in benchmark tasks.

    Args:
        config: Configuration controlling scan behavior.
    """

    def __init__(self, config: PromptSecurityConfig) -> None:
        """Initialize the scanner with compiled regex patterns.

        Args:
            config: PromptSecurityConfig controlling which patterns to check.
        """
        self._config = config
        self._compiled_patterns: list[tuple[_DetectionPattern, re.Pattern[str]]] = []
        self._compiled_allowlist: list[re.Pattern[str]] = []

        # Validate scan_level
        valid_scan_levels = ("full", "minimal")
        if config.scan_level not in valid_scan_levels:
            logger.warning(
                "Unknown scan_level '%s', treating as 'full'. Valid values: %s",
                config.scan_level,
                ", ".join(valid_scan_levels),
            )

        # Filter patterns by scan level
        for pat in INJECTION_PATTERNS:
            if config.scan_level == "minimal" and pat.severity not in (
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            ):
                continue
            try:
                compiled = re.compile(pat.pattern)
                self._compiled_patterns.append((pat, compiled))
            except re.error as e:
                logger.warning("Failed to compile pattern %s: %s", pat.name, e)

        # Add custom patterns
        for custom in config.custom_patterns:
            try:
                severity = FindingSeverity(custom.get("severity", "medium"))
                if config.scan_level == "minimal" and severity not in (
                    FindingSeverity.HIGH,
                    FindingSeverity.CRITICAL,
                ):
                    continue
                pat = _DetectionPattern(
                    name=custom["name"],
                    pattern=custom["pattern"],
                    severity=severity,
                    description=custom.get("description", "Custom pattern match"),
                )
                compiled = re.compile(pat.pattern)
                self._compiled_patterns.append((pat, compiled))
            except (re.error, KeyError, ValueError) as e:
                logger.warning("Failed to load custom pattern %s: %s", custom.get("name", "?"), e)

        # Compile allowlist patterns
        for allowlist_pat in config.allowlist_patterns:
            try:
                self._compiled_allowlist.append(re.compile(allowlist_pat))
            except re.error as e:
                logger.warning("Failed to compile allowlist pattern: %s", e)

    def scan_task(self, task: dict[str, Any]) -> ScanResult:
        """Scan a benchmark task for prompt injection patterns.

        Scans the problem_statement and related text fields (hints_text,
        hint, description, input) for known injection patterns.

        Args:
            task: Benchmark task dictionary.

        Returns:
            ScanResult with any findings and the action taken.
        """
        task_id = task.get("instance_id", task.get("task_id", "unknown"))
        result = ScanResult(task_id=task_id, action_taken=self._config.action)

        # Fields to scan
        fields_to_scan = [
            "problem_statement",
            "hints_text",
            "hint",
            "description",
            "input",
        ]

        for field_name in fields_to_scan:
            text = task.get(field_name)
            if text and isinstance(text, str):
                self._scan_text(text, field_name, task_id, result)

        # Determine if task should be blocked
        if self._config.action == SecurityAction.BLOCK and result.has_findings:
            max_sev = result.max_severity
            if max_sev in (FindingSeverity.HIGH, FindingSeverity.CRITICAL):
                result.blocked = True

        return result

    def _scan_text(self, text: str, location: str, task_id: str, result: ScanResult) -> None:
        """Scan a text field for injection patterns.

        Args:
            text: Text to scan.
            location: Field name for reporting.
            task_id: Task identifier for reporting.
            result: ScanResult to append findings to.
        """
        for pattern_def, compiled in self._compiled_patterns:
            for match in compiled.finditer(text):
                matched_text = match.group(0)
                # Check allowlist for each match individually
                if self._is_allowlisted(matched_text):
                    continue
                result.findings.append(
                    SecurityFinding(
                        pattern_name=pattern_def.name,
                        severity=pattern_def.severity,
                        matched_text=matched_text[:200],  # Truncate for safety
                        location=location,
                        description=pattern_def.description,
                        task_id=task_id,
                    )
                )

    def _is_allowlisted(self, text: str) -> bool:
        """Check whether matched text is covered by an allowlist pattern.

        Args:
            text: The matched text to check.

        Returns:
            True if the text matches an allowlist pattern.
        """
        for allowlist_re in self._compiled_allowlist:
            if allowlist_re.search(text):
                return True
        return False


def parse_prompt_security_config(config_dict: dict[str, Any]) -> PromptSecurityConfig:
    """Parse prompt security configuration from a YAML dictionary.

    Example YAML::

        prompt_security:
          enabled: true
          scan_level: full
          action: warn
          custom_patterns:
            - name: my_pattern
              pattern: "dangerous_keyword"
              severity: high
              description: "Custom dangerous keyword"
          allowlist_patterns:
            - "legitimate_security_term"

    Args:
        config_dict: Dictionary from YAML configuration.

    Returns:
        PromptSecurityConfig instance.
    """
    action_str = config_dict.get("action", "warn")
    try:
        action = SecurityAction(action_str)
    except ValueError:
        logger.warning("Unknown security action '%s', defaulting to 'warn'", action_str)
        action = SecurityAction.WARN

    return PromptSecurityConfig(
        enabled=config_dict.get("enabled", True),
        scan_level=config_dict.get("scan_level", "full"),
        action=action,
        custom_patterns=config_dict.get("custom_patterns", []),
        allowlist_patterns=config_dict.get("allowlist_patterns", []),
    )
