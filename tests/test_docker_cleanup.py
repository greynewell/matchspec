"""Tests for Docker cleanup functionality."""

import datetime
from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from mcpbr.docker_env import (
    MCPBR_LABEL,
    MCPBR_SESSION_LABEL,
    MCPBR_TIMESTAMP_LABEL,
    CleanupReport,
    DockerEnvironmentManager,
    TaskEnvironment,
    cleanup_all_resources,
    cleanup_orphaned_containers,
    cleanup_orphaned_networks,
    cleanup_orphaned_volumes,
)


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    with patch("mcpbr.docker_env.docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_container():
    """Create a mock Docker container."""
    container = MagicMock()
    container.name = "mcpbr-test-container"
    container.short_id = "abc123"
    container.labels = {
        MCPBR_LABEL: "true",
        MCPBR_SESSION_LABEL: "test-session",
        MCPBR_TIMESTAMP_LABEL: datetime.datetime.now(datetime.UTC).isoformat(),
    }
    return container


@pytest.fixture
def mock_volume():
    """Create a mock Docker volume."""
    volume = MagicMock()
    volume.name = "mcpbr-test-volume"
    return volume


@pytest.fixture
def mock_network():
    """Create a mock Docker network."""
    network = MagicMock()
    network.name = "mcpbr-test-network"
    return network


class TestCleanupReport:
    """Test CleanupReport dataclass."""

    def test_empty_report(self):
        """Test empty cleanup report."""
        report = CleanupReport()
        assert report.total_removed == 0
        assert len(report.containers_removed) == 0
        assert len(report.volumes_removed) == 0
        assert len(report.networks_removed) == 0
        assert len(report.errors) == 0

    def test_report_with_containers(self):
        """Test report with removed containers."""
        report = CleanupReport(containers_removed=["c1", "c2", "c3"])
        assert report.total_removed == 3
        assert "Containers: 3 removed" in str(report)

    def test_report_with_multiple_resources(self):
        """Test report with multiple resource types."""
        report = CleanupReport(
            containers_removed=["c1", "c2"],
            volumes_removed=["v1"],
            networks_removed=["n1"],
        )
        assert report.total_removed == 4
        output = str(report)
        assert "Containers: 2 removed" in output
        assert "Volumes: 1 removed" in output
        assert "Networks: 1 removed" in output

    def test_report_with_many_containers(self):
        """Test report truncation for many containers."""
        containers = [f"container-{i}" for i in range(10)]
        report = CleanupReport(containers_removed=containers)
        output = str(report)
        assert "... and 5 more" in output

    def test_report_with_errors(self):
        """Test report with errors."""
        report = CleanupReport(
            containers_removed=["c1"],
            errors=["Error 1", "Error 2"],
        )
        output = str(report)
        assert "Errors: 2" in output

    def test_report_with_temp_dirs(self):
        """Test report with temp directories cleaned."""
        report = CleanupReport(temp_dirs_cleaned=5)
        output = str(report)
        assert "Temp directories: 5 cleaned" in output


class TestCleanupOrphanedContainers:
    """Test cleanup_orphaned_containers function."""

    def test_cleanup_no_containers(self, mock_docker_client):
        """Test cleanup when no containers exist."""
        mock_docker_client.containers.list.return_value = []

        removed = cleanup_orphaned_containers(dry_run=False)

        assert removed == []
        mock_docker_client.containers.list.assert_called_once()

    def test_cleanup_dry_run(self, mock_docker_client, mock_container):
        """Test dry run doesn't remove containers."""
        mock_docker_client.containers.list.return_value = [mock_container]

        # Use force=True to bypass retention policy in dry run
        removed = cleanup_orphaned_containers(dry_run=True, force=True)

        assert len(removed) == 1
        assert removed[0] == "mcpbr-test-container"
        mock_container.stop.assert_not_called()
        mock_container.remove.assert_not_called()

    def test_cleanup_removes_containers(self, mock_docker_client, mock_container):
        """Test actual container removal."""
        mock_docker_client.containers.list.return_value = [mock_container]

        removed = cleanup_orphaned_containers(dry_run=False, force=True)

        assert len(removed) == 1
        mock_container.stop.assert_called_once_with(timeout=5)
        mock_container.remove.assert_called_once_with(force=True)

    def test_cleanup_respects_retention_policy(self, mock_docker_client):
        """Test retention policy prevents removal of recent containers."""
        # Create a recent container
        recent_container = MagicMock()
        recent_container.name = "recent-container"
        recent_container.labels = {
            MCPBR_LABEL: "true",
            MCPBR_TIMESTAMP_LABEL: datetime.datetime.now(datetime.UTC).isoformat(),
        }

        # Create an old container (48 hours ago)
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=48)
        old_container = MagicMock()
        old_container.name = "old-container"
        old_container.labels = {
            MCPBR_LABEL: "true",
            MCPBR_TIMESTAMP_LABEL: old_time.isoformat(),
        }

        mock_docker_client.containers.list.return_value = [recent_container, old_container]

        removed = cleanup_orphaned_containers(dry_run=False, retention_hours=24)

        # Only old container should be removed
        assert len(removed) == 1
        assert removed[0] == "old-container"
        recent_container.stop.assert_not_called()
        old_container.stop.assert_called_once()

    def test_cleanup_force_ignores_retention(self, mock_docker_client, mock_container):
        """Test force flag ignores retention policy."""
        mock_docker_client.containers.list.return_value = [mock_container]

        removed = cleanup_orphaned_containers(dry_run=False, force=True, retention_hours=999)

        assert len(removed) == 1
        mock_container.stop.assert_called_once()

    def test_cleanup_handles_removal_errors(self, mock_docker_client, mock_container):
        """Test cleanup handles errors gracefully."""
        mock_container.stop.side_effect = Exception("Stop failed")
        mock_docker_client.containers.list.return_value = [mock_container]

        # Should not raise, just log warning
        removed = cleanup_orphaned_containers(dry_run=False, force=True)

        assert len(removed) == 1  # Still counts as attempted


class TestCleanupOrphanedVolumes:
    """Test cleanup_orphaned_volumes function."""

    def test_cleanup_no_volumes(self, mock_docker_client):
        """Test cleanup when no volumes exist."""
        mock_docker_client.volumes.list.return_value = []

        removed = cleanup_orphaned_volumes(dry_run=False)

        assert removed == []

    def test_cleanup_dry_run(self, mock_docker_client, mock_volume):
        """Test dry run doesn't remove volumes."""
        mock_docker_client.volumes.list.return_value = [mock_volume]

        removed = cleanup_orphaned_volumes(dry_run=True)

        assert len(removed) == 1
        assert removed[0] == "mcpbr-test-volume"
        mock_volume.remove.assert_not_called()

    def test_cleanup_removes_volumes(self, mock_docker_client, mock_volume):
        """Test actual volume removal."""
        mock_docker_client.volumes.list.return_value = [mock_volume]

        removed = cleanup_orphaned_volumes(dry_run=False)

        assert len(removed) == 1
        mock_volume.remove.assert_called_once_with(force=False)

    def test_cleanup_force_removal(self, mock_docker_client, mock_volume):
        """Test force removal of volumes."""
        mock_docker_client.volumes.list.return_value = [mock_volume]

        removed = cleanup_orphaned_volumes(dry_run=False, force=True)

        assert len(removed) == 1
        mock_volume.remove.assert_called_once_with(force=True)


class TestCleanupOrphanedNetworks:
    """Test cleanup_orphaned_networks function."""

    def test_cleanup_no_networks(self, mock_docker_client):
        """Test cleanup when no networks exist."""
        mock_docker_client.networks.list.return_value = []

        removed = cleanup_orphaned_networks(dry_run=False)

        assert removed == []

    def test_cleanup_skips_default_networks(self, mock_docker_client):
        """Test cleanup skips default Docker networks."""
        bridge_network = MagicMock()
        bridge_network.name = "bridge"

        host_network = MagicMock()
        host_network.name = "host"

        mock_docker_client.networks.list.return_value = [bridge_network, host_network]

        removed = cleanup_orphaned_networks(dry_run=False)

        assert removed == []
        bridge_network.remove.assert_not_called()
        host_network.remove.assert_not_called()

    def test_cleanup_removes_custom_networks(self, mock_docker_client, mock_network):
        """Test removal of custom networks."""
        mock_docker_client.networks.list.return_value = [mock_network]

        removed = cleanup_orphaned_networks(dry_run=False)

        assert len(removed) == 1
        assert removed[0] == "mcpbr-test-network"
        mock_network.remove.assert_called_once()


class TestCleanupAllResources:
    """Test cleanup_all_resources function."""

    def test_cleanup_all_empty(self, mock_docker_client):
        """Test cleanup all with no resources."""
        mock_docker_client.containers.list.return_value = []
        mock_docker_client.volumes.list.return_value = []
        mock_docker_client.networks.list.return_value = []

        report = cleanup_all_resources(dry_run=False)

        assert report.total_removed == 0
        assert len(report.errors) == 0

    def test_cleanup_all_multiple_resources(
        self, mock_docker_client, mock_container, mock_volume, mock_network
    ):
        """Test cleanup all with multiple resource types."""
        mock_docker_client.containers.list.return_value = [mock_container]
        mock_docker_client.volumes.list.return_value = [mock_volume]
        mock_docker_client.networks.list.return_value = [mock_network]

        report = cleanup_all_resources(dry_run=False, force=True)

        assert report.total_removed == 3
        assert len(report.containers_removed) == 1
        assert len(report.volumes_removed) == 1
        assert len(report.networks_removed) == 1

    def test_cleanup_all_dry_run(
        self, mock_docker_client, mock_container, mock_volume, mock_network
    ):
        """Test cleanup all in dry run mode."""
        mock_docker_client.containers.list.return_value = [mock_container]
        mock_docker_client.volumes.list.return_value = [mock_volume]
        mock_docker_client.networks.list.return_value = [mock_network]

        # Use force=True to bypass retention policy
        report = cleanup_all_resources(dry_run=True, force=True)

        assert report.total_removed == 3
        # Verify nothing was actually removed
        mock_container.stop.assert_not_called()
        mock_volume.remove.assert_not_called()
        mock_network.remove.assert_not_called()

    def test_cleanup_all_handles_errors(self, mock_docker_client, mock_container):
        """Test cleanup all handles errors gracefully."""
        mock_docker_client.containers.list.side_effect = Exception("List failed")
        mock_docker_client.volumes.list.return_value = []
        mock_docker_client.networks.list.return_value = []

        report = cleanup_all_resources(dry_run=False)

        assert len(report.errors) > 0
        assert any("Container cleanup failed" in error for error in report.errors)


class TestDockerEnvironmentManager:
    """Test DockerEnvironmentManager cleanup methods."""

    def test_manager_cleanup_sync(self, mock_docker_client):
        """Test synchronous cleanup of manager resources."""
        manager = DockerEnvironmentManager()

        # Add mock resources
        mock_container = MagicMock()
        mock_container.name = "test-container"
        manager._containers = [mock_container]

        mock_volume = MagicMock()
        mock_volume.name = "test-volume"
        manager._volumes = [mock_volume]

        # Perform cleanup
        report = manager.cleanup_all_sync(report=True)

        assert len(report.containers_removed) == 1
        assert len(report.volumes_removed) == 1
        mock_container.stop.assert_called_once()
        mock_container.remove.assert_called_once()
        mock_volume.remove.assert_called_once()

    def test_manager_cleanup_temp_dirs(self, mock_docker_client):
        """Test cleanup of temporary directories."""
        manager = DockerEnvironmentManager()

        # Add mock temp dir
        mock_temp = MagicMock()
        manager._temp_dirs = [mock_temp]

        report = manager.cleanup_all_sync(report=True)

        assert report.temp_dirs_cleaned == 1
        mock_temp.cleanup.assert_called_once()

    def test_manager_cleanup_handles_errors(self, mock_docker_client):
        """Test manager cleanup handles errors gracefully."""
        manager = DockerEnvironmentManager()

        # Add mock container that fails to both stop AND remove
        mock_container = MagicMock()
        mock_container.name = "failing-container"
        mock_container.stop.side_effect = Exception("Stop failed")
        mock_container.remove.side_effect = Exception("Remove failed")
        manager._containers = [mock_container]

        report = manager.cleanup_all_sync(report=True)

        # Should still attempt cleanup and record error
        assert len(report.errors) > 0
        assert any("Failed to remove container" in error for error in report.errors)

    @pytest.mark.asyncio
    async def test_manager_cleanup_async(self, mock_docker_client):
        """Test asynchronous cleanup wrapper."""
        manager = DockerEnvironmentManager()

        mock_container = MagicMock()
        mock_container.name = "test-container"
        manager._containers = [mock_container]

        report = await manager.cleanup_all(report=True)

        assert len(report.containers_removed) == 1
        mock_container.stop.assert_called_once()


class TestTaskEnvironmentCleanup:
    """Test TaskEnvironment aggressive cleanup functionality."""

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_removes_temp_dir(self, mock_docker_client):
        """Test that TaskEnvironment.cleanup() removes temp directory."""
        from mcpbr.docker_env import TaskEnvironment

        manager = DockerEnvironmentManager()
        mock_container = MagicMock()
        mock_container.name = "test-container"

        # Create a mock temp directory
        mock_temp_dir = MagicMock()
        manager._temp_dirs = [mock_temp_dir]

        # Create task environment with temp dir reference
        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir="/tmp/test",
            instance_id="test-instance",
            _temp_dir=mock_temp_dir,
            _manager=manager,
        )

        # Cleanup environment
        await env.cleanup()

        # Verify temp directory cleanup was called
        mock_temp_dir.cleanup.assert_called_once()

        # Verify temp directory was removed from manager's list
        assert mock_temp_dir not in manager._temp_dirs

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_handles_missing_temp_dir(self, mock_docker_client):
        """Test that cleanup handles None temp directory gracefully."""
        from mcpbr.docker_env import TaskEnvironment

        mock_container = MagicMock()

        # Create task environment without temp dir reference
        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir="/tmp/test",
            instance_id="test-instance",
            _temp_dir=None,
            _manager=None,
        )

        # Should not raise
        await env.cleanup()

        mock_container.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_handles_errors(self, mock_docker_client):
        """Test that cleanup handles temp dir cleanup errors gracefully."""
        from mcpbr.docker_env import TaskEnvironment

        manager = DockerEnvironmentManager()
        mock_container = MagicMock()

        # Create a mock temp directory that fails to cleanup
        mock_temp_dir = MagicMock()
        mock_temp_dir.cleanup.side_effect = Exception("Cleanup failed")
        manager._temp_dirs = [mock_temp_dir]

        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir="/tmp/test",
            instance_id="test-instance",
            _temp_dir=mock_temp_dir,
            _manager=manager,
        )

        # Should not raise even if temp dir cleanup fails
        await env.cleanup()

        # Container should still be cleaned up
        mock_container.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_removes_from_manager_list(self, mock_docker_client):
        """Test that cleanup removes temp dir from manager's tracking list."""
        from mcpbr.docker_env import TaskEnvironment

        manager = DockerEnvironmentManager()
        mock_container = MagicMock()

        # Create multiple temp directories
        mock_temp_dir1 = MagicMock()
        mock_temp_dir2 = MagicMock()
        manager._temp_dirs = [mock_temp_dir1, mock_temp_dir2]

        # Create environment for first temp dir
        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir="/tmp/test",
            instance_id="test-instance",
            _temp_dir=mock_temp_dir1,
            _manager=manager,
        )

        # Cleanup environment
        await env.cleanup()

        # First temp dir should be removed, second should remain
        assert mock_temp_dir1 not in manager._temp_dirs
        assert mock_temp_dir2 in manager._temp_dirs
        assert len(manager._temp_dirs) == 1


class TestSignalHandlers:
    """Test signal handler cleanup."""

    def test_cleanup_on_exit(self, mock_docker_client):
        """Test cleanup on exit is registered."""
        import mcpbr.docker_env

        # Verify cleanup is registered with atexit
        # This is tested implicitly through integration tests
        assert hasattr(mcpbr.docker_env, "_cleanup_on_exit")

    def test_signal_handler_registration(self, mock_docker_client):
        """Test signal handlers can be registered."""
        from mcpbr.docker_env import register_signal_handlers

        # Should not raise
        register_signal_handlers()

        # Calling again should be idempotent
        register_signal_handlers()


@pytest.mark.usefixtures("mock_docker_client")
class TestTaskEnvironmentCleanupRetry:
    """Test TaskEnvironment cleanup retry, logging, and container tracking (#439)."""

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_logs_warning_on_failure(self, tmp_path):
        """Test that cleanup logs a warning when container stop fails but still succeeds."""
        manager = DockerEnvironmentManager()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.stop.side_effect = Exception("stop timed out")
        mock_container.remove.return_value = None
        manager._containers = [mock_container]

        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir=str(tmp_path),
            instance_id="test-instance",
            _temp_dir=None,
            _manager=manager,
        )

        # Should not raise despite stop failure
        await env.cleanup()

        # Stop failed but remove succeeded, so container is removed from list
        assert mock_container not in manager._containers
        # Remove was still called despite stop failure
        mock_container.remove.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_retries_remove(self, tmp_path):
        """Test that cleanup retries container.remove up to 3 times."""
        manager = DockerEnvironmentManager()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.stop.return_value = None
        # Fail twice, succeed on third attempt
        mock_container.remove.side_effect = [
            Exception("busy"),
            Exception("busy"),
            None,
        ]
        manager._containers = [mock_container]

        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir=str(tmp_path),
            instance_id="test-instance",
            _temp_dir=None,
            _manager=manager,
        )

        await env.cleanup()

        assert mock_container.remove.call_count == 3
        # On success, container should be removed from manager's list
        assert mock_container not in manager._containers

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_removes_from_containers_list(self, tmp_path):
        """Test that successful cleanup removes container from manager._containers."""
        manager = DockerEnvironmentManager()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.stop.return_value = None
        mock_container.remove.return_value = None
        manager._containers = [mock_container]

        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir=str(tmp_path),
            instance_id="test-instance",
            _temp_dir=None,
            _manager=manager,
        )

        await env.cleanup()

        assert mock_container not in manager._containers

    @pytest.mark.asyncio
    async def test_task_environment_cleanup_keeps_in_list_on_failure(self, tmp_path):
        """Test that failed cleanup keeps container in manager._containers for retry at exit."""
        manager = DockerEnvironmentManager()
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_container.stop.return_value = None
        # Fail all 3 attempts
        mock_container.remove.side_effect = Exception("permission denied")
        manager._containers = [mock_container]

        env = TaskEnvironment(
            container=mock_container,
            workdir="/workspace",
            host_workdir=str(tmp_path),
            instance_id="test-instance",
            _temp_dir=None,
            _manager=manager,
        )

        await env.cleanup()

        # Container stays in list for cleanup_all_sync to retry
        assert mock_container in manager._containers

    def test_cleanup_stale_session_containers_removes_old_sessions(self, mock_docker_client):
        """Test that stale containers from other sessions are removed."""
        manager = DockerEnvironmentManager()

        stale_container = MagicMock()
        stale_container.name = "mcpbr-old-session-task1"
        stale_container.labels = {
            MCPBR_LABEL: "true",
            MCPBR_SESSION_LABEL: "old-session-id",
        }
        stale_container.stop.return_value = None
        stale_container.remove.return_value = None

        mock_docker_client.containers.list.return_value = [stale_container]

        removed = manager.cleanup_stale_session_containers()

        assert removed == 1
        stale_container.stop.assert_called_once_with(timeout=5)
        stale_container.remove.assert_called_once_with(force=True)

    def test_cleanup_stale_session_containers_preserves_current_session(self, mock_docker_client):
        """Test that containers from the current session are preserved."""
        manager = DockerEnvironmentManager()

        current_container = MagicMock()
        current_container.name = "mcpbr-current-task1"
        current_container.labels = {
            MCPBR_LABEL: "true",
            MCPBR_SESSION_LABEL: manager._session_id,
        }

        mock_docker_client.containers.list.return_value = [current_container]

        removed = manager.cleanup_stale_session_containers()

        assert removed == 0
        current_container.stop.assert_not_called()
        current_container.remove.assert_not_called()

    def test_cleanup_all_sync_handles_not_found(self):
        """Test that cleanup_all_sync treats NotFound as success."""
        manager = DockerEnvironmentManager()

        mock_container = MagicMock()
        mock_container.name = "already-gone"
        mock_container.stop.side_effect = docker.errors.NotFound("gone")
        mock_container.remove.side_effect = docker.errors.NotFound("gone")
        manager._containers = [mock_container]

        report = manager.cleanup_all_sync(report=True)

        # Should count as successfully removed, no errors
        assert "already-gone" in report.containers_removed
        assert len(report.errors) == 0
