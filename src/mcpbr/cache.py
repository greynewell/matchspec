"""Task result caching system for mcpbr.

Implements intelligent result caching with content-based hashing,
cache invalidation, TTL management, and size limits.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    key: str
    result: dict[str, Any]
    timestamp: float
    version: str
    task_hash: str
    config_hash: str


@dataclass
class CacheStats:
    """Statistics about cache usage."""

    hits: int = 0
    misses: int = 0
    total_entries: int = 0
    cache_size_bytes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TaskResultCache:
    """Cache for task evaluation results.

    Features:
    - Content-based cache keys using task and config hashing
    - Configurable TTL (time-to-live) for cache entries
    - Cache size limits with LRU eviction
    - Cache statistics tracking
    - Atomic cache operations
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int | None = 86400,  # 24 hours default
        max_size_mb: int = 1000,  # 1GB default
        version: str = "0.3.8",
    ):
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.mcpbr/cache
            ttl_seconds: Time-to-live for cache entries in seconds. None = no expiration
            max_size_mb: Maximum cache size in megabytes
            version: mcpbr version for cache invalidation
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".mcpbr" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.version = version

        self.stats = CacheStats()
        self._load_stats()

    def _compute_task_hash(self, task: dict[str, Any]) -> str:
        """Compute hash of task definition.

        Args:
            task: Task dictionary

        Returns:
            SHA256 hash of task content
        """
        # Extract relevant fields for hashing
        # Exclude metadata that doesn't affect the task itself
        task_content = {
            "instance_id": task.get("instance_id"),
            "problem_statement": task.get("problem_statement"),
            "repo": task.get("repo"),
            "base_commit": task.get("base_commit"),
            "patch": task.get("patch"),
            "test_patch": task.get("test_patch"),
            "FAIL_TO_PASS": task.get("FAIL_TO_PASS"),
            "PASS_TO_PASS": task.get("PASS_TO_PASS"),
        }

        # Sort keys for consistent hashing
        content_str = json.dumps(task_content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _compute_config_hash(self, config: dict[str, Any]) -> str:
        """Compute hash of relevant configuration.

        Args:
            config: Configuration dictionary

        Returns:
            SHA256 hash of config content
        """
        # Only include config fields that affect task execution
        config_content = {
            "model": config.get("model"),
            "provider": config.get("provider"),
            "agent_harness": config.get("agent_harness"),
            "benchmark": config.get("benchmark"),
            "max_iterations": config.get("max_iterations"),
            "timeout_seconds": config.get("timeout_seconds"),
            "agent_prompt": config.get("agent_prompt"),
            "mcp_server": config.get("mcp_server"),
        }

        content_str = json.dumps(config_content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _compute_cache_key(self, task_hash: str, config_hash: str, run_type: str) -> str:
        """Compute final cache key.

        Args:
            task_hash: Hash of task content
            config_hash: Hash of configuration
            run_type: Type of run (mcp or baseline)

        Returns:
            Cache key string
        """
        key_content = f"{self.version}:{task_hash}:{config_hash}:{run_type}"
        return hashlib.sha256(key_content.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache entry.

        Args:
            key: Cache key

        Returns:
            Path to cache file
        """
        # Use first 2 characters for subdirectory to avoid too many files in one dir
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{key}.json"

    def get(
        self,
        task: dict[str, Any],
        config: dict[str, Any],
        run_type: str,
    ) -> dict[str, Any] | None:
        """Get cached result for a task.

        Args:
            task: Task dictionary
            config: Configuration dictionary
            run_type: Type of run (mcp or baseline)

        Returns:
            Cached result or None if not found or expired
        """
        task_hash = self._compute_task_hash(task)
        config_hash = self._compute_config_hash(config)
        key = self._compute_cache_key(task_hash, config_hash, run_type)

        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            self.stats.misses += 1
            self._save_stats()
            return None

        try:
            with open(cache_path) as f:
                entry_data = json.load(f)
                entry = CacheEntry(**entry_data)

            # Check version match
            if entry.version != self.version:
                self.stats.misses += 1
                self._save_stats()
                cache_path.unlink()
                return None

            # Check TTL
            if self.ttl_seconds is not None:
                age = time.time() - entry.timestamp
                if age > self.ttl_seconds:
                    self.stats.misses += 1
                    self._save_stats()
                    cache_path.unlink()
                    return None

            # Cache hit
            self.stats.hits += 1
            self._save_stats()
            return entry.result

        except (json.JSONDecodeError, KeyError, TypeError):
            # Corrupted cache entry
            self.stats.misses += 1
            self._save_stats()
            if cache_path.exists():
                cache_path.unlink()
            return None

    def put(
        self,
        task: dict[str, Any],
        config: dict[str, Any],
        run_type: str,
        result: dict[str, Any],
    ) -> None:
        """Store result in cache.

        Args:
            task: Task dictionary
            config: Configuration dictionary
            run_type: Type of run (mcp or baseline)
            result: Result to cache
        """
        task_hash = self._compute_task_hash(task)
        config_hash = self._compute_config_hash(config)
        key = self._compute_cache_key(task_hash, config_hash, run_type)

        entry = CacheEntry(
            key=key,
            result=result,
            timestamp=time.time(),
            version=self.version,
            task_hash=task_hash,
            config_hash=config_hash,
        )

        cache_path = self._get_cache_path(key)

        # Write atomically using temp file
        temp_path = cache_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(asdict(entry), f)
            temp_path.replace(cache_path)

            # Update stats
            self.stats.total_entries = self._count_entries()
            self.stats.cache_size_bytes = self._calculate_cache_size()
            self._save_stats()

            # Enforce size limit
            self._enforce_size_limit()

        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries removed
        """
        count = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for cache_file in subdir.glob("*.json"):
                    cache_file.unlink()
                    count += 1
                # Remove empty subdirectories
                try:
                    subdir.rmdir()
                except OSError:
                    pass

        # Reset stats
        self.stats.total_entries = 0
        self.stats.cache_size_bytes = 0
        self._save_stats()

        return count

    def _count_entries(self) -> int:
        """Count total cache entries."""
        count = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                count += len(list(subdir.glob("*.json")))
        return count

    def _calculate_cache_size(self) -> int:
        """Calculate total cache size in bytes."""
        total_size = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for cache_file in subdir.glob("*.json"):
                    try:
                        total_size += cache_file.stat().st_size
                    except OSError:
                        pass
        return total_size

    def _enforce_size_limit(self) -> None:
        """Enforce cache size limit using LRU eviction."""
        if self.stats.cache_size_bytes <= self.max_size_bytes:
            return

        # Get all cache entries with their access times
        entries: list[tuple[Path, float]] = []
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for cache_file in subdir.glob("*.json"):
                    try:
                        # Use modification time as proxy for last access
                        mtime = cache_file.stat().st_mtime
                        entries.append((cache_file, mtime))
                    except OSError:
                        pass

        # Sort by access time (oldest first)
        entries.sort(key=lambda x: x[1])

        # Remove oldest entries until under size limit
        for cache_file, _ in entries:
            if self.stats.cache_size_bytes <= self.max_size_bytes:
                break

            try:
                size = cache_file.stat().st_size
                cache_file.unlink()
                self.stats.cache_size_bytes -= size
                self.stats.total_entries -= 1
            except OSError:
                pass

        self._save_stats()

    def _get_stats_path(self) -> Path:
        """Get path to stats file."""
        return self.cache_dir / "stats.json"

    def _load_stats(self) -> None:
        """Load stats from disk."""
        stats_path = self._get_stats_path()
        if stats_path.exists():
            try:
                with open(stats_path) as f:
                    data = json.load(f)
                    self.stats = CacheStats(**data)
            except (json.JSONDecodeError, KeyError, TypeError):
                # Corrupted stats, start fresh
                self.stats = CacheStats()

        # Update counts from actual cache
        self.stats.total_entries = self._count_entries()
        self.stats.cache_size_bytes = self._calculate_cache_size()

    def _save_stats(self) -> None:
        """Save stats to disk."""
        stats_path = self._get_stats_path()
        try:
            with open(stats_path, "w") as f:
                json.dump(asdict(self.stats), f)
        except Exception:
            # Don't fail if we can't save stats
            pass

    def get_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            CacheStats object with current statistics
        """
        # Refresh stats
        self.stats.total_entries = self._count_entries()
        self.stats.cache_size_bytes = self._calculate_cache_size()
        return self.stats

    def invalidate_version(self, version: str) -> int:
        """Invalidate all cache entries for a specific version.

        Args:
            version: Version to invalidate

        Returns:
            Number of entries removed
        """
        count = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for cache_file in subdir.glob("*.json"):
                    try:
                        with open(cache_file) as f:
                            entry_data = json.load(f)
                            if entry_data.get("version") == version:
                                cache_file.unlink()
                                count += 1
                    except (json.JSONDecodeError, KeyError, OSError):
                        pass

        # Update stats
        self.stats.total_entries = self._count_entries()
        self.stats.cache_size_bytes = self._calculate_cache_size()
        self._save_stats()

        return count


def get_default_cache() -> TaskResultCache:
    """Get default cache instance.

    Returns:
        TaskResultCache with default settings
    """
    return TaskResultCache()
