"""Tests for benchmark abstraction and implementations."""

import pytest

from mcpbr.benchmarks import (
    Benchmark,
    CyberGymBenchmark,
    MCPToolBenchmark,
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
        assert "mcptoolbench" in benchmarks
        assert len(benchmarks) >= 3

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

    def test_create_mcptoolbench(self) -> None:
        """Test creating MCPToolBench++ benchmark."""
        benchmark = create_benchmark("mcptoolbench")
        assert isinstance(benchmark, MCPToolBenchmark)
        assert benchmark.name == "mcptoolbench"

    def test_create_mcptoolbench_with_custom_dataset(self) -> None:
        """Test creating MCPToolBench++ with custom dataset."""
        benchmark = create_benchmark("mcptoolbench", dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

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

    def test_verified_dataset(self) -> None:
        """Test SWE-bench with Verified dataset."""
        benchmark = SWEBenchmark(dataset="SWE-bench/SWE-bench_Verified")
        assert benchmark.dataset == "SWE-bench/SWE-bench_Verified"
        assert benchmark.name == "swe-bench"

    def test_full_dataset(self) -> None:
        """Test SWE-bench with full dataset."""
        benchmark = SWEBenchmark(dataset="SWE-bench/SWE-bench")
        assert benchmark.dataset == "SWE-bench/SWE-bench"
        assert benchmark.name == "swe-bench"

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
            "task_id": "arvo:1234",
            "project_name": "libxml2",
            "project_main_repo": "https://github.com/owner/repo.git",
            "project_language": "c++",
            "vulnerability_description": "Buffer overflow vulnerability",
            "task_difficulty": {"level0": [], "level1": [], "level2": [], "level3": []},
            "_cybergym_level": 1,
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "arvo:1234"
        assert (
            "vulnerability" in normalized.problem_statement.lower()
            or "exploit" in normalized.problem_statement.lower()
        )
        assert "owner/repo" in normalized.repo
        assert normalized.commit == "HEAD"

    def test_generate_problem_statement_level_0(self) -> None:
        """Test problem statement generation at level 0."""
        benchmark = CyberGymBenchmark(level=0)
        task = {
            "task_id": "arvo:123",
            "project_name": "test-project",
            "project_language": "c++",
            "vulnerability_description": "Test description",
            "_cybergym_level": 0,
        }

        statement = benchmark._generate_problem_statement(task)
        assert "test-project" in statement
        assert "arvo:123" in statement
        # Level 0 should be minimal
        assert len(statement) < 200

    def test_generate_problem_statement_level_3(self) -> None:
        """Test problem statement generation at level 3."""
        benchmark = CyberGymBenchmark(level=3)
        task = {
            "task_id": "arvo:123",
            "project_name": "test-project",
            "project_language": "c++",
            "vulnerability_description": "Test description",
            "_cybergym_level": 3,
        }

        statement = benchmark._generate_problem_statement(task)
        assert "test-project" in statement
        assert "arvo:123" in statement
        assert "c++" in statement
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


class TestMCPToolBenchmark:
    """Tests for MCPToolBench++ benchmark implementation."""

    def test_initialization(self) -> None:
        """Test MCPToolBench++ initialization."""
        benchmark = MCPToolBenchmark()
        assert benchmark.name == "mcptoolbench"
        assert benchmark.dataset == "MCPToolBench/MCPToolBenchPP"

    def test_custom_dataset(self) -> None:
        """Test MCPToolBench++ with custom dataset."""
        benchmark = MCPToolBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_normalize_task(self) -> None:
        """Test normalizing MCPToolBench++ task."""
        benchmark = MCPToolBenchmark()
        task = {
            "uuid": "test-uuid-123",
            "category": "browser",
            "call_type": "single",
            "query": "Navigate to example.com and click the submit button",
            "tools": ["navigate", "click"],
            "mcp_tools_dict": {"navigate": {}, "click": {}},
            "function_call_label": [{"name": "navigate", "parameters": {"url": "example.com"}}],
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "test-uuid-123"
        assert "Navigate to example.com" in normalized.problem_statement
        assert "mcptoolbench/browser" in normalized.repo
        assert normalized.commit == "HEAD"
        assert normalized.metadata["category"] == "browser"
        assert normalized.metadata["call_type"] == "single"

    def test_generate_problem_statement(self) -> None:
        """Test problem statement generation."""
        benchmark = MCPToolBenchmark()
        task = {
            "uuid": "test-123",
            "category": "finance",
            "call_type": "multi",
            "query": "Calculate portfolio returns",
            "tools": ["get_portfolio", "calculate_returns"],
        }

        statement = benchmark._generate_problem_statement(task)
        assert "finance" in statement
        assert "multi-step" in statement
        assert "Calculate portfolio returns" in statement
        assert "get_portfolio" in statement
        assert "calculate_returns" in statement

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image (should be None for MCPToolBench++)."""
        benchmark = MCPToolBenchmark()
        task = {"uuid": "test", "category": "browser"}
        image = benchmark.get_prebuilt_image(task)
        assert image is None

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = MCPToolBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "MCP" in prompt
        assert "tool" in prompt.lower()

    def test_extract_tool_calls_from_json(self) -> None:
        """Test extracting tool calls from JSON solution."""
        benchmark = MCPToolBenchmark()
        solution = '[{"name": "navigate", "parameters": {"url": "test.com"}}]'
        calls = benchmark._extract_tool_calls(solution)
        assert len(calls) == 1
        assert calls[0]["name"] == "navigate"

    def test_evaluate_tool_calls_exact_match(self) -> None:
        """Test evaluating tool calls with exact match."""
        benchmark = MCPToolBenchmark()
        agent_calls = [{"name": "navigate", "parameters": {"url": "test.com"}}]
        ground_truth = [{"name": "navigate", "parameters": {"url": "test.com"}}]

        result = benchmark._evaluate_tool_calls(agent_calls, ground_truth)
        assert result["correct"] is True
        assert result["tool_selection_accuracy"] == 1.0
        assert result["parameter_accuracy"] == 1.0
        assert result["sequence_match"] is True

    def test_evaluate_tool_calls_wrong_tool(self) -> None:
        """Test evaluating tool calls with wrong tool selected."""
        benchmark = MCPToolBenchmark()
        agent_calls = [{"name": "click", "parameters": {"selector": "button"}}]
        ground_truth = [{"name": "navigate", "parameters": {"url": "test.com"}}]

        result = benchmark._evaluate_tool_calls(agent_calls, ground_truth)
        assert result["correct"] is False
        assert result["tool_selection_accuracy"] == 0.0

    def test_evaluate_tool_calls_no_calls(self) -> None:
        """Test evaluating when agent makes no tool calls."""
        benchmark = MCPToolBenchmark()
        agent_calls = []
        ground_truth = [{"name": "navigate", "parameters": {"url": "test.com"}}]

        result = benchmark._evaluate_tool_calls(agent_calls, ground_truth)
        assert result["correct"] is False
        assert result["tool_selection_accuracy"] == 0.0
        assert "no tool calls" in result["details"].lower()


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

    def test_mcptoolbench_implements_protocol(self) -> None:
        """Test that MCPToolBenchmark implements Benchmark protocol."""
        benchmark = MCPToolBenchmark()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")
