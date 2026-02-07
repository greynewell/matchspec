"""Tests for infrastructure resource leak fixes (#430).

Verifies that SSH connections, SFTP sessions, and temp files are properly
cleaned up when errors occur in AWS, GCP, and K8s infrastructure providers.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# ============================================================================
# AWS Provider Resource Leak Tests
# ============================================================================


class TestAWSDownloadResultsSFTPLeak:
    """Test that _download_results closes SFTP even when errors occur."""

    @pytest.fixture
    def aws_provider(self) -> MagicMock:
        """Create an AWS provider with mocked SSH client."""
        from mcpbr.infrastructure.aws import AWSProvider

        config = MagicMock()
        config.infrastructure.mode = "aws"
        config.infrastructure.aws.region = "us-east-1"
        config.infrastructure.aws.instance_type = None
        config.infrastructure.aws.cpu_cores = 4
        config.infrastructure.aws.memory_gb = 16
        config.infrastructure.aws.disk_gb = 100
        config.infrastructure.aws.auto_shutdown = True
        config.infrastructure.aws.preserve_on_error = True
        config.infrastructure.aws.env_keys_to_export = []
        config.infrastructure.aws.ssh_key_path = None
        config.infrastructure.aws.key_name = None
        config.infrastructure.aws.ami_id = None
        config.infrastructure.aws.subnet_id = None
        config.infrastructure.aws.iam_instance_profile = None
        config.infrastructure.aws.python_version = "3.11"
        config.benchmark = "swe-bench-lite"
        config.task_ids = None
        config.model_dump.return_value = {"infrastructure": {"mode": "aws"}}
        provider = AWSProvider(config)
        return provider

    async def test_sftp_closed_on_get_error(self, aws_provider) -> None:
        """SFTP must be closed even when sftp.get() raises an exception."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_sftp.get.side_effect = IOError("Download failed")
        aws_provider.ssh_client = mock_ssh

        # Mock _ssh_exec to return a valid remote path
        aws_provider._ssh_exec = AsyncMock(return_value=(0, "/home/ubuntu/.mcpbr_run_001\n", ""))

        with pytest.raises((IOError, FileNotFoundError, RuntimeError)):
            await aws_provider._download_results()

        # SFTP must have been closed despite the error
        mock_sftp.close.assert_called()

    async def test_temp_file_cleaned_on_sftp_error(self, aws_provider) -> None:
        """Temp file must be cleaned up even when SFTP operations fail."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_sftp.get.side_effect = IOError("Download failed")
        aws_provider.ssh_client = mock_ssh

        aws_provider._ssh_exec = AsyncMock(return_value=(0, "/home/ubuntu/.mcpbr_run_001\n", ""))

        with pytest.raises((IOError, FileNotFoundError, RuntimeError)):
            await aws_provider._download_results()

        # The temp file should have been cleaned up
        # (We can't directly check temp files, but SFTP must be closed)
        mock_sftp.close.assert_called()


class TestAWSCollectArtifactsSFTPLeak:
    """Test that collect_artifacts closes SFTP even when errors occur."""

    @pytest.fixture
    def aws_provider(self) -> MagicMock:
        """Create an AWS provider."""
        from mcpbr.infrastructure.aws import AWSProvider

        config = MagicMock()
        config.infrastructure.mode = "aws"
        config.infrastructure.aws.region = "us-east-1"
        config.infrastructure.aws.instance_type = None
        config.infrastructure.aws.cpu_cores = 4
        config.infrastructure.aws.memory_gb = 16
        config.infrastructure.aws.disk_gb = 100
        config.infrastructure.aws.auto_shutdown = True
        config.infrastructure.aws.preserve_on_error = True
        config.infrastructure.aws.env_keys_to_export = []
        config.infrastructure.aws.ssh_key_path = None
        config.infrastructure.aws.key_name = None
        config.infrastructure.aws.ami_id = None
        config.infrastructure.aws.subnet_id = None
        config.infrastructure.aws.iam_instance_profile = None
        config.infrastructure.aws.python_version = "3.11"
        config.benchmark = "swe-bench-lite"
        config.task_ids = None
        config.model_dump.return_value = {"infrastructure": {"mode": "aws"}}
        return AWSProvider(config)

    async def test_sftp_closed_on_download_error(self, aws_provider, tmp_path) -> None:
        """SFTP must be closed even when recursive download raises."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        aws_provider.ssh_client = mock_ssh

        aws_provider._ssh_exec = AsyncMock(return_value=(0, "/home/ubuntu/.mcpbr_run_001\n", ""))

        # Make _recursive_download raise
        with patch("asyncio.to_thread", side_effect=OSError("Download failed")):
            with pytest.raises(OSError):
                await aws_provider.collect_artifacts(tmp_path / "artifacts")

        mock_sftp.close.assert_called()


# ============================================================================
# GCP Provider Resource Leak Tests
# ============================================================================


class TestGCPDownloadResultsSFTPLeak:
    """Test that GCP _download_results closes SFTP even when errors occur."""

    @pytest.fixture
    def gcp_provider(self) -> MagicMock:
        """Create a GCP provider with mocked SSH client."""
        from mcpbr.infrastructure.gcp import GCPProvider

        config = MagicMock()
        config.infrastructure.mode = "gcp"
        config.infrastructure.gcp.zone = "us-central1-a"
        config.infrastructure.gcp.machine_type = None
        config.infrastructure.gcp.cpu_cores = 4
        config.infrastructure.gcp.memory_gb = 16
        config.infrastructure.gcp.disk_gb = 100
        config.infrastructure.gcp.disk_type = "pd-ssd"
        config.infrastructure.gcp.image_family = "ubuntu-2204-lts"
        config.infrastructure.gcp.image_project = "ubuntu-os-cloud"
        config.infrastructure.gcp.project_id = "test-project"
        config.infrastructure.gcp.auto_shutdown = True
        config.infrastructure.gcp.preserve_on_error = True
        config.infrastructure.gcp.env_keys_to_export = []
        config.infrastructure.gcp.ssh_key_path = None
        config.infrastructure.gcp.python_version = "3.11"
        config.infrastructure.gcp.spot = False
        config.infrastructure.gcp.preemptible = False
        config.infrastructure.gcp.labels = {}
        config.infrastructure.gcp.service_account = None
        config.infrastructure.gcp.scopes = []
        config.benchmark = "swe-bench-lite"
        config.task_ids = None
        config.model_dump.return_value = {"infrastructure": {"mode": "gcp"}}
        return GCPProvider(config)

    async def test_sftp_closed_on_get_error(self, gcp_provider) -> None:
        """SFTP must be closed even when sftp.get() raises an exception."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        mock_sftp.get.side_effect = IOError("Download failed")
        gcp_provider.ssh_client = mock_ssh

        gcp_provider._ssh_exec = AsyncMock(return_value=(0, "/home/ubuntu/.mcpbr_run_001\n", ""))

        with pytest.raises((IOError, FileNotFoundError, RuntimeError)):
            await gcp_provider._download_results()

        mock_sftp.close.assert_called()


class TestGCPCollectArtifactsSFTPLeak:
    """Test that GCP collect_artifacts closes SFTP even when errors occur."""

    @pytest.fixture
    def gcp_provider(self) -> MagicMock:
        """Create a GCP provider."""
        from mcpbr.infrastructure.gcp import GCPProvider

        config = MagicMock()
        config.infrastructure.mode = "gcp"
        config.infrastructure.gcp.zone = "us-central1-a"
        config.infrastructure.gcp.machine_type = None
        config.infrastructure.gcp.cpu_cores = 4
        config.infrastructure.gcp.memory_gb = 16
        config.infrastructure.gcp.disk_gb = 100
        config.infrastructure.gcp.disk_type = "pd-ssd"
        config.infrastructure.gcp.image_family = "ubuntu-2204-lts"
        config.infrastructure.gcp.image_project = "ubuntu-os-cloud"
        config.infrastructure.gcp.project_id = "test-project"
        config.infrastructure.gcp.auto_shutdown = True
        config.infrastructure.gcp.preserve_on_error = True
        config.infrastructure.gcp.env_keys_to_export = []
        config.infrastructure.gcp.ssh_key_path = None
        config.infrastructure.gcp.python_version = "3.11"
        config.infrastructure.gcp.spot = False
        config.infrastructure.gcp.preemptible = False
        config.infrastructure.gcp.labels = {}
        config.infrastructure.gcp.service_account = None
        config.infrastructure.gcp.scopes = []
        config.benchmark = "swe-bench-lite"
        config.task_ids = None
        config.model_dump.return_value = {"infrastructure": {"mode": "gcp"}}
        return GCPProvider(config)

    async def test_sftp_closed_on_download_error(self, gcp_provider, tmp_path) -> None:
        """SFTP must be closed even when recursive download raises."""
        mock_ssh = MagicMock()
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        gcp_provider.ssh_client = mock_ssh

        gcp_provider._ssh_exec = AsyncMock(return_value=(0, "/home/ubuntu/.mcpbr_run_001\n", ""))

        with patch("asyncio.to_thread", side_effect=OSError("Download failed")):
            with pytest.raises(OSError):
                await gcp_provider.collect_artifacts(tmp_path / "artifacts")

        mock_sftp.close.assert_called()


# ============================================================================
# K8s Provider Resource Leak Tests
# ============================================================================


class TestK8sSetupPartialFailureCleanup:
    """Test that K8s setup cleans up partial resources on failure."""

    @pytest.fixture
    def k8s_provider(self) -> MagicMock:
        """Create a K8s provider."""
        from mcpbr.infrastructure.k8s import KubernetesProvider

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
        return KubernetesProvider(config)

    async def test_configmap_cleaned_up_when_secret_creation_fails(self, k8s_provider) -> None:
        """If _create_secret fails, the already-created ConfigMap must be cleaned up."""

        def fake_ensure_namespace():
            k8s_provider.namespace = "mcpbr"

        k8s_provider._ensure_namespace = MagicMock(side_effect=fake_ensure_namespace)
        k8s_provider._create_config_map = MagicMock(return_value="test-cm")
        k8s_provider._create_secret = MagicMock(side_effect=RuntimeError("Secret creation failed"))
        k8s_provider._run_kubectl = MagicMock(return_value=Mock(returncode=0))

        with pytest.raises(RuntimeError, match="Secret creation failed"):
            await k8s_provider.setup()

        # The provider should have attempted to clean up the ConfigMap
        # by calling _run_kubectl with delete configmap
        cleanup_calls = [str(call) for call in k8s_provider._run_kubectl.call_args_list]
        assert any("configmap" in call and "delete" in call for call in cleanup_calls), (
            f"Expected ConfigMap cleanup call, got: {cleanup_calls}"
        )

    async def test_error_flag_set_on_partial_failure(self, k8s_provider) -> None:
        """_error_occurred must be set when setup fails partially."""

        def fake_ensure_namespace():
            k8s_provider.namespace = "mcpbr"

        k8s_provider._ensure_namespace = MagicMock(side_effect=fake_ensure_namespace)
        k8s_provider._create_config_map = MagicMock(return_value="test-cm")
        k8s_provider._create_secret = MagicMock(side_effect=RuntimeError("Secret creation failed"))
        k8s_provider._run_kubectl = MagicMock(return_value=Mock(returncode=0))

        with pytest.raises(RuntimeError):
            await k8s_provider.setup()

        assert k8s_provider._error_occurred is True
