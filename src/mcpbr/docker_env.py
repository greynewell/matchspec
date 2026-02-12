"""Docker environment management for mcpbr benchmark tasks."""

import asyncio
import atexit
import datetime
import logging
import os
import signal
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .audit import AuditLogger
    from .sandbox import SandboxProfile

from docker.models.containers import Container
from docker.models.networks import Network
from docker.models.volumes import Volume

import docker

MCPBR_LABEL = "mcpbr"
MCPBR_INSTANCE_LABEL = "mcpbr.instance"
MCPBR_SESSION_LABEL = "mcpbr.session"
MCPBR_TIMESTAMP_LABEL = "mcpbr.timestamp"

SWEBENCH_IMAGE_REGISTRY = "ghcr.io/epoch-research/swe-bench.eval"

# Default retention policy: clean up resources older than 24 hours
DEFAULT_RETENTION_HOURS = 24

logger = logging.getLogger(__name__)

_active_managers: list["DockerEnvironmentManager"] = []


def _cleanup_on_exit() -> None:
    """Clean up all active managers on process exit."""
    for manager in _active_managers:
        try:
            manager.cleanup_all_sync()
        except Exception:
            pass


atexit.register(_cleanup_on_exit)


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle termination signals by cleaning up containers."""
    _cleanup_on_exit()
    raise KeyboardInterrupt()


_signals_registered = False


def register_signal_handlers() -> None:
    """Register signal handlers for graceful cleanup on SIGINT/SIGTERM.

    Should be called once at application startup (e.g., from CLI).
    """
    global _signals_registered
    if _signals_registered:
        return
    _signals_registered = True
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def get_swebench_image_name(instance_id: str) -> str:
    """Get the pre-built SWE-bench image name for an instance.

    Args:
        instance_id: SWE-bench instance ID (e.g., 'astropy__astropy-12907')

    Returns:
        Full image name like 'ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907'
    """
    # Always use x86_64 images - Epoch has better coverage for x86_64
    # and we can run them on arm64 via Docker emulation
    return f"{SWEBENCH_IMAGE_REGISTRY}.x86_64.{instance_id}"


@dataclass
class CleanupReport:
    """Report of cleaned resources."""

    containers_removed: list[str] = field(default_factory=list)
    volumes_removed: list[str] = field(default_factory=list)
    networks_removed: list[str] = field(default_factory=list)
    temp_dirs_cleaned: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        """Total number of resources removed."""
        return len(self.containers_removed) + len(self.volumes_removed) + len(self.networks_removed)

    def __str__(self) -> str:
        """Format cleanup report as string."""
        lines = ["Cleanup Report:"]
        if self.containers_removed:
            lines.append(f"  Containers: {len(self.containers_removed)} removed")
            for name in self.containers_removed[:5]:
                lines.append(f"    - {name}")
            if len(self.containers_removed) > 5:
                lines.append(f"    ... and {len(self.containers_removed) - 5} more")
        if self.volumes_removed:
            lines.append(f"  Volumes: {len(self.volumes_removed)} removed")
        if self.networks_removed:
            lines.append(f"  Networks: {len(self.networks_removed)} removed")
        if self.temp_dirs_cleaned:
            lines.append(f"  Temp directories: {self.temp_dirs_cleaned} cleaned")
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for error in self.errors[:3]:
                lines.append(f"    - {error}")
            if len(self.errors) > 3:
                lines.append(f"    ... and {len(self.errors) - 3} more")
        return "\n".join(lines)


@dataclass
class TaskEnvironment:
    """Represents an isolated environment for a SWE-bench task."""

    container: Container
    workdir: str
    host_workdir: str
    instance_id: str
    uses_prebuilt: bool = field(default=False)
    claude_cli_installed: bool = field(default=False)
    _temp_dir: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)
    _manager: "DockerEnvironmentManager | None" = field(default=None, repr=False)

    async def exec_command(
        self,
        command: str | list[str],
        timeout: int = 60,
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
        user: str | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command in the container.

        Args:
            command: Command to execute (string or list).
            timeout: Timeout in seconds.
            workdir: Working directory (defaults to /workspace).
            environment: Optional environment variables to set.
            user: Optional user to run the command as (e.g., "mcpbr").

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        if isinstance(command, list):
            cmd = command
        else:
            cmd = ["/bin/bash", "-c", command]

        wd = workdir or self.workdir

        def _exec() -> tuple[int, str, str]:
            result = self.container.exec_run(
                cmd,
                workdir=wd,
                demux=True,
                environment=environment,
                user=user or "",
            )
            stdout = result.output[0].decode("utf-8") if result.output[0] else ""
            stderr = result.output[1].decode("utf-8") if result.output[1] else ""
            return result.exit_code, stdout, stderr

        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _exec),
            timeout=timeout,
        )

    async def exec_command_streaming(
        self,
        command: list[str],
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
        timeout: int = 300,
        on_stdout: Any = None,
        on_stderr: Any = None,
    ) -> tuple[int, str, str]:
        """Execute a command in the container with streaming output.

        Args:
            command: Command to execute as list.
            workdir: Working directory (defaults to self.workdir).
            environment: Optional environment variables to set.
            timeout: Timeout in seconds.
            on_stdout: Optional callback for stdout lines (receives str).
            on_stderr: Optional callback for stderr lines (receives str).

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        wd = workdir or self.workdir

        def _exec_streaming() -> tuple[int, str, str]:
            # Create the exec instance
            exec_id = self.container.client.api.exec_create(
                self.container.id,
                command,
                workdir=wd,
                environment=environment,
                stdout=True,
                stderr=True,
            )

            # Start the exec with streaming
            output_gen = self.container.client.api.exec_start(
                exec_id,
                stream=True,
                demux=True,
            )

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []

            for stdout_chunk, stderr_chunk in output_gen:
                if stdout_chunk:
                    decoded = stdout_chunk.decode("utf-8", errors="replace")
                    stdout_lines.append(decoded)
                    if on_stdout:
                        # Process line by line
                        for line in decoded.splitlines():
                            on_stdout(line)

                if stderr_chunk:
                    decoded = stderr_chunk.decode("utf-8", errors="replace")
                    stderr_lines.append(decoded)
                    if on_stderr:
                        for line in decoded.splitlines():
                            on_stderr(line)

            # Get exit code
            inspect = self.container.client.api.exec_inspect(exec_id)
            exit_code = inspect.get("ExitCode", -1)

            return exit_code, "".join(stdout_lines), "".join(stderr_lines)

        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _exec_streaming),
            timeout=timeout,
        )

    async def write_file(self, path: str, content: str, workdir: str | None = None) -> None:
        """Write content to a file in the container.

        Args:
            path: File path (relative to workdir).
            content: Content to write.
            workdir: Working directory. If different from /workspace (the host mount),
                     writes directly into container via docker exec.
        """
        workdir = workdir or self.workdir

        # If writing to the host-mounted /workspace, use filesystem directly
        if workdir == "/workspace" or workdir == self.workdir:
            full_path = os.path.join(self.host_workdir, path.lstrip("/"))
            Path(full_path).parent.mkdir(parents=True, exist_ok=True)
            Path(full_path).write_text(content)
        else:
            # Write directly into container (e.g., /testbed)
            import base64

            encoded = base64.b64encode(content.encode()).decode()
            full_path = os.path.join(workdir, path.lstrip("/"))
            exit_code, _, stderr = await self.exec_command(
                f"echo '{encoded}' | base64 -d > {full_path}",
                timeout=30,
                workdir=workdir,
            )
            if exit_code != 0:
                raise RuntimeError(f"Failed to write file {full_path}: {stderr}")

    async def read_file(self, path: str) -> str:
        """Read content from a file in the container."""
        full_path = os.path.join(self.host_workdir, path.lstrip("/"))
        return Path(full_path).read_text()

    async def cleanup(self) -> None:
        """Stop and remove the container and clean up temp directory.

        This aggressively cleans up resources immediately after task completion
        to prevent disk space exhaustion when running many tasks.
        """
        # Stop and remove container
        try:
            self.container.stop(timeout=5)
            self.container.remove(force=True)
        except Exception:
            pass

        # Clean up temp directory immediately
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass

            # Remove from manager's list to avoid double cleanup
            if self._manager is not None and self._temp_dir in self._manager._temp_dirs:
                self._manager._temp_dirs.remove(self._temp_dir)


class DockerEnvironmentManager:
    """Manages Docker environments for SWE-bench tasks."""

    FALLBACK_IMAGE = "mcpbr-env"
    DOCKERFILE_PATH = Path(__file__).parent.parent.parent / "Dockerfile"

    def __init__(
        self,
        use_prebuilt: bool = True,
        extra_volumes: dict[str, str] | None = None,
        sandbox_profile: "SandboxProfile | None" = None,
        audit_logger: "AuditLogger | None" = None,
        claude_code_version: str | None = None,
    ) -> None:
        """Initialize the Docker environment manager.

        Args:
            use_prebuilt: If True, try to use pre-built SWE-bench images first.
            extra_volumes: Additional volume mounts (read-write) (host_path -> container_path).
            sandbox_profile: Security sandbox profile for containers. None uses defaults.
            audit_logger: Optional audit logger for sandbox security events.
            claude_code_version: Pin a specific Claude Code npm version (e.g., '2.1.37').
        """
        self.client = docker.from_env()
        self.use_prebuilt = use_prebuilt
        self.claude_code_version = claude_code_version
        self._extra_volumes = extra_volumes or {}
        self._sandbox_profile = sandbox_profile
        self._audit_logger = audit_logger
        self._fallback_image_built = False
        self._temp_dirs: list[tempfile.TemporaryDirectory[str]] = []
        self._containers: list[Container] = []
        self._volumes: list[Volume] = []
        self._networks: list[Network] = []
        self._session_id = uuid.uuid4().hex[:8]
        self._session_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _active_managers.append(self)

    async def _try_pull_prebuilt(self, instance_id: str) -> str | None:
        """Try to pull a pre-built SWE-bench image.

        Args:
            instance_id: SWE-bench instance ID.

        Returns:
            Image name if successful, None if not available.
        """
        image_name = get_swebench_image_name(instance_id)

        def _pull() -> str | None:
            try:
                self.client.images.pull(image_name, platform="linux/amd64")
                return image_name
            except docker.errors.ImageNotFound:
                return None
            except docker.errors.APIError:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _pull)

    async def _ensure_fallback_image(self) -> None:
        """Ensure the fallback Docker image is built."""
        if self._fallback_image_built:
            return

        def _build() -> None:
            try:
                self.client.images.get(self.FALLBACK_IMAGE)
            except docker.errors.ImageNotFound:
                dockerfile_dir = self.DOCKERFILE_PATH.parent
                if self.DOCKERFILE_PATH.exists():
                    self.client.images.build(
                        path=str(dockerfile_dir),
                        tag=self.FALLBACK_IMAGE,
                        rm=True,
                    )
                else:
                    self.client.images.pull("python:3.11-slim")
                    self._use_fallback_image()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _build)
        self._fallback_image_built = True

    def _use_fallback_image(self) -> None:
        """Build a comprehensive fallback image if Dockerfile not found.

        Includes all system dependencies commonly needed for SWE-bench tasks:
        - Version control (git)
        - Build tools (gcc, g++, make)
        - SSL/crypto libraries (for requests, urllib3, cryptography)
        - Database drivers (PostgreSQL, MySQL)
        - XML processing (lxml)
        - Image processing (Pillow, matplotlib)
        - Python testing tools (pytest, coverage)
        """
        try:
            # Build a comprehensive fallback image with common SWE-bench dependencies
            dockerfile_content = """FROM python:3.11-slim

# Install system dependencies commonly needed for SWE-bench tasks
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    curl \\
    wget \\
    vim \\
    ca-certificates \\
    build-essential \\
    libssl-dev \\
    libffi-dev \\
    libpq-dev \\
    default-libmysqlclient-dev \\
    libxml2-dev \\
    libxslt1-dev \\
    libjpeg-dev \\
    libpng-dev \\
    zlib1g-dev \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install common Python testing tools
RUN pip install --no-cache-dir \\
    pytest \\
    pytest-xdist \\
    coverage

CMD ["/bin/bash"]
"""
            with tempfile.TemporaryDirectory() as tmpdir:
                dockerfile_path = os.path.join(tmpdir, "Dockerfile")
                with open(dockerfile_path, "w") as f:
                    f.write(dockerfile_content)

                self.client.images.build(
                    path=tmpdir,
                    tag=self.FALLBACK_IMAGE,
                    rm=True,
                )
        except Exception as e:
            # Do NOT tag bare python:3.11-slim as the fallback image — it lacks
            # git, build tools, etc. and will poison all subsequent tasks.
            # Instead, mark the build as failed so callers get a clear error.
            logger.error(
                f"Failed to build fallback image: {e}. "
                f"Tasks requiring the fallback image will fail."
            )
            raise RuntimeError(
                f"Cannot create fallback image '{self.FALLBACK_IMAGE}': {e}. "
                f"Ensure Docker has enough disk space and network access."
            ) from e

    async def create_environment(
        self,
        task: dict[str, Any],
    ) -> TaskEnvironment:
        """Create an isolated environment for a SWE-bench task.

        Args:
            task: SWE-bench task dictionary with repo, base_commit, etc.

        Returns:
            TaskEnvironment instance.
        """
        instance_id = task["instance_id"]
        repo = task["repo"]
        base_commit = task["base_commit"]

        image_name = None
        uses_prebuilt = False

        if self.use_prebuilt:
            image_name = await self._try_pull_prebuilt(instance_id)
            if image_name:
                uses_prebuilt = True

        if not image_name:
            await self._ensure_fallback_image()
            image_name = self.FALLBACK_IMAGE

        temp_dir = tempfile.TemporaryDirectory(prefix=f"mcpbr_{instance_id}_")
        self._temp_dirs.append(temp_dir)
        host_workdir = temp_dir.name

        # Use a unique suffix per container to prevent name collisions when
        # MCP and baseline runs create containers for the same task.
        unique_suffix = uuid.uuid4().hex[:6]
        container_name = f"mcpbr-{self._session_id}-{instance_id}-{unique_suffix}"

        container_workdir = "/testbed" if uses_prebuilt else "/workspace"

        def _create_container() -> Container:
            max_retries = 3
            base_delay = 1  # Start with 1 second delay

            for attempt in range(max_retries + 1):
                try:
                    volumes_dict: dict[str, dict[str, str]] = {
                        host_workdir: {"bind": "/workspace", "mode": "rw"},
                    }
                    for host_path, container_path in self._extra_volumes.items():
                        volumes_dict[os.path.abspath(host_path)] = {
                            "bind": container_path,
                            "mode": "rw",
                        }

                    # Build sandbox kwargs if a profile is configured
                    sandbox_kwargs: dict = {}
                    if self._sandbox_profile is not None:
                        sandbox_kwargs = self._sandbox_profile.to_docker_kwargs()

                    # Default network mode; sandbox may override
                    network_mode = sandbox_kwargs.pop("network_mode", "bridge")

                    container = self.client.containers.run(
                        image_name,
                        command="tail -f /dev/null",
                        name=container_name,
                        detach=True,
                        platform="linux/amd64" if uses_prebuilt else None,
                        network_mode=network_mode,
                        volumes=volumes_dict,
                        working_dir=container_workdir,
                        remove=False,
                        labels={
                            MCPBR_LABEL: "true",
                            MCPBR_INSTANCE_LABEL: str(instance_id),
                            MCPBR_SESSION_LABEL: self._session_id,
                            MCPBR_TIMESTAMP_LABEL: self._session_timestamp,
                        },
                        **sandbox_kwargs,
                    )
                    return container
                except docker.errors.APIError as e:
                    response = getattr(e, "response", None)
                    status_code = getattr(response, "status_code", None) if response else None

                    # On 409 Conflict (container name already in use), try to
                    # remove the stale container and retry once.
                    if status_code == 409 and attempt < max_retries:
                        logger.warning(
                            f"Container name conflict (attempt {attempt + 1}): {e}. "
                            f"Removing stale container and retrying..."
                        )
                        try:
                            stale = self.client.containers.get(container_name)
                            stale.remove(force=True)
                        except Exception:
                            pass  # Container may already be gone
                        time.sleep(1)
                        continue

                    # Retry on 500 errors (transient Docker daemon issues)
                    if status_code == 500 and attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Docker API error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        continue

                    # Re-raise for unrecoverable errors or after max retries
                    raise

        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(None, _create_container)
        self._containers.append(container)

        # Audit: log sandbox applied and validate
        if self._sandbox_profile and self._audit_logger:
            from .audit import AuditAction

            self._audit_logger.log(
                action=AuditAction.SANDBOX_APPLIED,
                resource=container_name,
                details={
                    "profile_name": self._sandbox_profile.name,
                    "security_level": self._sandbox_profile.security_level.value,
                    "cap_drop": self._sandbox_profile.cap_drop,
                    "read_only_rootfs": self._sandbox_profile.read_only_rootfs,
                    "network_disabled": self._sandbox_profile.network_disabled,
                },
            )

            # Validate sandbox settings match profile
            from .sandbox import validate_sandbox

            try:
                container.reload()
                host_config = container.attrs.get("HostConfig", {})
                valid, mismatches = validate_sandbox(host_config, self._sandbox_profile)
                self._audit_logger.log(
                    action=AuditAction.SANDBOX_VALIDATED,
                    resource=container_name,
                    result="success" if valid else "warning",
                    details={
                        "valid": valid,
                        "mismatches": mismatches,
                    },
                )
            except Exception as e:
                logger.warning("Sandbox validation failed: %s", e)
                self._audit_logger.log(
                    action=AuditAction.SANDBOX_VALIDATED,
                    resource=container_name,
                    result="error",
                    details={"valid": False, "error": str(e)},
                )

        env = TaskEnvironment(
            container=container,
            workdir=container_workdir,
            host_workdir=host_workdir,
            instance_id=instance_id,
            uses_prebuilt=uses_prebuilt,
            claude_cli_installed=False,
            _temp_dir=temp_dir,
            _manager=self,
        )

        if uses_prebuilt:
            await self._copy_repo_to_workspace(env)
            # Install Claude CLI for running agent inside container
            await self._install_claude_cli(env)
            env.claude_cli_installed = True
        else:
            await self._setup_repo(env, repo, base_commit)

        return env

    async def _check_workspace_file_count(self, env: TaskEnvironment) -> int:
        """Check whether /workspace has any top-level entries.

        Args:
            env: Task environment to check.

        Returns:
            Number of top-level files/directories found (capped at 5).
        """
        try:
            exit_code, stdout, _ = await env.exec_command(
                "find /workspace -maxdepth 1 -mindepth 1 | head -5 | wc -l",
                timeout=10,
            )
            return int(stdout.strip()) if exit_code == 0 and stdout.strip().isdigit() else 0
        except Exception:
            return 0

    async def _copy_repo_to_workspace(self, env: TaskEnvironment) -> None:
        """Copy repo from pre-built image /testbed to /workspace for agent access.

        Under high concurrency the Docker filesystem copy can silently produce
        an empty workspace.  This method retries with a sync and, if necessary,
        a full re-copy before giving up.

        Args:
            env: Task environment with pre-built image.
        """
        # --- Phase 1: initial copy + verify ---
        exit_code, stdout, stderr = await env.exec_command(
            "cp -r /testbed/. /workspace/",
            timeout=120,
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to copy repo to workspace: {stderr}")

        # Mark the workspace as safe for git operations
        await env.exec_command(
            "git config --global --add safe.directory /workspace",
            timeout=10,
        )

        # Reset any uncommitted changes from the pre-built image
        await env.exec_command(
            "cd /workspace && git checkout -- . && git clean -fd",
            timeout=30,
        )

        # Flush filesystem buffers to ensure all copied files are visible
        # before any subsequent commands (e.g., setup_command) run.
        await env.exec_command("sync", timeout=10)

        file_count = await self._check_workspace_file_count(env)
        if file_count > 0:
            env.workdir = "/workspace"
            return

        # --- Phase 2: sync retry ---
        logger.warning(
            "Workspace /workspace empty after initial copy — retrying with sync "
            f"(instance={env.instance_id})"
        )
        await asyncio.sleep(2)
        await env.exec_command("sync", timeout=10)

        file_count = await self._check_workspace_file_count(env)
        if file_count > 0:
            logger.info(
                "Workspace populated after sync retry "
                f"(instance={env.instance_id}, files={file_count})"
            )
            env.workdir = "/workspace"
            return

        # --- Phase 3: full copy retry ---
        logger.warning(
            "Workspace still empty after sync retry — re-copying from /testbed "
            f"(instance={env.instance_id})"
        )
        exit_code, _, stderr = await env.exec_command(
            "cp -r /testbed/. /workspace/",
            timeout=120,
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to re-copy repo to workspace: {stderr}")

        await env.exec_command(
            "cd /workspace && git checkout -- . && git clean -fd",
            timeout=30,
        )
        await env.exec_command("sync", timeout=10)

        file_count = await self._check_workspace_file_count(env)
        if file_count > 0:
            logger.info(
                "Workspace populated after full copy retry "
                f"(instance={env.instance_id}, files={file_count})"
            )
            env.workdir = "/workspace"
            return

        # --- Exhausted ---
        raise RuntimeError(
            f"Workspace /workspace appears empty after copy from /testbed "
            f"(instance={env.instance_id}). "
            f"The filesystem may not have synced correctly."
        )

    async def _install_claude_cli(self, env: TaskEnvironment) -> None:
        """Install Node.js and Claude CLI in the container.

        Also creates a non-root user for running Claude CLI, since it blocks
        --dangerously-skip-permissions when running as root.

        Args:
            env: Task environment to install into.
        """
        # Install Node.js (using NodeSource for a recent version)
        install_node_cmd = (
            "apt-get update -qq && "
            "apt-get install -y -qq curl ca-certificates gnupg sudo && "
            "mkdir -p /etc/apt/keyrings && "
            "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | "
            "gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && "
            "echo 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main' | "
            "tee /etc/apt/sources.list.d/nodesource.list && "
            "apt-get update -qq && "
            "apt-get install -y -qq nodejs"
        )

        exit_code, stdout, stderr = await env.exec_command(
            install_node_cmd,
            timeout=300,
            workdir="/tmp",
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to install Node.js: {stderr}")

        # Install Claude CLI globally (optionally pin a specific version)
        claude_pkg = "@anthropic-ai/claude-code"
        if self.claude_code_version:
            claude_pkg = f"{claude_pkg}@{self.claude_code_version}"
        exit_code, stdout, stderr = await env.exec_command(
            f"npm install -g {claude_pkg}",
            timeout=120,
            workdir="/tmp",
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to install Claude CLI: {stderr}")

        # Create a non-root user for running Claude CLI
        # Claude CLI blocks --dangerously-skip-permissions when running as root
        # Ensure home directory (including .cache) is fully owned by mcpbr
        # so Claude CLI can create MCP log directories at runtime
        create_user_cmd = (
            "useradd -m -s /bin/bash mcpbr && "
            "mkdir -p /home/mcpbr/.cache && "
            "chown -R mcpbr:mcpbr /home/mcpbr && "
            "chown -R mcpbr:mcpbr /workspace && "
            f"chown -R mcpbr:mcpbr {env.workdir}"
        )
        exit_code, stdout, stderr = await env.exec_command(
            create_user_cmd,
            timeout=30,
            workdir="/tmp",
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to create non-root user: {stderr}")

    async def _setup_repo(
        self,
        env: TaskEnvironment,
        repo: str,
        base_commit: str,
    ) -> None:
        """Clone the repository at the specified commit (fallback path)."""
        repo_url = f"https://github.com/{repo}.git"

        exit_code, stdout, stderr = await env.exec_command(
            f"git clone --depth 100 {repo_url} .",
            timeout=120,
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to clone {repo}: {stderr}")

        exit_code, stdout, stderr = await env.exec_command(
            f"git fetch --depth 100 origin {base_commit}",
            timeout=60,
        )

        exit_code, stdout, stderr = await env.exec_command(
            f"git checkout {base_commit}",
            timeout=30,
        )
        if exit_code != 0:
            raise RuntimeError(f"Failed to checkout {base_commit}: {stderr}")

    def cleanup_all_sync(self, report: bool = False) -> CleanupReport:
        """Synchronously clean up all containers and temporary directories.

        Used by signal handlers and atexit.

        Args:
            report: If True, return detailed cleanup report.

        Returns:
            CleanupReport with details of cleaned resources.
        """
        cleanup_report = CleanupReport()

        # Clean up containers
        for container in self._containers:
            try:
                container_name = container.name or container.short_id
                container.stop(timeout=5)
                container.remove(force=True)
                cleanup_report.containers_removed.append(container_name)
            except Exception as e:
                cleanup_report.errors.append(f"Failed to remove container: {e}")
        self._containers.clear()

        # Clean up volumes
        for volume in self._volumes:
            try:
                volume_name = volume.name
                volume.remove(force=True)
                cleanup_report.volumes_removed.append(volume_name)
            except Exception as e:
                cleanup_report.errors.append(f"Failed to remove volume: {e}")
        self._volumes.clear()

        # Clean up networks
        for network in self._networks:
            try:
                network_name = network.name
                network.remove()
                cleanup_report.networks_removed.append(network_name)
            except Exception as e:
                cleanup_report.errors.append(f"Failed to remove network: {e}")
        self._networks.clear()

        # Clean up temp directories
        for temp_dir in self._temp_dirs:
            try:
                temp_dir.cleanup()
                cleanup_report.temp_dirs_cleaned += 1
            except Exception as e:
                cleanup_report.errors.append(f"Failed to cleanup temp dir: {e}")
        self._temp_dirs.clear()

        if self in _active_managers:
            _active_managers.remove(self)

        # Close the Docker client to release background threads/connections
        try:
            self.client.close()
        except Exception:
            pass

        if report and cleanup_report.total_removed > 0:
            logger.info(str(cleanup_report))

        return cleanup_report

    async def cleanup_all(self, report: bool = False) -> CleanupReport:
        """Clean up all containers and temporary directories.

        Args:
            report: If True, return detailed cleanup report.

        Returns:
            CleanupReport with details of cleaned resources.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cleanup_all_sync, report)


def cleanup_orphaned_containers(
    dry_run: bool = False, force: bool = False, retention_hours: int | None = None
) -> list[str]:
    """Find and remove orphaned mcpbr containers.

    Args:
        dry_run: If True, only list containers without removing them.
        force: If True, remove all containers regardless of age.
        retention_hours: Only remove containers older than this many hours.
                        Defaults to DEFAULT_RETENTION_HOURS if not specified.

    Returns:
        List of container names/IDs that were (or would be) removed.
    """
    client = docker.from_env()
    removed: list[str] = []

    if retention_hours is None:
        retention_hours = DEFAULT_RETENTION_HOURS

    containers = client.containers.list(
        all=True,
        filters={"label": f"{MCPBR_LABEL}=true"},
    )

    now = datetime.datetime.now(datetime.timezone.utc)

    for container in containers:
        name = container.name or container.short_id

        # Check age if not forcing
        if not force and retention_hours > 0:
            timestamp_str = container.labels.get(MCPBR_TIMESTAMP_LABEL)
            if timestamp_str:
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                    age_hours = (now - timestamp).total_seconds() / 3600
                    if age_hours < retention_hours:
                        continue  # Skip containers newer than retention period
                except (ValueError, TypeError):
                    pass  # If we can't parse timestamp, proceed with removal

        removed.append(name)
        if not dry_run:
            try:
                container.stop(timeout=5)
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Failed to remove container {name}: {e}")

    return removed


def cleanup_orphaned_volumes(dry_run: bool = False, force: bool = False) -> list[str]:
    """Find and remove orphaned mcpbr volumes.

    Args:
        dry_run: If True, only list volumes without removing them.
        force: If True, force removal even if volume is in use.

    Returns:
        List of volume names that were (or would be) removed.
    """
    client = docker.from_env()
    removed: list[str] = []

    try:
        volumes = client.volumes.list(filters={"label": f"{MCPBR_LABEL}=true"})
    except Exception as e:
        logger.warning(f"Failed to list volumes: {e}")
        return removed

    for volume in volumes:
        volume_name = volume.name
        removed.append(volume_name)
        if not dry_run:
            try:
                volume.remove(force=force)
            except Exception as e:
                logger.warning(f"Failed to remove volume {volume_name}: {e}")

    return removed


def cleanup_orphaned_networks(dry_run: bool = False) -> list[str]:
    """Find and remove orphaned mcpbr networks.

    Args:
        dry_run: If True, only list networks without removing them.

    Returns:
        List of network names that were (or would be) removed.
    """
    client = docker.from_env()
    removed: list[str] = []

    try:
        networks = client.networks.list(filters={"label": f"{MCPBR_LABEL}=true"})
    except Exception as e:
        logger.warning(f"Failed to list networks: {e}")
        return removed

    for network in networks:
        network_name = network.name
        # Skip default networks
        if network_name in ("bridge", "host", "none"):
            continue
        removed.append(network_name)
        if not dry_run:
            try:
                network.remove()
            except Exception as e:
                logger.warning(f"Failed to remove network {network_name}: {e}")

    return removed


def cleanup_all_resources(
    dry_run: bool = False,
    force: bool = False,
    retention_hours: int | None = None,
) -> CleanupReport:
    """Clean up all orphaned mcpbr Docker resources.

    Args:
        dry_run: If True, only report what would be removed.
        force: If True, force removal of all resources.
        retention_hours: Only remove resources older than this many hours.

    Returns:
        CleanupReport with details of cleaned resources.
    """
    report = CleanupReport()

    # Clean up containers first (they may hold references to volumes/networks)
    try:
        containers = cleanup_orphaned_containers(dry_run, force, retention_hours)
        report.containers_removed = containers
    except Exception as e:
        report.errors.append(f"Container cleanup failed: {e}")

    # Clean up volumes
    try:
        volumes = cleanup_orphaned_volumes(dry_run, force)
        report.volumes_removed = volumes
    except Exception as e:
        report.errors.append(f"Volume cleanup failed: {e}")

    # Clean up networks
    try:
        networks = cleanup_orphaned_networks(dry_run)
        report.networks_removed = networks
    except Exception as e:
        report.errors.append(f"Network cleanup failed: {e}")

    return report
