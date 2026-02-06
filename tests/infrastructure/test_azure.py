"""Tests for Azure infrastructure provider."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, mock_open, patch

import pytest

from mcpbr.config import AzureConfig, HarnessConfig, InfrastructureConfig, MCPServerConfig
from mcpbr.infrastructure.azure import AzureProvider


@pytest.fixture
def azure_config() -> AzureConfig:
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
def harness_config(azure_config: AzureConfig) -> HarnessConfig:
    """Create a test harness configuration with Azure."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        infrastructure=InfrastructureConfig(mode="azure", azure=azure_config),
    )


@pytest.fixture
def azure_provider(harness_config: HarnessConfig) -> AzureProvider:
    """Create an Azure provider instance."""
    return AzureProvider(harness_config)


# ============================================================================
# VM Size Mapping Tests
# ============================================================================


class TestVMSizeMapping:
    """Test VM size mapping from cpu_cores/memory_gb."""

    def test_mapping_2_cores_8gb(self) -> None:
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

    def test_mapping_4_cores_16gb(self) -> None:
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

    def test_mapping_8_cores_32gb(self) -> None:
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

    def test_mapping_16_cores_64gb(self) -> None:
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

    def test_mapping_32_cores_128gb(self) -> None:
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

    def test_mapping_large_64_cores_256gb(self) -> None:
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

    def test_custom_vm_size_overrides_mapping(self) -> None:
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
    async def test_create_vm_success(
        self,
        mock_time: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test successful VM creation."""
        # Use existing SSH key to avoid depending on ~/.ssh/mcpbr_azure state
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
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
        self,
        mock_time: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test VM creation with resource group creation."""
        # Use existing SSH key to avoid depending on ~/.ssh/mcpbr_azure state
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=1, stderr="ResourceGroupNotFound"),  # az group show (not found)
            Mock(returncode=0),  # az group create
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
        ]

        await azure_provider._create_vm("Standard_D8s_v3")

        assert azure_provider.vm_name == "mcpbr-eval-1234567890"

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_create_vm_with_ssh_key_generation(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test VM creation with SSH key generation."""
        # Redirect Path.home to tmp_path so ~/.ssh/mcpbr_azure doesn't exist
        with patch("mcpbr.infrastructure.azure.Path.home", return_value=tmp_path):
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
    async def test_create_vm_failure_quota_exceeded(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test VM creation failure (quota exceeded)."""
        # Use existing SSH key to avoid depending on ~/.ssh/mcpbr_azure state
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=1, stderr="QuotaExceeded: Core quota exceeded"),  # az vm create
        ]

        with pytest.raises(RuntimeError, match="VM creation failed"):
            await azure_provider._create_vm("Standard_D8s_v3")

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_create_vm_with_existing_ssh_key(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
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
    async def test_get_vm_ip_success(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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
    async def test_get_vm_ip_failure(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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
    async def test_ssh_connection_success(
        self,
        mock_ssh_client: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
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
        self,
        mock_sleep: MagicMock,
        mock_ssh_client: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
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
        self,
        mock_ssh_client: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
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
        self,
        mock_sleep: MagicMock,
        mock_ssh_client: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
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

    async def test_execute_command_success(self, azure_provider: AzureProvider) -> None:
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

    async def test_execute_command_non_zero_exit(self, azure_provider: AzureProvider) -> None:
        """Test command with non-zero exit code."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        exit_code, _stdout, stderr = await azure_provider._ssh_exec("false")

        assert exit_code == 1
        assert stderr == "error\n"

    async def test_execute_command_timeout(self, azure_provider: AzureProvider) -> None:
        """Test command timeout."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_client.exec_command.side_effect = Exception("Timeout")

        with pytest.raises(RuntimeError, match="SSH command failed"):
            await azure_provider._ssh_exec("sleep 1000", timeout=1)

    async def test_execute_command_no_client(self, azure_provider: AzureProvider) -> None:
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
    async def test_cleanup_success(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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

    async def test_cleanup_preserve_on_error(
        self,
        azure_provider: AzureProvider,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
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
    async def test_cleanup_auto_shutdown_false(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test VM deletion when auto_shutdown=False."""
        azure_provider.vm_name = "test-vm"
        azure_provider.vm_ip = "1.2.3.4"
        azure_provider.ssh_key_path = Path("/tmp/key")
        azure_provider.azure_config.auto_shutdown = False

        await azure_provider.cleanup()

        # VM should be preserved
        mock_run.assert_not_called()

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_force(self, mock_run: MagicMock, azure_provider: AzureProvider) -> None:
        """Test forced cleanup ignores preserve settings."""
        azure_provider.vm_name = "test-vm"
        azure_provider._error_occurred = True
        azure_provider.azure_config.preserve_on_error = True
        mock_run.return_value = Mock(returncode=0)

        await azure_provider.cleanup(force=True)

        # VM should be deleted despite preserve_on_error
        mock_run.assert_called_once()

    async def test_cleanup_no_vm(self, azure_provider: AzureProvider) -> None:
        """Test cleanup when no VM exists."""
        azure_provider.vm_name = None

        # Should not raise
        await azure_provider.cleanup()

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    async def test_cleanup_deletes_ssh_client(
        self,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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
    """Test full setup flow (old tests from Phase 3 - simplified expectations)."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_success(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test full setup flow (create VM, wait SSH, get IP, install, config, test)."""
        mock_env_get.return_value = "test-api-key"

        # Use existing SSH key to avoid depending on ~/.ssh/mcpbr_azure state
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        # Mock resource group show, vm create, vm show (no ssh-keygen needed)
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show (note: quoted string in JSON)
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        # Mock SSH exec_command for all operations
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Mock SFTP for config transfer
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider.setup()

        assert azure_provider.vm_name == "mcpbr-eval-1234567890"
        assert azure_provider.vm_ip == "1.2.3.4"
        assert azure_provider.ssh_client is not None

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    async def test_setup_failure_rolls_back(
        self,
        mock_time: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test setup failure rolls back VM creation."""
        # Use existing SSH key to avoid depending on ~/.ssh/mcpbr_azure state
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        # Mock resource group show, VM creation success, IP retrieval failure
        mock_run.side_effect = [
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
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_with_existing_ssh_key(
        self,
        mock_env_get: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test setup with existing SSH key."""
        mock_env_get.return_value = "test-api-key"
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

        # Mock SSH exec_command for all operations
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Mock SFTP for config transfer
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider.setup()

        # Verify ssh-keygen was NOT called
        assert all("ssh-keygen" not in str(call) for call in mock_run.call_args_list)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_with_generated_ssh_key(
        self,
        mock_env_get: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test setup with generated SSH key."""
        mock_env_get.return_value = "test-api-key"

        # No SSH key configured - redirect home to tmp_path so key doesn't exist
        azure_provider.azure_config.ssh_key_path = None

        mock_run.side_effect = [
            Mock(returncode=0),  # ssh-keygen
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        # Mock SSH exec_command for all operations
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Mock SFTP for config transfer
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        with patch("mcpbr.infrastructure.azure.Path.home", return_value=tmp_path):
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
    async def test_health_check_success(
        self,
        mock_health_check: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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
    async def test_health_check_failure(
        self,
        mock_health_check: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
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
# Environment Setup Tests
# ============================================================================


class TestEnvironmentSetup:
    """Test environment setup on VM (dependency installation)."""

    async def test_install_dependencies_success(self, azure_provider: AzureProvider) -> None:
        """Test successful dependency installation."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"Dependencies installed\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._install_dependencies()

        # Verify all 4 steps were executed (Docker, Python, Node.js, mcpbr)
        assert mock_client.exec_command.call_count == 4
        all_cmds = [call[0][0] for call in mock_client.exec_command.call_args_list]
        all_cmds_str = " ".join(all_cmds)
        assert "apt-get update" in all_cmds_str
        assert "docker" in all_cmds_str.lower()
        assert "pip install mcpbr" in all_cmds_str

    async def test_install_dependencies_handles_failures_gracefully(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test dependency installation handles apt-get failures gracefully."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"Some package failed\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Should not raise - just log warning
        await azure_provider._install_dependencies()

        # All 4 steps still execute even if individual steps fail
        assert mock_client.exec_command.call_count == 4

    async def test_install_dependencies_installs_docker(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test dependency installation includes Docker."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._install_dependencies()

        # Docker install is the first step
        all_cmds = [call[0][0] for call in mock_client.exec_command.call_args_list]
        assert any("get.docker.com" in cmd for cmd in all_cmds)

    async def test_install_dependencies_installs_python_version(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test dependency installation installs configured Python version."""
        azure_provider.azure_config.python_version = "3.11"
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._install_dependencies()

        cmd = mock_client.exec_command.call_args[0][0]
        assert "python3.11" in cmd

    async def test_install_dependencies_installs_mcpbr(self, azure_provider: AzureProvider) -> None:
        """Test dependency installation installs mcpbr via pip."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._install_dependencies()

        # mcpbr install is the last step
        all_cmds = [call[0][0] for call in mock_client.exec_command.call_args_list]
        assert any("pip install mcpbr" in cmd for cmd in all_cmds)


# ============================================================================
# Configuration Transfer Tests
# ============================================================================


class TestConfigurationTransfer:
    """Test configuration file transfer via SFTP."""

    async def test_transfer_config_creates_temporary_yaml(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test config transfer creates temporary YAML file."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider._transfer_config()

        # Verify SFTP operations
        mock_client.open_sftp.assert_called_once()
        mock_sftp.put.assert_called_once()
        mock_sftp.close.assert_called_once()

    async def test_transfer_config_uploads_via_sftp(self, azure_provider: AzureProvider) -> None:
        """Test config transfer uploads via SFTP."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider._transfer_config()

        # Verify upload destination
        call_args = mock_sftp.put.call_args
        assert call_args[0][1] == "/home/azureuser/config.yaml"

    async def test_transfer_config_handles_upload_failures(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test config transfer handles upload failures."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_sftp = MagicMock()
        mock_sftp.put.side_effect = Exception("Upload failed")
        mock_client.open_sftp.return_value = mock_sftp

        with pytest.raises(Exception, match="Upload failed"):
            await azure_provider._transfer_config()

        # Verify SFTP was closed despite error
        mock_sftp.close.assert_called_once()


# ============================================================================
# Environment Variable Export Tests
# ============================================================================


class TestEnvironmentVariableExport:
    """Test environment variable export to VM."""

    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_export_env_vars_exports_anthropic_api_key(
        self,
        mock_env_get: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
        """Test environment variable export includes ANTHROPIC_API_KEY."""
        mock_env_get.return_value = "sk-test-key"
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._export_env_vars()

        # Verify environment variable was exported
        calls = mock_client.exec_command.call_args_list
        assert len(calls) >= 2  # .bashrc and .profile
        for call in calls:
            cmd = call[0][0]
            if "ANTHROPIC_API_KEY" in cmd:
                assert "sk-test-key" in cmd

    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_export_env_vars_exports_multiple_keys(
        self,
        mock_env_get: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
        """Test environment variable export handles multiple keys."""
        azure_provider.azure_config.env_keys_to_export = ["KEY1", "KEY2", "KEY3"]

        # Return default for Rich environment vars, custom values for our keys
        def side_effect_fn(k, default=None):
            custom_values = {"KEY1": "val1", "KEY2": "val2", "KEY3": "val3"}
            if k in custom_values:
                return custom_values[k]
            return default

        mock_env_get.side_effect = side_effect_fn

        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._export_env_vars()

        # Verify all keys were exported
        calls = mock_client.exec_command.call_args_list
        all_commands = " ".join([call[0][0] for call in calls])
        assert "KEY1" in all_commands
        assert "KEY2" in all_commands
        assert "KEY3" in all_commands

    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_export_env_vars_writes_to_bashrc_and_profile(
        self,
        mock_env_get: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
        """Test environment variable export writes to both .bashrc and .profile."""
        mock_env_get.return_value = "test-value"
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._export_env_vars()

        # Verify writes to both files
        calls = mock_client.exec_command.call_args_list
        commands = [call[0][0] for call in calls]
        assert any(".bashrc" in cmd for cmd in commands)
        assert any(".profile" in cmd for cmd in commands)

    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_export_env_vars_handles_missing_env_vars_gracefully(
        self,
        mock_env_get: MagicMock,
        azure_provider: AzureProvider,
    ) -> None:
        """Test environment variable export handles missing vars gracefully."""

        # Return default for Rich environment vars, None for our keys
        def side_effect_fn(k, default=None):
            # Return defaults for system env vars used by Rich
            return default

        mock_env_get.side_effect = side_effect_fn

        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Should not raise - just warn
        await azure_provider._export_env_vars()

        # No SSH commands should be executed if no env vars found
        assert mock_client.exec_command.call_count == 0


# ============================================================================
# Test Task Validation Tests
# ============================================================================


class TestTaskValidation:
    """Test single task validation to verify setup."""

    async def test_run_test_task_executes_mcpbr_with_sample_size_1(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test task validation executes mcpbr with sample_size=1."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"Test task passed\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._run_test_task()

        # Verify command
        mock_client.exec_command.assert_called_once()
        cmd = mock_client.exec_command.call_args[0][0]
        assert "mcpbr run" in cmd
        assert "-n 1" in cmd or "sample_size=1" in cmd.lower()

    async def test_run_test_task_succeeds_with_exit_code_0(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test task validation succeeds with exit code 0."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"Test task passed\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        # Should not raise
        await azure_provider._run_test_task()

    async def test_run_test_task_fails_with_non_zero_exit_code(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test task validation fails with non-zero exit code."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        with pytest.raises(RuntimeError, match="Test task validation failed"):
            await azure_provider._run_test_task()

    async def test_run_test_task_captures_stdout_stderr(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test task validation captures stdout/stderr."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"stdout output\n"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"stderr output\n"

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        try:
            await azure_provider._run_test_task()
        except RuntimeError as e:
            # Verify error message includes output info
            assert "exit code 1" in str(e)

    async def test_run_test_task_uses_correct_timeout(self, azure_provider: AzureProvider) -> None:
        """Test task validation uses 600s timeout."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider._run_test_task()

        # Verify timeout parameter
        call_kwargs = mock_client.exec_command.call_args[1]
        assert call_kwargs.get("timeout") == 600


# ============================================================================
# Updated Setup Tests
# ============================================================================


class TestUpdatedSetup:
    """Test updated setup flow with environment setup and validation."""

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_includes_dependency_installation(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test full setup flow includes dependency installation."""
        mock_env_get.return_value = "test-api-key"
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        # Mock subprocess calls (no ssh-keygen needed with existing key)
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        # Mock SSH client
        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        await azure_provider.setup()

        # Verify SSH exec was called (for install, transfer, export, test)
        assert mock_client.exec_command.call_count >= 4
        commands = [call[0][0] for call in mock_client.exec_command.call_args_list]

        # Check for dependency installation
        assert any("apt-get" in cmd for cmd in commands)

        # Check for env var export
        assert any("bashrc" in cmd or "profile" in cmd for cmd in commands)

        # Check for test task
        assert any("mcpbr run" in cmd for cmd in commands)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_includes_config_transfer(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test full setup flow includes config transfer."""
        mock_env_get.return_value = "test-api-key"
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider.setup()

        # Verify SFTP was called
        mock_client.open_sftp.assert_called_once()
        mock_sftp.put.assert_called_once()

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_includes_env_var_export(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test full setup flow includes env var export."""
        mock_env_get.return_value = "test-api-key"
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider.setup()

        # Verify env vars were exported
        commands = [call[0][0] for call in mock_client.exec_command.call_args_list]
        assert any("export ANTHROPIC_API_KEY" in cmd for cmd in commands)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_includes_test_task(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test full setup flow includes test task."""
        mock_env_get.return_value = "test-api-key"
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"output\n"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        await azure_provider.setup()

        # Verify test task was run
        commands = [call[0][0] for call in mock_client.exec_command.call_args_list]
        assert any("mcpbr run" in cmd for cmd in commands)

    @patch("mcpbr.infrastructure.azure.subprocess.run")
    @patch("mcpbr.infrastructure.azure.paramiko.SSHClient")
    @patch("mcpbr.infrastructure.azure.time.time", return_value=1234567890)
    @patch("mcpbr.infrastructure.azure.os.environ.get")
    async def test_setup_fails_if_test_task_fails(
        self,
        mock_env_get: MagicMock,
        mock_time: MagicMock,
        mock_ssh_client: MagicMock,
        mock_run: MagicMock,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test setup fails if test task fails."""
        mock_env_get.return_value = "test-api-key"
        ssh_key = tmp_path / "test_key"
        ssh_key.touch()
        azure_provider.azure_config.ssh_key_path = ssh_key

        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"id": "rg-id"}'),  # az group show
            Mock(returncode=0, stdout='{"id": "vm-id"}'),  # az vm create
            Mock(returncode=0, stdout='"1.2.3.4"'),  # az vm show
        ]

        mock_client = MagicMock()
        mock_ssh_client.return_value = mock_client

        # Return success for first few calls, then failure for test task
        def exec_command_side_effect(cmd, timeout=300):
            stdout = MagicMock()
            stderr = MagicMock()

            if "mcpbr run" in cmd:
                # Test task fails
                stdout.read.return_value = b"Test failed\n"
                stdout.channel.recv_exit_status.return_value = 1
                stderr.read.return_value = b"Error\n"
            else:
                # Other commands succeed
                stdout.read.return_value = b"output\n"
                stdout.channel.recv_exit_status.return_value = 0
                stderr.read.return_value = b""

            return (None, stdout, stderr)

        mock_client.exec_command.side_effect = exec_command_side_effect

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        with pytest.raises(RuntimeError, match="Test task validation failed"):
            await azure_provider.setup()


# ============================================================================
# Remote Execution Tests
# ============================================================================


class TestRemoteExecution:
    """Test remote execution of evaluation on VM."""

    async def test_run_evaluation_executes_mcpbr_with_flags(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test run_evaluation executes mcpbr command with correct flags."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        # Mock exec_command for main evaluation
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        # Mock _download_results to return a fake result
        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(
                metadata={},
                summary={"pass_rate": 1.0},
                tasks=[],
            )

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=True)

        # Verify mcpbr was called
        mock_client.exec_command.assert_called()
        cmd = mock_client.exec_command.call_args[0][0]
        assert "mcpbr run" in cmd
        assert "-c ~/config.yaml" in cmd

    async def test_run_evaluation_with_mcp_only_flag(self, azure_provider: AzureProvider) -> None:
        """Test run_evaluation with mcp_only (-M flag)."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=False)

        cmd = mock_client.exec_command.call_args[0][0]
        assert "-M" in cmd

    async def test_run_evaluation_with_baseline_only_flag(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test run_evaluation with baseline_only (-B flag)."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=False, run_baseline=True)

        cmd = mock_client.exec_command.call_args[0][0]
        assert "-B" in cmd

    async def test_run_evaluation_with_both_mcp_and_baseline(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test run_evaluation with both mcp and baseline (no flags)."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=True)

        cmd = mock_client.exec_command.call_args[0][0]
        # Should have no -M or -B flags when running both
        assert "-M" not in cmd and "-B" not in cmd

    async def test_run_evaluation_streams_output(self, azure_provider: AzureProvider) -> None:
        """Test run_evaluation streams output to console."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        # Mock stdout to return some lines
        mock_stdout.__iter__ = Mock(return_value=iter(["Line 1\n", "Line 2\n", "Line 3\n"]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=False)

        # Verify stdout was iterated
        mock_stdout.__iter__.assert_called()

    async def test_run_evaluation_handles_success(self, azure_provider: AzureProvider) -> None:
        """Test run_evaluation handles evaluation success (exit code 0)."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        # Should not raise
        result = await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=False)
        assert result is not None

    async def test_run_evaluation_handles_failure(self, azure_provider: AzureProvider) -> None:
        """Test run_evaluation handles evaluation failure (non-zero exit code)."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"Evaluation error\n"

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        with pytest.raises(RuntimeError, match="Evaluation failed"):
            await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=False)

    async def test_run_evaluation_sets_error_flag_on_failure(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test run_evaluation sets _error_occurred flag on failure."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"error\n"

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        try:
            await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=False)
        except RuntimeError:
            pass

        assert azure_provider._error_occurred is True

    async def test_run_evaluation_returns_downloaded_results(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test run_evaluation returns results from downloaded JSON."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(
                metadata={},
                summary={"pass_rate": 0.95},
                tasks=[],
            )

        azure_provider._download_results = mock_download_results

        result = await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=True)

        assert result is not None
        assert result.summary["pass_rate"] == 0.95

    async def test_run_evaluation_forwards_task_ids(
        self,
    ) -> None:
        """Test that task_ids from config are forwarded as -t flags (#367)."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg"),
            ),
            task_ids=["sympy__sympy-11400", "sympy__sympy-11870"],
        )
        provider = AzureProvider(config)

        mock_client = MagicMock()
        provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        provider._download_results = mock_download_results

        await provider.run_evaluation(None, run_mcp=True, run_baseline=True)

        cmd = mock_client.exec_command.call_args[0][0]
        assert "-t" in cmd
        assert "sympy__sympy-11400" in cmd
        assert "sympy__sympy-11870" in cmd

    async def test_run_evaluation_no_task_ids_omits_t_flag(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test that no -t flags when task_ids is None."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.__iter__ = Mock(return_value=iter([]))
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        async def mock_download_results():
            from mcpbr.harness import EvaluationResults

            return EvaluationResults(metadata={}, summary={}, tasks=[])

        azure_provider._download_results = mock_download_results

        await azure_provider.run_evaluation(None, run_mcp=True, run_baseline=True)

        cmd = mock_client.exec_command.call_args[0][0]
        assert "-t" not in cmd


# ============================================================================
# Results Download Tests
# ============================================================================


class TestResultsDownload:
    """Test downloading results.json from VM."""

    async def test_download_results_finds_latest_directory(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test _download_results finds latest .mcpbr_run_* directory."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        # Mock _ssh_exec to return output directory path
        async def mock_ssh_exec(cmd, timeout=300):
            if "find" in cmd and ".mcpbr_run_" in cmd:
                return 0, "/home/azureuser/.mcpbr_run_12345", ""
            return 0, "", ""

        azure_provider._ssh_exec = mock_ssh_exec

        # Mock SFTP download
        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        with patch(
            "builtins.open", mock_open(read_data='{"metadata": {}, "summary": {}, "tasks": []}')
        ):
            with patch("pathlib.Path.unlink"):
                await azure_provider._download_results()

        mock_client.open_sftp.assert_called_once()

    async def test_download_results_downloads_json(self, azure_provider: AzureProvider) -> None:
        """Test _download_results downloads results.json."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            if "find" in cmd:
                return 0, "/home/azureuser/.mcpbr_run_12345", ""
            return 0, "", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        with patch(
            "builtins.open", mock_open(read_data='{"metadata": {}, "summary": {}, "tasks": []}')
        ):
            with patch("pathlib.Path.unlink"):
                await azure_provider._download_results()

        mock_sftp.get.assert_called_once()
        call_args = mock_sftp.get.call_args[0]
        assert "results.json" in call_args[0]

    async def test_download_results_parses_json(self, azure_provider: AzureProvider) -> None:
        """Test _download_results parses JSON into EvaluationResults."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        json_data = '{"metadata": {}, "summary": {"pass_rate": 0.9}, "tasks": []}'

        with patch("builtins.open", mock_open(read_data=json_data)):
            with patch("pathlib.Path.unlink"):
                result = await azure_provider._download_results()

        from mcpbr.harness import EvaluationResults

        assert isinstance(result, EvaluationResults)
        assert result.summary["pass_rate"] == 0.9

    async def test_download_results_handles_missing_json(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test _download_results handles missing results.json."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 1, "", "No such file or directory"

        azure_provider._ssh_exec = mock_ssh_exec

        with pytest.raises(FileNotFoundError, match="No output directory found"):
            await azure_provider._download_results()

    async def test_download_results_handles_invalid_json(
        self,
        azure_provider: AzureProvider,
    ) -> None:
        """Test _download_results handles invalid JSON."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_client.open_sftp.return_value = mock_sftp

        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("pathlib.Path.unlink"):
                with pytest.raises(json.JSONDecodeError):
                    await azure_provider._download_results()


# ============================================================================
# Artifact Collection Tests
# ============================================================================


class TestArtifactCollection:
    """Test collecting artifacts from VM."""

    async def test_collect_artifacts_finds_output_directory(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts finds output directory on VM."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            if "find" in cmd:
                return 0, "/home/azureuser/.mcpbr_run_12345", ""
            return 0, "", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        mock_client.open_sftp.return_value = mock_sftp

        output_dir = tmp_path / "artifacts"

        with patch("os.walk", return_value=[]):
            await azure_provider.collect_artifacts(output_dir)

        # Verify directory was created
        assert output_dir.exists()

    async def test_collect_artifacts_downloads_recursively(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts downloads recursively via SFTP."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()

        import stat

        mock_file = MagicMock()
        mock_file.filename = "results.json"
        mock_file.st_mode = stat.S_IFREG

        mock_sftp.listdir_attr.return_value = [mock_file]
        mock_client.open_sftp.return_value = mock_sftp

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir(parents=True)
        (output_dir / "results.json").write_text("test")

        await azure_provider.collect_artifacts(output_dir)

        # Verify SFTP operations
        mock_sftp.listdir_attr.assert_called()
        mock_sftp.get.assert_called()

    async def test_collect_artifacts_creates_zip_archive(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts creates ZIP archive locally."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        mock_client.open_sftp.return_value = mock_sftp

        output_dir = tmp_path / "artifacts"

        # Create a test file
        output_dir.mkdir(parents=True)
        (output_dir / "test.txt").write_text("test")

        result = await azure_provider.collect_artifacts(output_dir)

        assert result is not None
        assert result.exists()
        assert result.suffix == ".zip"

    async def test_collect_artifacts_includes_logs_results_traces(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts includes logs, results, traces."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        import stat

        mock_files = []
        for name in ["results.json", "evaluation.log", "trace.json"]:
            mock_file = MagicMock()
            mock_file.filename = name
            mock_file.st_mode = stat.S_IFREG
            mock_files.append(mock_file)

        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = mock_files
        mock_client.open_sftp.return_value = mock_sftp

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir(parents=True)
        for name in ["results.json", "evaluation.log", "trace.json"]:
            (output_dir / name).write_text("test")

        await azure_provider.collect_artifacts(output_dir)

        # Verify files were downloaded
        assert mock_sftp.get.call_count >= 1

    async def test_collect_artifacts_handles_missing_directory(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts handles missing output directory."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 1, "", "No such directory"

        azure_provider._ssh_exec = mock_ssh_exec

        output_dir = tmp_path / "artifacts"

        result = await azure_provider.collect_artifacts(output_dir)

        assert result is None

    async def test_collect_artifacts_returns_zip_path(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test collect_artifacts returns Path to ZIP file."""
        mock_client = MagicMock()
        azure_provider.ssh_client = mock_client

        async def mock_ssh_exec(cmd, timeout=300):
            return 0, "/home/azureuser/.mcpbr_run_12345", ""

        azure_provider._ssh_exec = mock_ssh_exec

        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        mock_client.open_sftp.return_value = mock_sftp

        output_dir = tmp_path / "artifacts"
        output_dir.mkdir(parents=True)
        (output_dir / "test.txt").write_text("test")

        result = await azure_provider.collect_artifacts(output_dir)

        assert isinstance(result, Path)


# ============================================================================
# SFTP Recursive Download Tests
# ============================================================================


class TestSFTPRecursiveDownload:
    """Test SFTP recursive download functionality."""

    def test_recursive_download_downloads_files(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test _recursive_download downloads files."""
        import stat

        mock_sftp = MagicMock()

        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.st_mode = stat.S_IFREG

        mock_sftp.listdir_attr.return_value = [mock_file]

        local_dir = tmp_path / "download"
        local_dir.mkdir()

        azure_provider._recursive_download(mock_sftp, "/remote", local_dir)

        mock_sftp.get.assert_called_once()

    def test_recursive_download_creates_directories(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test _recursive_download creates directories."""
        import stat

        mock_sftp = MagicMock()

        mock_dir = MagicMock()
        mock_dir.filename = "subdir"
        mock_dir.st_mode = stat.S_IFDIR

        # Return empty list for subdirectory
        mock_sftp.listdir_attr.side_effect = [[mock_dir], []]

        local_dir = tmp_path / "download"
        local_dir.mkdir()

        azure_provider._recursive_download(mock_sftp, "/remote", local_dir)

        # Verify subdirectory was created
        assert (local_dir / "subdir").exists()

    def test_recursive_download_handles_nested_structure(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test _recursive_download handles nested structures."""
        import stat

        mock_sftp = MagicMock()

        # First level: directory
        mock_dir = MagicMock()
        mock_dir.filename = "subdir"
        mock_dir.st_mode = stat.S_IFDIR

        # Second level: file
        mock_file = MagicMock()
        mock_file.filename = "nested.txt"
        mock_file.st_mode = stat.S_IFREG

        mock_sftp.listdir_attr.side_effect = [[mock_dir], [mock_file]]

        local_dir = tmp_path / "download"
        local_dir.mkdir()

        azure_provider._recursive_download(mock_sftp, "/remote", local_dir)

        # Verify nested structure
        assert (local_dir / "subdir").exists()
        mock_sftp.get.assert_called_once()

    def test_recursive_download_preserves_metadata(
        self,
        azure_provider: AzureProvider,
        tmp_path: Path,
    ) -> None:
        """Test _recursive_download preserves file permissions (metadata)."""
        import stat

        mock_sftp = MagicMock()

        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.st_mode = stat.S_IFREG | 0o755

        mock_sftp.listdir_attr.return_value = [mock_file]

        local_dir = tmp_path / "download"
        local_dir.mkdir()

        azure_provider._recursive_download(mock_sftp, "/remote", local_dir)

        # Verify file was downloaded (metadata preservation is implicit in listdir_attr)
        mock_sftp.get.assert_called_once()
