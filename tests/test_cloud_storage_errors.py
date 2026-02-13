"""Tests for cloud storage error handling, retry logic, and data integrity.

Covers error scenarios identified in GitHub issue #429:
- Upload/download failures should raise, not silently fail
- Partial/corrupt downloads should not return stale data
- Authentication errors should produce clear error messages
- Transient failures should be retried
- Timeout errors should be wrapped in CloudStorageError
- CLI-not-found errors should be caught for all providers
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.storage.cloud import (
    AzureBlobStorage,
    CloudStorageError,
    GCSStorage,
    S3Storage,
)


class TestS3ErrorHandling:
    """S3 error handling tests."""

    def test_upload_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """Upload timeout should raise CloudStorageError, not raw TimeoutExpired."""
        local_file = tmp_path / "data.json"
        local_file.write_text('{"key": "value"}')
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aws", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.upload(local_file, "results/data.json")

    def test_download_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """Download timeout should raise CloudStorageError, not raw TimeoutExpired."""
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aws", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.download("key", tmp_path / "out.json")

    def test_download_removes_partial_file_on_failure(self, tmp_path: Path) -> None:
        """Failed download should clean up any partial/corrupt file left behind."""
        storage = S3Storage(bucket="my-bucket")
        dest = tmp_path / "out.json"
        # Pre-existing file simulates a partial download or stale artifact
        dest.write_text("stale data")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="NoSuchKey")
            with pytest.raises(CloudStorageError, match="S3 download failed"):
                storage.download("missing-key", dest)

        # The stale/partial file should be removed
        assert not dest.exists(), "Partial/stale file should be removed after download failure"

    def test_download_cli_not_found(self, tmp_path: Path) -> None:
        """S3 download should raise clear error when AWS CLI is not installed."""
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(CloudStorageError, match="AWS CLI not found"):
                storage.download("key", tmp_path / "out.json")

    def test_upload_authentication_error_clear_message(self, tmp_path: Path) -> None:
        """Authentication errors should produce clear, actionable messages."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                255,
                "aws",
                stderr="An error occurred (InvalidAccessKeyId) when calling the PutObject "
                "operation: The AWS Access Key Id you provided does not exist in our records.",
            )
            with pytest.raises(CloudStorageError, match="S3 upload failed"):
                storage.upload(local_file, "key")

    def test_list_objects_authentication_error_raises(self) -> None:
        """list_objects should raise on authentication errors, not return empty list."""
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                255,
                "aws",
                stderr="An error occurred (InvalidAccessKeyId) when calling the "
                "ListObjectsV2 operation: The AWS Access Key Id you provided does "
                "not exist in our records.",
            )
            with pytest.raises(CloudStorageError, match=r"authentication|credential|access"):
                storage.list_objects()

    def test_list_objects_timeout_raises(self) -> None:
        """list_objects should raise on timeout, not return empty list."""
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aws", timeout=60)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.list_objects()

    def test_presigned_url_timeout_raises(self) -> None:
        """Presigned URL generation timeout should raise CloudStorageError."""
        storage = S3Storage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="aws", timeout=30)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.generate_presigned_url("key")

    def test_upload_results_validates_json_written(self) -> None:
        """upload_results should validate JSON was correctly serialized."""
        storage = S3Storage(bucket="my-bucket")

        # Object that can't be serialized to JSON
        class NonSerializable:
            pass

        with pytest.raises(CloudStorageError, match=r"serialize|JSON"):
            storage.upload_results("run-001", {"data": NonSerializable()})

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_retries_on_transient_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Upload should retry on transient network failures."""
        local_file = tmp_path / "data.json"
        local_file.write_text('{"key": "value"}')
        storage = S3Storage(bucket="my-bucket")

        # First call fails with a transient error, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "aws", stderr="RequestTimeout"),
            MagicMock(returncode=0),
        ]

        uri = storage.upload(local_file, "results/data.json")
        assert uri == "s3://my-bucket/mcpbr/results/data.json"
        assert mock_run.call_count == 2

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_download_retries_on_transient_failure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Download should retry on transient network failures."""
        storage = S3Storage(bucket="my-bucket")

        # First call fails transiently, second succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "aws", stderr="RequestTimeout"),
            MagicMock(returncode=0),
        ]

        result = storage.download("key", tmp_path / "out.json")
        assert result == tmp_path / "out.json"
        assert mock_run.call_count == 2

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_no_retry_on_auth_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Upload should NOT retry on authentication errors (non-transient)."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = S3Storage(bucket="my-bucket")

        mock_run.side_effect = subprocess.CalledProcessError(
            255, "aws", stderr="InvalidAccessKeyId"
        )

        with pytest.raises(CloudStorageError):
            storage.upload(local_file, "key")
        assert mock_run.call_count == 1  # No retries for auth errors

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_exhausts_retries(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Upload should raise after exhausting all retries."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = S3Storage(bucket="my-bucket")

        mock_run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="RequestTimeout")

        with pytest.raises(CloudStorageError, match="S3 upload failed"):
            storage.upload(local_file, "key")
        assert mock_run.call_count == 3  # Initial + 2 retries


class TestGCSErrorHandling:
    """GCS error handling tests."""

    def test_upload_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """GCS upload timeout should raise CloudStorageError."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = GCSStorage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="gcloud", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.upload(local_file, "key")

    def test_download_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """GCS download timeout should raise CloudStorageError."""
        storage = GCSStorage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="gcloud", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.download("key", tmp_path / "out.json")

    def test_download_cli_not_found(self, tmp_path: Path) -> None:
        """GCS download should raise clear error when gcloud CLI is not installed."""
        storage = GCSStorage(bucket="my-bucket")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(CloudStorageError, match="gcloud CLI not found"):
                storage.download("key", tmp_path / "out.json")

    def test_download_removes_partial_file_on_failure(self, tmp_path: Path) -> None:
        """GCS failed download should clean up partial/stale files."""
        storage = GCSStorage(bucket="my-bucket")
        dest = tmp_path / "out.json"
        dest.write_text("stale data")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "gcloud", stderr="NotFound")
            with pytest.raises(CloudStorageError):
                storage.download("missing-key", dest)

        assert not dest.exists(), "Partial/stale file should be removed after download failure"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_retries_on_transient_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """GCS upload should retry on transient failures."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = GCSStorage(bucket="my-bucket")

        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "gcloud", stderr="Connection reset"),
            MagicMock(returncode=0),
        ]

        uri = storage.upload(local_file, "key")
        assert uri.startswith("gs://")
        assert mock_run.call_count == 2


class TestAzureErrorHandling:
    """Azure Blob Storage error handling tests."""

    def test_upload_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """Azure upload timeout should raise CloudStorageError."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="az", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.upload(local_file, "key")

    def test_download_timeout_raises_cloud_storage_error(self, tmp_path: Path) -> None:
        """Azure download timeout should raise CloudStorageError."""
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="az", timeout=300)
            with pytest.raises(CloudStorageError, match="timed out"):
                storage.download("key", tmp_path / "out.json")

    def test_upload_cli_not_found(self, tmp_path: Path) -> None:
        """Azure upload should raise clear error when az CLI is not installed."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(CloudStorageError, match="Azure CLI not found"):
                storage.upload(local_file, "key")

    def test_download_cli_not_found(self, tmp_path: Path) -> None:
        """Azure download should raise clear error when az CLI is not installed."""
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(CloudStorageError, match="Azure CLI not found"):
                storage.download("key", tmp_path / "out.json")

    def test_download_removes_partial_file_on_failure(self, tmp_path: Path) -> None:
        """Azure failed download should clean up partial/stale files."""
        storage = AzureBlobStorage(container="my-container", account="myaccount")
        dest = tmp_path / "out.json"
        dest.write_text("stale data")

        with patch("mcpbr.storage.cloud.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "az", stderr="BlobNotFound")
            with pytest.raises(CloudStorageError):
                storage.download("missing-key", dest)

        assert not dest.exists(), "Partial/stale file should be removed after download failure"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_retries_on_transient_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Azure upload should retry on transient failures."""
        local_file = tmp_path / "data.json"
        local_file.write_text("{}")
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "az", stderr="Connection reset"),
            MagicMock(returncode=0),
        ]

        uri = storage.upload(local_file, "key")
        assert "blob.core.windows.net" in uri
        assert mock_run.call_count == 2
