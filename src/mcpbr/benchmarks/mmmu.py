"""MMMU (Massive Multi-discipline Multimodal Understanding) benchmark implementation."""

import base64
import io
import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class MMMUBenchmark:
    """MMMU benchmark implementation.

    The Massive Multi-discipline Multimodal Understanding (MMMU) benchmark
    evaluates multimodal models on college-level subject knowledge across
    30 subjects and 183 subfields. Tasks require understanding images
    (diagrams, charts, figures, etc.) alongside text to answer
    multiple-choice questions (A, B, C, D).

    Evaluation compares the selected answer letter against the ground truth.
    """

    name = "mmmu"

    def __init__(self, dataset: str = "MMMU/MMMU", subset: str = "Accounting"):
        """Initialize MMMU benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset/config name (default: 'Accounting').
                MMMU is organized by subject (e.g., 'Accounting', 'Art',
                'Biology', 'Chemistry', 'Computer_Science', etc.).
        """
        self.dataset = dataset
        self.subset = subset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from MMMU dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for MMMU (no difficulty levels).
            filter_difficulty: Unused for MMMU.
            filter_category: Filter by subject category (overrides subset).
            filter_tags: Unused for MMMU.

        Returns:
            List of MMMU task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        subset = self.subset
        if filter_category and len(filter_category) > 0:
            subset = filter_category[0]

        # MMMU uses 'validation' split for evaluation (test labels are hidden)
        dataset = load_dataset(self.dataset, subset, split="validation")

        # Optimization: use dataset.select() for early truncation when no
        # filtering is needed — avoids materializing the entire dataset.
        needs_full_scan = bool(task_ids)
        if not needs_full_scan and sample_size is not None and len(dataset) > sample_size:
            dataset = dataset.select(range(sample_size))

        tasks = list(dataset)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t.get("id", "") in task_id_set]

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            augmented["instance_id"] = f"mmmu_{task.get('id', idx)}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented["ground_truth_answer"] = task.get("answer", "")
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert MMMU task to normalized format.

        Args:
            task: MMMU task dictionary.

        Returns:
            Normalized BenchmarkTask.

        Raises:
            ValueError: If required fields are missing.
        """
        instance_id = task.get("instance_id")
        if not instance_id:
            msg = f"Task missing required 'instance_id' field: {task.keys()}"
            raise ValueError(msg)

        question = task.get("question", "")
        if not question:
            msg = f"Task missing required 'question' field: {task.keys()}"
            raise ValueError(msg)

        problem_statement = self._generate_problem_statement(task)

        metadata: dict[str, Any] = {
            "question": question,
            "answer": task.get("answer", ""),
            "subject": task.get("subfield", task.get("subject", "")),
            "options": task.get("options", []),
        }

        # Encode images as base64 in metadata
        image_data = self._extract_images(task)
        if image_data:
            metadata["images"] = image_data

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo="mmmu/multimodal",
            commit="HEAD",
            metadata=metadata,
        )

    def _extract_images(self, task: dict[str, Any]) -> list[str]:
        """Extract and encode images from the task as base64 strings.

        MMMU tasks can contain up to 7 images in fields image_1 through image_7.

        Args:
            task: MMMU task dictionary.

        Returns:
            List of base64-encoded image strings.
        """
        images = []
        for i in range(1, 8):
            image_key = f"image_{i}"
            image = task.get(image_key)
            if image is not None:
                try:
                    # Handle PIL Image objects from HuggingFace datasets
                    if hasattr(image, "save"):
                        buffer = io.BytesIO()
                        image.save(buffer, format="PNG")
                        img_bytes = buffer.getvalue()
                        images.append(base64.b64encode(img_bytes).decode("utf-8"))
                    elif isinstance(image, bytes):
                        images.append(base64.b64encode(image).decode("utf-8"))
                    elif isinstance(image, str):
                        # Already base64 or a path - store as-is
                        images.append(image)
                except Exception:  # noqa: S112 -- intentionally skip unreadable images and continue processing others
                    # Skip images that cannot be encoded
                    continue
        return images

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: MMMU task dictionary.

        Returns:
            Problem statement for the agent.
        """
        question = task.get("question", "No question provided")
        options = task.get("options", [])
        subject = task.get("subfield", task.get("subject", ""))

        statement = ""
        if subject:
            statement += f"Subject: {subject}\n\n"

        statement += f"Question:\n{question}\n\n"

        # Include image references in the statement
        image_data = self._extract_images(task)
        if image_data:
            statement += f"[This question includes {len(image_data)} image(s). "
            statement += "The image data is provided as base64-encoded PNG in the metadata.]\n\n"

        if options:
            statement += "Options:\n"
            labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
            for i, option in enumerate(options):
                if i < len(labels):
                    statement += f"  ({labels[i]}) {option}\n"

        statement += (
            "\nSelect the correct answer by providing ONLY the letter "
            "(A, B, C, or D) of the correct option."
        )

        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for MMMU task.

        MMMU doesn't require complex environment setup - creates minimal
        environment since evaluation is based on answer comparison.

        Args:
            task: MMMU task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "mmmu_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "mmmu/multimodal",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for MMMU task.

        Extracts the answer letter from the solution and compares it
        to the ground truth answer.

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: MMMU task dictionary.
            solution: Solution to evaluate (agent's response with answer letter).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        ground_truth = task.get("answer", task.get("ground_truth_answer", ""))
        if not ground_truth:
            return {
                "resolved": False,
                "error": "No ground truth answer available for evaluation",
            }

        # Normalize ground truth to uppercase letter
        ground_truth = ground_truth.strip().upper()

        # Extract answer from agent's solution
        agent_answer = self._extract_answer(solution)
        if agent_answer is None:
            return {
                "resolved": False,
                "error": "Could not extract answer letter from agent's solution",
                "agent_solution": solution[:500],
            }

        resolved = agent_answer == ground_truth

        return {
            "resolved": resolved,
            "agent_answer": agent_answer,
            "correct_answer": ground_truth,
        }

    def _extract_answer(self, text: str) -> str | None:
        """Extract the answer letter from the agent's response.

        Handles various formats:
        - Plain letter: "A", "B", "C", "D"
        - Parenthesized: "(A)", "(B)"
        - Sentence: "The answer is A", "The correct option is B"
        - Boxed: "\\boxed{A}"

        Args:
            text: Text containing the answer.

        Returns:
            Uppercase answer letter, or None if no answer found.
        """
        if not text:
            return None

        text_upper = text.upper().strip()

        # Pattern 1: LaTeX boxed answer
        match = re.search(r"\\boxed\{([A-D])\}", text_upper)
        if match:
            return match.group(1)

        # Pattern 2: "The answer is X" or "The correct answer is X"
        match = re.search(
            r"(?:the\s+)?(?:correct\s+)?(?:final\s+)?answer\s*(?:is|:)\s*\(?([A-D])\)?",
            text_upper,
        )
        if match:
            return match.group(1)

        # Pattern 3: "Option X" or "Choice X"
        match = re.search(r"(?:option|choice)\s*(?:is\s*)?:?\s*\(?([A-D])\)?", text_upper)
        if match:
            return match.group(1)

        # Pattern 4: Standalone letter (last single A-D found as a word boundary)
        matches = re.findall(r"\b([A-D])\b", text_upper)
        if matches:
            return str(matches[-1])

        return None

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for MMMU task.

        MMMU doesn't use pre-built images.

        Args:
            _task: MMMU task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get MMMU prompt template.

        Returns:
            Prompt template for multimodal understanding questions.
        """
        return (
            "Answer the following multi-modal question that may include images, "
            "diagrams, charts, or figures:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Carefully examine any images, diagrams, or figures provided\n"
            "- Apply your knowledge of the relevant subject area\n"
            "- Consider each answer option carefully\n"
            "- Show your reasoning step-by-step\n"
            "- Respond with ONLY the letter of the correct answer (A, B, C, or D)"
        )

    def get_default_sandbox_level(self) -> str | None:
        return None
