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
        assert profile.seccomp.blocked_syscalls == DANGEROUS_SYSCALLS
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
