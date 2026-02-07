"""Tests for sandbox execution environment."""

import json

import pytest

from mcpbr.sandbox import (
    DANGEROUS_CAPABILITIES,
    DANGEROUS_SYSCALLS,
    MINIMAL_CAPABILITIES,
    SandboxProfile,
    SeccompProfile,
    SecurityLevel,
    create_profile,
    parse_sandbox_config,
    validate_sandbox,
)


class TestSecurityLevel:
    """Tests for SecurityLevel enum."""

    def test_permissive_level(self) -> None:
        assert SecurityLevel.PERMISSIVE.value == "permissive"

    def test_standard_level(self) -> None:
        assert SecurityLevel.STANDARD.value == "standard"

    def test_strict_level(self) -> None:
        assert SecurityLevel.STRICT.value == "strict"

    def test_from_string(self) -> None:
        assert SecurityLevel("standard") == SecurityLevel.STANDARD


class TestSeccompProfile:
    """Tests for SeccompProfile."""

    def test_default_profile(self) -> None:
        profile = SeccompProfile()
        result = profile.to_docker_format()
        assert result["defaultAction"] == "SCMP_ACT_ERRNO"
        assert "SCMP_ARCH_X86_64" in result["architectures"]

    def test_blocked_syscalls(self) -> None:
        profile = SeccompProfile(
            default_action="SCMP_ACT_ALLOW",
            blocked_syscalls=["mount", "umount2"],
        )
        result = profile.to_docker_format()
        assert result["defaultAction"] == "SCMP_ACT_ALLOW"
        assert len(result["syscalls"]) == 1
        assert "mount" in result["syscalls"][0]["names"]
        assert "umount2" in result["syscalls"][0]["names"]
        assert result["syscalls"][0]["action"] == "SCMP_ACT_ERRNO"

    def test_no_blocked_syscalls_with_default_deny(self) -> None:
        profile = SeccompProfile(default_action="SCMP_ACT_ERRNO")
        result = profile.to_docker_format()
        assert result["syscalls"] == []


class TestSandboxProfile:
    """Tests for SandboxProfile."""

    def test_default_profile(self) -> None:
        profile = SandboxProfile()
        assert profile.name == "standard"
        assert profile.no_new_privileges is True

    def test_to_docker_kwargs_empty(self) -> None:
        profile = SandboxProfile(
            cap_drop=[],
            cap_add=[],
            seccomp=None,
            read_only_rootfs=False,
            no_new_privileges=False,
            network_disabled=False,
            resource_limits=None,
        )
        kwargs = profile.to_docker_kwargs()
        assert kwargs == {}

    def test_to_docker_kwargs_with_capabilities(self) -> None:
        profile = SandboxProfile(
            cap_drop=["SYS_ADMIN", "NET_ADMIN"],
            cap_add=["CHOWN"],
            no_new_privileges=False,
        )
        kwargs = profile.to_docker_kwargs()
        assert kwargs["cap_drop"] == ["SYS_ADMIN", "NET_ADMIN"]
        assert kwargs["cap_add"] == ["CHOWN"]

    def test_to_docker_kwargs_with_security_opts(self) -> None:
        profile = SandboxProfile(no_new_privileges=True)
        kwargs = profile.to_docker_kwargs()
        assert "security_opt" in kwargs
        assert "no-new-privileges:true" in kwargs["security_opt"]

    def test_to_docker_kwargs_with_seccomp(self) -> None:
        seccomp = SeccompProfile(
            default_action="SCMP_ACT_ALLOW",
            blocked_syscalls=["mount"],
        )
        profile = SandboxProfile(seccomp=seccomp, no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        security_opts = kwargs.get("security_opt", [])
        seccomp_opt = [s for s in security_opts if s.startswith("seccomp=")]
        assert len(seccomp_opt) == 1
        seccomp_json = json.loads(seccomp_opt[0].removeprefix("seccomp="))
        assert seccomp_json["defaultAction"] == "SCMP_ACT_ALLOW"

    def test_to_docker_kwargs_with_read_only(self) -> None:
        profile = SandboxProfile(
            read_only_rootfs=True,
            tmpfs_mounts={"/tmp": "size=512m"},
            no_new_privileges=False,
        )
        kwargs = profile.to_docker_kwargs()
        assert kwargs["read_only"] is True
        assert kwargs["tmpfs"] == {"/tmp": "size=512m"}

    def test_to_docker_kwargs_with_network_disabled(self) -> None:
        profile = SandboxProfile(network_disabled=True, no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert kwargs["network_mode"] == "none"

    def test_to_docker_kwargs_with_resource_limits(self) -> None:
        from mcpbr.resource_limits import ResourceLimits

        limits = ResourceLimits(cpu_count=2.0, memory_mb=4096, pids_limit=256)
        profile = SandboxProfile(resource_limits=limits, no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert kwargs["nano_cpus"] == int(2.0 * 1e9)
        assert kwargs["mem_limit"] == "4096m"
        assert kwargs["pids_limit"] == 256

    def test_network_disabled_overrides_resource_limit_network(self) -> None:
        """When network_disabled=True, sandbox's 'none' should win over resource limits."""
        from mcpbr.resource_limits import ResourceLimits

        limits = ResourceLimits(network_mode="bridge")
        profile = SandboxProfile(
            network_disabled=True, resource_limits=limits, no_new_privileges=False
        )
        kwargs = profile.to_docker_kwargs()
        assert kwargs["network_mode"] == "none"


class TestCreateProfile:
    """Tests for create_profile factory."""

    def test_create_permissive(self) -> None:
        profile = create_profile(SecurityLevel.PERMISSIVE)
        assert profile.name == "permissive"
        assert profile.cap_drop == []
        assert profile.no_new_privileges is False
        assert profile.network_disabled is False

    def test_create_standard(self) -> None:
        profile = create_profile(SecurityLevel.STANDARD)
        assert profile.name == "standard"
        assert profile.cap_drop == DANGEROUS_CAPABILITIES
        assert profile.no_new_privileges is True
        assert profile.resource_limits is not None
        assert profile.resource_limits.cpu_count == 2.0
        assert profile.resource_limits.memory_mb == 4096

    def test_create_strict(self) -> None:
        profile = create_profile(SecurityLevel.STRICT)
        assert profile.name == "strict"
        assert profile.cap_drop == ["ALL"]
        assert profile.cap_add == MINIMAL_CAPABILITIES
        assert profile.seccomp is not None
        assert profile.seccomp.default_action == "SCMP_ACT_ERRNO"
        assert len(profile.seccomp.allowed_syscalls) > 0
        assert profile.read_only_rootfs is True
        assert profile.no_new_privileges is True
        assert profile.network_disabled is True
        assert "/tmp" in profile.tmpfs_mounts

    def test_create_from_string(self) -> None:
        profile = create_profile("standard")
        assert profile.security_level == SecurityLevel.STANDARD

    def test_create_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown security level"):
            create_profile("nonexistent")

    def test_strict_docker_kwargs_complete(self) -> None:
        """Verify strict profile generates all expected Docker kwargs."""
        profile = create_profile("strict")
        kwargs = profile.to_docker_kwargs()
        assert "cap_drop" in kwargs
        assert "cap_add" in kwargs
        assert "security_opt" in kwargs
        assert "read_only" in kwargs
        assert "tmpfs" in kwargs
        assert "network_mode" in kwargs
        assert kwargs["network_mode"] == "none"
        assert kwargs["read_only"] is True


class TestParseSandboxConfig:
    """Tests for parse_sandbox_config."""

    def test_parse_level_only(self) -> None:
        config = {"level": "standard"}
        profile = parse_sandbox_config(config)
        assert profile.security_level == SecurityLevel.STANDARD
        assert profile.cap_drop == DANGEROUS_CAPABILITIES

    def test_parse_with_overrides(self) -> None:
        config = {
            "level": "standard",
            "cap_drop": ["SYS_ADMIN"],
            "read_only_rootfs": True,
        }
        profile = parse_sandbox_config(config)
        assert profile.cap_drop == ["SYS_ADMIN"]
        assert profile.read_only_rootfs is True

    def test_parse_network_disabled_override(self) -> None:
        config = {"level": "permissive", "network_disabled": True}
        profile = parse_sandbox_config(config)
        assert profile.network_disabled is True

    def test_parse_default_level(self) -> None:
        config = {}
        profile = parse_sandbox_config(config)
        assert profile.security_level == SecurityLevel.STANDARD

    def test_parse_tmpfs_override(self) -> None:
        config = {
            "level": "strict",
            "tmpfs_mounts": {"/tmp": "size=1g"},
        }
        profile = parse_sandbox_config(config)
        assert profile.tmpfs_mounts == {"/tmp": "size=1g"}

    def test_parse_invalid_level_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown security level"):
            parse_sandbox_config({"level": "ultra-strict"})


class TestConstants:
    """Tests for module constants."""

    def test_dangerous_capabilities_not_empty(self) -> None:
        assert len(DANGEROUS_CAPABILITIES) > 0

    def test_minimal_capabilities_not_empty(self) -> None:
        assert len(MINIMAL_CAPABILITIES) > 0

    def test_dangerous_syscalls_not_empty(self) -> None:
        assert len(DANGEROUS_SYSCALLS) > 0

    def test_no_overlap_capabilities(self) -> None:
        """Dangerous and minimal capabilities should not overlap."""
        overlap = set(DANGEROUS_CAPABILITIES) & set(MINIMAL_CAPABILITIES)
        assert len(overlap) == 0, f"Overlapping capabilities: {overlap}"


class TestNewSandboxFields:
    """Tests for v0.12.0 sandbox enhancements."""

    def test_userns_mode_default_none(self) -> None:
        profile = SandboxProfile()
        assert profile.userns_mode is None

    def test_userns_mode_in_strict_profile(self) -> None:
        profile = create_profile("strict")
        # Strict should NOT use "host" userns -- that shares host UIDs
        assert profile.userns_mode is None

    def test_userns_mode_in_docker_kwargs(self) -> None:
        profile = SandboxProfile(userns_mode="host", no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert kwargs["userns_mode"] == "host"

    def test_userns_mode_not_in_kwargs_when_none(self) -> None:
        profile = SandboxProfile(no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert "userns_mode" not in kwargs

    def test_device_read_bps_default_none(self) -> None:
        profile = SandboxProfile()
        assert profile.device_read_bps is None

    def test_device_write_bps_default_none(self) -> None:
        profile = SandboxProfile()
        assert profile.device_write_bps is None

    def test_device_read_bps_in_docker_kwargs(self) -> None:
        profile = SandboxProfile(device_read_bps=10_000_000, no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert "device_read_bps" in kwargs
        assert kwargs["device_read_bps"][0]["Rate"] == 10_000_000

    def test_device_write_bps_in_docker_kwargs(self) -> None:
        profile = SandboxProfile(device_write_bps=5_000_000, no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert "device_write_bps" in kwargs
        assert kwargs["device_write_bps"][0]["Rate"] == 5_000_000

    def test_io_limits_not_in_kwargs_when_none(self) -> None:
        profile = SandboxProfile(no_new_privileges=False)
        kwargs = profile.to_docker_kwargs()
        assert "device_read_bps" not in kwargs
        assert "device_write_bps" not in kwargs

    def test_network_allowlist_default_empty(self) -> None:
        profile = SandboxProfile()
        assert profile.network_allowlist == []

    def test_network_allowlist_values(self) -> None:
        profile = SandboxProfile(network_allowlist=["api.example.com", "cdn.example.com"])
        assert len(profile.network_allowlist) == 2
        assert "api.example.com" in profile.network_allowlist

    def test_parse_userns_mode(self) -> None:
        config = {"level": "standard", "userns_mode": "host"}
        profile = parse_sandbox_config(config)
        assert profile.userns_mode == "host"

    def test_parse_io_limits(self) -> None:
        config = {
            "level": "standard",
            "device_read_bps": 20_000_000,
            "device_write_bps": 10_000_000,
        }
        profile = parse_sandbox_config(config)
        assert profile.device_read_bps == 20_000_000
        assert profile.device_write_bps == 10_000_000

    def test_parse_network_allowlist(self) -> None:
        config = {
            "level": "standard",
            "network_allowlist": ["api.example.com"],
        }
        profile = parse_sandbox_config(config)
        assert profile.network_allowlist == ["api.example.com"]

    def test_parse_network_allowlist_emits_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """network_allowlist should warn that it's not yet enforced (#418)."""
        import logging

        with caplog.at_level(logging.WARNING):
            parse_sandbox_config(
                {
                    "level": "standard",
                    "network_allowlist": ["api.example.com"],
                }
            )
        assert any("network_allowlist" in m and "not yet enforced" in m for m in caplog.messages)


class TestValidateSandbox:
    """Tests for validate_sandbox function."""

    def test_valid_profile_passes(self) -> None:
        profile = SandboxProfile(
            cap_drop=["SYS_ADMIN"],
            cap_add=["CHOWN"],
            no_new_privileges=True,
            read_only_rootfs=True,
            network_disabled=True,
            userns_mode="host",
        )
        container_attrs = {
            "CapDrop": ["SYS_ADMIN"],
            "CapAdd": ["CHOWN"],
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "SecurityOpt": ["no-new-privileges:true"],
            "UsernsMode": "host",
        }
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is True
        assert mismatches == []

    def test_cap_drop_mismatch(self) -> None:
        profile = SandboxProfile(cap_drop=["SYS_ADMIN", "NET_ADMIN"], no_new_privileges=False)
        container_attrs = {"CapDrop": ["SYS_ADMIN"]}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("cap_drop" in m for m in mismatches)

    def test_cap_add_mismatch(self) -> None:
        profile = SandboxProfile(cap_add=["CHOWN", "SETUID"], no_new_privileges=False)
        container_attrs = {"CapAdd": ["CHOWN"]}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("cap_add" in m for m in mismatches)

    def test_read_only_mismatch(self) -> None:
        profile = SandboxProfile(read_only_rootfs=True, no_new_privileges=False)
        container_attrs = {"ReadonlyRootfs": False}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("read_only_rootfs" in m for m in mismatches)

    def test_network_mode_mismatch(self) -> None:
        profile = SandboxProfile(network_disabled=True, no_new_privileges=False)
        container_attrs = {"NetworkMode": "bridge"}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("network_mode" in m for m in mismatches)

    def test_no_new_privileges_mismatch(self) -> None:
        profile = SandboxProfile(no_new_privileges=True)
        container_attrs = {"SecurityOpt": []}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("no_new_privileges" in m for m in mismatches)

    def test_userns_mode_mismatch(self) -> None:
        profile = SandboxProfile(userns_mode="host", no_new_privileges=False)
        container_attrs = {"UsernsMode": ""}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert any("userns_mode" in m for m in mismatches)

    def test_empty_profile_passes(self) -> None:
        """A profile with no restrictions should pass with any container."""
        profile = SandboxProfile(
            cap_drop=[], cap_add=[], no_new_privileges=False, network_disabled=False
        )
        container_attrs = {}
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is True
        assert mismatches == []


class TestStrictSeccompAllowlist:
    """Tests for #417: Strict mode must use default-deny seccomp with allowlist."""

    def test_strict_seccomp_default_action_is_errno(self) -> None:
        """Strict profile must use SCMP_ACT_ERRNO (default-deny), not SCMP_ACT_ALLOW."""
        profile = create_profile("strict")
        assert profile.seccomp is not None
        assert profile.seccomp.default_action == "SCMP_ACT_ERRNO"

    def test_strict_seccomp_has_allowed_syscalls(self) -> None:
        """Strict profile must have an explicit allowlist of permitted syscalls."""
        profile = create_profile("strict")
        assert profile.seccomp is not None
        assert len(profile.seccomp.allowed_syscalls) > 0

    def test_strict_seccomp_allows_basic_operations(self) -> None:
        """Strict allowlist must include syscalls needed for Python/shell execution."""
        profile = create_profile("strict")
        assert profile.seccomp is not None
        required = [
            "read",
            "write",
            "openat",
            "close",
            "mmap",
            "execve",
            "exit_group",
            "brk",
            "clone",
            "wait4",
            "getpid",
            "fcntl",
            "fstat",
        ]
        for sc in required:
            assert sc in profile.seccomp.allowed_syscalls, f"Missing required syscall: {sc}"

    def test_strict_seccomp_blocks_container_escape_syscalls(self) -> None:
        """Strict allowlist must NOT include known container escape syscalls."""
        profile = create_profile("strict")
        assert profile.seccomp is not None
        forbidden = [
            "mount",
            "umount2",
            "pivot_root",
            "unshare",
            "setns",
            "kexec_load",
            "init_module",
            "finit_module",
            "delete_module",
            "open_by_handle_at",
            "bpf",
            "userfaultfd",
            "io_uring_setup",
            "io_uring_enter",
            "io_uring_register",
            "process_vm_readv",
            "process_vm_writev",
            "keyctl",
            "request_key",
            "add_key",
            "ptrace",
            "reboot",
        ]
        for sc in forbidden:
            assert sc not in profile.seccomp.allowed_syscalls, (
                f"Dangerous syscall in allowlist: {sc}"
            )

    def test_strict_seccomp_docker_format_has_allow_rule(self) -> None:
        """Docker seccomp JSON must have an ALLOW rule for allowed syscalls."""
        profile = create_profile("strict")
        assert profile.seccomp is not None
        docker_fmt = profile.seccomp.to_docker_format()
        assert docker_fmt["defaultAction"] == "SCMP_ACT_ERRNO"
        allow_rules = [r for r in docker_fmt["syscalls"] if r["action"] == "SCMP_ACT_ALLOW"]
        assert len(allow_rules) == 1
        assert len(allow_rules[0]["names"]) > 0

    def test_strict_minimal_capabilities_no_dac_override(self) -> None:
        """MINIMAL_CAPABILITIES must not include DAC_OVERRIDE (root-like file access)."""
        assert "DAC_OVERRIDE" not in MINIMAL_CAPABILITIES

    def test_strict_minimal_capabilities_no_fowner(self) -> None:
        """MINIMAL_CAPABILITIES must not include FOWNER."""
        assert "FOWNER" not in MINIMAL_CAPABILITIES

    def test_strict_minimal_capabilities_no_net_bind_service(self) -> None:
        """MINIMAL_CAPABILITIES must not include NET_BIND_SERVICE (useless with network disabled)."""
        assert "NET_BIND_SERVICE" not in MINIMAL_CAPABILITIES

    def test_strict_userns_mode_not_host(self) -> None:
        """Strict profile must not use userns_mode='host' (shares host UIDs)."""
        profile = create_profile("strict")
        assert profile.userns_mode != "host"

    def test_seccomp_profile_with_allowlist_docker_format(self) -> None:
        """SeccompProfile with allowed_syscalls generates proper Docker JSON."""
        sp = SeccompProfile(
            default_action="SCMP_ACT_ERRNO",
            allowed_syscalls=["read", "write", "close"],
        )
        fmt = sp.to_docker_format()
        assert fmt["defaultAction"] == "SCMP_ACT_ERRNO"
        assert len(fmt["syscalls"]) == 1
        assert fmt["syscalls"][0]["action"] == "SCMP_ACT_ALLOW"
        assert sorted(fmt["syscalls"][0]["names"]) == ["close", "read", "write"]

    def test_seccomp_profile_blocklist_still_works(self) -> None:
        """Existing blocklist approach still works for backward compatibility."""
        sp = SeccompProfile(
            default_action="SCMP_ACT_ALLOW",
            blocked_syscalls=["mount", "ptrace"],
        )
        fmt = sp.to_docker_format()
        assert fmt["defaultAction"] == "SCMP_ACT_ALLOW"
        assert fmt["syscalls"][0]["action"] == "SCMP_ACT_ERRNO"
        assert "mount" in fmt["syscalls"][0]["names"]


class TestValidateSandboxStrictMode:
    """Tests for #427: validate_sandbox raises errors in strict mode."""

    def test_strict_mode_raises_on_cap_drop_mismatch(self) -> None:
        """In strict mode, cap_drop mismatch should raise ValueError."""
        profile = SandboxProfile(
            cap_drop=["ALL"],
            cap_add=[],
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"CapDrop": ["SYS_ADMIN"]}
        with pytest.raises(ValueError, match="cap_drop"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_raises_on_network_mismatch(self) -> None:
        """In strict mode, network_mode mismatch should raise ValueError."""
        profile = SandboxProfile(
            network_disabled=True,
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"NetworkMode": "bridge"}
        with pytest.raises(ValueError, match="network_mode"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_raises_on_read_only_mismatch(self) -> None:
        """In strict mode, read_only_rootfs mismatch should raise ValueError."""
        profile = SandboxProfile(
            read_only_rootfs=True,
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"ReadonlyRootfs": False}
        with pytest.raises(ValueError, match="read_only_rootfs"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_raises_on_no_new_privileges_mismatch(self) -> None:
        """In strict mode, no_new_privileges mismatch should raise ValueError."""
        profile = SandboxProfile(
            no_new_privileges=True,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"SecurityOpt": []}
        with pytest.raises(ValueError, match="no_new_privileges"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_raises_on_cap_add_mismatch(self) -> None:
        """In strict mode, cap_add mismatch should raise ValueError."""
        profile = SandboxProfile(
            cap_add=["CHOWN", "SETUID"],
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"CapAdd": ["CHOWN"]}
        with pytest.raises(ValueError, match="cap_add"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_raises_on_userns_mismatch(self) -> None:
        """In strict mode, userns_mode mismatch should raise ValueError."""
        profile = SandboxProfile(
            userns_mode="host",
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {"UsernsMode": ""}
        with pytest.raises(ValueError, match="userns_mode"):
            validate_sandbox(container_attrs, profile)

    def test_strict_mode_valid_profile_passes(self) -> None:
        """In strict mode, a valid container should still pass without error."""
        profile = SandboxProfile(
            cap_drop=["ALL"],
            cap_add=["CHOWN"],
            no_new_privileges=True,
            read_only_rootfs=True,
            network_disabled=True,
            userns_mode="host",
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {
            "CapDrop": ["ALL"],
            "CapAdd": ["CHOWN"],
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "SecurityOpt": ["no-new-privileges:true"],
            "UsernsMode": "host",
        }
        valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is True
        assert mismatches == []

    def test_strict_mode_raises_with_multiple_mismatches(self) -> None:
        """In strict mode with multiple mismatches, ValueError should list all of them."""
        profile = SandboxProfile(
            cap_drop=["ALL"],
            read_only_rootfs=True,
            network_disabled=True,
            no_new_privileges=False,
            security_level=SecurityLevel.STRICT,
        )
        container_attrs = {
            "CapDrop": [],
            "ReadonlyRootfs": False,
            "NetworkMode": "bridge",
        }
        with pytest.raises(ValueError, match="Sandbox validation failed"):
            validate_sandbox(container_attrs, profile)

    def test_standard_mode_warns_but_does_not_raise(self, caplog: pytest.LogCaptureFixture) -> None:
        """In standard mode, mismatches should warn but NOT raise (backward compat)."""
        import logging

        profile = SandboxProfile(
            cap_drop=["SYS_ADMIN", "NET_ADMIN"],
            no_new_privileges=False,
            security_level=SecurityLevel.STANDARD,
        )
        container_attrs = {"CapDrop": ["SYS_ADMIN"]}
        with caplog.at_level(logging.WARNING):
            valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert len(mismatches) > 0
        assert any("cap_drop" in m for m in caplog.messages)

    def test_permissive_mode_warns_but_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """In permissive mode, mismatches should warn but NOT raise (backward compat)."""
        import logging

        profile = SandboxProfile(
            cap_drop=["SYS_ADMIN"],
            no_new_privileges=False,
            security_level=SecurityLevel.PERMISSIVE,
        )
        container_attrs = {"CapDrop": []}
        with caplog.at_level(logging.WARNING):
            valid, mismatches = validate_sandbox(container_attrs, profile)
        assert valid is False
        assert len(mismatches) > 0
        # Should NOT have raised
