# Azure Infrastructure Provider

The Azure infrastructure provider enables automated benchmark evaluation on Azure Virtual Machines.

## Features

- **Zero Manual Setup**: VM provisioned automatically from config
- **Reproducible**: Same config = same environment every time
- **Auto-validation**: Test task ensures setup works before full evaluation
- **Cost Control**: Automatic VM deletion after evaluation
- **Debugging**: Preserve VM on error for troubleshooting

## Prerequisites

1. **Azure CLI** installed: `curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`
2. **Azure Account** with active subscription
3. **Authentication**: `az login`
4. **Permissions**: Ability to create VMs, resource groups

## Configuration

### Minimal Example

```yaml
infrastructure:
  mode: azure
  azure:
    resource_group: mcpbr-benchmarks
    location: eastus

mcp_server:
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

benchmark: swe-bench-lite
sample_size: 10
```

### Full Configuration

```yaml
infrastructure:
  mode: azure
  azure:
    # Required
    resource_group: mcpbr-benchmarks
    location: eastus

    # VM Sizing (Option 1: Automatic mapping)
    cpu_cores: 10
    memory_gb: 40
    disk_gb: 300

    # VM Sizing (Option 2: Direct size)
    # vm_size: Standard_D8s_v3

    # Lifecycle
    auto_shutdown: true
    preserve_on_error: true

    # Environment
    env_keys_to_export:
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY
    python_version: "3.11"

    # SSH
    ssh_key_path: ~/.ssh/mcpbr_azure  # optional, auto-generated if not provided

benchmark: swe-bench-lite
max_concurrent: 10
timeout_seconds: 600
```

## Usage

### Basic Evaluation

```bash
mcpbr run -c azure-config.yaml
```

This will:
1. Provision Azure VM (~2-3 minutes)
2. Install Docker, Python, mcpbr (~3-5 minutes)
3. Run test task to validate setup (~1-2 minutes)
4. Execute full evaluation
5. Download results and create ZIP archive
6. Delete VM automatically

### MCP-Only Evaluation

```bash
mcpbr run -c azure-config.yaml -M
```

### Preserve VM for Debugging

Set in config:
```yaml
infrastructure:
  azure:
    preserve_on_error: true
```

If evaluation fails, VM is kept and SSH command is printed:
```text
VM preserved: mcpbr-eval-1234567890
SSH: ssh -i ~/.ssh/mcpbr_azure azureuser@20.30.40.50
Delete with: az vm delete -g mcpbr-benchmarks -n mcpbr-eval-1234567890 --yes
```

## VM Size Mapping

CPU/Memory automatically maps to Azure VM sizes:

| Cores | Memory | VM Size | $/hour (East US) |
| ------- | -------- | --------- | ------------------ |
| 2 | 8GB | Standard_D2s_v3 | $0.096 |
| 4 | 16GB | Standard_D4s_v3 | $0.192 |
| 8 | 32GB | Standard_D8s_v3 | $0.384 |
| 16 | 64GB | Standard_D16s_v3 | $0.768 |
| 32 | 128GB | Standard_D32s_v3 | $1.536 |

Or specify directly:
```yaml
vm_size: Standard_E8s_v3  # 8 cores, 64GB RAM
```

## Cost Estimation

Example: 100 tasks, 10 minutes each, 8 concurrent workers:
- Runtime: ~125 minutes (100/8 * 10 + 5 setup)
- VM Cost: ~$0.80 (Standard_D8s_v3 @ $0.384/hr * 2.08 hrs)
- API Cost: Depends on model and task complexity

## Troubleshooting

### VM Creation Fails

```bash
# Check authentication
az account show

# Check subscription
az account list --output table

# Check quotas
az vm list-usage --location eastus --output table
```

### SSH Connection Fails

- Wait 1-2 minutes for VM to boot fully
- Check Azure firewall rules allow SSH (port 22)
- Verify SSH key exists: `ls -la ~/.ssh/mcpbr_azure*`

### Test Task Fails

Common causes:
- MCP server command incorrect
- Missing environment variables
- Docker daemon not started (wait 30s after install)

Solution: Set `preserve_on_error: true`, SSH into VM, debug manually

### Evaluation Hangs

- Check Azure portal for VM status
- SSH into VM: `ssh -i ~/.ssh/mcpbr_azure azureuser@<VM_IP>`
- Check logs: `tail -f ~/.mcpbr_run_*/logs/*.log`

## Cleanup

### Manual Cleanup

If VMs are preserved:
```bash
# List VMs
az vm list --resource-group mcpbr-benchmarks --output table

# Delete specific VM
az vm delete -g mcpbr-benchmarks -n mcpbr-eval-1234567890 --yes

# Delete all mcpbr VMs
az vm list -g mcpbr-benchmarks --query "[?starts_with(name, 'mcpbr-eval-')].name" -o tsv | xargs -I {} az vm delete -g mcpbr-benchmarks -n {} --yes
```

### Cleanup Resource Group

```bash
az group delete -n mcpbr-benchmarks --yes
```

## Limitations

- **Region-specific**: VM must be created in region with available quota
- **SSH-based**: Requires outbound SSH (port 22) access
- **Single VM**: Currently only supports one VM per evaluation (no distribution)
- **Docker Required**: Cannot evaluate benchmarks requiring nested virtualization

## Future Enhancements

See related issues:
- #352: AWS EC2 provider
- #353: GCP Compute Engine provider
- #355: Kubernetes provider (distributed evaluation)
