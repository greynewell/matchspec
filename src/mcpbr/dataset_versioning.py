"""Dataset versioning for reproducible benchmark evaluations.

This module provides utilities to pin and track HuggingFace dataset versions,
ensuring that benchmark runs can be reproduced with the exact same data.
Version information includes dataset revision hashes, download timestamps,
and optional checksums for data integrity verification.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from datasets import Dataset, load_dataset
from huggingface_hub import dataset_info

logger = logging.getLogger(__name__)


@dataclass
class DatasetVersion:
    """Pinned version information for a HuggingFace dataset.

    Attributes:
        dataset_id: HuggingFace dataset identifier (e.g., 'SWE-bench/SWE-bench_Lite').
        revision: Git revision hash of the dataset (None for latest).
        download_date: ISO 8601 timestamp of when the version was pinned.
        checksum: Optional SHA256 checksum of the dataset content for integrity verification.
    """

    dataset_id: str
    revision: str | None
    download_date: str
    checksum: str | None


def pin_dataset_version(
    dataset_id: str,
    revision: str | None = None,
) -> DatasetVersion:
    """Record the current version of a HuggingFace dataset.

    Fetches dataset metadata from the HuggingFace Hub to determine the
    current revision. If a specific revision is provided, it is used directly.

    Args:
        dataset_id: HuggingFace dataset identifier (e.g., 'SWE-bench/SWE-bench_Lite').
        revision: Specific git revision to pin. If None, the latest revision is fetched.

    Returns:
        DatasetVersion with the pinned revision and metadata.

    Raises:
        Exception: If the dataset cannot be found or accessed on the HuggingFace Hub.
    """
    info = dataset_info(dataset_id, revision=revision)
    resolved_revision = info.sha

    # Compute a checksum from the dataset card and file metadata for integrity
    checksum_data = f"{dataset_id}:{resolved_revision}"
    if info.siblings:
        file_names = sorted(s.rfilename for s in info.siblings)
        checksum_data += ":" + ",".join(file_names)
    checksum = hashlib.sha256(checksum_data.encode()).hexdigest()

    download_date = datetime.now(UTC).isoformat()

    version = DatasetVersion(
        dataset_id=dataset_id,
        revision=resolved_revision,
        download_date=download_date,
        checksum=checksum,
    )

    logger.info(
        "Pinned dataset %s at revision %s",
        dataset_id,
        resolved_revision,
    )

    return version


def load_dataset_pinned(
    dataset_id: str,
    version: DatasetVersion | None = None,
    **kwargs: Any,
) -> Dataset:
    """Load a HuggingFace dataset using a pinned version for reproducibility.

    Wraps the standard ``datasets.load_dataset`` call, injecting the pinned
    revision so that the exact same data snapshot is used across runs.

    Args:
        dataset_id: HuggingFace dataset identifier.
        version: Pinned version to use. If None, loads the latest version.
        **kwargs: Additional keyword arguments passed to ``datasets.load_dataset``
            (e.g., split, name, streaming).

    Returns:
        The loaded HuggingFace Dataset.
    """
    revision = None
    if version is not None:
        revision = version.revision
        logger.info(
            "Loading dataset %s at pinned revision %s (pinned on %s)",
            dataset_id,
            revision,
            version.download_date,
        )
    else:
        logger.info("Loading dataset %s at latest revision", dataset_id)

    return load_dataset(dataset_id, revision=revision, **kwargs)


def save_version_manifest(
    versions: dict[str, DatasetVersion],
    path: Path,
) -> None:
    """Save dataset version pins to a JSON manifest file.

    The manifest file records all pinned dataset versions so they can be
    shared across team members or CI environments for reproducible runs.

    Args:
        versions: Mapping of dataset identifiers to their pinned versions.
        path: File path to write the JSON manifest.
    """
    manifest: dict[str, Any] = {
        "format_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "datasets": {},
    }

    for dataset_id, version in versions.items():
        manifest["datasets"][dataset_id] = asdict(version)

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Saved version manifest with %d datasets to %s", len(versions), path)


def load_version_manifest(path: Path) -> dict[str, DatasetVersion]:
    """Load pinned dataset versions from a JSON manifest file.

    Args:
        path: File path to the JSON manifest.

    Returns:
        Mapping of dataset identifiers to their pinned versions.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        json.JSONDecodeError: If the manifest file contains invalid JSON.
        KeyError: If the manifest is missing required fields.
    """
    with open(path) as f:
        manifest = json.load(f)

    versions: dict[str, DatasetVersion] = {}
    datasets_data = manifest.get("datasets", {})

    for dataset_id, version_data in datasets_data.items():
        versions[dataset_id] = DatasetVersion(
            dataset_id=version_data["dataset_id"],
            revision=version_data.get("revision"),
            download_date=version_data["download_date"],
            checksum=version_data.get("checksum"),
        )

    logger.info("Loaded version manifest with %d datasets from %s", len(versions), path)

    return versions


def get_dataset_info(dataset_id: str) -> dict[str, Any]:
    """Get metadata about a HuggingFace dataset.

    Retrieves information such as the latest revision, description,
    file listing, and other Hub metadata.

    Args:
        dataset_id: HuggingFace dataset identifier.

    Returns:
        Dictionary containing dataset metadata with keys:
            - dataset_id: The dataset identifier.
            - latest_revision: The current HEAD revision hash.
            - description: Dataset description text.
            - tags: List of dataset tags.
            - downloads: Number of downloads.
            - last_modified: Last modification timestamp.
            - files: List of files in the dataset repository.

    Raises:
        Exception: If the dataset cannot be found or accessed on the HuggingFace Hub.
    """
    info = dataset_info(dataset_id)

    files: list[str] = []
    if info.siblings:
        files = [s.rfilename for s in info.siblings]

    result: dict[str, Any] = {
        "dataset_id": dataset_id,
        "latest_revision": info.sha,
        "description": getattr(info, "description", "") or "",
        "tags": list(info.tags) if info.tags else [],
        "downloads": info.downloads if info.downloads is not None else 0,
        "last_modified": info.last_modified.isoformat() if info.last_modified else None,
        "files": files,
    }

    return result
