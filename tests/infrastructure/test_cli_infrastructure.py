"""Tests for CLI infrastructure integration."""

from mcpbr.config import load_config


class TestCLIInfrastructure:
    """Test CLI infrastructure mode integration."""

    def test_cli_respects_local_infrastructure_config_parsing(self, tmp_path):
        """Test CLI correctly parses local infrastructure configuration."""
        # Create minimal valid config with local mode
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
infrastructure:
  mode: local

mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

benchmark: swe-bench-lite
sample_size: 1
        """
        )

        # Import and load config to verify parsing
        config = load_config(config_path)

        # Verify infrastructure config was parsed
        assert hasattr(config, "infrastructure")
        assert config.infrastructure is not None
        assert config.infrastructure.mode == "local"

    def test_cli_with_azure_infrastructure_config_parsing(self, tmp_path):
        """Test CLI correctly parses Azure infrastructure configuration."""
        # Create config with infrastructure.mode: azure
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
infrastructure:
  mode: azure
  azure:
    resource_group: test-rg
    location: eastus
    cpu_cores: 4
    memory_gb: 16

mcp_server:
  command: echo
  args: ["test"]

benchmark: swe-bench-lite
sample_size: 1
        """
        )

        # Load config and verify Azure settings
        config = load_config(config_path)

        assert config.infrastructure.mode == "azure"
        assert config.infrastructure.azure is not None
        assert config.infrastructure.azure.resource_group == "test-rg"
        assert config.infrastructure.azure.location == "eastus"
        assert config.infrastructure.azure.cpu_cores == 4
        assert config.infrastructure.azure.memory_gb == 16

    def test_cli_with_azure_infrastructure_env_export(self, tmp_path):
        """Test CLI parses Azure env_keys_to_export configuration."""
        # Create config with Azure-specific settings
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
infrastructure:
  mode: azure
  azure:
    resource_group: test-rg
    location: eastus
    cpu_cores: 4
    memory_gb: 16
    env_keys_to_export:
      - ANTHROPIC_API_KEY
      - CUSTOM_KEY

mcp_server:
  command: echo
  args: ["test"]

benchmark: swe-bench-lite
sample_size: 1
        """
        )

        # Load config and verify Azure settings
        config = load_config(config_path)

        assert config.infrastructure.mode == "azure"
        assert config.infrastructure.azure is not None
        assert config.infrastructure.azure.resource_group == "test-rg"
        assert config.infrastructure.azure.location == "eastus"
        assert "ANTHROPIC_API_KEY" in config.infrastructure.azure.env_keys_to_export
        assert "CUSTOM_KEY" in config.infrastructure.azure.env_keys_to_export

    def test_cli_backward_compatibility_no_infrastructure(self, tmp_path):
        """Test CLI backward compatibility when infrastructure field is missing."""
        # Create config without infrastructure field (old format)
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

benchmark: swe-bench-lite
sample_size: 1
        """
        )

        # Load config - should default to local mode
        config = load_config(config_path)

        # Should have infrastructure with default mode
        assert hasattr(config, "infrastructure")
        # Infrastructure defaults to local mode when not specified
        assert config.infrastructure.mode == "local"

    def test_cli_azure_infrastructure_full_configuration(self, tmp_path):
        """Test CLI parses full Azure configuration with all options."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
infrastructure:
  mode: azure
  azure:
    resource_group: mcpbr-benchmarks
    location: eastus
    cpu_cores: 10
    memory_gb: 40
    disk_gb: 300
    vm_size: Standard_D8s_v3
    auto_shutdown: true
    preserve_on_error: true
    env_keys_to_export:
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY
    python_version: "3.11"
    ssh_key_path: ~/.ssh/mcpbr_azure

mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

benchmark: swe-bench-lite
sample_size: 10
        """
        )

        config = load_config(config_path)

        # Verify all Azure settings
        assert config.infrastructure.mode == "azure"
        azure = config.infrastructure.azure
        assert azure.resource_group == "mcpbr-benchmarks"
        assert azure.location == "eastus"
        assert azure.cpu_cores == 10
        assert azure.memory_gb == 40
        assert azure.disk_gb == 300
        assert azure.vm_size == "Standard_D8s_v3"
        assert azure.auto_shutdown is True
        assert azure.preserve_on_error is True
        assert "ANTHROPIC_API_KEY" in azure.env_keys_to_export
        assert "OPENAI_API_KEY" in azure.env_keys_to_export
        assert azure.python_version == "3.11"
        assert str(azure.ssh_key_path) == "~/.ssh/mcpbr_azure"
