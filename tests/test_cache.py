"""Tests for task result caching."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from mcpbr.cache import CacheEntry, CacheStats, TaskResultCache, get_default_cache


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_creation(self) -> None:
        """Test creating a cache entry."""
        entry = CacheEntry(
            key="test_key",
            result={"resolved": True, "cost": 0.5},
            timestamp=time.time(),
            version="0.3.8",
            task_hash="abc123",
            config_hash="def456",
        )
        assert entry.key == "test_key"
        assert entry.result["resolved"] is True
        assert entry.version == "0.3.8"


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_hit_rate_calculation(self) -> None:
        """Test hit rate calculation."""
        stats = CacheStats(hits=7, misses=3)
        assert stats.hit_rate == 0.7

    def test_hit_rate_zero_total(self) -> None:
        """Test hit rate when no hits or misses."""
        stats = CacheStats(hits=0, misses=0)
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self) -> None:
        """Test hit rate with all hits."""
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0


class TestTaskResultCache:
    """Tests for TaskResultCache."""

    @pytest.fixture
    def temp_cache_dir(self) -> Path:
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache(self, temp_cache_dir: Path) -> TaskResultCache:
        """Create a cache instance with temporary directory."""
        return TaskResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=3600,
            max_size_mb=10,
            version="0.3.8",
        )

    def test_initialization(self, temp_cache_dir: Path) -> None:
        """Test cache initialization."""
        cache = TaskResultCache(cache_dir=temp_cache_dir)
        assert cache.cache_dir == temp_cache_dir
        assert cache.cache_dir.exists()
        assert cache.ttl_seconds == 86400  # default
        assert cache.version == "0.3.8"

    def test_compute_task_hash(self, cache: TaskResultCache) -> None:
        """Test task hashing."""
        task1 = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "test/repo",
            "base_commit": "abc123",
        }
        task2 = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "test/repo",
            "base_commit": "abc123",
            "extra_field": "ignored",  # Should be ignored
        }
        task3 = {
            "instance_id": "test-2",
            "problem_statement": "Fix bug",
            "repo": "test/repo",
            "base_commit": "abc123",
        }

        hash1 = cache._compute_task_hash(task1)
        hash2 = cache._compute_task_hash(task2)
        hash3 = cache._compute_task_hash(task3)

        # Same relevant content = same hash
        assert hash1 == hash2
        # Different task = different hash
        assert hash1 != hash3

    def test_compute_config_hash(self, cache: TaskResultCache) -> None:
        """Test config hashing."""
        config1 = {
            "model": "claude-sonnet-4-5",
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "max_iterations": 10,
        }
        config2 = {
            "model": "claude-sonnet-4-5",
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "max_iterations": 10,
            "sample_size": 5,  # Should be ignored
        }
        config3 = {
            "model": "claude-opus-4-5",  # Different model
            "provider": "anthropic",
            "agent_harness": "claude-code",
            "max_iterations": 10,
        }

        hash1 = cache._compute_config_hash(config1)
        hash2 = cache._compute_config_hash(config2)
        hash3 = cache._compute_config_hash(config3)

        # Same relevant config = same hash
        assert hash1 == hash2
        # Different model = different hash
        assert hash1 != hash3

    def test_put_and_get(self, cache: TaskResultCache) -> None:
        """Test storing and retrieving cache entries."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True, "cost": 0.5, "tokens": {"input": 100, "output": 50}}

        # Store result
        cache.put(task, config, "mcp", result)

        # Retrieve result
        cached = cache.get(task, config, "mcp")
        assert cached is not None
        assert cached["resolved"] is True
        assert cached["cost"] == 0.5

        # Stats should show 1 hit
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

    def test_get_miss(self, cache: TaskResultCache) -> None:
        """Test cache miss."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}

        # Try to get non-existent entry
        cached = cache.get(task, config, "mcp")
        assert cached is None

        # Stats should show 1 miss
        assert cache.stats.hits == 0
        assert cache.stats.misses == 1

    def test_cache_different_run_types(self, cache: TaskResultCache) -> None:
        """Test caching different run types (mcp vs baseline)."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}

        mcp_result = {"resolved": True, "cost": 0.5}
        baseline_result = {"resolved": False, "cost": 0.3}

        # Store both
        cache.put(task, config, "mcp", mcp_result)
        cache.put(task, config, "baseline", baseline_result)

        # Retrieve both
        cached_mcp = cache.get(task, config, "mcp")
        cached_baseline = cache.get(task, config, "baseline")

        assert cached_mcp["resolved"] is True
        assert cached_baseline["resolved"] is False

    def test_cache_expiration(self, temp_cache_dir: Path) -> None:
        """Test TTL-based cache expiration."""
        # Create cache with very short TTL
        cache = TaskResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=1,
            version="0.3.8",
        )

        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store result
        cache.put(task, config, "mcp", result)

        # Should be cached immediately
        cached = cache.get(task, config, "mcp")
        assert cached is not None

        # Wait for TTL to expire
        time.sleep(1.5)

        # Should be expired
        cached = cache.get(task, config, "mcp")
        assert cached is None

    def test_cache_no_ttl(self, temp_cache_dir: Path) -> None:
        """Test cache with no expiration."""
        cache = TaskResultCache(
            cache_dir=temp_cache_dir,
            ttl_seconds=None,  # No expiration
            version="0.3.8",
        )

        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store result
        cache.put(task, config, "mcp", result)

        # Wait a bit (entry would expire with TTL)
        time.sleep(0.5)

        # Should still be cached
        cached = cache.get(task, config, "mcp")
        assert cached is not None

    def test_version_invalidation(self, cache: TaskResultCache) -> None:
        """Test version-based cache invalidation."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store with current version
        cache.put(task, config, "mcp", result)

        # Should be cached
        cached = cache.get(task, config, "mcp")
        assert cached is not None

        # Create new cache with different version
        new_cache = TaskResultCache(
            cache_dir=cache.cache_dir,
            version="0.4.0",  # Different version
        )

        # Should not find cached entry (version mismatch)
        cached = new_cache.get(task, config, "mcp")
        assert cached is None

    def test_clear_cache(self, cache: TaskResultCache) -> None:
        """Test clearing all cache entries."""
        task1 = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        task2 = {"instance_id": "test-2", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store multiple entries
        cache.put(task1, config, "mcp", result)
        cache.put(task2, config, "mcp", result)

        # Stats should show 2 entries
        stats = cache.get_stats()
        assert stats.total_entries == 2

        # Clear cache
        count = cache.clear()
        assert count == 2

        # Stats should show 0 entries
        stats = cache.get_stats()
        assert stats.total_entries == 0

    def test_cache_size_management(self, temp_cache_dir: Path) -> None:
        """Test cache size limit enforcement."""
        # Create cache with very small size limit (1 KB)
        cache = TaskResultCache(
            cache_dir=temp_cache_dir,
            max_size_mb=0.001,  # 1 KB
            version="0.3.8",
        )

        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        # Create large result (> 1 KB)
        large_result = {"resolved": True, "data": "x" * 2000}

        # Store multiple entries to exceed size limit
        for i in range(5):
            task = {"instance_id": f"test-{i}", "problem_statement": "Fix bug"}
            cache.put(task, config, "mcp", large_result)

        # Cache should have evicted some entries
        stats = cache.get_stats()
        assert stats.total_entries < 5
        assert stats.cache_size_bytes <= cache.max_size_bytes

    def test_corrupted_cache_entry(self, cache: TaskResultCache) -> None:
        """Test handling of corrupted cache entries."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store valid entry
        cache.put(task, config, "mcp", result)

        # Get cache file path
        task_hash = cache._compute_task_hash(task)
        config_hash = cache._compute_config_hash(config)
        key = cache._compute_cache_key(task_hash, config_hash, "mcp")
        cache_path = cache._get_cache_path(key)

        # Corrupt the file
        cache_path.write_text("invalid json{")

        # Should handle corruption gracefully
        cached = cache.get(task, config, "mcp")
        assert cached is None

        # File should be removed
        assert not cache_path.exists()

    def test_get_default_cache(self) -> None:
        """Test getting default cache instance."""
        cache = get_default_cache()
        assert isinstance(cache, TaskResultCache)
        assert cache.cache_dir == Path.home() / ".mcpbr" / "cache"

    def test_invalidate_version(self, cache: TaskResultCache) -> None:
        """Test invalidating cache entries by version."""
        task1 = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        task2 = {"instance_id": "test-2", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store entries
        cache.put(task1, config, "mcp", result)
        cache.put(task2, config, "mcp", result)

        # Invalidate current version
        count = cache.invalidate_version("0.3.8")
        assert count == 2

        # Entries should be gone
        stats = cache.get_stats()
        assert stats.total_entries == 0

    def test_cache_stats_persistence(self, cache: TaskResultCache) -> None:
        """Test that cache stats are persisted across instances."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        # Store entry and get it (1 miss, 1 hit)
        cache.put(task, config, "mcp", result)
        cache.get(task, config, "mcp")

        # Create new cache instance with same directory
        new_cache = TaskResultCache(
            cache_dir=cache.cache_dir,
            version="0.3.8",
        )

        # Stats should be loaded
        stats = new_cache.get_stats()
        assert stats.hits >= 1
        assert stats.total_entries == 1

    def test_cache_subdirectory_structure(self, cache: TaskResultCache) -> None:
        """Test that cache uses subdirectories to avoid too many files."""
        task = {"instance_id": "test-1", "problem_statement": "Fix bug"}
        config = {"model": "claude-sonnet-4-5", "provider": "anthropic"}
        result = {"resolved": True}

        cache.put(task, config, "mcp", result)

        # Should create subdirectory based on first 2 chars of key
        task_hash = cache._compute_task_hash(task)
        config_hash = cache._compute_config_hash(config)
        key = cache._compute_cache_key(task_hash, config_hash, "mcp")

        subdir = cache.cache_dir / key[:2]
        assert subdir.exists()
        assert subdir.is_dir()

        # Cache file should be in subdirectory
        cache_file = subdir / f"{key}.json"
        assert cache_file.exists()

    def test_task_hash_stability(self, cache: TaskResultCache) -> None:
        """Test that task hashes are stable across runs."""
        task = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "test/repo",
            "base_commit": "abc123",
        }

        hash1 = cache._compute_task_hash(task)
        hash2 = cache._compute_task_hash(task)

        # Same task should produce same hash
        assert hash1 == hash2

        # Hash should be deterministic
        expected_input = {
            "instance_id": "test-1",
            "problem_statement": "Fix bug",
            "repo": "test/repo",
            "base_commit": "abc123",
            "patch": None,
            "test_patch": None,
            "FAIL_TO_PASS": None,
            "PASS_TO_PASS": None,
        }
        content_str = json.dumps(expected_input, sort_keys=True)
        import hashlib

        expected_hash = hashlib.sha256(content_str.encode()).hexdigest()
        assert hash1 == expected_hash
