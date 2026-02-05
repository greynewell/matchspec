"""Tests for Docker image cache management."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.docker_cache import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    ImageCache,
    _is_mcpbr_image,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "docker_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def cache_config(temp_cache_dir: Path) -> CacheConfig:
    """Create a cache config pointing at a temp directory."""
    return CacheConfig(
        max_size_gb=10.0,
        max_images=5,
        eviction_strategy="lru",
        cache_dir=temp_cache_dir,
    )


@pytest.fixture
def sample_entry() -> CacheEntry:
    """Create a sample cache entry."""
    now = datetime.now(timezone.utc)
    return CacheEntry(
        image_tag="ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907",
        size_mb=1500.0,
        last_used=now,
        use_count=3,
        layers=["sha256:aaa", "sha256:bbb", "sha256:ccc"],
        created=now - timedelta(days=2),
    )


@pytest.fixture
def mock_docker_client():
    """Provide a mock Docker client via patch."""
    with patch("mcpbr.docker_cache.docker") as mock_docker_module:
        mock_client = MagicMock()
        mock_docker_module.from_env.return_value = mock_client
        yield mock_client


@pytest.fixture
def image_cache(cache_config: CacheConfig, mock_docker_client) -> ImageCache:
    """Create an ImageCache instance backed by temp dir and mock Docker."""
    return ImageCache(config=cache_config)


# ---------------------------------------------------------------------------
# CacheEntry tests
# ---------------------------------------------------------------------------


class TestCacheEntry:
    """Tests for the CacheEntry dataclass."""

    def test_to_dict(self, sample_entry: CacheEntry):
        """Test serialization to dictionary."""
        data = sample_entry.to_dict()
        assert data["image_tag"] == sample_entry.image_tag
        assert data["size_mb"] == sample_entry.size_mb
        assert data["use_count"] == sample_entry.use_count
        assert isinstance(data["last_used"], str)
        assert isinstance(data["created"], str)
        assert data["layers"] == sample_entry.layers

    def test_from_dict(self, sample_entry: CacheEntry):
        """Test deserialization from dictionary."""
        data = sample_entry.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.image_tag == sample_entry.image_tag
        assert restored.size_mb == sample_entry.size_mb
        assert restored.use_count == sample_entry.use_count
        assert restored.layers == sample_entry.layers

    def test_from_dict_missing_layers(self):
        """Test deserialization when layers field is absent."""
        data = {
            "image_tag": "test:latest",
            "size_mb": 100.0,
            "last_used": datetime.now(timezone.utc).isoformat(),
            "use_count": 0,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        entry = CacheEntry.from_dict(data)
        assert entry.layers == []

    def test_roundtrip_preserves_timestamps(self, sample_entry: CacheEntry):
        """Test that serialization roundtrip preserves datetime values."""
        data = sample_entry.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.last_used == sample_entry.last_used
        assert restored.created == sample_entry.created


# ---------------------------------------------------------------------------
# CacheConfig tests
# ---------------------------------------------------------------------------


class TestCacheConfig:
    """Tests for the CacheConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CacheConfig()
        assert config.max_size_gb == 50.0
        assert config.max_images == 100
        assert config.eviction_strategy == "lru"
        assert config.cache_dir == Path.home() / ".cache" / "mcpbr" / "docker"

    def test_custom_values(self, temp_cache_dir: Path):
        """Test custom configuration values."""
        config = CacheConfig(
            max_size_gb=25.0,
            max_images=50,
            eviction_strategy="lru",
            cache_dir=temp_cache_dir,
        )
        assert config.max_size_gb == 25.0
        assert config.max_images == 50

    def test_invalid_max_size(self):
        """Test that non-positive max_size_gb raises ValueError."""
        with pytest.raises(ValueError, match="max_size_gb must be positive"):
            CacheConfig(max_size_gb=0)

    def test_invalid_max_images(self):
        """Test that non-positive max_images raises ValueError."""
        with pytest.raises(ValueError, match="max_images must be positive"):
            CacheConfig(max_images=-1)

    def test_invalid_eviction_strategy(self):
        """Test that unsupported eviction strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported eviction strategy"):
            CacheConfig(eviction_strategy="fifo")


# ---------------------------------------------------------------------------
# CacheStats tests
# ---------------------------------------------------------------------------


class TestCacheStats:
    """Tests for the CacheStats dataclass."""

    def test_empty_stats(self):
        """Test stats for an empty cache."""
        stats = CacheStats(
            total_images=0,
            total_size_gb=0.0,
            cache_hit_rate=0.0,
            most_used=[],
            least_used=[],
            potential_savings_gb=0.0,
        )
        assert stats.total_images == 0
        assert stats.total_size_gb == 0.0
        assert stats.cache_hit_rate == 0.0

    def test_populated_stats(self):
        """Test stats with data."""
        stats = CacheStats(
            total_images=10,
            total_size_gb=5.5,
            cache_hit_rate=0.85,
            most_used=["img:a", "img:b"],
            least_used=["img:c", "img:d"],
            potential_savings_gb=1.2,
        )
        assert stats.total_images == 10
        assert stats.total_size_gb == 5.5
        assert stats.cache_hit_rate == 0.85
        assert len(stats.most_used) == 2
        assert len(stats.least_used) == 2
        assert stats.potential_savings_gb == 1.2


# ---------------------------------------------------------------------------
# _is_mcpbr_image helper tests
# ---------------------------------------------------------------------------


class TestIsMcpbrImage:
    """Tests for the _is_mcpbr_image helper."""

    def test_mcpbr_prefix(self):
        """Test detection of mcpbr-prefixed images."""
        assert _is_mcpbr_image("mcpbr-env") is True
        assert _is_mcpbr_image("mcpbr-session-abc123") is True

    def test_swebench_prefix(self):
        """Test detection of SWE-bench images."""
        assert (
            _is_mcpbr_image("ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907")
            is True
        )

    def test_swebench_generic(self):
        """Test detection of images containing 'swe-bench'."""
        assert _is_mcpbr_image("custom-swe-bench-image:latest") is True

    def test_unrelated_image(self):
        """Test that unrelated images are not matched."""
        assert _is_mcpbr_image("python:3.11-slim") is False
        assert _is_mcpbr_image("ubuntu:22.04") is False
        assert _is_mcpbr_image("nginx:latest") is False

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert _is_mcpbr_image("MCPBR-env") is True
        assert _is_mcpbr_image("SWE-BENCH-image") is True


# ---------------------------------------------------------------------------
# ImageCache tests
# ---------------------------------------------------------------------------


class TestImageCacheInit:
    """Tests for ImageCache initialization."""

    def test_default_config(self, mock_docker_client):
        """Test initialization with default config."""
        cache = ImageCache()
        assert cache._config.max_size_gb == 50.0
        assert cache._config.max_images == 100

    def test_custom_config(self, image_cache: ImageCache, cache_config: CacheConfig):
        """Test initialization with custom config."""
        assert image_cache._config.max_size_gb == cache_config.max_size_gb
        assert image_cache._config.max_images == cache_config.max_images

    def test_creates_cache_dir(self, tmp_path: Path, mock_docker_client):
        """Test that the cache directory is created on init."""
        cache_dir = tmp_path / "new_cache_dir"
        config = CacheConfig(cache_dir=cache_dir)
        ImageCache(config=config)
        assert cache_dir.exists()

    def test_loads_existing_metadata(
        self, temp_cache_dir: Path, mock_docker_client, sample_entry: CacheEntry
    ):
        """Test that existing metadata is loaded on init."""
        # Write metadata file before creating cache
        metadata = {
            "entries": [sample_entry.to_dict()],
            "hits": 10,
            "misses": 2,
            "benchmark_history": {"swe-bench-lite": ["img:a"]},
        }
        metadata_path = temp_cache_dir / "docker_cache_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

        config = CacheConfig(cache_dir=temp_cache_dir)
        cache = ImageCache(config=config)

        assert len(cache._entries) == 1
        assert sample_entry.image_tag in cache._entries
        assert cache._hits == 10
        assert cache._misses == 2

    def test_handles_corrupted_metadata(self, temp_cache_dir: Path, mock_docker_client):
        """Test graceful handling of corrupted metadata file."""
        metadata_path = temp_cache_dir / "docker_cache_metadata.json"
        with open(metadata_path, "w") as f:
            f.write("{invalid json!!!")

        config = CacheConfig(cache_dir=temp_cache_dir)
        cache = ImageCache(config=config)

        # Should start with empty state
        assert len(cache._entries) == 0
        assert cache._hits == 0
        assert cache._misses == 0


class TestImageCacheScan:
    """Tests for ImageCache.scan()."""

    def test_scan_discovers_mcpbr_images(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan discovers mcpbr-related images."""
        mock_image = MagicMock()
        mock_image.tags = ["ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-11099"]
        mock_image.attrs = {
            "Size": 2_000_000_000,  # ~2 GB
            "RootFS": {"Type": "layers", "Layers": ["sha256:aaa", "sha256:bbb"]},
        }
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        assert len(entries) == 1
        assert entries[0].image_tag == mock_image.tags[0]
        assert entries[0].layers == ["sha256:aaa", "sha256:bbb"]

    def test_scan_ignores_unrelated_images(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan ignores non-mcpbr images."""
        mock_image = MagicMock()
        mock_image.tags = ["python:3.11-slim"]
        mock_image.attrs = {"Size": 100_000_000}
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        assert len(entries) == 0

    def test_scan_removes_stale_entries(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan removes entries for images no longer present locally."""
        # Pre-populate with an entry
        now = datetime.now(timezone.utc)
        image_cache._entries["old-swe-bench-image"] = CacheEntry(
            image_tag="old-swe-bench-image",
            size_mb=500.0,
            last_used=now,
            use_count=1,
            layers=[],
            created=now,
        )

        # Docker reports no images
        mock_docker_client.images.list.return_value = []

        entries = image_cache.scan()

        assert len(entries) == 0
        assert "old-swe-bench-image" not in image_cache._entries

    def test_scan_preserves_use_count(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan preserves existing use_count for known images."""
        tag = "ghcr.io/epoch-research/swe-bench.eval.x86_64.sympy__sympy-20154"
        now = datetime.now(timezone.utc)
        image_cache._entries[tag] = CacheEntry(
            image_tag=tag,
            size_mb=1000.0,
            last_used=now,
            use_count=42,
            layers=["sha256:old"],
            created=now - timedelta(days=5),
        )

        mock_image = MagicMock()
        mock_image.tags = [tag]
        mock_image.attrs = {
            "Size": 1_100_000_000,
            "RootFS": {"Type": "layers", "Layers": ["sha256:new"]},
        }
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        assert len(entries) == 1
        assert entries[0].use_count == 42

    def test_scan_handles_tagless_images(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan skips images without tags."""
        mock_image = MagicMock()
        mock_image.tags = []
        mock_image.attrs = {"Size": 100_000_000}
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        assert len(entries) == 0

    def test_scan_docker_unavailable(self, temp_cache_dir: Path):
        """Test scan when Docker is not available."""
        with patch("mcpbr.docker_cache.docker") as mock_docker_module:
            mock_docker_module.from_env.side_effect = Exception("Docker not running")
            config = CacheConfig(cache_dir=temp_cache_dir)
            cache = ImageCache(config=config)

            entries = cache.scan()

            # Returns existing entries (empty in this case)
            assert entries == []

    def test_scan_saves_metadata(self, image_cache: ImageCache, mock_docker_client):
        """Test that scan persists metadata to disk."""
        mock_image = MagicMock()
        mock_image.tags = ["mcpbr-env"]
        mock_image.attrs = {
            "Size": 500_000_000,
            "RootFS": {"Type": "layers", "Layers": []},
        }
        mock_docker_client.images.list.return_value = [mock_image]

        image_cache.scan()

        metadata_path = image_cache._metadata_path()
        assert metadata_path.exists()
        with open(metadata_path) as f:
            data = json.load(f)
        assert len(data["entries"]) == 1


class TestImageCacheGetCached:
    """Tests for ImageCache.get_cached()."""

    def test_cache_hit(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test successful cache lookup."""
        image_cache._entries[sample_entry.image_tag] = sample_entry

        result = image_cache.get_cached(sample_entry.image_tag)

        assert result is not None
        assert result.image_tag == sample_entry.image_tag
        assert image_cache._hits == 1
        assert image_cache._misses == 0

    def test_cache_miss(self, image_cache: ImageCache):
        """Test cache miss for unknown image."""
        result = image_cache.get_cached("nonexistent:latest")

        assert result is None
        assert image_cache._hits == 0
        assert image_cache._misses == 1

    def test_hit_rate_tracking(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test that hit/miss counters accumulate correctly."""
        image_cache._entries[sample_entry.image_tag] = sample_entry

        image_cache.get_cached(sample_entry.image_tag)  # hit
        image_cache.get_cached(sample_entry.image_tag)  # hit
        image_cache.get_cached("missing:v1")  # miss

        assert image_cache._hits == 2
        assert image_cache._misses == 1


class TestImageCacheRecordUse:
    """Tests for ImageCache.record_use()."""

    def test_updates_last_used_and_count(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test that record_use updates last_used and increments use_count."""
        original_count = sample_entry.use_count
        original_last_used = sample_entry.last_used
        image_cache._entries[sample_entry.image_tag] = sample_entry

        image_cache.record_use(sample_entry.image_tag)

        updated = image_cache._entries[sample_entry.image_tag]
        assert updated.use_count == original_count + 1
        assert updated.last_used >= original_last_used

    def test_noop_for_unknown_image(self, image_cache: ImageCache):
        """Test that record_use is a no-op for untracked images."""
        # Should not raise
        image_cache.record_use("unknown:latest")
        assert len(image_cache._entries) == 0

    def test_multiple_uses(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test that multiple record_use calls accumulate correctly."""
        sample_entry.use_count = 0
        image_cache._entries[sample_entry.image_tag] = sample_entry

        for _ in range(5):
            image_cache.record_use(sample_entry.image_tag)

        assert image_cache._entries[sample_entry.image_tag].use_count == 5


class TestImageCacheRecordBenchmarkUse:
    """Tests for ImageCache.record_benchmark_use()."""

    def test_records_benchmark_image_association(self, image_cache: ImageCache):
        """Test recording a benchmark-image association."""
        image_cache.record_benchmark_use("swe-bench-lite", "img:django")

        assert "swe-bench-lite" in image_cache._benchmark_history
        assert "img:django" in image_cache._benchmark_history["swe-bench-lite"]

    def test_no_duplicates(self, image_cache: ImageCache):
        """Test that duplicate associations are not recorded."""
        image_cache.record_benchmark_use("swe-bench-lite", "img:django")
        image_cache.record_benchmark_use("swe-bench-lite", "img:django")

        assert len(image_cache._benchmark_history["swe-bench-lite"]) == 1

    def test_multiple_images_per_benchmark(self, image_cache: ImageCache):
        """Test recording multiple images for one benchmark."""
        image_cache.record_benchmark_use("swe-bench-lite", "img:django")
        image_cache.record_benchmark_use("swe-bench-lite", "img:astropy")

        assert len(image_cache._benchmark_history["swe-bench-lite"]) == 2


class TestImageCacheEvictLru:
    """Tests for ImageCache.evict_lru()."""

    def _make_entry(
        self, tag: str, size_mb: float, last_used: datetime, use_count: int = 0
    ) -> CacheEntry:
        """Helper to create a CacheEntry with specific values."""
        return CacheEntry(
            image_tag=tag,
            size_mb=size_mb,
            last_used=last_used,
            use_count=use_count,
            layers=[],
            created=last_used - timedelta(days=1),
        )

    def test_evict_by_size(self, image_cache: ImageCache, mock_docker_client):
        """Test LRU eviction when total size exceeds target."""
        now = datetime.now(timezone.utc)
        # Each image is ~5 GB (5120 MB) to exceed 10 GB limit with 3 images
        image_cache._entries = {
            "img:old": self._make_entry("img:old", 5120.0, now - timedelta(hours=3)),
            "img:mid": self._make_entry("img:mid", 5120.0, now - timedelta(hours=2)),
            "img:new": self._make_entry("img:new", 5120.0, now - timedelta(hours=1)),
        }

        evicted = image_cache.evict_lru(target_size_gb=10.0)

        # Should evict oldest first until we're under 10 GB
        assert "img:old" in evicted
        assert "img:new" not in evicted

    def test_evict_by_count(self, image_cache: ImageCache, mock_docker_client):
        """Test LRU eviction when image count exceeds max_images."""
        now = datetime.now(timezone.utc)
        # Config max_images=5, add 7 small images
        for i in range(7):
            tag = f"mcpbr-img:{i}"
            image_cache._entries[tag] = self._make_entry(tag, 100.0, now - timedelta(hours=7 - i))

        evicted = image_cache.evict_lru()

        # Should evict at least 2 to get from 7 down to 5
        assert len(evicted) >= 2
        # The oldest images should be evicted first
        assert "mcpbr-img:0" in evicted
        assert "mcpbr-img:1" in evicted

    def test_evict_nothing_when_within_limits(self, image_cache: ImageCache, mock_docker_client):
        """Test that no eviction occurs when cache is within limits."""
        now = datetime.now(timezone.utc)
        image_cache._entries = {
            "img:a": self._make_entry("img:a", 500.0, now),
            "img:b": self._make_entry("img:b", 500.0, now),
        }

        evicted = image_cache.evict_lru()

        assert evicted == []

    def test_evict_uses_default_target(self, image_cache: ImageCache, mock_docker_client):
        """Test that evict_lru uses config max_size_gb when target is None."""
        now = datetime.now(timezone.utc)
        # Within 10 GB limit
        image_cache._entries = {
            "img:a": self._make_entry("img:a", 1024.0, now),
        }

        evicted = image_cache.evict_lru(target_size_gb=None)

        assert evicted == []

    def test_evict_removes_docker_images(self, image_cache: ImageCache, mock_docker_client):
        """Test that eviction calls Docker to remove images."""
        now = datetime.now(timezone.utc)
        image_cache._entries = {
            "img:old": self._make_entry("img:old", 5120.0, now - timedelta(hours=2)),
            "img:new": self._make_entry("img:new", 5120.0, now),
        }
        # Set max_images to 1 to force eviction
        image_cache._config.max_images = 1

        evicted = image_cache.evict_lru()

        assert "img:old" in evicted
        mock_docker_client.images.remove.assert_called_with("img:old", force=True)

    def test_evict_saves_metadata(self, image_cache: ImageCache, mock_docker_client):
        """Test that eviction persists updated metadata."""
        now = datetime.now(timezone.utc)
        image_cache._config.max_images = 1
        image_cache._entries = {
            "img:old": self._make_entry("img:old", 100.0, now - timedelta(hours=2)),
            "img:new": self._make_entry("img:new", 100.0, now),
        }

        image_cache.evict_lru()

        metadata_path = image_cache._metadata_path()
        assert metadata_path.exists()
        with open(metadata_path) as f:
            data = json.load(f)
        tags = [e["image_tag"] for e in data["entries"]]
        assert "img:old" not in tags
        assert "img:new" in tags


class TestImageCacheGetStats:
    """Tests for ImageCache.get_stats()."""

    def test_empty_cache_stats(self, image_cache: ImageCache):
        """Test stats for an empty cache."""
        stats = image_cache.get_stats()

        assert stats.total_images == 0
        assert stats.total_size_gb == 0.0
        assert stats.cache_hit_rate == 0.0
        assert stats.most_used == []
        assert stats.least_used == []
        assert stats.potential_savings_gb == 0.0

    def test_stats_with_entries(self, image_cache: ImageCache):
        """Test stats reflect cached entries."""
        now = datetime.now(timezone.utc)
        image_cache._entries = {
            "img:a": CacheEntry("img:a", 1024.0, now, 10, ["sha256:x"], now),
            "img:b": CacheEntry("img:b", 2048.0, now, 5, ["sha256:y"], now),
            "img:c": CacheEntry("img:c", 512.0, now, 1, ["sha256:z"], now),
        }

        stats = image_cache.get_stats()

        assert stats.total_images == 3
        assert stats.total_size_gb > 0
        assert stats.most_used[0] == "img:a"
        assert stats.least_used[0] == "img:c"

    def test_hit_rate_calculation(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test hit rate calculation with mixed hits and misses."""
        image_cache._entries[sample_entry.image_tag] = sample_entry
        image_cache._hits = 8
        image_cache._misses = 2

        stats = image_cache.get_stats()

        assert stats.cache_hit_rate == 0.8

    def test_hit_rate_zero_lookups(self, image_cache: ImageCache):
        """Test hit rate is 0.0 when no lookups have occurred."""
        stats = image_cache.get_stats()

        assert stats.cache_hit_rate == 0.0

    def test_potential_savings_with_shared_layers(self, image_cache: ImageCache):
        """Test potential savings estimation with shared layers."""
        now = datetime.now(timezone.utc)
        shared = "sha256:shared"
        image_cache._entries = {
            "img:a": CacheEntry("img:a", 1024.0, now, 1, [shared, "sha256:a1"], now),
            "img:b": CacheEntry("img:b", 1024.0, now, 1, [shared, "sha256:b1"], now),
        }

        stats = image_cache.get_stats()

        # 4 total layers, 3 unique => dedup_ratio ~= 0.25
        assert stats.potential_savings_gb > 0

    def test_no_savings_without_shared_layers(self, image_cache: ImageCache):
        """Test zero savings when no layers are shared."""
        now = datetime.now(timezone.utc)
        image_cache._entries = {
            "img:a": CacheEntry("img:a", 1024.0, now, 1, ["sha256:a1"], now),
            "img:b": CacheEntry("img:b", 1024.0, now, 1, ["sha256:b1"], now),
        }

        stats = image_cache.get_stats()

        assert stats.potential_savings_gb == 0.0

    def test_most_used_limited_to_five(self, image_cache: ImageCache):
        """Test that most_used and least_used are capped at 5."""
        now = datetime.now(timezone.utc)
        for i in range(10):
            tag = f"img:{i}"
            image_cache._entries[tag] = CacheEntry(tag, 100.0, now, i, [], now)

        stats = image_cache.get_stats()

        assert len(stats.most_used) == 5
        assert len(stats.least_used) == 5


class TestImageCacheRecommendWarmup:
    """Tests for ImageCache.recommend_warmup()."""

    def test_recommends_missing_images(self, image_cache: ImageCache):
        """Test that warmup recommends images not currently cached."""
        image_cache._benchmark_history = {
            "swe-bench-lite": ["img:django", "img:astropy", "img:sympy"],
        }
        # Only django is currently cached
        now = datetime.now(timezone.utc)
        image_cache._entries = {
            "img:django": CacheEntry("img:django", 1000.0, now, 5, [], now),
        }

        recommendations = image_cache.recommend_warmup("swe-bench-lite")

        assert "img:astropy" in recommendations
        assert "img:sympy" in recommendations
        assert "img:django" not in recommendations

    def test_no_recommendations_for_unknown_benchmark(self, image_cache: ImageCache):
        """Test that unknown benchmarks yield no recommendations."""
        recommendations = image_cache.recommend_warmup("unknown-benchmark")

        assert recommendations == []

    def test_no_recommendations_when_all_cached(self, image_cache: ImageCache):
        """Test that no recommendations are made when everything is cached."""
        now = datetime.now(timezone.utc)
        image_cache._benchmark_history = {
            "swe-bench-lite": ["img:django"],
        }
        image_cache._entries = {
            "img:django": CacheEntry("img:django", 1000.0, now, 5, [], now),
        }

        recommendations = image_cache.recommend_warmup("swe-bench-lite")

        assert recommendations == []

    def test_empty_history(self, image_cache: ImageCache):
        """Test recommendations with empty benchmark history."""
        image_cache._benchmark_history = {"swe-bench-lite": []}

        recommendations = image_cache.recommend_warmup("swe-bench-lite")

        assert recommendations == []


class TestImageCacheCleanupDangling:
    """Tests for ImageCache.cleanup_dangling()."""

    def test_cleanup_removes_dangling(self, image_cache: ImageCache, mock_docker_client):
        """Test that dangling images are pruned."""
        mock_docker_client.images.prune.return_value = {
            "ImagesDeleted": [{"Deleted": "sha256:aaa"}, {"Deleted": "sha256:bbb"}],
            "SpaceReclaimed": 500_000_000,
        }

        count = image_cache.cleanup_dangling()

        assert count == 2
        mock_docker_client.images.prune.assert_called_once_with(filters={"dangling": True})

    def test_cleanup_no_dangling(self, image_cache: ImageCache, mock_docker_client):
        """Test cleanup when no dangling images exist."""
        mock_docker_client.images.prune.return_value = {
            "ImagesDeleted": None,
            "SpaceReclaimed": 0,
        }

        count = image_cache.cleanup_dangling()

        assert count == 0

    def test_cleanup_handles_docker_error(self, image_cache: ImageCache, mock_docker_client):
        """Test cleanup handles Docker errors gracefully."""
        mock_docker_client.images.prune.side_effect = Exception("API error")

        count = image_cache.cleanup_dangling()

        assert count == 0

    def test_cleanup_docker_unavailable(self, temp_cache_dir: Path):
        """Test cleanup when Docker is not available."""
        with patch("mcpbr.docker_cache.docker") as mock_docker_module:
            mock_docker_module.from_env.side_effect = Exception("Docker not running")
            config = CacheConfig(cache_dir=temp_cache_dir)
            cache = ImageCache(config=config)

            count = cache.cleanup_dangling()

            assert count == 0


class TestImageCacheMetadataPersistence:
    """Tests for metadata persistence across ImageCache instances."""

    def test_metadata_survives_restart(self, temp_cache_dir: Path, mock_docker_client):
        """Test that metadata persists when a new ImageCache instance is created."""
        config = CacheConfig(cache_dir=temp_cache_dir)

        # First instance records some state
        cache1 = ImageCache(config=config)
        now = datetime.now(timezone.utc)
        cache1._entries["img:test"] = CacheEntry("img:test", 500.0, now, 3, [], now)
        cache1._hits = 5
        cache1._misses = 1
        cache1._save_metadata()

        # Second instance should load the state
        cache2 = ImageCache(config=config)

        assert "img:test" in cache2._entries
        assert cache2._entries["img:test"].use_count == 3
        assert cache2._hits == 5
        assert cache2._misses == 1

    def test_benchmark_history_persists(self, temp_cache_dir: Path, mock_docker_client):
        """Test that benchmark history persists across instances."""
        config = CacheConfig(cache_dir=temp_cache_dir)

        cache1 = ImageCache(config=config)
        cache1.record_benchmark_use("swe-bench-lite", "img:django")

        cache2 = ImageCache(config=config)

        assert "swe-bench-lite" in cache2._benchmark_history
        assert "img:django" in cache2._benchmark_history["swe-bench-lite"]


class TestImageCacheEdgeCases:
    """Tests for edge cases and error handling."""

    def test_docker_image_removal_failure(self, image_cache: ImageCache, mock_docker_client):
        """Test that eviction continues even if Docker removal fails."""
        mock_docker_client.images.remove.side_effect = Exception("Permission denied")

        now = datetime.now(timezone.utc)
        image_cache._config.max_images = 1
        image_cache._entries = {
            "img:old": CacheEntry("img:old", 100.0, now - timedelta(hours=2), 0, [], now),
            "img:new": CacheEntry("img:new", 100.0, now, 0, [], now),
        }

        evicted = image_cache.evict_lru()

        # Entry should still be removed from metadata even if Docker removal fails
        assert "img:old" in evicted
        assert "img:old" not in image_cache._entries

    def test_scan_with_multiple_tags_per_image(self, image_cache: ImageCache, mock_docker_client):
        """Test scan when a single Docker image has multiple tags."""
        mock_image = MagicMock()
        mock_image.tags = [
            "mcpbr-env:latest",
            "mcpbr-env:v1",
        ]
        mock_image.attrs = {
            "Size": 500_000_000,
            "RootFS": {"Type": "layers", "Layers": ["sha256:abc"]},
        }
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        # Both tags should be tracked
        assert len(entries) == 2
        tags = {e.image_tag for e in entries}
        assert "mcpbr-env:latest" in tags
        assert "mcpbr-env:v1" in tags

    def test_concurrent_get_and_record(self, image_cache: ImageCache, sample_entry: CacheEntry):
        """Test that get_cached and record_use can be called in sequence."""
        image_cache._entries[sample_entry.image_tag] = sample_entry
        original_count = sample_entry.use_count

        entry = image_cache.get_cached(sample_entry.image_tag)
        assert entry is not None

        image_cache.record_use(sample_entry.image_tag)

        assert image_cache._entries[sample_entry.image_tag].use_count == original_count + 1
        assert image_cache._hits == 1

    def test_scan_image_without_rootfs(self, image_cache: ImageCache, mock_docker_client):
        """Test scan handles images without RootFS info."""
        mock_image = MagicMock()
        mock_image.tags = ["mcpbr-env:latest"]
        mock_image.attrs = {"Size": 500_000_000}  # No RootFS key
        mock_docker_client.images.list.return_value = [mock_image]

        entries = image_cache.scan()

        assert len(entries) == 1
        assert entries[0].layers == []
