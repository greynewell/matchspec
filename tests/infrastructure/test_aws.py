"""Tests for AWS EC2 infrastructure provider."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcpbr.infrastructure.aws import (
    AWSProvider,
    _check_aws_authenticated,
    _check_aws_cli_installed,
    _check_instance_type_available,
)


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock HarnessConfig with AWS settings."""
    config = MagicMock()
    config.infrastructure.mode = "aws"
    config.infrastructure.aws.region = "us-east-1"
    config.infrastructure.aws.instance_type = None
    config.infrastructure.aws.cpu_cores = 8
    config.infrastructure.aws.memory_gb = 32
    config.infrastructure.aws.disk_gb = 1000
    config.infrastructure.aws.auto_shutdown = True
    config.infrastructure.aws.preserve_on_error = True
    config.infrastructure.aws.env_keys_to_export = ["ANTHROPIC_API_KEY"]
    config.infrastructure.aws.ssh_key_path = None
    config.infrastructure.aws.key_name = None
    config.infrastructure.aws.ami_id = None
    config.infrastructure.aws.subnet_id = None
    config.infrastructure.aws.iam_instance_profile = None
    config.infrastructure.aws.python_version = "3.11"
    config.benchmark = "swe-bench-lite"
    config.task_ids = None
    config.model_dump.return_value = {"infrastructure": {"mode": "aws"}}
    return config


@pytest.fixture
def aws_provider(mock_config: MagicMock) -> AWSProvider:
    """Create an AWS provider instance with mocked config."""
    return AWSProvider(mock_config)


# ============================================================================
# Instance Type Mapping Tests
# ============================================================================


class TestInstanceTypeMapping:
    """Test _determine_instance_type mapping from cpu_cores/memory_gb."""

    def test_mapping_1_core_1gb(self, mock_config: MagicMock) -> None:
        """Test mapping 1 core, 1GB -> t3.micro."""
        mock_config.infrastructure.aws.cpu_cores = 1
        mock_config.infrastructure.aws.memory_gb = 1
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.micro"

    def test_mapping_1_core_2gb(self, mock_config: MagicMock) -> None:
        """Test mapping 1 core, 2GB -> t3.small."""
        mock_config.infrastructure.aws.cpu_cores = 1
        mock_config.infrastructure.aws.memory_gb = 2
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.small"

    def test_mapping_2_cores_4gb(self, mock_config: MagicMock) -> None:
        """Test mapping 2 cores, 4GB -> t3.medium."""
        mock_config.infrastructure.aws.cpu_cores = 2
        mock_config.infrastructure.aws.memory_gb = 4
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.medium"

    def test_mapping_2_cores_8gb(self, mock_config: MagicMock) -> None:
        """Test mapping 2 cores, 8GB -> t3.large."""
        mock_config.infrastructure.aws.cpu_cores = 2
        mock_config.infrastructure.aws.memory_gb = 8
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.large"

    def test_mapping_4_cores_16gb(self, mock_config: MagicMock) -> None:
        """Test mapping 4 cores, 16GB -> t3.xlarge."""
        mock_config.infrastructure.aws.cpu_cores = 4
        mock_config.infrastructure.aws.memory_gb = 16
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.xlarge"

    def test_mapping_8_cores_32gb(self, mock_config: MagicMock) -> None:
        """Test mapping 8 cores, 32GB -> t3.2xlarge."""
        mock_config.infrastructure.aws.cpu_cores = 8
        mock_config.infrastructure.aws.memory_gb = 32
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "t3.2xlarge"

    def test_mapping_16_cores_64gb(self, mock_config: MagicMock) -> None:
        """Test mapping 16 cores, 64GB -> m5.4xlarge."""
        mock_config.infrastructure.aws.cpu_cores = 16
        mock_config.infrastructure.aws.memory_gb = 64
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "m5.4xlarge"

    def test_mapping_large_cores_fallback(self, mock_config: MagicMock) -> None:
        """Test mapping 64+ cores -> m5.4xlarge fallback."""
        mock_config.infrastructure.aws.cpu_cores = 64
        mock_config.infrastructure.aws.memory_gb = 256
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "m5.4xlarge"

    def test_custom_instance_type_overrides_mapping(self, mock_config: MagicMock) -> None:
        """Test custom instance_type overrides cpu/memory mapping."""
        mock_config.infrastructure.aws.instance_type = "c5.4xlarge"
        mock_config.infrastructure.aws.cpu_cores = 2
        mock_config.infrastructure.aws.memory_gb = 4
        provider = AWSProvider(mock_config)
        assert provider._determine_instance_type() == "c5.4xlarge"


# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    """Test AWSProvider initialization."""

    def test_init_sets_config(self, aws_provider: AWSProvider, mock_config: MagicMock) -> None:
        """Test provider stores config reference."""
        assert aws_provider.config is mock_config

    def test_init_sets_aws_config(self, aws_provider: AWSProvider) -> None:
        """Test provider stores aws_config reference."""
        assert aws_provider.aws_config is not None

    def test_init_instance_id_none(self, aws_provider: AWSProvider) -> None:
        """Test instance_id is None initially."""
        assert aws_provider.instance_id is None

    def test_init_instance_ip_none(self, aws_provider: AWSProvider) -> None:
        """Test instance_ip is None initially."""
        assert aws_provider.instance_ip is None

    def test_init_ssh_client_none(self, aws_provider: AWSProvider) -> None:
        """Test ssh_client is None initially."""
        assert aws_provider.ssh_client is None

    def test_init_error_occurred_false(self, aws_provider: AWSProvider) -> None:
        """Test _error_occurred is False initially."""
        assert aws_provider._error_occurred is False


# ============================================================================
# SSH Exec Tests
# ============================================================================


class TestSSHExec:
    """Test _ssh_exec command execution."""

    async def test_ssh_exec_success(self, aws_provider: AWSProvider) -> None:
        """Test executing a command successfully over SSH."""
        mock_client = MagicMock()
        aws_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"hello world\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        exit_code, stdout, stderr = await aws_provider._ssh_exec("echo hello")

        assert exit_code == 0
        assert stdout == "hello world\n"
        assert stderr == ""

    async def test_ssh_exec_non_zero_exit(self, aws_provider: AWSProvider) -> None:
        """Test command with non-zero exit code."""
        mock_client = MagicMock()
        aws_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"command not found\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        exit_code, _stdout, stderr = await aws_provider._ssh_exec("bad_command")

        assert exit_code == 1
        assert stderr == "command not found\n"

    async def test_ssh_exec_no_client(self, aws_provider: AWSProvider) -> None:
        """Test executing command without SSH client raises error."""
        aws_provider.ssh_client = None

        with pytest.raises(RuntimeError, match="SSH client not initialized"):
            await aws_provider._ssh_exec("echo test")

    async def test_ssh_exec_exception(self, aws_provider: AWSProvider) -> None:
        """Test SSH command that raises an exception."""
        mock_client = MagicMock()
        aws_provider.ssh_client = mock_client
        mock_client.exec_command.side_effect = Exception("Connection lost")

        with pytest.raises(RuntimeError, match="SSH command failed"):
            await aws_provider._ssh_exec("echo test")


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test AWS health checks."""

    @patch("mcpbr.infrastructure.aws._check_instance_type_available")
    @patch("mcpbr.infrastructure.aws._check_aws_authenticated")
    @patch("mcpbr.infrastructure.aws._check_aws_cli_installed")
    async def test_health_check_all_pass(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_type: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test health check when all checks pass."""
        mock_cli.return_value = (True, "/usr/local/bin/aws")
        mock_auth.return_value = (True, "Authenticated as arn:aws:iam::123:user/test")
        mock_type.return_value = (True, "t3.2xlarge available in us-east-1")

        result = await aws_provider.health_check()

        assert result["aws_cli"] is True
        assert result["authenticated"] is True
        assert result["instance_type_valid"] is True
        assert len(result["errors"]) == 0

    @patch("mcpbr.infrastructure.aws._check_aws_cli_installed")
    async def test_health_check_cli_not_installed(
        self,
        mock_cli: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test health check when AWS CLI is not installed."""
        mock_cli.return_value = (False, "AWS CLI not found")

        result = await aws_provider.health_check()

        assert result["aws_cli"] is False
        assert len(result["errors"]) > 0

    @patch("mcpbr.infrastructure.aws._check_aws_authenticated")
    @patch("mcpbr.infrastructure.aws._check_aws_cli_installed")
    async def test_health_check_not_authenticated(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test health check when not authenticated."""
        mock_cli.return_value = (True, "/usr/local/bin/aws")
        mock_auth.return_value = (False, "Not authenticated to AWS")

        result = await aws_provider.health_check()

        assert result["aws_cli"] is True
        assert result["authenticated"] is False
        assert len(result["errors"]) > 0

    @patch("mcpbr.infrastructure.aws._check_instance_type_available")
    @patch("mcpbr.infrastructure.aws._check_aws_authenticated")
    @patch("mcpbr.infrastructure.aws._check_aws_cli_installed")
    async def test_health_check_instance_type_warning(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_type: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test health check when instance type is unavailable (warning, not error)."""
        mock_cli.return_value = (True, "/usr/local/bin/aws")
        mock_auth.return_value = (True, "Authenticated")
        mock_type.return_value = (False, "Instance type not available")

        result = await aws_provider.health_check()

        assert result["instance_type_valid"] is False
        assert len(result["warnings"]) > 0
        # Instance type is a warning, not an error
        assert len(result["errors"]) == 0


# ============================================================================
# Health Check Helper Tests
# ============================================================================


class TestHealthCheckHelpers:
    """Test standalone health check helper functions."""

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_aws_cli_installed_success(self, mock_run: MagicMock) -> None:
        """Test AWS CLI check when installed."""
        mock_run.return_value = Mock(returncode=0, stdout="/usr/local/bin/aws")
        ok, msg = _check_aws_cli_installed()
        assert ok is True

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_aws_cli_installed_missing(self, mock_run: MagicMock) -> None:
        """Test AWS CLI check when not installed."""
        mock_run.return_value = Mock(returncode=1, stdout="")
        ok, msg = _check_aws_cli_installed()
        assert ok is False

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_aws_authenticated_success(self, mock_run: MagicMock) -> None:
        """Test AWS auth check when authenticated."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"Arn": "arn:aws:iam::123:user/test"}',
        )
        ok, msg = _check_aws_authenticated()
        assert ok is True
        assert "arn:aws:iam" in msg

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_aws_authenticated_failure(self, mock_run: MagicMock) -> None:
        """Test AWS auth check when not authenticated."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="not configured")
        ok, msg = _check_aws_authenticated()
        assert ok is False

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_instance_type_available_success(self, mock_run: MagicMock) -> None:
        """Test instance type check when available."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"InstanceTypeOfferings": [{"InstanceType": "t3.large"}]}',
        )
        ok, msg = _check_instance_type_available("us-east-1", "t3.large")
        assert ok is True

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    def test_check_instance_type_not_available(self, mock_run: MagicMock) -> None:
        """Test instance type check when not available."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"InstanceTypeOfferings": []}',
        )
        ok, msg = _check_instance_type_available("us-east-1", "p4d.24xlarge")
        assert ok is False


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Test EC2 instance cleanup."""

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_cleanup_terminates_instance(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test cleanup terminates the EC2 instance."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        mock_run.return_value = Mock(returncode=0)

        await aws_provider.cleanup()

        # Should call terminate-instances
        calls = mock_run.call_args_list
        assert any("terminate-instances" in str(call) for call in calls)

    async def test_cleanup_no_instance(self, aws_provider: AWSProvider) -> None:
        """Test cleanup when no instance exists does nothing."""
        aws_provider.instance_id = None

        # Should not raise
        await aws_provider.cleanup()

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_cleanup_closes_ssh_client(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test cleanup closes SSH client."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        mock_client = MagicMock()
        aws_provider.ssh_client = mock_client
        mock_run.return_value = Mock(returncode=0)

        await aws_provider.cleanup()

        mock_client.close.assert_called_once()

    async def test_cleanup_preserve_on_error(self, aws_provider: AWSProvider) -> None:
        """Test cleanup preserves instance when error occurred and preserve_on_error is True."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        aws_provider.instance_ip = "1.2.3.4"
        aws_provider.ssh_key_path = Path("/tmp/key")
        aws_provider._error_occurred = True
        aws_provider.aws_config.preserve_on_error = True

        # Should not terminate
        await aws_provider.cleanup()

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_cleanup_force_ignores_preserve(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test forced cleanup ignores preserve_on_error."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        aws_provider._error_occurred = True
        aws_provider.aws_config.preserve_on_error = True
        mock_run.return_value = Mock(returncode=0)

        await aws_provider.cleanup(force=True)

        # Should still terminate despite preserve_on_error
        calls = mock_run.call_args_list
        assert any("terminate-instances" in str(call) for call in calls)

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_cleanup_auto_shutdown_false(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test cleanup skips termination when auto_shutdown is False."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        aws_provider.instance_ip = "1.2.3.4"
        aws_provider.ssh_key_path = Path("/tmp/key")
        aws_provider.aws_config.auto_shutdown = False

        await aws_provider.cleanup()

        # Should not call terminate
        mock_run.assert_not_called()


# ============================================================================
# Get Public IP Tests
# ============================================================================


class TestGetPublicIP:
    """Test _get_public_ip method."""

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_get_public_ip_success(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test getting public IP successfully."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        mock_run.return_value = Mock(returncode=0, stdout="54.123.45.67\n", stderr="")

        ip = await aws_provider._get_public_ip()

        assert ip == "54.123.45.67"

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_get_public_ip_failure(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test getting public IP when command fails."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        mock_run.return_value = Mock(returncode=1, stderr="Instance not found", stdout="")

        with pytest.raises(RuntimeError, match="Failed to get instance IP"):
            await aws_provider._get_public_ip()

    @patch("mcpbr.infrastructure.aws.subprocess.run")
    async def test_get_public_ip_none_value(
        self,
        mock_run: MagicMock,
        aws_provider: AWSProvider,
    ) -> None:
        """Test getting public IP when instance has no public IP."""
        aws_provider.instance_id = "i-1234567890abcdef0"
        mock_run.return_value = Mock(returncode=0, stdout="None\n", stderr="")

        with pytest.raises(RuntimeError, match="has no public IP"):
            await aws_provider._get_public_ip()


# ============================================================================
# SSH Connection Tests
# ============================================================================


class TestSSHConnection:
    """Test SSH connection management."""

    @patch("mcpbr.infrastructure.aws.paramiko.SSHClient")
    async def test_ssh_connection_success(
        self,
        mock_ssh_client: MagicMock,
        aws_provider: AWSProvider,
        tmp_path: Path,
    ) -> None:
        """Test successful SSH connection."""
        aws_provider.instance_ip = "54.123.45.67"
        aws_provider.ssh_key_path = tmp_path / "key"

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await aws_provider._wait_for_ssh(timeout=10)

        assert aws_provider.ssh_client is not None
        mock_client.connect.assert_called_once()
        connect_call = mock_client.connect.call_args
        assert connect_call[0][0] == "54.123.45.67"
        assert connect_call[1]["username"] == "ubuntu"

    @patch("mcpbr.infrastructure.aws.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.aws.asyncio.sleep", new_callable=AsyncMock)
    async def test_ssh_connection_timeout(
        self,
        mock_sleep: MagicMock,
        mock_ssh_client: MagicMock,
        aws_provider: AWSProvider,
        tmp_path: Path,
    ) -> None:
        """Test SSH connection timeout."""
        aws_provider.instance_ip = "54.123.45.67"
        aws_provider.ssh_key_path = tmp_path / "key"

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection refused")

        with pytest.raises(RuntimeError, match="SSH connection failed"):
            await aws_provider._wait_for_ssh(timeout=1)


# ============================================================================
# mcpbr Command Helper Tests
# ============================================================================


class TestMcpbrCmd:
    """Test _mcpbr_cmd helper."""

    def test_mcpbr_cmd_default_python(self, aws_provider: AWSProvider) -> None:
        """Test _mcpbr_cmd uses configured Python version."""
        aws_provider.aws_config.python_version = "3.11"
        assert aws_provider._mcpbr_cmd() == "python3.11 -m mcpbr"

    def test_mcpbr_cmd_custom_python(self, aws_provider: AWSProvider) -> None:
        """Test _mcpbr_cmd with custom Python version."""
        aws_provider.aws_config.python_version = "3.12"
        assert aws_provider._mcpbr_cmd() == "python3.12 -m mcpbr"


# ============================================================================
# Security Validation Tests (#421, #422)
# ============================================================================


class TestPythonVersionValidation:
    """Tests for #421: python_version shell injection prevention."""

    def test_valid_python_versions_accepted(self, mock_config: MagicMock) -> None:
        """Standard Python versions should be accepted."""
        for ver in ["3.11", "3.12", "3.13", "3.9"]:
            mock_config.infrastructure.aws.python_version = ver
            provider = AWSProvider(mock_config)
            assert provider.aws_config.python_version == ver

    def test_shell_injection_in_python_version_rejected(self) -> None:
        """Malicious python_version values should raise ValueError."""
        from mcpbr.infrastructure.aws import _validate_python_version

        for bad_ver in [
            "3.11; rm -rf /",
            "3.11 && curl evil.com",
            "$(whoami)",
            "3.11`id`",
            "../3.11",
        ]:
            with pytest.raises(ValueError, match="Invalid python_version"):
                _validate_python_version(bad_ver)

    def test_valid_python_version_passes_validation(self) -> None:
        from mcpbr.infrastructure.aws import _validate_python_version

        # Should not raise
        _validate_python_version("3.11")
        _validate_python_version("3.12")
        _validate_python_version("3.9")


class TestEnvKeyValidation:
    """Tests for #421: env key name injection prevention."""

    def test_valid_env_keys_accepted(self) -> None:
        from mcpbr.infrastructure.aws import _validate_env_key

        for key in ["ANTHROPIC_API_KEY", "HOME", "PATH", "_VAR", "MY_VAR_123"]:
            _validate_env_key(key)  # Should not raise

    def test_shell_injection_in_env_key_rejected(self) -> None:
        from mcpbr.infrastructure.aws import _validate_env_key

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


class TestSSHCIDRSafety:
    """Tests for #422: SSH CIDR should never fall back to 0.0.0.0/0."""

    def test_get_ssh_cidr_never_returns_open(self) -> None:
        """_get_ssh_cidr must never return 0.0.0.0/0."""
        # Simulate ifconfig.me failure
        with patch(
            "mcpbr.infrastructure.aws.subprocess.run", side_effect=Exception("network error")
        ):
            with pytest.raises(RuntimeError, match="Could not determine"):
                AWSProvider._get_ssh_cidr()

    def test_get_ssh_cidr_validates_ip_format(self) -> None:
        """_get_ssh_cidr must validate that the response is an IP address."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not-an-ip-address\n"
        with patch("mcpbr.infrastructure.aws.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Could not determine"):
                AWSProvider._get_ssh_cidr()

    def test_get_ssh_cidr_with_valid_ip(self) -> None:
        """_get_ssh_cidr should work with a valid IP response."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "203.0.113.42\n"
        with patch("mcpbr.infrastructure.aws.subprocess.run", return_value=mock_result):
            cidr = AWSProvider._get_ssh_cidr()
            assert cidr == "203.0.113.42/32"
