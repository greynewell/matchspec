"""Kubernetes infrastructure provider for distributed evaluation."""

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from ..config import HarnessConfig
from .base import InfrastructureProvider

logger = logging.getLogger(__name__)

# Default resource values
DEFAULT_CPU_REQUEST = "1"
DEFAULT_CPU_LIMIT = "4"
DEFAULT_MEMORY_REQUEST = "2Gi"
DEFAULT_MEMORY_LIMIT = "8Gi"
DEFAULT_STORAGE_SIZE = "10Gi"
DEFAULT_BACKOFF_LIMIT = 3
DEFAULT_TTL_SECONDS_AFTER_FINISHED = 3600
DEFAULT_IMAGE_PULL_POLICY = "IfNotPresent"

# Polling intervals
JOB_POLL_INTERVAL_SECONDS = 10
LOG_POLL_INTERVAL_SECONDS = 5


class KubernetesProvider(InfrastructureProvider):
    """Kubernetes infrastructure provider for distributed evaluation.

    Uses Kubernetes Jobs to run evaluation workloads across a cluster.
    Each pod in the Job executes a portion of the evaluation tasks,
    enabling horizontal scaling of benchmark runs.

    Config fields (under infrastructure.kubernetes):
        context: Kubernetes context to use (default: current-context).
        namespace: Namespace for Job resources (default: mcpbr).
        image: Container image for evaluation pods.
        image_pull_policy: Pull policy (Always, IfNotPresent, Never).
        cpu_request: CPU request per pod (e.g., "1").
        cpu_limit: CPU limit per pod (e.g., "4").
        memory_request: Memory request per pod (e.g., "2Gi").
        memory_limit: Memory limit per pod (e.g., "8Gi").
        storage_class: StorageClass for PVCs (optional).
        storage_size: PVC size (e.g., "10Gi").
        parallelism: Number of pods to run concurrently.
        backoff_limit: Number of retries before marking Job failed.
        ttl_seconds_after_finished: Auto-cleanup TTL for finished Jobs.
        env_keys_to_export: Environment variable names to inject as a Secret.
        config_map_name: Override ConfigMap name (default: auto-generated).
        secret_name: Override Secret name (default: auto-generated).
        enable_dind: Attach Docker-in-Docker sidecar to pods.
        dind_privileged: Run DinD in privileged mode (default: false, uses rootless).
        auto_cleanup: Delete resources on completion (default: True).
        preserve_on_error: Keep resources if evaluation fails (default: True).
        node_selector: Node selector labels for pod scheduling.
        tolerations: Pod tolerations for tainted nodes.
        labels: Additional labels to apply to all resources.
    """

    def __init__(self, config: HarnessConfig):
        """Initialize Kubernetes provider.

        Args:
            config: Harness configuration with Kubernetes settings.
        """
        self.config = config
        self.k8s_config = config.infrastructure.kubernetes
        self.namespace: str | None = None
        self.job_name: str | None = None
        self._error_occurred = False
        self._console = Console()

    # ------------------------------------------------------------------
    # Internal config helpers
    # ------------------------------------------------------------------

    def _cfg(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the Kubernetes config dict.

        Args:
            key: Configuration key name.
            default: Fallback value when key is absent.

        Returns:
            Configuration value or default.
        """
        if self.k8s_config is None:
            return default
        if isinstance(self.k8s_config, dict):
            return self.k8s_config.get(key, default)
        return getattr(self.k8s_config, key, default)

    def _kubectl_base(self) -> list[str]:
        """Return the base kubectl command with optional context flag.

        Returns:
            List of command tokens for kubectl invocations.
        """
        kubectl = shutil.which("kubectl")
        if not kubectl:
            raise RuntimeError("kubectl not found on PATH")
        cmd = [kubectl]
        context = self._cfg("context")
        if context:
            cmd.extend(["--context", context])
        if self.namespace:
            cmd.extend(["--namespace", self.namespace])
        return cmd

    def _run_kubectl(
        self,
        args: list[str],
        *,
        input_data: str | None = None,
        timeout: int = 120,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a kubectl command synchronously.

        Args:
            args: Arguments appended after the base kubectl command.
            input_data: Optional string piped to stdin.
            timeout: Command timeout in seconds.
            check: If True, raise on non-zero exit code.

        Returns:
            CompletedProcess result.

        Raises:
            RuntimeError: When check=True and the command fails.
        """
        full_cmd = self._kubectl_base() + args
        result = subprocess.run(
            full_cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"kubectl command failed (exit {result.returncode}): "
                f"{' '.join(full_cmd)}\n"
                f"stderr: {result.stderr.strip()}"
            )
        return result

    # ------------------------------------------------------------------
    # Resource cleanup helpers
    # ------------------------------------------------------------------

    def _cleanup_partial_resources(self) -> None:
        """Clean up any partially-created resources after a setup failure.

        Called from setup() when an error occurs mid-way through resource
        creation. This prevents orphaned ConfigMaps or Secrets from leaking
        in the cluster.
        """
        cm_name = getattr(self, "_config_map_name", None)
        if cm_name and self.namespace:
            try:
                self._run_kubectl(
                    ["delete", "configmap", cm_name, "--ignore-not-found"],
                    check=False,
                )
            except Exception as e:
                logger.warning("Failed to clean up ConfigMap '%s': %s", cm_name, e)

        secret_name = getattr(self, "_secret_name", None)
        if secret_name and self.namespace:
            try:
                self._run_kubectl(
                    ["delete", "secret", secret_name, "--ignore-not-found"],
                    check=False,
                )
            except Exception as e:
                logger.warning("Failed to clean up Secret '%s': %s", secret_name, e)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _ensure_namespace(self) -> None:
        """Create namespace if it does not already exist.

        Raises:
            RuntimeError: If namespace creation fails.
        """
        self.namespace = self._cfg("namespace", "mcpbr")
        self._console.print(f"[cyan]Ensuring namespace '{self.namespace}' exists...[/cyan]")

        # Check if namespace exists
        result = self._run_kubectl(
            ["get", "namespace", self.namespace, "-o", "name"],
            check=False,
        )
        if result.returncode == 0:
            self._console.print(f"[green]  Namespace '{self.namespace}' already exists[/green]")
            return

        # Create namespace
        result = self._run_kubectl(
            ["create", "namespace", self.namespace],
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create namespace '{self.namespace}': {result.stderr.strip()}"
            )
        self._console.print(f"[green]  Namespace '{self.namespace}' created[/green]")

    def _create_config_map(self) -> str:
        """Create a ConfigMap containing the harness configuration YAML.

        The ConfigMap is mounted into evaluation pods so that each pod
        has access to the full evaluation configuration.

        Returns:
            The name of the created ConfigMap.

        Raises:
            RuntimeError: If ConfigMap creation fails.
        """
        cm_name = self._cfg("config_map_name") or f"mcpbr-config-{int(time.time())}"
        self._console.print(f"[cyan]Creating ConfigMap '{cm_name}'...[/cyan]")

        # Serialize config to YAML
        config_dict = self.config.model_dump(mode="json")
        # Override infrastructure mode to local inside the pod
        if "infrastructure" in config_dict:
            config_dict["infrastructure"]["mode"] = "local"
        config_yaml = yaml.dump(config_dict, default_flow_style=False)

        # Build ConfigMap manifest
        cm_manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": cm_name,
                "namespace": self.namespace,
                "labels": self._resource_labels(),
            },
            "data": {
                "config.yaml": config_yaml,
            },
        }

        self._run_kubectl(
            ["apply", "-f", "-"],
            input_data=json.dumps(cm_manifest),
        )
        self._console.print(f"[green]  ConfigMap '{cm_name}' created[/green]")
        return cm_name

    def _create_secret(self) -> str | None:
        """Create a Kubernetes Secret from env_keys_to_export.

        Each key listed in env_keys_to_export is read from the current
        process environment and stored as an Opaque Secret in the target
        namespace.

        Returns:
            The name of the created Secret, or None if no keys to export.

        Raises:
            RuntimeError: If Secret creation fails.
        """
        env_keys: list[str] = self._cfg("env_keys_to_export", [])
        if not env_keys:
            return None

        secret_name = self._cfg("secret_name") or f"mcpbr-secrets-{int(time.time())}"
        self._console.print(f"[cyan]Creating Secret '{secret_name}'...[/cyan]")

        string_data: dict[str, str] = {}
        for key in env_keys:
            value = os.environ.get(key)
            if value:
                string_data[key] = value
            else:
                self._console.print(
                    f"[yellow]  Warning: environment variable '{key}' not set locally, skipping[/yellow]"
                )

        if not string_data:
            self._console.print(
                "[yellow]  No environment variables to export, skipping Secret[/yellow]"
            )
            return None

        secret_manifest: dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name,
                "namespace": self.namespace,
                "labels": self._resource_labels(),
            },
            "type": "Opaque",
            "stringData": string_data,
        }

        self._run_kubectl(
            ["apply", "-f", "-"],
            input_data=json.dumps(secret_manifest),
        )
        self._console.print(
            f"[green]  Secret '{secret_name}' created ({len(string_data)} keys)[/green]"
        )
        return secret_name

    # ------------------------------------------------------------------
    # Job manifest generation
    # ------------------------------------------------------------------

    def _resource_labels(self) -> dict[str, str]:
        """Return labels applied to all Kubernetes resources.

        Returns:
            Dict of label key-value pairs.
        """
        labels: dict[str, str] = {
            "app.kubernetes.io/name": "mcpbr",
            "app.kubernetes.io/component": "evaluation",
            "app.kubernetes.io/managed-by": "mcpbr-k8s-provider",
        }
        extra_labels: dict[str, str] = self._cfg("labels", {})
        if extra_labels:
            labels.update(extra_labels)
        return labels

    def _generate_job_manifest(
        self,
        config_map_name: str,
        secret_name: str | None,
    ) -> dict[str, Any]:
        """Generate a Kubernetes Job manifest as a Python dict.

        The manifest configures:
        - Parallelism and backoff behaviour
        - Resource requests and limits per pod
        - ConfigMap volume mount for evaluation config
        - Secret-based environment variable injection
        - Optional Docker-in-Docker sidecar container
        - Node selectors and tolerations

        Args:
            config_map_name: Name of the ConfigMap with evaluation config.
            secret_name: Name of the Secret with API keys (or None).

        Returns:
            Complete Job manifest as a dictionary ready for kubectl apply.
        """
        timestamp = int(time.time())
        self.job_name = self._cfg("job_name") or f"mcpbr-eval-{timestamp}"
        image = self._cfg("image", "ghcr.io/greynewell/mcpbr:latest")
        image_pull_policy = self._cfg("image_pull_policy", DEFAULT_IMAGE_PULL_POLICY)
        parallelism = self._cfg("parallelism", 1)
        backoff_limit = self._cfg("backoff_limit", DEFAULT_BACKOFF_LIMIT)
        ttl = self._cfg("ttl_seconds_after_finished", DEFAULT_TTL_SECONDS_AFTER_FINISHED)

        # Resource constraints
        cpu_request = self._cfg("cpu_request", DEFAULT_CPU_REQUEST)
        cpu_limit = self._cfg("cpu_limit", DEFAULT_CPU_LIMIT)
        memory_request = self._cfg("memory_request", DEFAULT_MEMORY_REQUEST)
        memory_limit = self._cfg("memory_limit", DEFAULT_MEMORY_LIMIT)

        # ---- Container definition ----
        main_container: dict[str, Any] = {
            "name": "mcpbr-eval",
            "image": image,
            "imagePullPolicy": image_pull_policy,
            "command": ["mcpbr", "run", "-c", "/etc/mcpbr/config.yaml"],
            "resources": {
                "requests": {"cpu": cpu_request, "memory": memory_request},
                "limits": {"cpu": cpu_limit, "memory": memory_limit},
            },
            "volumeMounts": [
                {
                    "name": "config-volume",
                    "mountPath": "/etc/mcpbr",
                    "readOnly": True,
                },
            ],
        }

        # Inject Secret as environment variables
        if secret_name:
            env_keys: list[str] = self._cfg("env_keys_to_export", [])
            env_from_secret: list[dict[str, Any]] = []
            for key in env_keys:
                env_from_secret.append(
                    {
                        "name": key,
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": secret_name,
                                "key": key,
                                "optional": True,
                            },
                        },
                    }
                )
            main_container["env"] = env_from_secret

        # ---- Volumes ----
        volumes: list[dict[str, Any]] = [
            {
                "name": "config-volume",
                "configMap": {"name": config_map_name},
            },
        ]

        # ---- Containers list ----
        containers: list[dict[str, Any]] = [main_container]

        # Docker-in-Docker sidecar
        enable_dind = self._cfg("enable_dind", False)
        if enable_dind:
            dind_privileged = self._cfg("dind_privileged", False)
            if dind_privileged:
                # Privileged mode: full host access (use only when required)
                self._console.print(
                    "[yellow]Warning: DinD sidecar running in privileged mode. "
                    "Consider using rootless mode (dind_privileged: false) "
                    "for better security.[/yellow]"
                )
                dind_image = "docker:27-dind"
                dind_security_ctx: dict[str, Any] = {"privileged": True}
            else:
                # Rootless mode (default): no privileged escalation needed
                dind_image = "docker:27-dind-rootless"
                dind_security_ctx = {"privileged": False, "runAsUser": 1000}

            dind_container: dict[str, Any] = {
                "name": "dind",
                "image": dind_image,
                "securityContext": dind_security_ctx,
                "env": [
                    {"name": "DOCKER_TLS_CERTDIR", "value": ""},
                ],
                "volumeMounts": [
                    {
                        "name": "dind-storage",
                        "mountPath": "/var/lib/docker",
                    },
                ],
            }
            containers.append(dind_container)
            volumes.append(
                {
                    "name": "dind-storage",
                    "emptyDir": {},
                }
            )
            # Point main container's Docker client at the sidecar
            docker_host_env = {"name": "DOCKER_HOST", "value": "tcp://localhost:2375"}
            main_container.setdefault("env", []).append(docker_host_env)

        # ---- Pod spec ----
        pod_spec: dict[str, Any] = {
            "containers": containers,
            "volumes": volumes,
            "restartPolicy": "Never",
        }

        # Node selector
        node_selector: dict[str, str] = self._cfg("node_selector", {})
        if node_selector:
            pod_spec["nodeSelector"] = node_selector

        # Tolerations
        tolerations: list[dict[str, Any]] = self._cfg("tolerations", [])
        if tolerations:
            pod_spec["tolerations"] = tolerations

        # ---- Job manifest ----
        job_manifest: dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": self.job_name,
                "namespace": self.namespace,
                "labels": self._resource_labels(),
            },
            "spec": {
                "parallelism": parallelism,
                "completions": parallelism,
                "backoffLimit": backoff_limit,
                "ttlSecondsAfterFinished": ttl,
                "template": {
                    "metadata": {
                        "labels": self._resource_labels(),
                    },
                    "spec": pod_spec,
                },
            },
        }

        return job_manifest

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------

    def _create_job(self, manifest: dict[str, Any]) -> None:
        """Apply the Job manifest to the cluster via kubectl apply.

        Args:
            manifest: Complete Job manifest dictionary.

        Raises:
            RuntimeError: If kubectl apply fails.
        """
        self._console.print(f"[cyan]Creating Job '{self.job_name}'...[/cyan]")
        self._run_kubectl(
            ["apply", "-f", "-"],
            input_data=json.dumps(manifest),
        )
        self._console.print(f"[green]  Job '{self.job_name}' created[/green]")

    async def _monitor_job(self) -> bool:
        """Poll the Job status until completion or failure.

        Streams pod logs concurrently while monitoring.

        Returns:
            True if the Job completed successfully, False otherwise.

        Raises:
            RuntimeError: If job monitoring encounters an unrecoverable error.
        """
        self._console.print(f"[cyan]Monitoring Job '{self.job_name}'...[/cyan]")
        tracked_pods: set[str] = set()
        log_tasks: list[asyncio.Task[None]] = []

        try:
            while True:
                # Get job status
                result = self._run_kubectl(
                    ["get", "job", self.job_name, "-o", "json"],
                    check=False,
                )
                if result.returncode != 0:
                    self._console.print(
                        f"[yellow]  Warning: could not fetch job status: {result.stderr.strip()}[/yellow]"
                    )
                    await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)
                    continue

                job_status = json.loads(result.stdout)
                status = job_status.get("status", {})
                conditions = status.get("conditions", [])

                active = status.get("active", 0)
                succeeded = status.get("succeeded", 0)
                failed = status.get("failed", 0)

                self._console.print(
                    f"[dim]  Job status: active={active}, succeeded={succeeded}, failed={failed}[/dim]"
                )

                # Start log streaming for new pods
                new_pods = await self._get_pod_names()
                for pod_name in new_pods:
                    if pod_name not in tracked_pods:
                        tracked_pods.add(pod_name)
                        task = asyncio.create_task(self._stream_pod_logs(pod_name))
                        log_tasks.append(task)

                # Check for completion
                for cond in conditions:
                    cond_type = cond.get("type", "")
                    cond_status = cond.get("status", "")
                    if cond_type == "Complete" and cond_status == "True":
                        self._console.print(
                            f"[green]  Job '{self.job_name}' completed successfully[/green]"
                        )
                        return True
                    if cond_type == "Failed" and cond_status == "True":
                        reason = cond.get("reason", "Unknown")
                        message = cond.get("message", "No details available")
                        self._console.print(
                            f"[red]  Job '{self.job_name}' failed: {reason} - {message}[/red]"
                        )
                        return False

                await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)
        finally:
            # Cancel any remaining log tasks
            for task in log_tasks:
                task.cancel()
            if log_tasks:
                await asyncio.gather(*log_tasks, return_exceptions=True)

    async def _get_pod_names(self) -> list[str]:
        """Retrieve pod names belonging to the current Job.

        Returns:
            List of pod name strings.
        """
        result = self._run_kubectl(
            [
                "get",
                "pods",
                "-l",
                f"job-name={self.job_name}",
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ],
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return result.stdout.strip().split()

    async def _stream_pod_logs(self, pod_name: str) -> None:
        """Stream logs from a single pod asynchronously.

        Waits for the pod to reach a Running or terminal state before
        attaching to the log stream.

        Args:
            pod_name: Name of the pod to stream logs from.
        """
        # Wait for the pod to be ready for log streaming
        for _ in range(60):
            result = self._run_kubectl(
                [
                    "get",
                    "pod",
                    pod_name,
                    "-o",
                    "jsonpath={.status.phase}",
                ],
                check=False,
            )
            phase = result.stdout.strip() if result.returncode == 0 else ""
            if phase in ("Running", "Succeeded", "Failed"):
                break
            await asyncio.sleep(LOG_POLL_INTERVAL_SECONDS)

        # Stream logs via subprocess
        kubectl_cmd = self._kubectl_base() + [
            "logs",
            "-f",
            pod_name,
            "--container",
            "mcpbr-eval",
            "--timestamps",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *kubectl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if proc.stdout:
                async for line in proc.stdout:
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    self._console.print(f"[dim][{pod_name}][/dim] {decoded}")
            await proc.wait()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._console.print(
                f"[yellow]  Warning: log streaming error for {pod_name}: {e}[/yellow]"
            )

    def _get_pod_logs(self, pod_name: str) -> str:
        """Retrieve complete logs from a pod synchronously.

        Args:
            pod_name: Name of the pod.

        Returns:
            Full log output as a string.
        """
        result = self._run_kubectl(
            ["logs", pod_name, "--container", "mcpbr-eval", "--timestamps"],
            check=False,
        )
        return (
            result.stdout if result.returncode == 0 else f"[error fetching logs: {result.stderr}]"
        )

    async def _aggregate_results(self) -> dict[str, Any]:
        """Collect and merge evaluation results from all Job pods.

        Each pod writes its results as structured JSON to stdout. This
        method gathers those outputs, parses them, and merges the task
        lists into a single result set.

        Returns:
            Merged results dictionary with metadata, summary, and tasks.
        """
        self._console.print("[cyan]Aggregating results from pods...[/cyan]")

        pod_names = await self._get_pod_names()
        all_tasks: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0

        for pod_name in pod_names:
            result = self._run_kubectl(
                ["logs", pod_name, "--container", "mcpbr-eval"],
                check=False,
            )
            if result.returncode != 0:
                self._console.print(
                    f"[yellow]  Warning: could not fetch results from {pod_name}[/yellow]"
                )
                continue

            # Try to extract JSON results from logs
            # Look for the last JSON object in the output
            log_output = result.stdout.strip()
            results_json = self._extract_json_results(log_output)
            if results_json is None:
                self._console.print(
                    f"[yellow]  Warning: no JSON results found in {pod_name} output[/yellow]"
                )
                continue

            if not metadata:
                metadata = results_json.get("metadata", {})

            tasks = results_json.get("tasks", [])
            all_tasks.extend(tasks)

            # Accumulate summary stats
            summary = results_json.get("summary", {})
            total_cost += summary.get("total_cost", 0.0)
            total_tokens_in += summary.get("total_tokens_input", 0)
            total_tokens_out += summary.get("total_tokens_output", 0)

        resolved = sum(1 for t in all_tasks if t.get("mcp", {}).get("resolved", False))
        total = len(all_tasks)

        aggregated: dict[str, Any] = {
            "metadata": {
                **metadata,
                "infrastructure": "kubernetes",
                "job_name": self.job_name,
                "namespace": self.namespace,
                "pod_count": len(pod_names),
            },
            "summary": {
                "total_tasks": total,
                "resolved": resolved,
                "resolve_rate": resolved / total if total > 0 else 0.0,
                "total_cost": total_cost,
                "total_tokens_input": total_tokens_in,
                "total_tokens_output": total_tokens_out,
            },
            "tasks": all_tasks,
        }

        self._console.print(
            f"[green]  Aggregated {total} task results from {len(pod_names)} pods[/green]"
        )
        return aggregated

    @staticmethod
    def _extract_json_results(log_output: str) -> dict[str, Any] | None:
        """Extract the last valid JSON object from log output.

        Pods emit structured results as a JSON blob at the end of their
        log stream. This method scans backwards to find and parse it.

        Args:
            log_output: Raw log output from a pod.

        Returns:
            Parsed JSON dict, or None if no valid JSON found.
        """
        # Search backwards for a JSON block starting with '{'
        lines = log_output.split("\n")
        json_buffer: list[str] = []
        brace_depth = 0
        in_json = False

        for line in reversed(lines):
            stripped = line.strip()
            # Strip timestamp prefix if present (e.g., "2024-01-01T00:00:00Z ...")
            if stripped and stripped[0].isdigit() and "Z " in stripped:
                stripped = stripped.split("Z ", 1)[-1].strip()

            if not in_json:
                if stripped.endswith("}"):
                    in_json = True
                    brace_depth = stripped.count("}") - stripped.count("{")
                    json_buffer.insert(0, stripped)
                    if brace_depth <= 0:
                        break
            else:
                brace_depth += stripped.count("}") - stripped.count("{")
                json_buffer.insert(0, stripped)
                if brace_depth <= 0:
                    break

        if json_buffer:
            try:
                return json.loads("\n".join(json_buffer))
            except json.JSONDecodeError:
                return None
        return None

    # ------------------------------------------------------------------
    # InfrastructureProvider interface
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Create namespace, ConfigMap, and Secret; validate cluster connectivity.

        This method prepares the Kubernetes cluster for running the evaluation
        Job by ensuring the target namespace exists and creating the necessary
        ConfigMap and Secret resources.

        Raises:
            RuntimeError: If any setup step fails.
        """
        self._console.print("[cyan]Setting up Kubernetes infrastructure...[/cyan]")
        try:
            self._ensure_namespace()
            self._config_map_name = self._create_config_map()
            self._secret_name = self._create_secret()
            self._console.print("[green]Kubernetes infrastructure ready[/green]")
        except Exception:
            self._error_occurred = True
            # Clean up any partially-created resources to avoid leaks
            self._cleanup_partial_resources()
            raise

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Create the Job, monitor pods, and aggregate results.

        Args:
            config: Harness configuration object.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object with aggregated results from all pods.

        Raises:
            RuntimeError: If Job creation, monitoring, or aggregation fails.
        """
        from ..harness import EvaluationResults

        self._console.print("[cyan]Starting Kubernetes evaluation...[/cyan]")

        try:
            # Update command flags based on run mode
            manifest = self._generate_job_manifest(
                config_map_name=self._config_map_name,
                secret_name=self._secret_name,
            )

            # Adjust the command for run mode flags
            command = manifest["spec"]["template"]["spec"]["containers"][0]["command"]
            if run_mcp and not run_baseline:
                command.append("-M")
            elif run_baseline and not run_mcp:
                command.append("-B")

            # Forward task IDs if specified
            if self.config.task_ids:
                for task_id in self.config.task_ids:
                    command.extend(["-t", task_id])

            self._create_job(manifest)
            success = await self._monitor_job()

            if not success:
                self._error_occurred = True
                raise RuntimeError(f"Job '{self.job_name}' failed. Check pod logs for details.")

            aggregated = await self._aggregate_results()

            # Convert to EvaluationResults
            return EvaluationResults(
                metadata=aggregated["metadata"],
                summary=aggregated["summary"],
                tasks=aggregated["tasks"],
            )
        except Exception:
            self._error_occurred = True
            raise

    async def collect_artifacts(self, output_dir: Path) -> Path:
        """Download pod logs and results into a ZIP archive.

        Retrieves logs from every pod in the Job and packages them
        alongside the aggregated results JSON into a single archive.

        Args:
            output_dir: Directory to store the collected artifacts.

        Returns:
            Path to the created ZIP archive.

        Raises:
            RuntimeError: If artifact collection fails.
        """
        self._console.print("[cyan]Collecting artifacts from Kubernetes pods...[/cyan]")

        output_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = output_dir / "pod_logs"
        logs_dir.mkdir(exist_ok=True)

        # Collect logs from each pod
        pod_names = await self._get_pod_names()
        for pod_name in pod_names:
            log_content = self._get_pod_logs(pod_name)
            log_file = logs_dir / f"{pod_name}.log"
            log_file.write_text(log_content, encoding="utf-8")

        # Save aggregated results
        try:
            aggregated = await self._aggregate_results()
            results_file = output_dir / "results.json"
            results_file.write_text(
                json.dumps(aggregated, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as e:
            self._console.print(f"[yellow]  Warning: could not aggregate results: {e}[/yellow]")

        # Save Job manifest for reproducibility
        if self.job_name:
            result = self._run_kubectl(
                ["get", "job", self.job_name, "-o", "json"],
                check=False,
            )
            if result.returncode == 0:
                manifest_file = output_dir / "job_manifest.json"
                manifest_file.write_text(result.stdout, encoding="utf-8")

        # Create ZIP archive
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_path = output_dir.parent / f"k8s_artifacts_{timestamp}.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)

        self._console.print(f"[green]  Artifacts archived: {archive_path}[/green]")
        return archive_path

    async def cleanup(self, force: bool = False) -> None:
        """Delete Job, ConfigMap, Secret, and optionally the namespace.

        Respects the auto_cleanup and preserve_on_error configuration
        settings unless force=True is specified.

        Args:
            force: If True, force cleanup regardless of configuration.
        """
        auto_cleanup = self._cfg("auto_cleanup", True)
        preserve_on_error = self._cfg("preserve_on_error", True)

        should_cleanup = force or (
            auto_cleanup and not (self._error_occurred and preserve_on_error)
        )

        if not should_cleanup:
            self._console.print(
                f"[yellow]Kubernetes resources preserved in namespace '{self.namespace}'[/yellow]"
            )
            if self.job_name:
                self._console.print(
                    f"[dim]  View job: kubectl get job {self.job_name} -n {self.namespace}[/dim]"
                )
                self._console.print(
                    f"[dim]  View pods: kubectl get pods -l job-name={self.job_name} -n {self.namespace}[/dim]"
                )
                self._console.print(
                    f"[dim]  Delete: kubectl delete job {self.job_name} -n {self.namespace}[/dim]"
                )
            return

        self._console.print("[cyan]Cleaning up Kubernetes resources...[/cyan]")

        # Delete Job (cascades to pods)
        if self.job_name:
            result = self._run_kubectl(
                ["delete", "job", self.job_name, "--ignore-not-found"],
                check=False,
            )
            if result.returncode == 0:
                self._console.print(f"[green]  Job '{self.job_name}' deleted[/green]")
            else:
                self._console.print(
                    f"[yellow]  Warning: could not delete Job: {result.stderr.strip()}[/yellow]"
                )

        # Delete ConfigMap
        cm_name = getattr(self, "_config_map_name", None)
        if cm_name:
            result = self._run_kubectl(
                ["delete", "configmap", cm_name, "--ignore-not-found"],
                check=False,
            )
            if result.returncode == 0:
                self._console.print(f"[green]  ConfigMap '{cm_name}' deleted[/green]")

        # Delete Secret
        secret_name = getattr(self, "_secret_name", None)
        if secret_name:
            result = self._run_kubectl(
                ["delete", "secret", secret_name, "--ignore-not-found"],
                check=False,
            )
            if result.returncode == 0:
                self._console.print(f"[green]  Secret '{secret_name}' deleted[/green]")

        self._console.print("[green]Kubernetes cleanup complete[/green]")

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run pre-flight validation for Kubernetes infrastructure.

        Checks:
        1. kubectl is installed and accessible
        2. Cluster is reachable (kubectl cluster-info)
        3. Namespace exists or can be created
        4. Resource quotas in the namespace (if applicable)

        Args:
            **kwargs: Additional health check parameters (unused).

        Returns:
            Dictionary with health check results:
                - healthy (bool): Overall health status
                - checks (list): Individual check result dicts
                - failures (list): Failure message strings
                - warnings (list): Warning message strings
        """
        checks: list[dict[str, Any]] = []
        failures: list[str] = []
        warnings: list[str] = []

        # 1. Check kubectl installed
        kubectl_ok, kubectl_msg = self._check_kubectl_installed()
        checks.append({"name": "kubectl_installed", "passed": kubectl_ok, "message": kubectl_msg})
        if not kubectl_ok:
            failures.append(kubectl_msg)
            return {"healthy": False, "checks": checks, "failures": failures, "warnings": warnings}

        # 2. Check cluster access
        cluster_ok, cluster_msg = self._check_cluster_access()
        checks.append({"name": "cluster_access", "passed": cluster_ok, "message": cluster_msg})
        if not cluster_ok:
            failures.append(cluster_msg)
            return {"healthy": False, "checks": checks, "failures": failures, "warnings": warnings}

        # 3. Check namespace
        ns = self._cfg("namespace", "mcpbr")
        ns_ok, ns_msg = self._check_namespace(ns)
        checks.append({"name": "namespace", "passed": ns_ok, "message": ns_msg})
        if not ns_ok:
            # Namespace not existing is a warning, not a failure -- setup will create it
            warnings.append(ns_msg)

        # 4. Check resource quotas
        quota_ok, quota_msg = self._check_resource_quotas(ns)
        checks.append({"name": "resource_quotas", "passed": quota_ok, "message": quota_msg})
        if not quota_ok:
            warnings.append(quota_msg)

        # 5. Check required environment variables
        env_keys: list[str] = self._cfg("env_keys_to_export", [])
        missing_keys: list[str] = []
        for key in env_keys:
            if not os.environ.get(key):
                missing_keys.append(key)
        if missing_keys:
            env_msg = f"Missing environment variables: {', '.join(missing_keys)}"
            checks.append({"name": "env_vars", "passed": False, "message": env_msg})
            warnings.append(env_msg)
        else:
            checks.append(
                {
                    "name": "env_vars",
                    "passed": True,
                    "message": f"All {len(env_keys)} environment variables are set"
                    if env_keys
                    else "No environment variables configured",
                }
            )

        return {
            "healthy": len(failures) == 0,
            "checks": checks,
            "failures": failures,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Health check helpers
    # ------------------------------------------------------------------

    def _check_kubectl_installed(self) -> tuple[bool, str]:
        """Check if kubectl is installed and on the PATH.

        Returns:
            Tuple of (success, message).
        """
        try:
            which_cmd = "where" if platform.system() == "Windows" else "which"
            result = subprocess.run(
                [which_cmd, "kubectl"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                return True, f"kubectl found at {path}"
            return (
                False,
                "kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/",
            )
        except Exception as e:
            return False, f"Error checking for kubectl: {e}"

    def _check_cluster_access(self) -> tuple[bool, str]:
        """Check if the cluster is reachable via kubectl cluster-info.

        Returns:
            Tuple of (success, message).
        """
        try:
            cmd = ["kubectl"]
            context = self._cfg("context")
            if context:
                cmd.extend(["--context", context])
            cmd.append("cluster-info")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Extract the first line which typically has the cluster endpoint
                first_line = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
                return True, f"Cluster accessible: {first_line}"
            return False, f"Cannot reach cluster: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return False, "Cluster connection timed out after 30 seconds"
        except Exception as e:
            return False, f"Error checking cluster access: {e}"

    def _check_namespace(self, namespace: str) -> tuple[bool, str]:
        """Check if the target namespace exists.

        Args:
            namespace: Namespace name to check.

        Returns:
            Tuple of (exists, message).
        """
        try:
            cmd = ["kubectl"]
            context = self._cfg("context")
            if context:
                cmd.extend(["--context", context])
            cmd.extend(["get", "namespace", namespace, "-o", "name"])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                return True, f"Namespace '{namespace}' exists"
            return False, f"Namespace '{namespace}' does not exist (will be created during setup)"
        except Exception as e:
            return False, f"Error checking namespace: {e}"

    def _check_resource_quotas(self, namespace: str) -> tuple[bool, str]:
        """Check resource quotas in the namespace.

        Args:
            namespace: Namespace to check quotas for.

        Returns:
            Tuple of (ok, message).
        """
        try:
            cmd = ["kubectl"]
            context = self._cfg("context")
            if context:
                cmd.extend(["--context", context])
            cmd.extend(
                [
                    "get",
                    "resourcequota",
                    "--namespace",
                    namespace,
                    "-o",
                    "json",
                ]
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                # No quotas or namespace doesn't exist yet -- that's fine
                return True, "No resource quotas found (unrestricted)"

            quotas = json.loads(result.stdout)
            items = quotas.get("items", [])
            if not items:
                return True, "No resource quotas found (unrestricted)"

            # Report existing quotas
            quota_names = [q.get("metadata", {}).get("name", "unnamed") for q in items]
            return True, f"Resource quotas found: {', '.join(quota_names)}"
        except json.JSONDecodeError:
            return True, "Could not parse quota response (assuming unrestricted)"
        except Exception as e:
            return False, f"Error checking resource quotas: {e}"
