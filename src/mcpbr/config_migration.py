"""Configuration migration tool for mcpbr.

Detects old config formats and migrates them to the current format.
Supports chained migrations (V1 -> V2 -> V3 -> V4_CURRENT), dry-run
preview, and automatic backup of originals.
"""

import copy
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class ConfigVersion(Enum):
    """Configuration format versions.

    Each version corresponds to a major release era of mcpbr.
    """

    V1 = "v1"  # Pre-0.3.0: api_key in config, "server" field
    V2 = "v2"  # 0.3.x: mcp_server, no benchmark field
    V3 = "v3"  # 0.4.x: benchmark field, sample_size, infrastructure
    V4_CURRENT = "v4"  # 0.5.0+: resource_limits, streaming config


@dataclass
class Migration:
    """A single migration step between two config versions.

    Attributes:
        from_version: Source config version.
        to_version: Target config version.
        description: Human-readable description of what this migration does.
        migrate: Callable that transforms a config dict from one version to the next.
    """

    from_version: ConfigVersion
    to_version: ConfigVersion
    description: str
    migrate: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class MigrationResult:
    """Result of a config migration operation.

    Attributes:
        original_version: Detected version of the original config.
        target_version: Target version after migration.
        migrations_applied: List of migration descriptions that were applied.
        warnings: List of warning messages (e.g., removed fields).
        config: The migrated config dictionary.
        changes_preview: List of human-readable change descriptions for dry-run.
    """

    original_version: ConfigVersion
    target_version: ConfigVersion
    migrations_applied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    changes_preview: list[str] = field(default_factory=list)


class MigrationChain:
    """Manages a chain of config migrations from any old version to current.

    Registers all known migration steps and provides methods to detect
    config versions, find applicable migrations, and execute them.
    """

    def __init__(self) -> None:
        """Initialize the migration chain with all known migrations."""
        self._migrations: list[Migration] = []
        self._register_all_migrations()

    def _register_all_migrations(self) -> None:
        """Register all known migration steps."""
        self._migrations.append(
            Migration(
                from_version=ConfigVersion.V1,
                to_version=ConfigVersion.V2,
                description="V1 -> V2: Move api_key to env vars, rename 'server' to 'mcp_server'",
                migrate=self._migrate_v1_to_v2,
            )
        )
        self._migrations.append(
            Migration(
                from_version=ConfigVersion.V2,
                to_version=ConfigVersion.V3,
                description=(
                    "V2 -> V3: Add benchmark field, rename max_tasks to sample_size, "
                    "add infrastructure section"
                ),
                migrate=self._migrate_v2_to_v3,
            )
        )
        self._migrations.append(
            Migration(
                from_version=ConfigVersion.V3,
                to_version=ConfigVersion.V4_CURRENT,
                description=(
                    "V3 -> V4: Add resource_limits defaults, add streaming config section"
                ),
                migrate=self._migrate_v3_to_v4,
            )
        )

    def detect_version(self, config: dict[str, Any]) -> ConfigVersion:
        """Detect the config version based on field presence/absence.

        Detection heuristics (checked in order, most specific first):
        - V1: Has "api_key" or "server" (not "mcp_server") top-level key.
        - V4_CURRENT: Has "resource_limits" or "streaming" key, or
                       none of the older markers are present.
        - V2: Has "mcp_server" but no "benchmark" or "infrastructure" key.
        - V3: Has "mcp_server" and "benchmark" or "infrastructure" but
               no "resource_limits" or "streaming" key.

        Args:
            config: Parsed config dictionary.

        Returns:
            Detected ConfigVersion.
        """
        has_api_key = "api_key" in config
        has_server = "server" in config and "mcp_server" not in config
        has_mcp_server = "mcp_server" in config
        has_benchmark = "benchmark" in config
        has_infrastructure = "infrastructure" in config
        has_resource_limits = "resource_limits" in config
        has_streaming = "streaming" in config

        # V1: legacy fields present
        if has_api_key or has_server:
            return ConfigVersion.V1

        # V4: has current-version fields (check before V2/V3 to avoid false matches)
        if has_resource_limits or has_streaming:
            return ConfigVersion.V4_CURRENT

        # V2: has mcp_server but no benchmark/infrastructure
        if has_mcp_server and not has_benchmark and not has_infrastructure:
            return ConfigVersion.V2

        # V3: has mcp_server with benchmark or infrastructure but not V4 fields
        if has_mcp_server and (has_benchmark or has_infrastructure):
            return ConfigVersion.V3

        # Default to current if no distinguishing markers found
        return ConfigVersion.V4_CURRENT

    def get_migrations(self, from_ver: ConfigVersion, to_ver: ConfigVersion) -> list[Migration]:
        """Get the ordered list of migrations needed to go from one version to another.

        Args:
            from_ver: Starting config version.
            to_ver: Target config version.

        Returns:
            Ordered list of Migration objects to apply. Empty list if no
            migration is needed or if from_ver >= to_ver.
        """
        version_order = list(ConfigVersion)
        from_idx = version_order.index(from_ver)
        to_idx = version_order.index(to_ver)

        if from_idx >= to_idx:
            return []

        result: list[Migration] = []
        current = from_ver
        for migration in self._migrations:
            if (
                migration.from_version == current
                and version_order.index(migration.to_version) <= to_idx
            ):
                result.append(migration)
                current = migration.to_version

        return result

    def migrate(self, config: dict[str, Any], dry_run: bool = False) -> MigrationResult:
        """Migrate a config dict from its detected version to the current version.

        Args:
            config: Parsed config dictionary to migrate.
            dry_run: If True, compute changes but do not modify the config.

        Returns:
            MigrationResult with migration details and the (possibly modified) config.
        """
        original_version = self.detect_version(config)
        target_version = ConfigVersion.V4_CURRENT

        result = MigrationResult(
            original_version=original_version,
            target_version=target_version,
            config=copy.deepcopy(config),
        )

        if original_version == target_version:
            result.changes_preview.append("Config is already at the current version (V4).")
            return result

        migrations = self.get_migrations(original_version, target_version)
        if not migrations:
            result.warnings.append(
                f"No migration path found from {original_version.value} to {target_version.value}."
            )
            return result

        working_config = copy.deepcopy(config)

        for migration in migrations:
            result.changes_preview.append(f"Apply: {migration.description}")
            if not dry_run:
                working_config = migration.migrate(working_config)
            result.migrations_applied.append(migration.description)

        if not dry_run:
            result.config = working_config
        else:
            # For dry-run, keep original config but show what would change
            result.config = copy.deepcopy(config)

        return result

    # -- Individual migration implementations --

    @staticmethod
    def _migrate_v1_to_v2(config: dict[str, Any]) -> dict[str, Any]:
        """Migrate V1 config to V2 format.

        Changes:
        - Remove "api_key" (moved to environment variables).
        - Rename "server" to "mcp_server" and convert to new structure.
        - Remove "dataset" if present (replaced by benchmark in V3).

        Args:
            config: V1 config dictionary.

        Returns:
            V2 config dictionary.
        """
        result = copy.deepcopy(config)

        # Remove api_key (should be in env vars now)
        if "api_key" in result:
            del result["api_key"]

        # Rename "server" to "mcp_server" with structure conversion
        if "server" in result:
            server = result.pop("server")
            if isinstance(server, dict):
                # Convert old server format to mcp_server format
                mcp_server: dict[str, Any] = {}
                if "command" in server:
                    mcp_server["command"] = server["command"]
                if "args" in server:
                    mcp_server["args"] = server["args"]
                if "env" in server:
                    mcp_server["env"] = server["env"]
                if "name" in server:
                    mcp_server["name"] = server["name"]
                result["mcp_server"] = mcp_server
            elif isinstance(server, str):
                # Simple string server specification -> convert to command
                result["mcp_server"] = {"command": server, "args": []}

        return result

    @staticmethod
    def _migrate_v2_to_v3(config: dict[str, Any]) -> dict[str, Any]:
        """Migrate V2 config to V3 format.

        Changes:
        - Add "benchmark" field (default: "swe-bench-verified").
        - Rename "max_tasks" to "sample_size".
        - Add "infrastructure" section with default local mode.
        - Convert "dataset" field to "benchmark" if present.

        Args:
            config: V2 config dictionary.

        Returns:
            V3 config dictionary.
        """
        result = copy.deepcopy(config)

        # Map old dataset names to benchmark identifiers
        dataset_to_benchmark = {
            "SWE-bench/SWE-bench_Lite": "swe-bench-lite",
            "SWE-bench/SWE-bench_Verified": "swe-bench-verified",
            "SWE-bench/SWE-bench": "swe-bench-full",
            "princeton-nlp/SWE-bench_Lite": "swe-bench-lite",
            "princeton-nlp/SWE-bench_Verified": "swe-bench-verified",
            "princeton-nlp/SWE-bench": "swe-bench-full",
        }

        # Convert dataset to benchmark if present
        if "dataset" in result:
            dataset_val = result.pop("dataset")
            if dataset_val in dataset_to_benchmark:
                result["benchmark"] = dataset_to_benchmark[dataset_val]
            else:
                result["benchmark"] = "swe-bench-verified"

        # Add benchmark default if not present
        if "benchmark" not in result:
            result["benchmark"] = "swe-bench-verified"

        # Rename max_tasks to sample_size
        if "max_tasks" in result:
            result["sample_size"] = result.pop("max_tasks")

        # Add infrastructure section if not present
        if "infrastructure" not in result:
            result["infrastructure"] = {"mode": "local"}

        return result

    @staticmethod
    def _migrate_v3_to_v4(config: dict[str, Any]) -> dict[str, Any]:
        """Migrate V3 config to V4 (current) format.

        Changes:
        - Add "resource_limits" section with defaults.
        - Add "streaming" config section.

        Args:
            config: V3 config dictionary.

        Returns:
            V4 config dictionary.
        """
        result = copy.deepcopy(config)

        # Add resource_limits with sensible defaults
        if "resource_limits" not in result:
            result["resource_limits"] = {
                "max_memory_mb": 4096,
                "max_cpu_percent": 80,
                "max_disk_mb": 10240,
            }

        # Add streaming config section
        if "streaming" not in result:
            result["streaming"] = {
                "enabled": True,
                "console_updates": True,
                "progressive_json": None,
                "progressive_yaml": None,
                "progressive_markdown": None,
            }

        return result


def migrate_config_file(path: Path, dry_run: bool = False, backup: bool = True) -> MigrationResult:
    """Migrate a config file from an old format to the current format.

    Reads the YAML file, detects its version, applies all necessary
    migrations, and writes back the updated config. Optionally creates
    a backup of the original file.

    Args:
        path: Path to the config YAML file.
        dry_run: If True, preview changes without modifying the file.
        backup: If True, create a backup (.bak) of the original before writing.

    Returns:
        MigrationResult with details of the migration.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file cannot be parsed as YAML.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        config = yaml.safe_load(f) or {}

    chain = MigrationChain()
    result = chain.migrate(config, dry_run=dry_run)

    if dry_run:
        return result

    # No migrations needed
    if result.original_version == result.target_version:
        return result

    # Create backup before writing
    if backup:
        backup_path = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup_path)
        result.changes_preview.append(f"Backup created: {backup_path}")

    # Write migrated config
    with open(path, "w") as f:
        yaml.dump(
            result.config,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    return result


def format_migration_report(result: MigrationResult) -> None:
    """Print a rich-formatted migration report to the console.

    Displays the detected version, target version, applied migrations,
    warnings, and a preview of changes.

    Args:
        result: MigrationResult to format and display.
    """
    console = Console(stderr=True)

    # Header
    title = f"Config Migration: {result.original_version.value} -> {result.target_version.value}"

    if result.original_version == result.target_version:
        console.print(
            Panel(
                "[green]Config is already at the current version. No migration needed.[/green]",
                title=title,
            )
        )
        return

    # Migrations table
    if result.migrations_applied:
        table = Table(title="Migrations Applied")
        table.add_column("#", style="dim", width=4)
        table.add_column("Description", style="cyan")

        for i, desc in enumerate(result.migrations_applied, 1):
            table.add_row(str(i), desc)

        console.print(table)

    # Warnings
    if result.warnings:
        console.print()
        console.print("[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]- {warning}[/yellow]")

    # Changes preview
    if result.changes_preview:
        console.print()
        console.print("[blue]Changes:[/blue]")
        for change in result.changes_preview:
            console.print(f"  [blue]- {change}[/blue]")

    console.print()
