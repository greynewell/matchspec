"""Tests for custom benchmark implementation loaded from YAML definitions."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from mcpbr.benchmarks.base import Benchmark
from mcpbr.benchmarks.custom import CustomBenchmark

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, definition: dict[str, Any]) -> Path:
    """Write a YAML definition to a temp file and return its path."""
    yaml_path = tmp_path / "benchmark.yaml"
    yaml_path.write_text(yaml.dump(definition))
    return yaml_path


def _minimal_definition(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid custom benchmark definition."""
    defn: dict[str, Any] = {
        "name": "test-bench",
        "dataset": "org/test-dataset",
        "evaluation_type": "exact_match",
    }
    defn.update(overrides)
    return defn


# ---------------------------------------------------------------------------
# YAML Parsing & Validation
# ---------------------------------------------------------------------------


class TestYAMLParsing:
    """Tests for YAML loading and field validation."""

    def test_load_from_yaml_file(self, tmp_path: Path) -> None:
        """Test loading a custom benchmark from a YAML file."""
        definition = _minimal_definition(
            subset="main",
            split="validation",
            task_id_field="task_id",
            problem_statement_field="prompt",
            answer_field="expected",
        )
        yaml_path = _write_yaml(tmp_path, definition)

        bench = CustomBenchmark(definition_path=yaml_path)

        assert bench.name == "test-bench"
        assert bench.dataset == "org/test-dataset"
        assert bench.subset == "main"
        assert bench.split == "validation"
        assert bench.task_id_field == "task_id"
        assert bench.problem_statement_field == "prompt"
        assert bench.answer_field == "expected"
        assert bench.evaluation_type == "exact_match"

    def test_load_from_kwargs(self) -> None:
        """Test constructing a benchmark from keyword arguments (no file)."""
        bench = CustomBenchmark(**_minimal_definition())
        assert bench.name == "test-bench"
        assert bench.dataset == "org/test-dataset"

    def test_kwargs_override_yaml(self, tmp_path: Path) -> None:
        """Test that kwargs override values from the YAML file."""
        definition = _minimal_definition(split="test")
        yaml_path = _write_yaml(tmp_path, definition)

        bench = CustomBenchmark(definition_path=yaml_path, split="train")
        assert bench.split == "train"

    def test_default_field_values(self) -> None:
        """Test that optional fields have sensible defaults."""
        bench = CustomBenchmark(**_minimal_definition())

        assert bench.subset is None
        assert bench.split == "test"
        assert bench.task_id_field == "id"
        assert bench.problem_statement_field == "question"
        assert bench.answer_field == "answer"
        assert bench.docker_image is None
        assert bench.setup_commands == []
        assert bench.prompt_template is None
        assert bench.evaluation_script is None

    def test_missing_required_field_name(self) -> None:
        """Test that missing 'name' raises ValueError."""
        defn = _minimal_definition()
        del defn["name"]
        with pytest.raises(ValueError, match=r"missing required fields.*name"):
            CustomBenchmark(**defn)

    def test_missing_required_field_dataset(self) -> None:
        """Test that missing 'dataset' raises ValueError."""
        defn = _minimal_definition()
        del defn["dataset"]
        with pytest.raises(ValueError, match=r"missing required fields.*dataset"):
            CustomBenchmark(**defn)

    def test_missing_required_field_evaluation_type(self) -> None:
        """Test that missing 'evaluation_type' raises ValueError."""
        defn = _minimal_definition()
        del defn["evaluation_type"]
        with pytest.raises(ValueError, match=r"missing required fields.*evaluation_type"):
            CustomBenchmark(**defn)

    def test_invalid_evaluation_type(self) -> None:
        """Test that an unsupported evaluation_type raises ValueError."""
        defn = _minimal_definition(evaluation_type="fuzzy_match")
        with pytest.raises(ValueError, match="Invalid evaluation_type"):
            CustomBenchmark(**defn)

    def test_script_eval_requires_evaluation_script(self) -> None:
        """Test that evaluation_type=script requires evaluation_script field."""
        defn = _minimal_definition(evaluation_type="script")
        with pytest.raises(ValueError, match="evaluation_script is required"):
            CustomBenchmark(**defn)

    def test_regex_eval_requires_regex_pattern(self) -> None:
        """Test that evaluation_type=regex requires regex_pattern field."""
        defn = _minimal_definition(evaluation_type="regex")
        with pytest.raises(ValueError, match="regex_pattern is required"):
            CustomBenchmark(**defn)

    def test_script_eval_with_script_is_valid(self) -> None:
        """Test that script evaluation with a script defined is valid."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="script",
                evaluation_script="python3 /tmp/eval.py",
            )
        )
        assert bench.evaluation_type == "script"
        assert bench.evaluation_script == "python3 /tmp/eval.py"

    def test_regex_eval_with_pattern_is_valid(self) -> None:
        """Test that regex evaluation with a pattern defined is valid."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"answer:\s*(\S+)",
            )
        )
        assert bench.evaluation_type == "regex"
        assert bench.regex_pattern == r"answer:\s*(\S+)"

    def test_file_not_found(self) -> None:
        """Test that a non-existent YAML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Custom benchmark definition not found"):
            CustomBenchmark(definition_path="/nonexistent/path/benchmark.yaml")

    def test_setup_commands_loaded(self, tmp_path: Path) -> None:
        """Test that setup_commands are loaded from YAML."""
        definition = _minimal_definition(setup_commands=["apt-get update", "pip install numpy"])
        yaml_path = _write_yaml(tmp_path, definition)
        bench = CustomBenchmark(definition_path=yaml_path)
        assert bench.setup_commands == ["apt-get update", "pip install numpy"]

    def test_docker_image_loaded(self) -> None:
        """Test that docker_image is loaded."""
        bench = CustomBenchmark(**_minimal_definition(docker_image="python:3.11-slim"))
        assert bench.docker_image == "python:3.11-slim"

    def test_numeric_tolerances(self) -> None:
        """Test that numeric tolerances can be configured."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="numeric",
                numeric_rtol=0.01,
                numeric_atol=0.5,
            )
        )
        assert bench.numeric_rtol == 0.01
        assert bench.numeric_atol == 0.5


# ---------------------------------------------------------------------------
# Protocol Compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Tests that CustomBenchmark satisfies the Benchmark protocol."""

    def test_implements_benchmark_protocol(self) -> None:
        """Test that CustomBenchmark implements the Benchmark protocol."""
        bench = CustomBenchmark(**_minimal_definition())
        assert isinstance(bench, Benchmark)

    def test_has_all_protocol_methods(self) -> None:
        """Test that all required protocol methods exist."""
        bench = CustomBenchmark(**_minimal_definition())
        assert hasattr(bench, "name")
        assert hasattr(bench, "load_tasks")
        assert hasattr(bench, "normalize_task")
        assert hasattr(bench, "create_environment")
        assert hasattr(bench, "evaluate")
        assert hasattr(bench, "get_prebuilt_image")
        assert hasattr(bench, "get_prompt_template")


# ---------------------------------------------------------------------------
# load_tasks (with mocked dataset)
# ---------------------------------------------------------------------------


class TestLoadTasks:
    """Tests for task loading with mocked HuggingFace datasets."""

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_basic(self, mock_load: MagicMock) -> None:
        """Test basic task loading with default fields."""
        mock_load.return_value = [
            {"id": "q1", "question": "What is 2+2?", "answer": "4"},
            {"id": "q2", "question": "What is 3+3?", "answer": "6"},
        ]

        bench = CustomBenchmark(**_minimal_definition())
        tasks = bench.load_tasks()

        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "test-bench_q1"
        assert tasks[1]["instance_id"] == "test-bench_q2"
        assert "problem_statement" in tasks[0]
        assert tasks[0]["ground_truth_answer"] == "4"
        mock_load.assert_called_once_with("org/test-dataset", split="test")

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_with_subset(self, mock_load: MagicMock) -> None:
        """Test that subset is passed to load_dataset."""
        mock_load.return_value = [
            {"id": "q1", "question": "Q1", "answer": "A1"},
        ]

        bench = CustomBenchmark(**_minimal_definition(subset="hard"))
        bench.load_tasks()

        mock_load.assert_called_once_with("org/test-dataset", "hard", split="test")

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_sample_size(self, mock_load: MagicMock) -> None:
        """Test sample_size limits the number of tasks returned."""
        mock_load.return_value = [
            {"id": str(i), "question": f"Q{i}", "answer": f"A{i}"} for i in range(10)
        ]

        bench = CustomBenchmark(**_minimal_definition())
        tasks = bench.load_tasks(sample_size=3)

        assert len(tasks) == 3

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_by_task_ids(self, mock_load: MagicMock) -> None:
        """Test loading specific tasks by ID."""
        mock_load.return_value = [
            {"id": "a", "question": "Q-a", "answer": "A-a"},
            {"id": "b", "question": "Q-b", "answer": "A-b"},
            {"id": "c", "question": "Q-c", "answer": "A-c"},
        ]

        bench = CustomBenchmark(**_minimal_definition())
        tasks = bench.load_tasks(task_ids=["a", "c"])

        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "test-bench_a"
        assert tasks[1]["instance_id"] == "test-bench_c"

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_custom_field_mapping(self, mock_load: MagicMock) -> None:
        """Test that custom field names are used correctly."""
        mock_load.return_value = [
            {"uid": "001", "prompt": "Translate this", "expected": "Bonjour"},
        ]

        bench = CustomBenchmark(
            **_minimal_definition(
                task_id_field="uid",
                problem_statement_field="prompt",
                answer_field="expected",
            )
        )
        tasks = bench.load_tasks()

        assert tasks[0]["instance_id"] == "test-bench_001"
        assert tasks[0]["ground_truth_answer"] == "Bonjour"

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_tasks_index_fallback_for_id(self, mock_load: MagicMock) -> None:
        """Test that dataset index is used when task_id_field is missing."""
        mock_load.return_value = [
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"},
        ]

        bench = CustomBenchmark(**_minimal_definition())
        tasks = bench.load_tasks()

        # Falls back to index since "id" field doesn't exist
        assert tasks[0]["instance_id"] == "test-bench_0"
        assert tasks[1]["instance_id"] == "test-bench_1"


# ---------------------------------------------------------------------------
# normalize_task
# ---------------------------------------------------------------------------


class TestNormalizeTask:
    """Tests for task normalization."""

    def test_normalize_task_basic(self) -> None:
        """Test basic task normalization."""
        bench = CustomBenchmark(**_minimal_definition())
        task = {
            "instance_id": "test-bench_q1",
            "question": "What is 2+2?",
            "answer": "4",
            "problem_statement": "What is 2+2?",
            "ground_truth_answer": "4",
        }

        normalized = bench.normalize_task(task)

        assert normalized.task_id == "test-bench_q1"
        assert normalized.problem_statement == "What is 2+2?"
        assert normalized.repo == "test-bench/custom"
        assert normalized.commit == "HEAD"
        assert normalized.metadata["evaluation_type"] == "exact_match"

    def test_normalize_task_missing_instance_id(self) -> None:
        """Test that missing instance_id raises ValueError."""
        bench = CustomBenchmark(**_minimal_definition())
        task = {"question": "Q1", "answer": "A1"}

        with pytest.raises(ValueError, match="missing required 'instance_id' field"):
            bench.normalize_task(task)

    def test_normalize_task_uses_problem_statement_field(self) -> None:
        """Test that normalize_task uses the configured problem_statement_field."""
        bench = CustomBenchmark(**_minimal_definition(problem_statement_field="prompt"))
        task = {
            "instance_id": "test-bench_1",
            "prompt": "Translate hello",
            "answer": "Bonjour",
        }

        normalized = bench.normalize_task(task)
        assert "Translate hello" in normalized.problem_statement


# ---------------------------------------------------------------------------
# Problem Statement Generation
# ---------------------------------------------------------------------------


class TestProblemStatement:
    """Tests for problem statement generation."""

    def test_default_statement(self) -> None:
        """Test default problem statement (raw field value)."""
        bench = CustomBenchmark(**_minimal_definition())
        task = {"question": "What is the speed of light?"}

        statement = bench._generate_problem_statement(task)
        assert statement == "What is the speed of light?"

    def test_custom_prompt_template(self) -> None:
        """Test problem statement with a custom prompt template."""
        bench = CustomBenchmark(
            **_minimal_definition(prompt_template="Answer concisely:\n{problem_statement}")
        )
        task = {"question": "What is 1+1?"}

        statement = bench._generate_problem_statement(task)
        assert "Answer concisely:" in statement
        assert "What is 1+1?" in statement

    def test_prompt_template_with_task_fields(self) -> None:
        """Test prompt template can reference other task fields."""
        bench = CustomBenchmark(
            **_minimal_definition(prompt_template="[{difficulty}] {problem_statement}")
        )
        task = {"question": "Hard question", "difficulty": "hard"}

        statement = bench._generate_problem_statement(task)
        assert "[hard]" in statement
        assert "Hard question" in statement

    def test_prompt_template_missing_field_fallback(self) -> None:
        """Test that missing template fields fall back to raw statement."""
        bench = CustomBenchmark(
            **_minimal_definition(prompt_template="{problem_statement} - Category: {category}")
        )
        task = {"question": "Some question"}  # no "category" field

        statement = bench._generate_problem_statement(task)
        assert statement == "Some question"  # falls back to raw


# ---------------------------------------------------------------------------
# Evaluation: exact_match
# ---------------------------------------------------------------------------


class TestEvaluateExactMatch:
    """Tests for exact_match evaluation."""

    def test_exact_match_correct(self) -> None:
        """Test that exact match finds answer in solution."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        result = bench._evaluate_exact_match("The answer is Paris", "Paris")
        assert result["resolved"] is True

    def test_exact_match_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        result = bench._evaluate_exact_match("The answer is PARIS", "paris")
        assert result["resolved"] is True

    def test_exact_match_whitespace_normalized(self) -> None:
        """Test whitespace normalization in matching."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        result = bench._evaluate_exact_match("Answer:  New   York", "new york")
        assert result["resolved"] is True

    def test_exact_match_incorrect(self) -> None:
        """Test that non-matching answers are rejected."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        result = bench._evaluate_exact_match("The answer is London", "Paris")
        assert result["resolved"] is False


# ---------------------------------------------------------------------------
# Evaluation: numeric
# ---------------------------------------------------------------------------


class TestEvaluateNumeric:
    """Tests for numeric evaluation."""

    def test_numeric_exact(self) -> None:
        """Test exact numeric match."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("The answer is 42", "42")
        assert result["resolved"] is True

    def test_numeric_within_tolerance(self) -> None:
        """Test numeric comparison within default tolerance."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("The answer is 42.0005", "42")
        assert result["resolved"] is True

    def test_numeric_outside_tolerance(self) -> None:
        """Test numeric comparison outside tolerance."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("The answer is 50", "42")
        assert result["resolved"] is False

    def test_numeric_custom_tolerance(self) -> None:
        """Test numeric comparison with custom tolerances."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="numeric",
                numeric_atol=1.0,
            )
        )
        result = bench._evaluate_numeric("The answer is 42.5", "42")
        assert result["resolved"] is True

    def test_numeric_no_number_in_solution(self) -> None:
        """Test that missing number in solution returns error."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("I have no idea", "42")
        assert result["resolved"] is False
        assert "error" in result

    def test_numeric_unparseable_ground_truth(self) -> None:
        """Test that unparseable ground truth returns error."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("42", "not-a-number")
        assert result["resolved"] is False
        assert "error" in result

    def test_numeric_comma_format(self) -> None:
        """Test numeric extraction from comma-formatted numbers."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("Total: 1,234", "1234")
        assert result["resolved"] is True

    def test_numeric_gsm8k_format(self) -> None:
        """Test numeric extraction from #### format."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        result = bench._evaluate_numeric("Steps... #### 42", "42")
        assert result["resolved"] is True


# ---------------------------------------------------------------------------
# Evaluation: regex
# ---------------------------------------------------------------------------


class TestEvaluateRegex:
    """Tests for regex evaluation."""

    def test_regex_with_capture_group(self) -> None:
        """Test regex evaluation with a capture group."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"answer:\s*(\w+)",
            )
        )
        result = bench._evaluate_regex("The answer: Paris", "Paris")
        assert result["resolved"] is True

    def test_regex_no_match(self) -> None:
        """Test regex evaluation when pattern does not match."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"answer:\s*(\w+)",
            )
        )
        result = bench._evaluate_regex("I don't know", "Paris")
        assert result["resolved"] is False

    def test_regex_wrong_answer(self) -> None:
        """Test regex evaluation when captured answer is wrong."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"answer:\s*(\w+)",
            )
        )
        result = bench._evaluate_regex("answer: London", "Paris")
        assert result["resolved"] is False

    def test_regex_case_insensitive(self) -> None:
        """Test regex evaluation is case-insensitive for comparison."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"answer:\s*(\w+)",
            )
        )
        result = bench._evaluate_regex("answer: PARIS", "paris")
        assert result["resolved"] is True

    def test_regex_no_pattern_configured(self) -> None:
        """Test that missing regex_pattern returns error."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        bench.evaluation_type = "regex"
        bench.regex_pattern = None
        result = bench._evaluate_regex("answer: Paris", "Paris")
        assert result["resolved"] is False
        assert "error" in result

    def test_regex_invalid_pattern(self) -> None:
        """Test that an invalid regex pattern returns error."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        bench.evaluation_type = "regex"
        bench.regex_pattern = r"[invalid("
        result = bench._evaluate_regex("some text", "truth")
        assert result["resolved"] is False
        assert "error" in result

    def test_regex_without_capture_group(self) -> None:
        """Test regex evaluation with full match (no capture group)."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="regex",
                regex_pattern=r"paris",
            )
        )
        result = bench._evaluate_regex("the answer is paris obviously", "paris")
        assert result["resolved"] is True


# ---------------------------------------------------------------------------
# Evaluation: script (async)
# ---------------------------------------------------------------------------


class TestEvaluateScript:
    """Tests for script-based evaluation."""

    def test_script_correct(self) -> None:
        """Test script evaluation returning exit code 0 (correct)."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="script",
                evaluation_script="python3 /tmp/eval.py",
            )
        )

        mock_env = AsyncMock()
        mock_env.exec_command = AsyncMock(return_value=(0, "OK", ""))

        result = asyncio.run(bench._evaluate_script(mock_env, {}, "my solution", "expected"))

        assert result["resolved"] is True
        assert result["script_exit_code"] == 0

    def test_script_incorrect(self) -> None:
        """Test script evaluation returning non-zero exit code (incorrect)."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="script",
                evaluation_script="python3 /tmp/eval.py",
            )
        )

        mock_env = AsyncMock()
        mock_env.exec_command = AsyncMock(return_value=(1, "", "mismatch"))

        result = asyncio.run(bench._evaluate_script(mock_env, {}, "wrong answer", "expected"))

        assert result["resolved"] is False
        assert result["script_exit_code"] == 1

    def test_script_no_evaluation_script(self) -> None:
        """Test script evaluation with no script configured."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        bench.evaluation_type = "script"
        bench.evaluation_script = None

        mock_env = AsyncMock()

        result = asyncio.run(bench._evaluate_script(mock_env, {}, "solution", "truth"))

        assert result["resolved"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# Evaluate dispatcher (async)
# ---------------------------------------------------------------------------


class TestEvaluateDispatch:
    """Tests for the top-level evaluate method dispatching."""

    def test_dispatch_exact_match(self) -> None:
        """Test that evaluate dispatches to exact_match."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        mock_env = AsyncMock()

        task = {"ground_truth_answer": "Paris"}
        result = asyncio.run(bench.evaluate(mock_env, task, "The answer is Paris"))

        assert result["resolved"] is True
        assert result["match_type"] == "exact_match"

    def test_dispatch_numeric(self) -> None:
        """Test that evaluate dispatches to numeric."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        mock_env = AsyncMock()

        task = {"ground_truth_answer": "42"}
        result = asyncio.run(bench.evaluate(mock_env, task, "The answer is 42"))

        assert result["resolved"] is True
        assert result["match_type"] == "numeric"

    def test_dispatch_no_ground_truth(self) -> None:
        """Test that evaluate returns error when no ground truth is available."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="exact_match"))
        mock_env = AsyncMock()

        task = {}  # no ground truth
        result = asyncio.run(bench.evaluate(mock_env, task, "some solution"))

        assert result["resolved"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# get_prebuilt_image
# ---------------------------------------------------------------------------


class TestGetPrebuiltImage:
    """Tests for Docker image retrieval."""

    def test_no_docker_image(self) -> None:
        """Test that None is returned when no docker_image is configured."""
        bench = CustomBenchmark(**_minimal_definition())
        assert bench.get_prebuilt_image({}) is None

    def test_configured_docker_image(self) -> None:
        """Test that configured docker_image is returned."""
        bench = CustomBenchmark(**_minimal_definition(docker_image="python:3.11"))
        assert bench.get_prebuilt_image({}) == "python:3.11"


# ---------------------------------------------------------------------------
# get_prompt_template
# ---------------------------------------------------------------------------


class TestGetPromptTemplate:
    """Tests for prompt template retrieval."""

    def test_default_prompt_template(self) -> None:
        """Test the default prompt template contains benchmark name and placeholder."""
        bench = CustomBenchmark(**_minimal_definition())
        template = bench.get_prompt_template()
        assert "{problem_statement}" in template
        assert "test-bench" in template

    def test_custom_prompt_template(self) -> None:
        """Test that a custom prompt template is returned as-is."""
        custom_tpl = "Custom: {problem_statement}"
        bench = CustomBenchmark(**_minimal_definition(prompt_template=custom_tpl))
        assert bench.get_prompt_template() == custom_tpl


# ---------------------------------------------------------------------------
# create_environment (async, mocked)
# ---------------------------------------------------------------------------


class TestCreateEnvironment:
    """Tests for environment creation with mocked Docker manager."""

    def test_create_environment_basic(self) -> None:
        """Test basic environment creation."""
        bench = CustomBenchmark(**_minimal_definition())

        mock_env = AsyncMock()
        mock_manager = AsyncMock()
        mock_manager.create_environment = AsyncMock(return_value=mock_env)

        task = {"instance_id": "test-bench_q1"}

        env = asyncio.run(bench.create_environment(task, mock_manager))

        assert env is mock_env
        mock_manager.create_environment.assert_called_once()
        call_args = mock_manager.create_environment.call_args[0][0]
        assert call_args["instance_id"] == "test-bench_q1"
        assert call_args["repo"] == "test-bench/custom"

    def test_create_environment_runs_setup_commands(self) -> None:
        """Test that setup commands are executed during environment creation."""
        bench = CustomBenchmark(
            **_minimal_definition(setup_commands=["apt-get update", "pip install numpy"])
        )

        mock_env = AsyncMock()
        mock_env.exec_command = AsyncMock(return_value=(0, "", ""))
        mock_manager = AsyncMock()
        mock_manager.create_environment = AsyncMock(return_value=mock_env)

        task = {"instance_id": "test-bench_q1"}

        asyncio.run(bench.create_environment(task, mock_manager))

        assert mock_env.exec_command.call_count == 2
        calls = [c[0][0] for c in mock_env.exec_command.call_args_list]
        assert "apt-get update" in calls
        assert "pip install numpy" in calls


# ---------------------------------------------------------------------------
# Utility methods
# ---------------------------------------------------------------------------


class TestUtilityMethods:
    """Tests for internal utility methods."""

    def test_normalize_text(self) -> None:
        """Test text normalization."""
        assert CustomBenchmark._normalize_text("  Hello   World  ") == "hello world"
        assert CustomBenchmark._normalize_text("ALL CAPS") == "all caps"
        assert CustomBenchmark._normalize_text("no\nnewlines") == "no newlines"

    def test_extract_number_plain(self) -> None:
        """Test extracting plain numbers."""
        assert CustomBenchmark._extract_number("42") == 42.0
        assert CustomBenchmark._extract_number("3.14") == 3.14
        assert CustomBenchmark._extract_number("-7") == -7.0

    def test_extract_number_with_text(self) -> None:
        """Test extracting numbers from sentences."""
        assert CustomBenchmark._extract_number("The answer is 42") == 42.0
        assert CustomBenchmark._extract_number("#### 100") == 100.0

    def test_extract_number_no_number(self) -> None:
        """Test that None is returned when no number is found."""
        assert CustomBenchmark._extract_number("no numbers here") is None
        assert CustomBenchmark._extract_number("") is None

    def test_parse_number_various_formats(self) -> None:
        """Test parsing numbers in various formats."""
        assert CustomBenchmark._parse_number("42") == 42.0
        assert CustomBenchmark._parse_number("1,234") == 1234.0
        assert CustomBenchmark._parse_number("$99.99") == 99.99
        assert CustomBenchmark._parse_number("-5") == -5.0
        assert CustomBenchmark._parse_number("abc") is None

    def test_compare_numbers_exact(self) -> None:
        """Test exact numeric comparison."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        assert bench._compare_numbers(42.0, 42.0) is True
        assert bench._compare_numbers(0.0, 0.0) is True

    def test_compare_numbers_tolerance(self) -> None:
        """Test numeric comparison with tolerance."""
        bench = CustomBenchmark(**_minimal_definition(evaluation_type="numeric"))
        assert bench._compare_numbers(42.0, 42.0005) is True
        assert bench._compare_numbers(42.0, 43.0) is False

    def test_compare_numbers_custom_tolerance(self) -> None:
        """Test numeric comparison with custom tolerance."""
        bench = CustomBenchmark(
            **_minimal_definition(
                evaluation_type="numeric",
                numeric_atol=2.0,
            )
        )
        assert bench._compare_numbers(42.0, 43.5) is True
        assert bench._compare_numbers(42.0, 45.0) is False


# ---------------------------------------------------------------------------
# Full YAML round-trip
# ---------------------------------------------------------------------------


class TestFullYAMLRoundTrip:
    """Integration-style tests that load from YAML and exercise the benchmark."""

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_and_evaluate_exact_match(self, mock_load: MagicMock, tmp_path: Path) -> None:
        """Test end-to-end: load YAML, load tasks, evaluate with exact_match."""
        definition = {
            "name": "geography-quiz",
            "dataset": "my-org/geo-quiz",
            "split": "test",
            "task_id_field": "qid",
            "problem_statement_field": "question",
            "answer_field": "answer",
            "evaluation_type": "exact_match",
        }
        yaml_path = _write_yaml(tmp_path, definition)

        mock_load.return_value = [
            {"qid": "g1", "question": "Capital of France?", "answer": "Paris"},
            {"qid": "g2", "question": "Capital of Germany?", "answer": "Berlin"},
        ]

        bench = CustomBenchmark(definition_path=yaml_path)
        tasks = bench.load_tasks()

        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "geography-quiz_g1"

        # Normalize
        normalized = bench.normalize_task(tasks[0])
        assert normalized.task_id == "geography-quiz_g1"

        # Evaluate correct
        mock_env = AsyncMock()
        result = asyncio.run(bench.evaluate(mock_env, tasks[0], "The capital is Paris"))
        assert result["resolved"] is True

        # Evaluate incorrect
        result = asyncio.run(bench.evaluate(mock_env, tasks[0], "The capital is London"))
        assert result["resolved"] is False

    @patch("mcpbr.benchmarks.custom.load_dataset")
    def test_load_and_evaluate_numeric(self, mock_load: MagicMock, tmp_path: Path) -> None:
        """Test end-to-end: load YAML, load tasks, evaluate with numeric."""
        definition = {
            "name": "math-quiz",
            "dataset": "my-org/math-quiz",
            "split": "test",
            "evaluation_type": "numeric",
            "answer_field": "answer",
        }
        yaml_path = _write_yaml(tmp_path, definition)

        mock_load.return_value = [
            {"id": "m1", "question": "What is 2+2?", "answer": "4"},
        ]

        bench = CustomBenchmark(definition_path=yaml_path)
        tasks = bench.load_tasks()

        mock_env = AsyncMock()
        result = asyncio.run(bench.evaluate(mock_env, tasks[0], "The answer is 4"))
        assert result["resolved"] is True
