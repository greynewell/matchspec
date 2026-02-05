"""Tests for configuration migration tool."""

from pathlib import Path

import pytest
import yaml

from mcpbr.config_migration import (
    ConfigVersion,
    Migration,
    MigrationChain,
    MigrationResult,
    format_migration_report,
    migrate_config_file,
)

# ---------------------------------------------------------------------------
# Fixtures: sample configs for each version
# ---------------------------------------------------------------------------


@pytest.fixture
def v1_config() -> dict:
    """A V1-era config with api_key and server fields."""
    return {
        "api_key": "sk-ant-fake-key-12345",
        "server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            "env": {"TOKEN": "abc"},
        },
        "provider": "anthropic",
        "model": "sonnet",
        "max_tasks": 5,
        "timeout_seconds": 300,
    }


@pytest.fixture
def v2_config() -> dict:
    """A V2-era config with mcp_server but no benchmark or infrastructure."""
    return {
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        },
        "provider": "anthropic",
        "model": "sonnet",
        "dataset": "SWE-bench/SWE-bench_Lite",
        "max_tasks": 10,
        "timeout_seconds": 300,
    }


@pytest.fixture
def v3_config() -> dict:
    """A V3-era config with mcp_server, benchmark, and infrastructure."""
    return {
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        },
        "provider": "anthropic",
        "model": "sonnet",
        "benchmark": "swe-bench-verified",
        "sample_size": 5,
        "infrastructure": {"mode": "local"},
        "timeout_seconds": 300,
    }


@pytest.fixture
def v4_config() -> dict:
    """A V4 (current) config with all modern fields."""
    return {
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        },
        "provider": "anthropic",
        "model": "sonnet",
        "benchmark": "swe-bench-verified",
        "sample_size": 5,
        "infrastructure": {"mode": "local"},
        "resource_limits": {
            "max_memory_mb": 4096,
            "max_cpu_percent": 80,
            "max_disk_mb": 10240,
        },
        "streaming": {
            "enabled": True,
            "console_updates": True,
        },
        "timeout_seconds": 300,
    }


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for config file tests."""
    return tmp_path


# ---------------------------------------------------------------------------
# ConfigVersion enum tests
# ---------------------------------------------------------------------------


class TestConfigVersion:
    """Tests for the ConfigVersion enum."""

    def test_enum_values(self) -> None:
        """Test that all expected versions exist."""
        assert ConfigVersion.V1.value == "v1"
        assert ConfigVersion.V2.value == "v2"
        assert ConfigVersion.V3.value == "v3"
        assert ConfigVersion.V4_CURRENT.value == "v4"

    def test_enum_ordering(self) -> None:
        """Test that enum members are in expected order."""
        versions = list(ConfigVersion)
        assert versions == [
            ConfigVersion.V1,
            ConfigVersion.V2,
            ConfigVersion.V3,
            ConfigVersion.V4_CURRENT,
        ]

    def test_enum_member_count(self) -> None:
        """Test that we have exactly four versions."""
        assert len(ConfigVersion) == 4


# ---------------------------------------------------------------------------
# Migration dataclass tests
# ---------------------------------------------------------------------------


class TestMigration:
    """Tests for the Migration dataclass."""

    def test_migration_creation(self) -> None:
        """Test creating a migration with all fields."""
        migration = Migration(
            from_version=ConfigVersion.V1,
            to_version=ConfigVersion.V2,
            description="Test migration",
            migrate=lambda c: c,
        )
        assert migration.from_version == ConfigVersion.V1
        assert migration.to_version == ConfigVersion.V2
        assert migration.description == "Test migration"

    def test_migration_callable(self) -> None:
        """Test that the migrate callable works."""

        def add_field(config: dict) -> dict:
            config["new_field"] = True
            return config

        migration = Migration(
            from_version=ConfigVersion.V1,
            to_version=ConfigVersion.V2,
            description="Add new_field",
            migrate=add_field,
        )
        result = migration.migrate({"existing": 1})
        assert result["new_field"] is True
        assert result["existing"] == 1


# ---------------------------------------------------------------------------
# MigrationResult dataclass tests
# ---------------------------------------------------------------------------


class TestMigrationResult:
    """Tests for the MigrationResult dataclass."""

    def test_default_fields(self) -> None:
        """Test that default fields are properly initialized."""
        result = MigrationResult(
            original_version=ConfigVersion.V1,
            target_version=ConfigVersion.V4_CURRENT,
        )
        assert result.original_version == ConfigVersion.V1
        assert result.target_version == ConfigVersion.V4_CURRENT
        assert result.migrations_applied == []
        assert result.warnings == []
        assert result.config == {}
        assert result.changes_preview == []

    def test_mutable_defaults_are_independent(self) -> None:
        """Test that mutable default fields are not shared between instances."""
        result1 = MigrationResult(
            original_version=ConfigVersion.V1,
            target_version=ConfigVersion.V4_CURRENT,
        )
        result2 = MigrationResult(
            original_version=ConfigVersion.V2,
            target_version=ConfigVersion.V4_CURRENT,
        )
        result1.warnings.append("test warning")
        assert result2.warnings == []


# ---------------------------------------------------------------------------
# Version detection tests
# ---------------------------------------------------------------------------


class TestDetectVersion:
    """Tests for MigrationChain.detect_version()."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_detect_v1_with_api_key(self, v1_config: dict) -> None:
        """Test that api_key triggers V1 detection."""
        assert self.chain.detect_version(v1_config) == ConfigVersion.V1

    def test_detect_v1_with_server_field(self) -> None:
        """Test that 'server' (without mcp_server) triggers V1 detection."""
        config = {
            "server": {"command": "npx", "args": []},
            "provider": "anthropic",
        }
        assert self.chain.detect_version(config) == ConfigVersion.V1

    def test_detect_v1_api_key_alone(self) -> None:
        """Test that api_key alone triggers V1 even with other modern fields."""
        config = {
            "api_key": "sk-ant-fake",
            "mcp_server": {"command": "npx", "args": []},
            "benchmark": "swe-bench-verified",
        }
        assert self.chain.detect_version(config) == ConfigVersion.V1

    def test_detect_v2(self, v2_config: dict) -> None:
        """Test V2 detection: mcp_server without benchmark or infrastructure."""
        assert self.chain.detect_version(v2_config) == ConfigVersion.V2

    def test_detect_v2_minimal(self) -> None:
        """Test V2 detection with minimal fields."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "provider": "anthropic",
        }
        assert self.chain.detect_version(config) == ConfigVersion.V2

    def test_detect_v3(self, v3_config: dict) -> None:
        """Test V3 detection: mcp_server + benchmark + infrastructure."""
        assert self.chain.detect_version(v3_config) == ConfigVersion.V3

    def test_detect_v3_with_benchmark_only(self) -> None:
        """Test V3 detection with benchmark but no infrastructure."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "benchmark": "swe-bench-verified",
        }
        assert self.chain.detect_version(config) == ConfigVersion.V3

    def test_detect_v3_with_infrastructure_only(self) -> None:
        """Test V3 detection with infrastructure but no benchmark."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "infrastructure": {"mode": "local"},
        }
        assert self.chain.detect_version(config) == ConfigVersion.V3

    def test_detect_v4_with_resource_limits(self, v4_config: dict) -> None:
        """Test V4 detection with resource_limits."""
        assert self.chain.detect_version(v4_config) == ConfigVersion.V4_CURRENT

    def test_detect_v4_with_streaming(self) -> None:
        """Test V4 detection with streaming field."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "streaming": {"enabled": True},
        }
        assert self.chain.detect_version(config) == ConfigVersion.V4_CURRENT

    def test_detect_v4_empty_config(self) -> None:
        """Test that an empty config defaults to V4_CURRENT."""
        assert self.chain.detect_version({}) == ConfigVersion.V4_CURRENT

    def test_detect_v4_resource_limits_only(self) -> None:
        """Test V4 detection with only resource_limits."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "resource_limits": {"max_memory_mb": 2048},
        }
        assert self.chain.detect_version(config) == ConfigVersion.V4_CURRENT


# ---------------------------------------------------------------------------
# get_migrations tests
# ---------------------------------------------------------------------------


class TestGetMigrations:
    """Tests for MigrationChain.get_migrations()."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_v1_to_v4_returns_three_steps(self) -> None:
        """Test that V1 -> V4 requires three migration steps."""
        migrations = self.chain.get_migrations(ConfigVersion.V1, ConfigVersion.V4_CURRENT)
        assert len(migrations) == 3
        assert migrations[0].from_version == ConfigVersion.V1
        assert migrations[0].to_version == ConfigVersion.V2
        assert migrations[1].from_version == ConfigVersion.V2
        assert migrations[1].to_version == ConfigVersion.V3
        assert migrations[2].from_version == ConfigVersion.V3
        assert migrations[2].to_version == ConfigVersion.V4_CURRENT

    def test_v2_to_v4_returns_two_steps(self) -> None:
        """Test that V2 -> V4 requires two migration steps."""
        migrations = self.chain.get_migrations(ConfigVersion.V2, ConfigVersion.V4_CURRENT)
        assert len(migrations) == 2
        assert migrations[0].from_version == ConfigVersion.V2
        assert migrations[1].from_version == ConfigVersion.V3

    def test_v3_to_v4_returns_one_step(self) -> None:
        """Test that V3 -> V4 requires one migration step."""
        migrations = self.chain.get_migrations(ConfigVersion.V3, ConfigVersion.V4_CURRENT)
        assert len(migrations) == 1
        assert migrations[0].from_version == ConfigVersion.V3

    def test_v4_to_v4_returns_empty(self) -> None:
        """Test that V4 -> V4 returns no migrations."""
        migrations = self.chain.get_migrations(ConfigVersion.V4_CURRENT, ConfigVersion.V4_CURRENT)
        assert migrations == []

    def test_downgrade_returns_empty(self) -> None:
        """Test that attempting a downgrade returns no migrations."""
        migrations = self.chain.get_migrations(ConfigVersion.V4_CURRENT, ConfigVersion.V1)
        assert migrations == []

    def test_v1_to_v2_returns_one_step(self) -> None:
        """Test partial migration V1 -> V2."""
        migrations = self.chain.get_migrations(ConfigVersion.V1, ConfigVersion.V2)
        assert len(migrations) == 1
        assert migrations[0].from_version == ConfigVersion.V1
        assert migrations[0].to_version == ConfigVersion.V2

    def test_v1_to_v3_returns_two_steps(self) -> None:
        """Test partial migration V1 -> V3."""
        migrations = self.chain.get_migrations(ConfigVersion.V1, ConfigVersion.V3)
        assert len(migrations) == 2


# ---------------------------------------------------------------------------
# V1 -> V2 migration tests
# ---------------------------------------------------------------------------


class TestMigrateV1ToV2:
    """Tests for the V1 -> V2 migration step."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_removes_api_key(self, v1_config: dict) -> None:
        """Test that api_key is removed."""
        result = MigrationChain._migrate_v1_to_v2(v1_config)
        assert "api_key" not in result

    def test_renames_server_to_mcp_server(self, v1_config: dict) -> None:
        """Test that 'server' is renamed to 'mcp_server'."""
        result = MigrationChain._migrate_v1_to_v2(v1_config)
        assert "server" not in result
        assert "mcp_server" in result
        assert result["mcp_server"]["command"] == "npx"

    def test_preserves_server_env(self, v1_config: dict) -> None:
        """Test that server env vars are preserved in mcp_server."""
        result = MigrationChain._migrate_v1_to_v2(v1_config)
        assert result["mcp_server"]["env"] == {"TOKEN": "abc"}

    def test_preserves_server_args(self, v1_config: dict) -> None:
        """Test that server args are preserved in mcp_server."""
        result = MigrationChain._migrate_v1_to_v2(v1_config)
        assert result["mcp_server"]["args"] == [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "{workdir}",
        ]

    def test_string_server_converted(self) -> None:
        """Test that a simple string 'server' is converted to mcp_server dict."""
        config = {"server": "my-server-command", "api_key": "sk-ant-fake"}
        result = MigrationChain._migrate_v1_to_v2(config)
        assert result["mcp_server"] == {"command": "my-server-command", "args": []}

    def test_preserves_other_fields(self, v1_config: dict) -> None:
        """Test that non-migrated fields are preserved."""
        result = MigrationChain._migrate_v1_to_v2(v1_config)
        assert result["provider"] == "anthropic"
        assert result["model"] == "sonnet"
        assert result["timeout_seconds"] == 300

    def test_no_mutation_of_original(self, v1_config: dict) -> None:
        """Test that the original config dict is not mutated."""
        original_copy = v1_config.copy()
        MigrationChain._migrate_v1_to_v2(v1_config)
        assert v1_config == original_copy

    def test_missing_api_key_is_fine(self) -> None:
        """Test that V1 config without api_key still migrates."""
        config = {
            "server": {"command": "echo", "args": ["hello"]},
        }
        result = MigrationChain._migrate_v1_to_v2(config)
        assert "mcp_server" in result
        assert "server" not in result


# ---------------------------------------------------------------------------
# V2 -> V3 migration tests
# ---------------------------------------------------------------------------


class TestMigrateV2ToV3:
    """Tests for the V2 -> V3 migration step."""

    def test_adds_benchmark_default(self) -> None:
        """Test that benchmark is added with default value."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "provider": "anthropic",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-verified"

    def test_converts_dataset_to_benchmark_lite(self) -> None:
        """Test dataset SWE-bench_Lite is converted to swe-bench-lite."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "SWE-bench/SWE-bench_Lite",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-lite"
        assert "dataset" not in result

    def test_converts_dataset_to_benchmark_verified(self) -> None:
        """Test dataset SWE-bench_Verified is converted to swe-bench-verified."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "SWE-bench/SWE-bench_Verified",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-verified"

    def test_converts_dataset_to_benchmark_full(self) -> None:
        """Test dataset SWE-bench full is converted to swe-bench-full."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "SWE-bench/SWE-bench",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-full"

    def test_converts_princeton_dataset_variant(self) -> None:
        """Test princeton-nlp dataset prefix is also recognized."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "princeton-nlp/SWE-bench_Lite",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-lite"

    def test_unknown_dataset_defaults_to_verified(self) -> None:
        """Test that an unrecognized dataset defaults to swe-bench-verified."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "some-unknown-dataset",
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["benchmark"] == "swe-bench-verified"
        assert "dataset" not in result

    def test_renames_max_tasks_to_sample_size(self, v2_config: dict) -> None:
        """Test that max_tasks is renamed to sample_size."""
        result = MigrationChain._migrate_v2_to_v3(v2_config)
        assert "max_tasks" not in result
        assert result["sample_size"] == 10

    def test_adds_infrastructure_section(self) -> None:
        """Test that infrastructure section is added."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["infrastructure"] == {"mode": "local"}

    def test_preserves_existing_infrastructure(self) -> None:
        """Test that an existing infrastructure field is preserved."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "infrastructure": {"mode": "azure", "azure": {"resource_group": "rg-test"}},
        }
        result = MigrationChain._migrate_v2_to_v3(config)
        assert result["infrastructure"]["mode"] == "azure"

    def test_no_mutation_of_original(self, v2_config: dict) -> None:
        """Test that the original config dict is not mutated."""
        original_keys = set(v2_config.keys())
        MigrationChain._migrate_v2_to_v3(v2_config)
        assert set(v2_config.keys()) == original_keys


# ---------------------------------------------------------------------------
# V3 -> V4 migration tests
# ---------------------------------------------------------------------------


class TestMigrateV3ToV4:
    """Tests for the V3 -> V4 migration step."""

    def test_adds_resource_limits(self, v3_config: dict) -> None:
        """Test that resource_limits section is added."""
        result = MigrationChain._migrate_v3_to_v4(v3_config)
        assert "resource_limits" in result
        assert result["resource_limits"]["max_memory_mb"] == 4096
        assert result["resource_limits"]["max_cpu_percent"] == 80
        assert result["resource_limits"]["max_disk_mb"] == 10240

    def test_adds_streaming_section(self, v3_config: dict) -> None:
        """Test that streaming section is added."""
        result = MigrationChain._migrate_v3_to_v4(v3_config)
        assert "streaming" in result
        assert result["streaming"]["enabled"] is True
        assert result["streaming"]["console_updates"] is True

    def test_preserves_existing_resource_limits(self) -> None:
        """Test that existing resource_limits are not overwritten."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "benchmark": "swe-bench-verified",
            "infrastructure": {"mode": "local"},
            "resource_limits": {"max_memory_mb": 8192},
        }
        result = MigrationChain._migrate_v3_to_v4(config)
        assert result["resource_limits"]["max_memory_mb"] == 8192

    def test_preserves_existing_streaming(self) -> None:
        """Test that existing streaming config is not overwritten."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "benchmark": "swe-bench-verified",
            "infrastructure": {"mode": "local"},
            "streaming": {"enabled": False},
        }
        result = MigrationChain._migrate_v3_to_v4(config)
        assert result["streaming"]["enabled"] is False

    def test_preserves_all_v3_fields(self, v3_config: dict) -> None:
        """Test that all existing V3 fields survive the migration."""
        result = MigrationChain._migrate_v3_to_v4(v3_config)
        assert result["mcp_server"] == v3_config["mcp_server"]
        assert result["provider"] == "anthropic"
        assert result["model"] == "sonnet"
        assert result["benchmark"] == "swe-bench-verified"
        assert result["sample_size"] == 5
        assert result["infrastructure"] == {"mode": "local"}

    def test_no_mutation_of_original(self, v3_config: dict) -> None:
        """Test that the original config dict is not mutated."""
        original_keys = set(v3_config.keys())
        MigrationChain._migrate_v3_to_v4(v3_config)
        assert set(v3_config.keys()) == original_keys


# ---------------------------------------------------------------------------
# Full chain migration tests
# ---------------------------------------------------------------------------


class TestFullChainMigration:
    """Tests for running the full migration chain."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_v1_to_current_full_chain(self, v1_config: dict) -> None:
        """Test full migration from V1 to V4_CURRENT."""
        result = self.chain.migrate(v1_config)

        assert result.original_version == ConfigVersion.V1
        assert result.target_version == ConfigVersion.V4_CURRENT
        assert len(result.migrations_applied) == 3

        config = result.config
        # V1 -> V2 changes
        assert "api_key" not in config
        assert "server" not in config
        assert "mcp_server" in config
        # V2 -> V3 changes
        assert "benchmark" in config
        assert "max_tasks" not in config
        assert "infrastructure" in config
        # V3 -> V4 changes
        assert "resource_limits" in config
        assert "streaming" in config

    def test_v2_to_current(self, v2_config: dict) -> None:
        """Test migration from V2 to V4_CURRENT."""
        result = self.chain.migrate(v2_config)

        assert result.original_version == ConfigVersion.V2
        assert len(result.migrations_applied) == 2

        config = result.config
        assert "dataset" not in config
        assert config["benchmark"] == "swe-bench-lite"
        assert config["sample_size"] == 10
        assert "resource_limits" in config
        assert "streaming" in config

    def test_v3_to_current(self, v3_config: dict) -> None:
        """Test migration from V3 to V4_CURRENT."""
        result = self.chain.migrate(v3_config)

        assert result.original_version == ConfigVersion.V3
        assert len(result.migrations_applied) == 1
        assert "resource_limits" in result.config
        assert "streaming" in result.config

    def test_v4_no_migration_needed(self, v4_config: dict) -> None:
        """Test that V4 config needs no migration."""
        result = self.chain.migrate(v4_config)

        assert result.original_version == ConfigVersion.V4_CURRENT
        assert len(result.migrations_applied) == 0
        assert result.config == v4_config

    def test_migration_preserves_unknown_fields(self) -> None:
        """Test that unknown/custom fields survive migration."""
        config = {
            "api_key": "sk-ant-fake",
            "server": {"command": "echo", "args": []},
            "custom_field": "preserved",
            "extra_stuff": [1, 2, 3],
        }
        result = self.chain.migrate(config)
        assert result.config["custom_field"] == "preserved"
        assert result.config["extra_stuff"] == [1, 2, 3]

    def test_original_config_not_mutated(self, v1_config: dict) -> None:
        """Test that the original config dict is never mutated by migrate."""
        import copy

        original = copy.deepcopy(v1_config)
        self.chain.migrate(v1_config)
        assert v1_config == original


# ---------------------------------------------------------------------------
# Dry-run tests
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for dry-run migration mode."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_dry_run_does_not_modify_config(self, v1_config: dict) -> None:
        """Test that dry-run returns the original config unchanged."""
        result = self.chain.migrate(v1_config, dry_run=True)
        # The result config should be the original (not migrated)
        assert "api_key" in result.config
        assert "server" in result.config

    def test_dry_run_populates_changes_preview(self, v1_config: dict) -> None:
        """Test that dry-run populates changes_preview."""
        result = self.chain.migrate(v1_config, dry_run=True)
        assert len(result.changes_preview) > 0
        assert any("V1 -> V2" in c for c in result.changes_preview)

    def test_dry_run_populates_migrations_applied(self, v1_config: dict) -> None:
        """Test that dry-run still records which migrations would be applied."""
        result = self.chain.migrate(v1_config, dry_run=True)
        assert len(result.migrations_applied) == 3

    def test_dry_run_v4_shows_no_changes(self, v4_config: dict) -> None:
        """Test that dry-run on V4 config shows no changes needed."""
        result = self.chain.migrate(v4_config, dry_run=True)
        assert len(result.migrations_applied) == 0
        assert any("already at the current version" in c for c in result.changes_preview)


# ---------------------------------------------------------------------------
# migrate_config_file tests
# ---------------------------------------------------------------------------


class TestMigrateConfigFile:
    """Tests for the migrate_config_file() function."""

    def _write_yaml(self, path: Path, config: dict) -> None:
        """Helper to write a config dict as YAML."""
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    def test_migrate_v1_file(self, tmp_config_dir: Path, v1_config: dict) -> None:
        """Test migrating a V1 config file to current version."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v1_config)

        result = migrate_config_file(config_file)

        assert result.original_version == ConfigVersion.V1
        assert len(result.migrations_applied) == 3

        # Re-read the file and verify it was updated
        with open(config_file) as f:
            migrated = yaml.safe_load(f)
        assert "api_key" not in migrated
        assert "mcp_server" in migrated
        assert "resource_limits" in migrated

    def test_backup_created(self, tmp_config_dir: Path, v1_config: dict) -> None:
        """Test that a backup file is created."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v1_config)

        migrate_config_file(config_file, backup=True)

        backup_file = tmp_config_dir / "config.yaml.bak"
        assert backup_file.exists()

        # Verify backup has original content
        with open(backup_file) as f:
            backup_config = yaml.safe_load(f)
        assert "api_key" in backup_config
        assert "server" in backup_config

    def test_no_backup_when_disabled(self, tmp_config_dir: Path, v1_config: dict) -> None:
        """Test that backup is skipped when backup=False."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v1_config)

        migrate_config_file(config_file, backup=False)

        backup_file = tmp_config_dir / "config.yaml.bak"
        assert not backup_file.exists()

    def test_dry_run_does_not_modify_file(self, tmp_config_dir: Path, v1_config: dict) -> None:
        """Test that dry-run mode does not modify the config file."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v1_config)

        # Record original content
        original_content = config_file.read_text()

        result = migrate_config_file(config_file, dry_run=True)

        # File should be unchanged
        assert config_file.read_text() == original_content
        # But result should indicate migrations would be applied
        assert len(result.migrations_applied) == 3

    def test_dry_run_no_backup(self, tmp_config_dir: Path, v1_config: dict) -> None:
        """Test that dry-run mode does not create a backup."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v1_config)

        migrate_config_file(config_file, dry_run=True, backup=True)

        backup_file = tmp_config_dir / "config.yaml.bak"
        assert not backup_file.exists()

    def test_v4_file_not_modified(self, tmp_config_dir: Path, v4_config: dict) -> None:
        """Test that a V4 config file is not modified or backed up."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v4_config)

        original_content = config_file.read_text()
        result = migrate_config_file(config_file)

        assert result.original_version == ConfigVersion.V4_CURRENT
        assert len(result.migrations_applied) == 0
        # File should be unchanged
        assert config_file.read_text() == original_content
        # No backup should exist
        assert not (tmp_config_dir / "config.yaml.bak").exists()

    def test_file_not_found(self, tmp_config_dir: Path) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            migrate_config_file(tmp_config_dir / "nonexistent.yaml")

    def test_migrate_v2_file(self, tmp_config_dir: Path, v2_config: dict) -> None:
        """Test migrating a V2 config file."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v2_config)

        result = migrate_config_file(config_file)

        assert result.original_version == ConfigVersion.V2
        assert len(result.migrations_applied) == 2

        with open(config_file) as f:
            migrated = yaml.safe_load(f)
        assert "dataset" not in migrated
        assert migrated["benchmark"] == "swe-bench-lite"

    def test_migrate_v3_file(self, tmp_config_dir: Path, v3_config: dict) -> None:
        """Test migrating a V3 config file."""
        config_file = tmp_config_dir / "config.yaml"
        self._write_yaml(config_file, v3_config)

        result = migrate_config_file(config_file)

        assert result.original_version == ConfigVersion.V3
        assert len(result.migrations_applied) == 1

        with open(config_file) as f:
            migrated = yaml.safe_load(f)
        assert "resource_limits" in migrated
        assert "streaming" in migrated


# ---------------------------------------------------------------------------
# format_migration_report tests
# ---------------------------------------------------------------------------


class TestFormatMigrationReport:
    """Tests for the format_migration_report() function."""

    def test_report_no_migration_needed(self, capsys: pytest.CaptureFixture) -> None:
        """Test report output when no migration is needed."""
        result = MigrationResult(
            original_version=ConfigVersion.V4_CURRENT,
            target_version=ConfigVersion.V4_CURRENT,
        )
        format_migration_report(result)
        # The function writes to stderr via Rich console, so we just verify
        # it runs without error. Detailed output verification is difficult
        # because Rich uses ANSI codes.

    def test_report_with_migrations(self, capsys: pytest.CaptureFixture) -> None:
        """Test report output with applied migrations."""
        result = MigrationResult(
            original_version=ConfigVersion.V1,
            target_version=ConfigVersion.V4_CURRENT,
            migrations_applied=[
                "V1 -> V2: Move api_key to env vars",
                "V2 -> V3: Add benchmark field",
                "V3 -> V4: Add resource_limits",
            ],
            changes_preview=["Apply: V1 -> V2", "Apply: V2 -> V3", "Apply: V3 -> V4"],
        )
        format_migration_report(result)

    def test_report_with_warnings(self, capsys: pytest.CaptureFixture) -> None:
        """Test report output with warnings."""
        result = MigrationResult(
            original_version=ConfigVersion.V1,
            target_version=ConfigVersion.V4_CURRENT,
            migrations_applied=["V1 -> V2: test"],
            warnings=["Field 'deprecated_field' was removed"],
        )
        format_migration_report(result)


# ---------------------------------------------------------------------------
# Edge case and integration tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and unusual configurations."""

    def setup_method(self) -> None:
        """Set up a MigrationChain for each test."""
        self.chain = MigrationChain()

    def test_empty_config_detected_as_v4(self) -> None:
        """Test that an empty config is detected as V4 (current)."""
        result = self.chain.migrate({})
        assert result.original_version == ConfigVersion.V4_CURRENT
        assert len(result.migrations_applied) == 0

    def test_v1_with_both_server_and_api_key(self) -> None:
        """Test V1 config with both legacy markers."""
        config = {
            "api_key": "sk-ant-fake",
            "server": {"command": "npx", "args": ["{workdir}"]},
        }
        result = self.chain.migrate(config)
        assert result.original_version == ConfigVersion.V1
        assert "api_key" not in result.config
        assert "server" not in result.config
        assert "mcp_server" in result.config

    def test_v1_server_with_name_field(self) -> None:
        """Test V1 config where server dict includes a name field."""
        config = {
            "server": {
                "name": "my-tool",
                "command": "python",
                "args": ["-m", "myserver"],
            },
        }
        result = MigrationChain._migrate_v1_to_v2(config)
        assert result["mcp_server"]["name"] == "my-tool"

    def test_v2_with_dataset_and_max_tasks(self) -> None:
        """Test V2 config that has both dataset and max_tasks fields."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "dataset": "princeton-nlp/SWE-bench_Verified",
            "max_tasks": 25,
        }
        result = self.chain.migrate(config)
        assert result.config["benchmark"] == "swe-bench-verified"
        assert result.config["sample_size"] == 25
        assert "dataset" not in result.config
        assert "max_tasks" not in result.config

    def test_deeply_nested_fields_preserved(self) -> None:
        """Test that deeply nested custom fields survive full migration."""
        config = {
            "api_key": "sk-ant-fake",
            "server": {"command": "echo", "args": []},
            "custom": {
                "nested": {
                    "deep": {"value": 42},
                },
            },
        }
        result = self.chain.migrate(config)
        assert result.config["custom"]["nested"]["deep"]["value"] == 42

    def test_config_with_none_values(self) -> None:
        """Test migration handles None values gracefully."""
        config = {
            "mcp_server": {"command": "echo", "args": []},
            "sample_size": None,
            "agent_prompt": None,
        }
        result = self.chain.migrate(config)
        assert result.config["sample_size"] is None
        assert result.config["agent_prompt"] is None

    def test_v1_with_empty_server_dict(self) -> None:
        """Test V1 migration with empty server dict."""
        config = {"server": {}}
        result = MigrationChain._migrate_v1_to_v2(config)
        assert "mcp_server" in result
        assert result["mcp_server"] == {}

    def test_migration_result_changes_preview_populated(self, v1_config: dict) -> None:
        """Test that changes_preview is populated correctly."""
        result = self.chain.migrate(v1_config)
        assert len(result.changes_preview) >= 3
        # Each migration step should add a preview entry
        assert any("V1 -> V2" in p for p in result.changes_preview)
        assert any("V2 -> V3" in p for p in result.changes_preview)
        assert any("V3 -> V4" in p for p in result.changes_preview)
