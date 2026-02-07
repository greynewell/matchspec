"""AWS EC2 infrastructure provider."""

import asyncio
import ipaddress
import json
import logging
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

try:
    import paramiko
except ImportError:
    # paramiko is optional, only needed when actually using AWS provider
    paramiko = None  # type: ignore

from rich.console import Console

from .. import __version__
from ..config import HarnessConfig
from .base import InfrastructureProvider

logger = logging.getLogger(__name__)

# Regex for valid Python version strings (e.g., "3.11", "3.12")
_PYTHON_VERSION_RE = re.compile(r"^\d+\.\d+$")

# Regex for valid environment variable names (POSIX)
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_python_version(version: str) -> None:
    """Validate python_version is a safe version string (e.g. '3.11').

    Raises:
        ValueError: If the version string contains unsafe characters.
    """
    if not _PYTHON_VERSION_RE.match(version):
        raise ValueError(
            f"Invalid python_version: {version!r}. Must be a version like '3.11' or '3.12'."
        )


def _validate_env_key(key: str) -> None:
    """Validate an environment variable name is safe for shell interpolation.

    Raises:
        ValueError: If the key contains unsafe characters.
    """
    if not _ENV_KEY_RE.match(key):
        raise ValueError(
            f"Invalid environment variable name: {key!r}. Must match [A-Za-z_][A-Za-z0-9_]*."
        )


class AWSProvider(InfrastructureProvider):
    """AWS EC2 infrastructure provider.

    This provider manages the lifecycle of AWS EC2 instances for running evaluations:
    - Provisions instances with appropriate sizing
    - Manages SSH connectivity
    - Handles instance cleanup with configurable preservation policies
    """

    def __init__(self, config: HarnessConfig):
        """Initialize AWS provider.

        Args:
            config: Harness configuration with AWS settings.
        """
        self.config = config
        self.aws_config = config.infrastructure.aws
        self.instance_id: str | None = None
        self.instance_ip: str | None = None
        self.ssh_client: paramiko.SSHClient | None = None
        self.ssh_key_path: Path | None = None
        self._error_occurred = False

    @staticmethod
    def _get_ssh_cidr() -> str:
        """Get CIDR for SSH security group rule, restricted to caller's IP.

        Raises:
            RuntimeError: If the caller's public IP cannot be determined. Never
                falls back to 0.0.0.0/0.
        """
        try:
            result = subprocess.run(
                ["curl", "-s", "--max-time", "5", "https://ifconfig.me"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                ip_str = result.stdout.strip()
                # Validate it's actually an IP address
                ipaddress.ip_address(ip_str)
                return f"{ip_str}/32"
        except (ValueError, Exception) as exc:
            logger.debug("IP detection failed: %s", exc)

        raise RuntimeError(
            "Could not determine your public IP address for SSH security group. "
            "Set the SSH CIDR manually or check your network connection."
        )

    def _determine_instance_type(self) -> str:
        """Map cpu_cores/memory_gb to AWS EC2 instance type.

        Returns:
            AWS instance type string (e.g., "t3.large").
        """
        # If explicit instance type specified, use it
        if self.aws_config.instance_type:
            return self.aws_config.instance_type

        cores = self.aws_config.cpu_cores
        memory = self.aws_config.memory_gb

        # Map cores/memory to instance types
        # t3 family: burstable general purpose (up to 8 vCPUs)
        # m5 family: general purpose (larger instances, 16+ vCPUs)
        if cores <= 1 and memory <= 1:
            return "t3.micro"
        elif cores <= 1 and memory <= 2:
            return "t3.small"
        elif cores <= 2 and memory <= 4:
            return "t3.medium"
        elif cores <= 2 and memory <= 8:
            return "t3.large"
        elif cores <= 4 and memory <= 16:
            return "t3.xlarge"
        elif cores <= 8 and memory <= 32:
            return "t3.2xlarge"
        elif cores <= 16 and memory <= 64:
            return "m5.4xlarge"
        else:
            return "m5.4xlarge"

    async def _create_instance(self, instance_type: str) -> None:
        """Create AWS EC2 instance using aws CLI.

        Args:
            instance_type: AWS instance type (e.g., "t3.large").

        Raises:
            RuntimeError: If instance creation fails.
        """
        console = Console()

        # Generate or use existing SSH key
        ssh_key_name = self.aws_config.key_name
        ssh_key_path = self.aws_config.ssh_key_path
        if not ssh_key_path:
            ssh_key_path = Path.home() / ".ssh" / "mcpbr_aws"
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
                    timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"SSH key generation failed: {result.stderr}")

        self.ssh_key_path = ssh_key_path

        # Import key pair to AWS if key_name not already provided
        if not ssh_key_name:
            timestamp = int(time.time())
            ssh_key_name = f"mcpbr-eval-{timestamp}"
            console.print(f"[cyan]Importing SSH key pair: {ssh_key_name}...[/cyan]")

            pub_key_path = f"{ssh_key_path}.pub"
            result = subprocess.run(
                [
                    "aws",
                    "ec2",
                    "import-key-pair",
                    "--key-name",
                    ssh_key_name,
                    "--public-key-material",
                    f"fileb://{pub_key_path}",
                    "--region",
                    self.aws_config.region,
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                # Key may already exist, try to continue
                if "InvalidKeyPair.Duplicate" not in result.stderr:
                    raise RuntimeError(f"Key pair import failed: {result.stderr}")
                console.print(f"[dim]Key pair {ssh_key_name} already exists, reusing[/dim]")

        # Determine AMI (default to Ubuntu 22.04 in the specified region)
        ami_id = self.aws_config.ami_id
        if not ami_id:
            console.print("[cyan]Looking up latest Ubuntu 22.04 AMI...[/cyan]")
            result = subprocess.run(
                [
                    "aws",
                    "ec2",
                    "describe-images",
                    "--region",
                    self.aws_config.region,
                    "--owners",
                    "099720109477",
                    "--filters",
                    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
                    "Name=state,Values=available",
                    "--query",
                    "sort_by(Images, &CreationDate)[-1].ImageId",
                    "--output",
                    "text",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            if result.returncode != 0 or not result.stdout.strip():
                raise RuntimeError(
                    f"Failed to find Ubuntu 22.04 AMI in {self.aws_config.region}: {result.stderr}"
                )
            ami_id = result.stdout.strip()
            console.print(f"[dim]Using AMI: {ami_id}[/dim]")

        # Create security group for SSH access
        timestamp = int(time.time())
        sg_name = f"mcpbr-eval-{timestamp}"
        console.print(f"[cyan]Creating security group: {sg_name}...[/cyan]")

        result = subprocess.run(
            [
                "aws",
                "ec2",
                "create-security-group",
                "--group-name",
                sg_name,
                "--description",
                "mcpbr evaluation instance SSH access",
                "--region",
                self.aws_config.region,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Security group creation failed: {result.stderr}")

        sg_data = json.loads(result.stdout)
        sg_id = sg_data["GroupId"]

        # Authorize SSH ingress (port 22)
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "authorize-security-group-ingress",
                "--group-id",
                sg_id,
                "--protocol",
                "tcp",
                "--port",
                "22",
                "--cidr",
                self._get_ssh_cidr(),
                "--region",
                self.aws_config.region,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            console.print(
                f"[yellow]Warning: Could not authorize SSH ingress: {result.stderr[:200]}[/yellow]"
            )

        # Create instance
        console.print(
            f"[cyan]Creating EC2 instance: {instance_type} in {self.aws_config.region}...[/cyan]"
        )
        run_cmd = [
            "aws",
            "ec2",
            "run-instances",
            "--image-id",
            ami_id,
            "--instance-type",
            instance_type,
            "--key-name",
            ssh_key_name,
            "--security-group-ids",
            sg_id,
            "--region",
            self.aws_config.region,
            "--block-device-mappings",
            json.dumps(
                [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {
                            "VolumeSize": self.aws_config.disk_gb,
                            "VolumeType": "gp3",
                            "DeleteOnTermination": True,
                        },
                    }
                ]
            ),
            "--tag-specifications",
            json.dumps(
                [
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": "Name", "Value": f"mcpbr-eval-{timestamp}"},
                            {"Key": "CreatedBy", "Value": "mcpbr"},
                        ],
                    }
                ]
            ),
            "--count",
            "1",
            "--output",
            "json",
        ]

        if self.aws_config.subnet_id:
            run_cmd.extend(["--subnet-id", self.aws_config.subnet_id])

        if self.aws_config.iam_instance_profile:
            run_cmd.extend(
                ["--iam-instance-profile", f"Name={self.aws_config.iam_instance_profile}"]
            )

        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"EC2 instance creation failed: {result.stderr}")

        instance_data = json.loads(result.stdout)
        self.instance_id = instance_data["Instances"][0]["InstanceId"]
        self._security_group_id = sg_id
        self._key_name = ssh_key_name

        console.print(f"[green]Instance created: {self.instance_id}[/green]")

        # Wait for instance to be running
        console.print("[cyan]Waiting for instance to enter running state...[/cyan]")
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "wait",
                "instance-running",
                "--instance-ids",
                self.instance_id,
                "--region",
                self.aws_config.region,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Instance failed to reach running state: {result.stderr}")

        console.print(f"[green]Instance {self.instance_id} is running[/green]")

    async def _get_public_ip(self) -> str:
        """Get EC2 instance public IP address.

        Returns:
            Public IP address of the instance.

        Raises:
            RuntimeError: If IP retrieval fails.
        """
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "describe-instances",
                "--instance-ids",
                self.instance_id,
                "--region",
                self.aws_config.region,
                "--query",
                "Reservations[0].Instances[0].PublicIpAddress",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get instance IP: {result.stderr}")

        ip = result.stdout.strip()
        if not ip or ip == "None":
            raise RuntimeError(
                f"Instance {self.instance_id} has no public IP. "
                "Ensure the instance is in a subnet with auto-assign public IP enabled, "
                "or specify a subnet_id with public IP assignment."
            )
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
                "paramiko is required for AWS provider. Install with: pip install paramiko"
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
                    username="ubuntu",
                    key_filename=str(self.ssh_key_path),
                    timeout=10,
                )
                console.print("[green]SSH connection established[/green]")
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
            "Instance may not be ready or security group may not allow SSH."
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
        """Install Docker, Python, Node.js, and mcpbr on EC2 instance."""
        console = Console()
        py_ver = self.aws_config.python_version

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
            console.print(f"[yellow]System packages/Docker install issues: {stderr[:300]}[/yellow]")
        else:
            console.print("[green]Docker installed[/green]")

        # Step 2: Python (from deadsnakes PPA if needed)
        console.print(f"[cyan]Installing Python {py_ver}...[/cyan]")
        step2_cmd = (
            "export DEBIAN_FRONTEND=noninteractive && "
            f"sudo add-apt-repository -y ppa:deadsnakes/ppa && "
            "sudo apt-get update -qq && "
            f"sudo apt-get install -y -qq python{py_ver} python{py_ver}-venv python{py_ver}-distutils && "
            f"curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python{py_ver}"
        )
        exit_code, _stdout, stderr = await self._ssh_exec(step2_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]Python install issues: {stderr[:300]}[/yellow]")
        else:
            console.print(f"[green]Python {py_ver} installed[/green]")

        # Step 3: Node.js (for npx / MCP servers)
        console.print("[cyan]Installing Node.js...[/cyan]")
        step3_cmd = (
            "curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && "
            "sudo apt-get install -y -qq nodejs"
        )
        exit_code, _stdout, stderr = await self._ssh_exec(step3_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]Node.js install issues: {stderr[:300]}[/yellow]")
        else:
            console.print("[green]Node.js installed[/green]")

        # Step 4: Install mcpbr (pin to local version)
        console.print(f"[cyan]Installing mcpbr=={__version__}...[/cyan]")
        step4_cmd = f"python{py_ver} -m pip install mcpbr=={__version__}"
        exit_code, _stdout, stderr = await self._ssh_exec(step4_cmd, timeout=300)
        if exit_code != 0:
            console.print(f"[yellow]mcpbr install issues: {stderr[:300]}[/yellow]")
        else:
            console.print("[green]mcpbr installed[/green]")

    async def _transfer_config(self) -> None:
        """Transfer configuration file to EC2 instance via SFTP."""
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
            sftp.put(temp_config_path, "/home/ubuntu/config.yaml")
            console.print("[green]Configuration transferred[/green]")
        finally:
            if sftp:
                sftp.close()
            Path(temp_config_path).unlink()

    async def _export_env_vars(self) -> None:
        """Export environment variables to EC2 instance."""
        console = Console()
        console.print("[cyan]Exporting environment variables...[/cyan]")

        env_vars = {}
        for key in self.aws_config.env_keys_to_export:
            _validate_env_key(key)
            value = os.environ.get(key)
            if value:
                env_vars[key] = value
            else:
                console.print(f"[yellow]Environment variable {key} not found locally[/yellow]")

        if not env_vars:
            console.print("[yellow]No environment variables to export[/yellow]")
            return

        # Write to .bashrc and .profile using shlex.quote to prevent shell injection
        env_commands = [f"export {k}={shlex.quote(v)}" for k, v in env_vars.items()]
        bashrc_append = "\n".join(env_commands)

        # Use a here-document to safely write env vars without shell expansion
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.bashrc\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)
        heredoc_cmd = f"cat << 'MCPBR_ENV_EOF' >> ~/.profile\n{bashrc_append}\nMCPBR_ENV_EOF"
        await self._ssh_exec(heredoc_cmd)

        console.print(f"[green]Exported {len(env_vars)} environment variables[/green]")

    def _mcpbr_cmd(self) -> str:
        """Return the mcpbr command for the configured Python version."""
        py_ver = self.aws_config.python_version
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
            console.print("[red]Test task failed![/red]")
            console.print(f"[red]STDOUT:[/red]\n{stdout[:1000]}")
            console.print(f"[red]STDERR:[/red]\n{stderr[:1000]}")
            raise RuntimeError(
                f"Test task validation failed with exit code {exit_code}. "
                f"This indicates the MCP server or evaluation setup has issues."
            )

        console.print("[green]Test task passed - setup validated[/green]")

    async def setup(self) -> None:
        """Provision AWS EC2 instance and prepare for evaluation.

        This method:
        1. Determines appropriate instance type
        2. Creates the EC2 instance
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
        console.print("[cyan]Provisioning AWS EC2 instance...[/cyan]")

        try:
            # Determine instance type
            instance_type = self._determine_instance_type()
            console.print(f"[cyan]  Instance Type: {instance_type}[/cyan]")

            # Create instance
            await self._create_instance(instance_type)

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

            console.print("[green]AWS EC2 instance ready for evaluation[/green]")

        except Exception:
            self._error_occurred = True
            raise

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on AWS EC2 instance.

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
        console.print("[cyan]Starting remote evaluation on AWS EC2 instance...[/cyan]")

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
            console.print(f"[red]Evaluation failed with exit code {exit_code}[/red]")
            console.print(f"[red]{stderr_output[:2000]}[/red]")
            raise RuntimeError(f"Evaluation failed: {stderr_output[:500]}")

        console.print("[green]Evaluation completed successfully[/green]")

        # Download and parse results
        results = await self._download_results()
        return results

    async def _download_results(self) -> Any:
        """Download results.json from EC2 instance.

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
        """Download all logs and results from EC2 instance, create ZIP archive.

        Args:
            output_dir: Local directory to store downloaded artifacts.

        Returns:
            Path to ZIP archive, or None if no artifacts found.
        """
        console = Console()
        console.print("[cyan]Collecting artifacts from EC2 instance...[/cyan]")

        # Find output directory on instance
        exit_code, stdout, _stderr = await self._ssh_exec(
            "find ~ -maxdepth 1 -type d -name '.mcpbr_run_*' | sort -r | head -n1"
        )

        if exit_code != 0 or not stdout.strip():
            console.print("[yellow]No output directory found on instance[/yellow]")
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

        console.print(f"[green]Artifacts archived: {archive_path}[/green]")
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
        """Terminate AWS EC2 instance and clean up resources.

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
        if not self.instance_id:
            return

        # Determine if should cleanup
        should_cleanup = force or (
            self.aws_config.auto_shutdown
            and not (self._error_occurred and self.aws_config.preserve_on_error)
        )

        if not should_cleanup:
            console.print(f"[yellow]Instance preserved: {self.instance_id}[/yellow]")
            if self.instance_ip and self.ssh_key_path:
                console.print(
                    f"[dim]SSH: ssh -i {self.ssh_key_path} ubuntu@{self.instance_ip}[/dim]"
                )
                console.print(
                    f"[dim]Terminate with: aws ec2 terminate-instances "
                    f"--instance-ids {self.instance_id} "
                    f"--region {self.aws_config.region}[/dim]"
                )
            return

        # Terminate instance
        console.print(f"[cyan]Terminating instance: {self.instance_id}...[/cyan]")
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "terminate-instances",
                "--instance-ids",
                self.instance_id,
                "--region",
                self.aws_config.region,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode == 0:
            console.print("[green]Instance terminated[/green]")
        else:
            console.print(
                f"[yellow]Instance termination may have failed: {result.stderr[:200]}[/yellow]"
            )

        # Clean up security group (wait for instance to terminate first)
        sg_id = getattr(self, "_security_group_id", None)
        if sg_id:
            console.print(
                "[cyan]Waiting for instance termination to clean up security group...[/cyan]"
            )
            result = subprocess.run(
                [
                    "aws",
                    "ec2",
                    "wait",
                    "instance-terminated",
                    "--instance-ids",
                    self.instance_id,
                    "--region",
                    self.aws_config.region,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )

            result = subprocess.run(
                [
                    "aws",
                    "ec2",
                    "delete-security-group",
                    "--group-id",
                    sg_id,
                    "--region",
                    self.aws_config.region,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                console.print("[green]Security group deleted[/green]")
            else:
                console.print(
                    f"[yellow]Security group cleanup may have failed: {result.stderr[:200]}[/yellow]"
                )

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run AWS health checks.

        Validates:
        1. AWS CLI is installed
        2. AWS credentials are configured
        3. Instance type is valid for the region

        Returns:
            Dictionary with health check results.
        """
        results: dict[str, Any] = {
            "aws_cli": False,
            "authenticated": False,
            "instance_type_valid": False,
            "errors": [],
            "warnings": [],
        }

        # Check 1: AWS CLI installed
        cli_ok, cli_msg = _check_aws_cli_installed()
        results["aws_cli"] = cli_ok
        if not cli_ok:
            results["errors"].append(f"AWS CLI: {cli_msg}")
            return results  # Can't proceed without CLI

        # Check 2: Authenticated
        auth_ok, auth_msg = _check_aws_authenticated()
        results["authenticated"] = auth_ok
        if not auth_ok:
            results["errors"].append(f"Authentication: {auth_msg}")
            return results  # Can't proceed without auth

        # Check 3: Instance type availability
        instance_type = self._determine_instance_type()
        type_ok, type_msg = _check_instance_type_available(self.aws_config.region, instance_type)
        results["instance_type_valid"] = type_ok
        if not type_ok:
            # Instance type check is non-fatal (warning, not error)
            results["warnings"].append(f"Instance type: {type_msg}")

        return results


def _check_aws_cli_installed() -> tuple[bool, str]:
    """Check if AWS CLI is installed.

    Returns:
        Tuple of (success, message).
    """
    try:
        import platform as _platform

        command = "where" if _platform.system() == "Windows" else "which"
        result = subprocess.run(
            [command, "aws"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            aws_path = result.stdout.strip()
            return True, aws_path
        else:
            return (
                False,
                "AWS CLI (aws) not found. "
                "Please install it from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
            )
    except Exception as e:
        return False, f"Error checking for AWS CLI: {e}"


def _check_aws_authenticated() -> tuple[bool, str]:
    """Check if authenticated to AWS.

    Returns:
        Tuple of (success, message).
    """
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            try:
                identity = json.loads(result.stdout)
                arn = identity.get("Arn", "unknown")
                return True, f"Authenticated as {arn}"
            except json.JSONDecodeError:
                return False, "Error parsing AWS identity information"
        else:
            return (
                False,
                "Not authenticated to AWS. "
                "Please configure credentials with 'aws configure' or set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.",
            )
    except Exception as e:
        return False, f"Error checking AWS authentication: {e}"


def _check_instance_type_available(region: str, instance_type: str) -> tuple[bool, str]:
    """Check if instance type is available in the specified region.

    Args:
        region: AWS region (e.g., us-east-1).
        instance_type: EC2 instance type (e.g., t3.large).

    Returns:
        Tuple of (success, message).
    """
    try:
        result = subprocess.run(
            [
                "aws",
                "ec2",
                "describe-instance-type-offerings",
                "--location-type",
                "region",
                "--filters",
                f"Name=instance-type,Values={instance_type}",
                "--region",
                region,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                offerings = data.get("InstanceTypeOfferings", [])
                if offerings:
                    return True, f"Instance type {instance_type} is available in {region}"
                else:
                    return (
                        False,
                        f"Instance type {instance_type} is not available in {region}. "
                        f"Try a different instance_type or region.",
                    )
            except json.JSONDecodeError:
                return False, "Error parsing instance type availability data"
        else:
            return False, f"Error checking instance type availability: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Timeout checking instance type availability"
    except Exception as e:
        return False, f"Error checking instance type availability: {e}"
