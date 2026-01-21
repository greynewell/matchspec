"""Result caching system for benchmark evaluations.

This module provides a content-based caching mechanism to avoid re-running
identical evaluations. Cache keys are computed from task content, configuration,
and prompt to ensure cache hits only occur for truly identical evaluations.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import HarnessConfig


@dataclass
class CacheStats:
    """Statistics about cache usage."""

    total_entries: int
    total_size_bytes: int
    oldest_entry: datetime | None
    newest_entry: datetime | None
    cache_dir: Path

    def format_size(self) -> str:
        """Format cache size in human-readable format."""
        size = self.total_size_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


@dataclass
class CachedResult:
    """A cached evaluation result."""

    instance_id: str
    cache_key: str
    result: dict[str, Any]
    timestamp: datetime
    config_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "instance_id": self.instance_id,
            "cache_key": self.cache_key,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CachedResult":
        """Create from dictionary loaded from JSON."""
        return cls(
            instance_id=data["instance_id"],
            cache_key=data["cache_key"],
            result=data["result"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            config_hash=data["config_hash"],
        )


class ResultCache:
    """File-based cache for benchmark evaluation results.

    Cache keys are computed from:
    - Task instance_id and problem statement
    - Model and provider configuration
    - Agent prompt template
    - Benchmark type
    - MCP server configuration (command, args)

    This ensures cache hits only occur when evaluating the exact same task
    with the exact same configuration.
    """

    def __init__(self, cache_dir: Path | None = None, enabled: bool = True):
        """Initialize result cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.cache/mcpbr
            enabled: Whether caching is enabled. If False, all operations are no-ops.
        """
        self.enabled = enabled
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "mcpbr"
        self.cache_dir = cache_dir

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_cache_key(
        self,
        task: dict[str, Any],
        config: HarnessConfig,
        prompt: str,
        is_mcp: bool,
    ) -> str:
        """Compute cache key from task and configuration.

        Args:
            task: Task dictionary with instance_id and problem statement
            config: Harness configuration
            prompt: Agent prompt template
            is_mcp: Whether this is for MCP agent or baseline

        Returns:
            SHA256 hash as cache key
        """
        # Build cache key components
        key_parts = {
            "instance_id": task.get("instance_id", ""),
            "problem_statement": task.get("problem_statement", ""),
            "model": config.model,
            "provider": config.provider,
            "benchmark": config.benchmark,
            "prompt": prompt,
            "max_iterations": config.max_iterations,
            "timeout_seconds": config.timeout_seconds,
            "is_mcp": is_mcp,
        }

        # Add MCP server config if this is MCP agent
        if is_mcp:
            key_parts["mcp_server"] = {
                "command": config.mcp_server.command,
                "args": config.mcp_server.args,
                # Don't include env vars in cache key as they may contain secrets
                # and vary between runs without affecting results
            }

        # For CyberGym, include level in cache key
        if config.benchmark == "cybergym":
            key_parts["cybergym_level"] = config.cybergym_level

        # Serialize to JSON with sorted keys for consistent hashing
        key_json = json.dumps(key_parts, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get file path for a cache key.

        Args:
            cache_key: SHA256 hash

        Returns:
            Path to cache file
        """
        # Use first 2 chars for subdirectory to avoid too many files in one dir
        subdir = cache_key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(parents=True, exist_ok=True)
        return cache_subdir / f"{cache_key}.json"

    def get(
        self,
        task: dict[str, Any],
        config: HarnessConfig,
        prompt: str,
        is_mcp: bool,
    ) -> dict[str, Any] | None:
        """Get cached result if available.

        Args:
            task: Task dictionary
            config: Harness configuration
            prompt: Agent prompt template
            is_mcp: Whether this is for MCP agent or baseline

        Returns:
            Cached result dictionary or None if not cached
        """
        if not self.enabled:
            return None

        cache_key = self._compute_cache_key(task, config, prompt, is_mcp)
        cache_file = self._get_cache_file_path(cache_key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cached = CachedResult.from_dict(json.load(f))

            # Verify instance_id matches (sanity check)
            if cached.instance_id != task.get("instance_id"):
                # Cache corruption, remove the file
                cache_file.unlink()
                return None

            return cached.result

        except (json.JSONDecodeError, KeyError, ValueError):
            # Cache file is corrupted, remove it
            cache_file.unlink()
            return None

    def put(
        self,
        task: dict[str, Any],
        config: HarnessConfig,
        prompt: str,
        is_mcp: bool,
        result: dict[str, Any],
    ) -> None:
        """Store result in cache.

        Args:
            task: Task dictionary
            config: Harness configuration
            prompt: Agent prompt template
            is_mcp: Whether this is for MCP agent or baseline
            result: Result dictionary to cache
        """
        if not self.enabled:
            return

        cache_key = self._compute_cache_key(task, config, prompt, is_mcp)
        config_hash = self._compute_config_hash(config)

        cached = CachedResult(
            instance_id=task.get("instance_id", "unknown"),
            cache_key=cache_key,
            result=result,
            timestamp=datetime.now(timezone.utc),
            config_hash=config_hash,
        )

        cache_file = self._get_cache_file_path(cache_key)
        with open(cache_file, "w") as f:
            json.dump(cached.to_dict(), f, indent=2)

    def _compute_config_hash(self, config: HarnessConfig) -> str:
        """Compute hash of relevant config fields for metadata.

        Args:
            config: Harness configuration

        Returns:
            SHA256 hash of configuration
        """
        config_dict = {
            "model": config.model,
            "provider": config.provider,
            "benchmark": config.benchmark,
            "max_iterations": config.max_iterations,
        }
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]

    def invalidate(
        self,
        task: dict[str, Any],
        config: HarnessConfig,
        prompt: str,
        is_mcp: bool,
    ) -> bool:
        """Invalidate (remove) cached result for a specific task.

        Args:
            task: Task dictionary
            config: Harness configuration
            prompt: Agent prompt template
            is_mcp: Whether this is for MCP agent or baseline

        Returns:
            True if cache entry was removed, False if it didn't exist
        """
        if not self.enabled:
            return False

        cache_key = self._compute_cache_key(task, config, prompt, is_mcp)
        cache_file = self._get_cache_file_path(cache_key)

        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of cache files removed
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.rglob("*.json"):
            cache_file.unlink()
            count += 1

        # Remove empty subdirectories
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and not list(subdir.iterdir()):
                subdir.rmdir()

        return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with information about cache usage
        """
        if not self.enabled or not self.cache_dir.exists():
            return CacheStats(
                total_entries=0,
                total_size_bytes=0,
                oldest_entry=None,
                newest_entry=None,
                cache_dir=self.cache_dir,
            )

        cache_files = list(self.cache_dir.rglob("*.json"))
        total_entries = len(cache_files)
        total_size_bytes = sum(f.stat().st_size for f in cache_files)

        oldest_entry = None
        newest_entry = None

        for cache_file in cache_files:
            try:
                with open(cache_file) as f:
                    cached = CachedResult.from_dict(json.load(f))
                    if oldest_entry is None or cached.timestamp < oldest_entry:
                        oldest_entry = cached.timestamp
                    if newest_entry is None or cached.timestamp > newest_entry:
                        newest_entry = cached.timestamp
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip corrupted cache files
                continue

        return CacheStats(
            total_entries=total_entries,
            total_size_bytes=total_size_bytes,
            oldest_entry=oldest_entry,
            newest_entry=newest_entry,
            cache_dir=self.cache_dir,
        )

    def prune(self, max_age_days: int | None = None, max_size_mb: int | None = None) -> int:
        """Remove old cache entries based on age or size limits.

        Args:
            max_age_days: Remove entries older than this many days
            max_size_mb: Remove oldest entries if cache exceeds this size

        Returns:
            Number of cache files removed
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        cache_files = list(self.cache_dir.rglob("*.json"))
        removed_count = 0

        # Remove by age
        if max_age_days is not None:
            now = datetime.now(timezone.utc)
            for cache_file in cache_files:
                try:
                    with open(cache_file) as f:
                        cached = CachedResult.from_dict(json.load(f))
                    age_days = (now - cached.timestamp).days
                    if age_days > max_age_days:
                        cache_file.unlink()
                        removed_count += 1
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Remove corrupted files
                    cache_file.unlink()
                    removed_count += 1

        # Remove by size (keep newest files)
        if max_size_mb is not None:
            cache_files = list(self.cache_dir.rglob("*.json"))
            current_size_mb = sum(f.stat().st_size for f in cache_files) / (1024 * 1024)

            if current_size_mb > max_size_mb:
                # Sort by modification time (oldest first)
                sorted_files = sorted(cache_files, key=lambda f: f.stat().st_mtime)

                for cache_file in sorted_files:
                    if current_size_mb <= max_size_mb:
                        break
                    file_size_mb = cache_file.stat().st_size / (1024 * 1024)
                    cache_file.unlink()
                    current_size_mb -= file_size_mb
                    removed_count += 1

        # Remove empty subdirectories
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir() and not list(subdir.iterdir()):
                subdir.rmdir()

        return removed_count


def get_default_cache() -> ResultCache:
    """Get default cache instance.

    Returns:
        ResultCache with default settings
    """
    return ResultCache()
