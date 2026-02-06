"""Integration tests for MCPToolBench++ benchmark implementation.

Tests cover load_tasks with mock data, normalize_task, evaluate with mock solutions,
prompt template, tool call extraction, and edge cases.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.benchmarks import MCPToolBenchmark
from mcpbr.benchmarks.base import BenchmarkTask

# --- Fixtures and helpers ---


_SENTINEL = object()


def _make_task(
    uuid: str = "uuid-001",
    category: str = "browser",
    call_type: str = "single",
    query: str = "Navigate to example.com",
    tools: list[str] | object = _SENTINEL,
    mcp_tools_dict: dict[str, Any] | object = _SENTINEL,
    function_call_label: list[dict[str, Any]] | object = _SENTINEL,
) -> dict[str, Any]:
    """Create a minimal MCPToolBench++ task dictionary.

    Uses a sentinel so that callers can pass an explicit empty list ``[]``
    to override the default without it being treated as falsy / None.
    """
    return {
        "uuid": uuid,
        "category": category,
        "call_type": call_type,
        "query": query,
        "tools": ["navigate", "click"] if tools is _SENTINEL else tools,
        "mcp_tools_dict": {"navigate": {}, "click": {}}
        if mcp_tools_dict is _SENTINEL
        else mcp_tools_dict,
        "function_call_label": [{"name": "navigate", "parameters": {"url": "example.com"}}]
        if function_call_label is _SENTINEL
        else function_call_label,
    }


def _mock_dataset(tasks: list[dict[str, Any]]) -> MagicMock:
    """Create a mock HuggingFace dataset that behaves like a list of dicts."""
    dataset = MagicMock()
    dataset.__iter__ = MagicMock(return_value=iter(tasks))
    dataset.__len__ = MagicMock(return_value=len(tasks))

    def _select(indices):
        selected = [tasks[i] for i in indices]
        return _mock_dataset(selected)

    dataset.select = MagicMock(side_effect=_select)
    return dataset


# --- Test load_tasks ---


class TestLoadTasks:
    """Tests for MCPToolBenchmark.load_tasks with mocked HuggingFace data."""

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_all_tasks(self, mock_load: MagicMock) -> None:
        """Loading without filters returns all tasks augmented with instance_id."""
        raw_tasks = [_make_task(uuid="a"), _make_task(uuid="b")]
        mock_load.return_value = _mock_dataset(raw_tasks)

        benchmark = MCPToolBenchmark()
        tasks = benchmark.load_tasks()

        mock_load.assert_called_once_with("MCPToolBench/MCPToolBenchPP", split="train")
        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "a"
        assert tasks[1]["instance_id"] == "b"
        # Each task should have a generated problem_statement
        assert "problem_statement" in tasks[0]
        assert "problem_statement" in tasks[1]

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_with_sample_size(self, mock_load: MagicMock) -> None:
        """sample_size truncates results."""
        raw_tasks = [_make_task(uuid=f"id-{i}") for i in range(5)]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(sample_size=2)
        assert len(tasks) == 2

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_by_task_ids(self, mock_load: MagicMock) -> None:
        """task_ids filters to matching uuids only."""
        raw_tasks = [
            _make_task(uuid="keep-1"),
            _make_task(uuid="skip"),
            _make_task(uuid="keep-2"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(task_ids=["keep-1", "keep-2"])
        uuids = [t["uuid"] for t in tasks]
        assert uuids == ["keep-1", "keep-2"]

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_difficulty_easy(self, mock_load: MagicMock) -> None:
        """filter_difficulty=['easy'] keeps only single-step tasks."""
        raw_tasks = [
            _make_task(uuid="s1", call_type="single"),
            _make_task(uuid="m1", call_type="multi"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_difficulty=["easy"])
        assert len(tasks) == 1
        assert tasks[0]["uuid"] == "s1"

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_difficulty_hard(self, mock_load: MagicMock) -> None:
        """filter_difficulty=['hard'] keeps only multi-step tasks."""
        raw_tasks = [
            _make_task(uuid="s1", call_type="single"),
            _make_task(uuid="m1", call_type="multi"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_difficulty=["hard"])
        assert len(tasks) == 1
        assert tasks[0]["uuid"] == "m1"

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_difficulty_medium_maps_to_multi(self, mock_load: MagicMock) -> None:
        """filter_difficulty=['medium'] maps to multi-step tasks."""
        raw_tasks = [
            _make_task(uuid="s1", call_type="single"),
            _make_task(uuid="m1", call_type="multi"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_difficulty=["medium"])
        assert len(tasks) == 1
        assert tasks[0]["uuid"] == "m1"

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_difficulty_both(self, mock_load: MagicMock) -> None:
        """filter_difficulty=['easy','hard'] keeps all tasks."""
        raw_tasks = [
            _make_task(uuid="s1", call_type="single"),
            _make_task(uuid="m1", call_type="multi"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_difficulty=["easy", "hard"])
        assert len(tasks) == 2

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_category(self, mock_load: MagicMock) -> None:
        """filter_category keeps only matching categories."""
        raw_tasks = [
            _make_task(uuid="b1", category="browser"),
            _make_task(uuid="f1", category="finance"),
            _make_task(uuid="w1", category="web"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_category=["browser", "web"])
        uuids = {t["uuid"] for t in tasks}
        assert uuids == {"b1", "w1"}

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_category_case_insensitive(self, mock_load: MagicMock) -> None:
        """filter_category matching is case-insensitive."""
        raw_tasks = [_make_task(uuid="b1", category="Browser")]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_category=["browser"])
        assert len(tasks) == 1

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_combined_filters(self, mock_load: MagicMock) -> None:
        """Combined difficulty and category filters intersect correctly."""
        raw_tasks = [
            _make_task(uuid="bs", category="browser", call_type="single"),
            _make_task(uuid="bm", category="browser", call_type="multi"),
            _make_task(uuid="fs", category="finance", call_type="single"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(
            filter_difficulty=["easy"],
            filter_category=["browser"],
        )
        # Only browser + single should survive
        assert len(tasks) == 1
        assert tasks[0]["uuid"] == "bs"

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_sample_size_after_filters(self, mock_load: MagicMock) -> None:
        """sample_size is applied after all filters."""
        raw_tasks = [
            _make_task(uuid=f"b{i}", category="browser", call_type="single") for i in range(5)
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(
            filter_difficulty=["easy"],
            filter_category=["browser"],
            sample_size=2,
        )
        assert len(tasks) == 2

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_tags_silenced(self, mock_load: MagicMock) -> None:
        """filter_tags is accepted but has no effect on results."""
        raw_tasks = [_make_task(uuid="a")]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_tags=["security"])
        assert len(tasks) == 1

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_custom_dataset(self, mock_load: MagicMock) -> None:
        """Custom dataset identifier is forwarded to load_dataset."""
        raw_tasks = [_make_task()]
        mock_load.return_value = _mock_dataset(raw_tasks)

        MCPToolBenchmark(dataset="custom/ds").load_tasks()
        mock_load.assert_called_once_with("custom/ds", split="train")


# --- Test normalize_task ---


class TestNormalizeTask:
    """Tests for MCPToolBenchmark.normalize_task."""

    def test_basic_normalization(self) -> None:
        """normalize_task produces a valid BenchmarkTask."""
        benchmark = MCPToolBenchmark()
        task = _make_task(
            uuid="test-uuid",
            category="finance",
            call_type="multi",
            query="Get stock price",
            tools=["get_stock"],
        )
        result = benchmark.normalize_task(task)

        assert isinstance(result, BenchmarkTask)
        assert result.task_id == "test-uuid"
        assert result.repo == "mcptoolbench/finance"
        assert result.commit == "HEAD"
        assert "Get stock price" in result.problem_statement

    def test_metadata_fields(self) -> None:
        """Metadata includes category, call_type, tools, mcp_tools_dict, etc."""
        benchmark = MCPToolBenchmark()
        task = _make_task(
            uuid="meta-test",
            category="web",
            call_type="single",
            tools=["fetch_url"],
            mcp_tools_dict={"fetch_url": {"type": "function"}},
            function_call_label=[{"name": "fetch_url", "parameters": {"url": "x.com"}}],
        )
        result = benchmark.normalize_task(task)

        assert result.metadata["category"] == "web"
        assert result.metadata["call_type"] == "single"
        assert result.metadata["tools"] == ["fetch_url"]
        assert "fetch_url" in result.metadata["mcp_tools_dict"]
        assert len(result.metadata["function_call_label"]) == 1
        assert result.metadata["query"] == "Navigate to example.com"

    def test_missing_uuid_raises_error(self) -> None:
        """normalize_task raises ValueError when uuid is missing."""
        benchmark = MCPToolBenchmark()
        task = {"category": "browser", "query": "do something"}

        with pytest.raises(ValueError, match="missing required 'uuid' field"):
            benchmark.normalize_task(task)

    def test_fallback_to_instance_id(self) -> None:
        """normalize_task uses instance_id when uuid is missing."""
        benchmark = MCPToolBenchmark()
        task = {
            "instance_id": "fallback-id",
            "category": "browser",
            "call_type": "single",
            "query": "test",
            "tools": [],
            "mcp_tools_dict": {},
            "function_call_label": [],
        }
        result = benchmark.normalize_task(task)
        assert result.task_id == "fallback-id"

    def test_missing_optional_fields_default(self) -> None:
        """Missing optional fields get sensible defaults."""
        benchmark = MCPToolBenchmark()
        task = {"uuid": "minimal"}
        result = benchmark.normalize_task(task)

        assert result.task_id == "minimal"
        assert result.repo == "mcptoolbench/unknown"
        assert result.metadata["category"] == "unknown"
        assert result.metadata["call_type"] == ""
        assert result.metadata["tools"] == []


# --- Test _generate_problem_statement ---


class TestGenerateProblemStatement:
    """Tests for MCPToolBenchmark._generate_problem_statement."""

    def test_contains_query(self) -> None:
        """Problem statement includes the original query."""
        benchmark = MCPToolBenchmark()
        task = _make_task(query="List all open PRs")
        result = benchmark._generate_problem_statement(task)
        assert "List all open PRs" in result

    def test_contains_category(self) -> None:
        """Problem statement includes the category."""
        benchmark = MCPToolBenchmark()
        task = _make_task(category="github")
        result = benchmark._generate_problem_statement(task)
        assert "github" in result

    def test_contains_call_type(self) -> None:
        """Problem statement includes the call type."""
        benchmark = MCPToolBenchmark()
        task = _make_task(call_type="multi")
        result = benchmark._generate_problem_statement(task)
        assert "multi-step" in result

    def test_contains_tools(self) -> None:
        """Problem statement lists available tools."""
        benchmark = MCPToolBenchmark()
        task = _make_task(tools=["search", "fetch", "parse"])
        result = benchmark._generate_problem_statement(task)
        assert "search" in result
        assert "fetch" in result
        assert "parse" in result

    def test_empty_tools_list(self) -> None:
        """Problem statement handles empty tools list gracefully."""
        benchmark = MCPToolBenchmark()
        task = _make_task(tools=[])
        result = benchmark._generate_problem_statement(task)
        assert "no tools specified" in result

    def test_missing_query(self) -> None:
        """Problem statement handles missing query field."""
        benchmark = MCPToolBenchmark()
        task = {"uuid": "x", "category": "test", "call_type": "single", "tools": []}
        result = benchmark._generate_problem_statement(task)
        assert "No query provided" in result


# --- Test prompt template ---


class TestPromptTemplate:
    """Tests for MCPToolBenchmark.get_prompt_template."""

    def test_has_placeholder(self) -> None:
        """Template contains the required {problem_statement} placeholder."""
        prompt = MCPToolBenchmark().get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_mentions_mcp(self) -> None:
        """Template mentions MCP tools."""
        prompt = MCPToolBenchmark().get_prompt_template()
        assert "MCP" in prompt

    def test_mentions_tool_usage(self) -> None:
        """Template contains guidance about tool usage."""
        prompt = MCPToolBenchmark().get_prompt_template()
        lower = prompt.lower()
        assert "tool" in lower
        assert "parameter" in lower or "schema" in lower

    def test_mentions_sequence(self) -> None:
        """Template mentions calling tools in correct sequence."""
        prompt = MCPToolBenchmark().get_prompt_template()
        assert "sequence" in prompt.lower()


# --- Test _extract_tool_calls ---


class TestExtractToolCalls:
    """Tests for MCPToolBenchmark._extract_tool_calls."""

    def test_extract_from_json_list(self) -> None:
        """Extracts tool calls from a JSON array."""
        benchmark = MCPToolBenchmark()
        solution = json.dumps(
            [
                {"name": "navigate", "parameters": {"url": "test.com"}},
                {"name": "click", "parameters": {"selector": "#btn"}},
            ]
        )
        calls = benchmark._extract_tool_calls(solution)
        assert len(calls) == 2
        assert calls[0]["name"] == "navigate"
        assert calls[1]["name"] == "click"

    def test_extract_from_json_dict_with_tool_calls_key(self) -> None:
        """Extracts tool calls from a JSON dict with 'tool_calls' key."""
        benchmark = MCPToolBenchmark()
        solution = json.dumps(
            {
                "reasoning": "I need to navigate first",
                "tool_calls": [{"name": "navigate", "parameters": {"url": "x.com"}}],
            }
        )
        calls = benchmark._extract_tool_calls(solution)
        assert len(calls) == 1
        assert calls[0]["name"] == "navigate"

    def test_extract_returns_empty_for_plain_text(self) -> None:
        """Returns empty list for non-JSON text."""
        benchmark = MCPToolBenchmark()
        solution = "I used the navigate tool to go to test.com and then clicked the button."
        calls = benchmark._extract_tool_calls(solution)
        assert calls == []

    def test_extract_returns_empty_for_invalid_json(self) -> None:
        """Returns empty list for malformed JSON."""
        benchmark = MCPToolBenchmark()
        calls = benchmark._extract_tool_calls("{broken json")
        assert calls == []

    def test_extract_returns_empty_for_empty_string(self) -> None:
        """Returns empty list for empty string."""
        benchmark = MCPToolBenchmark()
        calls = benchmark._extract_tool_calls("")
        assert calls == []

    def test_extract_from_json_dict_without_tool_calls_key(self) -> None:
        """Returns empty list for JSON dict without 'tool_calls' key."""
        benchmark = MCPToolBenchmark()
        solution = json.dumps({"result": "success", "data": 42})
        calls = benchmark._extract_tool_calls(solution)
        assert calls == []


# --- Test _evaluate_tool_calls ---


class TestEvaluateToolCalls:
    """Tests for MCPToolBenchmark._evaluate_tool_calls."""

    def test_exact_match(self) -> None:
        """Perfect match yields correct=True and 100% accuracies."""
        benchmark = MCPToolBenchmark()
        calls = [{"name": "nav", "parameters": {"url": "x.com"}}]
        gt = [{"name": "nav", "parameters": {"url": "x.com"}}]
        result = benchmark._evaluate_tool_calls(calls, gt)

        assert result["correct"] is True
        assert result["tool_selection_accuracy"] == 1.0
        assert result["parameter_accuracy"] == 1.0
        assert result["sequence_match"] is True

    def test_wrong_tool(self) -> None:
        """Wrong tool yields correct=False."""
        benchmark = MCPToolBenchmark()
        calls = [{"name": "click", "parameters": {}}]
        gt = [{"name": "navigate", "parameters": {"url": "test.com"}}]
        result = benchmark._evaluate_tool_calls(calls, gt)

        assert result["correct"] is False
        assert result["tool_selection_accuracy"] == 0.0

    def test_wrong_parameters(self) -> None:
        """Correct tool but wrong parameters yields low parameter accuracy."""
        benchmark = MCPToolBenchmark()
        calls = [{"name": "navigate", "parameters": {"url": "wrong.com"}}]
        gt = [{"name": "navigate", "parameters": {"url": "right.com"}}]
        result = benchmark._evaluate_tool_calls(calls, gt)

        assert result["tool_selection_accuracy"] == 1.0
        assert result["parameter_accuracy"] == 0.0

    def test_empty_agent_calls(self) -> None:
        """No agent calls yields correct=False with zero accuracies."""
        benchmark = MCPToolBenchmark()
        result = benchmark._evaluate_tool_calls([], [{"name": "nav", "parameters": {}}])

        assert result["correct"] is False
        assert result["tool_selection_accuracy"] == 0.0
        assert result["parameter_accuracy"] == 0.0
        assert "no tool calls" in result["details"].lower()

    def test_empty_ground_truth(self) -> None:
        """No ground truth yields correct=False."""
        benchmark = MCPToolBenchmark()
        result = benchmark._evaluate_tool_calls(
            [{"name": "nav", "parameters": {}}],
            [],
        )
        assert result["correct"] is False
        assert "no ground truth" in result["details"].lower()

    def test_both_empty(self) -> None:
        """Both empty yields correct=False."""
        benchmark = MCPToolBenchmark()
        result = benchmark._evaluate_tool_calls([], [])
        assert result["correct"] is False

    def test_sequence_match_different_order(self) -> None:
        """Correct tools in wrong order yields sequence_match=False."""
        benchmark = MCPToolBenchmark()
        calls = [
            {"name": "click", "parameters": {"sel": "#btn"}},
            {"name": "navigate", "parameters": {"url": "x.com"}},
        ]
        gt = [
            {"name": "navigate", "parameters": {"url": "x.com"}},
            {"name": "click", "parameters": {"sel": "#btn"}},
        ]
        result = benchmark._evaluate_tool_calls(calls, gt)
        assert result["sequence_match"] is False

    def test_sequence_match_different_length(self) -> None:
        """Different number of calls yields sequence_match=False."""
        benchmark = MCPToolBenchmark()
        calls = [{"name": "nav", "parameters": {}}]
        gt = [
            {"name": "nav", "parameters": {}},
            {"name": "click", "parameters": {}},
        ]
        result = benchmark._evaluate_tool_calls(calls, gt)
        assert result["sequence_match"] is False

    def test_multiple_tools_partial_match(self) -> None:
        """Partial tool match produces intermediate accuracy."""
        benchmark = MCPToolBenchmark()
        calls = [
            {"name": "navigate", "parameters": {"url": "x.com"}},
            {"name": "wrong_tool", "parameters": {}},
        ]
        gt = [
            {"name": "navigate", "parameters": {"url": "x.com"}},
            {"name": "click", "parameters": {"selector": "#btn"}},
        ]
        result = benchmark._evaluate_tool_calls(calls, gt)
        assert result["tool_selection_accuracy"] == 0.5

    def test_too_many_extra_calls_fails(self) -> None:
        """Too many extra agent calls causes correct=False."""
        benchmark = MCPToolBenchmark()
        # Ground truth has 1 call; agent has 3 (>1.5x)
        calls = [
            {"name": "nav", "parameters": {"url": "x.com"}},
            {"name": "extra1", "parameters": {}},
            {"name": "extra2", "parameters": {}},
        ]
        gt = [{"name": "nav", "parameters": {"url": "x.com"}}]
        result = benchmark._evaluate_tool_calls(calls, gt)
        # Even though tool_selection_accuracy=1.0 and parameter_accuracy=1.0,
        # the agent made too many calls (3 > 1.5 * 1 = 1.5)
        assert result["correct"] is False


# --- Test evaluate (async) ---


class TestEvaluateAsync:
    """Tests for MCPToolBenchmark.evaluate (async method)."""

    @pytest.mark.asyncio
    async def test_evaluate_correct_solution(self) -> None:
        """evaluate returns resolved=True for a perfect solution."""
        benchmark = MCPToolBenchmark()
        env = MagicMock()
        task = _make_task(
            function_call_label=[{"name": "navigate", "parameters": {"url": "example.com"}}],
        )
        solution = json.dumps([{"name": "navigate", "parameters": {"url": "example.com"}}])

        result = await benchmark.evaluate(env, task, solution)

        assert result["resolved"] is True
        assert result["tool_selection_accuracy"] == 1.0
        assert result["parameter_accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_wrong_solution(self) -> None:
        """evaluate returns resolved=False for a wrong tool call."""
        benchmark = MCPToolBenchmark()
        env = MagicMock()
        task = _make_task(
            function_call_label=[{"name": "navigate", "parameters": {"url": "correct.com"}}],
        )
        solution = json.dumps([{"name": "click", "parameters": {"selector": "#wrong"}}])

        result = await benchmark.evaluate(env, task, solution)

        assert result["resolved"] is False

    @pytest.mark.asyncio
    async def test_evaluate_no_ground_truth(self) -> None:
        """evaluate returns error when no function_call_label exists."""
        benchmark = MCPToolBenchmark()
        env = MagicMock()
        task = _make_task(function_call_label=[])
        solution = json.dumps([{"name": "navigate", "parameters": {}}])

        result = await benchmark.evaluate(env, task, solution)

        assert result["resolved"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_evaluate_non_json_solution(self) -> None:
        """evaluate handles non-JSON solution gracefully."""
        benchmark = MCPToolBenchmark()
        env = MagicMock()
        task = _make_task(
            function_call_label=[{"name": "navigate", "parameters": {"url": "test.com"}}],
        )
        solution = "I navigated to test.com using the navigate tool."

        result = await benchmark.evaluate(env, task, solution)

        assert result["resolved"] is False


# --- Test get_prebuilt_image ---


class TestGetPrebuiltImage:
    """Tests for MCPToolBenchmark.get_prebuilt_image."""

    def test_returns_none(self) -> None:
        """MCPToolBench++ has no pre-built images."""
        benchmark = MCPToolBenchmark()
        assert benchmark.get_prebuilt_image({"uuid": "test"}) is None

    def test_returns_none_empty_task(self) -> None:
        """Returns None even for empty task dict."""
        benchmark = MCPToolBenchmark()
        assert benchmark.get_prebuilt_image({}) is None


# --- Edge cases ---


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_empty_dataset(self, mock_load: MagicMock) -> None:
        """Loading from an empty dataset returns empty list."""
        mock_load.return_value = _mock_dataset([])

        tasks = MCPToolBenchmark().load_tasks()
        assert tasks == []

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_with_missing_fields(self, mock_load: MagicMock) -> None:
        """Tasks with missing optional fields still load."""
        raw_tasks = [{"uuid": "sparse-task"}]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks()
        assert len(tasks) == 1
        assert tasks[0]["instance_id"] == "sparse-task"
        assert "problem_statement" in tasks[0]

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_filter_no_matches(self, mock_load: MagicMock) -> None:
        """Filtering with no matches returns empty list."""
        raw_tasks = [_make_task(uuid="a", category="browser")]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_category=["nonexistent"])
        assert tasks == []

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_difficulty_filter_unknown_value(self, mock_load: MagicMock) -> None:
        """Unknown difficulty value is used as-is for call_type matching."""
        raw_tasks = [
            _make_task(uuid="a", call_type="custom_type"),
        ]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(filter_difficulty=["custom_type"])
        assert len(tasks) == 1

    def test_normalize_task_with_only_uuid(self) -> None:
        """normalize_task works with only uuid present."""
        benchmark = MCPToolBenchmark()
        task = {"uuid": "only-uuid"}
        result = benchmark.normalize_task(task)
        assert result.task_id == "only-uuid"
        assert result.repo == "mcptoolbench/unknown"

    def test_evaluate_tool_calls_missing_parameters_key(self) -> None:
        """Evaluation handles calls without 'parameters' key."""
        benchmark = MCPToolBenchmark()
        calls = [{"name": "navigate"}]
        gt = [{"name": "navigate", "parameters": {"url": "test.com"}}]
        result = benchmark._evaluate_tool_calls(calls, gt)
        assert result["tool_selection_accuracy"] == 1.0
        # Parameter accuracy = 0 because agent has no parameters
        assert result["parameter_accuracy"] == 0.0

    def test_evaluate_tool_calls_empty_parameters(self) -> None:
        """Evaluation handles ground truth with no parameters.

        When total_params is 0 the implementation defaults parameter_accuracy to 0.0
        which causes correct=False because the threshold is 0.7.
        """
        benchmark = MCPToolBenchmark()
        calls = [{"name": "list_files", "parameters": {}}]
        gt = [{"name": "list_files", "parameters": {}}]
        result = benchmark._evaluate_tool_calls(calls, gt)
        # 0 total params => parameter_accuracy defaults to 0.0 => below 0.7 threshold
        assert result["correct"] is False
        assert result["tool_selection_accuracy"] == 1.0
        assert result["parameter_accuracy"] == 0.0
        assert result["sequence_match"] is True

    @patch("mcpbr.benchmarks.mcptoolbench.load_dataset")
    def test_load_tasks_sample_size_larger_than_dataset(self, mock_load: MagicMock) -> None:
        """sample_size larger than dataset returns all tasks."""
        raw_tasks = [_make_task(uuid="a"), _make_task(uuid="b")]
        mock_load.return_value = _mock_dataset(raw_tasks)

        tasks = MCPToolBenchmark().load_tasks(sample_size=100)
        assert len(tasks) == 2

    def test_initialization_defaults(self) -> None:
        """Default initialization values are correct."""
        benchmark = MCPToolBenchmark()
        assert benchmark.name == "mcptoolbench"
        assert benchmark.dataset == "MCPToolBench/MCPToolBenchPP"

    def test_initialization_custom_dataset(self) -> None:
        """Custom dataset is stored correctly."""
        benchmark = MCPToolBenchmark(dataset="my/custom-ds")
        assert benchmark.dataset == "my/custom-ds"
