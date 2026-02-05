"""Resource limit configuration for Docker containers and evaluation runs.

Provides dataclasses and utilities for configuring CPU, memory, disk, network,
and timeout limits for Docker containers used in benchmark evaluations. Includes
monitoring capabilities to check container resource usage and detect violations.

Key capabilities:
- Configure CPU, memory, disk, and PID limits for Docker containers
- Set per-task and per-evaluation timeouts
- Convert limits to Docker container creation kwargs
- Monitor container resource usage via docker stats
- Detect and report resource limit violations
- Parse resource limits from YAML config dictionaries
"""

import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Valid Docker network modes
VALID_NETWORK_MODES = ("bridge", "host", "none")


@dataclass
class ResourceLimits:
    """Resource limits for a Docker container or evaluation run.

    Attributes:
        cpu_count: Number of CPUs to allocate (e.g., 2.0 for 2 CPUs). None means no limit.
        memory_mb: Memory limit in megabytes (e.g., 4096 for 4GB). None means no limit.
        memory_swap_mb: Total memory + swap limit in megabytes. None means no limit.
            Must be >= memory_mb if both are set. Set to same value as memory_mb to
            disable swap.
        disk_mb: Disk space limit in megabytes. None means no limit. Note: Docker does
            not natively enforce disk limits per container without storage drivers;
            this is tracked for monitoring/reporting purposes.
        network_mode: Docker network mode (bridge, host, none). None uses Docker default.
        pids_limit: Maximum number of processes in the container. None means no limit.
        task_timeout_seconds: Timeout in seconds for a single task. Defaults to 600 (10 min).
        total_timeout_seconds: Timeout in seconds for the entire evaluation run.
            None means no total timeout.
    """

    cpu_count: float | None = None
    memory_mb: int | None = None
    memory_swap_mb: int | None = None
    disk_mb: int | None = None
    network_mode: str | None = None
    pids_limit: int | None = None
    task_timeout_seconds: int = 600
    total_timeout_seconds: int | None = None


@dataclass
class ResourceUsage:
    """Current resource usage snapshot for a container.

    Attributes:
        cpu_percent: CPU usage as a percentage (e.g., 150.0 means 1.5 CPUs).
        memory_mb: Current memory usage in megabytes.
        disk_mb: Current disk usage in megabytes.
        pids: Current number of processes.
    """

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    pids: int = 0


# Sensible defaults for benchmark evaluation containers
DEFAULT_LIMITS = ResourceLimits(
    cpu_count=2.0,
    memory_mb=4096,
    memory_swap_mb=8192,
    disk_mb=10240,
    network_mode="bridge",
    pids_limit=256,
    task_timeout_seconds=600,
    total_timeout_seconds=None,
)


class ContainerResourceConfig:
    """Converts ResourceLimits into Docker container creation kwargs.

    Provides a bridge between the ResourceLimits dataclass and the keyword
    arguments expected by docker-py's ``containers.run()`` or
    ``containers.create()`` methods.
    """

    def __init__(self, limits: ResourceLimits) -> None:
        """Initialize with resource limits.

        Args:
            limits: ResourceLimits to convert to Docker configuration.
        """
        self.limits = limits

    @staticmethod
    def from_limits(limits: ResourceLimits) -> dict:
        """Convert ResourceLimits to Docker container creation kwargs.

        Translates each supported resource limit field into the corresponding
        Docker API parameter. Fields set to None are omitted from the output.

        Args:
            limits: ResourceLimits instance to convert.

        Returns:
            Dictionary of keyword arguments suitable for passing to
            ``docker.containers.run()`` or ``docker.containers.create()``.
        """
        config: dict = {}

        if limits.cpu_count is not None:
            # nano_cpus expects integer nanoseconds (1 CPU = 1e9 nano CPUs)
            config["nano_cpus"] = int(limits.cpu_count * 1e9)

        if limits.memory_mb is not None:
            # mem_limit accepts bytes or string like "4g"
            config["mem_limit"] = f"{limits.memory_mb}m"

        if limits.memory_swap_mb is not None:
            # memswap_limit is total memory + swap
            config["memswap_limit"] = f"{limits.memory_swap_mb}m"

        if limits.network_mode is not None:
            config["network_mode"] = limits.network_mode

        if limits.pids_limit is not None:
            config["pids_limit"] = limits.pids_limit

        return config

    def validate(self) -> list[str]:
        """Validate the resource limits and return any warnings.

        Checks for common misconfigurations such as swap being less than
        memory, excessively low limits, or invalid network modes.

        Returns:
            List of warning messages. Empty list means no issues found.
        """
        warnings: list[str] = []

        limits = self.limits

        # Validate memory_swap_mb >= memory_mb
        if (
            limits.memory_mb is not None
            and limits.memory_swap_mb is not None
            and limits.memory_swap_mb < limits.memory_mb
        ):
            warnings.append(
                f"memory_swap_mb ({limits.memory_swap_mb}) is less than "
                f"memory_mb ({limits.memory_mb}). Swap limit must be >= memory limit."
            )

        # Validate network_mode
        if limits.network_mode is not None and limits.network_mode not in VALID_NETWORK_MODES:
            warnings.append(
                f"network_mode '{limits.network_mode}' is not a standard Docker network mode. "
                f"Valid modes: {', '.join(VALID_NETWORK_MODES)}"
            )

        # Warn about very low memory
        if limits.memory_mb is not None and limits.memory_mb < 256:
            warnings.append(
                f"memory_mb ({limits.memory_mb}) is very low. "
                "Most benchmark tasks require at least 256MB."
            )

        # Warn about very low CPU
        if limits.cpu_count is not None and limits.cpu_count < 0.5:
            warnings.append(
                f"cpu_count ({limits.cpu_count}) is very low. "
                "Most benchmark tasks require at least 0.5 CPUs."
            )

        # Warn about very low task timeout
        if limits.task_timeout_seconds < 30:
            warnings.append(
                f"task_timeout_seconds ({limits.task_timeout_seconds}) is very low. "
                "Most benchmark tasks require at least 30 seconds."
            )

        # Warn about very low PID limit
        if limits.pids_limit is not None and limits.pids_limit < 16:
            warnings.append(
                f"pids_limit ({limits.pids_limit}) is very low. "
                "Most containers need at least 16 PIDs to function."
            )

        # Validate positive values
        if limits.cpu_count is not None and limits.cpu_count <= 0:
            warnings.append(f"cpu_count ({limits.cpu_count}) must be positive.")

        if limits.memory_mb is not None and limits.memory_mb <= 0:
            warnings.append(f"memory_mb ({limits.memory_mb}) must be positive.")

        if limits.disk_mb is not None and limits.disk_mb <= 0:
            warnings.append(f"disk_mb ({limits.disk_mb}) must be positive.")

        if limits.pids_limit is not None and limits.pids_limit <= 0:
            warnings.append(f"pids_limit ({limits.pids_limit}) must be positive.")

        if limits.task_timeout_seconds <= 0:
            warnings.append(
                f"task_timeout_seconds ({limits.task_timeout_seconds}) must be positive."
            )

        if limits.total_timeout_seconds is not None and limits.total_timeout_seconds <= 0:
            warnings.append(
                f"total_timeout_seconds ({limits.total_timeout_seconds}) must be positive."
            )

        return warnings


class ResourceMonitor:
    """Monitors Docker container resource usage and checks against limits.

    Uses ``docker stats`` to query current container resource consumption
    and compares it against configured limits to detect violations.
    """

    def __init__(self, limits: ResourceLimits) -> None:
        """Initialize the resource monitor.

        Args:
            limits: ResourceLimits to check usage against.
        """
        self.limits = limits

    def check_container_resources(self, container_id: str) -> ResourceUsage:
        """Get current resource usage for a Docker container.

        Queries ``docker stats`` for a single snapshot of the container's
        CPU, memory, and PID usage.

        Args:
            container_id: Docker container ID or name.

        Returns:
            ResourceUsage with current consumption metrics.

        Raises:
            RuntimeError: If docker stats command fails.
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    container_id,
                    "--no-stream",
                    "--format",
                    '{"cpu":"{{.CPUPerc}}","mem":"{{.MemUsage}}","pids":"{{.PIDs}}"}',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"docker stats failed for container {container_id}: {result.stderr}"
                )

            stats_str = result.stdout.strip()
            if not stats_str:
                raise RuntimeError(f"Empty output from docker stats for container {container_id}")

            stats = json.loads(stats_str)

            # Parse CPU percentage (e.g., "150.25%" -> 150.25)
            cpu_str = stats.get("cpu", "0%").rstrip("%")
            cpu_percent = float(cpu_str) if cpu_str else 0.0

            # Parse memory usage (e.g., "512MiB / 4GiB" -> 512.0)
            memory_mb = _parse_memory_usage(stats.get("mem", "0B / 0B"))

            # Parse PIDs
            pids_str = stats.get("pids", "0")
            pids = int(pids_str) if pids_str and pids_str != "--" else 0

            return ResourceUsage(
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                disk_mb=0.0,  # Docker stats does not report disk usage
                pids=pids,
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"docker stats timed out for container {container_id}")
            raise RuntimeError(f"docker stats timed out for container {container_id}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse docker stats output: {e}")
            raise RuntimeError(f"Failed to parse docker stats output: {e}")

    def is_within_limits(self, usage: ResourceUsage) -> bool:
        """Check whether resource usage is within configured limits.

        Args:
            usage: Current resource usage to check.

        Returns:
            True if all usage metrics are within limits, False otherwise.
        """
        return len(self.get_violations(usage)) == 0

    def get_violations(self, usage: ResourceUsage) -> list[str]:
        """Get list of resource limit violations.

        Compares each usage metric against the corresponding limit and
        returns human-readable descriptions of any violations found.

        Args:
            usage: Current resource usage to check.

        Returns:
            List of violation description strings. Empty if all within limits.
        """
        violations: list[str] = []

        # Check CPU: convert cpu_count limit to percentage for comparison
        # e.g., 2.0 CPUs = 200% max
        if self.limits.cpu_count is not None:
            max_cpu_percent = self.limits.cpu_count * 100
            if usage.cpu_percent > max_cpu_percent:
                violations.append(
                    f"CPU usage ({usage.cpu_percent:.1f}%) exceeds limit "
                    f"({max_cpu_percent:.1f}% = {self.limits.cpu_count} CPUs)"
                )

        # Check memory
        if self.limits.memory_mb is not None:
            if usage.memory_mb > self.limits.memory_mb:
                violations.append(
                    f"Memory usage ({usage.memory_mb:.1f}MB) exceeds limit "
                    f"({self.limits.memory_mb}MB)"
                )

        # Check disk
        if self.limits.disk_mb is not None:
            if usage.disk_mb > self.limits.disk_mb:
                violations.append(
                    f"Disk usage ({usage.disk_mb:.1f}MB) exceeds limit ({self.limits.disk_mb}MB)"
                )

        # Check PIDs
        if self.limits.pids_limit is not None:
            if usage.pids > self.limits.pids_limit:
                violations.append(
                    f"PID count ({usage.pids}) exceeds limit ({self.limits.pids_limit})"
                )

        return violations


def _parse_memory_usage(mem_str: str) -> float:
    """Parse Docker memory usage string to megabytes.

    Docker stats reports memory usage in formats like:
    - "512MiB / 4GiB"
    - "1.5GiB / 8GiB"
    - "256KiB / 4GiB"

    This function extracts the current usage (before the "/") and
    converts it to megabytes.

    Args:
        mem_str: Memory usage string from docker stats.

    Returns:
        Current memory usage in megabytes.
    """
    # Extract the usage part (before " / ")
    parts = mem_str.split("/")
    if not parts:
        return 0.0

    usage_str = parts[0].strip()

    # Parse the value and unit
    value = 0.0
    unit = ""

    # Find where the number ends and the unit begins
    i = 0
    while i < len(usage_str) and (usage_str[i].isdigit() or usage_str[i] == "."):
        i += 1

    try:
        value = float(usage_str[:i]) if i > 0 else 0.0
    except ValueError:
        return 0.0

    unit = usage_str[i:].strip().lower()

    # Convert to MB
    if unit in ("gib", "gb"):
        return value * 1024
    elif unit in ("mib", "mb"):
        return value
    elif unit in ("kib", "kb"):
        return value / 1024
    elif unit in ("b",):
        return value / (1024 * 1024)
    else:
        # Default: assume MB
        return value


def parse_resource_limits(config: dict) -> ResourceLimits:
    """Parse resource limits from a YAML configuration dictionary.

    Accepts a dictionary (typically loaded from a YAML config file) and
    creates a ResourceLimits instance. Unknown keys are ignored with a
    warning. Missing keys use the dataclass defaults.

    Expected YAML structure::

        resource_limits:
          cpu_count: 2.0
          memory_mb: 4096
          memory_swap_mb: 8192
          disk_mb: 10240
          network_mode: bridge
          pids_limit: 256
          task_timeout_seconds: 600
          total_timeout_seconds: 3600

    Args:
        config: Dictionary of resource limit configuration values.

    Returns:
        ResourceLimits instance with values from the config dict.
    """
    known_fields = {
        "cpu_count",
        "memory_mb",
        "memory_swap_mb",
        "disk_mb",
        "network_mode",
        "pids_limit",
        "task_timeout_seconds",
        "total_timeout_seconds",
    }

    # Warn about unknown keys
    unknown_keys = set(config.keys()) - known_fields
    for key in sorted(unknown_keys):
        logger.warning(f"Unknown resource limit key '{key}' will be ignored.")

    kwargs: dict = {}

    # Parse each field with appropriate type conversion
    if "cpu_count" in config:
        kwargs["cpu_count"] = float(config["cpu_count"])

    if "memory_mb" in config:
        kwargs["memory_mb"] = int(config["memory_mb"])

    if "memory_swap_mb" in config:
        kwargs["memory_swap_mb"] = int(config["memory_swap_mb"])

    if "disk_mb" in config:
        kwargs["disk_mb"] = int(config["disk_mb"])

    if "network_mode" in config:
        kwargs["network_mode"] = str(config["network_mode"])

    if "pids_limit" in config:
        kwargs["pids_limit"] = int(config["pids_limit"])

    if "task_timeout_seconds" in config:
        kwargs["task_timeout_seconds"] = int(config["task_timeout_seconds"])

    if "total_timeout_seconds" in config:
        kwargs["total_timeout_seconds"] = int(config["total_timeout_seconds"])

    return ResourceLimits(**kwargs)
