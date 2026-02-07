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

# Minimal set of capabilities needed for benchmark execution.
# Intentionally excludes DAC_OVERRIDE (root-like file access), FOWNER (bypass
# ownership checks), and NET_BIND_SERVICE (useless when network is disabled).
MINIMAL_CAPABILITIES = [
    "CHOWN",  # Change file ownership (needed for setup)
    "SETGID",  # Set group ID (needed for process setup)
    "SETUID",  # Set user ID (needed for process setup)
    "KILL",  # Send signals to processes (needed for test runner)
]


@dataclass
class SeccompProfile:
    """Seccomp (Secure Computing) profile for syscall filtering.

    Supports two modes:
    - **Allowlist (recommended)**: ``default_action="SCMP_ACT_ERRNO"`` with
      ``allowed_syscalls`` listing the only permitted syscalls.
    - **Blocklist (legacy)**: ``default_action="SCMP_ACT_ALLOW"`` with
      ``blocked_syscalls`` listing syscalls to deny.

    Attributes:
        default_action: Default action for syscalls not in any rule.
            SCMP_ACT_ERRNO blocks with EPERM, SCMP_ACT_ALLOW permits.
        blocked_syscalls: Syscalls to explicitly block (blocklist mode).
        allowed_syscalls: Syscalls to explicitly allow (allowlist mode).
        architecture: Target architecture for the profile.
    """

    default_action: str = "SCMP_ACT_ERRNO"
    blocked_syscalls: list[str] = field(default_factory=list)
    allowed_syscalls: list[str] = field(default_factory=list)
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

        # Allowlist mode: default-deny with explicit allow rules
        if self.allowed_syscalls:
            profile["syscalls"].append(
                {
                    "names": list(self.allowed_syscalls),
                    "action": "SCMP_ACT_ALLOW",
                }
            )
            return profile

        if self.default_action == "SCMP_ACT_ERRNO" and not self.blocked_syscalls:
            # Default-deny with no allowlist — return empty profile so Docker
            # applies its own default seccomp.
            return profile

        # Blocklist mode: default-allow with explicit deny rules
        if self.blocked_syscalls:
            profile["syscalls"].append(
                {
                    "names": self.blocked_syscalls,
                    "action": "SCMP_ACT_ERRNO",
                    "errnoRet": 1,  # EPERM
                }
            )

        return profile


# Dangerous syscalls kept for reference and used by the blocklist in non-strict profiles.
DANGEROUS_SYSCALLS = [
    "mount",  # Mount filesystems
    "umount2",  # Unmount filesystems
    "pivot_root",  # Change root filesystem
    "reboot",  # Reboot the system
    "swapon",  # Enable swap
    "swapoff",  # Disable swap
    "kexec_load",  # Load new kernel
    "kexec_file_load",  # Load new kernel from file
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
    "open_by_handle_at",  # Container escape (Shocker exploit)
    "name_to_handle_at",  # Companion to open_by_handle_at
    "bpf",  # Load BPF programs into kernel
    "userfaultfd",  # Used in container escape exploits
    "io_uring_setup",  # io_uring — frequent kernel vuln source
    "io_uring_enter",
    "io_uring_register",
    "process_vm_readv",  # Read another process's memory
    "process_vm_writev",  # Write another process's memory
    "keyctl",  # Kernel keyring manipulation
    "request_key",  # Kernel key management
    "add_key",  # Add key to kernel keyring
    "move_mount",  # Mount manipulation (Linux 5.2+)
    "open_tree",  # Mount namespace manipulation
    "fsopen",  # New mount API
    "fsmount",
    "fsconfig",
    "clone3",  # Enhanced process creation with namespace flags
    "lookup_dcookie",  # Information leak
    "perf_event_open",  # Performance counters / side channels
    "kcmp",  # Compare kernel objects between processes
]

# Syscalls explicitly allowed in strict mode (default-deny allowlist).
# Covers what Python, shell, C/C++ compilation, and test runners need.
STRICT_ALLOWED_SYSCALLS = [
    # File I/O
    "read",
    "write",
    "open",
    "openat",
    "close",
    "lseek",
    "pread64",
    "pwrite64",
    "readv",
    "writev",
    "stat",
    "fstat",
    "lstat",
    "newfstatat",
    "statx",
    "access",
    "faccessat",
    "faccessat2",
    "dup",
    "dup2",
    "dup3",
    "pipe",
    "pipe2",
    "rename",
    "renameat",
    "renameat2",
    "unlink",
    "unlinkat",
    "rmdir",
    "mkdir",
    "mkdirat",
    "link",
    "linkat",
    "symlink",
    "symlinkat",
    "readlink",
    "readlinkat",
    "chmod",
    "fchmod",
    "fchmodat",
    "chown",
    "fchown",
    "fchownat",
    "truncate",
    "ftruncate",
    "fallocate",
    "getcwd",
    "chdir",
    "fchdir",
    "getdents",
    "getdents64",
    "umask",
    "statfs",
    "fstatfs",
    "copy_file_range",
    "sendfile",
    "splice",
    "tee",
    "fadvise64",
    # Memory
    "brk",
    "mmap",
    "munmap",
    "mprotect",
    "mremap",
    "msync",
    "madvise",
    "mlock",
    "mlock2",
    "munlock",
    "mincore",
    "membarrier",
    # Process
    "clone",
    "fork",
    "vfork",
    "execve",
    "execveat",
    "exit",
    "exit_group",
    "wait4",
    "waitid",
    "getpid",
    "getppid",
    "gettid",
    "getuid",
    "geteuid",
    "getgid",
    "getegid",
    "getgroups",
    "setuid",
    "setgid",
    "setgroups",
    "setreuid",
    "setregid",
    "setresuid",
    "setresgid",
    "getresuid",
    "getresgid",
    "setsid",
    "getsid",
    "getpgid",
    "setpgid",
    "getpgrp",
    "prctl",
    "arch_prctl",
    "set_tid_address",
    "set_robust_list",
    "get_robust_list",
    "sched_yield",
    "sched_getaffinity",
    "sched_setaffinity",
    "sched_getscheduler",
    "sched_setscheduler",
    "sched_getparam",
    "sched_setparam",
    "getpriority",
    "setpriority",
    "capget",
    "capset",
    # Signals
    "rt_sigaction",
    "rt_sigprocmask",
    "rt_sigreturn",
    "rt_sigpending",
    "rt_sigsuspend",
    "rt_sigtimedwait",
    "rt_sigqueueinfo",
    "rt_tgsigqueueinfo",
    "kill",
    "tgkill",
    "tkill",
    "sigaltstack",
    # I/O multiplexing
    "ioctl",
    "fcntl",
    "poll",
    "ppoll",
    "select",
    "pselect6",
    "epoll_create",
    "epoll_create1",
    "epoll_ctl",
    "epoll_wait",
    "epoll_pwait",
    "eventfd",
    "eventfd2",
    # Time
    "clock_gettime",
    "clock_getres",
    "gettimeofday",
    "time",
    "nanosleep",
    "clock_nanosleep",
    "timer_create",
    "timer_settime",
    "timer_gettime",
    "timer_delete",
    "timer_getoverrun",
    "timerfd_create",
    "timerfd_settime",
    "timerfd_gettime",
    # Networking (local sockets/pipes still needed even with network disabled)
    "socket",
    "bind",
    "listen",
    "accept",
    "accept4",
    "connect",
    "sendto",
    "recvfrom",
    "sendmsg",
    "recvmsg",
    "shutdown",
    "getsockname",
    "getpeername",
    "socketpair",
    "setsockopt",
    "getsockopt",
    "sendmmsg",
    "recvmmsg",
    # Misc
    "futex",
    "getrandom",
    "memfd_create",
    "inotify_init",
    "inotify_init1",
    "inotify_add_watch",
    "inotify_rm_watch",
    "signalfd",
    "signalfd4",
    "sysinfo",
    "uname",
    "getrlimit",
    "setrlimit",
    "prlimit64",
    "getrusage",
    "rseq",
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
        userns_mode: Docker user namespace remapping mode (e.g., "host").
        device_read_bps: I/O rate limit for device reads in bytes per second.
        device_write_bps: I/O rate limit for device writes in bytes per second.
        network_allowlist: Allowed hosts when using allowlist network mode.
            Parsed from config for future enforcement; not yet applied at runtime.
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
    userns_mode: str | None = None
    device_read_bps: int | None = None
    device_write_bps: int | None = None
    network_allowlist: list[str] = field(default_factory=list)

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

        # User namespace remapping
        if self.userns_mode:
            kwargs["userns_mode"] = self.userns_mode

        # I/O rate limits — uses /dev/sda as the default block device path.
        # Docker silently ignores limits if the device doesn't exist, so this
        # acts as a best-effort control for standard environments.
        if self.device_read_bps is not None:
            kwargs["device_read_bps"] = [{"Path": "/dev/sda", "Rate": self.device_read_bps}]
        if self.device_write_bps is not None:
            kwargs["device_write_bps"] = [{"Path": "/dev/sda", "Rate": self.device_write_bps}]

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
                default_action="SCMP_ACT_ERRNO",
                allowed_syscalls=STRICT_ALLOWED_SYSCALLS,
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
            # Do not use userns_mode="host" — that shares host UIDs with the
            # container, meaning UID 0 inside == UID 0 on the host.
            userns_mode=None,
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
    if "userns_mode" in config_dict:
        profile.userns_mode = config_dict["userns_mode"]
    if "device_read_bps" in config_dict:
        profile.device_read_bps = config_dict["device_read_bps"]
    if "device_write_bps" in config_dict:
        profile.device_write_bps = config_dict["device_write_bps"]
    if "network_allowlist" in config_dict:
        profile.network_allowlist = config_dict["network_allowlist"]
        if config_dict["network_allowlist"]:
            logger.warning(
                "network_allowlist is configured but not yet enforced at runtime. "
                "Containers will have unrestricted network access unless "
                "network_disabled is set to true."
            )

    return profile


def validate_sandbox(
    container_attrs: dict[str, Any], profile: SandboxProfile
) -> tuple[bool, list[str]]:
    """Validate that a container's host config matches the expected sandbox profile.

    Inspects container attributes (from ``container.attrs["HostConfig"]``) and
    verifies that capability, filesystem, and network settings match the profile.
    This is advisory only — mismatches are logged as warnings but do not abort.

    Args:
        container_attrs: The ``HostConfig`` dictionary from ``container.attrs``.
        profile: The expected SandboxProfile.

    Returns:
        Tuple of ``(valid, mismatches)`` where *valid* is True if all checked
        settings match, and *mismatches* is a list of human-readable descriptions
        for any differences found.
    """
    mismatches: list[str] = []

    # Check cap_drop
    actual_cap_drop = container_attrs.get("CapDrop") or []
    if profile.cap_drop and sorted(actual_cap_drop) != sorted(profile.cap_drop):
        mismatches.append(f"cap_drop mismatch: expected {profile.cap_drop}, got {actual_cap_drop}")

    # Check cap_add
    actual_cap_add = container_attrs.get("CapAdd") or []
    if profile.cap_add and sorted(actual_cap_add) != sorted(profile.cap_add):
        mismatches.append(f"cap_add mismatch: expected {profile.cap_add}, got {actual_cap_add}")

    # Check read-only rootfs
    actual_read_only = container_attrs.get("ReadonlyRootfs", False)
    if profile.read_only_rootfs and not actual_read_only:
        mismatches.append("read_only_rootfs expected True but container has False")

    # Check network mode
    actual_network_mode = container_attrs.get("NetworkMode", "")
    if profile.network_disabled and actual_network_mode != "none":
        mismatches.append(f"network_mode mismatch: expected 'none', got '{actual_network_mode}'")

    # Check security_opt for no-new-privileges
    actual_security_opt = container_attrs.get("SecurityOpt") or []
    if profile.no_new_privileges:
        if "no-new-privileges:true" not in actual_security_opt:
            # Docker may also store it as "no-new-privileges"
            if "no-new-privileges" not in actual_security_opt:
                mismatches.append("no_new_privileges expected but not found in SecurityOpt")

    # Check userns_mode
    actual_userns = container_attrs.get("UsernsMode", "")
    if profile.userns_mode and actual_userns != profile.userns_mode:
        mismatches.append(
            f"userns_mode mismatch: expected '{profile.userns_mode}', got '{actual_userns}'"
        )

    valid = len(mismatches) == 0
    if not valid:
        if profile.security_level == SecurityLevel.STRICT:
            detail = "; ".join(mismatches)
            raise ValueError(f"Sandbox validation failed in strict mode: {detail}")
        for mismatch in mismatches:
            logger.warning("Sandbox validation: %s", mismatch)

    return valid, mismatches
