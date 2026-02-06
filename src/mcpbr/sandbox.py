"""Sandbox execution environment for secure code execution.

Provides Docker-based sandboxing with configurable security profiles,
resource limits, network isolation, and filesystem restrictions.
Used to safely execute untrusted code from benchmark responses.

Security layers:
- Linux capability restrictions (drop dangerous capabilities)
- Seccomp syscall filtering profiles
- Network isolation modes
- Read-only filesystem with tmpfs scratch space
- Resource limits (CPU, memory, PIDs) via ContainerResourceConfig
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .resource_limits import ContainerResourceConfig, ResourceLimits

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Predefined security levels for sandbox profiles.

    Each level provides progressively stricter isolation:
    - PERMISSIVE: Minimal restrictions, suitable for trusted code
    - STANDARD: Default restrictions, suitable for most benchmarks
    - STRICT: Maximum restrictions, suitable for untrusted code
    """

    PERMISSIVE = "permissive"
    STANDARD = "standard"
    STRICT = "strict"


# Linux capabilities that are safe to drop for benchmark evaluation.
# These are dangerous capabilities that untrusted code should not have.
DANGEROUS_CAPABILITIES = [
    "SYS_ADMIN",  # Mount, cgroups, namespace manipulation
    "NET_ADMIN",  # Network configuration, firewall rules
    "SYS_PTRACE",  # Process tracing (debugging other processes)
    "SYS_RAWIO",  # Raw I/O port access
    "SYS_MODULE",  # Load/unload kernel modules
    "NET_RAW",  # Raw sockets (packet sniffing)
    "MKNOD",  # Create device nodes
    "SYS_BOOT",  # Reboot the system
    "SYS_TIME",  # Modify system clock
    "LINUX_IMMUTABLE",  # Modify immutable file attributes
    "MAC_ADMIN",  # MAC configuration
    "MAC_OVERRIDE",  # Override MAC policies
    "AUDIT_CONTROL",  # Audit configuration
    "AUDIT_WRITE",  # Write audit log
    "SETFCAP",  # Set file capabilities
]

# Minimal set of capabilities needed for benchmark execution
MINIMAL_CAPABILITIES = [
    "CHOWN",  # Change file ownership (needed for setup)
    "DAC_OVERRIDE",  # Bypass file permission checks (needed for test execution)
    "FOWNER",  # Bypass permission checks on file owner operations
    "SETGID",  # Set group ID
    "SETUID",  # Set user ID
    "KILL",  # Send signals to processes
    "NET_BIND_SERVICE",  # Bind to privileged ports (needed for some MCP servers)
]


@dataclass
class SeccompProfile:
    """Seccomp (Secure Computing) profile for syscall filtering.

    Attributes:
        default_action: Default action for syscalls not in the allow list.
            SCMP_ACT_ERRNO blocks with EPERM, SCMP_ACT_ALLOW permits.
        blocked_syscalls: Syscalls to explicitly block (when default is allow).
        architecture: Target architecture for the profile.
    """

    default_action: str = "SCMP_ACT_ERRNO"
    blocked_syscalls: list[str] = field(default_factory=list)
    architecture: str = "SCMP_ARCH_X86_64"

    def to_docker_format(self) -> dict[str, Any]:
        """Convert to Docker-compatible seccomp profile JSON.

        Returns:
            Dictionary suitable for passing as Docker seccomp profile.
        """
        profile: dict[str, Any] = {
            "defaultAction": self.default_action,
            "architectures": [self.architecture, "SCMP_ARCH_X86", "SCMP_ARCH_X32"],
            "syscalls": [],
        }

        if self.default_action == "SCMP_ACT_ERRNO" and not self.blocked_syscalls:
            # If blocking by default, we need an allow list.
            # Use Docker's default seccomp profile as base (it allows ~300 syscalls).
            # We don't override the default — Docker applies its own seccomp by default.
            return profile

        if self.blocked_syscalls:
            profile["syscalls"].append(
                {
                    "names": self.blocked_syscalls,
                    "action": "SCMP_ACT_ERRNO",
                    "errnoRet": 1,  # EPERM
                }
            )

        return profile


# Dangerous syscalls to block in strict mode
DANGEROUS_SYSCALLS = [
    "mount",  # Mount filesystems
    "umount2",  # Unmount filesystems
    "pivot_root",  # Change root filesystem
    "reboot",  # Reboot the system
    "swapon",  # Enable swap
    "swapoff",  # Disable swap
    "kexec_load",  # Load new kernel
    "init_module",  # Load kernel module
    "finit_module",  # Load kernel module from fd
    "delete_module",  # Unload kernel module
    "acct",  # Process accounting
    "settimeofday",  # Set system time
    "clock_settime",  # Set clock time
    "adjtimex",  # Tune kernel clock
    "ptrace",  # Process tracing
    "personality",  # Change process execution domain
    "unshare",  # Create new namespaces
    "setns",  # Join existing namespace
]


@dataclass
class SandboxProfile:
    """Complete sandbox security profile.

    Combines capability restrictions, seccomp filtering, network isolation,
    and filesystem restrictions into a single configurable profile.

    Attributes:
        name: Human-readable profile name.
        security_level: Predefined security level (permissive/standard/strict).
        cap_drop: Linux capabilities to drop from the container.
        cap_add: Linux capabilities to explicitly add.
        seccomp: Seccomp syscall filtering profile.
        read_only_rootfs: Mount root filesystem as read-only.
        tmpfs_mounts: tmpfs mounts for writable scratch space (path → size).
        no_new_privileges: Prevent privilege escalation.
        resource_limits: Resource limits for the container.
        network_disabled: Completely disable networking.
    """

    name: str = "standard"
    security_level: SecurityLevel = SecurityLevel.STANDARD
    cap_drop: list[str] = field(default_factory=list)
    cap_add: list[str] = field(default_factory=list)
    seccomp: SeccompProfile | None = None
    read_only_rootfs: bool = False
    tmpfs_mounts: dict[str, str] = field(default_factory=dict)
    no_new_privileges: bool = True
    resource_limits: ResourceLimits | None = None
    network_disabled: bool = False

    def to_docker_kwargs(self) -> dict[str, Any]:
        """Convert sandbox profile to Docker container creation kwargs.

        Returns:
            Dictionary of keyword arguments for docker.containers.run().
        """
        kwargs: dict[str, Any] = {}

        # Capability restrictions
        if self.cap_drop:
            kwargs["cap_drop"] = self.cap_drop
        if self.cap_add:
            kwargs["cap_add"] = self.cap_add

        # Security options
        security_opts: list[str] = []
        if self.no_new_privileges:
            security_opts.append("no-new-privileges:true")
        if self.seccomp:
            profile_json = json.dumps(self.seccomp.to_docker_format())
            security_opts.append(f"seccomp={profile_json}")
        if security_opts:
            kwargs["security_opt"] = security_opts

        # Read-only root filesystem
        if self.read_only_rootfs:
            kwargs["read_only"] = True

        # tmpfs mounts for writable scratch space
        if self.tmpfs_mounts:
            kwargs["tmpfs"] = self.tmpfs_mounts

        # Network isolation
        if self.network_disabled:
            kwargs["network_mode"] = "none"

        # Resource limits
        if self.resource_limits:
            resource_kwargs = ContainerResourceConfig.from_limits(self.resource_limits)
            # Don't override network_mode if we set it above
            if self.network_disabled and "network_mode" in resource_kwargs:
                del resource_kwargs["network_mode"]
            kwargs.update(resource_kwargs)

        return kwargs


def create_profile(level: SecurityLevel | str) -> SandboxProfile:
    """Create a sandbox profile for the given security level.

    Args:
        level: Security level (permissive, standard, or strict).

    Returns:
        SandboxProfile configured for the specified level.

    Raises:
        ValueError: If the security level is not recognized.
    """
    if isinstance(level, str):
        try:
            level = SecurityLevel(level)
        except ValueError:
            raise ValueError(
                f"Unknown security level: {level}. "
                f"Valid levels: {', '.join(s.value for s in SecurityLevel)}"
            )

    if level == SecurityLevel.PERMISSIVE:
        return SandboxProfile(
            name="permissive",
            security_level=SecurityLevel.PERMISSIVE,
            cap_drop=[],
            cap_add=[],
            seccomp=None,
            read_only_rootfs=False,
            no_new_privileges=False,
            resource_limits=None,
            network_disabled=False,
        )

    elif level == SecurityLevel.STANDARD:
        return SandboxProfile(
            name="standard",
            security_level=SecurityLevel.STANDARD,
            cap_drop=DANGEROUS_CAPABILITIES,
            cap_add=[],
            seccomp=None,  # Use Docker's built-in default seccomp
            read_only_rootfs=False,
            no_new_privileges=True,
            resource_limits=ResourceLimits(
                cpu_count=2.0,
                memory_mb=4096,
                memory_swap_mb=8192,
                pids_limit=256,
            ),
            network_disabled=False,
        )

    elif level == SecurityLevel.STRICT:
        return SandboxProfile(
            name="strict",
            security_level=SecurityLevel.STRICT,
            cap_drop=["ALL"],
            cap_add=MINIMAL_CAPABILITIES,
            seccomp=SeccompProfile(
                default_action="SCMP_ACT_ALLOW",
                blocked_syscalls=DANGEROUS_SYSCALLS,
            ),
            read_only_rootfs=True,
            tmpfs_mounts={
                "/tmp": "size=512m",
                "/var/tmp": "size=256m",
                "/run": "size=64m",
            },
            no_new_privileges=True,
            resource_limits=ResourceLimits(
                cpu_count=1.0,
                memory_mb=2048,
                memory_swap_mb=2048,  # No swap
                pids_limit=128,
                network_mode="none",
            ),
            network_disabled=True,
        )

    # Should not reach here due to enum exhaustiveness
    raise ValueError(f"Unknown security level: {level}")


def parse_sandbox_config(config_dict: dict[str, Any]) -> SandboxProfile:
    """Parse sandbox configuration from a YAML dictionary.

    Supports both preset levels and custom configuration:

    Preset::

        sandbox:
          level: standard

    Custom::

        sandbox:
          level: standard
          cap_drop: [SYS_ADMIN, NET_ADMIN]
          read_only_rootfs: true
          network_disabled: false

    Args:
        config_dict: Dictionary from YAML configuration.

    Returns:
        SandboxProfile configured from the dictionary.
    """
    level_str = config_dict.get("level", "standard")
    profile = create_profile(level_str)

    # Override individual settings if provided
    if "cap_drop" in config_dict:
        profile.cap_drop = config_dict["cap_drop"]
    if "cap_add" in config_dict:
        profile.cap_add = config_dict["cap_add"]
    if "read_only_rootfs" in config_dict:
        profile.read_only_rootfs = config_dict["read_only_rootfs"]
    if "no_new_privileges" in config_dict:
        profile.no_new_privileges = config_dict["no_new_privileges"]
    if "network_disabled" in config_dict:
        profile.network_disabled = config_dict["network_disabled"]
    if "tmpfs_mounts" in config_dict:
        profile.tmpfs_mounts = config_dict["tmpfs_mounts"]

    return profile
