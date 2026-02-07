"""Tests for Kubernetes infrastructure provider."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mcpbr.infrastructure.k8s import KubernetesProvider


@pytest.fixture
def mock_config() -> MagicMock:
    """Create a mock HarnessConfig with Kubernetes settings."""
    config = MagicMock()
    config.infrastructure.mode = "kubernetes"
    config.infrastructure.kubernetes = MagicMock()
    config.infrastructure.kubernetes.context = None
    config.infrastructure.kubernetes.namespace = "mcpbr"
    config.infrastructure.kubernetes.image = "ghcr.io/greynewell/mcpbr:latest"
    config.infrastructure.kubernetes.image_pull_policy = "IfNotPresent"
    config.infrastructure.kubernetes.cpu_request = "1"
    config.infrastructure.kubernetes.cpu_limit = "4"
    config.infrastructure.kubernetes.memory_request = "2Gi"
    config.infrastructure.kubernetes.memory_limit = "8Gi"
    config.infrastructure.kubernetes.parallelism = 2
    config.infrastructure.kubernetes.backoff_limit = 3
    config.infrastructure.kubernetes.ttl_seconds_after_finished = 3600
    config.infrastructure.kubernetes.env_keys_to_export = ["ANTHROPIC_API_KEY"]
    config.infrastructure.kubernetes.enable_dind = False
    config.infrastructure.kubernetes.dind_privileged = False
    config.infrastructure.kubernetes.auto_cleanup = True
    config.infrastructure.kubernetes.preserve_on_error = True
    config.infrastructure.kubernetes.node_selector = {}
    config.infrastructure.kubernetes.tolerations = []
    config.infrastructure.kubernetes.labels = {}
    config.infrastructure.kubernetes.config_map_name = None
    config.infrastructure.kubernetes.secret_name = None
    config.infrastructure.kubernetes.job_name = None
    config.benchmark = "swe-bench-lite"
    config.task_ids = None
    config.model_dump.return_value = {"infrastructure": {"mode": "kubernetes"}}
    return config


@pytest.fixture
def k8s_provider(mock_config: MagicMock) -> KubernetesProvider:
    """Create a Kubernetes provider instance with mocked config."""
    return KubernetesProvider(mock_config)


# ============================================================================
# Initialization Tests
# ============================================================================


class TestInitialization:
    """Test KubernetesProvider initialization."""

    def test_init_sets_config(
        self, k8s_provider: KubernetesProvider, mock_config: MagicMock
    ) -> None:
        """Test provider stores config reference."""
        assert k8s_provider.config is mock_config

    def test_init_sets_k8s_config(self, k8s_provider: KubernetesProvider) -> None:
        """Test provider stores k8s_config reference."""
        assert k8s_provider.k8s_config is not None

    def test_init_namespace_none(self, k8s_provider: KubernetesProvider) -> None:
        """Test namespace is None initially."""
        assert k8s_provider.namespace is None

    def test_init_job_name_none(self, k8s_provider: KubernetesProvider) -> None:
        """Test job_name is None initially."""
        assert k8s_provider.job_name is None

    def test_init_error_occurred_false(self, k8s_provider: KubernetesProvider) -> None:
        """Test _error_occurred is False initially."""
        assert k8s_provider._error_occurred is False


# ============================================================================
# Resource Labels Tests
# ============================================================================


class TestResourceLabels:
    """Test _resource_labels method."""

    def test_resource_labels_default(self, k8s_provider: KubernetesProvider) -> None:
        """Test default resource labels contain required keys."""
        labels = k8s_provider._resource_labels()

        assert "app.kubernetes.io/name" in labels
        assert labels["app.kubernetes.io/name"] == "mcpbr"
        assert "app.kubernetes.io/component" in labels
        assert labels["app.kubernetes.io/component"] == "evaluation"
        assert "app.kubernetes.io/managed-by" in labels
        assert labels["app.kubernetes.io/managed-by"] == "mcpbr-k8s-provider"

    def test_resource_labels_with_extra_labels(self, k8s_provider: KubernetesProvider) -> None:
        """Test resource labels merge extra labels from config."""
        # Make _cfg return extra labels for 'labels' key
        k8s_provider.k8s_config.labels = {"team": "ml-infra", "env": "test"}

        labels = k8s_provider._resource_labels()

        assert labels["app.kubernetes.io/name"] == "mcpbr"
        assert labels["team"] == "ml-infra"
        assert labels["env"] == "test"

    def test_resource_labels_extra_dont_override_defaults(
        self, k8s_provider: KubernetesProvider
    ) -> None:
        """Test extra labels can override default labels."""
        k8s_provider.k8s_config.labels = {"app.kubernetes.io/name": "custom"}

        labels = k8s_provider._resource_labels()

        # Extra labels override defaults
        assert labels["app.kubernetes.io/name"] == "custom"


# ============================================================================
# Job Manifest Generation Tests
# ============================================================================


class TestGenerateJobManifest:
    """Test _generate_job_manifest method."""

    def test_manifest_structure(self, k8s_provider: KubernetesProvider) -> None:
        """Test generated manifest has correct top-level structure."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        assert manifest["apiVersion"] == "batch/v1"
        assert manifest["kind"] == "Job"
        assert "metadata" in manifest
        assert "spec" in manifest

    def test_manifest_metadata(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest metadata contains name, namespace, and labels."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        metadata = manifest["metadata"]
        assert metadata["namespace"] == "mcpbr"
        assert "name" in metadata
        assert "labels" in metadata
        assert metadata["labels"]["app.kubernetes.io/name"] == "mcpbr"

    def test_manifest_spec_parallelism(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest spec contains parallelism."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        spec = manifest["spec"]
        assert "parallelism" in spec
        assert "completions" in spec
        assert "backoffLimit" in spec

    def test_manifest_container_resources(self, k8s_provider: KubernetesProvider) -> None:
        """Test container has resource requests and limits."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        main_container = containers[0]
        assert main_container["name"] == "mcpbr-eval"
        assert "resources" in main_container
        assert "requests" in main_container["resources"]
        assert "limits" in main_container["resources"]

    def test_manifest_config_volume_mount(self, k8s_provider: KubernetesProvider) -> None:
        """Test container has ConfigMap volume mount."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        main_container = containers[0]
        vol_mounts = main_container["volumeMounts"]
        assert any(vm["name"] == "config-volume" for vm in vol_mounts)

    def test_manifest_with_secret(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest includes secret env vars when secret_name is provided."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", "test-secret")

        containers = manifest["spec"]["template"]["spec"]["containers"]
        main_container = containers[0]
        assert "env" in main_container
        # At least one env var referencing the secret
        assert any(
            e.get("valueFrom", {}).get("secretKeyRef", {}).get("name") == "test-secret"
            for e in main_container["env"]
        )

    def test_manifest_without_secret(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest has no secret env vars when secret_name is None."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        main_container = containers[0]
        # 'env' key should not be present (or empty) when no secret
        env = main_container.get("env", [])
        assert not any("secretKeyRef" in str(e) for e in env)

    def test_manifest_dind_sidecar(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest includes DinD sidecar when enable_dind is True."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        container_names = [c["name"] for c in containers]
        assert "dind" in container_names

    def test_manifest_no_dind_by_default(self, k8s_provider: KubernetesProvider) -> None:
        """Test manifest does not include DinD sidecar when enable_dind is False."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = False

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        container_names = [c["name"] for c in containers]
        assert "dind" not in container_names

    def test_manifest_restart_policy_never(self, k8s_provider: KubernetesProvider) -> None:
        """Test pod spec has restartPolicy: Never."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        pod_spec = manifest["spec"]["template"]["spec"]
        assert pod_spec["restartPolicy"] == "Never"

    def test_manifest_command(self, k8s_provider: KubernetesProvider) -> None:
        """Test container command runs mcpbr with config path."""
        k8s_provider.namespace = "mcpbr"
        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        main_container = containers[0]
        assert "mcpbr" in main_container["command"]
        assert "/etc/mcpbr/config.yaml" in main_container["command"]


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test Kubernetes health checks."""

    @patch.object(KubernetesProvider, "_check_resource_quotas")
    @patch.object(KubernetesProvider, "_check_namespace")
    @patch.object(KubernetesProvider, "_check_cluster_access")
    @patch.object(KubernetesProvider, "_check_kubectl_installed")
    async def test_health_check_all_pass(
        self,
        mock_kubectl: MagicMock,
        mock_cluster: MagicMock,
        mock_ns: MagicMock,
        mock_quota: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test health check when all checks pass."""
        mock_kubectl.return_value = (True, "kubectl found at /usr/local/bin/kubectl")
        mock_cluster.return_value = (True, "Cluster accessible")
        mock_ns.return_value = (True, "Namespace 'mcpbr' exists")
        mock_quota.return_value = (True, "No resource quotas found")

        result = await k8s_provider.health_check()

        assert result["healthy"] is True
        assert len(result["failures"]) == 0

    @patch.object(KubernetesProvider, "_check_kubectl_installed")
    async def test_health_check_kubectl_not_installed(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test health check when kubectl is not installed."""
        mock_kubectl.return_value = (False, "kubectl not found")

        result = await k8s_provider.health_check()

        assert result["healthy"] is False
        assert len(result["failures"]) > 0
        assert any("kubectl" in f.lower() for f in result["failures"])

    @patch.object(KubernetesProvider, "_check_cluster_access")
    @patch.object(KubernetesProvider, "_check_kubectl_installed")
    async def test_health_check_cluster_unreachable(
        self,
        mock_kubectl: MagicMock,
        mock_cluster: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test health check when cluster is unreachable."""
        mock_kubectl.return_value = (True, "kubectl found")
        mock_cluster.return_value = (False, "Cannot reach cluster")

        result = await k8s_provider.health_check()

        assert result["healthy"] is False
        assert len(result["failures"]) > 0

    @patch.object(KubernetesProvider, "_check_resource_quotas")
    @patch.object(KubernetesProvider, "_check_namespace")
    @patch.object(KubernetesProvider, "_check_cluster_access")
    @patch.object(KubernetesProvider, "_check_kubectl_installed")
    async def test_health_check_namespace_missing_is_warning(
        self,
        mock_kubectl: MagicMock,
        mock_cluster: MagicMock,
        mock_ns: MagicMock,
        mock_quota: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test health check when namespace does not exist is a warning, not a failure."""
        mock_kubectl.return_value = (True, "kubectl found")
        mock_cluster.return_value = (True, "Cluster accessible")
        mock_ns.return_value = (False, "Namespace 'mcpbr' does not exist")
        mock_quota.return_value = (True, "No quotas")

        result = await k8s_provider.health_check()

        assert result["healthy"] is True
        assert len(result["warnings"]) > 0


# ============================================================================
# Health Check Helpers Tests
# ============================================================================


class TestHealthCheckHelpers:
    """Test health check helper methods."""

    @patch("mcpbr.infrastructure.k8s.subprocess.run")
    def test_check_kubectl_installed_success(
        self,
        mock_run: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test kubectl check when installed."""
        mock_run.return_value = Mock(returncode=0, stdout="/usr/local/bin/kubectl")
        ok, msg = k8s_provider._check_kubectl_installed()
        assert ok is True

    @patch("mcpbr.infrastructure.k8s.subprocess.run")
    def test_check_kubectl_installed_missing(
        self,
        mock_run: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test kubectl check when not installed."""
        mock_run.return_value = Mock(returncode=1, stdout="")
        ok, msg = k8s_provider._check_kubectl_installed()
        assert ok is False

    @patch("mcpbr.infrastructure.k8s.subprocess.run")
    def test_check_cluster_access_success(
        self,
        mock_run: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test cluster access check when reachable."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Kubernetes control plane is running at https://127.0.0.1:6443",
        )
        ok, msg = k8s_provider._check_cluster_access()
        assert ok is True

    @patch("mcpbr.infrastructure.k8s.subprocess.run")
    def test_check_cluster_access_failure(
        self,
        mock_run: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test cluster access check when unreachable."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="The connection to the server was refused",
        )
        ok, msg = k8s_provider._check_cluster_access()
        assert ok is False


# ============================================================================
# kubectl Base Command Tests
# ============================================================================


class TestKubectlBase:
    """Test _kubectl_base method."""

    def test_kubectl_base_default(self, k8s_provider: KubernetesProvider) -> None:
        """Test default kubectl base command."""
        cmd = k8s_provider._kubectl_base()
        assert cmd[0].endswith("kubectl")
        assert len(cmd) == 1

    def test_kubectl_base_with_context(self, k8s_provider: KubernetesProvider) -> None:
        """Test kubectl base command with context."""
        k8s_provider.k8s_config.context = "my-cluster"
        cmd = k8s_provider._kubectl_base()
        assert "--context" in cmd
        assert "my-cluster" in cmd

    def test_kubectl_base_with_namespace(self, k8s_provider: KubernetesProvider) -> None:
        """Test kubectl base command with namespace."""
        k8s_provider.namespace = "test-ns"
        cmd = k8s_provider._kubectl_base()
        assert "--namespace" in cmd
        assert "test-ns" in cmd


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Test Kubernetes resource cleanup."""

    @patch.object(KubernetesProvider, "_run_kubectl")
    async def test_cleanup_deletes_job(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test cleanup deletes the Job."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"
        mock_kubectl.return_value = Mock(returncode=0)

        await k8s_provider.cleanup(force=True)

        # Verify kubectl delete job was called
        calls = mock_kubectl.call_args_list
        assert any("delete" in str(call) and "job" in str(call) for call in calls)

    @patch.object(KubernetesProvider, "_run_kubectl")
    async def test_cleanup_deletes_configmap(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test cleanup deletes the ConfigMap."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"
        k8s_provider._config_map_name = "test-cm"
        mock_kubectl.return_value = Mock(returncode=0)

        await k8s_provider.cleanup(force=True)

        calls = mock_kubectl.call_args_list
        assert any("configmap" in str(call) for call in calls)

    @patch.object(KubernetesProvider, "_run_kubectl")
    async def test_cleanup_deletes_secret(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test cleanup deletes the Secret."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"
        k8s_provider._secret_name = "test-secret"
        mock_kubectl.return_value = Mock(returncode=0)

        await k8s_provider.cleanup(force=True)

        calls = mock_kubectl.call_args_list
        assert any("secret" in str(call) for call in calls)

    async def test_cleanup_preserve_on_error(self, k8s_provider: KubernetesProvider) -> None:
        """Test cleanup preserves resources when error occurred and preserve_on_error is True."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"
        k8s_provider._error_occurred = True
        k8s_provider.k8s_config.preserve_on_error = True
        k8s_provider.k8s_config.auto_cleanup = True

        # Should not raise, but should not delete resources
        await k8s_provider.cleanup()

    @patch.object(KubernetesProvider, "_run_kubectl")
    async def test_cleanup_force_ignores_preserve(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test forced cleanup ignores preserve_on_error."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"
        k8s_provider._error_occurred = True
        k8s_provider.k8s_config.preserve_on_error = True
        mock_kubectl.return_value = Mock(returncode=0)

        await k8s_provider.cleanup(force=True)

        # Should still delete
        assert mock_kubectl.call_count > 0


# ============================================================================
# Extract JSON Results Tests
# ============================================================================


class TestExtractJsonResults:
    """Test _extract_json_results static method."""

    def test_extract_json_simple(self) -> None:
        """Test extracting JSON from simple log output."""
        log_output = 'Some log lines\n{"metadata": {}, "tasks": []}'
        result = KubernetesProvider._extract_json_results(log_output)
        assert result is not None
        assert result["metadata"] == {}

    def test_extract_json_multiline(self) -> None:
        """Test extracting multiline JSON from log output."""
        log_output = (
            "Log line 1\nLog line 2\n"
            '{\n  "metadata": {},\n  "summary": {"total": 10},\n  "tasks": []\n}'
        )
        result = KubernetesProvider._extract_json_results(log_output)
        assert result is not None
        assert result["summary"]["total"] == 10

    def test_extract_json_no_json(self) -> None:
        """Test extracting JSON when no JSON present."""
        log_output = "Just some log lines\nNo JSON here"
        result = KubernetesProvider._extract_json_results(log_output)
        assert result is None

    def test_extract_json_invalid_json(self) -> None:
        """Test extracting JSON with invalid JSON."""
        log_output = "Some logs\n{invalid json content}"
        result = KubernetesProvider._extract_json_results(log_output)
        assert result is None

    def test_extract_json_with_timestamp_prefix(self) -> None:
        """Test extracting JSON with Kubernetes timestamp prefixes."""
        log_output = (
            '2024-01-01T00:00:00Z Log line\n2024-01-01T00:00:01Z {"metadata": {}, "tasks": []}'
        )
        result = KubernetesProvider._extract_json_results(log_output)
        assert result is not None


# ============================================================================
# Async Safety Tests (issue #424)
# ============================================================================


class TestAsyncSafety:
    """Test that async methods do not call run_until_complete from a running loop."""

    @patch.object(KubernetesProvider, "_run_kubectl")
    async def test_aggregate_results_works_in_async_context(
        self,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
    ) -> None:
        """Test _aggregate_results works when called from an async context.

        Previously, _aggregate_results called
        asyncio.get_event_loop().run_until_complete() which raises
        RuntimeError when already inside a running event loop.
        """
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"

        # Mock _run_kubectl: first call for _get_pod_names, rest for pod logs
        pod_names_result = Mock(returncode=0, stdout="pod-1 pod-2")
        log_result = Mock(
            returncode=0,
            stdout='{"metadata": {}, "summary": {"total_cost": 0.1, '
            '"total_tokens_input": 100, "total_tokens_output": 50}, '
            '"tasks": [{"mcp": {"resolved": true}}]}',
        )
        mock_kubectl.side_effect = [pod_names_result, log_result, log_result]

        result = await k8s_provider._aggregate_results()
        assert result["summary"]["total_tasks"] == 2
        assert result["metadata"]["infrastructure"] == "kubernetes"

    @patch.object(KubernetesProvider, "_run_kubectl")
    @patch.object(KubernetesProvider, "_aggregate_results")
    async def test_collect_artifacts_calls_aggregate_from_async(
        self,
        mock_aggregate: MagicMock,
        mock_kubectl: MagicMock,
        k8s_provider: KubernetesProvider,
        tmp_path,
    ) -> None:
        """Test collect_artifacts can call _aggregate_results from async context."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.job_name = "mcpbr-eval-123"

        # Mock _get_pod_names via _run_kubectl
        mock_kubectl.return_value = Mock(returncode=0, stdout="pod-1")
        mock_aggregate.return_value = {
            "metadata": {},
            "summary": {},
            "tasks": [],
        }

        output_dir = tmp_path / "artifacts"
        archive_path = await k8s_provider.collect_artifacts(output_dir)
        assert archive_path.exists()


# ============================================================================
# DinD Security Tests (issue #426)
# ============================================================================


class TestDinDSecurityDefaults:
    """Test that DinD sidecar does NOT use --privileged by default."""

    def test_dind_not_privileged_by_default(self, k8s_provider: KubernetesProvider) -> None:
        """Test DinD sidecar does not run with privileged:true by default.

        Previously, the DinD sidecar unconditionally set
        securityContext.privileged = True, which grants the container full
        host access. The default should be unprivileged (using sysbox or
        rootless mode).
        """
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True
        # Do NOT explicitly set dind_privileged — test the default

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        dind = next(c for c in containers if c["name"] == "dind")
        security_ctx = dind.get("securityContext", {})
        assert security_ctx.get("privileged") is not True, (
            "DinD sidecar must NOT default to privileged mode"
        )

    def test_dind_privileged_when_explicitly_enabled(
        self, k8s_provider: KubernetesProvider
    ) -> None:
        """Test DinD uses privileged mode only when explicitly requested."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True
        k8s_provider.k8s_config.dind_privileged = True

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        dind = next(c for c in containers if c["name"] == "dind")
        security_ctx = dind.get("securityContext", {})
        assert security_ctx.get("privileged") is True

    def test_dind_rootless_image_by_default(self, k8s_provider: KubernetesProvider) -> None:
        """Test DinD uses rootless image variant by default."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        dind = next(c for c in containers if c["name"] == "dind")
        assert "rootless" in dind["image"], "DinD should use rootless image variant by default"

    def test_dind_privileged_uses_standard_image(self, k8s_provider: KubernetesProvider) -> None:
        """Test DinD uses standard (non-rootless) image when privileged."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True
        k8s_provider.k8s_config.dind_privileged = True

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        dind = next(c for c in containers if c["name"] == "dind")
        assert "rootless" not in dind["image"]
        assert security_ctx_privileged(dind)

    def test_existing_dind_test_still_passes_with_explicit_flag(
        self, k8s_provider: KubernetesProvider
    ) -> None:
        """Verify backward compat: DinD sidecar present when enable_dind=True."""
        k8s_provider.namespace = "mcpbr"
        k8s_provider.k8s_config.enable_dind = True

        manifest = k8s_provider._generate_job_manifest("test-cm", None)

        containers = manifest["spec"]["template"]["spec"]["containers"]
        container_names = [c["name"] for c in containers]
        assert "dind" in container_names


def security_ctx_privileged(container: dict) -> bool:
    """Helper to check if a container has privileged security context."""
    return container.get("securityContext", {}).get("privileged") is True
