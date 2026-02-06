"""Cloud storage backends for benchmark results.

Supports uploading and downloading results from cloud storage services:
- AWS S3
- Google Cloud Storage (GCS)
- Azure Blob Storage

Uses CLI tools (aws, gsutil, az) rather than SDKs to minimize dependencies.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CloudStorageError(RuntimeError):
    """Raised when a cloud storage operation fails."""

    pass


class S3Storage:
    """AWS S3 storage backend for benchmark results.

    Uses the `aws` CLI for operations. Requires AWS credentials configured
    via `aws configure` or environment variables.
    """

    def __init__(self, bucket: str, prefix: str = "mcpbr") -> None:
        """Initialize S3 storage.

        Args:
            bucket: S3 bucket name.
            prefix: Key prefix for all objects (default: "mcpbr").
        """
        self.bucket = bucket
        self.prefix = prefix

    def _s3_path(self, key: str) -> str:
        """Build full S3 URI."""
        return f"s3://{self.bucket}/{self.prefix}/{key}"

    def upload(self, local_path: Path, key: str) -> str:
        """Upload a file to S3.

        Args:
            local_path: Local file path to upload.
            key: S3 object key (relative to prefix).

        Returns:
            Full S3 URI of uploaded object.

        Raises:
            CloudStorageError: If upload fails.
        """
        s3_uri = self._s3_path(key)
        try:
            subprocess.run(
                ["aws", "s3", "cp", str(local_path), s3_uri],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            logger.info(f"Uploaded {local_path} to {s3_uri}")
            return s3_uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"S3 upload failed: {e.stderr}") from e
        except FileNotFoundError:
            raise CloudStorageError("AWS CLI not found. Install it: pip install awscli")

    def download(self, key: str, local_path: Path) -> Path:
        """Download a file from S3.

        Args:
            key: S3 object key (relative to prefix).
            local_path: Local destination path.

        Returns:
            Local path of downloaded file.

        Raises:
            CloudStorageError: If download fails.
        """
        s3_uri = self._s3_path(key)
        try:
            subprocess.run(
                ["aws", "s3", "cp", s3_uri, str(local_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            logger.info(f"Downloaded {s3_uri} to {local_path}")
            return local_path
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"S3 download failed: {e.stderr}") from e

    def list_objects(self, prefix: str = "") -> list[str]:
        """List objects in the bucket under the given prefix.

        Args:
            prefix: Additional prefix filter.

        Returns:
            List of object keys.
        """
        full_prefix = f"{self.prefix}/{prefix}" if prefix else self.prefix
        try:
            result = subprocess.run(
                [
                    "aws",
                    "s3api",
                    "list-objects-v2",
                    "--bucket",
                    self.bucket,
                    "--prefix",
                    full_prefix,
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            data = json.loads(result.stdout)
            contents = data.get("Contents", [])
            return [obj["Key"] for obj in contents]
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to list S3 objects: {e}")
            return []

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for an S3 object.

        Args:
            key: S3 object key.
            expires_in: URL expiration time in seconds (default: 1 hour).

        Returns:
            Presigned URL string.
        """
        s3_uri = self._s3_path(key)
        try:
            result = subprocess.run(
                [
                    "aws",
                    "s3",
                    "presign",
                    s3_uri,
                    "--expires-in",
                    str(expires_in),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"Failed to generate presigned URL: {e.stderr}") from e

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON.

        Args:
            run_id: Evaluation run identifier.
            results: Results dictionary to upload.

        Returns:
            S3 URI of the uploaded results.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            json.dump(results, f)
            temp_path = Path(f.name)

        try:
            return self.upload(temp_path, f"results/{run_id}/results.json")
        finally:
            temp_path.unlink(missing_ok=True)


class GCSStorage:
    """Google Cloud Storage backend for benchmark results.

    Uses the `gsutil` or `gcloud storage` CLI for operations.
    """

    def __init__(self, bucket: str, prefix: str = "mcpbr") -> None:
        """Initialize GCS storage.

        Args:
            bucket: GCS bucket name.
            prefix: Object prefix (default: "mcpbr").
        """
        self.bucket = bucket
        self.prefix = prefix

    def _gcs_path(self, key: str) -> str:
        """Build full GCS URI."""
        return f"gs://{self.bucket}/{self.prefix}/{key}"

    def upload(self, local_path: Path, key: str) -> str:
        """Upload a file to GCS."""
        gcs_uri = self._gcs_path(key)
        try:
            subprocess.run(
                ["gcloud", "storage", "cp", str(local_path), gcs_uri],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            logger.info(f"Uploaded {local_path} to {gcs_uri}")
            return gcs_uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"GCS upload failed: {e.stderr}") from e
        except FileNotFoundError:
            raise CloudStorageError("gcloud CLI not found. Install: https://cloud.google.com/sdk")

    def download(self, key: str, local_path: Path) -> Path:
        """Download a file from GCS."""
        gcs_uri = self._gcs_path(key)
        try:
            subprocess.run(
                ["gcloud", "storage", "cp", gcs_uri, str(local_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return local_path
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"GCS download failed: {e.stderr}") from e

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            json.dump(results, f)
            temp_path = Path(f.name)
        try:
            return self.upload(temp_path, f"results/{run_id}/results.json")
        finally:
            temp_path.unlink(missing_ok=True)


class AzureBlobStorage:
    """Azure Blob Storage backend for benchmark results.

    Uses the `az` CLI for operations.
    """

    def __init__(self, container: str, account: str, prefix: str = "mcpbr") -> None:
        """Initialize Azure Blob Storage.

        Args:
            container: Blob container name.
            account: Storage account name.
            prefix: Blob prefix (default: "mcpbr").
        """
        self.container = container
        self.account = account
        self.prefix = prefix

    def upload(self, local_path: Path, key: str) -> str:
        """Upload a file to Azure Blob Storage."""
        blob_name = f"{self.prefix}/{key}"
        try:
            subprocess.run(
                [
                    "az",
                    "storage",
                    "blob",
                    "upload",
                    "--account-name",
                    self.account,
                    "--container-name",
                    self.container,
                    "--name",
                    blob_name,
                    "--file",
                    str(local_path),
                    "--overwrite",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            uri = f"https://{self.account}.blob.core.windows.net/{self.container}/{blob_name}"
            logger.info(f"Uploaded {local_path} to {uri}")
            return uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"Azure Blob upload failed: {e.stderr}") from e

    def download(self, key: str, local_path: Path) -> Path:
        """Download a file from Azure Blob Storage."""
        blob_name = f"{self.prefix}/{key}"
        try:
            subprocess.run(
                [
                    "az",
                    "storage",
                    "blob",
                    "download",
                    "--account-name",
                    self.account,
                    "--container-name",
                    self.container,
                    "--name",
                    blob_name,
                    "--file",
                    str(local_path),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )
            return local_path
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"Azure Blob download failed: {e.stderr}") from e

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            json.dump(results, f)
            temp_path = Path(f.name)
        try:
            return self.upload(temp_path, f"results/{run_id}/results.json")
        finally:
            temp_path.unlink(missing_ok=True)


def create_cloud_storage(config: dict[str, Any]) -> S3Storage | GCSStorage | AzureBlobStorage:
    """Factory function to create a cloud storage backend from config.

    Config format::

        cloud_storage:
          provider: s3  # or gcs, azure_blob
          bucket: my-bucket  # or container for azure
          account: my-account  # azure only
          prefix: mcpbr

    Args:
        config: Cloud storage configuration dictionary.

    Returns:
        Cloud storage backend instance.

    Raises:
        ValueError: If the provider is not recognized.
    """
    provider = config.get("provider", "s3")
    prefix = config.get("prefix", "mcpbr")

    if provider == "s3":
        return S3Storage(bucket=config["bucket"], prefix=prefix)
    elif provider == "gcs":
        return GCSStorage(bucket=config["bucket"], prefix=prefix)
    elif provider == "azure_blob":
        return AzureBlobStorage(
            container=config.get("container", config.get("bucket", "")),
            account=config["account"],
            prefix=prefix,
        )
    else:
        raise ValueError(
            f"Unknown cloud storage provider: {provider}. Supported: s3, gcs, azure_blob"
        )
