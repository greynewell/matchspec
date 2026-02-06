"""Tests for cloud storage backends."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.storage.cloud import (
    AzureBlobStorage,
    CloudStorageError,
    GCSStorage,
    S3Storage,
    create_cloud_storage,
)


class TestS3Storage:
    """Tests for S3Storage backend."""

    def test_init(self) -> None:
        """Test S3Storage initialization."""
        storage = S3Storage(bucket="my-bucket", prefix="test")
        assert storage.bucket == "my-bucket"
        assert storage.prefix == "test"

    def test_init_default_prefix(self) -> None:
        """Test S3Storage uses default prefix."""
        storage = S3Storage(bucket="my-bucket")
        assert storage.prefix == "mcpbr"

    def test_s3_path(self) -> None:
        """Test S3 URI construction."""
        storage = S3Storage(bucket="my-bucket", prefix="test")
        assert storage._s3_path("results/run-1.json") == "s3://my-bucket/test/results/run-1.json"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful upload to S3."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = S3Storage(bucket="my-bucket", prefix="test")

        local_file = tmp_path / "data.json"
        local_file.write_text('{"key": "value"}')

        uri = storage.upload(local_file, "results/data.json")
        assert uri == "s3://my-bucket/test/results/data.json"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0:3] == ["aws", "s3", "cp"]

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test upload failure raises CloudStorageError."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="Access Denied")
        storage = S3Storage(bucket="my-bucket")

        local_file = tmp_path / "data.json"
        local_file.write_text("{}")

        with pytest.raises(CloudStorageError, match="S3 upload failed"):
            storage.upload(local_file, "key")

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_cli_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test upload when AWS CLI is not installed."""
        mock_run.side_effect = FileNotFoundError()
        storage = S3Storage(bucket="my-bucket")

        local_file = tmp_path / "data.json"
        local_file.write_text("{}")

        with pytest.raises(CloudStorageError, match="AWS CLI not found"):
            storage.upload(local_file, "key")

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_download_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful download from S3."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = S3Storage(bucket="my-bucket", prefix="test")

        local_path = tmp_path / "downloaded.json"
        result = storage.download("results/data.json", local_path)
        assert result == local_path
        mock_run.assert_called_once()

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_download_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test download failure raises CloudStorageError."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="Not found")
        storage = S3Storage(bucket="my-bucket")

        with pytest.raises(CloudStorageError, match="S3 download failed"):
            storage.download("missing-key", tmp_path / "out.json")

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_list_objects(self, mock_run: MagicMock) -> None:
        """Test listing S3 objects."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "Contents": [
                        {"Key": "mcpbr/results/run-1.json"},
                        {"Key": "mcpbr/results/run-2.json"},
                    ]
                }
            ),
        )
        storage = S3Storage(bucket="my-bucket")
        keys = storage.list_objects("results/")
        assert len(keys) == 2
        assert keys[0] == "mcpbr/results/run-1.json"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_list_objects_empty(self, mock_run: MagicMock) -> None:
        """Test listing with no objects returns empty list."""
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({}))
        storage = S3Storage(bucket="my-bucket")
        keys = storage.list_objects()
        assert keys == []

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_list_objects_failure(self, mock_run: MagicMock) -> None:
        """Test list failure returns empty list."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="error")
        storage = S3Storage(bucket="my-bucket")
        keys = storage.list_objects()
        assert keys == []

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_generate_presigned_url(self, mock_run: MagicMock) -> None:
        """Test presigned URL generation."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://my-bucket.s3.amazonaws.com/test/key?sig=abc\n"
        )
        storage = S3Storage(bucket="my-bucket", prefix="test")
        url = storage.generate_presigned_url("key", expires_in=7200)
        assert "s3.amazonaws.com" in url
        # Verify expires-in was passed
        args = mock_run.call_args[0][0]
        assert "--expires-in" in args
        assert "7200" in args

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_results(self, mock_run: MagicMock) -> None:
        """Test uploading evaluation results as JSON."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = S3Storage(bucket="my-bucket")
        results = {"summary": {"pass_rate": 0.75}, "tasks": []}

        uri = storage.upload_results("run-001", results)
        assert "results/run-001/results.json" in uri


class TestGCSStorage:
    """Tests for GCSStorage backend."""

    def test_init(self) -> None:
        """Test GCSStorage initialization."""
        storage = GCSStorage(bucket="my-gcs-bucket", prefix="test")
        assert storage.bucket == "my-gcs-bucket"
        assert storage.prefix == "test"

    def test_gcs_path(self) -> None:
        """Test GCS URI construction."""
        storage = GCSStorage(bucket="my-gcs-bucket", prefix="test")
        assert storage._gcs_path("key") == "gs://my-gcs-bucket/test/key"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful upload to GCS."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = GCSStorage(bucket="my-gcs-bucket")

        local_file = tmp_path / "data.json"
        local_file.write_text("{}")

        uri = storage.upload(local_file, "results/data.json")
        assert uri.startswith("gs://")
        args = mock_run.call_args[0][0]
        assert args[0:3] == ["gcloud", "storage", "cp"]

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_gcloud_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test upload when gcloud CLI is not installed."""
        mock_run.side_effect = FileNotFoundError()
        storage = GCSStorage(bucket="my-gcs-bucket")

        local_file = tmp_path / "data.json"
        local_file.write_text("{}")

        with pytest.raises(CloudStorageError, match="gcloud CLI not found"):
            storage.upload(local_file, "key")

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_download_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful download from GCS."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = GCSStorage(bucket="my-gcs-bucket")

        result = storage.download("key", tmp_path / "out.json")
        assert result == tmp_path / "out.json"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_results(self, mock_run: MagicMock) -> None:
        """Test uploading results to GCS."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = GCSStorage(bucket="my-gcs-bucket")

        uri = storage.upload_results("run-002", {"summary": {}, "tasks": []})
        assert "results/run-002" in uri


class TestAzureBlobStorage:
    """Tests for AzureBlobStorage backend."""

    def test_init(self) -> None:
        """Test AzureBlobStorage initialization."""
        storage = AzureBlobStorage(container="my-container", account="myaccount")
        assert storage.container == "my-container"
        assert storage.account == "myaccount"
        assert storage.prefix == "mcpbr"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful upload to Azure Blob Storage."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        local_file = tmp_path / "data.json"
        local_file.write_text("{}")

        uri = storage.upload(local_file, "results/data.json")
        assert "blob.core.windows.net" in uri
        assert "myaccount" in uri
        assert "my-container" in uri
        args = mock_run.call_args[0][0]
        assert args[0:4] == ["az", "storage", "blob", "upload"]

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_download_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful download from Azure Blob Storage."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        result = storage.download("key", tmp_path / "out.json")
        assert result == tmp_path / "out.json"

    @patch("mcpbr.storage.cloud.subprocess.run")
    def test_upload_results(self, mock_run: MagicMock) -> None:
        """Test uploading results to Azure."""
        mock_run.return_value = MagicMock(returncode=0)
        storage = AzureBlobStorage(container="my-container", account="myaccount")

        uri = storage.upload_results("run-003", {"summary": {}, "tasks": []})
        assert "blob.core.windows.net" in uri


class TestCreateCloudStorage:
    """Tests for create_cloud_storage factory function."""

    def test_create_s3_storage(self) -> None:
        """Test creating S3 storage backend."""
        config = {"provider": "s3", "bucket": "my-bucket", "prefix": "custom"}
        storage = create_cloud_storage(config)
        assert isinstance(storage, S3Storage)
        assert storage.bucket == "my-bucket"
        assert storage.prefix == "custom"

    def test_create_gcs_storage(self) -> None:
        """Test creating GCS storage backend."""
        config = {"provider": "gcs", "bucket": "my-gcs-bucket"}
        storage = create_cloud_storage(config)
        assert isinstance(storage, GCSStorage)

    def test_create_azure_storage(self) -> None:
        """Test creating Azure Blob storage backend."""
        config = {
            "provider": "azure_blob",
            "container": "my-container",
            "account": "myaccount",
        }
        storage = create_cloud_storage(config)
        assert isinstance(storage, AzureBlobStorage)
        assert storage.container == "my-container"

    def test_create_azure_storage_with_bucket_alias(self) -> None:
        """Test creating Azure storage with 'bucket' as alias for 'container'."""
        config = {
            "provider": "azure_blob",
            "bucket": "my-bucket",
            "account": "myaccount",
        }
        storage = create_cloud_storage(config)
        assert isinstance(storage, AzureBlobStorage)
        assert storage.container == "my-bucket"

    def test_default_provider_is_s3(self) -> None:
        """Test that default provider is S3."""
        config = {"bucket": "my-bucket"}
        storage = create_cloud_storage(config)
        assert isinstance(storage, S3Storage)

    def test_unknown_provider_raises(self) -> None:
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown cloud storage provider"):
            create_cloud_storage({"provider": "unknown", "bucket": "b"})

    def test_default_prefix(self) -> None:
        """Test that default prefix is 'mcpbr'."""
        config = {"provider": "s3", "bucket": "my-bucket"}
        storage = create_cloud_storage(config)
        assert storage.prefix == "mcpbr"
