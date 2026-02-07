"""Cloudflare Workers infrastructure provider.

Uses a hybrid approach where the Worker acts as an orchestrator that calls
back to a local Python API for actual evaluation. The Worker handles
request routing, result storage in KV, and status reporting, while the
heavy lifting (model invocation, evaluation scoring) happens locally or
via an external callback endpoint.

Limitations:
    - No Docker support (benchmarks requiring containers not supported)
    - API-based MCP servers only (no stdio transport)
    - Suitable for: GSM8K, HumanEval, MCPToolBench (API-only)
    - NOT suitable for: SWE-bench, CyberGym (require Docker)
"""

import asyncio
import json
import os
import platform
import secrets
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from ..config import HarnessConfig
from .base import InfrastructureProvider

# Default compatibility date for Cloudflare Workers runtime
_DEFAULT_COMPATIBILITY_DATE = "2024-09-23"

# Poll interval and timeout defaults (seconds)
_DEFAULT_POLL_INTERVAL = 5
_DEFAULT_POLL_TIMEOUT = 3600  # 1 hour

# HTTP request timeout for Worker invocations (seconds)
_DEFAULT_HTTP_TIMEOUT = 30


class CloudflareProvider(InfrastructureProvider):
    """Cloudflare Workers infrastructure provider for serverless evaluation.

    Uses a hybrid approach: the Worker handles orchestration and result storage,
    while evaluation logic runs locally or on an external service.

    Limitations:
        - No Docker support (benchmarks requiring containers not supported)
        - API-based MCP servers only (no stdio transport)
        - Suitable for: GSM8K, HumanEval, MCPToolBench (API-only)
        - NOT suitable for: SWE-bench, CyberGym (require Docker)
    """

    # Benchmarks that do NOT require Docker and can run on Cloudflare Workers
    SUPPORTED_BENCHMARKS = {
        "gsm8k",
        "humaneval",
        "mbpp",
        "math",
        "truthfulqa",
        "bigbench-hard",
        "hellaswag",
        "arc",
        "mmmu",
        "longbench",
    }

    # Benchmarks that require Docker and are NOT supported
    DOCKER_REQUIRED_BENCHMARKS = {
        "swe-bench-lite",
        "swe-bench-verified",
        "swe-bench-full",
        "cybergym",
        "terminalbench",
    }

    def __init__(self, config: HarnessConfig):
        """Initialize Cloudflare Workers provider.

        Args:
            config: Harness configuration with Cloudflare settings.
                    Expects config.infrastructure.cloudflare to be set.
        """
        self.config = config
        self.cf_config = config.infrastructure.cloudflare
        self.worker_name: str | None = None
        self.worker_url: str | None = None
        self.kv_namespace_id: str | None = None
        self._error_occurred = False
        self._deploy_dir: str | None = None
        self._console = Console()

    # ------------------------------------------------------------------

    def _ensure_auth_token(self) -> str:
        """Ensure an auth token is available for Worker authentication.

        If no auth_token is configured, generates a secure random token.
        This prevents Worker endpoints from being exposed without authentication.

        Returns:
            The auth token string (existing or newly generated).
        """
        existing_token = getattr(self.cf_config, "auth_token", None)
        if existing_token:
            return existing_token

        # Generate a secure random token (48 bytes = 64 chars in URL-safe base64)
        token = secrets.token_urlsafe(48)
        self.cf_config.auth_token = token
        self._console.print(
            "[yellow]Warning: No auth_token configured. "
            "Auto-generated a secure token for Worker authentication.[/yellow]"
        )
        return token

    # Benchmark compatibility
    # ------------------------------------------------------------------

    def _check_benchmark_compatibility(self) -> None:
        """Verify the configured benchmark does not require Docker.

        Raises:
            RuntimeError: If the benchmark requires Docker or is otherwise
                unsupported on Cloudflare Workers.
        """
        benchmark = self.config.benchmark

        if benchmark in self.DOCKER_REQUIRED_BENCHMARKS:
            raise RuntimeError(
                f"Benchmark '{benchmark}' requires Docker containers and cannot run "
                f"on Cloudflare Workers. Use 'local' or 'azure' infrastructure instead. "
                f"Docker-required benchmarks: {', '.join(sorted(self.DOCKER_REQUIRED_BENCHMARKS))}"
            )

        if benchmark not in self.SUPPORTED_BENCHMARKS and benchmark != "custom":
            self._console.print(
                f"[yellow]Warning: Benchmark '{benchmark}' has not been verified "
                f"for Cloudflare Workers. It may work if it does not require Docker "
                f"or stdio-based MCP servers.[/yellow]"
            )

    # ------------------------------------------------------------------
    # Wrangler configuration generation
    # ------------------------------------------------------------------

    def _generate_wrangler_config(self, deploy_dir: Path) -> Path:
        """Generate wrangler.toml configuration for the Worker.

        Args:
            deploy_dir: Temporary directory for deployment artifacts.

        Returns:
            Path to the generated wrangler.toml file.
        """
        worker_name = self.cf_config.worker_name or f"mcpbr-eval-{int(time.time())}"
        self.worker_name = worker_name

        account_id = self.cf_config.account_id
        compatibility_date = getattr(
            self.cf_config, "compatibility_date", _DEFAULT_COMPATIBILITY_DATE
        )
        cpu_ms = getattr(self.cf_config, "cpu_ms", 30000)
        kv_namespace = getattr(self.cf_config, "kv_namespace", None)
        r2_bucket = getattr(self.cf_config, "r2_bucket", None)

        # Build wrangler.toml content
        lines = [
            f'name = "{worker_name}"',
            'main = "worker.ts"',
            f'compatibility_date = "{compatibility_date}"',
            "",
            "[vars]",
            f'MCPBR_BENCHMARK = "{self.config.benchmark}"',
            f'MCPBR_WORKER_NAME = "{worker_name}"',
            f'MCPBR_AUTH_TOKEN = "{getattr(self.cf_config, "auth_token", "")}"',
            "",
        ]

        if account_id:
            lines.insert(1, f'account_id = "{account_id}"')

        # CPU time limit (in milliseconds)
        lines.extend(
            [
                "[limits]",
                f"cpu_ms = {cpu_ms}",
                "",
            ]
        )

        # KV namespace binding
        if kv_namespace:
            lines.extend(
                [
                    "[[kv_namespaces]]",
                    'binding = "MCPBR_KV"',
                    f'id = "{kv_namespace}"',
                    "",
                ]
            )

        # R2 bucket binding
        if r2_bucket:
            lines.extend(
                [
                    "[[r2_buckets]]",
                    'binding = "MCPBR_R2"',
                    f'bucket_name = "{r2_bucket}"',
                    "",
                ]
            )

        config_path = deploy_dir / "wrangler.toml"
        config_path.write_text("\n".join(lines))

        self._console.print(f"[dim]Generated wrangler.toml for worker: {worker_name}[/dim]")
        return config_path

    # ------------------------------------------------------------------
    # Worker script generation
    # ------------------------------------------------------------------

    def _generate_worker_script(self, deploy_dir: Path) -> Path:
        """Generate the Worker TypeScript orchestrator script.

        The Worker provides:
        - POST /evaluate: Accept evaluation config, store in KV, return run ID
        - GET /status/:runId: Return current status from KV
        - GET /results/:runId: Return completed results from KV
        - POST /results/:runId: Store results (called by local evaluator callback)
        - GET /health: Health check endpoint

        Args:
            deploy_dir: Temporary directory for deployment artifacts.

        Returns:
            Path to the generated worker.ts file.
        """
        worker_script = r"""
// mcpbr Cloudflare Worker - Evaluation Orchestrator
// This Worker acts as a lightweight orchestrator: it receives evaluation
// requests, stores configuration and results in KV, and provides status
// polling endpoints.

export interface Env {
  MCPBR_KV?: KVNamespace;
  MCPBR_R2?: R2Bucket;
  MCPBR_BENCHMARK: string;
  MCPBR_WORKER_NAME: string;
  MCPBR_AUTH_TOKEN?: string;
}

interface EvalRequest {
  run_id?: string;
  benchmark: string;
  config: Record<string, unknown>;
  callback_url?: string;
}

interface RunStatus {
  run_id: string;
  status: "pending" | "running" | "completed" | "failed";
  benchmark: string;
  created_at: string;
  updated_at: string;
  error?: string;
  results?: Record<string, unknown>;
}

function generateRunId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `run-${timestamp}-${random}`;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(message: string, status = 400): Response {
  return jsonResponse({ error: message }, status);
}

function checkAuth(request: Request, env: Env): boolean {
  const token = env.MCPBR_AUTH_TOKEN;
  if (!token) return false; // Deny access when no auth token is configured
  const header = request.headers.get("Authorization");
  return header === `Bearer ${token}`;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // Health check - no auth required
    if (path === "/health" && request.method === "GET") {
      return jsonResponse({
        status: "ok",
        worker: env.MCPBR_WORKER_NAME,
        benchmark: env.MCPBR_BENCHMARK,
        kv_available: !!env.MCPBR_KV,
        r2_available: !!env.MCPBR_R2,
        timestamp: new Date().toISOString(),
      });
    }

    // Auth check for all other endpoints
    if (!checkAuth(request, env)) {
      return errorResponse("Unauthorized", 401);
    }

    // POST /evaluate - Submit new evaluation
    if (path === "/evaluate" && request.method === "POST") {
      if (!env.MCPBR_KV) {
        return errorResponse("KV namespace not configured", 500);
      }

      let body: EvalRequest;
      try {
        body = await request.json() as EvalRequest;
      } catch {
        return errorResponse("Invalid JSON body");
      }

      if (!body.config) {
        return errorResponse("Missing 'config' field");
      }

      const runId = body.run_id || generateRunId();
      const now = new Date().toISOString();

      const runStatus: RunStatus = {
        run_id: runId,
        status: "pending",
        benchmark: body.benchmark || env.MCPBR_BENCHMARK,
        created_at: now,
        updated_at: now,
      };

      // Store config and status in KV
      await env.MCPBR_KV.put(`config:${runId}`, JSON.stringify(body.config));
      await env.MCPBR_KV.put(`status:${runId}`, JSON.stringify(runStatus));

      return jsonResponse({ run_id: runId, status: "pending" }, 201);
    }

    // GET /status/:runId - Check evaluation status
    const statusMatch = path.match(/^\/status\/(.+)$/);
    if (statusMatch && request.method === "GET") {
      if (!env.MCPBR_KV) {
        return errorResponse("KV namespace not configured", 500);
      }

      const runId = statusMatch[1];
      const statusStr = await env.MCPBR_KV.get(`status:${runId}`);

      if (!statusStr) {
        return errorResponse(`Run not found: ${runId}`, 404);
      }

      return jsonResponse(JSON.parse(statusStr));
    }

    // POST /status/:runId - Update evaluation status (from local evaluator)
    const statusUpdateMatch = path.match(/^\/status\/(.+)$/);
    if (statusUpdateMatch && request.method === "POST") {
      if (!env.MCPBR_KV) {
        return errorResponse("KV namespace not configured", 500);
      }

      const runId = statusUpdateMatch[1];
      const existingStr = await env.MCPBR_KV.get(`status:${runId}`);

      if (!existingStr) {
        return errorResponse(`Run not found: ${runId}`, 404);
      }

      let update: Partial<RunStatus>;
      try {
        update = await request.json() as Partial<RunStatus>;
      } catch {
        return errorResponse("Invalid JSON body");
      }

      const existing = JSON.parse(existingStr) as RunStatus;
      const updated: RunStatus = {
        ...existing,
        ...update,
        run_id: runId, // Prevent overriding run_id
        updated_at: new Date().toISOString(),
      };

      await env.MCPBR_KV.put(`status:${runId}`, JSON.stringify(updated));
      return jsonResponse(updated);
    }

    // GET /results/:runId - Get evaluation results
    const resultsGetMatch = path.match(/^\/results\/(.+)$/);
    if (resultsGetMatch && request.method === "GET") {
      if (!env.MCPBR_KV) {
        return errorResponse("KV namespace not configured", 500);
      }

      const runId = resultsGetMatch[1];
      const resultsStr = await env.MCPBR_KV.get(`results:${runId}`);

      if (!resultsStr) {
        return errorResponse(`Results not found for run: ${runId}`, 404);
      }

      return jsonResponse(JSON.parse(resultsStr));
    }

    // POST /results/:runId - Store evaluation results (from local evaluator)
    const resultsPostMatch = path.match(/^\/results\/(.+)$/);
    if (resultsPostMatch && request.method === "POST") {
      if (!env.MCPBR_KV) {
        return errorResponse("KV namespace not configured", 500);
      }

      const runId = resultsPostMatch[1];

      let results: Record<string, unknown>;
      try {
        results = await request.json() as Record<string, unknown>;
      } catch {
        return errorResponse("Invalid JSON body");
      }

      // Store results
      await env.MCPBR_KV.put(`results:${runId}`, JSON.stringify(results));

      // Update status to completed
      const statusStr = await env.MCPBR_KV.get(`status:${runId}`);
      if (statusStr) {
        const status = JSON.parse(statusStr) as RunStatus;
        status.status = "completed";
        status.updated_at = new Date().toISOString();
        await env.MCPBR_KV.put(`status:${runId}`, JSON.stringify(status));
      }

      // Optionally store in R2 for long-term archival
      if (env.MCPBR_R2) {
        await env.MCPBR_R2.put(
          `results/${runId}.json`,
          JSON.stringify(results, null, 2),
          { httpMetadata: { contentType: "application/json" } }
        );
      }

      return jsonResponse({ run_id: runId, status: "completed", stored: true });
    }

    return errorResponse("Not found", 404);
  },
};
""".strip()

        script_path = deploy_dir / "worker.ts"
        script_path.write_text(worker_script)

        self._console.print("[dim]Generated worker.ts orchestrator script[/dim]")
        return script_path

    # ------------------------------------------------------------------
    # Deployment helpers
    # ------------------------------------------------------------------

    def _run_wrangler(
        self, args: list[str], cwd: str | Path | None = None, timeout: int = 120
    ) -> subprocess.CompletedProcess:
        """Run a wrangler command via npx.

        Args:
            args: Arguments to pass to wrangler (e.g., ["deploy"]).
            cwd: Working directory for the command.
            timeout: Command timeout in seconds.

        Returns:
            CompletedProcess instance.

        Raises:
            RuntimeError: If the command fails.
        """
        cmd = ["npx", "wrangler"] + args
        self._console.print(f"[dim]$ {' '.join(cmd)}[/dim]")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Wrangler command failed: {' '.join(args)}\n"
                f"Exit code: {result.returncode}\n"
                f"Error: {error_msg}"
            )

        return result

    async def _deploy_worker(self, deploy_dir: Path) -> str:
        """Deploy the Worker via wrangler.

        Args:
            deploy_dir: Directory containing wrangler.toml and worker.ts.

        Returns:
            Deployed Worker URL.

        Raises:
            RuntimeError: If deployment fails.
        """
        self._console.print("[cyan]Deploying Cloudflare Worker...[/cyan]")

        result = await asyncio.to_thread(
            self._run_wrangler, ["deploy", "--minify"], cwd=str(deploy_dir), timeout=180
        )

        # Parse Worker URL from deploy output
        worker_url = self._parse_worker_url(result.stdout + result.stderr)
        if not worker_url:
            # Construct URL from known config
            subdomain = getattr(self.cf_config, "workers_subdomain", None)
            if subdomain:
                worker_url = f"https://{self.worker_name}.{subdomain}.workers.dev"
            else:
                raise RuntimeError(
                    "Could not determine Worker URL from deploy output. "
                    "Set 'workers_subdomain' in cloudflare config."
                )

        self.worker_url = worker_url
        self._console.print(f"[green]Worker deployed: {worker_url}[/green]")
        return worker_url

    @staticmethod
    def _parse_worker_url(output: str) -> str | None:
        """Parse the Worker URL from wrangler deploy output.

        Args:
            output: Combined stdout/stderr from wrangler deploy.

        Returns:
            Worker URL string, or None if not found.
        """
        # Wrangler outputs lines like:
        #   Published mcpbr-eval-xxx (x.xx sec)
        #     https://mcpbr-eval-xxx.subdomain.workers.dev
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.startswith("https://") and "workers.dev" in stripped:
                return stripped
        return None

    async def _configure_secrets(self) -> None:
        """Set environment variables as Worker secrets via wrangler.

        Exports keys listed in cf_config.env_keys_to_export from the local
        environment to the deployed Worker as encrypted secrets.
        """
        env_keys = getattr(self.cf_config, "env_keys_to_export", [])
        if not env_keys:
            self._console.print("[dim]No secrets to configure[/dim]")
            return

        self._console.print(f"[cyan]Configuring {len(env_keys)} Worker secret(s)...[/cyan]")

        configured = 0
        for key in env_keys:
            value = os.environ.get(key)
            if not value:
                self._console.print(
                    f"[yellow]Warning: Environment variable '{key}' not found locally, "
                    f"skipping secret[/yellow]"
                )
                continue

            try:
                # wrangler secret put reads from stdin
                cmd = ["npx", "wrangler", "secret", "put", key, "--name", self.worker_name]
                result = subprocess.run(
                    cmd,
                    input=value,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                if result.returncode != 0:
                    self._console.print(
                        f"[yellow]Warning: Failed to set secret '{key}': "
                        f"{result.stderr.strip()[:200]}[/yellow]"
                    )
                else:
                    configured += 1
            except subprocess.TimeoutExpired:
                self._console.print(f"[yellow]Warning: Timeout setting secret '{key}'[/yellow]")

        self._console.print(f"[green]Configured {configured} secret(s)[/green]")

    async def _create_kv_namespace(self) -> str:
        """Create a KV namespace if one is not already configured.

        Returns:
            KV namespace ID.

        Raises:
            RuntimeError: If KV namespace creation fails.
        """
        existing_ns = getattr(self.cf_config, "kv_namespace", None)
        if existing_ns:
            self._console.print(f"[dim]Using existing KV namespace: {existing_ns}[/dim]")
            self.kv_namespace_id = existing_ns
            return existing_ns

        namespace_title = f"mcpbr-{self.worker_name}-kv"
        self._console.print(f"[cyan]Creating KV namespace: {namespace_title}...[/cyan]")

        result = await asyncio.to_thread(
            self._run_wrangler,
            ["kv:namespace", "create", namespace_title, "--json"],
            timeout=60,
        )

        # Parse namespace ID from JSON output
        try:
            # wrangler may output non-JSON lines before the actual JSON
            output = result.stdout.strip()
            # Find the JSON object in the output
            json_start = output.find("{")
            if json_start == -1:
                raise ValueError("No JSON found in output")
            json_str = output[json_start:]
            ns_data = json.loads(json_str)
            ns_id = ns_data.get("id")
            if not ns_id:
                raise ValueError(f"No 'id' field in response: {ns_data}")
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(
                f"Failed to parse KV namespace ID from wrangler output: {e}\nOutput: {output[:500]}"
            ) from e

        self.kv_namespace_id = ns_id
        self._console.print(f"[green]KV namespace created: {ns_id}[/green]")
        return ns_id

    # ------------------------------------------------------------------
    # Worker invocation and polling
    # ------------------------------------------------------------------

    async def _invoke_worker(self, evaluation_config: dict[str, Any]) -> str:
        """Submit an evaluation request to the deployed Worker.

        Args:
            evaluation_config: Serialized evaluation configuration.

        Returns:
            Run ID assigned by the Worker.

        Raises:
            RuntimeError: If invocation fails or Worker returns an error.
        """
        import urllib.error
        import urllib.request

        if not self.worker_url:
            raise RuntimeError("Worker URL not set. Was setup() called?")

        url = f"{self.worker_url}/evaluate"
        payload = json.dumps(
            {
                "benchmark": self.config.benchmark,
                "config": evaluation_config,
            }
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}

        # Add auth token if configured
        auth_token = getattr(self.cf_config, "auth_token", None)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        self._console.print(f"[cyan]Submitting evaluation to Worker: {url}[/cyan]")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            response = await asyncio.to_thread(
                urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT
            )
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"Worker returned HTTP {e.code}: {error_body[:500]}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to Worker: {e.reason}") from e

        run_id = response_data.get("run_id")
        if not run_id:
            raise RuntimeError(f"Worker did not return a run_id: {response_data}")

        self._console.print(f"[green]Evaluation submitted: run_id={run_id}[/green]")
        return run_id

    async def _update_worker_status(
        self, run_id: str, status: str, error: str | None = None
    ) -> None:
        """Update the run status on the Worker.

        Args:
            run_id: Run identifier.
            status: New status value.
            error: Optional error message.
        """
        import urllib.error
        import urllib.request

        if not self.worker_url:
            return

        url = f"{self.worker_url}/status/{run_id}"
        payload_dict: dict[str, Any] = {"status": status}
        if error:
            payload_dict["error"] = error

        payload = json.dumps(payload_dict).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        auth_token = getattr(self.cf_config, "auth_token", None)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT)
        except Exception as e:
            self._console.print(f"[yellow]Warning: Failed to update Worker status: {e}[/yellow]")

    async def _post_results_to_worker(self, run_id: str, results: dict[str, Any]) -> None:
        """Post evaluation results back to the Worker for storage in KV/R2.

        Args:
            run_id: Run identifier.
            results: Serialized evaluation results.
        """
        import urllib.error
        import urllib.request

        if not self.worker_url:
            return

        url = f"{self.worker_url}/results/{run_id}"
        payload = json.dumps(results).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        auth_token = getattr(self.cf_config, "auth_token", None)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            await asyncio.to_thread(urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT)
            self._console.print(f"[green]Results posted to Worker: {url}[/green]")
        except Exception as e:
            self._console.print(f"[yellow]Warning: Failed to post results to Worker: {e}[/yellow]")

    async def _poll_results(
        self,
        run_id: str,
        poll_interval: int = _DEFAULT_POLL_INTERVAL,
        poll_timeout: int = _DEFAULT_POLL_TIMEOUT,
    ) -> dict[str, Any]:
        """Poll the Worker for evaluation completion.

        Args:
            run_id: Run identifier to poll.
            poll_interval: Seconds between poll requests.
            poll_timeout: Maximum seconds to wait before timing out.

        Returns:
            Results dictionary from the Worker.

        Raises:
            RuntimeError: If polling times out or the run fails.
            TimeoutError: If poll_timeout is exceeded.
        """
        import urllib.error
        import urllib.request

        if not self.worker_url:
            raise RuntimeError("Worker URL not set")

        status_url = f"{self.worker_url}/status/{run_id}"
        results_url = f"{self.worker_url}/results/{run_id}"

        headers = {}
        auth_token = getattr(self.cf_config, "auth_token", None)
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        start_time = time.monotonic()
        last_status = "unknown"

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed > poll_timeout:
                raise TimeoutError(
                    f"Evaluation polling timed out after {poll_timeout}s. "
                    f"Last status: {last_status}. Run ID: {run_id}"
                )

            # Check status
            try:
                req = urllib.request.Request(status_url, headers=headers, method="GET")
                response = await asyncio.to_thread(
                    urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT
                )
                status_data = json.loads(response.read().decode("utf-8"))
                current_status = status_data.get("status", "unknown")

                if current_status != last_status:
                    self._console.print(
                        f"[dim]Run {run_id}: status={current_status} "
                        f"(elapsed {int(elapsed)}s)[/dim]"
                    )
                    last_status = current_status

                if current_status == "completed":
                    # Fetch results
                    req = urllib.request.Request(results_url, headers=headers, method="GET")
                    response = await asyncio.to_thread(
                        urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT
                    )
                    return json.loads(response.read().decode("utf-8"))

                if current_status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    raise RuntimeError(
                        f"Evaluation failed on Worker: {error_msg}. Run ID: {run_id}"
                    )

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self._console.print(
                        f"[dim]Run {run_id}: not found yet (elapsed {int(elapsed)}s)[/dim]"
                    )
                else:
                    error_body = e.read().decode("utf-8") if e.fp else ""
                    self._console.print(
                        f"[yellow]Poll error HTTP {e.code}: {error_body[:200]}[/yellow]"
                    )
            except urllib.error.URLError as e:
                self._console.print(f"[yellow]Poll connection error: {e.reason}[/yellow]")
            except TimeoutError:
                raise
            except Exception as e:
                self._console.print(f"[yellow]Poll error: {e}[/yellow]")

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # InfrastructureProvider interface
    # ------------------------------------------------------------------

    async def setup(self) -> None:
        """Deploy Worker, configure secrets, and create KV namespace.

        This method:
        1. Validates benchmark compatibility
        2. Creates a temporary deployment directory
        3. Generates wrangler.toml and worker.ts
        4. Creates KV namespace (if needed)
        5. Updates wrangler.toml with KV binding
        6. Deploys the Worker
        7. Configures secrets

        Raises:
            RuntimeError: If any setup step fails.
        """
        try:
            self._console.print("[cyan]Setting up Cloudflare Workers infrastructure...[/cyan]")

            # 1. Validate benchmark compatibility
            self._check_benchmark_compatibility()

            # 1b. Ensure auth token is available for Worker security
            self._ensure_auth_token()

            # 2. Create temporary deployment directory
            deploy_dir = Path(tempfile.mkdtemp(prefix="mcpbr-cf-"))
            self._deploy_dir = str(deploy_dir)

            # 3. Generate deployment files
            self._generate_wrangler_config(deploy_dir)
            self._generate_worker_script(deploy_dir)

            # Also generate a package.json for wrangler
            package_json = {
                "name": self.worker_name,
                "version": "0.0.1",
                "private": True,
            }
            (deploy_dir / "package.json").write_text(json.dumps(package_json, indent=2))

            # 4. Create KV namespace if needed
            kv_ns_id = await self._create_kv_namespace()

            # 5. Update wrangler.toml with KV namespace binding if we just created one
            existing_kv = getattr(self.cf_config, "kv_namespace", None)
            if not existing_kv and kv_ns_id:
                wrangler_path = deploy_dir / "wrangler.toml"
                existing_content = wrangler_path.read_text()
                # Only add KV binding if not already present
                if "kv_namespaces" not in existing_content:
                    kv_binding = f'\n[[kv_namespaces]]\nbinding = "MCPBR_KV"\nid = "{kv_ns_id}"\n'
                    wrangler_path.write_text(existing_content + kv_binding)

            # 6. Deploy the Worker
            await self._deploy_worker(deploy_dir)

            # 7. Configure secrets
            await self._configure_secrets()

            # 8. Verify deployment with health check against the Worker
            await self._verify_deployment()

            self._console.print("[green]Cloudflare Workers infrastructure ready[/green]")

        except Exception:
            self._error_occurred = True
            raise

    async def _verify_deployment(self) -> None:
        """Verify the deployed Worker is reachable and healthy.

        Raises:
            RuntimeError: If the Worker health check fails.
        """
        import urllib.error
        import urllib.request

        if not self.worker_url:
            return

        health_url = f"{self.worker_url}/health"
        self._console.print(f"[cyan]Verifying Worker deployment: {health_url}[/cyan]")

        # Retry with backoff since the Worker may take a moment to propagate
        max_retries = 5
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(health_url, method="GET")
                response = await asyncio.to_thread(
                    urllib.request.urlopen, req, timeout=_DEFAULT_HTTP_TIMEOUT
                )
                health_data = json.loads(response.read().decode("utf-8"))

                if health_data.get("status") == "ok":
                    self._console.print("[green]Worker health check passed[/green]")
                    return
                else:
                    self._console.print(
                        f"[yellow]Worker returned unexpected health status: {health_data}[/yellow]"
                    )
            except urllib.error.HTTPError as e:
                if attempt < max_retries - 1:
                    self._console.print(
                        f"[dim]Health check attempt {attempt + 1}/{max_retries} "
                        f"failed (HTTP {e.code}), retrying...[/dim]"
                    )
                    await asyncio.sleep(2**attempt)
                else:
                    raise RuntimeError(
                        f"Worker health check failed after {max_retries} attempts: HTTP {e.code}"
                    ) from e
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    self._console.print(
                        f"[dim]Health check attempt {attempt + 1}/{max_retries} "
                        f"failed ({e.reason}), retrying...[/dim]"
                    )
                    await asyncio.sleep(2**attempt)
                else:
                    raise RuntimeError(
                        f"Worker health check failed after {max_retries} attempts: {e.reason}"
                    ) from e

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation using the Cloudflare Worker as orchestrator.

        In this hybrid approach:
        1. Submit evaluation config to Worker (gets run_id)
        2. Run the actual evaluation locally
        3. Post results back to Worker for storage
        4. Return results

        The Worker serves as a coordination point and result store, while the
        actual evaluation logic runs locally (identical to LocalProvider).

        Args:
            config: Harness configuration object.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object with all results.

        Raises:
            RuntimeError: If evaluation fails.
        """
        from ..harness import run_evaluation

        self._console.print(
            "[cyan]Starting hybrid evaluation (Worker orchestration + local execution)...[/cyan]"
        )

        # Serialize config for the Worker
        config_dict = config.model_dump() if hasattr(config, "model_dump") else {}

        # Submit to Worker to get a run_id and register the evaluation
        run_id = await self._invoke_worker(config_dict)

        # Update status to running
        await self._update_worker_status(run_id, "running")

        try:
            # Run evaluation locally (the actual compute happens here)
            self._console.print("[cyan]Running evaluation locally...[/cyan]")
            results = await run_evaluation(
                config=config, run_mcp=run_mcp, run_baseline=run_baseline
            )

            # Serialize results for Worker storage
            results_dict = self._serialize_results(results)

            # Post results to Worker for KV/R2 storage
            await self._post_results_to_worker(run_id, results_dict)

            self._console.print(
                f"[green]Evaluation completed and results stored (run_id={run_id})[/green]"
            )

            return results

        except Exception as e:
            self._error_occurred = True
            # Report failure to Worker
            await self._update_worker_status(run_id, "failed", error=str(e))
            raise

    @staticmethod
    def _serialize_results(results: Any) -> dict[str, Any]:
        """Serialize evaluation results to a JSON-compatible dictionary.

        Args:
            results: EvaluationResults dataclass or similar object.

        Returns:
            JSON-serializable dictionary.
        """
        if hasattr(results, "__dataclass_fields__"):
            from dataclasses import asdict

            return asdict(results)
        elif hasattr(results, "model_dump"):
            return results.model_dump()
        elif hasattr(results, "__dict__"):
            return results.__dict__
        else:
            return {"raw": str(results)}

    async def collect_artifacts(self, output_dir: Path) -> Path:
        """Collect evaluation artifacts into a ZIP archive.

        Downloads results from the Worker KV/R2 and combines with local
        outputs into a single archive.

        Args:
            output_dir: Directory containing local evaluation outputs.

        Returns:
            Path to the created ZIP archive.
        """

        self._console.print("[cyan]Collecting artifacts...[/cyan]")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_path = output_dir.parent / f"artifacts_cf_{timestamp}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add local output files
            if output_dir.exists():
                for file_path in output_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(output_dir)
                        zf.write(file_path, arcname)

            # Add Worker deployment info
            worker_info = {
                "worker_name": self.worker_name,
                "worker_url": self.worker_url,
                "kv_namespace_id": self.kv_namespace_id,
                "timestamp": timestamp,
            }
            zf.writestr(
                "cloudflare/worker_info.json",
                json.dumps(worker_info, indent=2),
            )

            # Try to download KV-stored results from Worker
            if self.worker_url and self.kv_namespace_id:
                try:
                    # List is not directly available via Worker API, but we can
                    # try to get the most recent run's results
                    self._console.print(
                        "[dim]Note: KV results are stored on the Worker and can be "
                        "retrieved via the /results/:runId endpoint[/dim]"
                    )
                except Exception as e:
                    self._console.print(
                        f"[yellow]Warning: Could not retrieve KV artifacts: {e}[/yellow]"
                    )

        self._console.print(f"[green]Artifacts archived: {zip_path}[/green]")
        return zip_path

    async def cleanup(self, force: bool = False) -> None:
        """Delete the Worker and associated KV namespace.

        Respects auto_cleanup and preserve_on_error settings unless
        force=True is specified.

        Args:
            force: If True, force cleanup regardless of settings.
        """
        auto_cleanup = getattr(self.cf_config, "auto_cleanup", True)
        preserve_on_error = getattr(self.cf_config, "preserve_on_error", True)

        should_cleanup = force or (
            auto_cleanup and not (self._error_occurred and preserve_on_error)
        )

        if not should_cleanup:
            self._console.print(f"[yellow]Worker preserved: {self.worker_name}[/yellow]")
            if self.worker_url:
                self._console.print(f"[dim]Worker URL: {self.worker_url}[/dim]")
                self._console.print(
                    f"[dim]Delete with: npx wrangler delete --name {self.worker_name}[/dim]"
                )
            return

        # Delete Worker
        if self.worker_name:
            self._console.print(f"[cyan]Deleting Worker: {self.worker_name}...[/cyan]")
            try:
                await asyncio.to_thread(
                    self._run_wrangler,
                    ["delete", "--name", self.worker_name, "--force"],
                    timeout=60,
                )
                self._console.print("[green]Worker deleted[/green]")
            except RuntimeError as e:
                self._console.print(
                    f"[yellow]Warning: Worker deletion may have failed: {e}[/yellow]"
                )

        # Delete KV namespace (only if we created it, not if pre-existing)
        existing_kv = getattr(self.cf_config, "kv_namespace", None)
        if self.kv_namespace_id and not existing_kv:
            self._console.print(f"[cyan]Deleting KV namespace: {self.kv_namespace_id}...[/cyan]")
            try:
                await asyncio.to_thread(
                    self._run_wrangler,
                    ["kv:namespace", "delete", "--namespace-id", self.kv_namespace_id],
                    timeout=60,
                )
                self._console.print("[green]KV namespace deleted[/green]")
            except RuntimeError as e:
                self._console.print(
                    f"[yellow]Warning: KV namespace deletion may have failed: {e}[/yellow]"
                )

        # Clean up temporary deployment directory
        if self._deploy_dir:
            deploy_path = Path(self._deploy_dir)
            if deploy_path.exists():
                import shutil

                shutil.rmtree(deploy_path, ignore_errors=True)
                self._console.print("[dim]Cleaned up temporary deployment files[/dim]")

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run pre-flight validation checks for Cloudflare Workers.

        Checks:
        1. wrangler CLI is installed and accessible
        2. wrangler is authenticated to Cloudflare
        3. Account access is valid
        4. Benchmark compatibility

        Args:
            **kwargs: Provider-specific health check parameters.

        Returns:
            Dictionary with health check results:
                - healthy (bool): Overall health status
                - checks (list): List of individual check results
                - failures (list): List of failure messages
                - warnings (list): Non-fatal issues
        """
        checks: list[dict[str, Any]] = []
        failures: list[str] = []
        warnings: list[str] = []

        # Check 1: Wrangler CLI installed
        wrangler_ok, wrangler_msg = self._check_wrangler_installed()
        checks.append(
            {
                "name": "wrangler_cli",
                "passed": wrangler_ok,
                "message": wrangler_msg,
            }
        )
        if not wrangler_ok:
            failures.append(f"Wrangler CLI: {wrangler_msg}")

        # Check 2: Wrangler authenticated (only if CLI is available)
        if wrangler_ok:
            auth_ok, auth_msg = self._check_wrangler_authenticated()
            checks.append(
                {
                    "name": "wrangler_auth",
                    "passed": auth_ok,
                    "message": auth_msg,
                }
            )
            if not auth_ok:
                failures.append(f"Wrangler auth: {auth_msg}")

        # Check 3: Account ID configured
        account_id = getattr(self.cf_config, "account_id", None)
        account_ok = bool(account_id)
        account_msg = (
            f"Account ID: {account_id}"
            if account_ok
            else "No account_id configured in cloudflare config"
        )
        checks.append(
            {
                "name": "account_id",
                "passed": account_ok,
                "message": account_msg,
            }
        )
        if not account_ok:
            # Account ID can sometimes be inferred by wrangler, so this is a warning
            warnings.append("No account_id configured. Wrangler may prompt for account selection.")

        # Check 4: Benchmark compatibility
        benchmark = self.config.benchmark
        if benchmark in self.DOCKER_REQUIRED_BENCHMARKS:
            compat_ok = False
            compat_msg = (
                f"Benchmark '{benchmark}' requires Docker and cannot run on Cloudflare Workers"
            )
            failures.append(compat_msg)
        elif benchmark in self.SUPPORTED_BENCHMARKS or benchmark == "custom":
            compat_ok = True
            compat_msg = f"Benchmark '{benchmark}' is compatible with Cloudflare Workers"
        else:
            compat_ok = True
            compat_msg = f"Benchmark '{benchmark}' has not been verified for Cloudflare Workers"
            warnings.append(compat_msg)

        checks.append(
            {
                "name": "benchmark_compatibility",
                "passed": compat_ok,
                "message": compat_msg,
            }
        )

        # Check 5: Node.js available (required for npx)
        node_ok, node_msg = self._check_node_installed()
        checks.append(
            {
                "name": "nodejs",
                "passed": node_ok,
                "message": node_msg,
            }
        )
        if not node_ok:
            failures.append(f"Node.js: {node_msg}")

        healthy = len(failures) == 0

        result: dict[str, Any] = {
            "healthy": healthy,
            "checks": checks,
            "failures": failures,
        }
        if warnings:
            result["warnings"] = warnings

        return result

    # ------------------------------------------------------------------
    # Health check helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_wrangler_installed() -> tuple[bool, str]:
        """Check if wrangler CLI is available.

        Returns:
            Tuple of (success, message).
        """
        # Try npx wrangler --version first
        try:
            result = subprocess.run(
                ["npx", "wrangler", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                return True, f"wrangler {version} (via npx)"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try direct wrangler command
        try:
            command = "where" if platform.system() == "Windows" else "which"
            result = subprocess.run(
                [command, "wrangler"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                return True, f"wrangler at {result.stdout.strip()}"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return (
            False,
            "Wrangler CLI not found. Install with: npm install -g wrangler or use npx wrangler",
        )

    @staticmethod
    def _check_wrangler_authenticated() -> tuple[bool, str]:
        """Check if wrangler is authenticated to Cloudflare.

        Returns:
            Tuple of (success, message).
        """
        try:
            result = subprocess.run(
                ["npx", "wrangler", "whoami"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                # Parse account info from whoami output
                for line in output.splitlines():
                    if "account" in line.lower() or "@" in line or "token" in line.lower():
                        return True, line.strip()
                return True, "Authenticated (details in wrangler whoami)"
            else:
                return (
                    False,
                    "Not authenticated to Cloudflare. Run 'npx wrangler login' to authenticate.",
                )
        except FileNotFoundError:
            return False, "npx not found"
        except subprocess.TimeoutExpired:
            return False, "Wrangler whoami timed out"
        except Exception as e:
            return False, f"Error checking wrangler authentication: {e}"

    @staticmethod
    def _check_node_installed() -> tuple[bool, str]:
        """Check if Node.js is installed.

        Returns:
            Tuple of (success, message).
        """
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return True, f"Node.js {version}"
            else:
                return False, "Node.js not found"
        except FileNotFoundError:
            return (
                False,
                "Node.js not found. Install from https://nodejs.org or via nvm.",
            )
        except subprocess.TimeoutExpired:
            return False, "Node.js version check timed out"
        except Exception as e:
            return False, f"Error checking Node.js: {e}"
