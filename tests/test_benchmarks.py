"""Tests for benchmark abstraction and implementations."""

import pytest

from mcpbr.benchmarks import (
    AgentBenchBenchmark,
    AiderPolyglotBenchmark,
    APPSBenchmark,
    ARCBenchmark,
    Benchmark,
    BigBenchHardBenchmark,
    BigCodeBenchBenchmark,
    CodeContestsBenchmark,
    CoderEvalBenchmark,
    CyberGymBenchmark,
    GAIABenchmark,
    GSM8KBenchmark,
    HellaSwagBenchmark,
    HumanEvalBenchmark,
    InterCodeBenchmark,
    LeetCodeBenchmark,
    MATHBenchmark,
    MBPPBenchmark,
    MCPToolBenchmark,
    MLAgentBenchBenchmark,
    RepoQABenchmark,
    SWEBenchmark,
    TerminalBenchBenchmark,
    ToolBenchBenchmark,
    TruthfulQABenchmark,
    WebArenaBenchmark,
    create_benchmark,
    list_benchmarks,
)


class TestBenchmarkRegistry:
    """Tests for benchmark registry and factory."""

    def test_list_benchmarks(self) -> None:
        """Test listing available benchmarks."""
        benchmarks = list_benchmarks()
        assert "swe-bench-lite" in benchmarks
        assert "swe-bench-verified" in benchmarks
        assert "swe-bench-full" in benchmarks
        assert "cybergym" in benchmarks
        assert "humaneval" in benchmarks
        assert "mcptoolbench" in benchmarks
        assert "gsm8k" in benchmarks
        assert "mbpp" in benchmarks
        assert "math" in benchmarks
        assert "truthfulqa" in benchmarks
        assert "bigbench-hard" in benchmarks
        assert "hellaswag" in benchmarks
        assert "arc" in benchmarks
        assert "apps" in benchmarks
        assert "codecontests" in benchmarks
        assert "bigcodebench" in benchmarks
        assert "leetcode" in benchmarks
        assert "codereval" in benchmarks
        assert "repoqa" in benchmarks
        assert "toolbench" in benchmarks
        assert "aider-polyglot" in benchmarks
        assert "terminalbench" in benchmarks
        assert "gaia" in benchmarks
        assert "agentbench" in benchmarks
        assert "webarena" in benchmarks
        assert "mlagentbench" in benchmarks
        assert "intercode" in benchmarks
        assert len(benchmarks) >= 27

    def test_create_swebench_lite(self) -> None:
        """Test creating SWE-bench Lite benchmark."""
        benchmark = create_benchmark("swe-bench-lite")
        assert isinstance(benchmark, SWEBenchmark)
        assert benchmark.name == "swe-bench"
        assert benchmark.dataset == "SWE-bench/SWE-bench_Lite"

    def test_create_swebench_verified(self) -> None:
        """Test creating SWE-bench Verified benchmark."""
        benchmark = create_benchmark("swe-bench-verified")
        assert isinstance(benchmark, SWEBenchmark)
        assert benchmark.name == "swe-bench"
        assert benchmark.dataset == "SWE-bench/SWE-bench_Verified"

    def test_create_swebench_full(self) -> None:
        """Test creating SWE-bench Full benchmark."""
        benchmark = create_benchmark("swe-bench-full")
        assert isinstance(benchmark, SWEBenchmark)
        assert benchmark.name == "swe-bench"
        assert benchmark.dataset == "SWE-bench/SWE-bench"

    def test_create_cybergym(self) -> None:
        """Test creating CyberGym benchmark."""
        benchmark = create_benchmark("cybergym")
        assert isinstance(benchmark, CyberGymBenchmark)
        assert benchmark.name == "cybergym"

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

    def test_create_gsm8k(self) -> None:
        """Test creating GSM8K benchmark."""
        benchmark = create_benchmark("gsm8k")
        assert isinstance(benchmark, GSM8KBenchmark)
        assert benchmark.name == "gsm8k"

    def test_create_gsm8k_with_custom_dataset(self) -> None:
        """Test creating GSM8K with custom dataset."""
        benchmark = create_benchmark("gsm8k", dataset="custom/dataset")
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


class TestHumanEvalBenchmark:
    """Tests for HumanEval benchmark implementation."""

    def test_initialization(self) -> None:
        """Test HumanEval initialization."""
        benchmark = HumanEvalBenchmark()
        assert benchmark.name == "humaneval"
        assert benchmark.dataset == "openai_humaneval"

    def test_custom_dataset(self) -> None:
        """Test HumanEval with custom dataset."""
        benchmark = HumanEvalBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_normalize_task(self) -> None:
        """Test normalizing HumanEval task."""
        benchmark = HumanEvalBenchmark()
        task = {
            "task_id": "HumanEval/0",
            "prompt": "def example(x):\n    '''Example function'''\n    pass",
            "entry_point": "example",
            "canonical_solution": "    return x",
            "test": "def check(candidate):\n    assert candidate(1) == 1",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "HumanEval_0"
        assert "Complete the following Python function" in normalized.problem_statement
        assert normalized.repo == "openai/humaneval"
        assert normalized.commit == "HEAD"
        assert normalized.metadata["entry_point"] == "example"

    def test_generate_problem_statement(self) -> None:
        """Test problem statement generation."""
        benchmark = HumanEvalBenchmark()
        task = {
            "task_id": "HumanEval/0",
            "prompt": "def add(a, b):\n    '''Add two numbers'''\n    pass",
            "entry_point": "add",
        }

        statement = benchmark._generate_problem_statement(task)
        assert "HumanEval/0" in statement
        assert "def add(a, b)" in statement
        assert "solution.py" in statement
        assert "entry_point" in statement.lower() or "add" in statement

    def test_extract_code_from_markdown(self) -> None:
        """Test extracting code from markdown solution."""
        benchmark = HumanEvalBenchmark()
        solution = """
Here is the solution:

```python
def add(a, b):
    return a + b
```

This should work!
"""
        code = benchmark._extract_code_from_solution(solution)
        assert code is not None
        assert "def add(a, b):" in code
        assert "return a + b" in code

    def test_extract_code_from_plain_text(self) -> None:
        """Test extracting code from plain text solution."""
        benchmark = HumanEvalBenchmark()
        solution = """
def add(a, b):
    return a + b
"""
        code = benchmark._extract_code_from_solution(solution)
        assert code is not None
        assert "def add(a, b):" in code
        assert "return a + b" in code

    def test_extract_code_returns_none_for_no_code(self) -> None:
        """Test that code extraction returns None when no code found."""
        benchmark = HumanEvalBenchmark()
        solution = "This is just text without any code."
        code = benchmark._extract_code_from_solution(solution)
        assert code is None

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image (should be None for HumanEval)."""
        benchmark = HumanEvalBenchmark()
        task = {"task_id": "HumanEval/0"}
        image = benchmark.get_prebuilt_image(task)
        assert image is None

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = HumanEvalBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "solution.py" in prompt
        assert "function" in prompt.lower()
        assert "implement" in prompt.lower()

    def test_create_humaneval_benchmark(self) -> None:
        """Test creating HumanEval benchmark via factory."""
        benchmark = create_benchmark("humaneval")
        assert isinstance(benchmark, HumanEvalBenchmark)
        assert benchmark.name == "humaneval"

    def test_create_humaneval_with_custom_dataset(self) -> None:
        """Test creating HumanEval with custom dataset via factory."""
        benchmark = create_benchmark("humaneval", dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"


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

    def test_gsm8k_implements_protocol(self) -> None:
        """Test that GSM8KBenchmark implements Benchmark protocol."""
        benchmark = GSM8KBenchmark()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")

    def test_humaneval_implements_protocol(self) -> None:
        """Test that HumanEvalBenchmark implements Benchmark protocol."""
        benchmark = HumanEvalBenchmark()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")


class TestGSM8KBenchmark:
    """Tests for GSM8K benchmark implementation."""

    def test_initialization(self) -> None:
        """Test GSM8K initialization."""
        benchmark = GSM8KBenchmark()
        assert benchmark.name == "gsm8k"
        assert benchmark.dataset == "openai/gsm8k"
        assert benchmark.subset == "main"

    def test_custom_dataset(self) -> None:
        """Test GSM8K with custom dataset."""
        benchmark = GSM8KBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_custom_subset(self) -> None:
        """Test GSM8K with custom subset."""
        benchmark = GSM8KBenchmark(subset="socratic")
        assert benchmark.subset == "socratic"

    def test_normalize_task(self) -> None:
        """Test normalizing GSM8K task."""
        benchmark = GSM8KBenchmark()
        task = {
            "instance_id": "gsm8k_0",
            "question": "Janet has 5 apples. She buys 3 more. How many apples does she have?",
            "answer": "#### 8",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "gsm8k_0"
        assert "Janet has 5 apples" in normalized.problem_statement
        assert normalized.repo == "gsm8k/math"
        assert normalized.commit == "HEAD"
        assert normalized.metadata["question"] == task["question"]
        assert normalized.metadata["answer"] == task["answer"]
        assert normalized.metadata["ground_truth_numeric"] == 8.0

    def test_normalize_task_missing_instance_id(self) -> None:
        """Test normalizing task without instance_id raises error."""
        benchmark = GSM8KBenchmark()
        task = {
            "question": "What is 2+2?",
            "answer": "#### 4",
        }

        with pytest.raises(ValueError, match="missing required 'instance_id' field"):
            benchmark.normalize_task(task)

    def test_normalize_task_missing_question(self) -> None:
        """Test normalizing task without question raises error."""
        benchmark = GSM8KBenchmark()
        task = {
            "instance_id": "gsm8k_0",
            "answer": "#### 4",
        }

        with pytest.raises(ValueError, match="missing required 'question' field"):
            benchmark.normalize_task(task)

    def test_generate_problem_statement(self) -> None:
        """Test problem statement generation."""
        benchmark = GSM8KBenchmark()
        task = {
            "question": "If a train travels 60 miles per hour for 2 hours, how far does it go?",
        }

        statement = benchmark._generate_problem_statement(task)
        assert "Solve the following math problem" in statement
        assert "train travels 60 miles per hour" in statement
        assert "chain-of-thought" in statement
        assert "final numeric answer" in statement

    def test_extract_answer_gsm8k_format(self) -> None:
        """Test extracting answer in GSM8K format (#### number)."""
        benchmark = GSM8KBenchmark()

        # Standard GSM8K format
        text = "First, add 5 + 3 = 8\n#### 8"
        assert benchmark._extract_answer(text) == 8.0

        # With decimal
        text = "The area is 3.14 square meters\n#### 3.14"
        assert benchmark._extract_answer(text) == 3.14

        # With negative number
        text = "The temperature dropped to #### -5"
        assert benchmark._extract_answer(text) == -5.0

        # With comma
        text = "The total is #### 1,234"
        assert benchmark._extract_answer(text) == 1234.0

    def test_extract_answer_boxed_format(self) -> None:
        """Test extracting answer in LaTeX boxed format."""
        benchmark = GSM8KBenchmark()

        text = "Therefore, the answer is \\boxed{42}"
        assert benchmark._extract_answer(text) == 42.0

        text = "The solution is \\boxed{3.14159}"
        assert benchmark._extract_answer(text) == 3.14159

    def test_extract_answer_sentence_format(self) -> None:
        """Test extracting answer from sentence patterns."""
        benchmark = GSM8KBenchmark()

        # "The answer is X"
        text = "After calculation, the answer is 42."
        assert benchmark._extract_answer(text) == 42.0

        # "Final answer: X"
        text = "Step 1: ... Step 2: ... Final answer: 123"
        assert benchmark._extract_answer(text) == 123.0

        # With dollar sign
        text = "The total cost is $1,234.56"
        assert benchmark._extract_answer(text) == 1234.56

    def test_extract_answer_last_number(self) -> None:
        """Test extracting last number as fallback."""
        benchmark = GSM8KBenchmark()

        text = "We have 5 apples, then 3 more, so 8 total."
        assert benchmark._extract_answer(text) == 8.0

    def test_extract_answer_no_number(self) -> None:
        """Test extracting answer when no number present."""
        benchmark = GSM8KBenchmark()

        text = "I don't know the answer."
        assert benchmark._extract_answer(text) is None

        text = ""
        assert benchmark._extract_answer(text) is None

    def test_parse_number(self) -> None:
        """Test parsing various number formats."""
        benchmark = GSM8KBenchmark()

        # Simple integers
        assert benchmark._parse_number("42") == 42.0
        assert benchmark._parse_number("0") == 0.0

        # Decimals
        assert benchmark._parse_number("3.14") == 3.14
        assert benchmark._parse_number("0.5") == 0.5

        # With commas
        assert benchmark._parse_number("1,234") == 1234.0
        assert benchmark._parse_number("1,234,567") == 1234567.0

        # With dollar sign
        assert benchmark._parse_number("$42") == 42.0
        assert benchmark._parse_number("$1,234.56") == 1234.56

        # Negative numbers
        assert benchmark._parse_number("-42") == -42.0
        assert benchmark._parse_number("-3.14") == -3.14

        # Invalid
        assert benchmark._parse_number("abc") is None
        assert benchmark._parse_number("") is None

    def test_compare_answers_exact(self) -> None:
        """Test comparing answers with exact match."""
        benchmark = GSM8KBenchmark()

        assert benchmark._compare_answers(42.0, 42.0) is True
        assert benchmark._compare_answers(0.0, 0.0) is True
        assert benchmark._compare_answers(-5.0, -5.0) is True

    def test_compare_answers_with_tolerance(self) -> None:
        """Test comparing answers with small differences."""
        benchmark = GSM8KBenchmark()

        # Within absolute tolerance (0.001)
        assert benchmark._compare_answers(42.0, 42.0005) is True
        assert benchmark._compare_answers(0.0, 0.0005) is True

        # Within relative tolerance (0.1%)
        assert benchmark._compare_answers(1000.0, 1000.5) is True

        # Outside tolerance
        assert benchmark._compare_answers(42.0, 43.0) is False
        assert benchmark._compare_answers(100.0, 105.0) is False

    def test_compare_answers_different_signs(self) -> None:
        """Test comparing answers with different signs."""
        benchmark = GSM8KBenchmark()

        assert benchmark._compare_answers(42.0, -42.0) is False
        assert benchmark._compare_answers(-5.0, 5.0) is False

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image (should be None for GSM8K)."""
        benchmark = GSM8KBenchmark()
        task = {"instance_id": "gsm8k_0"}
        image = benchmark.get_prebuilt_image(task)
        assert image is None

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = GSM8KBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "grade-school math" in prompt.lower()
        assert "chain-of-thought" in prompt.lower()
        assert "final numeric answer" in prompt.lower()

    def test_evaluate_correct_answer(self) -> None:
        """Test evaluation with correct answer."""
        benchmark = GSM8KBenchmark()
        task = {
            "instance_id": "gsm8k_0",
            "question": "What is 2 + 2?",
            "answer": "#### 4",
        }
        solution = "Let me solve this step by step:\n2 + 2 = 4\nThe answer is: 4"

        # This would be async in real code, but we can test the logic
        result = benchmark._extract_answer(solution)
        assert result == 4.0

        ground_truth = benchmark._extract_answer(task["answer"])
        assert ground_truth == 4.0

        assert benchmark._compare_answers(result, ground_truth) is True

    def test_evaluate_incorrect_answer(self) -> None:
        """Test evaluation with incorrect answer."""
        benchmark = GSM8KBenchmark()
        task = {
            "instance_id": "gsm8k_0",
            "question": "What is 2 + 2?",
            "answer": "#### 4",
        }
        solution = "Let me solve this:\n2 + 2 = 5\nThe answer is: 5"

        result = benchmark._extract_answer(solution)
        assert result == 5.0

        ground_truth = benchmark._extract_answer(task["answer"])
        assert ground_truth == 4.0

        assert benchmark._compare_answers(result, ground_truth) is False

    def test_evaluate_no_answer_extracted(self) -> None:
        """Test evaluation when no answer can be extracted."""
        benchmark = GSM8KBenchmark()

        solution = "I don't understand this problem."
        result = benchmark._extract_answer(solution)
        assert result is None

    def test_edge_case_large_numbers(self) -> None:
        """Test handling of large numbers."""
        benchmark = GSM8KBenchmark()

        text = "The population is #### 7,890,123"
        assert benchmark._extract_answer(text) == 7890123.0

        text = "The answer is 1,000,000"
        assert benchmark._extract_answer(text) == 1000000.0

    def test_edge_case_small_decimals(self) -> None:
        """Test handling of small decimal numbers."""
        benchmark = GSM8KBenchmark()

        text = "The probability is #### 0.0001"
        assert benchmark._extract_answer(text) == 0.0001

        # Compare with tolerance
        assert benchmark._compare_answers(0.0001, 0.00010001) is True

    def test_edge_case_scientific_notation(self) -> None:
        """Test that scientific notation is not currently supported."""
        benchmark = GSM8KBenchmark()

        # Scientific notation is not in the initial implementation
        text = "The answer is 1.23e5"
        # This will either return None or extract "1.23" depending on regex
        _ = benchmark._extract_answer(text)
        # We don't assert specific behavior since scientific notation
        # could be added in the future


class TestMBPPBenchmark:
    """Tests for MBPP benchmark implementation."""

    def test_initialization(self) -> None:
        """Test MBPP initialization."""
        benchmark = MBPPBenchmark()
        assert benchmark.name == "mbpp"
        assert benchmark.dataset == "google-research-datasets/mbpp"

    def test_custom_dataset(self) -> None:
        """Test MBPP with custom dataset."""
        benchmark = MBPPBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_normalize_task(self) -> None:
        """Test normalizing MBPP task."""
        benchmark = MBPPBenchmark()
        task = {
            "instance_id": "mbpp_1",
            "task_id": 1,
            "text": "Write a function to add two numbers",
            "code": "def add(a, b): return a + b",
            "test_list": ["assert add(1, 2) == 3"],
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "mbpp_1"
        assert "add two numbers" in normalized.problem_statement
        assert normalized.repo == "mbpp/code"

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = MBPPBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_get_prebuilt_image(self) -> None:
        """Test getting pre-built image (should be None)."""
        benchmark = MBPPBenchmark()
        assert benchmark.get_prebuilt_image({}) is None

    def test_create_via_factory(self) -> None:
        """Test creating MBPP via factory."""
        benchmark = create_benchmark("mbpp")
        assert isinstance(benchmark, MBPPBenchmark)

    def test_mbpp_in_list(self) -> None:
        """Test MBPP appears in benchmark list."""
        assert "mbpp" in list_benchmarks()


class TestMATHBenchmark:
    """Tests for MATH benchmark implementation."""

    def test_initialization(self) -> None:
        """Test MATH initialization."""
        benchmark = MATHBenchmark()
        assert benchmark.name == "math"
        assert benchmark.dataset == "DigitalLearningGmbH/MATH-lighteval"

    def test_normalize_task(self) -> None:
        """Test normalizing MATH task."""
        benchmark = MATHBenchmark()
        task = {
            "instance_id": "math_0",
            "problem": "Find the value of x if 2x + 3 = 7",
            "solution": "2x = 4, so x = \\boxed{2}",
            "level": "Level 1",
            "type": "Algebra",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "math_0"
        assert "2x + 3 = 7" in normalized.problem_statement

    def test_extract_boxed_answer(self) -> None:
        """Test extracting boxed answers."""
        benchmark = MATHBenchmark()
        assert benchmark._extract_boxed_answer("The answer is \\boxed{42}") == "42"
        assert benchmark._extract_boxed_answer("\\boxed{\\frac{1}{2}}") == "\\frac{1}{2}"

    def test_normalize_answer(self) -> None:
        """Test answer normalization."""
        benchmark = MATHBenchmark()
        assert benchmark._normalize_answer(" 42 ") == "42"
        assert benchmark._normalize_answer("\\left(1\\right)") == "(1)"

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = MATHBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "\\boxed" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating MATH via factory."""
        benchmark = create_benchmark("math")
        assert isinstance(benchmark, MATHBenchmark)


class TestTruthfulQABenchmark:
    """Tests for TruthfulQA benchmark implementation."""

    def test_initialization(self) -> None:
        """Test TruthfulQA initialization."""
        benchmark = TruthfulQABenchmark()
        assert benchmark.name == "truthfulqa"
        assert benchmark.dataset == "truthfulqa/truthful_qa"

    def test_normalize_task(self) -> None:
        """Test normalizing TruthfulQA task."""
        benchmark = TruthfulQABenchmark()
        task = {
            "instance_id": "truthfulqa_0",
            "question": "What happens if you eat watermelon seeds?",
            "category": "Health",
            "best_answer": "Nothing bad happens",
            "correct_answers": ["Nothing bad happens", "They pass through your body"],
            "incorrect_answers": ["A watermelon grows in your stomach"],
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "truthfulqa_0"
        assert "watermelon seeds" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = TruthfulQABenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt
        assert "truthful" in prompt.lower()

    def test_create_via_factory(self) -> None:
        """Test creating TruthfulQA via factory."""
        benchmark = create_benchmark("truthfulqa")
        assert isinstance(benchmark, TruthfulQABenchmark)


class TestBigBenchHardBenchmark:
    """Tests for BigBench-Hard benchmark implementation."""

    def test_initialization(self) -> None:
        """Test BBH initialization."""
        benchmark = BigBenchHardBenchmark()
        assert benchmark.name == "bigbench-hard"
        assert benchmark.dataset == "lukaemon/bbh"

    def test_normalize_task(self) -> None:
        """Test normalizing BBH task."""
        benchmark = BigBenchHardBenchmark()
        task = {
            "instance_id": "bbh_boolean_expressions_0",
            "input": "Evaluate: True and False",
            "target": "False",
            "subtask": "boolean_expressions",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "bbh_boolean_expressions_0"
        assert "True and False" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = BigBenchHardBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating BBH via factory."""
        benchmark = create_benchmark("bigbench-hard")
        assert isinstance(benchmark, BigBenchHardBenchmark)


class TestHellaSwagBenchmark:
    """Tests for HellaSwag benchmark implementation."""

    def test_initialization(self) -> None:
        """Test HellaSwag initialization."""
        benchmark = HellaSwagBenchmark()
        assert benchmark.name == "hellaswag"
        assert benchmark.dataset == "Rowan/hellaswag"

    def test_normalize_task(self) -> None:
        """Test normalizing HellaSwag task."""
        benchmark = HellaSwagBenchmark()
        task = {
            "instance_id": "hellaswag_0",
            "ctx": "A person is cooking dinner.",
            "endings": ["They eat.", "They fly.", "They sleep.", "They swim."],
            "label": "0",
            "activity_label": "cooking",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "hellaswag_0"
        assert "cooking dinner" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = HellaSwagBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating HellaSwag via factory."""
        benchmark = create_benchmark("hellaswag")
        assert isinstance(benchmark, HellaSwagBenchmark)


class TestARCBenchmark:
    """Tests for ARC benchmark implementation."""

    def test_initialization(self) -> None:
        """Test ARC initialization."""
        benchmark = ARCBenchmark()
        assert benchmark.name == "arc"
        assert benchmark.dataset == "allenai/ai2_arc"
        assert benchmark.subset == "ARC-Challenge"

    def test_custom_subset(self) -> None:
        """Test ARC with custom subset."""
        benchmark = ARCBenchmark(subset="ARC-Easy")
        assert benchmark.subset == "ARC-Easy"

    def test_normalize_task(self) -> None:
        """Test normalizing ARC task."""
        benchmark = ARCBenchmark()
        task = {
            "instance_id": "arc_123",
            "id": "123",
            "question": "What causes seasons on Earth?",
            "choices": {
                "label": ["A", "B", "C", "D"],
                "text": ["The Moon", "Earth's tilt", "The Sun", "Wind"],
            },
            "answerKey": "B",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "arc_123"
        assert "seasons" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = ARCBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating ARC via factory."""
        benchmark = create_benchmark("arc")
        assert isinstance(benchmark, ARCBenchmark)


class TestAPPSBenchmark:
    """Tests for APPS benchmark implementation."""

    def test_initialization(self) -> None:
        """Test APPS initialization."""
        benchmark = APPSBenchmark()
        assert benchmark.name == "apps"
        assert benchmark.dataset == "metr-evals/apps"

    def test_normalize_task(self) -> None:
        """Test normalizing APPS task."""
        benchmark = APPSBenchmark()
        task = {
            "instance_id": "apps_0",
            "question": "Read N integers and print their sum.",
            "difficulty": "introductory",
            "input_output": '{"inputs": ["3\\n1 2 3"], "outputs": ["6"]}',
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "apps_0"
        assert "sum" in normalized.problem_statement.lower()

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = APPSBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating APPS via factory."""
        benchmark = create_benchmark("apps")
        assert isinstance(benchmark, APPSBenchmark)


class TestCodeContestsBenchmark:
    """Tests for CodeContests benchmark implementation."""

    def test_initialization(self) -> None:
        """Test CodeContests initialization."""
        benchmark = CodeContestsBenchmark()
        assert benchmark.name == "codecontests"
        assert benchmark.dataset == "deepmind/code_contests"

    def test_normalize_task(self) -> None:
        """Test normalizing CodeContests task."""
        benchmark = CodeContestsBenchmark()
        task = {
            "instance_id": "codecontests_abc123",
            "name": "abc123",
            "description": "Find the shortest path in a graph.",
            "difficulty": 3,
            "source": "codeforces",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "codecontests_abc123"
        assert "shortest path" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = CodeContestsBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating CodeContests via factory."""
        benchmark = create_benchmark("codecontests")
        assert isinstance(benchmark, CodeContestsBenchmark)


class TestBigCodeBenchBenchmark:
    """Tests for BigCodeBench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test BigCodeBench initialization."""
        benchmark = BigCodeBenchBenchmark()
        assert benchmark.name == "bigcodebench"
        assert benchmark.dataset == "bigcode/bigcodebench"

    def test_normalize_task(self) -> None:
        """Test normalizing BigCodeBench task."""
        benchmark = BigCodeBenchBenchmark()
        task = {
            "instance_id": "bigcodebench_task_0",
            "task_id": "task_0",
            "instruct_prompt": "Implement a function that sorts a list",
            "libs": ["numpy", "pandas"],
            "test": "assert sort_list([3,1,2]) == [1,2,3]",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "bigcodebench_task_0"

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = BigCodeBenchBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating BigCodeBench via factory."""
        benchmark = create_benchmark("bigcodebench")
        assert isinstance(benchmark, BigCodeBenchBenchmark)


class TestLeetCodeBenchmark:
    """Tests for LeetCode benchmark implementation."""

    def test_initialization(self) -> None:
        """Test LeetCode initialization."""
        benchmark = LeetCodeBenchmark()
        assert benchmark.name == "leetcode"
        assert benchmark.dataset == "greengerong/leetcode"

    def test_normalize_task(self) -> None:
        """Test normalizing LeetCode task."""
        benchmark = LeetCodeBenchmark()
        task = {
            "instance_id": "leetcode_1",
            "id": "1",
            "title": "Two Sum",
            "content": "Given an array of integers...",
            "difficulty": "Easy",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "leetcode_1"
        assert "Two Sum" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = LeetCodeBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating LeetCode via factory."""
        benchmark = create_benchmark("leetcode")
        assert isinstance(benchmark, LeetCodeBenchmark)


class TestCoderEvalBenchmark:
    """Tests for CoderEval benchmark implementation."""

    def test_initialization(self) -> None:
        """Test CoderEval initialization."""
        benchmark = CoderEvalBenchmark()
        assert benchmark.name == "codereval"
        assert benchmark.dataset == "CoderEval/CoderEval"

    def test_normalize_task(self) -> None:
        """Test normalizing CoderEval task."""
        benchmark = CoderEvalBenchmark()
        task = {
            "instance_id": "codereval_0",
            "task_id": "0",
            "function_name": "parse_config",
            "language": "Python",
            "repo": "example/repo",
            "commit": "abc123",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "codereval_0"
        assert "parse_config" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = CoderEvalBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating CoderEval via factory."""
        benchmark = create_benchmark("codereval")
        assert isinstance(benchmark, CoderEvalBenchmark)


class TestRepoQABenchmark:
    """Tests for RepoQA benchmark implementation."""

    def test_initialization(self) -> None:
        """Test RepoQA initialization."""
        benchmark = RepoQABenchmark()
        assert benchmark.name == "repoqa"
        assert benchmark.dataset == "evaluating/RepoQA"

    def test_normalize_task(self) -> None:
        """Test normalizing RepoQA task."""
        benchmark = RepoQABenchmark()
        task = {
            "instance_id": "repoqa_0",
            "function_name": "calculate_metrics",
            "language": "Python",
            "description": "Calculates evaluation metrics",
            "repo": "example/repo",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "repoqa_0"
        assert (
            "calculate_metrics" in normalized.problem_statement
            or "evaluation" in normalized.problem_statement.lower()
        )

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = RepoQABenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating RepoQA via factory."""
        benchmark = create_benchmark("repoqa")
        assert isinstance(benchmark, RepoQABenchmark)


class TestToolBenchBenchmark:
    """Tests for ToolBench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test ToolBench initialization."""
        benchmark = ToolBenchBenchmark()
        assert benchmark.name == "toolbench"
        assert benchmark.dataset == "tuandunghcmut/toolbench-v1"

    def test_normalize_task(self) -> None:
        """Test normalizing ToolBench task."""
        benchmark = ToolBenchBenchmark()
        task = {
            "instance_id": "toolbench_0",
            "id": "0",
            "query": "Get the weather for New York",
            "tools": [{"name": "get_weather", "description": "Get weather data"}],
            "category": "weather",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "toolbench_0"
        assert "weather" in normalized.problem_statement.lower()

    def test_extract_tool_calls_json(self) -> None:
        """Test extracting tool calls from JSON."""
        benchmark = ToolBenchBenchmark()
        solution = '[{"name": "get_weather", "parameters": {"city": "NYC"}}]'
        calls = benchmark._extract_tool_calls(solution)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_weather"

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = ToolBenchBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating ToolBench via factory."""
        benchmark = create_benchmark("toolbench")
        assert isinstance(benchmark, ToolBenchBenchmark)


class TestAiderPolyglotBenchmark:
    """Tests for Aider Polyglot benchmark implementation."""

    def test_initialization(self) -> None:
        """Test Aider Polyglot initialization."""
        benchmark = AiderPolyglotBenchmark()
        assert benchmark.name == "aider-polyglot"
        assert benchmark.dataset == "aider-ai/polyglot-benchmark"

    def test_normalize_task(self) -> None:
        """Test normalizing Aider Polyglot task."""
        benchmark = AiderPolyglotBenchmark()
        task = {
            "instance_id": "aider_0",
            "task_id": "0",
            "exercise": "hello-world",
            "language": "python",
            "source_file": "hello_world.py",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "aider_0"
        assert "hello-world" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = AiderPolyglotBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating Aider Polyglot via factory."""
        benchmark = create_benchmark("aider-polyglot")
        assert isinstance(benchmark, AiderPolyglotBenchmark)


class TestTerminalBenchBenchmark:
    """Tests for TerminalBench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test TerminalBench initialization."""
        benchmark = TerminalBenchBenchmark()
        assert benchmark.name == "terminalbench"
        assert benchmark.dataset == "ia03/terminal-bench"

    def test_normalize_task(self) -> None:
        """Test normalizing TerminalBench task."""
        benchmark = TerminalBenchBenchmark()
        task = {
            "instance_id": "terminalbench_0",
            "task_id": "0",
            "instruction": "Create a directory named 'test'",
            "category": "file_operations",
            "validation_command": "test -d test",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "terminalbench_0"
        assert "directory" in normalized.problem_statement.lower()

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = TerminalBenchBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating TerminalBench via factory."""
        benchmark = create_benchmark("terminalbench")
        assert isinstance(benchmark, TerminalBenchBenchmark)


class TestGAIABenchmark:
    """Tests for GAIA benchmark implementation."""

    def test_initialization(self) -> None:
        """Test GAIA initialization."""
        benchmark = GAIABenchmark()
        assert benchmark.name == "gaia"
        assert benchmark.dataset == "gaia-benchmark/GAIA"

    def test_normalize_task(self) -> None:
        """Test normalizing GAIA task."""
        benchmark = GAIABenchmark()
        task = {
            "instance_id": "gaia_0",
            "task_id": "0",
            "Question": "What is the capital of France?",
            "Level": 1,
            "Final answer": "Paris",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "gaia_0"
        assert "capital of France" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = GAIABenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating GAIA via factory."""
        benchmark = create_benchmark("gaia")
        assert isinstance(benchmark, GAIABenchmark)


class TestAgentBenchBenchmark:
    """Tests for AgentBench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test AgentBench initialization."""
        benchmark = AgentBenchBenchmark()
        assert benchmark.name == "agentbench"
        assert benchmark.dataset == "THUDM/AgentBench"

    def test_normalize_task(self) -> None:
        """Test normalizing AgentBench task."""
        benchmark = AgentBenchBenchmark()
        task = {
            "instance_id": "agentbench_0",
            "task_id": "0",
            "environment": "os",
            "instruction": "List all files in the current directory",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "agentbench_0"
        assert "os" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = AgentBenchBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating AgentBench via factory."""
        benchmark = create_benchmark("agentbench")
        assert isinstance(benchmark, AgentBenchBenchmark)


class TestWebArenaBenchmark:
    """Tests for WebArena benchmark implementation."""

    def test_initialization(self) -> None:
        """Test WebArena initialization."""
        benchmark = WebArenaBenchmark()
        assert benchmark.name == "webarena"
        assert benchmark.dataset == "WebArena/WebArena"

    def test_normalize_task(self) -> None:
        """Test normalizing WebArena task."""
        benchmark = WebArenaBenchmark()
        task = {
            "instance_id": "webarena_0",
            "task_id": "0",
            "intent": "Find the cheapest laptop on the shopping site",
            "sites": ["shopping"],
            "eval": {"eval_types": ["string_match"], "reference_answers": "Laptop X"},
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "webarena_0"
        assert "laptop" in normalized.problem_statement.lower()

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = WebArenaBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating WebArena via factory."""
        benchmark = create_benchmark("webarena")
        assert isinstance(benchmark, WebArenaBenchmark)


class TestMLAgentBenchBenchmark:
    """Tests for MLAgentBench benchmark implementation."""

    def test_initialization(self) -> None:
        """Test MLAgentBench initialization."""
        benchmark = MLAgentBenchBenchmark()
        assert benchmark.name == "mlagentbench"
        assert benchmark.dataset == "MLAgentBench/MLAgentBench"

    def test_normalize_task(self) -> None:
        """Test normalizing MLAgentBench task."""
        benchmark = MLAgentBenchBenchmark()
        task = {
            "instance_id": "mlagentbench_0",
            "task_id": "0",
            "research_problem": "Improve model accuracy on CIFAR-10",
            "domain": "cv",
            "metric": "accuracy",
            "baseline_score": 0.85,
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "mlagentbench_0"
        assert "CIFAR-10" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = MLAgentBenchBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating MLAgentBench via factory."""
        benchmark = create_benchmark("mlagentbench")
        assert isinstance(benchmark, MLAgentBenchBenchmark)


class TestInterCodeBenchmark:
    """Tests for InterCode benchmark implementation."""

    def test_initialization(self) -> None:
        """Test InterCode initialization."""
        benchmark = InterCodeBenchmark()
        assert benchmark.name == "intercode"
        assert benchmark.dataset == "intercode-benchmark/intercode"

    def test_normalize_task(self) -> None:
        """Test normalizing InterCode task."""
        benchmark = InterCodeBenchmark()
        task = {
            "instance_id": "intercode_0",
            "task_id": "0",
            "query": "Find all .py files in the current directory",
            "environment": "bash",
            "gold_solution": "find . -name '*.py'",
        }
        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "intercode_0"
        assert "bash" in normalized.problem_statement

    def test_get_prompt_template(self) -> None:
        """Test getting prompt template."""
        benchmark = InterCodeBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_create_via_factory(self) -> None:
        """Test creating InterCode via factory."""
        benchmark = create_benchmark("intercode")
        assert isinstance(benchmark, InterCodeBenchmark)


class TestNewBenchmarkProtocol:
    """Tests for protocol compliance of all new benchmarks."""

    @pytest.mark.parametrize(
        "benchmark_class",
        [
            MBPPBenchmark,
            MATHBenchmark,
            TruthfulQABenchmark,
            BigBenchHardBenchmark,
            HellaSwagBenchmark,
            ARCBenchmark,
            APPSBenchmark,
            CodeContestsBenchmark,
            BigCodeBenchBenchmark,
            LeetCodeBenchmark,
            CoderEvalBenchmark,
            RepoQABenchmark,
            ToolBenchBenchmark,
            AiderPolyglotBenchmark,
            TerminalBenchBenchmark,
            GAIABenchmark,
            AgentBenchBenchmark,
            WebArenaBenchmark,
            MLAgentBenchBenchmark,
            InterCodeBenchmark,
        ],
    )
    def test_implements_protocol(self, benchmark_class: type) -> None:
        """Test that benchmark implements the Benchmark protocol."""
        benchmark = benchmark_class()
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "name")
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")

    @pytest.mark.parametrize(
        "benchmark_name",
        [
            "mbpp",
            "math",
            "truthfulqa",
            "bigbench-hard",
            "hellaswag",
            "arc",
            "apps",
            "codecontests",
            "bigcodebench",
            "leetcode",
            "codereval",
            "repoqa",
            "toolbench",
            "aider-polyglot",
            "terminalbench",
            "gaia",
            "agentbench",
            "webarena",
            "mlagentbench",
            "intercode",
        ],
    )
    def test_in_registry(self, benchmark_name: str) -> None:
        """Test that benchmark is registered and listed."""
        benchmarks = list_benchmarks()
        assert benchmark_name in benchmarks

    @pytest.mark.parametrize(
        "benchmark_name",
        [
            "mbpp",
            "math",
            "truthfulqa",
            "bigbench-hard",
            "hellaswag",
            "arc",
            "apps",
            "codecontests",
            "bigcodebench",
            "leetcode",
            "codereval",
            "repoqa",
            "toolbench",
            "aider-polyglot",
            "terminalbench",
            "gaia",
            "agentbench",
            "webarena",
            "mlagentbench",
            "intercode",
        ],
    )
    def test_factory_creates(self, benchmark_name: str) -> None:
        """Test that factory creates the benchmark correctly."""
        benchmark = create_benchmark(benchmark_name)
        assert isinstance(benchmark, Benchmark)
        assert hasattr(benchmark, "name")
