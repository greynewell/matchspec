"""Tests for the result caching system."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mcpbr.cache import CachedResult, ResultCache
from mcpbr.config import HarnessConfig, MCPServerConfig


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def sample_config() -> HarnessConfig:
    """Create a sample configuration for testing."""
    return HarnessConfig(
        mcp_server=MCPServerConfig(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
        ),
        model="claude-sonnet-4-5-20250929",
        provider="anthropic",
        benchmark="swe-bench",
    )


@pytest.fixture
def sample_task() -> dict:
    """Create a sample task for testing."""
    return {
        "instance_id": "test-task-1",
        "problem_statement": "Fix the bug in the code",
        "repo": "test/repo",
    }


@pytest.fixture
def sample_result() -> dict:
    """Create a sample result for testing."""
    return {
        "resolved": True,
        "patch_applied": True,
        "tokens": {"input": 1000, "output": 500},
        "iterations": 5,
        "tool_calls": 10,
        "cost": 0.05,
    }


def test_cache_initialization(temp_cache_dir: Path):
    """Test cache initialization."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    assert cache.enabled
    assert cache.cache_dir == temp_cache_dir
    assert cache.cache_dir.exists()


def test_cache_disabled():
    """Test that disabled cache is a no-op."""
    cache = ResultCache(enabled=False)
    assert not cache.enabled

    # All operations should be no-ops
    task = {"instance_id": "test"}
    config = HarnessConfig(
        mcp_server=MCPServerConfig(command="test", args=[]),
        model="test",
        provider="anthropic",
        benchmark="swe-bench",
    )
    result = {"resolved": True}

    # Get should return None
    assert cache.get(task, config, "test prompt", is_mcp=True) is None

    # Put should not raise an error
    cache.put(task, config, "test prompt", is_mcp=True, result=result)

    # Stats should show empty cache
    stats = cache.get_stats()
    assert stats.total_entries == 0


def test_cache_put_and_get(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
    sample_result: dict,
):
    """Test storing and retrieving results from cache."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue: {problem_statement}"

    # Initially cache miss
    assert cache.get(sample_task, sample_config, prompt, is_mcp=True) is None

    # Store result
    cache.put(sample_task, sample_config, prompt, is_mcp=True, result=sample_result)

    # Now should be a cache hit
    cached = cache.get(sample_task, sample_config, prompt, is_mcp=True)
    assert cached is not None
    assert cached["resolved"] == sample_result["resolved"]
    assert cached["cost"] == sample_result["cost"]


def test_cache_key_uniqueness(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
):
    """Test that cache keys are unique for different configurations."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"
    result1 = {"resolved": True}
    result2 = {"resolved": False}

    # Store MCP result
    cache.put(sample_task, sample_config, prompt, is_mcp=True, result=result1)

    # Store baseline result (should have different key)
    cache.put(sample_task, sample_config, prompt, is_mcp=False, result=result2)

    # Both should be retrievable separately
    mcp_cached = cache.get(sample_task, sample_config, prompt, is_mcp=True)
    baseline_cached = cache.get(sample_task, sample_config, prompt, is_mcp=False)

    assert mcp_cached["resolved"]
    assert not baseline_cached["resolved"]


def test_cache_key_depends_on_config(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
):
    """Test that different configs produce different cache keys."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"
    result1 = {"resolved": True}
    result2 = {"resolved": False}

    # Store with first config
    cache.put(sample_task, sample_config, prompt, is_mcp=True, result=result1)

    # Modify config (different model)
    config2 = sample_config.model_copy()
    config2.model = "claude-opus-4-5-20251101"

    # Store with second config
    cache.put(sample_task, config2, prompt, is_mcp=True, result=result2)

    # Should get different results
    cached1 = cache.get(sample_task, sample_config, prompt, is_mcp=True)
    cached2 = cache.get(sample_task, config2, prompt, is_mcp=True)

    assert cached1["resolved"]
    assert not cached2["resolved"]


def test_cache_key_depends_on_prompt(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
):
    """Test that different prompts produce different cache keys."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    result1 = {"resolved": True}
    result2 = {"resolved": False}

    # Store with first prompt
    cache.put(sample_task, sample_config, "Prompt 1", is_mcp=True, result=result1)

    # Store with second prompt
    cache.put(sample_task, sample_config, "Prompt 2", is_mcp=True, result=result2)

    # Should get different results
    cached1 = cache.get(sample_task, sample_config, "Prompt 1", is_mcp=True)
    cached2 = cache.get(sample_task, sample_config, "Prompt 2", is_mcp=True)

    assert cached1["resolved"]
    assert not cached2["resolved"]


def test_cache_key_depends_on_task(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
):
    """Test that different tasks produce different cache keys."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"
    result1 = {"resolved": True}
    result2 = {"resolved": False}

    task1 = {"instance_id": "task-1", "problem_statement": "Bug 1"}
    task2 = {"instance_id": "task-2", "problem_statement": "Bug 2"}

    # Store results for different tasks
    cache.put(task1, sample_config, prompt, is_mcp=True, result=result1)
    cache.put(task2, sample_config, prompt, is_mcp=True, result=result2)

    # Should get different results
    cached1 = cache.get(task1, sample_config, prompt, is_mcp=True)
    cached2 = cache.get(task2, sample_config, prompt, is_mcp=True)

    assert cached1["resolved"]
    assert not cached2["resolved"]


def test_cache_invalidate(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
    sample_result: dict,
):
    """Test cache invalidation."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Store result
    cache.put(sample_task, sample_config, prompt, is_mcp=True, result=sample_result)

    # Verify it's cached
    assert cache.get(sample_task, sample_config, prompt, is_mcp=True) is not None

    # Invalidate
    removed = cache.invalidate(sample_task, sample_config, prompt, is_mcp=True)
    assert removed

    # Should be a cache miss now
    assert cache.get(sample_task, sample_config, prompt, is_mcp=True) is None

    # Invalidating again should return False
    removed = cache.invalidate(sample_task, sample_config, prompt, is_mcp=True)
    assert not removed


def test_cache_clear(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
):
    """Test clearing all cache entries."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Store multiple results
    for i in range(5):
        task = {"instance_id": f"task-{i}", "problem_statement": f"Bug {i}"}
        result = {"resolved": i % 2 == 0}
        cache.put(task, sample_config, prompt, is_mcp=True, result=result)

    # Verify they're all cached
    stats = cache.get_stats()
    assert stats.total_entries == 5

    # Clear cache
    removed = cache.clear()
    assert removed == 5

    # Cache should be empty
    stats = cache.get_stats()
    assert stats.total_entries == 0


def test_cache_stats(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
):
    """Test cache statistics."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Empty cache
    stats = cache.get_stats()
    assert stats.total_entries == 0
    assert stats.total_size_bytes == 0
    assert stats.oldest_entry is None
    assert stats.newest_entry is None

    # Add some entries
    for i in range(3):
        task = {"instance_id": f"task-{i}", "problem_statement": f"Bug {i}"}
        result = {"resolved": True}
        cache.put(task, sample_config, prompt, is_mcp=True, result=result)

    # Check stats
    stats = cache.get_stats()
    assert stats.total_entries == 3
    assert stats.total_size_bytes > 0
    assert stats.oldest_entry is not None
    assert stats.newest_entry is not None
    assert stats.oldest_entry <= stats.newest_entry


def test_cache_prune_by_age(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
):
    """Test pruning cache entries by age."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Create some cache entries with different timestamps
    for i in range(3):
        task = {"instance_id": f"task-{i}", "problem_statement": f"Bug {i}"}
        result = {"resolved": True}
        cache.put(task, sample_config, prompt, is_mcp=True, result=result)

    # Manually modify timestamps of cache files to simulate old entries
    cache_files = list(temp_cache_dir.rglob("*.json"))
    assert len(cache_files) == 3

    # Make first file "old" by modifying its timestamp in the JSON
    with open(cache_files[0]) as f:
        data = json.load(f)
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=31)
    data["timestamp"] = old_timestamp.isoformat()
    with open(cache_files[0], "w") as f:
        json.dump(data, f)

    # Prune entries older than 30 days
    removed = cache.prune(max_age_days=30)
    assert removed == 1

    # Should have 2 entries left
    stats = cache.get_stats()
    assert stats.total_entries == 2


def test_cache_prune_by_size(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
):
    """Test pruning cache entries by size."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Add several entries
    for i in range(5):
        task = {"instance_id": f"task-{i}", "problem_statement": f"Bug {i}"}
        result = {"resolved": True, "large_data": "x" * 1000}  # Make entries larger
        cache.put(task, sample_config, prompt, is_mcp=True, result=result)

    # Check current size
    stats = cache.get_stats()
    initial_size_mb = stats.total_size_bytes / (1024 * 1024)

    # Prune to very small size (will remove most entries)
    removed = cache.prune(max_size_mb=0.001)
    assert removed > 0

    # Should have fewer entries
    stats = cache.get_stats()
    final_size_mb = stats.total_size_bytes / (1024 * 1024)
    assert final_size_mb < initial_size_mb


def test_cached_result_serialization():
    """Test CachedResult serialization and deserialization."""
    cached = CachedResult(
        instance_id="test-task",
        cache_key="abc123",
        result={"resolved": True, "cost": 0.05},
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        config_hash="def456",
    )

    # Convert to dict
    data = cached.to_dict()
    assert data["instance_id"] == "test-task"
    assert data["cache_key"] == "abc123"
    assert data["result"]["resolved"]
    assert "timestamp" in data

    # Convert back from dict
    restored = CachedResult.from_dict(data)
    assert restored.instance_id == cached.instance_id
    assert restored.cache_key == cached.cache_key
    assert restored.result == cached.result
    assert restored.timestamp == cached.timestamp
    assert restored.config_hash == cached.config_hash


def test_cache_corrupted_file_handling(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
    sample_task: dict,
):
    """Test that corrupted cache files are handled gracefully."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"
    result = {"resolved": True}

    # Store a result
    cache.put(sample_task, sample_config, prompt, is_mcp=True, result=result)

    # Corrupt the cache file
    cache_files = list(temp_cache_dir.rglob("*.json"))
    assert len(cache_files) == 1
    with open(cache_files[0], "w") as f:
        f.write("corrupted json {{{")

    # Get should return None and remove corrupted file
    cached = cache.get(sample_task, sample_config, prompt, is_mcp=True)
    assert cached is None
    assert not cache_files[0].exists()


def test_cache_subdirectory_structure(
    temp_cache_dir: Path,
    sample_config: HarnessConfig,
):
    """Test that cache uses subdirectories to avoid too many files."""
    cache = ResultCache(cache_dir=temp_cache_dir, enabled=True)
    prompt = "Fix the issue"

    # Add many entries
    for i in range(10):
        task = {"instance_id": f"task-{i}", "problem_statement": f"Bug {i}"}
        result = {"resolved": True}
        cache.put(task, sample_config, prompt, is_mcp=True, result=result)

    # Check that subdirectories were created
    subdirs = [d for d in temp_cache_dir.iterdir() if d.is_dir()]
    assert len(subdirs) > 0

    # Each subdirectory should contain cache files
    for subdir in subdirs:
        files = list(subdir.glob("*.json"))
        assert len(files) > 0


def test_cache_format_size():
    """Test size formatting in CacheStats."""
    from mcpbr.cache import CacheStats

    stats = CacheStats(
        total_entries=10,
        total_size_bytes=1024,
        oldest_entry=None,
        newest_entry=None,
        cache_dir=Path("/tmp/cache"),
    )
    assert "KB" in stats.format_size()

    stats.total_size_bytes = 1024 * 1024
    assert "MB" in stats.format_size()

    stats.total_size_bytes = 1024 * 1024 * 1024
    assert "GB" in stats.format_size()
