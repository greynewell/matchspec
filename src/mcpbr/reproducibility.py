"""Benchmark reproducibility for evaluation runs.

Provides environment snapshotting, deterministic seeding, and reproducibility
reports to ensure benchmark results can be reliably reproduced across runs
and environments.
"""

import hashlib
import json
import os
import platform
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Environment variables relevant to reproducibility
_REPRODUCIBILITY_ENV_VARS = (
    "PYTHONHASHSEED",
    "MCPBR_LOG_LEVEL",
    "ANTHROPIC_API_KEY",
)

# Environment variables whose values should be masked in snapshots
_MASKED_ENV_VARS = frozenset({"ANTHROPIC_API_KEY"})


@dataclass
class EnvironmentSnapshot:
    """Snapshot of the runtime environment for reproducibility tracking.

    Captures all environment details needed to reproduce a benchmark run,
    including Python version, platform info, installed packages, and
    relevant environment variables.

    Attributes:
        python_version: Full Python version string (e.g., '3.11.5').
        platform: Operating system name (e.g., 'Darwin', 'Linux').
        platform_version: OS version string.
        mcpbr_version: Version of the mcpbr package.
        timestamp: ISO 8601 timestamp of when the snapshot was taken.
        packages: Mapping of installed package names to their versions.
        env_vars: Selected environment variables relevant to reproducibility.
            Sensitive values (e.g., API keys) are masked with '***'.
        global_seed: RNG seed used for the run, or None if unseeded.
    """

    python_version: str
    platform: str
    platform_version: str
    mcpbr_version: str
    timestamp: str
    packages: dict[str, str] = field(default_factory=dict)
    env_vars: dict[str, str] = field(default_factory=dict)
    global_seed: int | None = None


@dataclass
class ReproducibilityConfig:
    """Configuration controlling reproducibility behavior.

    Attributes:
        global_seed: Seed for all RNG sources. None means no seeding.
        record_environment: Whether to capture an environment snapshot.
        lock_file: Path to save/load reproducibility lock files.
            None means no lock file is used.
        deterministic_mode: When True, sets PYTHONHASHSEED and other
            flags to maximize determinism.
    """

    global_seed: int | None = None
    record_environment: bool = True
    lock_file: str | None = None
    deterministic_mode: bool = False


@dataclass
class ReproducibilityReport:
    """Report documenting the reproducibility state of a benchmark run.

    Contains the full configuration, environment snapshot, a verification
    checksum, and any warnings about non-deterministic conditions.

    Attributes:
        config: The reproducibility configuration used.
        environment: Snapshot of the runtime environment.
        checksum: SHA256 hash of the serialized config and environment
            for integrity verification.
        warnings: List of warnings about potential reproducibility issues
            (e.g., PYTHONHASHSEED not set in deterministic mode).
    """

    config: ReproducibilityConfig
    environment: EnvironmentSnapshot
    checksum: str = ""
    warnings: list[str] = field(default_factory=list)


def _collect_packages() -> dict[str, str]:
    """Collect installed package names and versions.

    Attempts to use importlib.metadata to enumerate installed packages.
    Falls back gracefully to an empty dict if the metadata API is
    unavailable or fails.

    Returns:
        Mapping of package names to version strings.
    """
    packages: dict[str, str] = {}
    try:
        from importlib.metadata import distributions

        for dist in distributions():
            name = dist.metadata.get("Name", "")
            version = dist.metadata.get("Version", "")
            if name:
                packages[name] = version
    except Exception:
        # importlib.metadata may not be available in all environments
        pass
    return packages


def _collect_env_vars() -> dict[str, str]:
    """Collect selected environment variables for the snapshot.

    Sensitive variables (like API keys) are masked with '***' if set,
    or recorded as empty string if not set.

    Returns:
        Mapping of variable names to their values or masked placeholders.
    """
    env_vars: dict[str, str] = {}
    for var in _REPRODUCIBILITY_ENV_VARS:
        value = os.environ.get(var, "")
        if var in _MASKED_ENV_VARS and value:
            env_vars[var] = "***"
        else:
            env_vars[var] = value
    return env_vars


def capture_environment(mcpbr_version: str, seed: int | None = None) -> EnvironmentSnapshot:
    """Capture a snapshot of the current runtime environment.

    Gathers Python version, platform details, installed packages, and
    selected environment variables into an EnvironmentSnapshot for
    reproducibility tracking.

    Args:
        mcpbr_version: The mcpbr package version string.
        seed: Optional global RNG seed to record in the snapshot.

    Returns:
        EnvironmentSnapshot populated with current environment details.
    """
    return EnvironmentSnapshot(
        python_version=sys.version,
        platform=platform.system(),
        platform_version=platform.version(),
        mcpbr_version=mcpbr_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        packages=_collect_packages(),
        env_vars=_collect_env_vars(),
        global_seed=seed,
    )


def set_global_seed(seed: int) -> None:
    """Set a global seed for all RNG sources to ensure determinism.

    Seeds Python's built-in random module and sets the PYTHONHASHSEED
    environment variable for hash reproducibility.

    Args:
        seed: The integer seed value to apply.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def _compute_checksum(config: ReproducibilityConfig, environment: EnvironmentSnapshot) -> str:
    """Compute a SHA256 checksum of the config and environment.

    Serializes both dataclasses to a deterministic JSON string and
    returns its hex digest for integrity verification.

    Args:
        config: The reproducibility configuration.
        environment: The environment snapshot.

    Returns:
        Hex-encoded SHA256 digest of the serialized data.
    """
    data = {
        "config": asdict(config),
        "environment": asdict(environment),
    }
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _check_deterministic_warnings(config: ReproducibilityConfig) -> list[str]:
    """Check for conditions that may undermine deterministic mode.

    Args:
        config: The reproducibility configuration to validate.

    Returns:
        List of warning messages about potential reproducibility issues.
    """
    warnings: list[str] = []

    if config.deterministic_mode:
        hashseed = os.environ.get("PYTHONHASHSEED", "")
        if not hashseed or hashseed == "random":
            warnings.append(
                "deterministic_mode is enabled but PYTHONHASHSEED is not set "
                "to a fixed value. Hash-based operations may not be reproducible."
            )

        if config.global_seed is None:
            warnings.append(
                "deterministic_mode is enabled but no global_seed is configured. "
                "Random operations will not be reproducible."
            )

    return warnings


def generate_reproducibility_report(
    config: ReproducibilityConfig, mcpbr_version: str
) -> ReproducibilityReport:
    """Generate a full reproducibility report for a benchmark run.

    Captures the environment, applies the global seed if configured,
    computes a verification checksum, and checks for any conditions
    that may undermine reproducibility.

    Args:
        config: The reproducibility configuration to apply.
        mcpbr_version: The mcpbr package version string.

    Returns:
        ReproducibilityReport with environment snapshot, checksum,
        and any reproducibility warnings.
    """
    if config.global_seed is not None:
        set_global_seed(config.global_seed)

    environment = capture_environment(
        mcpbr_version=mcpbr_version,
        seed=config.global_seed,
    )

    checksum = _compute_checksum(config, environment)
    warnings = _check_deterministic_warnings(config)

    return ReproducibilityReport(
        config=config,
        environment=environment,
        checksum=checksum,
        warnings=warnings,
    )


def save_report(report: ReproducibilityReport, path: Path) -> None:
    """Save a reproducibility report to a JSON file.

    Serializes the report's dataclasses to a human-readable JSON file
    with sorted keys and indentation.

    Args:
        report: The reproducibility report to save.
        path: File path to write the JSON report to.
    """
    data = {
        "config": asdict(report.config),
        "environment": asdict(report.environment),
        "checksum": report.checksum,
        "warnings": report.warnings,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def load_report(path: Path) -> ReproducibilityReport:
    """Load a reproducibility report from a JSON file.

    Deserializes a JSON file written by save_report back into a
    ReproducibilityReport with fully populated dataclasses.

    Args:
        path: File path to read the JSON report from.

    Returns:
        ReproducibilityReport reconstructed from the file.

    Raises:
        FileNotFoundError: If the path does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        KeyError: If required fields are missing from the JSON.
    """
    data = json.loads(path.read_text())

    config = ReproducibilityConfig(
        global_seed=data["config"].get("global_seed"),
        record_environment=data["config"].get("record_environment", True),
        lock_file=data["config"].get("lock_file"),
        deterministic_mode=data["config"].get("deterministic_mode", False),
    )

    env_data = data["environment"]
    environment = EnvironmentSnapshot(
        python_version=env_data["python_version"],
        platform=env_data["platform"],
        platform_version=env_data["platform_version"],
        mcpbr_version=env_data["mcpbr_version"],
        timestamp=env_data["timestamp"],
        packages=env_data.get("packages", {}),
        env_vars=env_data.get("env_vars", {}),
        global_seed=env_data.get("global_seed"),
    )

    return ReproducibilityReport(
        config=config,
        environment=environment,
        checksum=data.get("checksum", ""),
        warnings=data.get("warnings", []),
    )
