"""Tests for infrastructure configuration models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from mcpbr.config import AzureConfig, HarnessConfig, InfrastructureConfig, MCPServerConfig


class TestInfrastructureConfig:
    """Tests for InfrastructureConfig model."""

    def test_infrastructure_config_default_mode(self) -> None:
        """Test InfrastructureConfig with default mode (local)."""
        config = InfrastructureConfig()
        assert config.mode == "local"
        assert config.azure is None

    def test_infrastructure_config_local_mode(self) -> None:
        """Test InfrastructureConfig with explicit local mode."""
        config = InfrastructureConfig(mode="local")
        assert config.mode == "local"
        assert config.azure is None

    def test_infrastructure_config_azure_mode_with_config(self) -> None:
        """Test InfrastructureConfig with azure mode and config."""
        azure_config = AzureConfig(resource_group="test-rg")
        config = InfrastructureConfig(mode="azure", azure=azure_config)
        assert config.mode == "azure"
        assert config.azure is not None
        assert config.azure.resource_group == "test-rg"

    def test_infrastructure_config_azure_mode_without_config_fails(self) -> None:
        """Test InfrastructureConfig with azure mode but no config fails."""
        with pytest.raises(ValidationError, match="azure"):
            InfrastructureConfig(mode="azure")

    def test_infrastructure_config_invalid_mode(self) -> None:
        """Test InfrastructureConfig with invalid mode fails."""
        with pytest.raises(ValidationError):
            InfrastructureConfig(mode="invalid")


class TestAzureConfig:
    """Tests for AzureConfig model."""

    def test_azure_config_minimal(self) -> None:
        """Test AzureConfig with only required fields."""
        config = AzureConfig(resource_group="test-rg")
        assert config.resource_group == "test-rg"
        assert config.location == "eastus"  # default
        assert config.cpu_cores == 8  # default
        assert config.memory_gb == 32  # default
        assert config.disk_gb == 250  # default
        assert config.auto_shutdown is True  # default
        assert config.preserve_on_error is True  # default
        assert config.env_keys_to_export == ["ANTHROPIC_API_KEY"]  # default
        assert config.vm_size is None  # default
        assert config.ssh_key_path is None  # default
        assert config.python_version == "3.11"  # default

    def test_azure_config_all_fields(self) -> None:
        """Test AzureConfig with all fields specified."""
        config = AzureConfig(
            resource_group="my-rg",
            location="westus2",
            vm_size="Standard_D4s_v3",
            cpu_cores=4,
            memory_gb=16,
            disk_gb=100,
            auto_shutdown=False,
            preserve_on_error=False,
            env_keys_to_export=["API_KEY", "SECRET"],
            ssh_key_path=Path("/path/to/key"),
            python_version="3.12",
        )
        assert config.resource_group == "my-rg"
        assert config.location == "westus2"
        assert config.vm_size == "Standard_D4s_v3"
        assert config.cpu_cores == 4
        assert config.memory_gb == 16
        assert config.disk_gb == 100
        assert config.auto_shutdown is False
        assert config.preserve_on_error is False
        assert config.env_keys_to_export == ["API_KEY", "SECRET"]
        assert config.ssh_key_path == Path("/path/to/key")
        assert config.python_version == "3.12"

    def test_azure_config_resource_group_validation_valid(self) -> None:
        """Test resource_group validation with valid names."""
        valid_names = [
            "test-rg",
            "test_rg",
            "TestRG123",
            "my-test_rg-123",
        ]
        for name in valid_names:
            config = AzureConfig(resource_group=name)
            assert config.resource_group == name

    def test_azure_config_resource_group_validation_invalid(self) -> None:
        """Test resource_group validation with invalid names."""
        invalid_names = [
            "test rg",  # spaces
            "test@rg",  # special chars
            "test.rg",  # dots
            "test/rg",  # slashes
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError, match="resource_group"):
                AzureConfig(resource_group=name)

    def test_azure_config_location_validation_valid(self) -> None:
        """Test location validation with valid Azure regions."""
        valid_locations = [
            "eastus",
            "westus2",
            "northeurope",
            "southeastasia",
            "uksouth",
        ]
        for location in valid_locations:
            config = AzureConfig(resource_group="test-rg", location=location)
            assert config.location == location

    def test_azure_config_location_validation_invalid(self) -> None:
        """Test location validation with invalid regions."""
        with pytest.raises(ValidationError, match="location"):
            AzureConfig(resource_group="test-rg", location="invalid-region")

    def test_azure_config_cpu_cores_validation_valid(self) -> None:
        """Test cpu_cores validation with valid values."""
        for cores in [1, 2, 4, 8, 16, 32]:
            config = AzureConfig(resource_group="test-rg", cpu_cores=cores)
            assert config.cpu_cores == cores

    def test_azure_config_cpu_cores_validation_invalid(self) -> None:
        """Test cpu_cores validation with invalid values."""
        with pytest.raises(ValidationError, match="cpu_cores"):
            AzureConfig(resource_group="test-rg", cpu_cores=0)
        with pytest.raises(ValidationError, match="cpu_cores"):
            AzureConfig(resource_group="test-rg", cpu_cores=-1)

    def test_azure_config_memory_gb_validation_valid(self) -> None:
        """Test memory_gb validation with valid values."""
        for memory in [1, 2, 4, 8, 16, 32, 64]:
            config = AzureConfig(resource_group="test-rg", memory_gb=memory)
            assert config.memory_gb == memory

    def test_azure_config_memory_gb_validation_invalid(self) -> None:
        """Test memory_gb validation with invalid values."""
        with pytest.raises(ValidationError, match="memory_gb"):
            AzureConfig(resource_group="test-rg", memory_gb=0)
        with pytest.raises(ValidationError, match="memory_gb"):
            AzureConfig(resource_group="test-rg", memory_gb=-1)

    def test_azure_config_disk_gb_validation_valid(self) -> None:
        """Test disk_gb validation with valid values."""
        for disk in [30, 50, 100, 250, 500, 1000]:
            config = AzureConfig(resource_group="test-rg", disk_gb=disk)
            assert config.disk_gb == disk

    def test_azure_config_disk_gb_validation_invalid_too_small(self) -> None:
        """Test disk_gb validation with too small values."""
        with pytest.raises(ValidationError, match="disk_gb"):
            AzureConfig(resource_group="test-rg", disk_gb=29)
        with pytest.raises(ValidationError, match="disk_gb"):
            AzureConfig(resource_group="test-rg", disk_gb=0)

    def test_azure_config_env_keys_to_export_validation_valid(self) -> None:
        """Test env_keys_to_export validation with valid values."""
        config = AzureConfig(
            resource_group="test-rg",
            env_keys_to_export=["KEY1", "KEY2", "KEY3"],
        )
        assert config.env_keys_to_export == ["KEY1", "KEY2", "KEY3"]

    def test_azure_config_env_keys_to_export_validation_invalid(self) -> None:
        """Test env_keys_to_export validation with invalid values."""
        with pytest.raises(ValidationError):
            AzureConfig(
                resource_group="test-rg",
                env_keys_to_export=["KEY1", 123, "KEY2"],  # type: ignore
            )


class TestHarnessConfigWithInfrastructure:
    """Tests for HarnessConfig with infrastructure field."""

    def test_harness_config_without_infrastructure_field(self) -> None:
        """Test HarnessConfig without infrastructure field (backward compatibility)."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            )
        )
        # Should have default infrastructure config
        assert config.infrastructure.mode == "local"
        assert config.infrastructure.azure is None

    def test_harness_config_with_local_infrastructure(self) -> None:
        """Test HarnessConfig with explicit local infrastructure."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            ),
            infrastructure=InfrastructureConfig(mode="local"),
        )
        assert config.infrastructure.mode == "local"
        assert config.infrastructure.azure is None

    def test_harness_config_with_azure_infrastructure(self) -> None:
        """Test HarnessConfig with Azure infrastructure."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            ),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(resource_group="test-rg"),
            ),
        )
        assert config.infrastructure.mode == "azure"
        assert config.infrastructure.azure is not None
        assert config.infrastructure.azure.resource_group == "test-rg"

    def test_harness_config_with_nested_azure_config(self) -> None:
        """Test HarnessConfig with nested Azure configuration."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            ),
            infrastructure=InfrastructureConfig(
                mode="azure",
                azure=AzureConfig(
                    resource_group="prod-rg",
                    location="westus2",
                    cpu_cores=16,
                    memory_gb=64,
                    disk_gb=500,
                    auto_shutdown=False,
                ),
            ),
        )
        assert config.infrastructure.mode == "azure"
        assert config.infrastructure.azure.resource_group == "prod-rg"
        assert config.infrastructure.azure.location == "westus2"
        assert config.infrastructure.azure.cpu_cores == 16
        assert config.infrastructure.azure.memory_gb == 64
        assert config.infrastructure.azure.disk_gb == 500
        assert config.infrastructure.azure.auto_shutdown is False

    def test_harness_config_with_task_ids(self) -> None:
        """Test HarnessConfig with task_ids for remote forwarding (#367)."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=[]),
            task_ids=["sympy__sympy-11400", "django__django-16379"],
        )
        assert config.task_ids == ["sympy__sympy-11400", "django__django-16379"]

    def test_harness_config_task_ids_default_none(self) -> None:
        """Test HarnessConfig task_ids defaults to None."""
        config = HarnessConfig(mcp_server=MCPServerConfig(command="npx", args=[]))
        assert config.task_ids is None

    def test_azure_config_quota_check_timeout(self) -> None:
        """Test AzureConfig quota_check_timeout field (#375)."""
        config = AzureConfig(resource_group="test-rg", quota_check_timeout=180)
        assert config.quota_check_timeout == 180

    def test_azure_config_quota_check_timeout_default(self) -> None:
        """Test AzureConfig quota_check_timeout defaults to 120."""
        config = AzureConfig(resource_group="test-rg")
        assert config.quota_check_timeout == 120
