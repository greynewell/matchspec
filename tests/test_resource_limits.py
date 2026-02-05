"""Tests for resource limits configuration module."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.resource_limits import (
    DEFAULT_LIMITS,
    VALID_NETWORK_MODES,
    ContainerResourceConfig,
    ResourceLimits,
    ResourceMonitor,
    ResourceUsage,
    _parse_memory_usage,
    parse_resource_limits,
)


class TestResourceLimits:
    """Tests for the ResourceLimits dataclass."""

    def test_default_values(self):
        """Test that default ResourceLimits has sensible defaults."""
        limits = ResourceLimits()

        assert limits.cpu_count is None
        assert limits.memory_mb is None
        assert limits.memory_swap_mb is None
        assert limits.disk_mb is None
        assert limits.network_mode is None
        assert limits.pids_limit is None
        assert limits.task_timeout_seconds == 600
        assert limits.total_timeout_seconds is None

    def test_custom_values(self):
        """Test creating ResourceLimits with custom values."""
        limits = ResourceLimits(
            cpu_count=4.0,
            memory_mb=8192,
            memory_swap_mb=16384,
            disk_mb=20480,
            network_mode="none",
            pids_limit=512,
            task_timeout_seconds=300,
            total_timeout_seconds=7200,
        )

        assert limits.cpu_count == 4.0
        assert limits.memory_mb == 8192
        assert limits.memory_swap_mb == 16384
        assert limits.disk_mb == 20480
        assert limits.network_mode == "none"
        assert limits.pids_limit == 512
        assert limits.task_timeout_seconds == 300
        assert limits.total_timeout_seconds == 7200

    def test_partial_values(self):
        """Test creating ResourceLimits with only some fields set."""
        limits = ResourceLimits(cpu_count=2.0, memory_mb=4096)

        assert limits.cpu_count == 2.0
        assert limits.memory_mb == 4096
        assert limits.memory_swap_mb is None
        assert limits.disk_mb is None
        assert limits.task_timeout_seconds == 600


class TestResourceUsage:
    """Tests for the ResourceUsage dataclass."""

    def test_default_values(self):
        """Test that default ResourceUsage starts at zero."""
        usage = ResourceUsage()

        assert usage.cpu_percent == 0.0
        assert usage.memory_mb == 0.0
        assert usage.disk_mb == 0.0
        assert usage.pids == 0

    def test_custom_values(self):
        """Test creating ResourceUsage with custom values."""
        usage = ResourceUsage(
            cpu_percent=150.5,
            memory_mb=2048.0,
            disk_mb=5120.0,
            pids=42,
        )

        assert usage.cpu_percent == 150.5
        assert usage.memory_mb == 2048.0
        assert usage.disk_mb == 5120.0
        assert usage.pids == 42


class TestDefaultLimits:
    """Tests for the DEFAULT_LIMITS constant."""

    def test_default_limits_are_sensible(self):
        """Test that DEFAULT_LIMITS has reasonable values."""
        assert DEFAULT_LIMITS.cpu_count == 2.0
        assert DEFAULT_LIMITS.memory_mb == 4096
        assert DEFAULT_LIMITS.memory_swap_mb == 8192
        assert DEFAULT_LIMITS.disk_mb == 10240
        assert DEFAULT_LIMITS.network_mode == "bridge"
        assert DEFAULT_LIMITS.pids_limit == 256
        assert DEFAULT_LIMITS.task_timeout_seconds == 600
        assert DEFAULT_LIMITS.total_timeout_seconds is None

    def test_default_limits_is_resource_limits_instance(self):
        """Test that DEFAULT_LIMITS is a ResourceLimits instance."""
        assert isinstance(DEFAULT_LIMITS, ResourceLimits)


class TestContainerResourceConfig:
    """Tests for ContainerResourceConfig class."""

    def test_from_limits_full(self):
        """Test converting full ResourceLimits to Docker config."""
        limits = ResourceLimits(
            cpu_count=2.0,
            memory_mb=4096,
            memory_swap_mb=8192,
            network_mode="bridge",
            pids_limit=256,
        )

        config = ContainerResourceConfig.from_limits(limits)

        assert config["nano_cpus"] == 2_000_000_000
        assert config["mem_limit"] == "4096m"
        assert config["memswap_limit"] == "8192m"
        assert config["network_mode"] == "bridge"
        assert config["pids_limit"] == 256

    def test_from_limits_empty(self):
        """Test converting ResourceLimits with no limits set."""
        limits = ResourceLimits()
        config = ContainerResourceConfig.from_limits(limits)

        # Only task_timeout_seconds has a default, but it's not a Docker config
        assert "nano_cpus" not in config
        assert "mem_limit" not in config
        assert "memswap_limit" not in config
        assert "network_mode" not in config
        assert "pids_limit" not in config

    def test_from_limits_partial(self):
        """Test converting ResourceLimits with only some fields."""
        limits = ResourceLimits(cpu_count=1.5, memory_mb=2048)
        config = ContainerResourceConfig.from_limits(limits)

        assert config["nano_cpus"] == 1_500_000_000
        assert config["mem_limit"] == "2048m"
        assert "memswap_limit" not in config
        assert "network_mode" not in config
        assert "pids_limit" not in config

    def test_from_limits_fractional_cpu(self):
        """Test fractional CPU values are correctly converted to nano CPUs."""
        limits = ResourceLimits(cpu_count=0.5)
        config = ContainerResourceConfig.from_limits(limits)

        assert config["nano_cpus"] == 500_000_000

    def test_from_limits_network_none(self):
        """Test network_mode='none' is passed through."""
        limits = ResourceLimits(network_mode="none")
        config = ContainerResourceConfig.from_limits(limits)

        assert config["network_mode"] == "none"

    def test_from_limits_disk_not_in_docker_config(self):
        """Test that disk_mb is not included in Docker config (not natively supported)."""
        limits = ResourceLimits(disk_mb=10240)
        config = ContainerResourceConfig.from_limits(limits)

        assert "disk_mb" not in config
        assert "disk_limit" not in config

    def test_from_limits_timeouts_not_in_docker_config(self):
        """Test that timeout fields are not included in Docker config."""
        limits = ResourceLimits(task_timeout_seconds=300, total_timeout_seconds=3600)
        config = ContainerResourceConfig.from_limits(limits)

        assert "task_timeout_seconds" not in config
        assert "total_timeout_seconds" not in config

    def test_validate_no_warnings(self):
        """Test validation with sensible limits produces no warnings."""
        limits = ResourceLimits(
            cpu_count=2.0,
            memory_mb=4096,
            memory_swap_mb=8192,
            network_mode="bridge",
            pids_limit=256,
            task_timeout_seconds=600,
        )
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert warnings == []

    def test_validate_swap_less_than_memory(self):
        """Test validation warns when swap < memory."""
        limits = ResourceLimits(memory_mb=4096, memory_swap_mb=2048)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert len(warnings) == 1
        assert "memory_swap_mb" in warnings[0]
        assert "less than" in warnings[0]

    def test_validate_invalid_network_mode(self):
        """Test validation warns about invalid network mode."""
        limits = ResourceLimits(network_mode="custom_network")
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("network_mode" in w for w in warnings)
        assert any("custom_network" in w for w in warnings)

    def test_validate_low_memory(self):
        """Test validation warns about very low memory."""
        limits = ResourceLimits(memory_mb=128)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("memory_mb" in w and "very low" in w for w in warnings)

    def test_validate_low_cpu(self):
        """Test validation warns about very low CPU."""
        limits = ResourceLimits(cpu_count=0.1)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("cpu_count" in w and "very low" in w for w in warnings)

    def test_validate_low_timeout(self):
        """Test validation warns about very low timeout."""
        limits = ResourceLimits(task_timeout_seconds=10)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("task_timeout_seconds" in w and "very low" in w for w in warnings)

    def test_validate_low_pids(self):
        """Test validation warns about very low PID limit."""
        limits = ResourceLimits(pids_limit=4)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("pids_limit" in w and "very low" in w for w in warnings)

    def test_validate_negative_cpu(self):
        """Test validation warns about negative CPU count."""
        limits = ResourceLimits(cpu_count=-1.0)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("cpu_count" in w and "must be positive" in w for w in warnings)

    def test_validate_zero_memory(self):
        """Test validation warns about zero memory."""
        limits = ResourceLimits(memory_mb=0)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("memory_mb" in w and "must be positive" in w for w in warnings)

    def test_validate_negative_disk(self):
        """Test validation warns about negative disk."""
        limits = ResourceLimits(disk_mb=-100)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("disk_mb" in w and "must be positive" in w for w in warnings)

    def test_validate_zero_pids(self):
        """Test validation warns about zero PIDs."""
        limits = ResourceLimits(pids_limit=0)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("pids_limit" in w and "must be positive" in w for w in warnings)

    def test_validate_zero_timeout(self):
        """Test validation warns about zero task timeout."""
        limits = ResourceLimits(task_timeout_seconds=0)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("task_timeout_seconds" in w and "must be positive" in w for w in warnings)

    def test_validate_negative_total_timeout(self):
        """Test validation warns about negative total timeout."""
        limits = ResourceLimits(total_timeout_seconds=-100)
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert any("total_timeout_seconds" in w and "must be positive" in w for w in warnings)

    def test_validate_empty_limits(self):
        """Test validation with default (empty) limits produces no warnings."""
        limits = ResourceLimits()
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        assert warnings == []

    def test_validate_multiple_issues(self):
        """Test validation reports multiple issues at once."""
        limits = ResourceLimits(
            cpu_count=-1.0,
            memory_mb=0,
            memory_swap_mb=-100,
            pids_limit=0,
            task_timeout_seconds=0,
        )
        config = ContainerResourceConfig(limits)

        warnings = config.validate()
        # Should have multiple warnings
        assert len(warnings) >= 4


class TestResourceMonitor:
    """Tests for ResourceMonitor class."""

    def test_init_stores_limits(self):
        """Test that monitor stores provided limits."""
        limits = ResourceLimits(cpu_count=2.0, memory_mb=4096)
        monitor = ResourceMonitor(limits)

        assert monitor.limits is limits

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_success(self, mock_run):
        """Test successful container resource check."""
        stats_output = json.dumps(
            {
                "cpu": "75.50%",
                "mem": "1024MiB / 4096MiB",
                "pids": "42",
            }
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=stats_output + "\n",
            stderr="",
        )

        limits = ResourceLimits(cpu_count=2.0, memory_mb=4096)
        monitor = ResourceMonitor(limits)
        usage = monitor.check_container_resources("test_container_id")

        assert usage.cpu_percent == 75.5
        assert usage.memory_mb == 1024.0
        assert usage.pids == 42

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "docker" in call_args[0][0][0]
        assert "stats" in call_args[0][0][1]
        assert "test_container_id" in call_args[0][0][2]

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_gib_memory(self, mock_run):
        """Test parsing GiB memory format."""
        stats_output = json.dumps(
            {
                "cpu": "50.00%",
                "mem": "2.5GiB / 8GiB",
                "pids": "10",
            }
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=stats_output + "\n",
            stderr="",
        )

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)
        usage = monitor.check_container_resources("container123")

        assert usage.cpu_percent == 50.0
        assert usage.memory_mb == 2.5 * 1024  # 2560 MB
        assert usage.pids == 10

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_failure(self, mock_run):
        """Test container resource check when docker stats fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: No such container: bad_id",
        )

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)

        with pytest.raises(RuntimeError, match="docker stats failed"):
            monitor.check_container_resources("bad_id")

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_timeout(self, mock_run):
        """Test container resource check when docker stats times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker stats", timeout=10)

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)

        with pytest.raises(RuntimeError, match="timed out"):
            monitor.check_container_resources("container_id")

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_empty_output(self, mock_run):
        """Test container resource check with empty output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)

        with pytest.raises(RuntimeError, match="Empty output"):
            monitor.check_container_resources("container_id")

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_invalid_json(self, mock_run):
        """Test container resource check with invalid JSON output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json\n",
            stderr="",
        )

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)

        with pytest.raises(RuntimeError, match="Failed to parse"):
            monitor.check_container_resources("container_id")

    @patch("mcpbr.resource_limits.subprocess.run")
    def test_check_container_resources_dashes_for_pids(self, mock_run):
        """Test parsing when PIDs shows as '--' (e.g., container not running)."""
        stats_output = json.dumps(
            {
                "cpu": "0.00%",
                "mem": "0B / 0B",
                "pids": "--",
            }
        )
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=stats_output + "\n",
            stderr="",
        )

        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)
        usage = monitor.check_container_resources("container_id")

        assert usage.pids == 0

    def test_is_within_limits_all_within(self):
        """Test is_within_limits returns True when all within limits."""
        limits = ResourceLimits(
            cpu_count=2.0,
            memory_mb=4096,
            disk_mb=10240,
            pids_limit=256,
        )
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(
            cpu_percent=100.0,
            memory_mb=2048.0,
            disk_mb=5000.0,
            pids=50,
        )

        assert monitor.is_within_limits(usage) is True

    def test_is_within_limits_cpu_exceeded(self):
        """Test is_within_limits returns False when CPU exceeds limit."""
        limits = ResourceLimits(cpu_count=2.0)  # 200% max
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(cpu_percent=250.0)

        assert monitor.is_within_limits(usage) is False

    def test_is_within_limits_memory_exceeded(self):
        """Test is_within_limits returns False when memory exceeds limit."""
        limits = ResourceLimits(memory_mb=4096)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(memory_mb=5000.0)

        assert monitor.is_within_limits(usage) is False

    def test_is_within_limits_disk_exceeded(self):
        """Test is_within_limits returns False when disk exceeds limit."""
        limits = ResourceLimits(disk_mb=10240)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(disk_mb=15000.0)

        assert monitor.is_within_limits(usage) is False

    def test_is_within_limits_pids_exceeded(self):
        """Test is_within_limits returns False when PIDs exceed limit."""
        limits = ResourceLimits(pids_limit=256)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(pids=300)

        assert monitor.is_within_limits(usage) is False

    def test_is_within_limits_no_limits_set(self):
        """Test is_within_limits returns True when no limits are configured."""
        limits = ResourceLimits()
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(
            cpu_percent=999.0,
            memory_mb=99999.0,
            disk_mb=99999.0,
            pids=9999,
        )

        assert monitor.is_within_limits(usage) is True

    def test_is_within_limits_at_exact_limit(self):
        """Test is_within_limits at exact boundary (should be within)."""
        limits = ResourceLimits(cpu_count=2.0, memory_mb=4096, pids_limit=256)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(cpu_percent=200.0, memory_mb=4096.0, pids=256)

        assert monitor.is_within_limits(usage) is True

    def test_get_violations_empty(self):
        """Test get_violations returns empty list when within limits."""
        limits = ResourceLimits(cpu_count=4.0, memory_mb=8192)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(cpu_percent=100.0, memory_mb=2048.0)

        violations = monitor.get_violations(usage)
        assert violations == []

    def test_get_violations_cpu(self):
        """Test get_violations reports CPU violation."""
        limits = ResourceLimits(cpu_count=1.0)  # 100% max
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(cpu_percent=150.0)

        violations = monitor.get_violations(usage)
        assert len(violations) == 1
        assert "CPU usage" in violations[0]
        assert "150.0%" in violations[0]

    def test_get_violations_memory(self):
        """Test get_violations reports memory violation."""
        limits = ResourceLimits(memory_mb=4096)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(memory_mb=6000.0)

        violations = monitor.get_violations(usage)
        assert len(violations) == 1
        assert "Memory usage" in violations[0]
        assert "6000.0MB" in violations[0]

    def test_get_violations_disk(self):
        """Test get_violations reports disk violation."""
        limits = ResourceLimits(disk_mb=10240)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(disk_mb=20000.0)

        violations = monitor.get_violations(usage)
        assert len(violations) == 1
        assert "Disk usage" in violations[0]

    def test_get_violations_pids(self):
        """Test get_violations reports PID violation."""
        limits = ResourceLimits(pids_limit=100)
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(pids=150)

        violations = monitor.get_violations(usage)
        assert len(violations) == 1
        assert "PID count" in violations[0]
        assert "150" in violations[0]

    def test_get_violations_multiple(self):
        """Test get_violations reports multiple violations at once."""
        limits = ResourceLimits(
            cpu_count=1.0,
            memory_mb=2048,
            disk_mb=5000,
            pids_limit=50,
        )
        monitor = ResourceMonitor(limits)
        usage = ResourceUsage(
            cpu_percent=200.0,
            memory_mb=4096.0,
            disk_mb=10000.0,
            pids=100,
        )

        violations = monitor.get_violations(usage)
        assert len(violations) == 4
        assert any("CPU" in v for v in violations)
        assert any("Memory" in v for v in violations)
        assert any("Disk" in v for v in violations)
        assert any("PID" in v for v in violations)


class TestParseMemoryUsage:
    """Tests for the _parse_memory_usage helper function."""

    def test_parse_mib(self):
        """Test parsing MiB format."""
        assert _parse_memory_usage("512MiB / 4GiB") == 512.0

    def test_parse_gib(self):
        """Test parsing GiB format."""
        assert _parse_memory_usage("2GiB / 8GiB") == 2 * 1024

    def test_parse_fractional_gib(self):
        """Test parsing fractional GiB format."""
        assert _parse_memory_usage("1.5GiB / 8GiB") == 1.5 * 1024

    def test_parse_kib(self):
        """Test parsing KiB format."""
        result = _parse_memory_usage("512KiB / 4GiB")
        assert result == 512 / 1024

    def test_parse_bytes(self):
        """Test parsing bytes format."""
        result = _parse_memory_usage("0B / 0B")
        assert result == 0.0

    def test_parse_mb(self):
        """Test parsing MB format."""
        assert _parse_memory_usage("256MB / 4GB") == 256.0

    def test_parse_gb(self):
        """Test parsing GB format."""
        assert _parse_memory_usage("4GB / 16GB") == 4 * 1024

    def test_parse_empty(self):
        """Test parsing empty string."""
        assert _parse_memory_usage("") == 0.0

    def test_parse_no_slash(self):
        """Test parsing string without slash separator."""
        assert _parse_memory_usage("512MiB") == 512.0

    def test_parse_invalid(self):
        """Test parsing invalid format returns 0."""
        assert _parse_memory_usage("invalid") == 0.0


class TestParseResourceLimits:
    """Tests for parse_resource_limits function."""

    def test_parse_full_config(self):
        """Test parsing a complete config dictionary."""
        config = {
            "cpu_count": 2.0,
            "memory_mb": 4096,
            "memory_swap_mb": 8192,
            "disk_mb": 10240,
            "network_mode": "bridge",
            "pids_limit": 256,
            "task_timeout_seconds": 300,
            "total_timeout_seconds": 3600,
        }

        limits = parse_resource_limits(config)

        assert limits.cpu_count == 2.0
        assert limits.memory_mb == 4096
        assert limits.memory_swap_mb == 8192
        assert limits.disk_mb == 10240
        assert limits.network_mode == "bridge"
        assert limits.pids_limit == 256
        assert limits.task_timeout_seconds == 300
        assert limits.total_timeout_seconds == 3600

    def test_parse_empty_config(self):
        """Test parsing an empty config returns defaults."""
        limits = parse_resource_limits({})

        assert limits.cpu_count is None
        assert limits.memory_mb is None
        assert limits.task_timeout_seconds == 600
        assert limits.total_timeout_seconds is None

    def test_parse_partial_config(self):
        """Test parsing a partial config."""
        config = {
            "cpu_count": 1.5,
            "memory_mb": 2048,
        }

        limits = parse_resource_limits(config)

        assert limits.cpu_count == 1.5
        assert limits.memory_mb == 2048
        assert limits.memory_swap_mb is None
        assert limits.disk_mb is None
        assert limits.network_mode is None

    def test_parse_type_conversion_int_to_float(self):
        """Test that integer cpu_count is converted to float."""
        config = {"cpu_count": 2}

        limits = parse_resource_limits(config)

        assert limits.cpu_count == 2.0
        assert isinstance(limits.cpu_count, float)

    def test_parse_type_conversion_float_to_int(self):
        """Test that float memory values are converted to int."""
        config = {"memory_mb": 4096.0}

        limits = parse_resource_limits(config)

        assert limits.memory_mb == 4096
        assert isinstance(limits.memory_mb, int)

    def test_parse_string_network_mode(self):
        """Test that network_mode is converted to string."""
        config = {"network_mode": "none"}

        limits = parse_resource_limits(config)

        assert limits.network_mode == "none"
        assert isinstance(limits.network_mode, str)

    def test_parse_unknown_keys_ignored(self):
        """Test that unknown config keys are ignored with warning."""
        config = {
            "cpu_count": 2.0,
            "unknown_key": "some_value",
            "another_unknown": 42,
        }

        with patch("mcpbr.resource_limits.logger") as mock_logger:
            limits = parse_resource_limits(config)

            # Should still parse known keys
            assert limits.cpu_count == 2.0

            # Should warn about unknown keys
            assert mock_logger.warning.call_count == 2

    def test_parse_only_timeout(self):
        """Test parsing with only timeout configuration."""
        config = {
            "task_timeout_seconds": 1200,
            "total_timeout_seconds": 7200,
        }

        limits = parse_resource_limits(config)

        assert limits.task_timeout_seconds == 1200
        assert limits.total_timeout_seconds == 7200
        assert limits.cpu_count is None

    def test_parse_result_is_resource_limits(self):
        """Test that parse result is a ResourceLimits instance."""
        config = {"cpu_count": 1.0}
        limits = parse_resource_limits(config)

        assert isinstance(limits, ResourceLimits)


class TestValidNetworkModes:
    """Tests for VALID_NETWORK_MODES constant."""

    def test_contains_standard_modes(self):
        """Test that standard Docker network modes are included."""
        assert "bridge" in VALID_NETWORK_MODES
        assert "host" in VALID_NETWORK_MODES
        assert "none" in VALID_NETWORK_MODES

    def test_is_tuple(self):
        """Test that VALID_NETWORK_MODES is a tuple (immutable)."""
        assert isinstance(VALID_NETWORK_MODES, tuple)


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_parse_then_convert_to_docker(self):
        """Test full pipeline: parse config -> validate -> generate Docker kwargs."""
        config = {
            "cpu_count": 2.0,
            "memory_mb": 4096,
            "memory_swap_mb": 8192,
            "network_mode": "bridge",
            "pids_limit": 256,
            "task_timeout_seconds": 600,
        }

        # Parse config
        limits = parse_resource_limits(config)

        # Validate
        container_config = ContainerResourceConfig(limits)
        warnings = container_config.validate()
        assert warnings == []

        # Convert to Docker kwargs
        docker_kwargs = ContainerResourceConfig.from_limits(limits)
        assert docker_kwargs["nano_cpus"] == 2_000_000_000
        assert docker_kwargs["mem_limit"] == "4096m"
        assert docker_kwargs["memswap_limit"] == "8192m"
        assert docker_kwargs["network_mode"] == "bridge"
        assert docker_kwargs["pids_limit"] == 256

    def test_parse_then_monitor(self):
        """Test full pipeline: parse config -> create monitor -> check usage."""
        config = {
            "cpu_count": 4.0,
            "memory_mb": 8192,
            "pids_limit": 512,
        }

        limits = parse_resource_limits(config)
        monitor = ResourceMonitor(limits)

        # Usage within limits
        usage_ok = ResourceUsage(cpu_percent=200.0, memory_mb=4096.0, pids=100)
        assert monitor.is_within_limits(usage_ok) is True
        assert monitor.get_violations(usage_ok) == []

        # Usage exceeding limits
        usage_bad = ResourceUsage(cpu_percent=500.0, memory_mb=10000.0, pids=1000)
        assert monitor.is_within_limits(usage_bad) is False
        violations = monitor.get_violations(usage_bad)
        assert len(violations) == 3

    def test_default_limits_validate_cleanly(self):
        """Test that DEFAULT_LIMITS passes validation without warnings."""
        config = ContainerResourceConfig(DEFAULT_LIMITS)
        warnings = config.validate()
        assert warnings == []

    def test_default_limits_generate_docker_config(self):
        """Test that DEFAULT_LIMITS generates valid Docker config."""
        docker_kwargs = ContainerResourceConfig.from_limits(DEFAULT_LIMITS)

        assert "nano_cpus" in docker_kwargs
        assert "mem_limit" in docker_kwargs
        assert "memswap_limit" in docker_kwargs
        assert "network_mode" in docker_kwargs
        assert "pids_limit" in docker_kwargs
