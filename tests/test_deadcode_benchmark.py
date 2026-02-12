"""Tests for dead code detection benchmark."""

from mcpbr.benchmarks import BENCHMARK_REGISTRY, create_benchmark
from mcpbr.benchmarks.deadcode import DeadCodeBenchmark


class TestDeadCodeBenchmark:
    """Tests for DeadCodeBenchmark class."""

    def test_benchmark_in_registry(self) -> None:
        """Verify dead-code benchmark is registered."""
        assert "dead-code" in BENCHMARK_REGISTRY
        assert BENCHMARK_REGISTRY["dead-code"] == DeadCodeBenchmark

    def test_create_benchmark(self) -> None:
        """Test benchmark creation via factory."""
        benchmark = create_benchmark("dead-code")
        assert isinstance(benchmark, DeadCodeBenchmark)
        assert benchmark.name == "dead-code"

    def test_load_synthetic_tasks(self) -> None:
        """Test loading synthetic tasks when no dataset provided."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark.load_tasks()

        assert len(tasks) > 0
        for task in tasks:
            assert "instance_id" in task
            assert "repo_content" in task
            assert "dead_code" in task
            assert "alive_code" in task

    def test_load_tasks_with_sample_size(self) -> None:
        """Test sample_size limiting."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark.load_tasks(sample_size=1)

        assert len(tasks) == 1

    def test_load_tasks_filter_by_language(self) -> None:
        """Test filtering by language (category)."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark.load_tasks(filter_category=["python"])

        assert len(tasks) > 0
        for task in tasks:
            assert task["language"] == "python"

    def test_load_tasks_filter_by_difficulty(self) -> None:
        """Test filtering by difficulty."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark.load_tasks(filter_difficulty=["easy"])

        assert len(tasks) > 0
        for task in tasks:
            assert task["difficulty"] == "easy"

    def test_normalize_task(self) -> None:
        """Test task normalization."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark.load_tasks(sample_size=1)
        task = tasks[0]

        normalized = benchmark.normalize_task(task)

        assert normalized.task_id == task["instance_id"]
        assert "dead code" in normalized.problem_statement.lower()
        assert normalized.metadata["language"] == task["language"]
        assert normalized.metadata["dead_code"] == task["dead_code"]

    def test_get_prompt_template(self) -> None:
        """Test prompt template generation."""
        benchmark = DeadCodeBenchmark()
        template = benchmark.get_prompt_template()

        assert "dead code" in template.lower()
        assert "{problem_statement}" in template

    def test_get_prebuilt_image_returns_none(self) -> None:
        """Test that no pre-built images are used."""
        benchmark = DeadCodeBenchmark()
        result = benchmark.get_prebuilt_image({})

        assert result is None

    def test_synthetic_task_structure(self) -> None:
        """Verify synthetic tasks have correct structure."""
        benchmark = DeadCodeBenchmark()
        tasks = benchmark._generate_synthetic_tasks()

        for task in tasks:
            # Required fields
            assert "instance_id" in task
            assert "language" in task
            assert "difficulty" in task
            assert "repo_content" in task
            assert "dead_code" in task
            assert "alive_code" in task

            # Repo content should have files
            assert len(task["repo_content"]) > 0

            # Dead code entries should have required fields
            for dead in task["dead_code"]:
                assert "file" in dead
                assert "name" in dead
                assert "line" in dead
                assert "type" in dead

            # Alive code entries should have required fields
            for alive in task["alive_code"]:
                assert "file" in alive
                assert "name" in alive
                assert "line" in alive
                assert "type" in alive
