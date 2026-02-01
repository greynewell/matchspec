"""Tests for Azure infrastructure provider."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcpbr.config import AzureConfig, HarnessConfig, InfrastructureConfig, MCPServerConfig
from mcpbr.infrastructure.azure import AzureProvider


@pytest.fixture
def azure_config():
    """Create a test Azure configuration."""
    return AzureConfig(
        resource_group="test-rg",
        location="eastus",
        cpu_cores=8,
        memory_gb=32,
        disk_gb=250,
        auto_shutdown=True,
        preserve_on_error=True,
    )


@pytest.fixture
def harness_config(azure_config):
    """Create a test harness configuration with Azure."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        infrastructure=InfrastructureConfig(mode="azure", azure=azure_config),
    )


@pytest.fixture
def azure_provider(harness_config):
    """Create an Azure provider instance."""
    return AzureProvider(harness_config)


# ============================================================================
# VM Size Mapping Tests
# ============================================================================


class TestVMSizeMapping:
    """Test VM size mapping from cpu_cores/memory_gb."""

    def test_mapping_2_cores_8gb(self):
        """Test mapping 2 cores, 8GB → Standard_D2s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=2, memory_gb=8),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D2s_v3"

    def test_mapping_4_cores_16gb(self):
        """Test mapping 4 cores, 16GB → Standard_D4s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=4, memory_gb=16),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D4s_v3"

    def test_mapping_8_cores_32gb(self):
        """Test mapping 8 cores, 32GB → Standard_D8s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=8, memory_gb=32),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D8s_v3"

    def test_mapping_16_cores_64gb(self):
        """Test mapping 16 cores, 64GB → Standard_D16s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=16, memory_gb=64),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D16s_v3"

    def test_mapping_32_cores_128gb(self):
        """Test mapping 32 cores, 128GB → Standard_D32s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=32, memory_gb=128),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D32s_v3"

    def test_mapping_large_64_cores_256gb(self):
        """Test mapping 64+ cores → Standard_D64s_v3."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg", cpu_cores=64, memory_gb=256),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_D64s_v3"

    def test_custom_vm_size_overrides_mapping(self):
        """Test custom vm_size overrides cpu/memory mapping."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(
                    resource_group="test-rg",
                    cpu_cores=8,
                    memory_gb=32,
                    vm_size="Standard_E4s_v3",
                ),
            ),
        )
        provider = AzureProvider(config)
        assert provider._determine_vm_size() == "Standard_E4s_v3"


# ============================================================================
# VM Provisioning Tests
# ============================================================================


class TestVMProvisioning:
    """Test VM provisioning via az CLI."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    async def test_create_vm_success(self, mock_time, mock_run, azure_provider):
        """Test successful VM creation."""
        # Mock ssh-keygen, resource group show (exists), vm create
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show (exists)
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
        ]

        await azure_provider._create_vm("Standard_D8s_v3")

        assert azure_provider.vm_name == "mcpbr-eval-1234567890"
        assert azure_provider.ssh_key_path is not None
        # Verify az vm create was called
        calls = mock_run.call_args_list
        assert any("az" in str(call) and "vm" in str(call) for call in calls)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    async def test_create_vm_with_resource_group_creation(
        self, mock_time, mock_run, azure_provider
    ):
        """Test VM creation with resource group creation."""
        # Mock resource group doesn't exist, then create it
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=1, stderr="ResourceGroupNotFound"),  # az group show (not found)
            Mock(returncode=0),  # az group create
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
        ]

        await azure_provider._create_vm("Standard_D8s_v3")

        assert azure_provider.vm_name == "mcpbr-eval-1234567890"

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_create_vm_with_ssh_key_generation(self, mock_run, azure_provider):
        """Test VM creation with SSH key generation."""
        # Mock ssh-keygen, resource group show, and vm creation
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
        ]

        await azure_provider._create_vm("Standard_D8s_v3")

        # Verify ssh-keygen was called
        ssh_keygen_call = mock_run.call_args_list[0]
        assert "ssh-keygen" in str(ssh_keygen_call)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_create_vm_failure_quota_exceeded(self, mock_run, azure_provider):
        """Test VM creation failure (quota exceeded)."""
        # Mock ssh-keygen success, resource group show, VM creation failure
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=1, stderr="QuotaExceeded: Core quota exceeded"),  # az vm create
        ]

        with pytest.raises(RuntimeError, match="VM creation failed"):
            await azure_provider._create_vm("Standard_D8s_v3")

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_create_vm_with_existing_ssh_key(self, mock_run, azure_provider, tmp_path):
        """Test VM creation with existing SSH key."""
        # Create a dummy SSH key
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        # Mock resource group show and VM creation (no ssh-keygen)
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
        ]

        await azure_provider._create_vm("Standard_D8s_v3")

        # Verify ssh-keygen was NOT called
        assert all("ssh-keygen" not in str(call) for call in mock_run.call_args_list)


# ============================================================================
# VM IP Tests
# ============================================================================


class TestVMIP:
    """Test getting VM public IP."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_get_vm_ip_success(self, mock_run, azure_provider):
        """Test getting VM public IP."""
        azure_provider.vm_name = "test-vm"
        mock_run.return_value = Mock(returncode=0, stdout='"1.2.3.4"', stderr="")

        ip = await azure_provider._get_vm_ip()

        assert ip == "1.2.3.4"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "az" in args
        assert "vm" in args
        assert "show" in args

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_get_vm_ip_failure(self, mock_run, azure_provider):
        """Test VM IP retrieval failure."""
        azure_provider.vm_name = "test-vm"
        mock_run.return_value = Mock(returncode=1, stderr="VM not found", stdout="")

        with pytest.raises(RuntimeError, match="Failed to get VM IP"):
            await azure_provider._get_vm_ip()


# ============================================================================
# SSH Connection Tests
# ============================================================================


class TestSSHConnection:
    """Test SSH connection management."""

    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    async def test_ssh_connection_success(self, mock_ssh_client, azure_provider, tmp_path):
        """Test successful SSH connection."""
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = tmp_path / "key"

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await azure_provider._wait_for_ssh(timeout=10)

        assert azure_provider.ssh_client is not None
        mock_client.connect.assert_called_once()
        connect_call = mock_client.connect.call_args
        assert connect_call[0][0] == "1.2.3.4"
        assert connect_call[1]["username"] == "azureuser"

    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.asyncio.sleep", new_callable=AsyncMock)
    async def test_ssh_connection_timeout(
        self, mock_sleep, mock_ssh_client, azure_provider, tmp_path
    ):
        """Test SSH connection timeout."""
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = tmp_path / "key"

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client
        mock_client.connect.side_effect = Exception("Connection refused")

        with pytest.raises(RuntimeError, match="SSH connection failed"):
            await azure_provider._wait_for_ssh(timeout=1)

    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    async def test_ssh_connection_with_custom_key_path(
        self, mock_ssh_client, azure_provider, tmp_path
    ):
        """Test SSH connection with custom key path."""
        custom_key = tmp_path / "custom_key"
        custom_key.touch()
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = custom_key

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await azure_provider._wait_for_ssh(timeout=10)

        connect_call = mock_client.connect.call_args
        assert connect_call[1]["key_filename"] == str(custom_key)

    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.asyncio.sleep", new_callable=AsyncMock)
    async def test_ssh_connection_retries(
        self, mock_sleep, mock_ssh_client, azure_provider, tmp_path
    ):
        """Test SSH connection with retries."""
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = tmp_path / "key"

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client
        # Fail twice, then succeed
        mock_client.connect.side_effect = [
            Exception("Connection refused"),
            Exception("Connection refused"),
            None,
        ]

        await azure_provider._wait_for_ssh(timeout=30)

        assert azure_provider.ssh_client is not None
        assert mock_client.connect.call_count == 3


# ============================================================================
# SSH Command Execution Tests
# ============================================================================


class TestSSHCommandExecution:
    """Test executing commands over SSH."""

    async def test_execute_command_success(self, azure_provider):
        """Test executing command successfully."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        exit_code, stdout, stderr = await azure_provider._ssh_exec("echo test")

        assert exit_code == 0
        assert stdout == "output\n"
        assert stderr == ""

    async def test_execute_command_non_zero_exit(self, azure_provider):
        """Test command with non-zero exit code."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        exit_code, stdout, stderr = await azure_provider._ssh_exec("false")

        assert exit_code == 1
        assert stderr == "error\n"

    async def test_execute_command_timeout(self, azure_provider):
        """Test command timeout."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_client.exec_command.side_effect = Exception("Timeout")

        with pytest.raises(RuntimeError, match="SSH command failed"):
            await azure_provider._ssh_exec("sleep 1000", timeout=1)

    async def test_execute_command_no_client(self, azure_provider):
        """Test executing command without SSH client."""
        azure_provider.ssh_client = None

        with pytest.raises(RuntimeError, match="SSH client not initialized"):
            await azure_provider._ssh_exec("echo test")


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Test VM deletion and cleanup."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_success(self, mock_run, azure_provider):
        """Test VM deletion success."""
        azure_provider.vm_name = "test-vm"
        mock_run.return_value = Mock(returncode=0)

        await azure_provider.cleanup()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "az" in args
        assert "vm" in args
        assert "delete" in args
        assert "test-vm" in args

    async def test_cleanup_preserve_on_error(self, azure_provider, capsys):
        """Test VM deletion when preserve_on_error=True and error occurred."""
        azure_provider.vm_name = "test-vm"
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = Path("/tmp/key")
        azure_provider._error_occurred = True
        azure_provider.azure_config.preserve_on_error = True

        await azure_provider.cleanup()

        # VM should be preserved, message printed
        captured = capsys.readouterr()
        assert "VM preserved" in captured.out or "test-vm" in str(azure_provider.vm_name)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_auto_shutdown_false(self, mock_run, azure_provider, capsys):
        """Test VM deletion when auto_shutdown=False."""
        azure_provider.vm_name = "test-vm"
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = Path("/tmp/key")
        azure_provider.azure_config.auto_shutdown = False

        await azure_provider.cleanup()

        # VM should be preserved
        mock_run.assert_not_called()

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_force(self, mock_run, azure_provider):
        """Test forced cleanup ignores preserve settings."""
        azure_provider.vm_name = "test-vm"
        azure_provider._error_occurred = True
        azure_provider.azure_config.preserve_on_error = True
        mock_run.return_value = Mock(returncode=0)

        await azure_provider.cleanup(force=True)

        # VM should be deleted despite preserve_on_error
        mock_run.assert_called_once()

    async def test_cleanup_no_vm(self, azure_provider):
        """Test cleanup when no VM exists."""
        azure_provider.vm_name = None

        # Should not raise
        await azure_provider.cleanup()

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_deletes_ssh_client(self, mock_run, azure_provider):
        """Test cleanup closes SSH client."""
        azure_provider.vm_name = "test-vm"
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client
        mock_run.return_value = Mock(returncode=0)

        await azure_provider.cleanup()

        mock_client.close.assert_called_once()


# ============================================================================
# Setup Method Tests
# ============================================================================


class TestSetup:
    """Test full setup flow."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    async def test_setup_success(self, mock_time, mock_ssh_client, mock_run, azure_provider):
        """Test full setup flow (create VM, wait SSH, get IP)."""
        # Mock ssh-keygen, resource group show, vm create, vm show
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show (note: quoted string in JSON)
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await azure_provider.setup()

        assert azure_provider.vm_name == "mcpbr-eval-1234567890"
        assert azure_provider.vm_ip == "1.2.3.4"
        assert azure_provider.ssh_client is not None

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    async def test_setup_failure_rolls_back(self, mock_time, mock_run, azure_provider):
        """Test setup failure rolls back VM creation."""
        # Mock ssh-keygen success, resource group show, VM creation success, IP retrieval failure
        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=1, stderr="VM not found"),  # az vm show (failure)
        ]

        with pytest.raises(RuntimeError, match="Failed to get VM IP"):
            await azure_provider.setup()

        # VM should still have name for cleanup
        assert azure_provider.vm_name == "mcpbr-eval-1234567890"

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    async def test_setup_with_existing_ssh_key(
        self, mock_ssh_client, mock_run, azure_provider, tmp_path
    ):
        """Test setup with existing SSH key."""
        ssh_key = tmp_path / "existing_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create (no ssh-keygen)
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await azure_provider.setup()

        # Verify ssh-keygen was NOT called
        assert all("ssh-keygen" not in str(call) for call in mock_run.call_args_list)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    async def test_setup_with_generated_ssh_key(self, mock_ssh_client, mock_run, azure_provider):
        """Test setup with generated SSH key."""
        # No SSH key configured
        azure_provider.azure_config.ssh_key_path = None

        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        await azure_provider.setup()

        # Verify ssh-keygen was called
        ssh_keygen_call = mock_run.call_args_list[0]
        assert "ssh-keygen" in str(ssh_keygen_call)
        assert azure_provider.ssh_key_path is not None


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test Azure health checks."""

    @patch("mcpbr.infrastructure.azure_health.run_azure_health_checks")
    async def test_health_check_success(self, mock_health_check, azure_provider):
        """Test health check delegates to azure_health module."""
        mock_health_check.return_value = {
            "healthy": True,
            "checks": [],
            "failures": [],
        }

        result = await azure_provider.health_check()

        assert result["healthy"] is True
        mock_health_check.assert_called_once_with(azure_provider.azure_config)

    @patch("mcpbr.infrastructure.azure_health.run_azure_health_checks")
    async def test_health_check_failure(self, mock_health_check, azure_provider):
        """Test health check with failures."""
        mock_health_check.return_value = {
            "healthy": False,
            "checks": [],
            "failures": ["az CLI not found"],
        }

        result = await azure_provider.health_check()

        assert result["healthy"] is False
        assert len(result["failures"]) > 0


# ============================================================================
# Not Yet Implemented Tests
# ============================================================================


class TestNotYetImplemented:
    """Test methods not yet implemented in Phase 3."""

    async def test_run_evaluation_not_implemented(self, azure_provider):
        """Test run_evaluation raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Phase 4"):
            await azure_provider.run_evaluation(None, True, True)

    async def test_collect_artifacts_not_implemented(self, azure_provider):
        """Test collect_artifacts raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Phase 5"):
            await azure_provider.collect_artifacts(Path("/tmp"))
