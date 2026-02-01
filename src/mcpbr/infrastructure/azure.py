"""Azure VM infrastructure provider."""

import asyncio
import json
import os
import shlex
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
                # AutoAddPolicy is used because we just provisioned this VM and
                # its host key is not yet in known_hosts. This is acceptable for
                # automated provisioning where MITM risk is low, but enterprise
                # deployments may want to use RejectPolicy with pre-seeded keys.
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
            _stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode("utf-8")
            stderr_str = stderr.read().decode("utf-8")
            return exit_code, stdout_str, stderr_str
        except Exception as e:
            raise RuntimeError(f"SSH command failed: {e}") from e

    async def _install_dependencies(self) -> None:
        """Install Docker, Python, and mcpbr on VM."""
        console = Console()
        console.print("[cyan]Installing dependencies on VM...[/cyan]")

        # Update apt cache
        install_cmd = (
            "sudo apt-get update -qq && "
            "sudo apt-get install -y -qq curl python3-pip && "
            # Install Docker
            "curl -fsSL https://get.docker.com -o get-docker.sh && "
            "sudo sh get-docker.sh && "
            "sudo usermod -aG docker $USER && "
            # Install Python version
            f"sudo apt-get install -y python{self.azure_config.python_version} python{self.azure_config.python_version}-venv && "
            # Install mcpbr
            "pip3 install mcpbr"
        )

        exit_code, _stdout, stderr = await self._ssh_exec(install_cmd, timeout=600)

        # Don't fail hard on installation issues - log and continue
        if exit_code != 0:
            console.print(
                f"[yellow]⚠ Some installations may have issues (exit code {exit_code})[/yellow]"
            )
            console.print(f"[dim]{stderr[:500]}[/dim]")
        else:
            console.print("[green]✓ Dependencies installed[/green]")

    async def _transfer_config(self) -> None:
        """Transfer configuration file to VM via SFTP."""
        console = Console()
        console.print("[cyan]Transferring configuration...[/cyan]")

        # Create temporary config file
        import tempfile

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Serialize config to YAML (convert Pydantic model to dict)
            config_dict = self.config.model_dump()
            yaml.dump(config_dict, f)
            temp_config_path = f.name

        sftp = None
        try:
            # Upload via SFTP
            sftp = self.ssh_client.open_sftp()
            sftp.put(temp_config_path, "/home/azureuser/config.yaml")
            console.print("[green]✓ Configuration transferred[/green]")
        finally:
            if sftp:
                sftp.close()
            Path(temp_config_path).unlink()

    async def _export_env_vars(self) -> None:
        """Export environment variables to VM."""
        console = Console()
        console.print("[cyan]Exporting environment variables...[/cyan]")

        env_vars = {}
        for key in self.azure_config.env_keys_to_export:
            value = os.environ.get(key)
            if value:
                env_vars[key] = value
            else:
                console.print(f"[yellow]⚠ Environment variable {key} not found locally[/yellow]")

        if not env_vars:
            console.print("[yellow]⚠ No environment variables to export[/yellow]")
            return

        # Write to .bashrc and .profile using shlex.quote to prevent shell injection
        env_commands = [f"export {k}={shlex.quote(v)}" for k, v in env_vars.items()]
        bashrc_append = "\n".join(env_commands)

        # Use a here-document to safely write env vars without shell expansion
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.bashrc\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.profile\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)

        console.print(f"[green]✓ Exported {len(env_vars)} environment variables[/green]")

    async def _run_test_task(self) -> None:
        """Run single test task to validate setup."""
        console = Console()
        console.print("[cyan]Running test task to validate setup...[/cyan]")

        # Run mcpbr with sample_size=1, max_concurrent=1
        test_cmd = "mcpbr run -c ~/config.yaml -M -n 1"

        exit_code, stdout, stderr = await self._ssh_exec(test_cmd, timeout=600)

        if exit_code != 0:
            console.print("[red]✗ Test task failed![/red]")
            console.print(f"[red]STDOUT:[/red]\n{stdout[:1000]}")
            console.print(f"[red]STDERR:[/red]\n{stderr[:1000]}")
            raise RuntimeError(
                f"Test task validation failed with exit code {exit_code}. "
                f"This indicates the MCP server or evaluation setup has issues."
            )

        console.print("[green]✓ Test task passed - setup validated[/green]")

    async def setup(self) -> None:
        """Provision Azure VM and prepare for evaluation.

        This method:
        1. Determines appropriate VM size
        2. Creates the VM
        3. Retrieves the public IP
        4. Waits for SSH to become available
        5. Installs dependencies (Docker, Python, mcpbr)
        6. Transfers configuration file
        7. Exports environment variables
        8. Runs test task to validate setup

        Raises:
            RuntimeError: If setup fails at any step.
        """
        console = Console()
        console.print("[cyan]Provisioning Azure VM...[/cyan]")

        try:
            # Determine VM size
            vm_size = self._determine_vm_size()
            console.print(f"[cyan]  VM Size: {vm_size}[/cyan]")

            # Create VM
            await self._create_vm(vm_size)

            # Get IP
            self.vm_ip = await self._get_vm_ip()
            console.print(f"[cyan]  VM IP: {self.vm_ip}[/cyan]")

            # Wait for SSH
            await self._wait_for_ssh()

            # Install dependencies
            await self._install_dependencies()

            # Transfer config
            await self._transfer_config()

            # Export environment variables
            await self._export_env_vars()

            # Run test task
            await self._run_test_task()

            console.print("[green]✓ Azure VM ready for evaluation[/green]")

        except Exception:
            self._error_occurred = True
            raise

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on Azure VM.

        Args:
            config: Harness configuration.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object.

        Raises:
            RuntimeError: If evaluation fails.
        """

        console = Console()
        console.print("[cyan]Starting remote evaluation on Azure VM...[/cyan]")

        # Build command flags
        flags = []
        if run_mcp and not run_baseline:
            flags.append("-M")
        elif run_baseline and not run_mcp:
            flags.append("-B")

        # Execute mcpbr
        cmd = f"mcpbr run -c ~/config.yaml {' '.join(flags)}"
        console.print(f"[dim]Running: {cmd}[/dim]")

        # Execute with streaming output
        _stdin, stdout, stderr = self.ssh_client.exec_command(cmd)

        # Stream output line by line
        for line in stdout:
            console.print(line.rstrip())

        # Wait for completion
        exit_code = stdout.channel.recv_exit_status()

        if exit_code != 0:
            self._error_occurred = True
            stderr_output = stderr.read().decode()
            console.print(f"[red]✗ Evaluation failed with exit code {exit_code}[/red]")
            console.print(f"[red]{stderr_output[:2000]}[/red]")
            raise RuntimeError(f"Evaluation failed: {stderr_output[:500]}")

        console.print("[green]✓ Evaluation completed successfully[/green]")

        # Download and parse results
        results = await self._download_results()
        return results

    async def _download_results(self) -> Any:
        """Download results.json from VM.

        Returns:
            EvaluationResults object parsed from JSON.

        Raises:
            FileNotFoundError: If no output directory or results.json found.
        """
        import json
        import tempfile

        from ..harness import EvaluationResults

        console = Console()
        console.print("[cyan]Downloading evaluation results...[/cyan]")

        # Find latest output directory
        exit_code, stdout, _stderr = await self._ssh_exec(
            "find ~ -maxdepth 1 -type d -name '.mcpbr_run_*' | sort -r | head -n1"
        )

        if exit_code != 0 or not stdout.strip():
            raise FileNotFoundError("No output directory found on VM")

        remote_output_dir = stdout.strip()
        results_path = f"{remote_output_dir}/results.json"

        # Download results.json
        sftp = self.ssh_client.open_sftp()

        with tempfile.NamedTemporaryFile(mode="r", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            sftp.get(results_path, temp_path)
            sftp.close()

            with open(temp_path) as f:
                results_dict = json.load(f)

            return EvaluationResults(**results_dict)
        finally:
            Path(temp_path).unlink()

    async def collect_artifacts(self, output_dir: Path) -> Path | None:
        """Download all logs and results from VM, create ZIP archive.

        Args:
            output_dir: Local directory to store downloaded artifacts.

        Returns:
            Path to ZIP archive, or None if no artifacts found.
        """
        console = Console()
        console.print("[cyan]Collecting artifacts from VM...[/cyan]")

        # Find output directory on VM
        exit_code, stdout, _stderr = await self._ssh_exec(
            "find ~ -maxdepth 1 -type d -name '.mcpbr_run_*' | sort -r | head -n1"
        )

        if exit_code != 0 or not stdout.strip():
            console.print("[yellow]⚠ No output directory found on VM[/yellow]")
            return None

        remote_output_dir = stdout.strip()

        # Create local archive directory
        local_archive_dir = output_dir
        local_archive_dir.mkdir(parents=True, exist_ok=True)

        # Recursively download
        sftp = self.ssh_client.open_sftp()
        await asyncio.to_thread(
            self._recursive_download, sftp, remote_output_dir, local_archive_dir
        )
        sftp.close()

        # Create ZIP archive
        import zipfile

        archive_path = local_archive_dir.parent / f"{local_archive_dir.name}.zip"

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _dirs, files in os.walk(local_archive_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(local_archive_dir.parent)
                    zipf.write(file_path, arcname)

        console.print(f"[green]✓ Artifacts archived: {archive_path}[/green]")
        return archive_path

    def _recursive_download(self, sftp: Any, remote_dir: str, local_dir: Path) -> None:
        """Recursively download directory via SFTP.

        Args:
            sftp: Paramiko SFTP client.
            remote_dir: Remote directory path.
            local_dir: Local directory path.
        """
        import stat

        for item in sftp.listdir_attr(remote_dir):
            remote_path = f"{remote_dir}/{item.filename}"
            local_path = local_dir / item.filename

            if stat.S_ISDIR(item.st_mode):
                local_path.mkdir(exist_ok=True)
                self._recursive_download(sftp, remote_path, local_path)
            else:
                sftp.get(remote_path, str(local_path))

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
            except Exception as e:
                console.print(f"[dim]Note: SSH close warning: {e}[/dim]")

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
                console.print(
                    f"[dim]Delete with: az vm delete -g {self.azure_config.resource_group} -n {self.vm_name} --yes[/dim]"
                )
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
        if result.returncode == 0:
            console.print("[green]✓ VM deleted[/green]")
        else:
            console.print(f"[yellow]⚠ VM deletion may have failed: {result.stderr[:200]}[/yellow]")

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run Azure health checks.

        Returns:
            Dictionary with health check results.
        """
        from .azure_health import run_azure_health_checks

        return run_azure_health_checks(self.azure_config)
