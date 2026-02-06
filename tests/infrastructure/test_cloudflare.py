"""Tests for Cloudflare Workers infrastructure provider."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from mcpbr.infrastructure.cloudflare import CloudflareProvider


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock HarnessConfig with Cloudflare settings."""
    config = MagicMock()
    config.infrastructure.mode = "cloudflare"
    config.infrastructure.cloudflare = MagicMock()
    config.infrastructure.cloudflare.account_id = "test-account-id"
    config.infrastructure.cloudflare.workers_subdomain = "test-subdomain"
    config.infrastructure.cloudflare.worker_name = None
    config.infrastructure.cloudflare.auto_cleanup = True
    config.infrastructure.cloudflare.preserve_on_error = True
    config.infrastructure.cloudflare.env_keys_to_export = ["ANTHROPIC_API_KEY"]
    config.infrastructure.cloudflare.kv_namespace = None
    config.infrastructure.cloudflare.r2_bucket = None
    config.infrastructure.cloudflare.compatibility_date = "2024-09-23"
    config.infrastructure.cloudflare.cpu_ms = 30000
    config.infrastructure.cloudflare.auth_token = None
    config.benchmark = "gsm8k"
    config.task_ids = None
    config.model_dump.return_value = {"infrastructure": {"mode": "cloudflare"}}
    return config


@pytest.fixture
def cf_provider(mock_config: MagicMock) -> CloudflareProvider:
    """Create a Cloudflare provider instance with mocked config."""
    return CloudflareProvider(mock_config)


# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    """Test CloudflareProvider initialization."""

    def test_init_sets_config(
        self, cf_provider: CloudflareProvider, mock_config: MagicMock
    ) -> None:
        """Test provider stores config reference."""
        assert cf_provider.config is mock_config

    def test_init_sets_cf_config(self, cf_provider: CloudflareProvider) -> None:
        """Test provider stores cf_config reference."""
        assert cf_provider.cf_config is not None

    def test_init_worker_name_none(self, cf_provider: CloudflareProvider) -> None:
        """Test worker_name is None initially."""
        assert cf_provider.worker_name is None

    def test_init_worker_url_none(self, cf_provider: CloudflareProvider) -> None:
        """Test worker_url is None initially."""
        assert cf_provider.worker_url is None

    def test_init_kv_namespace_id_none(self, cf_provider: CloudflareProvider) -> None:
        """Test kv_namespace_id is None initially."""
        assert cf_provider.kv_namespace_id is None

    def test_init_error_occurred_false(self, cf_provider: CloudflareProvider) -> None:
        """Test _error_occurred is False initially."""
        assert cf_provider._error_occurred is False

    def test_init_deploy_dir_none(self, cf_provider: CloudflareProvider) -> None:
        """Test _deploy_dir is None initially."""
        assert cf_provider._deploy_dir is None


# ============================================================================
# Benchmark Compatibility Tests
# ============================================================================


class TestBenchmarkCompatibility:
    """Test _check_benchmark_compatibility method."""

    def test_supported_benchmark_gsm8k(self, cf_provider: CloudflareProvider) -> None:
        """Test gsm8k is a supported benchmark."""
        cf_provider.config.benchmark = "gsm8k"
        # Should not raise
        cf_provider._check_benchmark_compatibility()

    def test_supported_benchmark_humaneval(self, cf_provider: CloudflareProvider) -> None:
        """Test humaneval is a supported benchmark."""
        cf_provider.config.benchmark = "humaneval"
        cf_provider._check_benchmark_compatibility()

    def test_docker_required_swe_bench_raises(self, cf_provider: CloudflareProvider) -> None:
        """Test swe-bench-lite raises RuntimeError (requires Docker)."""
        cf_provider.config.benchmark = "swe-bench-lite"

        with pytest.raises(RuntimeError, match="requires Docker"):
            cf_provider._check_benchmark_compatibility()

    def test_docker_required_cybergym_raises(self, cf_provider: CloudflareProvider) -> None:
        """Test cybergym raises RuntimeError (requires Docker)."""
        cf_provider.config.benchmark = "cybergym"

        with pytest.raises(RuntimeError, match="requires Docker"):
            cf_provider._check_benchmark_compatibility()

    def test_docker_required_terminalbench_raises(self, cf_provider: CloudflareProvider) -> None:
        """Test terminalbench raises RuntimeError (requires Docker)."""
        cf_provider.config.benchmark = "terminalbench"

        with pytest.raises(RuntimeError, match="requires Docker"):
            cf_provider._check_benchmark_compatibility()

    def test_custom_benchmark_allowed(self, cf_provider: CloudflareProvider) -> None:
        """Test 'custom' benchmark is allowed without warning."""
        cf_provider.config.benchmark = "custom"
        # Should not raise
        cf_provider._check_benchmark_compatibility()

    def test_unknown_benchmark_warns(self, cf_provider: CloudflareProvider) -> None:
        """Test unknown benchmark does not raise but prints a warning."""
        cf_provider.config.benchmark = "unknown-benchmark"
        # Should not raise
        cf_provider._check_benchmark_compatibility()

    def test_supported_benchmarks_set(self) -> None:
        """Test SUPPORTED_BENCHMARKS contains expected benchmarks."""
        assert "gsm8k" in CloudflareProvider.SUPPORTED_BENCHMARKS
        assert "humaneval" in CloudflareProvider.SUPPORTED_BENCHMARKS
        assert "mbpp" in CloudflareProvider.SUPPORTED_BENCHMARKS

    def test_docker_required_benchmarks_set(self) -> None:
        """Test DOCKER_REQUIRED_BENCHMARKS contains expected benchmarks."""
        assert "swe-bench-lite" in CloudflareProvider.DOCKER_REQUIRED_BENCHMARKS
        assert "swe-bench-verified" in CloudflareProvider.DOCKER_REQUIRED_BENCHMARKS
        assert "cybergym" in CloudflareProvider.DOCKER_REQUIRED_BENCHMARKS


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test Cloudflare health checks."""

    @patch.object(CloudflareProvider, "_check_node_installed")
    @patch.object(CloudflareProvider, "_check_wrangler_authenticated")
    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_all_pass(
        self,
        mock_wrangler: MagicMock,
        mock_auth: MagicMock,
        mock_node: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check when all checks pass with supported benchmark."""
        mock_wrangler.return_value = (True, "wrangler 3.0.0 (via npx)")
        mock_auth.return_value = (True, "Authenticated")
        mock_node.return_value = (True, "Node.js v22.0.0")

        result = await cf_provider.health_check()

        assert result["healthy"] is True
        assert len(result["failures"]) == 0

    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_wrangler_not_installed(
        self,
        mock_wrangler: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check when wrangler is not installed."""
        mock_wrangler.return_value = (False, "Wrangler CLI not found")

        result = await cf_provider.health_check()

        assert result["healthy"] is False
        assert any("Wrangler" in f for f in result["failures"])

    @patch.object(CloudflareProvider, "_check_node_installed")
    @patch.object(CloudflareProvider, "_check_wrangler_authenticated")
    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_not_authenticated(
        self,
        mock_wrangler: MagicMock,
        mock_auth: MagicMock,
        mock_node: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check when not authenticated."""
        mock_wrangler.return_value = (True, "wrangler found")
        mock_auth.return_value = (False, "Not authenticated")
        mock_node.return_value = (True, "Node.js v22.0.0")

        result = await cf_provider.health_check()

        assert result["healthy"] is False
        assert any("auth" in f.lower() for f in result["failures"])

    @patch.object(CloudflareProvider, "_check_node_installed")
    @patch.object(CloudflareProvider, "_check_wrangler_authenticated")
    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_docker_benchmark_fails(
        self,
        mock_wrangler: MagicMock,
        mock_auth: MagicMock,
        mock_node: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check fails for Docker-required benchmark."""
        mock_wrangler.return_value = (True, "wrangler found")
        mock_auth.return_value = (True, "Authenticated")
        mock_node.return_value = (True, "Node.js v22.0.0")
        cf_provider.config.benchmark = "swe-bench-lite"

        result = await cf_provider.health_check()

        assert result["healthy"] is False
        assert any("Docker" in f for f in result["failures"])

    @patch.object(CloudflareProvider, "_check_node_installed")
    @patch.object(CloudflareProvider, "_check_wrangler_authenticated")
    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_missing_account_id_warning(
        self,
        mock_wrangler: MagicMock,
        mock_auth: MagicMock,
        mock_node: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check when account_id is missing is a warning."""
        mock_wrangler.return_value = (True, "wrangler found")
        mock_auth.return_value = (True, "Authenticated")
        mock_node.return_value = (True, "Node.js v22.0.0")
        cf_provider.cf_config.account_id = None

        result = await cf_provider.health_check()

        # Missing account_id is a warning, not an error
        assert "warnings" in result
        assert any("account_id" in w.lower() for w in result.get("warnings", []))

    @patch.object(CloudflareProvider, "_check_node_installed")
    @patch.object(CloudflareProvider, "_check_wrangler_authenticated")
    @patch.object(CloudflareProvider, "_check_wrangler_installed")
    async def test_health_check_node_not_installed(
        self,
        mock_wrangler: MagicMock,
        mock_auth: MagicMock,
        mock_node: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test health check when Node.js is not installed."""
        mock_wrangler.return_value = (True, "wrangler found")
        mock_auth.return_value = (True, "Authenticated")
        mock_node.return_value = (False, "Node.js not found")

        result = await cf_provider.health_check()

        assert result["healthy"] is False
        assert any("Node.js" in f for f in result["failures"])


# ============================================================================
# Health Check Helpers Tests
# ============================================================================


class TestHealthCheckHelpers:
    """Test health check helper methods."""

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_wrangler_installed_via_npx(self, mock_run: MagicMock) -> None:
        """Test wrangler check when available via npx."""
        mock_run.return_value = Mock(returncode=0, stdout="3.0.0\n")
        ok, msg = CloudflareProvider._check_wrangler_installed()
        assert ok is True
        assert "npx" in msg

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_wrangler_installed_not_found(self, mock_run: MagicMock) -> None:
        """Test wrangler check when not installed."""
        mock_run.side_effect = FileNotFoundError("npx not found")
        ok, msg = CloudflareProvider._check_wrangler_installed()
        assert ok is False

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_wrangler_authenticated_success(self, mock_run: MagicMock) -> None:
        """Test wrangler auth check when authenticated."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Getting accounts...\naccount: test@example.com\n",
        )
        ok, msg = CloudflareProvider._check_wrangler_authenticated()
        assert ok is True

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_wrangler_authenticated_failure(self, mock_run: MagicMock) -> None:
        """Test wrangler auth check when not authenticated."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Not authenticated",
        )
        ok, msg = CloudflareProvider._check_wrangler_authenticated()
        assert ok is False

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_node_installed_success(self, mock_run: MagicMock) -> None:
        """Test Node.js check when installed."""
        mock_run.return_value = Mock(returncode=0, stdout="v22.0.0\n")
        ok, msg = CloudflareProvider._check_node_installed()
        assert ok is True
        assert "v22.0.0" in msg

    @patch("mcpbr.infrastructure.cloudflare.subprocess.run")
    def test_check_node_installed_not_found(self, mock_run: MagicMock) -> None:
        """Test Node.js check when not installed."""
        mock_run.side_effect = FileNotFoundError("node not found")
        ok, msg = CloudflareProvider._check_node_installed()
        assert ok is False


# ============================================================================
# Wrangler Config Generation Tests
# ============================================================================


class TestWranglerConfigGeneration:
    """Test _generate_wrangler_config method."""

    def test_generates_wrangler_toml(self, cf_provider: CloudflareProvider, tmp_path: Path) -> None:
        """Test wrangler.toml is generated in deploy dir."""
        config_path = cf_provider._generate_wrangler_config(tmp_path)

        assert config_path.exists()
        assert config_path.name == "wrangler.toml"

    def test_wrangler_toml_contains_worker_name(
        self, cf_provider: CloudflareProvider, tmp_path: Path
    ) -> None:
        """Test wrangler.toml contains the worker name."""
        cf_provider.cf_config.worker_name = "test-worker"
        config_path = cf_provider._generate_wrangler_config(tmp_path)

        content = config_path.read_text()
        assert "test-worker" in content

    def test_wrangler_toml_contains_account_id(
        self, cf_provider: CloudflareProvider, tmp_path: Path
    ) -> None:
        """Test wrangler.toml contains account_id."""
        config_path = cf_provider._generate_wrangler_config(tmp_path)

        content = config_path.read_text()
        assert "test-account-id" in content

    def test_wrangler_toml_contains_benchmark(
        self, cf_provider: CloudflareProvider, tmp_path: Path
    ) -> None:
        """Test wrangler.toml contains the benchmark name."""
        cf_provider.config.benchmark = "humaneval"
        config_path = cf_provider._generate_wrangler_config(tmp_path)

        content = config_path.read_text()
        assert "humaneval" in content

    def test_worker_name_auto_generated(
        self, cf_provider: CloudflareProvider, tmp_path: Path
    ) -> None:
        """Test worker name is auto-generated when not configured."""
        cf_provider.cf_config.worker_name = None
        cf_provider._generate_wrangler_config(tmp_path)

        assert cf_provider.worker_name is not None
        assert "mcpbr-eval-" in cf_provider.worker_name


# ============================================================================
# Worker Script Generation Tests
# ============================================================================


class TestWorkerScriptGeneration:
    """Test _generate_worker_script method."""

    def test_generates_worker_ts(self, cf_provider: CloudflareProvider, tmp_path: Path) -> None:
        """Test worker.ts is generated in deploy dir."""
        script_path = cf_provider._generate_worker_script(tmp_path)

        assert script_path.exists()
        assert script_path.name == "worker.ts"

    def test_worker_ts_contains_endpoints(
        self, cf_provider: CloudflareProvider, tmp_path: Path
    ) -> None:
        """Test worker.ts contains expected API endpoints."""
        script_path = cf_provider._generate_worker_script(tmp_path)

        content = script_path.read_text()
        assert "/health" in content
        assert "/evaluate" in content
        assert "/status/" in content
        assert "/results/" in content


# ============================================================================
# Parse Worker URL Tests
# ============================================================================


class TestParseWorkerUrl:
    """Test _parse_worker_url static method."""

    def test_parse_url_from_deploy_output(self) -> None:
        """Test parsing Worker URL from wrangler deploy output."""
        output = (
            "Published mcpbr-eval-123 (1.23 sec)\n"
            "  https://mcpbr-eval-123.subdomain.workers.dev\n"
            "Done."
        )
        url = CloudflareProvider._parse_worker_url(output)
        assert url == "https://mcpbr-eval-123.subdomain.workers.dev"

    def test_parse_url_not_found(self) -> None:
        """Test parsing Worker URL when not in output."""
        output = "Some output without a URL"
        url = CloudflareProvider._parse_worker_url(output)
        assert url is None

    def test_parse_url_non_workers_url(self) -> None:
        """Test parsing ignores non-workers.dev URLs."""
        output = "See https://cloudflare.com/docs for more info"
        url = CloudflareProvider._parse_worker_url(output)
        assert url is None


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Test Cloudflare resource cleanup."""

    @patch.object(CloudflareProvider, "_run_wrangler")
    async def test_cleanup_deletes_worker(
        self,
        mock_wrangler: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test cleanup deletes the Worker."""
        cf_provider.worker_name = "test-worker"
        cf_provider.cf_config.auto_cleanup = True
        cf_provider.cf_config.preserve_on_error = False
        mock_wrangler.return_value = Mock(returncode=0)

        await cf_provider.cleanup()

        # Verify wrangler delete was called
        assert mock_wrangler.call_count >= 1
        calls = mock_wrangler.call_args_list
        assert any("delete" in str(call) for call in calls)

    async def test_cleanup_preserve_on_error(self, cf_provider: CloudflareProvider) -> None:
        """Test cleanup preserves worker when error occurred and preserve_on_error is True."""
        cf_provider.worker_name = "test-worker"
        cf_provider.worker_url = "https://test-worker.workers.dev"
        cf_provider._error_occurred = True
        cf_provider.cf_config.preserve_on_error = True
        cf_provider.cf_config.auto_cleanup = True

        # Should not raise
        await cf_provider.cleanup()

    @patch.object(CloudflareProvider, "_run_wrangler")
    async def test_cleanup_force_ignores_preserve(
        self,
        mock_wrangler: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test forced cleanup ignores preserve_on_error."""
        cf_provider.worker_name = "test-worker"
        cf_provider._error_occurred = True
        cf_provider.cf_config.preserve_on_error = True
        mock_wrangler.return_value = Mock(returncode=0)

        await cf_provider.cleanup(force=True)

        # Should still delete
        assert mock_wrangler.call_count >= 1

    async def test_cleanup_no_worker(self, cf_provider: CloudflareProvider) -> None:
        """Test cleanup when no worker exists does nothing."""
        cf_provider.worker_name = None
        cf_provider.cf_config.auto_cleanup = True
        cf_provider.cf_config.preserve_on_error = False

        # Should not raise
        await cf_provider.cleanup()

    @patch.object(CloudflareProvider, "_run_wrangler")
    async def test_cleanup_deletes_kv_namespace(
        self,
        mock_wrangler: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test cleanup deletes KV namespace if we created it."""
        cf_provider.worker_name = "test-worker"
        cf_provider.kv_namespace_id = "abc123"
        cf_provider.cf_config.kv_namespace = None  # We created it
        cf_provider.cf_config.auto_cleanup = True
        cf_provider.cf_config.preserve_on_error = False
        mock_wrangler.return_value = Mock(returncode=0)

        await cf_provider.cleanup()

        calls = mock_wrangler.call_args_list
        assert any("kv:namespace" in str(call) for call in calls)

    @patch.object(CloudflareProvider, "_run_wrangler")
    async def test_cleanup_skips_preexisting_kv(
        self,
        mock_wrangler: MagicMock,
        cf_provider: CloudflareProvider,
    ) -> None:
        """Test cleanup does not delete pre-existing KV namespace."""
        cf_provider.worker_name = "test-worker"
        cf_provider.kv_namespace_id = "abc123"
        cf_provider.cf_config.kv_namespace = "abc123"  # Pre-existing
        cf_provider.cf_config.auto_cleanup = True
        cf_provider.cf_config.preserve_on_error = False
        mock_wrangler.return_value = Mock(returncode=0)

        await cf_provider.cleanup()

        calls = mock_wrangler.call_args_list
        # Should not call kv:namespace delete for pre-existing
        assert not any("kv:namespace" in str(call) and "delete" in str(call) for call in calls)


# ============================================================================
# Serialize Results Tests
# ============================================================================


class TestSerializeResults:
    """Test _serialize_results static method."""

    def test_serialize_dataclass(self) -> None:
        """Test serializing a dataclass result."""
        from dataclasses import dataclass

        @dataclass
        class FakeResults:
            metadata: dict
            summary: dict
            tasks: list

        results = FakeResults(metadata={}, summary={"total": 10}, tasks=[])
        serialized = CloudflareProvider._serialize_results(results)

        assert serialized["summary"]["total"] == 10

    def test_serialize_pydantic_model(self) -> None:
        """Test serializing an object with model_dump."""
        mock_results = MagicMock()
        mock_results.__dataclass_fields__ = None  # Not a dataclass
        mock_results.model_dump.return_value = {"metadata": {}, "tasks": []}

        # Remove __dataclass_fields__ to trigger model_dump branch
        del mock_results.__dataclass_fields__
        serialized = CloudflareProvider._serialize_results(mock_results)

        assert "metadata" in serialized

    def test_serialize_fallback(self) -> None:
        """Test serializing an object without standard methods."""

        class PlainResult:
            def __init__(self):
                self.data = "test"

        result = PlainResult()
        serialized = CloudflareProvider._serialize_results(result)

        assert serialized["data"] == "test"
