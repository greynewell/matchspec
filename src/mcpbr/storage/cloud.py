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
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds

# Patterns that indicate transient (retryable) failures
_TRANSIENT_ERROR_PATTERNS = (
    "RequestTimeout",
    "Connection reset",
    "ConnectionError",
    "ServiceUnavailable",
    "ThrottlingException",
    "SlowDown",
    "InternalError",
    "RequestTimeTooSkewed",
    "connection reset",
    "timeout",
    "Throttled",
    "TooManyRequests",
    "ECONNRESET",
    "ETIMEDOUT",
)

# Patterns that indicate authentication/authorization failures (non-retryable)
_AUTH_ERROR_PATTERNS = (
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "AccessDenied",
    "AuthorizationError",
    "AuthenticationFailed",
    "InvalidCredential",
    "ExpiredToken",
    "InvalidToken",
    "Forbidden",
    "Unauthorized",
    "AuthorizationPermissionMismatch",
)


class CloudStorageError(RuntimeError):
    """Raised when a cloud storage operation fails."""

    pass


def _is_transient_error(error: subprocess.CalledProcessError) -> bool:
    """Check if a subprocess error is transient and should be retried.

    Args:
        error: The CalledProcessError to check.

    Returns:
        True if the error appears transient, False otherwise.
    """
    stderr = error.stderr or ""
    # Never retry authentication errors
    for pattern in _AUTH_ERROR_PATTERNS:
        if pattern in stderr:
            return False
    # Check for transient patterns
    for pattern in _TRANSIENT_ERROR_PATTERNS:
        if pattern in stderr:
            return True
    return False


def _run_with_retry(
    cmd: list[str],
    *,
    timeout: int = 300,
    max_retries: int = MAX_RETRIES,
    operation_label: str = "operation",
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command with retry logic for transient failures.

    Args:
        cmd: Command and arguments to run.
        timeout: Timeout in seconds for each attempt.
        max_retries: Maximum number of attempts (including the first).
        operation_label: Human-readable label for log messages.

    Returns:
        The CompletedProcess result on success.

    Raises:
        subprocess.CalledProcessError: If all retries are exhausted.
        subprocess.TimeoutExpired: If the command times out on the final attempt.
        FileNotFoundError: If the CLI tool is not found.
    """
    last_error: subprocess.CalledProcessError | subprocess.TimeoutExpired | None = None

    for attempt in range(max_retries):
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as e:
            last_error = e
            if attempt < max_retries - 1 and _is_transient_error(e):
                wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    f"{operation_label} failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time:.1f}s: {e.stderr}"
                )
                time.sleep(wait_time)
                continue
            raise
        except subprocess.TimeoutExpired as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    f"{operation_label} timed out (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time:.1f}s"
                )
                time.sleep(wait_time)
                continue
            raise
        # FileNotFoundError is never retried -- let it propagate immediately

    # Should not reach here, but raise the last error for safety
    raise last_error  # type: ignore[misc]


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
            _run_with_retry(
                ["aws", "s3", "cp", str(local_path), s3_uri],
                timeout=300,
                operation_label=f"S3 upload to {s3_uri}",
            )
            logger.info(f"Uploaded {local_path} to {s3_uri}")
            return s3_uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"S3 upload failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise CloudStorageError(f"S3 upload timed out after {e.timeout}s for {s3_uri}") from e
        except FileNotFoundError:
            raise CloudStorageError("AWS CLI not found. Install it: pip install awscli") from None

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
            _run_with_retry(
                ["aws", "s3", "cp", s3_uri, str(local_path)],
                timeout=300,
                operation_label=f"S3 download from {s3_uri}",
            )
            logger.info(f"Downloaded {s3_uri} to {local_path}")
            return local_path
        except subprocess.CalledProcessError as e:
            # Clean up any partial/stale file to prevent corrupt data
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(f"S3 download failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(f"S3 download timed out after {e.timeout}s for {s3_uri}") from e
        except FileNotFoundError:
            raise CloudStorageError("AWS CLI not found. Install it: pip install awscli") from None

    def list_objects(self, prefix: str = "") -> list[str]:
        """List objects in the bucket under the given prefix.

        Args:
            prefix: Additional prefix filter.

        Returns:
            List of object keys.

        Raises:
            CloudStorageError: If the listing fails due to authentication,
                timeout, or other non-transient errors.
        """
        full_prefix = f"{self.prefix}/{prefix}" if prefix else self.prefix
        try:
            result = _run_with_retry(
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
                timeout=60,
                operation_label=f"S3 list objects in {self.bucket}/{full_prefix}",
            )
            data = json.loads(result.stdout)
            contents = data.get("Contents", [])
            return [obj["Key"] for obj in contents]
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            # Check for authentication/authorization errors -- these should raise
            for pattern in _AUTH_ERROR_PATTERNS:
                if pattern in stderr:
                    raise CloudStorageError(
                        f"S3 list failed due to authentication/credential error: {stderr}"
                    ) from e
            # For other errors, log warning and return empty (backward-compatible)
            logger.warning(f"Failed to list S3 objects: {e}")
            return []
        except subprocess.TimeoutExpired as e:
            raise CloudStorageError(f"S3 list objects timed out after {e.timeout}s") from e
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse S3 list response: {e}")
            return []

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for an S3 object.

        Args:
            key: S3 object key.
            expires_in: URL expiration time in seconds (default: 1 hour).

        Returns:
            Presigned URL string.

        Raises:
            CloudStorageError: If URL generation fails.
        """
        s3_uri = self._s3_path(key)
        try:
            result = _run_with_retry(
                [
                    "aws",
                    "s3",
                    "presign",
                    s3_uri,
                    "--expires-in",
                    str(expires_in),
                ],
                timeout=30,
                operation_label=f"S3 presign {s3_uri}",
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"Failed to generate presigned URL: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise CloudStorageError(f"S3 presign timed out after {e.timeout}s for {s3_uri}") from e

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON.

        Args:
            run_id: Evaluation run identifier.
            results: Results dictionary to upload.

        Returns:
            S3 URI of the uploaded results.

        Raises:
            CloudStorageError: If JSON serialization or upload fails.
        """
        try:
            json_data = json.dumps(results)
        except (TypeError, ValueError) as e:
            raise CloudStorageError(f"Failed to serialize results to JSON: {e}") from e

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            f.write(json_data)
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
        """Upload a file to GCS.

        Args:
            local_path: Local file path to upload.
            key: GCS object key (relative to prefix).

        Returns:
            Full GCS URI of uploaded object.

        Raises:
            CloudStorageError: If upload fails.
        """
        gcs_uri = self._gcs_path(key)
        try:
            _run_with_retry(
                ["gcloud", "storage", "cp", str(local_path), gcs_uri],
                timeout=300,
                operation_label=f"GCS upload to {gcs_uri}",
            )
            logger.info(f"Uploaded {local_path} to {gcs_uri}")
            return gcs_uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"GCS upload failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise CloudStorageError(f"GCS upload timed out after {e.timeout}s for {gcs_uri}") from e
        except FileNotFoundError:
            raise CloudStorageError(
                "gcloud CLI not found. Install: https://cloud.google.com/sdk"
            ) from None

    def download(self, key: str, local_path: Path) -> Path:
        """Download a file from GCS.

        Args:
            key: GCS object key (relative to prefix).
            local_path: Local destination path.

        Returns:
            Local path of downloaded file.

        Raises:
            CloudStorageError: If download fails.
        """
        gcs_uri = self._gcs_path(key)
        try:
            _run_with_retry(
                ["gcloud", "storage", "cp", gcs_uri, str(local_path)],
                timeout=300,
                operation_label=f"GCS download from {gcs_uri}",
            )
            return local_path
        except subprocess.CalledProcessError as e:
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(f"GCS download failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(
                f"GCS download timed out after {e.timeout}s for {gcs_uri}"
            ) from e
        except FileNotFoundError:
            raise CloudStorageError(
                "gcloud CLI not found. Install: https://cloud.google.com/sdk"
            ) from None

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON.

        Args:
            run_id: Evaluation run identifier.
            results: Results dictionary to upload.

        Returns:
            GCS URI of the uploaded results.

        Raises:
            CloudStorageError: If JSON serialization or upload fails.
        """
        try:
            json_data = json.dumps(results)
        except (TypeError, ValueError) as e:
            raise CloudStorageError(f"Failed to serialize results to JSON: {e}") from e

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            f.write(json_data)
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
        """Upload a file to Azure Blob Storage.

        Args:
            local_path: Local file path to upload.
            key: Blob name (relative to prefix).

        Returns:
            Full Azure Blob URI of uploaded object.

        Raises:
            CloudStorageError: If upload fails.
        """
        blob_name = f"{self.prefix}/{key}"
        try:
            _run_with_retry(
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
                timeout=300,
                operation_label=f"Azure Blob upload {blob_name}",
            )
            uri = f"https://{self.account}.blob.core.windows.net/{self.container}/{blob_name}"
            logger.info(f"Uploaded {local_path} to {uri}")
            return uri
        except subprocess.CalledProcessError as e:
            raise CloudStorageError(f"Azure Blob upload failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            raise CloudStorageError(
                f"Azure Blob upload timed out after {e.timeout}s for {blob_name}"
            ) from e
        except FileNotFoundError:
            raise CloudStorageError(
                "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            ) from None

    def download(self, key: str, local_path: Path) -> Path:
        """Download a file from Azure Blob Storage.

        Args:
            key: Blob name (relative to prefix).
            local_path: Local destination path.

        Returns:
            Local path of downloaded file.

        Raises:
            CloudStorageError: If download fails.
        """
        blob_name = f"{self.prefix}/{key}"
        try:
            _run_with_retry(
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
                timeout=300,
                operation_label=f"Azure Blob download {blob_name}",
            )
            return local_path
        except subprocess.CalledProcessError as e:
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(f"Azure Blob download failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            Path(local_path).unlink(missing_ok=True)
            raise CloudStorageError(
                f"Azure Blob download timed out after {e.timeout}s for {blob_name}"
            ) from e
        except FileNotFoundError:
            raise CloudStorageError(
                "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
            ) from None

    def upload_results(self, run_id: str, results: dict[str, Any]) -> str:
        """Upload evaluation results as JSON.

        Args:
            run_id: Evaluation run identifier.
            results: Results dictionary to upload.

        Returns:
            Azure Blob URI of the uploaded results.

        Raises:
            CloudStorageError: If JSON serialization or upload fails.
        """
        try:
            json_data = json.dumps(results)
        except (TypeError, ValueError) as e:
            raise CloudStorageError(f"Failed to serialize results to JSON: {e}") from e

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix=f"mcpbr_{run_id}_"
        ) as f:
            f.write(json_data)
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
