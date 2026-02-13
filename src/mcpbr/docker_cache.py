"""Docker image caching strategy for optimized evaluation startup.

This module provides an LRU-based cache management system for Docker images
used in mcpbr benchmark evaluations. It tracks locally cached images, enforces
size limits, supports eviction strategies, and recommends cache warming based
on benchmark history.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import docker

logger = logging.getLogger(__name__)

# Prefix used to identify mcpbr-related Docker images
MCPBR_IMAGE_PREFIX = "mcpbr"
SWEBENCH_IMAGE_PREFIX = "ghcr.io/epoch-research/swe-bench"

# Default metadata file name
CACHE_METADATA_FILE = "docker_cache_metadata.json"


@dataclass
class CacheEntry:
    """Metadata for a single cached Docker image.

    Attributes:
        image_tag: Full Docker image tag (e.g., 'ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907').
        size_mb: Image size in megabytes.
        last_used: Timestamp of the last time this image was used.
        use_count: Number of times this image has been used.
        layers: List of layer digest strings for deduplication awareness.
        created: Timestamp when this image was first cached.
    """

    image_tag: str
    size_mb: float
    last_used: datetime
    use_count: int
    layers: list[str]
    created: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the cache entry.
        """
        return {
            "image_tag": self.image_tag,
            "size_mb": self.size_mb,
            "last_used": self.last_used.isoformat(),
            "use_count": self.use_count,
            "layers": self.layers,
            "created": self.created.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create a CacheEntry from a dictionary.

        Args:
            data: Dictionary with cache entry fields.

        Returns:
            CacheEntry instance.
        """
        return cls(
            image_tag=data["image_tag"],
            size_mb=data["size_mb"],
            last_used=datetime.fromisoformat(data["last_used"]),
            use_count=data["use_count"],
            layers=data.get("layers", []),
            created=datetime.fromisoformat(data["created"]),
        )


@dataclass
class CacheConfig:
    """Configuration for Docker image cache management.

    Attributes:
        max_size_gb: Maximum total disk usage for cached images in gigabytes.
        max_images: Maximum number of cached images to retain.
        eviction_strategy: Strategy for evicting images when limits are reached.
            Currently only 'lru' (least recently used) is supported.
        cache_dir: Directory for storing cache metadata files.
    """

    max_size_gb: float = 50.0
    max_images: int = 100
    eviction_strategy: str = "lru"
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "mcpbr" / "docker")

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if self.max_size_gb <= 0:
            raise ValueError(f"max_size_gb must be positive, got {self.max_size_gb}")
        if self.max_images <= 0:
            raise ValueError(f"max_images must be positive, got {self.max_images}")
        if self.eviction_strategy not in ("lru",):
            raise ValueError(
                f"Unsupported eviction strategy: {self.eviction_strategy!r}. "
                f"Supported strategies: 'lru'"
            )


@dataclass
class CacheStats:
    """Statistics about the Docker image cache.

    Attributes:
        total_images: Number of images currently tracked in the cache.
        total_size_gb: Total size of cached images in gigabytes.
        cache_hit_rate: Ratio of cache hits to total lookups (0.0 to 1.0).
        most_used: List of image tags sorted by descending use count (top 5).
        least_used: List of image tags sorted by ascending use count (bottom 5).
        potential_savings_gb: Estimated savings from layer deduplication in gigabytes.
    """

    total_images: int
    total_size_gb: float
    cache_hit_rate: float
    most_used: list[str]
    least_used: list[str]
    potential_savings_gb: float


def _is_mcpbr_image(tag: str) -> bool:
    """Check if a Docker image tag is mcpbr-related.

    Args:
        tag: Docker image tag string.

    Returns:
        True if the image is related to mcpbr benchmarks.
    """
    tag_lower = tag.lower()
    return (
        tag_lower.startswith(MCPBR_IMAGE_PREFIX)
        or SWEBENCH_IMAGE_PREFIX in tag_lower
        or "swe-bench" in tag_lower
    )


class ImageCache:
    """Manages Docker image caching with LRU eviction for mcpbr evaluations.

    Tracks which Docker images are cached locally, records usage metadata,
    enforces cache size and count limits via LRU eviction, and provides
    statistics and cache warming recommendations.

    The cache stores metadata in a JSON file on disk and interacts with
    the Docker daemon to inspect and remove images.
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize the Docker image cache manager.

        Args:
            config: Cache configuration. Uses defaults if not provided.
        """
        self._config = config or CacheConfig()
        self._entries: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._benchmark_history: dict[str, list[str]] = {}
        self._client: Any = None

        # Ensure the metadata directory exists
        self._config.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing metadata from disk
        self._load_metadata()

    @property
    def _docker_client(self) -> Any:
        """Lazily initialize and return the Docker client.

        Returns:
            Docker client instance, or None if Docker is unavailable.
        """
        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as e:
                logger.warning(f"Docker is not available: {e}")
                self._client = None
        return self._client

    def _metadata_path(self) -> Path:
        """Return the path to the cache metadata file.

        Returns:
            Path to the JSON metadata file.
        """
        return self._config.cache_dir / CACHE_METADATA_FILE

    def _load_metadata(self) -> None:
        """Load cache metadata from disk."""
        metadata_path = self._metadata_path()
        if not metadata_path.exists():
            return

        try:
            with open(metadata_path) as f:
                data = json.load(f)

            for entry_data in data.get("entries", []):
                try:
                    entry = CacheEntry.from_dict(entry_data)
                    self._entries[entry.image_tag] = entry
                except (KeyError, ValueError) as e:
                    logger.debug(f"Skipping corrupted cache entry: {e}")

            self._hits = data.get("hits", 0)
            self._misses = data.get("misses", 0)
            self._benchmark_history = data.get("benchmark_history", {})

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to load cache metadata, starting fresh: {e}")
            self._entries = {}
            self._hits = 0
            self._misses = 0
            self._benchmark_history = {}

    def _save_metadata(self) -> None:
        """Persist cache metadata to disk."""
        data = {
            "entries": [entry.to_dict() for entry in self._entries.values()],
            "hits": self._hits,
            "misses": self._misses,
            "benchmark_history": self._benchmark_history,
        }

        metadata_path = self._metadata_path()
        try:
            with open(metadata_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save cache metadata: {e}")

    def scan(self) -> list[CacheEntry]:
        """Scan local Docker images and update cache entries for mcpbr-related images.

        Queries the Docker daemon for locally available images, filters for
        mcpbr-related ones, and updates the internal metadata. New images
        are added with initial metadata; existing entries retain their usage
        counters.

        Returns:
            List of CacheEntry objects for all mcpbr-related images found locally.
        """
        client = self._docker_client
        if client is None:
            logger.warning("Cannot scan images: Docker is not available")
            return list(self._entries.values())

        try:
            images = client.images.list()
        except Exception as e:
            logger.warning(f"Failed to list Docker images: {e}")
            return list(self._entries.values())

        now = datetime.now(UTC)
        found_tags: set[str] = set()

        for image in images:
            tags = image.tags if image.tags else []
            for tag in tags:
                if not _is_mcpbr_image(tag):
                    continue

                found_tags.add(tag)

                if tag in self._entries:
                    # Update size from Docker (it may have changed)
                    size_mb = image.attrs.get("Size", 0) / (1024 * 1024)
                    self._entries[tag].size_mb = size_mb
                else:
                    # New image discovered
                    size_mb = image.attrs.get("Size", 0) / (1024 * 1024)
                    layers = []
                    root_fs = image.attrs.get("RootFS", {})
                    if root_fs.get("Type") == "layers":
                        layers = root_fs.get("Layers", [])

                    self._entries[tag] = CacheEntry(
                        image_tag=tag,
                        size_mb=size_mb,
                        last_used=now,
                        use_count=0,
                        layers=layers,
                        created=now,
                    )

        # Remove entries for images that no longer exist locally
        stale_tags = set(self._entries.keys()) - found_tags
        for stale_tag in stale_tags:
            del self._entries[stale_tag]

        self._save_metadata()
        return list(self._entries.values())

    def get_cached(self, image_tag: str) -> CacheEntry | None:
        """Look up a cached image by tag.

        Records a cache hit or miss for statistics tracking.

        Args:
            image_tag: Docker image tag to look up.

        Returns:
            CacheEntry if the image is tracked in the cache, None otherwise.
        """
        entry = self._entries.get(image_tag)
        if entry is not None:
            self._hits += 1
        else:
            self._misses += 1
        self._save_metadata()
        return entry

    def record_use(self, image_tag: str) -> None:
        """Record usage of a cached image, updating last_used and use_count.

        If the image is not currently tracked, this is a no-op.

        Args:
            image_tag: Docker image tag that was used.
        """
        entry = self._entries.get(image_tag)
        if entry is None:
            logger.debug(f"Image {image_tag!r} is not tracked in cache, skipping record_use")
            return

        entry.last_used = datetime.now(UTC)
        entry.use_count += 1
        self._save_metadata()

    def record_benchmark_use(self, benchmark_name: str, image_tag: str) -> None:
        """Record that a benchmark used a specific image for warmup recommendations.

        Args:
            benchmark_name: Name of the benchmark (e.g., 'swe-bench-lite').
            image_tag: Docker image tag used by the benchmark.
        """
        if benchmark_name not in self._benchmark_history:
            self._benchmark_history[benchmark_name] = []

        history = self._benchmark_history[benchmark_name]
        if image_tag not in history:
            history.append(image_tag)

        self._save_metadata()

    def evict_lru(self, target_size_gb: float | None = None) -> list[str]:
        """Evict least recently used images to meet cache size or count limits.

        Removes images from both the cache metadata and the local Docker daemon.
        Images are evicted in order of least recent usage until the target size
        is reached or the image count limit is satisfied.

        Args:
            target_size_gb: Target cache size in gigabytes. If None, uses the
                configured max_size_gb.

        Returns:
            List of image tags that were evicted.
        """
        target_gb = target_size_gb if target_size_gb is not None else self._config.max_size_gb
        evicted: list[str] = []

        # Sort entries by last_used ascending (oldest first = evict first)
        sorted_entries = sorted(self._entries.values(), key=lambda e: e.last_used)

        current_size_gb = sum(e.size_mb for e in self._entries.values()) / 1024.0
        current_count = len(self._entries)

        for entry in sorted_entries:
            # Check if we are within limits
            size_ok = current_size_gb <= target_gb
            count_ok = current_count <= self._config.max_images
            if size_ok and count_ok:
                break

            # Evict the image
            tag = entry.image_tag
            self._remove_docker_image(tag)
            del self._entries[tag]
            evicted.append(tag)

            current_size_gb -= entry.size_mb / 1024.0
            current_count -= 1

        if evicted:
            self._save_metadata()
            logger.info(f"Evicted {len(evicted)} image(s) from cache: {evicted}")

        return evicted

    def _remove_docker_image(self, image_tag: str) -> bool:
        """Remove a Docker image from the local daemon.

        Args:
            image_tag: Docker image tag to remove.

        Returns:
            True if the image was successfully removed, False otherwise.
        """
        client = self._docker_client
        if client is None:
            return False

        try:
            client.images.remove(image_tag, force=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to remove Docker image {image_tag!r}: {e}")
            return False

    def get_stats(self) -> CacheStats:
        """Compute and return current cache statistics.

        Returns:
            CacheStats with totals, hit rate, usage rankings, and savings estimate.
        """
        entries = list(self._entries.values())
        total_images = len(entries)
        total_size_gb = sum(e.size_mb for e in entries) / 1024.0

        total_lookups = self._hits + self._misses
        cache_hit_rate = self._hits / total_lookups if total_lookups > 0 else 0.0

        # Most used (top 5, descending by use_count)
        by_use_desc = sorted(entries, key=lambda e: e.use_count, reverse=True)
        most_used = [e.image_tag for e in by_use_desc[:5]]

        # Least used (bottom 5, ascending by use_count)
        by_use_asc = sorted(entries, key=lambda e: e.use_count)
        least_used = [e.image_tag for e in by_use_asc[:5]]

        # Estimate potential savings from shared layers
        potential_savings_gb = self._estimate_layer_savings()

        return CacheStats(
            total_images=total_images,
            total_size_gb=round(total_size_gb, 3),
            cache_hit_rate=round(cache_hit_rate, 4),
            most_used=most_used,
            least_used=least_used,
            potential_savings_gb=round(potential_savings_gb, 3),
        )

    def _estimate_layer_savings(self) -> float:
        """Estimate disk savings from Docker layer deduplication.

        Calculates the total size of all images minus the deduplicated size
        based on unique layers.

        Returns:
            Estimated savings in gigabytes.
        """
        entries = list(self._entries.values())
        if not entries:
            return 0.0

        # Count total layers vs unique layers
        all_layers: list[str] = []
        unique_layers: set[str] = set()

        for entry in entries:
            all_layers.extend(entry.layers)
            unique_layers.update(entry.layers)

        total_layer_count = len(all_layers)
        unique_layer_count = len(unique_layers)

        if total_layer_count == 0 or unique_layer_count == 0:
            return 0.0

        # Estimate: shared layers reduce total size proportionally
        total_size_gb = sum(e.size_mb for e in entries) / 1024.0
        dedup_ratio = 1.0 - (unique_layer_count / total_layer_count)
        return total_size_gb * dedup_ratio

    def recommend_warmup(self, benchmark_name: str) -> list[str]:
        """Recommend images to pre-pull based on benchmark history.

        Analyzes past benchmark runs to determine which images are commonly
        needed and not currently cached locally.

        Args:
            benchmark_name: Name of the benchmark to prepare for
                (e.g., 'swe-bench-lite').

        Returns:
            List of image tags that should be pre-pulled for optimal performance.
        """
        history = self._benchmark_history.get(benchmark_name, [])
        if not history:
            return []

        # Recommend images that were used before but are not currently cached
        cached_tags = set(self._entries.keys())
        recommendations = [tag for tag in history if tag not in cached_tags]

        return recommendations

    def cleanup_dangling(self) -> int:
        """Remove dangling (untagged) Docker images to reclaim disk space.

        Returns:
            Number of dangling images removed.
        """
        client = self._docker_client
        if client is None:
            logger.warning("Cannot clean up dangling images: Docker is not available")
            return 0

        try:
            result = client.images.prune(filters={"dangling": True})
            deleted = result.get("ImagesDeleted") or []
            count = len(deleted)
            space_reclaimed = result.get("SpaceReclaimed", 0)
            if count > 0:
                logger.info(
                    f"Removed {count} dangling image(s), "
                    f"reclaimed {space_reclaimed / (1024 * 1024):.1f} MB"
                )
            return count
        except Exception as e:
            logger.warning(f"Failed to prune dangling images: {e}")
            return 0
