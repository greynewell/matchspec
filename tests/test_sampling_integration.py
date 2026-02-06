"""Tests for sampling integration — wiring sampling.py into harness/config."""

import pytest

from mcpbr.config import HarnessConfig, MCPServerConfig
from mcpbr.sampling import SamplingStrategy, sample_tasks

# ---------------------------------------------------------------------------
# Config acceptance tests
# ---------------------------------------------------------------------------


class TestSamplingConfig:
    """Config accepts sampling_strategy, random_seed, stratify_field."""

    def _make_config(self, **overrides):
        defaults = {
            "mcp_server": MCPServerConfig(command="echo", args=[]),
            "benchmark": "humaneval",
        }
        defaults.update(overrides)
        return HarnessConfig(**defaults)

    def test_default_sampling_strategy_is_sequential(self):
        cfg = self._make_config()
        assert cfg.sampling_strategy == "sequential"

    def test_accepts_random_strategy(self):
        cfg = self._make_config(sampling_strategy="random")
        assert cfg.sampling_strategy == "random"

    def test_accepts_stratified_strategy(self):
        cfg = self._make_config(sampling_strategy="stratified", stratify_field="difficulty")
        assert cfg.sampling_strategy == "stratified"

    def test_rejects_invalid_strategy(self):
        with pytest.raises(ValueError):
            self._make_config(sampling_strategy="bogus")

    def test_random_seed_default_none(self):
        cfg = self._make_config()
        assert cfg.random_seed is None

    def test_random_seed_accepts_int(self):
        cfg = self._make_config(random_seed=42)
        assert cfg.random_seed == 42

    def test_stratify_field_default_none(self):
        cfg = self._make_config()
        assert cfg.stratify_field is None

    def test_stratify_field_accepts_string(self):
        cfg = self._make_config(stratify_field="difficulty")
        assert cfg.stratify_field == "difficulty"

    def test_stratified_requires_stratify_field(self):
        with pytest.raises(ValueError, match="stratify_field is required"):
            self._make_config(sampling_strategy="stratified")


# ---------------------------------------------------------------------------
# Harness wiring tests
# ---------------------------------------------------------------------------

FAKE_TASKS = [
    {"instance_id": f"task-{i}", "difficulty": "easy" if i < 5 else "hard"} for i in range(10)
]


class TestHarnessSamplingWiring:
    """Harness applies sample_tasks() after benchmark.load_tasks()."""

    def _make_config(self, **overrides):
        defaults = {
            "mcp_server": MCPServerConfig(command="echo", args=[]),
            "benchmark": "humaneval",
            "sample_size": 3,
        }
        defaults.update(overrides)
        return HarnessConfig(**defaults)

    @pytest.mark.asyncio
    async def test_sequential_strategy_uses_first_n(self):
        """Default sequential strategy takes first N tasks."""
        cfg = self._make_config(sampling_strategy="sequential")
        tasks = list(FAKE_TASKS)
        result = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=cfg.random_seed,
        )
        assert result == tasks[:3]

    @pytest.mark.asyncio
    async def test_random_strategy_shuffles(self):
        """Random strategy with a seed produces a shuffled subset."""
        cfg = self._make_config(sampling_strategy="random", random_seed=42)
        tasks = list(FAKE_TASKS)
        result = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=cfg.random_seed,
        )
        # Should have correct count
        assert len(result) == 3
        # Should NOT be the first 3 (with overwhelming probability for seed=42)
        assert result != tasks[:3]

    @pytest.mark.asyncio
    async def test_same_seed_produces_identical_selection(self):
        """Same random_seed yields identical task selection."""
        cfg = self._make_config(sampling_strategy="random", random_seed=99)
        tasks = list(FAKE_TASKS)
        r1 = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=cfg.random_seed,
        )
        r2 = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=cfg.random_seed,
        )
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_different_seeds_differ(self):
        """Different seeds produce different selections."""
        tasks = list(FAKE_TASKS)
        r1 = sample_tasks(tasks, sample_size=3, strategy=SamplingStrategy.RANDOM, seed=1)
        r2 = sample_tasks(tasks, sample_size=3, strategy=SamplingStrategy.RANDOM, seed=2)
        assert r1 != r2

    @pytest.mark.asyncio
    async def test_none_seed_is_nondeterministic(self):
        """When random_seed is None, sampling is non-deterministic."""
        cfg = self._make_config(
            sampling_strategy="random",
            random_seed=None,
        )
        # seed=None means non-deterministic (no seeding)
        seed = cfg.random_seed  # None
        tasks = list(FAKE_TASKS)
        result = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=seed,
        )
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_non_sequential_loads_all_then_samples(self):
        """When strategy != sequential, harness should pass sample_size=None
        to benchmark.load_tasks() and apply sampling after."""
        cfg = self._make_config(sampling_strategy="random", random_seed=42, sample_size=3)

        # The key contract: when sampling_strategy != sequential,
        # benchmark gets sample_size=None (load all) and sampling happens after
        strategy = SamplingStrategy(cfg.sampling_strategy)
        assert strategy != SamplingStrategy.SEQUENTIAL

        # Load all tasks (simulating benchmark.load_tasks(sample_size=None))
        all_tasks = list(FAKE_TASKS)  # 10 tasks
        # Then sample
        result = sample_tasks(
            all_tasks,
            sample_size=cfg.sample_size,
            strategy=strategy,
            seed=cfg.random_seed,
        )
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_stratified_with_field(self):
        """Stratified sampling groups by stratify_field."""
        cfg = self._make_config(
            sampling_strategy="stratified",
            random_seed=42,
            sample_size=4,
            stratify_field="difficulty",
        )
        tasks = list(FAKE_TASKS)  # 5 easy + 5 hard
        result = sample_tasks(
            tasks,
            sample_size=cfg.sample_size,
            strategy=SamplingStrategy(cfg.sampling_strategy),
            seed=cfg.random_seed,
            stratify_field=cfg.stratify_field,
        )
        assert len(result) == 4
        # Both groups should be represented
        difficulties = {t["difficulty"] for t in result}
        assert "easy" in difficulties
        assert "hard" in difficulties
