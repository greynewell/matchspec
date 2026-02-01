"""Tests for Docker retry logic with exponential backoff."""

import time
from unittest.mock import MagicMock, patch

import docker.errors
import pytest

from mcpbr.docker_env import DockerEnvironmentManager


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    with patch("mcpbr.docker_env.docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        yield mock_client


@pytest.fixture
def manager(mock_docker_client):  # noqa: ARG001
    """Create a DockerEnvironmentManager instance."""
    return DockerEnvironmentManager()


def create_api_error(message, status_code=500):
    """Create a mock Docker APIError with status_code."""
    error = docker.errors.APIError(message)
    error.response = MagicMock()
    error.response.status_code = status_code
    return error


class TestDockerRetryLogic:
    """Test Docker container creation retry logic."""

    @pytest.mark.asyncio
    async def test_container_creation_succeeds_first_try(self, manager, mock_docker_client):
        """Test container creation succeeds on first attempt."""
        mock_container = MagicMock()
        mock_container.name = "test-container"
        mock_docker_client.containers.run.return_value = mock_container

        # Mock the necessary methods
        with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
            with patch.object(manager, "_install_claude_cli", return_value=None):
                env = await manager.create_environment(
                    task={
                        "instance_id": "test-instance",
                        "repo": "test/repo",
                        "base_commit": "abc123",
                    }
                )

        assert env.container == mock_container
        # Should only call run once
        assert mock_docker_client.containers.run.call_count == 1

    @pytest.mark.asyncio
    async def test_container_creation_retries_on_500_error(self, manager, mock_docker_client):
        """Test container creation retries on 500 error."""
        mock_container = MagicMock()
        mock_container.name = "test-container"

        # Fail twice with 500 error, then succeed
        mock_docker_client.containers.run.side_effect = [
            create_api_error("500 Server Error", status_code=500),
            create_api_error("500 Server Error", status_code=500),
            mock_container,
        ]

        start_time = time.time()

        with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
            with patch.object(manager, "_install_claude_cli", return_value=None):
                env = await manager.create_environment(
                    task={
                        "instance_id": "test-instance",
                        "repo": "test/repo",
                        "base_commit": "abc123",
                    }
                )

        elapsed = time.time() - start_time

        assert env.container == mock_container
        # Should call run 3 times (2 failures + 1 success)
        assert mock_docker_client.containers.run.call_count == 3
        # Should have waited for retries (1s + 2s = 3s minimum)
        assert elapsed >= 3.0

    @pytest.mark.asyncio
    async def test_container_creation_fails_after_max_retries(self, manager, mock_docker_client):
        """Test container creation fails after max retries."""
        # Always fail with 500 error
        mock_docker_client.containers.run.side_effect = create_api_error(
            "500 Server Error", status_code=500
        )

        with pytest.raises(Exception) as exc_info:
            with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
                with patch.object(manager, "_install_claude_cli", return_value=None):
                    await manager.create_environment(
                        task={
                            "instance_id": "test-instance",
                            "repo": "test/repo",
                            "base_commit": "abc123",
                        }
                    )

        # Should have tried max_retries + 1 times (initial + 3 retries = 4 total)
        assert mock_docker_client.containers.run.call_count == 4
        assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_container_creation_no_retry_on_404_error(self, manager, mock_docker_client):
        """Test container creation does not retry on non-500 errors."""
        # Fail with 404 error (image not found)
        mock_docker_client.containers.run.side_effect = create_api_error(
            "404 Not Found", status_code=404
        )

        with pytest.raises(Exception) as exc_info:
            with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
                with patch.object(manager, "_install_claude_cli", return_value=None):
                    await manager.create_environment(
                        task={
                            "instance_id": "test-instance",
                            "repo": "test/repo",
                            "base_commit": "abc123",
                        }
                    )

        # Should only try once for non-500 errors
        assert mock_docker_client.containers.run.call_count == 1
        assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_container_creation_no_retry_on_other_exceptions(
        self, manager, mock_docker_client
    ):
        """Test container creation does not retry on non-APIError exceptions."""
        # Fail with a different exception type
        mock_docker_client.containers.run.side_effect = ValueError("Invalid argument")

        with pytest.raises(ValueError) as exc_info:
            with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
                with patch.object(manager, "_install_claude_cli", return_value=None):
                    await manager.create_environment(
                        task={
                            "instance_id": "test-instance",
                            "repo": "test/repo",
                            "base_commit": "abc123",
                        }
                    )

        # Should only try once for non-APIError exceptions
        assert mock_docker_client.containers.run.call_count == 1
        assert "Invalid argument" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, manager, mock_docker_client):
        """Test that retry backoff follows exponential pattern."""
        mock_container = MagicMock()

        # Fail 3 times, then succeed
        mock_docker_client.containers.run.side_effect = [
            create_api_error("500 Server Error", status_code=500),
            create_api_error("500 Server Error", status_code=500),
            create_api_error("500 Server Error", status_code=500),
            mock_container,
        ]

        start_time = time.time()

        with patch.object(manager, "_copy_repo_to_workspace", return_value=None):
            with patch.object(manager, "_install_claude_cli", return_value=None):
                await manager.create_environment(
                    task={
                        "instance_id": "test-instance",
                        "repo": "test/repo",
                        "base_commit": "abc123",
                    }
                )

        elapsed = time.time() - start_time

        # Should have waited: 1s + 2s + 4s = 7s minimum
        assert elapsed >= 7.0
        # But not too much longer (allow 1s buffer for execution time)
        assert elapsed < 9.0

    @pytest.mark.asyncio
    async def test_retry_with_non_prebuilt_image(self, manager, mock_docker_client):
        """Test retry logic works with non-prebuilt images."""
        # Disable prebuilt image usage
        manager.use_prebuilt = False

        mock_container = MagicMock()

        # Fail once with 500 error, then succeed
        mock_docker_client.containers.run.side_effect = [
            create_api_error("500 Server Error", status_code=500),
            mock_container,
        ]

        # Mock the fallback image to already exist
        mock_docker_client.images.get.return_value = MagicMock()

        with patch.object(manager, "_setup_repo", return_value=None):
            env = await manager.create_environment(
                task={
                    "instance_id": "test-instance",
                    "repo": "test/repo",
                    "base_commit": "abc123",
                }
            )

        assert env.container == mock_container
        # Should have retried once
        assert mock_docker_client.containers.run.call_count == 2
