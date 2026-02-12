"""Configuration models and loading for swebench-mcp."""

import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from rich.console import Console

from .config_inheritance import load_config_with_inheritance
from .env_expansion import expand_env_vars, load_dotenv_file, validate_config_security
from .models import DEFAULT_MODEL

VALID_PROVIDERS = ("anthropic", "openai", "gemini", "qwen")
VALID_HARNESSES = ("claude-code",)
VALID_BENCHMARKS = (
    "swe-bench-lite",
    "swe-bench-verified",
    "swe-bench-full",
    "cybergym",
    "gsm8k",
    "humaneval",
    "mcptoolbench",
    "mbpp",
    "math",
    "truthfulqa",
    "bigbench-hard",
    "hellaswag",
    "arc",
    "apps",
    "codecontests",
    "bigcodebench",
    "leetcode",
    "codereval",
    "repoqa",
    "toolbench",
    "aider-polyglot",
    "terminalbench",
    "gaia",
    "agentbench",
    "webarena",
    "mlagentbench",
    "intercode",
    "custom",
    "mmmu",
    "longbench",
    "adversarial",
)
VALID_INFRASTRUCTURE_MODES = ("local", "azure", "aws", "gcp", "kubernetes", "cloudflare")

# Valid Azure regions (common ones)
VALID_AZURE_REGIONS = (
    "eastus",
    "eastus2",
    "westus",
    "westus2",
    "westus3",
    "centralus",
    "northcentralus",
    "southcentralus",
    "westcentralus",
    "northeurope",
    "westeurope",
    "uksouth",
    "ukwest",
    "francecentral",
    "francesouth",
    "germanywestcentral",
    "swedencentral",
    "switzerlandnorth",
    "norwayeast",
    "eastasia",
    "southeastasia",
    "japaneast",
    "japanwest",
    "australiaeast",
    "australiasoutheast",
    "australiacentral",
    "brazilsouth",
    "canadacentral",
    "canadaeast",
    "southafricanorth",
    "southindia",
    "centralindia",
    "koreacentral",
    "koreasouth",
)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str = Field(
        default="mcpbr", description="Name to register the MCP server as (appears in tool names)"
    )
    command: str = Field(
        description="Command to start the MCP server (e.g., 'npx', 'uvx', 'python')"
    )
    args: list[str] = Field(
        default_factory=list,
        description="Arguments to pass to the command. Use {workdir} as placeholder.",
    )
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the MCP server",
    )
    startup_timeout_ms: int = Field(
        default=60000,
        description="Timeout in milliseconds for MCP server startup (default: 60s)",
    )
    tool_timeout_ms: int = Field(
        default=900000,
        description="Timeout in milliseconds for MCP tool execution (default: 15 min for long-running tools)",
    )
    setup_command: str | None = Field(
        default=None,
        description="Shell command to run inside the container BEFORE the agent starts. "
        "Runs outside the task timer (does not count against timeout_seconds). "
        "Use {workdir} as placeholder. Useful for pre-computing caches.",
    )
    setup_timeout_ms: int = Field(
        default=900000,
        description="Timeout in milliseconds for the setup_command (default: 15 min)",
    )
    setup_only: bool = Field(
        default=False,
        description="When true, only run setup_command. No MCP server is started or "
        "registered with the agent. Use when setup produces static files the agent "
        "reads with native tools.",
    )
    disallowed_native_tools: list[str] = Field(
        default_factory=list,
        description="Native tool names to disable via --disallowedTools when MCP is "
        "active. Use to prevent the agent from bypassing MCP tools with native "
        "equivalents (e.g., ['Read', 'Grep', 'Glob'] for a filesystem MCP server).",
    )
    system_prompt_append: str | None = Field(
        default=None,
        description="Text to append to the system prompt via --append-system-prompt "
        "when MCP is active. Use to guide the agent toward MCP tools.",
    )

    @model_validator(mode="after")
    def validate_setup_only_requires_setup_command(self) -> "MCPServerConfig":
        """Ensure setup_command is provided when setup_only is True."""
        if self.setup_only and not self.setup_command:
            raise ValueError(
                "setup_command is required when setup_only is True. "
                "Without it, no MCP server is started and no setup runs."
            )
        return self

    def get_args_for_workdir(self, workdir: str) -> list[str]:
        """Replace {workdir} placeholder in args with actual path."""
        result = []
        for arg in self.args:
            result.append(arg.replace("{workdir}", workdir))
        return result

    def get_setup_command_for_workdir(self, workdir: str) -> str | None:
        """Replace {workdir} placeholder in setup_command with actual path."""
        if self.setup_command is None:
            return None
        return self.setup_command.replace("{workdir}", workdir)

    def get_expanded_env(self) -> dict[str, str]:
        """Expand ${VAR} references in env values using os.environ.

        Returns:
            Dictionary with environment variables expanded.
        """
        result = {}
        for key, value in self.env.items():
            expanded = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)
            result[key] = expanded
        return result


class AzureConfig(BaseModel):
    """Configuration for Azure infrastructure."""

    resource_group: str = Field(
        description="Azure resource group name (alphanumeric, dash, underscore only)"
    )
    location: str = Field(
        default="eastus",
        description="Azure region (e.g., eastus, westus2, northeurope)",
    )
    vm_size: str | None = Field(
        default=None,
        description="Azure VM size (e.g., Standard_D4s_v3). Alternative to cpu_cores/memory_gb.",
    )
    cpu_cores: int = Field(
        default=8,
        description="Number of CPU cores (used if vm_size not specified)",
    )
    memory_gb: int = Field(
        default=32,
        description="Memory in GB (used if vm_size not specified)",
    )
    disk_gb: int = Field(
        default=1000,
        description="Disk size in GB",
    )
    auto_shutdown: bool = Field(
        default=True,
        description="Automatically shutdown VM after evaluation completes",
    )
    preserve_on_error: bool = Field(
        default=True,
        description="Keep VM running if evaluation fails for debugging",
    )
    env_keys_to_export: list[str] = Field(
        default_factory=lambda: ["ANTHROPIC_API_KEY"],
        description="Environment variables to export to Azure VM",
    )
    ssh_key_path: Path | None = Field(
        default=None,
        description="Path to SSH key for VM access (optional, auto-generated if not provided)",
    )
    zone: str | None = Field(
        default=None,
        description="Azure availability zone (e.g., '1', '2', '3'). Required when VM size has zone-specific restrictions.",
    )
    python_version: str = Field(
        default="3.11",
        description="Python version to install on VM",
    )
    quota_check_timeout: int = Field(
        default=120,
        description="Timeout in seconds for Azure quota check commands (e.g., az vm list-skus)",
    )

    @field_validator("resource_group")
    @classmethod
    def validate_resource_group(cls, v: str) -> str:
        """Validate resource group name format.

        Azure resource groups must be 1-90 characters and contain only
        alphanumeric characters, dashes, and underscores.
        """
        if not re.match(r"^[a-zA-Z0-9_-]{1,90}$", v):
            raise ValueError(
                "resource_group must be 1-90 characters and contain only "
                "alphanumeric characters, dashes, and underscores"
            )
        return v

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Validate Azure region."""
        if v not in VALID_AZURE_REGIONS:
            raise ValueError(
                f"Invalid Azure region: {v}. Must be one of: {', '.join(VALID_AZURE_REGIONS)}"
            )
        return v

    @field_validator("cpu_cores")
    @classmethod
    def validate_cpu_cores(cls, v: int) -> int:
        """Validate CPU cores is at least 1."""
        if v < 1:
            raise ValueError("cpu_cores must be at least 1")
        return v

    @field_validator("memory_gb")
    @classmethod
    def validate_memory_gb(cls, v: int) -> int:
        """Validate memory is at least 1 GB."""
        if v < 1:
            raise ValueError("memory_gb must be at least 1")
        return v

    @field_validator("disk_gb")
    @classmethod
    def validate_disk_gb(cls, v: int) -> int:
        """Validate disk size is at least 30 GB."""
        if v < 30:
            raise ValueError("disk_gb must be at least 30 GB")
        return v

    @field_validator("env_keys_to_export")
    @classmethod
    def validate_env_keys(cls, v: list[str]) -> list[str]:
        """Validate env_keys_to_export is a list of strings."""
        if not all(isinstance(key, str) for key in v):
            raise ValueError("env_keys_to_export must be a list of strings")
        return v


class AWSConfig(BaseModel):
    """Configuration for AWS EC2 infrastructure."""

    region: str = Field(default="us-east-1", description="AWS region")
    instance_type: str | None = Field(
        default=None, description="AWS EC2 instance type (e.g., t3.2xlarge)"
    )
    cpu_cores: int = Field(default=8, description="Number of CPU cores")
    memory_gb: int = Field(default=32, description="Memory in GB")
    disk_gb: int = Field(default=1000, description="EBS volume size in GB")
    ami: str | None = Field(
        default=None, description="AMI ID (auto-selects Ubuntu 22.04 if not specified)"
    )
    auto_shutdown: bool = Field(default=True, description="Terminate instance after evaluation")
    preserve_on_error: bool = Field(default=True, description="Keep instance on error")
    env_keys_to_export: list[str] = Field(
        default_factory=lambda: ["ANTHROPIC_API_KEY"],
        description="Environment variables to export",
    )
    ssh_key_path: Path | None = Field(default=None, description="Path to SSH private key")
    vpc_id: str | None = Field(default=None, description="VPC ID (uses default if not set)")
    subnet_id: str | None = Field(default=None, description="Subnet ID")
    security_group_ids: list[str] | None = Field(default=None, description="Security group IDs")
    iam_role: str | None = Field(default=None, description="IAM instance profile name")
    tags: dict[str, str] = Field(default_factory=dict, description="EC2 instance tags")
    python_version: str = Field(default="3.11", description="Python version to install")


class GCPConfig(BaseModel):
    """Configuration for GCP Compute Engine infrastructure."""

    project_id: str | None = Field(
        default=None,
        description="GCP project ID (uses default project if not specified)",
    )
    region: str = Field(
        default="us-central1",
        description="GCP region (e.g., us-central1, us-east1, europe-west1)",
    )
    zone: str = Field(
        default="us-central1-a",
        description="GCP zone (e.g., us-central1-a, us-east1-b)",
    )
    machine_type: str | None = Field(
        default=None,
        description="GCE machine type (e.g., n2-standard-8). Alternative to cpu_cores/memory_gb.",
    )
    cpu_cores: int = Field(
        default=8,
        description="Number of CPU cores (used if machine_type not specified)",
    )
    memory_gb: int = Field(
        default=32,
        description="Memory in GB (used if machine_type not specified)",
    )
    disk_gb: int = Field(
        default=1000,
        description="Boot disk size in GB",
    )
    disk_type: str = Field(
        default="pd-balanced",
        description="Boot disk type (pd-standard, pd-balanced, pd-ssd)",
    )
    image_family: str = Field(
        default="ubuntu-2204-lts",
        description="Image family for the boot disk",
    )
    image_project: str = Field(
        default="ubuntu-os-cloud",
        description="Image project for the boot disk",
    )
    preemptible: bool = Field(
        default=False,
        description="Use preemptible instance (cheaper but can be terminated)",
    )
    spot: bool = Field(
        default=False,
        description="Use Spot VM (cheaper but can be terminated, replaces preemptible)",
    )
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Labels to apply to the instance",
    )
    service_account: str | None = Field(
        default=None,
        description="Service account email to attach to the instance",
    )
    scopes: list[str] | None = Field(
        default=None,
        description="API scopes for the instance (e.g., ['compute-rw', 'storage-ro'])",
    )
    env_keys_to_export: list[str] = Field(
        default_factory=lambda: ["ANTHROPIC_API_KEY"],
        description="Environment variables to export to GCE instance",
    )
    auto_shutdown: bool = Field(
        default=True,
        description="Automatically delete instance after evaluation completes",
    )
    preserve_on_error: bool = Field(
        default=True,
        description="Keep instance running if evaluation fails for debugging",
    )
    ssh_key_path: Path | None = Field(
        default=None,
        description="Path to SSH key for instance access (optional, auto-generated if not provided)",
    )
    python_version: str = Field(
        default="3.11",
        description="Python version to install on instance",
    )

    @field_validator("cpu_cores")
    @classmethod
    def validate_cpu_cores(cls, v: int) -> int:
        """Validate CPU cores is at least 1."""
        if v < 1:
            raise ValueError("cpu_cores must be at least 1")
        return v

    @field_validator("memory_gb")
    @classmethod
    def validate_memory_gb(cls, v: int) -> int:
        """Validate memory is at least 1 GB."""
        if v < 1:
            raise ValueError("memory_gb must be at least 1")
        return v

    @field_validator("disk_gb")
    @classmethod
    def validate_disk_gb(cls, v: int) -> int:
        """Validate disk size is at least 10 GB."""
        if v < 10:
            raise ValueError("disk_gb must be at least 10 GB")
        return v

    @field_validator("disk_type")
    @classmethod
    def validate_disk_type(cls, v: str) -> str:
        """Validate disk type."""
        valid = ("pd-standard", "pd-balanced", "pd-ssd")
        if v not in valid:
            raise ValueError(f"Invalid disk_type: {v}. Must be one of: {', '.join(valid)}")
        return v

    @field_validator("env_keys_to_export")
    @classmethod
    def validate_env_keys(cls, v: list[str]) -> list[str]:
        """Validate env_keys_to_export is a list of strings."""
        if not all(isinstance(key, str) for key in v):
            raise ValueError("env_keys_to_export must be a list of strings")
        return v


class KubernetesConfig(BaseModel):
    """Configuration for Kubernetes infrastructure."""

    context: str | None = Field(default=None, description="kubectl context (auto-detect if None)")
    namespace: str = Field(default="mcpbr-benchmarks", description="Kubernetes namespace")
    image: str = Field(default="python:3.11-slim", description="Base image for pods")
    image_pull_policy: str = Field(default="IfNotPresent", description="Image pull policy")
    cpu_request: str = Field(default="2000m", description="CPU request per pod")
    cpu_limit: str = Field(default="4000m", description="CPU limit per pod")
    memory_request: str = Field(default="4Gi", description="Memory request per pod")
    memory_limit: str = Field(default="8Gi", description="Memory limit per pod")
    parallelism: int = Field(default=10, description="Max concurrent pods")
    backoff_limit: int = Field(default=3, description="Retry failed pods")
    ttl_seconds_after_finished: int = Field(default=600, description="Cleanup pods after N seconds")
    env_keys_to_export: list[str] = Field(
        default_factory=lambda: ["ANTHROPIC_API_KEY"],
        description="Environment variables to export as Secret",
    )
    enable_dind: bool = Field(default=True, description="Enable Docker-in-Docker sidecar")
    auto_cleanup: bool = Field(default=True, description="Delete resources after evaluation")
    preserve_on_error: bool = Field(default=True, description="Keep resources on error")
    node_selector: dict[str, str] = Field(default_factory=dict, description="Node selector")
    tolerations: list[dict[str, str]] = Field(default_factory=list, description="Pod tolerations")
    labels: dict[str, str] = Field(default_factory=dict, description="Resource labels")


class CloudflareConfig(BaseModel):
    """Configuration for Cloudflare Workers infrastructure."""

    account_id: str = Field(description="Cloudflare account ID")
    workers_subdomain: str | None = Field(
        default=None, description="Workers subdomain (<subdomain>.workers.dev)"
    )
    worker_name: str | None = Field(
        default=None, description="Worker name (auto-generated if not set)"
    )
    auto_cleanup: bool = Field(default=True, description="Delete Worker after evaluation")
    preserve_on_error: bool = Field(default=True, description="Keep Worker on error")
    env_keys_to_export: list[str] = Field(
        default_factory=lambda: ["ANTHROPIC_API_KEY"],
        description="Environment variables to set as Worker secrets",
    )
    kv_namespace: str | None = Field(default=None, description="KV namespace for result storage")
    r2_bucket: str | None = Field(default=None, description="R2 bucket for artifact storage")
    compatibility_date: str = Field(default="2024-01-01", description="Worker compatibility date")


class InfrastructureConfig(BaseModel):
    """Configuration for infrastructure mode."""

    mode: Literal["local", "azure", "aws", "gcp", "kubernetes", "cloudflare"] = Field(
        default="local",
        description="Infrastructure mode: local, azure, aws, gcp, kubernetes, or cloudflare",
    )
    azure: AzureConfig | None = Field(
        default=None,
        description="Azure configuration (required when mode=azure)",
    )
    aws: AWSConfig | None = Field(
        default=None,
        description="AWS configuration (required when mode=aws)",
    )
    gcp: GCPConfig | None = Field(
        default=None,
        description="GCP configuration (required when mode=gcp)",
    )
    kubernetes: KubernetesConfig | None = Field(
        default=None,
        description="Kubernetes configuration (required when mode=kubernetes)",
    )
    cloudflare: CloudflareConfig | None = Field(
        default=None,
        description="Cloudflare configuration (required when mode=cloudflare)",
    )

    @model_validator(mode="after")
    def validate_provider_config(self) -> "InfrastructureConfig":
        """Ensure the correct provider config is present for the selected mode."""
        mode_config_map = {
            "azure": self.azure,
            "aws": self.aws,
            "gcp": self.gcp,
            "kubernetes": self.kubernetes,
            "cloudflare": self.cloudflare,
        }
        if self.mode in mode_config_map and mode_config_map[self.mode] is None:
            raise ValueError(f"{self.mode} configuration is required when mode={self.mode}")
        return self


class HarnessConfig(BaseModel):
    """Main configuration for the test harness.

    Supports multiple model providers and agent harnesses.
    """

    # Single server field (for backward compatibility)
    mcp_server: MCPServerConfig | None = Field(
        default=None, description="MCP server configuration (single server mode)"
    )

    # Comparison mode fields
    mcp_server_a: MCPServerConfig | None = Field(
        default=None, description="First MCP server for comparison"
    )
    mcp_server_b: MCPServerConfig | None = Field(
        default=None, description="Second MCP server for comparison"
    )
    comparison_mode: bool = Field(default=False, description="Enable side-by-side comparison mode")

    provider: str = Field(
        default="anthropic",
        description="Model provider (currently only anthropic is supported)",
    )

    agent_harness: str = Field(
        default="claude-code",
        description="Agent harness (currently only claude-code is supported)",
    )

    agent_prompt: str | None = Field(
        default=None,
        description="Custom prompt template for the agent. Use {problem_statement} placeholder.",
    )

    model: str = Field(
        default=DEFAULT_MODEL,
        description="Model ID for the selected provider",
    )

    benchmark: str = Field(
        default="swe-bench-verified",
        description="Benchmark to run (use `mcpbr benchmarks` for the full list).",
    )

    cybergym_level: int = Field(
        default=1,
        description="CyberGym difficulty level (0-3), controls context given to agent",
    )

    sample_size: int | None = Field(
        default=None,
        description="Number of tasks to evaluate (None for full dataset)",
    )

    timeout_seconds: int = Field(
        default=300,
        description="Timeout for each task in seconds",
    )

    eval_timeout_seconds: int = Field(
        default=600,
        description="Timeout for post-agent evaluation (applying patches and running tests) "
        "in seconds. Set higher for benchmarks with slow test suites (e.g., Django).",
    )

    max_concurrent: int = Field(
        default=4,
        description="Maximum concurrent task evaluations",
    )

    max_iterations: int = Field(
        default=10,
        description="Maximum agent iterations per task",
    )

    thinking_budget: int | None = Field(
        default=None,
        description="Extended thinking token budget. Set to enable thinking mode (e.g., 10000)",
    )

    @field_validator("thinking_budget")
    @classmethod
    def validate_thinking_budget(cls, v: int | None) -> int | None:
        """Validate thinking_budget is within acceptable bounds.

        Claude API requires budget_tokens >= 1024 and < max_tokens.
        Claude Code caps thinking at 31999 tokens by default.
        """
        if v is None:
            return v
        if v < 1024:
            raise ValueError("thinking_budget must be at least 1024 tokens (Claude API minimum)")
        if v > 31999:
            raise ValueError("thinking_budget cannot exceed 31999 tokens (Claude Code maximum)")
        return v

    task_ids: list[str] | None = Field(
        default=None,
        description="Specific task instance IDs to evaluate (None for all). "
        "CLI --task/-t flags are merged into this field for remote execution.",
    )

    use_prebuilt_images: bool = Field(
        default=True,
        description="Use pre-built SWE-bench Docker images when available",
    )

    claude_code_version: str | None = Field(
        default=None,
        description="Pin a specific Claude Code version inside Docker containers "
        "(e.g., '2.1.37'). Defaults to latest. Useful for version comparison experiments.",
    )

    budget: float | None = Field(
        default=None,
        description="Maximum budget in USD for the evaluation (halts when reached)",
    )

    cache_enabled: bool = Field(
        default=False,
        description="Enable result caching to avoid re-running identical evaluations",
    )

    cache_dir: Path | None = Field(
        default=None,
        description="Directory to store cache files (default: ~/.cache/mcpbr)",
    )

    output_dir: str | None = Field(
        default=None,
        description="Directory for all evaluation outputs (logs, state, results). Default: .mcpbr_run_TIMESTAMP",
    )

    disable_logs: bool = Field(
        default=False,
        description="Disable detailed execution logs (logs are enabled by default to output_dir/logs/)",
    )

    filter_difficulty: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by difficulty (e.g., ['easy', 'medium', 'hard'] or ['0', '1', '2', '3'] for CyberGym)",
    )

    filter_category: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by category (e.g., ['browser', 'finance'] for MCPToolBench)",
    )

    filter_tags: list[str] | None = Field(
        default=None,
        description="Filter benchmarks by tags (requires all tags to match)",
    )

    enable_profiling: bool = Field(
        default=False,
        description="Enable comprehensive performance profiling (tool latency, memory, overhead)",
    )

    volumes: dict[str, str] = Field(
        default_factory=dict,
        description="Additional volume mounts (read-write) for Docker containers (host_path: container_path). "
        "Mounted into every container, persists across tasks. Useful for pre-computed caches.",
    )

    sandbox: dict | None = Field(
        default=None,
        description="Sandbox security profile for Docker containers. "
        "Use {'level': 'standard'} for default security, "
        "{'level': 'strict'} for maximum isolation, "
        "or {'level': 'permissive'} for no restrictions. "
        "Custom overrides: cap_drop, cap_add, read_only_rootfs, network_disabled, tmpfs_mounts.",
    )

    prompt_security: dict | None = Field(
        default=None,
        description="Prompt security scanning configuration. "
        "Use {'enabled': true} for default scanning. "
        "Options: scan_level (full/minimal), action (audit/warn/block), "
        "custom_patterns, allowlist_patterns.",
    )

    infrastructure: InfrastructureConfig = Field(
        default_factory=InfrastructureConfig,
        description="Infrastructure configuration (local or azure)",
    )

    # --- Rate Limiting (v0.9.0) ---
    rate_limit_rpm: int | None = Field(
        default=None,
        description="Maximum API requests per minute (None for unlimited)",
    )

    rate_limit_strategy: str = Field(
        default="adaptive",
        description="Rate limit backoff strategy: fixed, exponential, or adaptive",
    )

    # --- Reproducibility (v0.9.0) ---
    global_seed: int | None = Field(
        default=None,
        description="Global random seed for reproducible evaluations",
    )

    deterministic_mode: bool = Field(
        default=False,
        description="Enable deterministic mode (sets PYTHONHASHSEED, seeds all RNG)",
    )

    record_environment: bool = Field(
        default=False,
        description="Record environment snapshot for reproducibility verification",
    )

    # --- Privacy Controls (v0.9.0) ---
    redaction_level: str = Field(
        default="none",
        description="PII redaction level for results: none, basic, or strict",
    )

    data_retention_days: int | None = Field(
        default=None,
        description="Days to retain evaluation data (None for forever)",
    )

    exclude_result_fields: list[str] = Field(
        default_factory=list,
        description="Result fields to strip before saving (e.g., ['agent_trace'])",
    )

    # --- Audit Logging (v0.9.0) ---
    audit_enabled: bool = Field(
        default=False,
        description="Enable tamper-proof audit logging of all benchmark operations",
    )

    audit_log_file: str | None = Field(
        default=None,
        description="Path to the audit log file (default: output_dir/audit.jsonl)",
    )

    continue_on_error: bool = Field(
        default=True,
        description="Continue evaluation when individual tasks fail instead of stopping",
    )

    max_failures: int | None = Field(
        default=None,
        description="Maximum number of task failures before halting evaluation (None for unlimited)",
    )

    checkpoint_interval: int = Field(
        default=1,
        description="Save execution checkpoint every N completed tasks",
    )

    resume_from_checkpoint: Path | None = Field(
        default=None,
        description="Path to a checkpoint file to resume evaluation from",
    )

    # --- Sampling (v0.10.0) ---
    sampling_strategy: str = Field(
        default="sequential",
        description="Sampling strategy: sequential, random, or stratified.",
    )
    random_seed: int | None = Field(
        default=None,
        description="Random seed for reproducible sampling (None = non-deterministic).",
    )
    stratify_field: str | None = Field(
        default=None,
        description="Field to stratify by when using stratified sampling.",
    )

    # --- Integrations (v0.10.0) ---
    wandb_enabled: bool = Field(default=False, description="Enable W&B logging.")
    wandb_project: str = Field(default="mcpbr", description="W&B project name.")

    # --- Cloud Storage (v0.11.0) ---
    cloud_storage: dict | None = Field(
        default=None,
        description=(
            "Cloud storage config for auto-uploading results. "
            "Format: {provider: 's3'|'gcs'|'azure_blob', bucket: '...', account: '...'}"
        ),
    )

    # --- Notifications (v0.10.0) ---
    notify_slack_webhook: str | None = Field(
        default=None, description="Slack webhook URL for completion notifications."
    )
    notify_discord_webhook: str | None = Field(
        default=None, description="Discord webhook URL for completion notifications."
    )
    notify_email: dict[str, Any] | None = Field(
        default=None, description="Email config dict (smtp_host, smtp_port, from_addr, to_addrs)."
    )
    slack_bot_token: str | None = Field(
        default=None, description="Slack bot token for file uploads (xoxb-...)."
    )
    slack_channel: str | None = Field(
        default=None, description="Slack channel ID for file uploads."
    )
    github_token: str | None = Field(
        default=None, description="GitHub token for creating Gist reports."
    )

    # --- Lifecycle Notifications (v0.13.0) ---
    notify_progress_interval: int = Field(
        default=0,
        description="Send progress notification every N completed tasks (0 = disabled).",
    )
    notify_progress_time_minutes: int = Field(
        default=0,
        description="Send progress notification every N minutes (0 = disabled).",
    )

    @field_validator("notify_progress_interval", "notify_progress_time_minutes")
    @classmethod
    def validate_notify_progress_intervals(cls, v: int) -> int:
        """Validate progress notification intervals are non-negative."""
        if v < 0:
            raise ValueError("progress notification intervals must be >= 0")
        return v

    @model_validator(mode="after")
    def validate_stratified_sampling(self) -> "HarnessConfig":
        """Ensure stratify_field is set when using stratified sampling."""
        if self.sampling_strategy == "stratified" and not self.stratify_field:
            raise ValueError("stratify_field is required when sampling_strategy is 'stratified'")
        return self

    @field_validator("checkpoint_interval")
    @classmethod
    def validate_checkpoint_interval(cls, v: int) -> int:
        """Validate checkpoint_interval is at least 1."""
        if v < 1:
            raise ValueError("checkpoint_interval must be at least 1")
        return v

    @field_validator("max_failures")
    @classmethod
    def validate_max_failures(cls, v: int | None) -> int | None:
        """Validate max_failures is positive if set."""
        if v is not None and v < 1:
            raise ValueError("max_failures must be at least 1")
        return v

    @field_validator("rate_limit_rpm")
    @classmethod
    def validate_rate_limit_rpm(cls, v: int | None) -> int | None:
        """Validate rate_limit_rpm is positive if set."""
        if v is not None and v < 1:
            raise ValueError("rate_limit_rpm must be at least 1")
        return v

    @field_validator("rate_limit_strategy")
    @classmethod
    def validate_rate_limit_strategy(cls, v: str) -> str:
        """Validate rate limit strategy."""
        valid = ("fixed", "exponential", "adaptive")
        if v not in valid:
            raise ValueError(
                f"Invalid rate_limit_strategy: {v}. Must be one of: {', '.join(valid)}"
            )
        return v

    @field_validator("redaction_level")
    @classmethod
    def validate_redaction_level(cls, v: str) -> str:
        """Validate redaction level."""
        valid = ("none", "basic", "strict")
        if v not in valid:
            raise ValueError(f"Invalid redaction_level: {v}. Must be one of: {', '.join(valid)}")
        return v

    @field_validator("data_retention_days")
    @classmethod
    def validate_data_retention_days(cls, v: int | None) -> int | None:
        """Validate data_retention_days is positive if set."""
        if v is not None and v < 1:
            raise ValueError("data_retention_days must be at least 1")
        return v

    @field_validator("sampling_strategy")
    @classmethod
    def validate_sampling_strategy(cls, v: str) -> str:
        allowed = {"sequential", "random", "stratified"}
        if v not in allowed:
            raise ValueError(f"sampling_strategy must be one of {allowed}, got '{v}'")
        return v

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider: {v}. Valid providers: {', '.join(VALID_PROVIDERS)}"
            )
        return v

    @field_validator("agent_harness")
    @classmethod
    def validate_agent_harness(cls, v: str) -> str:
        if v not in VALID_HARNESSES:
            raise ValueError(
                f"Invalid agent_harness: {v}. Valid harnesses: {', '.join(VALID_HARNESSES)}"
            )
        return v

    @field_validator("benchmark")
    @classmethod
    def validate_benchmark(cls, v: str) -> str:
        if v not in VALID_BENCHMARKS:
            raise ValueError(
                f"Invalid benchmark: {v}. Valid benchmarks: {', '.join(VALID_BENCHMARKS)}"
            )
        return v

    @field_validator("cybergym_level")
    @classmethod
    def validate_cybergym_level(cls, v: int) -> int:
        if v < 0 or v > 3:
            raise ValueError("cybergym_level must be between 0 and 3")
        return v

    @model_validator(mode="after")
    def validate_model_for_provider(self) -> "HarnessConfig":
        """Validate model ID based on the provider.

        Anthropic provider accepts any model ID (direct API).
        """
        return self

    @model_validator(mode="after")
    def validate_server_config(self) -> "HarnessConfig":
        """Validate MCP server configuration consistency."""
        if self.comparison_mode:
            if not (self.mcp_server_a and self.mcp_server_b):
                raise ValueError("comparison_mode requires both mcp_server_a and mcp_server_b")
            if self.mcp_server:
                raise ValueError("comparison_mode: use mcp_server_a/b instead of mcp_server")
        else:
            if not self.mcp_server:
                raise ValueError("mcp_server required when comparison_mode is false")
            if self.mcp_server_a or self.mcp_server_b:
                raise ValueError("mcp_server_a/b only valid in comparison_mode")
        return self

    @field_validator("max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_concurrent must be at least 1")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 30:
            raise ValueError("timeout_seconds must be at least 30")
        return v

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("budget must be positive")
        return v


def load_config(config_path: str | Path, warn_security: bool = True) -> HarnessConfig:
    """Load configuration from a YAML file with environment variable expansion.

    Automatically loads .env file from current directory if it exists.
    Supports ${VAR} and ${VAR:-default} syntax for environment variables.
    Supports config inheritance via the 'extends' field.

    Args:
        config_path: Path to the YAML configuration file.
        warn_security: Whether to print security warnings for hardcoded secrets.

    Returns:
        Validated HarnessConfig instance.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config is invalid or required environment variables are missing.
        CircularInheritanceError: If circular inheritance is detected.
        ConfigInheritanceError: If there's an error loading or merging inherited configs.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Load .env file if it exists in the current directory
    load_dotenv_file()

    # Load raw YAML with inheritance support
    raw_config: dict[str, Any] = load_config_with_inheritance(path)

    # Check for security issues before expansion
    if warn_security:
        security_warnings = validate_config_security(raw_config)
        if security_warnings:
            console = Console(stderr=True)
            console.print("[yellow]⚠ Security warnings:[/yellow]")
            for warning in security_warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
            console.print()

    # Expand environment variables
    required_vars: set[str] = set()
    try:
        expanded_config = expand_env_vars(raw_config, required_vars)
    except ValueError as e:
        # Provide helpful error message for missing required variables
        raise ValueError(
            f"Configuration error: {e}\n\n"
            f"You can either:\n"
            f"1. Set the environment variable before running mcpbr\n"
            f"2. Add it to a .env file in the current directory\n"
            f"3. Provide a default value in the config: ${{{{VAR:-default}}}}"
        ) from e

    return HarnessConfig(**expanded_config)


def create_default_config() -> HarnessConfig:
    """Create a default configuration for testing."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        provider="anthropic",
        agent_harness="claude-code",
        model=DEFAULT_MODEL,
    )
