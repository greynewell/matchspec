"""Tests for MMMU benchmark implementation."""

from unittest.mock import MagicMock, patch

import pytest

from mcpbr.benchmarks.base import Benchmark
from mcpbr.benchmarks.mmmu import MMMUBenchmark


def _mock_mmmu_dataset(items: list[dict]) -> MagicMock:
    """Create a mock HuggingFace dataset from a list of dicts."""
    mock_ds = MagicMock()
    mock_ds.__iter__ = MagicMock(return_value=iter(items))
    mock_ds.__len__ = MagicMock(return_value=len(items))

    def _select(indices):
        selected = [items[i] for i in indices]
        return _mock_mmmu_dataset(selected)

    mock_ds.select = MagicMock(side_effect=_select)
    return mock_ds


class TestMMMUBenchmarkInit:
    """Tests for MMMU benchmark initialization."""

    def test_initialization_defaults(self) -> None:
        """Test MMMU initialization with default values."""
        benchmark = MMMUBenchmark()
        assert benchmark.name == "mmmu"
        assert benchmark.dataset == "MMMU/MMMU"
        assert benchmark.subset == "Accounting"

    def test_custom_dataset(self) -> None:
        """Test MMMU with custom dataset."""
        benchmark = MMMUBenchmark(dataset="custom/dataset")
        assert benchmark.dataset == "custom/dataset"

    def test_custom_subset(self) -> None:
        """Test MMMU with custom subset."""
        benchmark = MMMUBenchmark(subset="Biology")
        assert benchmark.subset == "Biology"

    def test_custom_dataset_and_subset(self) -> None:
        """Test MMMU with both custom dataset and subset."""
        benchmark = MMMUBenchmark(dataset="custom/mmmu", subset="Chemistry")
        assert benchmark.dataset == "custom/mmmu"
        assert benchmark.subset == "Chemistry"


class TestMMMUBenchmarkProtocol:
    """Tests for MMMU benchmark protocol compliance."""

    def test_implements_benchmark_protocol(self) -> None:
        """Test that MMMUBenchmark implements the Benchmark protocol."""
        benchmark = MMMUBenchmark()
        assert isinstance(benchmark, Benchmark)

    def test_has_required_attributes(self) -> None:
        """Test that MMMUBenchmark has all required protocol attributes."""
        benchmark = MMMUBenchmark()
        assert hasattr(benchmark, "name")
        assert hasattr(benchmark, "load_tasks")
        assert hasattr(benchmark, "normalize_task")
        assert hasattr(benchmark, "create_environment")
        assert hasattr(benchmark, "evaluate")
        assert hasattr(benchmark, "get_prebuilt_image")
        assert hasattr(benchmark, "get_prompt_template")


class TestMMMUNormalizeTask:
    """Tests for MMMU task normalization."""

    def test_normalize_task_basic(self) -> None:
        """Test normalizing a basic MMMU task."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_validation_Accounting_1",
            "id": "validation_Accounting_1",
            "question": "What is the total revenue shown in the chart?",
            "options": ["$100", "$200", "$300", "$400"],
            "answer": "B",
            "subfield": "Financial Accounting",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.task_id == "mmmu_validation_Accounting_1"
        assert "total revenue" in normalized.problem_statement
        assert normalized.repo == "mmmu/multimodal"
        assert normalized.commit == "HEAD"
        assert normalized.metadata["question"] == task["question"]
        assert normalized.metadata["answer"] == "B"
        assert normalized.metadata["subject"] == "Financial Accounting"
        assert normalized.metadata["options"] == task["options"]

    def test_normalize_task_missing_instance_id(self) -> None:
        """Test normalizing task without instance_id raises error."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "What is shown in the image?",
            "options": ["A cat", "A dog", "A bird", "A fish"],
            "answer": "A",
        }

        with pytest.raises(ValueError, match="missing required 'instance_id' field"):
            benchmark.normalize_task(task)

    def test_normalize_task_missing_question(self) -> None:
        """Test normalizing task without question raises error."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "options": ["A", "B", "C", "D"],
            "answer": "A",
        }

        with pytest.raises(ValueError, match="missing required 'question' field"):
            benchmark.normalize_task(task)

    def test_normalize_task_with_subject_fallback(self) -> None:
        """Test normalization uses 'subject' when 'subfield' is missing."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "Which diagram shows the correct structure?",
            "options": ["Diagram A", "Diagram B", "Diagram C", "Diagram D"],
            "answer": "C",
            "subject": "Biology",
        }

        normalized = benchmark.normalize_task(task)
        assert normalized.metadata["subject"] == "Biology"


class TestMMMUGenerateProblemStatement:
    """Tests for MMMU problem statement generation."""

    def test_problem_statement_includes_question(self) -> None:
        """Test that problem statement includes the question."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "What does the graph indicate about economic growth?",
            "options": ["Growth", "Decline", "Stagnation", "Fluctuation"],
        }

        statement = benchmark._generate_problem_statement(task)
        assert "economic growth" in statement

    def test_problem_statement_includes_options(self) -> None:
        """Test that problem statement includes answer options."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "What is the answer?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
        }

        statement = benchmark._generate_problem_statement(task)
        assert "(A) Option A" in statement
        assert "(B) Option B" in statement
        assert "(C) Option C" in statement
        assert "(D) Option D" in statement

    def test_problem_statement_includes_subject(self) -> None:
        """Test that problem statement includes the subject."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "What is the answer?",
            "options": ["A", "B", "C", "D"],
            "subfield": "Organic Chemistry",
        }

        statement = benchmark._generate_problem_statement(task)
        assert "Organic Chemistry" in statement

    def test_problem_statement_answer_instruction(self) -> None:
        """Test that problem statement includes answer format instruction."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "What is the answer?",
            "options": ["A", "B", "C", "D"],
        }

        statement = benchmark._generate_problem_statement(task)
        assert "ONLY the letter" in statement

    def test_problem_statement_with_images(self) -> None:
        """Test that problem statement notes when images are present."""
        benchmark = MMMUBenchmark()
        # Create a mock PIL Image
        mock_image = MagicMock()
        mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"fake_png_data"))

        task = {
            "question": "What is shown in the diagram?",
            "options": ["A", "B", "C", "D"],
            "image_1": mock_image,
        }

        statement = benchmark._generate_problem_statement(task)
        assert "image" in statement.lower()
        assert "1" in statement

    def test_problem_statement_no_options(self) -> None:
        """Test problem statement generation when options are absent."""
        benchmark = MMMUBenchmark()
        task = {
            "question": "Describe the image.",
        }

        statement = benchmark._generate_problem_statement(task)
        assert "Describe the image" in statement
        assert "Options:" not in statement


class TestMMMUExtractImages:
    """Tests for MMMU image extraction."""

    def test_extract_no_images(self) -> None:
        """Test extraction when no images are present."""
        benchmark = MMMUBenchmark()
        task = {"question": "A text-only question"}

        images = benchmark._extract_images(task)
        assert images == []

    def test_extract_pil_image(self) -> None:
        """Test extraction of PIL Image objects."""
        benchmark = MMMUBenchmark()
        mock_image = MagicMock()
        mock_image.save = MagicMock(side_effect=lambda buf, format: buf.write(b"fake_png_data"))

        task = {"image_1": mock_image}

        images = benchmark._extract_images(task)
        assert len(images) == 1
        # The result should be base64 encoded
        import base64

        decoded = base64.b64decode(images[0])
        assert decoded == b"fake_png_data"

    def test_extract_bytes_image(self) -> None:
        """Test extraction of raw bytes images."""
        benchmark = MMMUBenchmark()
        raw_bytes = b"\x89PNG\r\n\x1a\n"

        task = {"image_1": raw_bytes}

        images = benchmark._extract_images(task)
        assert len(images) == 1
        import base64

        decoded = base64.b64decode(images[0])
        assert decoded == raw_bytes

    def test_extract_string_image(self) -> None:
        """Test extraction of string-based images (e.g., base64 or paths)."""
        benchmark = MMMUBenchmark()
        task = {"image_1": "base64_encoded_string_here"}

        images = benchmark._extract_images(task)
        assert len(images) == 1
        assert images[0] == "base64_encoded_string_here"

    def test_extract_multiple_images(self) -> None:
        """Test extraction of multiple images."""
        benchmark = MMMUBenchmark()
        task = {
            "image_1": "img1_data",
            "image_2": "img2_data",
            "image_3": "img3_data",
        }

        images = benchmark._extract_images(task)
        assert len(images) == 3
        assert images[0] == "img1_data"
        assert images[1] == "img2_data"
        assert images[2] == "img3_data"

    def test_extract_images_with_none_gaps(self) -> None:
        """Test extraction skips None images."""
        benchmark = MMMUBenchmark()
        task = {
            "image_1": "img1_data",
            "image_2": None,
            "image_3": "img3_data",
        }

        images = benchmark._extract_images(task)
        assert len(images) == 2
        assert images[0] == "img1_data"
        assert images[1] == "img3_data"

    def test_extract_images_handles_errors(self) -> None:
        """Test extraction handles image encoding errors gracefully."""
        benchmark = MMMUBenchmark()
        bad_image = MagicMock()
        bad_image.save = MagicMock(side_effect=Exception("Cannot save"))
        # Ensure hasattr returns True for 'save'
        type(bad_image).save = bad_image.save

        task = {"image_1": bad_image}

        images = benchmark._extract_images(task)
        assert images == []


class TestMMMUExtractAnswer:
    """Tests for MMMU answer extraction."""

    def test_extract_single_letter(self) -> None:
        """Test extracting a single letter answer."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("A") == "A"
        assert benchmark._extract_answer("B") == "B"
        assert benchmark._extract_answer("C") == "C"
        assert benchmark._extract_answer("D") == "D"

    def test_extract_lowercase_letter(self) -> None:
        """Test extracting lowercase letter answer."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("a") == "A"
        assert benchmark._extract_answer("b") == "B"

    def test_extract_parenthesized_letter(self) -> None:
        """Test extracting answer in parentheses."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("(A)") == "A"
        assert benchmark._extract_answer("(B)") == "B"

    def test_extract_answer_is_pattern(self) -> None:
        """Test extracting 'The answer is X' pattern."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("The answer is A") == "A"
        assert benchmark._extract_answer("The correct answer is B") == "B"
        assert benchmark._extract_answer("The final answer is: C") == "C"

    def test_extract_boxed_answer(self) -> None:
        """Test extracting LaTeX boxed answer."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("\\boxed{A}") == "A"
        assert benchmark._extract_answer("Therefore \\boxed{B}") == "B"

    def test_extract_option_pattern(self) -> None:
        """Test extracting 'Option X' pattern."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("Option A is correct") == "A"
        assert benchmark._extract_answer("Choice B") == "B"

    def test_extract_last_letter_fallback(self) -> None:
        """Test extracting the last standalone letter as fallback."""
        benchmark = MMMUBenchmark()
        text = "I think option A is possible, but actually B is better, so C"
        assert benchmark._extract_answer(text) == "C"

    def test_extract_answer_empty_text(self) -> None:
        """Test extracting answer from empty text returns None."""
        benchmark = MMMUBenchmark()
        assert benchmark._extract_answer("") is None
        assert benchmark._extract_answer(None) is None

    def test_extract_answer_no_valid_letter(self) -> None:
        """Test extracting answer when no valid letter is found."""
        benchmark = MMMUBenchmark()
        # Text with no A-D letters as standalone words
        assert benchmark._extract_answer("12345 !! ?? ##") is None

    def test_extract_answer_from_verbose_response(self) -> None:
        """Test extracting answer from a verbose agent response."""
        benchmark = MMMUBenchmark()
        solution = (
            "Looking at the diagram, I can see that the revenue has been "
            "increasing over time. The chart shows a clear upward trend. "
            "Based on my analysis, the total revenue is approximately $200. "
            "Therefore, the answer is B."
        )
        assert benchmark._extract_answer(solution) == "B"


class TestMMMUEvaluate:
    """Tests for MMMU evaluation logic."""

    @pytest.mark.asyncio
    async def test_evaluate_correct_answer(self) -> None:
        """Test evaluation with correct answer."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
            "answer": "B",
        }
        solution = "The answer is B"

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        assert result["resolved"] is True
        assert result["agent_answer"] == "B"
        assert result["correct_answer"] == "B"

    @pytest.mark.asyncio
    async def test_evaluate_incorrect_answer(self) -> None:
        """Test evaluation with incorrect answer."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
            "answer": "B",
        }
        solution = "The answer is C"

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        assert result["resolved"] is False
        assert result["agent_answer"] == "C"
        assert result["correct_answer"] == "B"

    @pytest.mark.asyncio
    async def test_evaluate_no_ground_truth(self) -> None:
        """Test evaluation when no ground truth is available."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
        }
        solution = "A"

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        assert result["resolved"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_evaluate_no_answer_extracted(self) -> None:
        """Test evaluation when no answer can be extracted from solution."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
            "answer": "A",
        }
        solution = "I don't know the answer to this question."

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        # The fallback pattern may match 'I' or other letters,
        # but 'I' is not in [A-D] standalone. Let's use text without any A-D.
        # Actually "I" is not A-D. But we do have no standalone A-D here.
        # Wait, "I" is not in the range A-D. The text has no standalone A-D letters.
        # Actually re-check: "I" is uppercase, but our regex matches [A-D], so I is excluded.
        # The word "don't" doesn't contain A-D as standalone.
        # But "answer" contains 'A' embedded, not standalone (\b boundary).
        # So this should return None -> error path.
        # Actually let's verify: no standalone A, B, C, or D in this text.
        assert result["resolved"] is False

    @pytest.mark.asyncio
    async def test_evaluate_case_insensitive(self) -> None:
        """Test evaluation handles case-insensitive comparison."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
            "answer": "b",
        }
        solution = "The answer is B"

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        assert result["resolved"] is True

    @pytest.mark.asyncio
    async def test_evaluate_ground_truth_answer_field(self) -> None:
        """Test evaluation uses ground_truth_answer as fallback."""
        benchmark = MMMUBenchmark()
        task = {
            "instance_id": "mmmu_0",
            "question": "What is shown?",
            "ground_truth_answer": "D",
        }
        solution = "D"

        env = MagicMock()
        result = await benchmark.evaluate(env, task, solution)
        assert result["resolved"] is True
        assert result["correct_answer"] == "D"


class TestMMMUGetPrebuiltImage:
    """Tests for MMMU pre-built image retrieval."""

    def test_get_prebuilt_image_returns_none(self) -> None:
        """Test that MMMU has no pre-built images."""
        benchmark = MMMUBenchmark()
        task = {"instance_id": "mmmu_0"}
        assert benchmark.get_prebuilt_image(task) is None


class TestMMMUGetPromptTemplate:
    """Tests for MMMU prompt template."""

    def test_prompt_template_has_placeholder(self) -> None:
        """Test that prompt template contains the problem_statement placeholder."""
        benchmark = MMMUBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "{problem_statement}" in prompt

    def test_prompt_template_mentions_multimodal(self) -> None:
        """Test that prompt template mentions multimodal content."""
        benchmark = MMMUBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "multi-modal" in prompt.lower() or "image" in prompt.lower()

    def test_prompt_template_mentions_answer_format(self) -> None:
        """Test that prompt template mentions the answer format."""
        benchmark = MMMUBenchmark()
        prompt = benchmark.get_prompt_template()
        assert "letter" in prompt.lower()


class TestMMMULoadTasks:
    """Tests for MMMU task loading with mocked dataset."""

    @patch("mcpbr.benchmarks.mmmu.load_dataset")
    def test_load_tasks_basic(self, mock_load_dataset: MagicMock) -> None:
        """Test loading tasks from dataset."""
        mock_dataset = [
            {
                "id": "validation_Accounting_1",
                "question": "What is the total revenue?",
                "options": ["$100", "$200", "$300", "$400"],
                "answer": "B",
                "subfield": "Financial Accounting",
                "image_1": None,
            },
            {
                "id": "validation_Accounting_2",
                "question": "What is the net income?",
                "options": ["$50", "$100", "$150", "$200"],
                "answer": "C",
                "subfield": "Managerial Accounting",
                "image_1": None,
            },
        ]
        mock_load_dataset.return_value = mock_dataset

        benchmark = MMMUBenchmark()
        tasks = benchmark.load_tasks()

        assert len(tasks) == 2
        assert tasks[0]["instance_id"] == "mmmu_validation_Accounting_1"
        assert tasks[1]["instance_id"] == "mmmu_validation_Accounting_2"
        assert "problem_statement" in tasks[0]
        assert "ground_truth_answer" in tasks[0]
        mock_load_dataset.assert_called_once_with("MMMU/MMMU", "Accounting", split="validation")

    @patch("mcpbr.benchmarks.mmmu.load_dataset")
    def test_load_tasks_with_sample_size(self, mock_load_dataset: MagicMock) -> None:
        """Test loading tasks with sample size limit."""
        items = [
            {"id": f"q_{i}", "question": f"Question {i}", "options": [], "answer": "A"}
            for i in range(10)
        ]
        mock_load_dataset.return_value = _mock_mmmu_dataset(items)

        benchmark = MMMUBenchmark()
        tasks = benchmark.load_tasks(sample_size=3)

        assert len(tasks) == 3

    @patch("mcpbr.benchmarks.mmmu.load_dataset")
    def test_load_tasks_with_task_ids(self, mock_load_dataset: MagicMock) -> None:
        """Test loading specific tasks by ID."""
        mock_dataset = [
            {"id": "q_1", "question": "Question 1", "options": [], "answer": "A"},
            {"id": "q_2", "question": "Question 2", "options": [], "answer": "B"},
            {"id": "q_3", "question": "Question 3", "options": [], "answer": "C"},
        ]
        mock_load_dataset.return_value = mock_dataset

        benchmark = MMMUBenchmark()
        tasks = benchmark.load_tasks(task_ids=["q_1", "q_3"])

        assert len(tasks) == 2
        assert tasks[0]["id"] == "q_1"
        assert tasks[1]["id"] == "q_3"

    @patch("mcpbr.benchmarks.mmmu.load_dataset")
    def test_load_tasks_with_filter_category(self, mock_load_dataset: MagicMock) -> None:
        """Test loading tasks with category filter overrides subset."""
        mock_dataset = [
            {"id": "q_1", "question": "Question 1", "options": [], "answer": "A"},
        ]
        mock_load_dataset.return_value = mock_dataset

        benchmark = MMMUBenchmark(subset="Accounting")
        benchmark.load_tasks(filter_category=["Biology"])

        mock_load_dataset.assert_called_once_with("MMMU/MMMU", "Biology", split="validation")

    @patch("mcpbr.benchmarks.mmmu.load_dataset")
    def test_load_tasks_augments_fields(self, mock_load_dataset: MagicMock) -> None:
        """Test that loaded tasks have augmented fields."""
        mock_dataset = [
            {
                "id": "q_1",
                "question": "What is this?",
                "options": ["A", "B", "C", "D"],
                "answer": "B",
            },
        ]
        mock_load_dataset.return_value = mock_dataset

        benchmark = MMMUBenchmark()
        tasks = benchmark.load_tasks()

        task = tasks[0]
        assert "instance_id" in task
        assert task["instance_id"] == "mmmu_q_1"
        assert "problem_statement" in task
        assert "ground_truth_answer" in task
        assert task["ground_truth_answer"] == "B"
