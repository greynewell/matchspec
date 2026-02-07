"""Tests for GCP Compute Engine infrastructure provider."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mcpbr.infrastructure.aws import _validate_env_key, _validate_python_version


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock HarnessConfig with GCP settings."""
    config = MagicMock()
    config.infrastructure.mode = "gcp"
    config.infrastructure.gcp.zone = "us-central1-a"
    config.infrastructure.gcp.machine_type = None
    config.infrastructure.gcp.cpu_cores = 4
    config.infrastructure.gcp.memory_gb = 16
    config.infrastructure.gcp.disk_gb = 100
    config.infrastructure.gcp.disk_type = "pd-ssd"
    config.infrastructure.gcp.image_family = "ubuntu-2204-lts"
    config.infrastructure.gcp.image_project = "ubuntu-os-cloud"
    config.infrastructure.gcp.project_id = "test-project"
    config.infrastructure.gcp.auto_shutdown = True
    config.infrastructure.gcp.preserve_on_error = True
    config.infrastructure.gcp.env_keys_to_export = ["ANTHROPIC_API_KEY"]
    config.infrastructure.gcp.ssh_key_path = None
    config.infrastructure.gcp.python_version = "3.11"
    config.infrastructure.gcp.spot = False
    config.infrastructure.gcp.preemptible = False
    config.infrastructure.gcp.labels = {}
    config.infrastructure.gcp.service_account = None
    config.infrastructure.gcp.scopes = []
    config.benchmark = "swe-bench-lite"
    config.task_ids = None
    config.model_dump.return_value = {"infrastructure": {"mode": "gcp"}}
    return config


# ============================================================================
# Security Validation Tests (#421, #422)
# ============================================================================


class TestGCPPythonVersionValidation:
    """Tests for #421: python_version shell injection prevention in GCP provider."""

    def test_valid_python_versions_accepted(self) -> None:
        """Standard Python versions should be accepted."""
        for ver in ["3.11", "3.12", "3.13", "3.9"]:
            _validate_python_version(ver)  # Should not raise

    def test_shell_injection_in_python_version_rejected(self) -> None:
        """Malicious python_version values should raise ValueError."""
        for bad_ver in [
            "3.11; rm -rf /",
            "3.11 && curl evil.com",
            "$(whoami)",
            "3.11`id`",
            "../3.11",
        ]:
            with pytest.raises(ValueError, match="Invalid python_version"):
                _validate_python_version(bad_ver)


class TestGCPEnvKeyValidation:
    """Tests for #421: env key name injection prevention in GCP provider."""

    def test_valid_env_keys_accepted(self) -> None:
        for key in ["ANTHROPIC_API_KEY", "HOME", "PATH", "_VAR", "MY_VAR_123"]:
            _validate_env_key(key)  # Should not raise

    def test_shell_injection_in_env_key_rejected(self) -> None:
        for bad_key in [
            "FOO;rm -rf /",
            "BAR && evil",
            "$(whoami)",
            "KEY`id`",
            "KEY=value",
            "KEY NAME",
        ]:
            with pytest.raises(ValueError, match="Invalid environment variable name"):
                _validate_env_key(bad_key)


class TestGCPSSHFirewallSafety:
    """Tests for #422: SSH firewall rule should never fall back to 0.0.0.0/0."""

    async def test_firewall_rule_never_uses_open_cidr(self, mock_config: MagicMock) -> None:
        """_ensure_ssh_firewall_rule must never use 0.0.0.0/0 when IP detection fails."""
        from mcpbr.infrastructure.gcp import GCPProvider

        provider = GCPProvider(mock_config)

        # Simulate: firewall rule does not exist yet (describe returns non-zero),
        # and IP detection fails (curl errors out)
        def mock_run_side_effects(*args, **kwargs):
            cmd = args[0]
            if "firewall-rules" in cmd and "describe" in cmd:
                return Mock(returncode=1, stdout="", stderr="not found")
            if "curl" in cmd:
                raise Exception("network error")
            return Mock(returncode=0, stdout="", stderr="")

        with patch("mcpbr.infrastructure.gcp.subprocess.run", side_effect=mock_run_side_effects):
            with pytest.raises(RuntimeError, match="Could not determine"):
                await provider._ensure_ssh_firewall_rule()

    async def test_firewall_rule_validates_ip_format(self, mock_config: MagicMock) -> None:
        """Firewall rule creation should validate the IP address format."""
        from mcpbr.infrastructure.gcp import GCPProvider

        provider = GCPProvider(mock_config)

        def mock_run_side_effects(*args, **kwargs):
            cmd = args[0]
            if "firewall-rules" in cmd and "describe" in cmd:
                return Mock(returncode=1, stdout="", stderr="not found")
            if "curl" in cmd:
                return Mock(returncode=0, stdout="not-an-ip\n")
            return Mock(returncode=0, stdout="", stderr="")

        with patch("mcpbr.infrastructure.gcp.subprocess.run", side_effect=mock_run_side_effects):
            with pytest.raises(RuntimeError, match="Could not determine"):
                await provider._ensure_ssh_firewall_rule()

    async def test_firewall_rule_with_valid_ip(self, mock_config: MagicMock) -> None:
        """Firewall rule should work with a valid IP response."""
        from mcpbr.infrastructure.gcp import GCPProvider

        provider = GCPProvider(mock_config)

        def mock_run_side_effects(*args, **kwargs):
            cmd = args[0]
            if "firewall-rules" in cmd and "describe" in cmd:
                return Mock(returncode=1, stdout="", stderr="not found")
            if "curl" in cmd:
                return Mock(returncode=0, stdout="203.0.113.42\n")
            if "firewall-rules" in cmd and "create" in cmd:
                # Verify the source-ranges argument contains our IP, not 0.0.0.0/0
                assert "203.0.113.42/32" in cmd
                assert "0.0.0.0/0" not in cmd
                return Mock(returncode=0, stdout="", stderr="")
            return Mock(returncode=0, stdout="", stderr="")

        with patch("mcpbr.infrastructure.gcp.subprocess.run", side_effect=mock_run_side_effects):
            await provider._ensure_ssh_firewall_rule()


class TestGCPInstallDependenciesValidation:
    """Test that GCP _install_dependencies validates python_version."""

    async def test_malicious_python_version_rejected(self, mock_config: MagicMock) -> None:
        """_install_dependencies should reject malicious python_version before SSH."""
        from mcpbr.infrastructure.gcp import GCPProvider

        mock_config.infrastructure.gcp.python_version = "3.11; rm -rf /"
        provider = GCPProvider(mock_config)

        # Should raise ValueError before ever calling SSH
        with pytest.raises(ValueError, match="Invalid python_version"):
            await provider._install_dependencies()


class TestGCPExportEnvVarsValidation:
    """Test that GCP _export_env_vars validates env key names."""

    async def test_malicious_env_key_rejected(self, mock_config: MagicMock) -> None:
        """_export_env_vars should reject malicious env key names."""
        from mcpbr.infrastructure.gcp import GCPProvider

        mock_config.infrastructure.gcp.env_keys_to_export = ["VALID_KEY", "BAD;rm -rf /"]
        provider = GCPProvider(mock_config)

        with pytest.raises(ValueError, match="Invalid environment variable name"):
            await provider._export_env_vars()
