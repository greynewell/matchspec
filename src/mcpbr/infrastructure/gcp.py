"""GCP Compute Engine infrastructure provider."""

import asyncio
import ipaddress
import json
import logging
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError:
    # paramiko is optional, only needed when actually using GCP provider
    paramiko = None  # type: ignore

from rich.console import Console

from .. import __version__
from ..config import HarnessConfig
from ..run_state import RunState
from .aws import _validate_env_key, _validate_python_version
from .base import InfrastructureProvider

logger = logging.getLogger(__name__)


class GCPProvider(InfrastructureProvider):
    """GCP Compute Engine infrastructure provider.

    This provider manages the lifecycle of GCE instances for running evaluations:
    - Provisions instances with appropriate machine types
    - Manages SSH connectivity
    - Handles instance cleanup with configurable preservation policies
    """

    def __init__(self, config: HarnessConfig):
        """Initialize GCP provider.

        Args:
            config: Harness configuration with GCP settings.
        """
        self.config = config
        self.gcp_config = config.infrastructure.gcp
        self.instance_name: str | None = None
        self.instance_ip: str | None = None
        self.ssh_client: paramiko.SSHClient | None = None
        self.ssh_key_path: Path | None = None
        self._error_occurred = False

    def _determine_machine_type(self) -> str:
        """Map cpu_cores/memory_gb to GCP machine type.

        Returns:
            GCP machine type string (e.g., "e2-standard-4").
        """
        # If explicit machine_type specified, use it
        if self.gcp_config.machine_type:
            return self.gcp_config.machine_type

        cores = self.gcp_config.cpu_cores
        memory = self.gcp_config.memory_gb

        # e2-series for smaller workloads (cost-effective, up to 8 vCPUs)
        if cores <= 1 and memory <= 1:
            return "e2-micro"
        elif cores <= 2 and memory <= 8:
            return "e2-standard-2"
        elif cores <= 4 and memory <= 16:
            return "e2-standard-4"
        elif cores <= 8 and memory <= 32:
            return "e2-standard-8"
        # n2-series for larger workloads (better performance)
        elif cores <= 16 and memory <= 64:
            return "n2-standard-16"
        else:
            return "n2-standard-32"

    async def _create_instance(self, machine_type: str) -> None:
        """Create GCE instance using gcloud CLI.

        Args:
            machine_type: GCP machine type (e.g., "e2-standard-4").

        Raises:
            RuntimeError: If instance creation fails.
        """
        console = Console()

        # Generate unique instance name
        timestamp = int(time.time())
        self.instance_name = f"mcpbr-eval-{timestamp}"

        # Generate or use existing SSH key
        ssh_key_path = self.gcp_config.ssh_key_path
        if not ssh_key_path:
            ssh_key_path = Path.home() / ".ssh" / "mcpbr_gcp"
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

        # Determine SSH username (GCP uses OS Login or current username)
        self._ssh_user = os.environ.get("USER", os.environ.get("USERNAME", "mcpbr"))

        # Build instance create command
        console.print(
            f"[cyan]Creating GCE instance: {self.instance_name} ({machine_type})...[/cyan]"
        )

        image_family = self.gcp_config.image_family
        image_project = self.gcp_config.image_project
        disk_gb = self.gcp_config.disk_gb
        disk_type = self.gcp_config.disk_type
        zone = self.gcp_config.zone

        instance_create_cmd = [
            "gcloud",
            "compute",
            "instances",
            "create",
            self.instance_name,
            "--zone",
            zone,
            "--machine-type",
            machine_type,
            "--image-family",
            image_family,
            "--image-project",
            image_project,
            "--boot-disk-size",
            f"{disk_gb}GB",
            "--boot-disk-type",
            disk_type,
            "--format",
            "json",
        ]

        # Add project if specified
        if self.gcp_config.project_id:
            instance_create_cmd.extend(["--project", self.gcp_config.project_id])

        # Add SSH key metadata
        pub_key_path = f"{ssh_key_path}.pub"
        if Path(pub_key_path).exists():
            pub_key_content = Path(pub_key_path).read_text().strip()
            metadata_value = f"{self._ssh_user}:{pub_key_content}"
            instance_create_cmd.extend(["--metadata", f"ssh-keys={metadata_value}"])

        # Add preemptible/spot flags
        if self.gcp_config.spot:
            instance_create_cmd.append("--provisioning-model=SPOT")
            instance_create_cmd.append("--instance-termination-action=STOP")
        elif self.gcp_config.preemptible:
            instance_create_cmd.append("--preemptible")

        # Add labels
        if self.gcp_config.labels:
            label_str = ",".join(f"{k}={v}" for k, v in self.gcp_config.labels.items())
            instance_create_cmd.extend(["--labels", label_str])

        # Add service account
        if self.gcp_config.service_account:
            instance_create_cmd.extend(["--service-account", self.gcp_config.service_account])

        # Add scopes
        if self.gcp_config.scopes:
            instance_create_cmd.extend(["--scopes", ",".join(self.gcp_config.scopes)])

        # Add network tags for firewall (allow SSH)
        instance_create_cmd.extend(["--tags", "mcpbr-ssh"])

        result = subprocess.run(
            instance_create_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"GCE instance creation failed: {result.stderr}")

        console.print(f"[green]  Instance created: {self.instance_name}[/green]")

        # Ensure firewall rule exists for SSH access
        await self._ensure_ssh_firewall_rule()

    async def _ensure_ssh_firewall_rule(self) -> None:
        """Ensure a firewall rule exists to allow SSH access to mcpbr instances.

        Creates the rule if it does not already exist.
        """
        console = Console()
        rule_name = "mcpbr-allow-ssh"

        # Check if rule already exists
        check_cmd = [
            "gcloud",
            "compute",
            "firewall-rules",
            "describe",
            rule_name,
            "--format",
            "json",
        ]
        if self.gcp_config.project_id:
            check_cmd.extend(["--project", self.gcp_config.project_id])

        result = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            # Rule already exists
            return

        # Create firewall rule — restrict to caller's public IP (required)
        console.print("[cyan]Creating SSH firewall rule...[/cyan]")
        try:
            ip_result = subprocess.run(
                ["curl", "-s", "--max-time", "5", "https://ifconfig.me"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if ip_result.returncode == 0 and ip_result.stdout.strip():
                ip_str = ip_result.stdout.strip()
                ipaddress.ip_address(ip_str)  # Validate it's an IP
                source_range = f"{ip_str}/32"
                console.print(f"[dim]  Restricting SSH to caller IP: {source_range}[/dim]")
            else:
                raise RuntimeError("curl returned no output")
        except Exception as exc:
            raise RuntimeError(
                "Could not determine your public IP address for SSH firewall rule. "
                "Set the source range manually or check your network connection."
            ) from exc

        create_cmd = [
            "gcloud",
            "compute",
            "firewall-rules",
            "create",
            rule_name,
            "--allow",
            "tcp:22",
            "--target-tags",
            "mcpbr-ssh",
            "--source-ranges",
            source_range,
            "--description",
            "Allow SSH access for mcpbr evaluation instances",
        ]
        if self.gcp_config.project_id:
            create_cmd.extend(["--project", self.gcp_config.project_id])

        result = subprocess.run(
            create_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            console.print(
                f"[yellow]  Firewall rule creation warning: {result.stderr[:300]}[/yellow]"
            )
        else:
            console.print("[green]  SSH firewall rule created[/green]")

    async def _get_public_ip(self) -> str:
        """Get instance public IP address.

        Returns:
            Public IP address of the instance.

        Raises:
            RuntimeError: If IP retrieval fails.
        """
        result = subprocess.run(
            [
                "gcloud",
                "compute",
                "instances",
                "describe",
                self.instance_name,
                "--zone",
                self.gcp_config.zone,
                "--format",
                "json(networkInterfaces[0].accessConfigs[0].natIP)",
            ]
            + (["--project", self.gcp_config.project_id] if self.gcp_config.project_id else []),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get instance IP: {result.stderr}")

        try:
            data = json.loads(result.stdout)
            ip = data["networkInterfaces"][0]["accessConfigs"][0]["natIP"]
            return ip
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise RuntimeError(f"Failed to parse instance IP from response: {e}") from e

    async def _wait_for_ssh(self, timeout: int = 300) -> None:
        """Wait for SSH to become available.

        Args:
            timeout: Maximum time to wait in seconds.

        Raises:
            RuntimeError: If SSH connection fails within timeout.
        """
        if paramiko is None:
            raise RuntimeError(
                "paramiko is required for GCP provider. Install with: pip install paramiko"
            )

        console = Console()
        console.print("[cyan]Waiting for SSH to become available...[/cyan]")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Create SSH client
                self.ssh_client = paramiko.SSHClient()
                # AutoAddPolicy is used because we just provisioned this instance and
                # its host key is not yet in known_hosts. This is acceptable for
                # automated provisioning where MITM risk is low, but enterprise
                # deployments may want to use RejectPolicy with pre-seeded keys.
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh_client.connect(
                    self.instance_ip,
                    username=self._ssh_user,
                    key_filename=str(self.ssh_key_path),
                    timeout=10,
                )
                console.print("[green]  SSH connection established[/green]")
                return
            except Exception:
                # Close failed client
                if self.ssh_client:
                    self.ssh_client.close()
                    self.ssh_client = None
                # Wait and retry
                await asyncio.sleep(5)

        raise RuntimeError(
            f"SSH connection failed after {timeout}s. "
            f"Instance may not be ready or network issues exist."
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
        """Install Docker, Python, Node.js, and mcpbr on instance."""
        console = Console()
        py_ver = self.gcp_config.python_version

        # Validate python version before interpolating into shell commands
        _validate_python_version(py_ver)

        # Step 1: System packages + Docker
        console.print("[cyan]Installing system packages and Docker...[/cyan]")
        step1_cmd = (
            "export DEBIAN_FRONTEND=noninteractive && "
            "sudo apt-get update -qq && "
            "sudo apt-get install -y -qq curl software-properties-common && "
            "curl -fsSL https://get.docker.com -o get-docker.sh && "
            "sudo sh get-docker.sh && "
            "sudo usermod -aG docker $USER && "
            "sudo systemctl start docker && "
            "sudo systemctl enable docker"
        )
        exit_code, _stdout, stderr = await self._ssh_exec(step1_cmd, timeout=600)
        if exit_code != 0:
            console.print(
                f"[yellow]  System packages/Docker install issues: {stderr[:300]}[/yellow]"
            )
        else:
            console.print("[green]  Docker installed[/green]")

        # Step 2: Python (from deadsnakes PPA if needed)
        console.print(f"[cyan]Installing Python {py_ver}...[/cyan]")
        step2_cmd = (
            "export DEBIAN_FRONTEND=noninteractive && "
            f"sudo add-apt-repository -y ppa:deadsnakes/ppa && "
            "sudo apt-get update -qq && "
            f"sudo apt-get install -y -qq python{py_ver} python{py_ver}-venv "
            f"python{py_ver}-distutils && "
            f"curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python{py_ver}"
        )
        exit_code, _stdout, stderr = await self._ssh_exec(step2_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]  Python install issues: {stderr[:300]}[/yellow]")
        else:
            console.print(f"[green]  Python {py_ver} installed[/green]")

        # Step 3: Node.js (for npx / MCP servers)
        console.print("[cyan]Installing Node.js...[/cyan]")
        step3_cmd = (
            "curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && "
            "sudo apt-get install -y -qq nodejs"
        )
        exit_code, _stdout, stderr = await self._ssh_exec(step3_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]  Node.js install issues: {stderr[:300]}[/yellow]")
        else:
            console.print("[green]  Node.js installed[/green]")

        # Step 4: Install mcpbr (pin to local version)
        console.print(f"[cyan]Installing mcpbr=={__version__}...[/cyan]")
        step4_cmd = f"python{py_ver} -m pip install mcpbr=={__version__}"
        exit_code, _stdout, stderr = await self._ssh_exec(step4_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]  mcpbr install issues: {stderr[:300]}[/yellow]")
        else:
            console.print("[green]  mcpbr installed[/green]")

    async def _transfer_config(self) -> None:
        """Transfer configuration file to instance via SFTP."""
        console = Console()
        console.print("[cyan]Transferring configuration...[/cyan]")

        # Create temporary config file
        import tempfile

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Serialize config to YAML (convert Pydantic model to dict)
            config_dict = self.config.model_dump()
            # Override infrastructure mode to local -- the instance IS the infrastructure
            if "infrastructure" in config_dict:
                config_dict["infrastructure"]["mode"] = "local"
            yaml.dump(config_dict, f)
            temp_config_path = f.name

        sftp = None
        try:
            # Upload via SFTP
            sftp = self.ssh_client.open_sftp()
            remote_home = f"/home/{self._ssh_user}"
            sftp.put(temp_config_path, f"{remote_home}/config.yaml")
            console.print("[green]  Configuration transferred[/green]")
        finally:
            if sftp:
                sftp.close()
            Path(temp_config_path).unlink()

    async def _export_env_vars(self) -> None:
        """Export environment variables to instance."""
        console = Console()
        console.print("[cyan]Exporting environment variables...[/cyan]")

        env_vars = {}
        for key in self.gcp_config.env_keys_to_export:
            _validate_env_key(key)
            value = os.environ.get(key)
            if value:
                env_vars[key] = value
            else:
                console.print(f"[yellow]  Environment variable {key} not found locally[/yellow]")

        if not env_vars:
            console.print("[yellow]  No environment variables to export[/yellow]")
            return

        # Write to .bashrc and .profile using shlex.quote to prevent shell injection
        env_commands = [f"export {k}={shlex.quote(v)}" for k, v in env_vars.items()]
        bashrc_append = "\n".join(env_commands)

        # Use a here-document to safely write env vars without shell expansion
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.bashrc\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.profile\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)

        console.print(f"[green]  Exported {len(env_vars)} environment variables[/green]")

    def _mcpbr_cmd(self) -> str:
        """Return the mcpbr command for the configured Python version."""
        py_ver = self.gcp_config.python_version
        return f"python{py_ver} -m mcpbr"

    def _wrap_cmd(self, cmd: str) -> str:
        """Wrap a command with bash login shell and docker group access.

        SSH exec_command uses /bin/sh by default, which doesn't source
        .bashrc. This wraps commands to run in a bash login shell with
        env vars loaded and docker group access (via sg).
        """
        return f"bash -lc {shlex.quote(f'sg docker -c {shlex.quote(cmd)}')}"

    async def _run_test_task(self) -> None:
        """Run single test task to validate setup."""
        console = Console()
        console.print("[cyan]Running test task to validate setup...[/cyan]")

        # Run mcpbr with sample_size=1, max_concurrent=1
        test_cmd = self._wrap_cmd(
            f"{self._mcpbr_cmd()} run -c ~/config.yaml -M -n 1 --skip-preflight"
        )

        exit_code, stdout, stderr = await self._ssh_exec(test_cmd, timeout=600)

        if exit_code != 0:
            console.print("[red]  Test task failed![/red]")
            console.print(f"[red]STDOUT:[/red]\n{stdout[:1000]}")
            console.print(f"[red]STDERR:[/red]\n{stderr[:1000]}")
            raise RuntimeError(
                f"Test task validation failed with exit code {exit_code}. "
                f"This indicates the MCP server or evaluation setup has issues."
            )

        console.print("[green]  Test task passed - setup validated[/green]")

    @staticmethod
    def get_run_status(state: "RunState") -> dict:
        """Get the status of a GCE instance run.

        Args:
            state: RunState with instance_name and zone.

        Returns:
            Dict with status information from gcloud compute instances describe.
        """
        cmd = [
            "gcloud",
            "compute",
            "instances",
            "describe",
            state.vm_name,
            "--zone",
            state.location,
            "--format",
            "json",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "status": "unknown"}
        return json.loads(result.stdout)

    @staticmethod
    def get_ssh_command(state: "RunState") -> str:
        """Get SSH command to connect to GCE instance.

        Args:
            state: RunState with vm_ip and ssh_key_path.

        Returns:
            SSH command string.
        """
        user = os.environ.get("USER", os.environ.get("USERNAME", "mcpbr"))
        return f"ssh -i {state.ssh_key_path} {user}@{state.vm_ip}"

    @staticmethod
    def stop_run(state: "RunState") -> None:
        """Stop a GCE instance.

        Args:
            state: RunState with instance name and zone.
        """
        subprocess.run(
            [
                "gcloud",
                "compute",
                "instances",
                "stop",
                state.vm_name,
                "--zone",
                state.location,
            ],
            check=True,
            timeout=300,
        )

    async def setup(self) -> None:
        """Provision GCE instance and prepare for evaluation.

        This method:
        1. Determines appropriate machine type
        2. Creates the instance
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
        console.print("[cyan]Provisioning GCE instance...[/cyan]")

        try:
            # Determine machine type
            machine_type = self._determine_machine_type()
            console.print(f"[cyan]  Machine Type: {machine_type}[/cyan]")

            # Create instance
            await self._create_instance(machine_type)

            # Get IP
            self.instance_ip = await self._get_public_ip()
            console.print(f"[cyan]  Instance IP: {self.instance_ip}[/cyan]")

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

            # Save run state for monitoring
            from datetime import datetime

            run_state = RunState(
                vm_name=self.instance_name,
                vm_ip=self.instance_ip,
                resource_group=self.gcp_config.project_id or "",
                location=self.gcp_config.zone,
                ssh_key_path=str(self.ssh_key_path),
                config_path=str(self.config.config_path)
                if hasattr(self.config, "config_path")
                else "",
                started_at=datetime.now().isoformat(),
            )
            state_dir = Path.home() / ".mcpbr"
            run_state.save(state_dir / "run_state.json")

            console.print("[green]  GCE instance ready for evaluation[/green]")

        except Exception:
            self._error_occurred = True
            raise

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on GCE instance.

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
        console.print("[cyan]Starting remote evaluation on GCE instance...[/cyan]")

        # Build command flags
        flags = []
        if run_mcp and not run_baseline:
            flags.append("-M")
        elif run_baseline and not run_mcp:
            flags.append("-B")

        # Forward task_ids from config (merged from CLI --task/-t flags)
        if self.config.task_ids:
            for task_id in self.config.task_ids:
                flags.append(f"-t {shlex.quote(task_id)}")

        # Execute mcpbr
        raw_cmd = f"{self._mcpbr_cmd()} run -c ~/config.yaml {' '.join(flags)}"
        console.print(f"[dim]Running: {raw_cmd}[/dim]")

        # Wrap with bash login shell + docker group access.
        # No per-read timeout: evaluations can run for hours.
        cmd = self._wrap_cmd(raw_cmd)
        _stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
        stdout.channel.settimeout(None)

        # Stream output line by line
        for line in stdout:
            console.print(line.rstrip())

        # Wait for completion
        exit_code = stdout.channel.recv_exit_status()

        if exit_code != 0:
            self._error_occurred = True
            stderr_output = stderr.read().decode()
            console.print(f"[red]  Evaluation failed with exit code {exit_code}[/red]")
            console.print(f"[red]{stderr_output[:2000]}[/red]")
            raise RuntimeError(f"Evaluation failed: {stderr_output[:500]}")

        console.print("[green]  Evaluation completed successfully[/green]")

        # Download and parse results
        results = await self._download_results()
        return results

    async def _download_results(self) -> Any:
        """Download results.json from instance.

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
            raise FileNotFoundError("No output directory found on instance")

        remote_output_dir = stdout.strip()
        results_path = f"{remote_output_dir}/results.json"

        # Download results.json
        sftp = self.ssh_client.open_sftp()

        with tempfile.NamedTemporaryFile(mode="r", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            sftp.get(results_path, temp_path)

            with open(temp_path) as f:
                results_dict = json.load(f)

            return EvaluationResults(**results_dict)
        finally:
            sftp.close()
            Path(temp_path).unlink()

    async def collect_artifacts(self, output_dir: Path) -> Path | None:
        """Download all logs and results from instance, create ZIP archive.

        Args:
            output_dir: Local directory to store downloaded artifacts.

        Returns:
            Path to ZIP archive, or None if no artifacts found.
        """
        console = Console()
        console.print("[cyan]Collecting artifacts from instance...[/cyan]")

        # Find output directory on instance
        exit_code, stdout, _stderr = await self._ssh_exec(
            "find ~ -maxdepth 1 -type d -name '.mcpbr_run_*' | sort -r | head -n1"
        )

        if exit_code != 0 or not stdout.strip():
            console.print("[yellow]  No output directory found on instance[/yellow]")
            return None

        remote_output_dir = stdout.strip()

        # Create local archive directory
        local_archive_dir = output_dir
        local_archive_dir.mkdir(parents=True, exist_ok=True)

        # Recursively download
        sftp = self.ssh_client.open_sftp()
        try:
            await asyncio.to_thread(
                self._recursive_download, sftp, remote_output_dir, local_archive_dir
            )
        finally:
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

        console.print(f"[green]  Artifacts archived: {archive_path}[/green]")
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
        """Delete GCE instance.

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
        if not self.instance_name:
            return

        # Determine if should cleanup
        should_cleanup = force or (
            self.gcp_config.auto_shutdown
            and not (self._error_occurred and self.gcp_config.preserve_on_error)
        )

        if not should_cleanup:
            console.print(f"[yellow]Instance preserved: {self.instance_name}[/yellow]")
            if self.instance_ip and self.ssh_key_path:
                console.print(
                    f"[dim]SSH: ssh -i {self.ssh_key_path} "
                    f"{self._ssh_user}@{self.instance_ip}[/dim]"
                )
                console.print(
                    f"[dim]Delete with: gcloud compute instances delete "
                    f"{self.instance_name} --zone={self.gcp_config.zone} --quiet[/dim]"
                )
            return

        # Delete instance
        console.print(f"[cyan]Deleting instance: {self.instance_name}...[/cyan]")
        delete_cmd = [
            "gcloud",
            "compute",
            "instances",
            "delete",
            self.instance_name,
            "--zone",
            self.gcp_config.zone,
            "--quiet",
        ]
        if self.gcp_config.project_id:
            delete_cmd.extend(["--project", self.gcp_config.project_id])

        result = subprocess.run(
            delete_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            console.print("[green]  Instance deleted[/green]")
        else:
            console.print(
                f"[yellow]  Instance deletion may have failed: {result.stderr[:200]}[/yellow]"
            )

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run GCP health checks.

        Returns:
            Dictionary with health check results.
        """
        from .gcp_health import run_gcp_health_checks

        return run_gcp_health_checks(self.gcp_config)
