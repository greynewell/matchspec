"""Azure VM infrastructure provider."""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError:
    # paramiko is optional, only needed when actually using Azure provider
    paramiko = None  # type: ignore

from rich.console import Console

from ..config import HarnessConfig
from .base import InfrastructureProvider


class AzureProvider(InfrastructureProvider):
    """Azure VM infrastructure provider.

    This provider manages the lifecycle of Azure VMs for running evaluations:
    - Provisions VMs with appropriate sizing
    - Manages SSH connectivity
    - Handles VM cleanup with configurable preservation policies
    """

    def __init__(self, config: HarnessConfig):
        """Initialize Azure provider.

        Args:
            config: Harness configuration with Azure settings.
        """
        self.config = config
        self.azure_config = config.infrastructure.azure
        self.vm_name: str | None = None
        self.vm_ip: str | None = None
        self.ssh_client: paramiko.SSHClient | None = None
        self.ssh_key_path: Path | None = None
        self._error_occurred = False

    def _determine_vm_size(self) -> str:
        """Map cpu_cores/memory_gb to Azure VM size.

        Returns:
            Azure VM size string (e.g., "Standard_D8s_v3").
        """
        # If explicit VM size specified, use it
        if self.azure_config.vm_size:
            return self.azure_config.vm_size

        cores = self.azure_config.cpu_cores
        memory = self.azure_config.memory_gb

        # Standard_D series mapping (general purpose, good balance)
        if cores <= 2 and memory <= 8:
            return "Standard_D2s_v3"
        elif cores <= 4 and memory <= 16:
            return "Standard_D4s_v3"
        elif cores <= 8 and memory <= 32:
            return "Standard_D8s_v3"
        elif cores <= 16 and memory <= 64:
            return "Standard_D16s_v3"
        elif cores <= 32 and memory <= 128:
            return "Standard_D32s_v3"
        else:
            return "Standard_D64s_v3"

    async def _create_vm(self, vm_size: str) -> None:
        """Create Azure VM using az CLI.

        Args:
            vm_size: Azure VM size (e.g., "Standard_D8s_v3").

        Raises:
            RuntimeError: If VM creation fails.
        """
        console = Console()

        # Generate unique VM name
        timestamp = int(time.time())
        self.vm_name = f"mcpbr-eval-{timestamp}"

        # Generate or use existing SSH key
        ssh_key_path = self.azure_config.ssh_key_path
        if not ssh_key_path:
            ssh_key_path = Path.home() / ".ssh" / "mcpbr_azure"
            if not ssh_key_path.exists():
                console.print("[cyan]Generating SSH key...[/cyan]")
                ssh_key_path.parent.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(
                    [
                        "ssh-keygen",
                        "-t",
                        "rsa",
                        "-b",
                        "4096",
                        "-f",
                        str(ssh_key_path),
                        "-N",
                        "",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"SSH key generation failed: {result.stderr}")
        self.ssh_key_path = ssh_key_path

        # Check if resource group exists, create if needed
        console.print(f"[cyan]Checking resource group: {self.azure_config.resource_group}[/cyan]")
        result = subprocess.run(
            [
                "az",
                "group",
                "show",
                "--name",
                self.azure_config.resource_group,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print("[cyan]Creating resource group...[/cyan]")
            result = subprocess.run(
                [
                    "az",
                    "group",
                    "create",
                    "--name",
                    self.azure_config.resource_group,
                    "--location",
                    self.azure_config.location,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Resource group creation failed: {result.stderr}")

        # Create VM
        console.print(f"[cyan]Creating VM: {self.vm_name} ({vm_size})...[/cyan]")
        result = subprocess.run(
            [
                "az",
                "vm",
                "create",
                "--resource-group",
                self.azure_config.resource_group,
                "--name",
                self.vm_name,
                "--image",
                "Ubuntu2204",
                "--size",
                vm_size,
                "--admin-username",
                "azureuser",
                "--ssh-key-values",
                f"{ssh_key_path}.pub",
                "--public-ip-sku",
                "Standard",
                "--os-disk-size-gb",
                str(self.azure_config.disk_gb),
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"VM creation failed: {result.stderr}")

        console.print(f"[green]✓ VM created: {self.vm_name}[/green]")

    async def _get_vm_ip(self) -> str:
        """Get VM public IP address.

        Returns:
            Public IP address of the VM.

        Raises:
            RuntimeError: If IP retrieval fails.
        """
        result = subprocess.run(
            [
                "az",
                "vm",
                "show",
                "--resource-group",
                self.azure_config.resource_group,
                "--name",
                self.vm_name,
                "--show-details",
                "--query",
                "publicIps",
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get VM IP: {result.stderr}")

        ip = json.loads(result.stdout)
        return ip

    async def _wait_for_ssh(self, timeout: int = 300) -> None:
        """Wait for SSH to become available.

        Args:
            timeout: Maximum time to wait in seconds.

        Raises:
            RuntimeError: If SSH connection fails within timeout.
        """
        if paramiko is None:
            raise RuntimeError(
                "paramiko is required for Azure provider. Install with: pip install paramiko"
            )

        console = Console()
        console.print("[cyan]Waiting for SSH to become available...[/cyan]")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Create SSH client
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh_client.connect(
                    self.vm_ip,
                    username="azureuser",
                    key_filename=str(self.ssh_key_path),
                    timeout=10,
                )
                console.print("[green]✓ SSH connection established[/green]")
                return
            except Exception:
                # Close failed client
                if self.ssh_client:
                    self.ssh_client.close()
                    self.ssh_client = None
                # Wait and retry
                await asyncio.sleep(5)

        raise RuntimeError(
            f"SSH connection failed after {timeout}s. VM may not be ready or network issues exist."
        )

    async def _ssh_exec(self, command: str, timeout: int = 300) -> tuple[int, str, str]:
        """Execute command over SSH.

        Args:
            command: Command to execute.
            timeout: Command timeout in seconds.

        Returns:
            Tuple of (exit_code, stdout, stderr).

        Raises:
            RuntimeError: If SSH client not initialized or command fails.
        """
        if not self.ssh_client:
            raise RuntimeError("SSH client not initialized")

        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode("utf-8")
            stderr_str = stderr.read().decode("utf-8")
            return exit_code, stdout_str, stderr_str
        except Exception as e:
            raise RuntimeError(f"SSH command failed: {e}") from e

    async def setup(self) -> None:
        """Provision Azure VM and prepare for evaluation.

        This method:
        1. Determines appropriate VM size
        2. Creates the VM
        3. Retrieves the public IP
        4. Waits for SSH to become available

        Raises:
            RuntimeError: If setup fails at any step.
        """
        console = Console()
        console.print("[cyan]Provisioning Azure VM...[/cyan]")

        try:
            # Determine VM size
            vm_size = self._determine_vm_size()

            # Create VM
            await self._create_vm(vm_size)

            # Get IP
            self.vm_ip = await self._get_vm_ip()
            console.print(f"[cyan]VM IP: {self.vm_ip}[/cyan]")

            # Wait for SSH
            await self._wait_for_ssh()

            console.print("[green]✓ VM provisioned successfully[/green]")

        except Exception:
            self._error_occurred = True
            raise

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on Azure VM (Phase 4).

        Args:
            config: Harness configuration.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object.

        Raises:
            NotImplementedError: This will be implemented in Phase 4.
        """
        raise NotImplementedError("Phase 4: Remote execution not yet implemented")

    async def collect_artifacts(self, output_dir: Path) -> Path:
        """Download artifacts from VM (Phase 5).

        Args:
            output_dir: Directory to store artifacts.

        Returns:
            Path to ZIP archive.

        Raises:
            NotImplementedError: This will be implemented in Phase 5.
        """
        raise NotImplementedError("Phase 5: Artifact collection not yet implemented")

    async def cleanup(self, force: bool = False) -> None:
        """Delete Azure VM.

        This method respects the auto_shutdown and preserve_on_error settings
        unless force=True is specified.

        Args:
            force: If True, force cleanup regardless of settings.
        """
        console = Console()

        # Close SSH connection
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass  # Best effort

        # Check if we should cleanup
        if not self.vm_name:
            return

        # Determine if should cleanup
        should_cleanup = force or (
            self.azure_config.auto_shutdown
            and not (self._error_occurred and self.azure_config.preserve_on_error)
        )

        if not should_cleanup:
            console.print(f"[yellow]VM preserved: {self.vm_name}[/yellow]")
            if self.vm_ip and self.ssh_key_path:
                console.print(f"[dim]SSH: ssh -i {self.ssh_key_path} azureuser@{self.vm_ip}[/dim]")
            return

        # Delete VM
        console.print(f"[cyan]Deleting VM: {self.vm_name}...[/cyan]")
        result = subprocess.run(
            [
                "az",
                "vm",
                "delete",
                "--resource-group",
                self.azure_config.resource_group,
                "--name",
                self.vm_name,
                "--yes",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print(f"[yellow]Warning: VM deletion failed: {result.stderr}[/yellow]")
        else:
            console.print("[green]✓ VM deleted[/green]")

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run Azure health checks.

        Returns:
            Dictionary with health check results.
        """
        from .azure_health import run_azure_health_checks

        return run_azure_health_checks(self.azure_config)
