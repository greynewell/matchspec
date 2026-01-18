"""Tests for benchmark abstraction and implementations."""

import pytest

from mcpbr.benchmarks import (
    BENCHMARK_REGISTRY,
    Benchmark,
    CyberGymBenchmark,
    SWEBenchmark,
    create_benchmark,
    list_benchmarks,
)


class TestBenchmarkRegistry:
    """Tests for benchmark registry and factory."""

    def test_list_benchmarks(self) -> None:
        """Test listing available benchmarks."""
        benchmarks = list_benchmarks()
        assert "swe-bench" in benchmarks
        assert "cybergym" in benchmarks
        assert len(benchmarks) >= 2

    def test_create_swebench(self) -> None:
        """Test creating SWE-bench benchmark."""
        benchmark = create_benchmark("swe-bench")
        assert isinstance(benchmark, SWEBenchmark)
        assert benchmark.name == "swe-bench"

    def test_create_cybergym(self) -> None:
        """Test creating CyberGym benchmark."""
        benchmark = create_benchmark("cybergym")
        assert isinstance(benchmark, CyberGymBenchmark)
        assert benchmark.name == "cybergym"

    def test_create_with_custom_dataset(self) -> None:
        """Test creating benchmark with custom dataset."""
        benchmark = create_benchmark("swe-bench", dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_create_cybergym_with_level(self) -> None:
        """Test creating CyberGym with difficulty level."""
        benchmark = create_benchmark("cybergym", level=2)
        assert benchmark.level == 2

    def test_create_unknown_benchmark(self) -> None:
        """Test creating unknown benchmark raises error."""
        with pytest.raises(ValueError, match="Unknown benchmark"):
            create_benchmark("unknown-benchmark")


class TestSWEBenchmark:
    """Tests for SWE-bench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test SWE-bench initialization."""
        benchmark = SWEBenchmark()
        assert benchmark.name == "swe-bench"
        assert benchmark.dataset == "SWE-bench/SWE-bench_Lite"

    def test_custom_dataset(self) -> None:
        """Test SWE-bench with custom dataset."""
        benchmark = SWEBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_normalize_task(self) -> None:
        """Test normalizing SWE-bench task."""
        benchmark = SWEBenchmark()
        task = {
            "instance_id": "test-123",
            "problem_statement": "Fix the bug",
            "repo": "owner/repo",
            "base_commit": "abc123",
            "FAIL_TO_PASS": "[]",
            "PASS_TO_PASS": "[]",
            "test_patch": "",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "test-123"
        assert normalized.problem_statement == "Fix the bug"
        assert normalized.repo == "owner/repo"
        assert normalized.commit == "abc123"

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image name."""
        benchmark = SWEBenchmark()
        task = {"instance_id": "astropy__astropy-12907"}
        image = benchmark.get_prebuilt_image(task)
        assert image is not None
        assert "astropy__astropy-12907" in image

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = SWEBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "Fix" in prompt or "fix" in prompt


class TestCyberGymBenchmark:
    """Tests for CyberGym benchmark implementation."""

    def test_initialization(self) -> None:
        """Test CyberGym initialization."""
        benchmark = CyberGymBenchmark()
        assert benchmark.name == "cybergym"
        assert benchmark.dataset == "sunblaze-ucb/cybergym"
        assert benchmark.level == 1

    def test_custom_level(self) -> None:
        """Test CyberGym with custom level."""
        benchmark = CyberGymBenchmark(level=3)
        assert benchmark.level == 3

    def test_normalize_task(self) -> None:
        """Test normalizing CyberGym task."""
        benchmark = CyberGymBenchmark()
        task = {
            "project": "libxml2",
            "bug_id": "CVE-2021-1234",
            "description": "Buffer overflow vulnerability",
            "pre_patch_repo": "https://github.com/owner/repo.git",
            "pre_patch_commit": "abc123",
            "post_patch_repo": "https://github.com/owner/repo.git",
            "post_patch_commit": "def456",
            "vulnerability_type": "buffer_overflow",
            "_cybergym_level": 1,
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "libxml2_CVE-2021-1234"
        assert "vulnerability" in normalized.problem_statement.lower() or "exploit" in normalized.problem_statement.lower()
        assert "owner/repo" in normalized.repo
        assert normalized.commit == "abc123"

    def test_generate_problem_statement_level_0(self) -> None:
        """Test problem statement generation at level 0."""
        benchmark = CyberGymBenchmark(level=0)
        task = {
            "project": "test-project",
            "bug_id": "123",
            "description": "Test description",
            "vulnerability_type": "buffer_overflow",
            "_cybergym_level": 0,
        }

        statement = benchmark._generate_problem_statement(task)
        assert "test-project" in statement
        assert "123" in statement
        # Level 0 should be minimal
        assert len(statement) < 200

    def test_generate_problem_statement_level_3(self) -> None:
        """Test problem statement generation at level 3."""
        benchmark = CyberGymBenchmark(level=3)
        task = {
            "project": "test-project",
            "bug_id": "123",
            "description": "Test description",
            "vulnerability_type": "buffer_overflow",
            "_cybergym_level": 3,
        }

        statement = benchmark._generate_problem_statement(task)
        assert "test-project" in statement
        assert "123" in statement
        assert "buffer_overflow" in statement
        assert "Test description" in statement
        # Level 3 should be detailed
        assert len(statement) > 200

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image (should be None for CyberGym)."""
        benchmark = CyberGymBenchmark()
        task = {"project": "test", "bug_id": "123"}
        image = benchmark.get_prebuilt_image(task)
        assert image is None

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = CyberGymBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "PoC" in prompt or "Proof-of-Concept" in prompt
        assert "exploit" in prompt.lower() or "vulnerability" in prompt.lower()


class TestBenchmarkProtocol:
    """Tests for benchmark protocol compliance."""

    def test_swebench_implements_protocol(self) -> None:
        """Test that SWEBenchmark implements Benchmark protocol."""
        benchmark = SWEBenchmark()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")

    def test_cybergym_implements_protocol(self) -> None:
        """Test that CyberGymBenchmark implements Benchmark protocol."""
        benchmark = CyberGymBenchmark()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")
