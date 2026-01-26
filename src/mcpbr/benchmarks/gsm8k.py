"""GSM8K benchmark implementation."""

import re
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class GSM8KBenchmark:
    """GSM8K benchmark implementation.

    Tasks involve solving grade-school math word problems.
    Agents must read the problem, perform mathematical reasoning
    (often using chain-of-thought), and produce a numeric answer.

    Evaluation compares the final numeric answer against ground truth
    with support for different numeric formats (integers, decimals, fractions).
    """

    name = "gsm8k"

    def __init__(self, dataset: str = "openai/gsm8k", subset: str = "main"):
        """Initialize GSM8K benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset/config name (default: 'main').
        """
        self.dataset = dataset
        self.subset = subset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from GSM8K dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for GSM8K (no difficulty levels).

        Returns:
            List of GSM8K task dictionaries.
        """
        # GSM8K uses 'test' split for evaluation
        dataset = load_dataset(self.dataset, self.subset, split="test")

        if task_ids:
            # task_ids in GSM8K are indices (0, 1, 2, ...)
            task_id_set = set(task_ids)
            tasks = []
            for idx, item in enumerate(dataset):
                if str(idx) in task_id_set:
                    tasks.append(item)
        else:
            tasks = list(dataset)

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        # Augment tasks with instance_id for compatibility with harness
        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            # Use index as instance_id since GSM8K doesn't have explicit IDs
            augmented["instance_id"] = f"gsm8k_{idx}"
            # Generate problem_statement from question
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            # Store the ground truth answer for evaluation
            augmented["ground_truth_answer"] = task.get("answer", "")
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert GSM8K task to normalized format.

        Args:
            task: GSM8K task dictionary.

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

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo="gsm8k/math",
            commit="HEAD",
            metadata={
                "question": question,
                "answer": task.get("answer", ""),
                "ground_truth_numeric": self._extract_answer(task.get("answer", "")),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: GSM8K task dictionary.

        Returns:
            Problem statement for the agent.
        """
        question = task.get("question", "No question provided")

        statement = (
            f"Solve the following math problem:\n\n"
            f"{question}\n\n"
            f"Show your work and reasoning step-by-step (chain-of-thought). "
            f"Provide your final numeric answer at the end."
        )

        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for GSM8K task.

        GSM8K doesn't require repository setup - creates minimal environment
        with Python and basic math libraries.

        Args:
            task: GSM8K task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        # Create minimal environment
        instance_id = task.get("instance_id", "gsm8k_unknown")

        temp_task = {
            "instance_id": instance_id,
            "repo": "gsm8k/math",
            "base_commit": "HEAD",
        }

        env = await docker_manager.create_environment(temp_task)

        # Install Python and math libraries
        await self._setup_environment(env)

        return env

    async def _setup_environment(self, env: TaskEnvironment) -> None:
        """Setup environment with Python and math tools.

        Args:
            env: Task environment.
        """
        # Install Python packages that might be useful for math
        install_cmd = (
            "apt-get update -qq && "
            "apt-get install -y -qq python3 python3-pip && "
            "pip3 install --quiet numpy scipy sympy 2>&1 | grep -v 'Requirement already satisfied' || true"
        )

        exit_code, stdout, stderr = await env.exec_command(
            install_cmd,
            timeout=300,
        )
        # Don't fail if installation has issues - proceed anyway

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for GSM8K task.

        Extracts the numeric answer from the solution and compares it
        to the ground truth answer with tolerance for different formats.

        Args:
            env: Task environment.
            task: GSM8K task dictionary.
            solution: Solution to evaluate (agent's response with reasoning and answer).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Extract ground truth answer
        ground_truth_str = task.get("answer", "")
        if not ground_truth_str:
            return {
                "resolved": False,
                "error": "No ground truth answer available for evaluation",
            }

        ground_truth_numeric = self._extract_answer(ground_truth_str)
        if ground_truth_numeric is None:
            return {
                "resolved": False,
                "error": f"Could not parse ground truth answer: {ground_truth_str}",
            }

        # Extract answer from agent's solution
        agent_answer = self._extract_answer(solution)
        if agent_answer is None:
            return {
                "resolved": False,
                "error": "Could not extract numeric answer from agent's solution",
                "agent_solution": solution[:500],  # Include snippet for debugging
            }

        # Compare answers with tolerance
        resolved = self._compare_answers(agent_answer, ground_truth_numeric)

        return {
            "resolved": resolved,
            "agent_answer": agent_answer,
            "ground_truth_answer": ground_truth_numeric,
            "answer_match": resolved,
        }

    def _extract_answer(self, text: str) -> float | None:
        """Extract numeric answer from text.

        Handles various formats:
        - Plain numbers: "42", "3.14"
        - Numbers with commas: "1,234"
        - Numbers in sentences: "The answer is 42."
        - Dollar amounts: "$1,234.56"
        - Percentages: "25%"
        - Negative numbers: "-42"
        - Boxed answers (LaTeX): "\\boxed{42}"

        Args:
            text: Text containing the answer.

        Returns:
            Numeric answer as float, or None if no answer found.
        """
        if not text:
            return None

        # Try to extract from common answer patterns
        # Pattern 1: "####" followed by number (GSM8K ground truth format)
        match = re.search(r"####\s*([+-]?[\d,]+(?:\.\d+)?)", text)
        if match:
            return self._parse_number(match.group(1))

        # Pattern 2: LaTeX boxed answer: \boxed{number}
        match = re.search(r"\\boxed\{([+-]?[\d,]+(?:\.\d+)?)\}", text)
        if match:
            return self._parse_number(match.group(1))

        # Pattern 3: "The answer is X" or "Final answer: X"
        match = re.search(
            r"(?:the\s+)?(?:final\s+)?answer\s*(?:is|:)\s*\$?([+-]?[\d,]+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if match:
            return self._parse_number(match.group(1))

        # Pattern 4: Last number in the text (fallback)
        # Find all numbers in the text
        numbers = re.findall(r"([+-]?[\d,]+(?:\.\d+)?)", text)
        if numbers:
            # Return the last number found (often the final answer)
            return self._parse_number(numbers[-1])

        return None

    def _parse_number(self, num_str: str) -> float | None:
        """Parse a number string to float.

        Args:
            num_str: String representation of number.

        Returns:
            Float value or None if parsing fails.
        """
        try:
            # Remove commas and dollar signs
            cleaned = num_str.replace(",", "").replace("$", "").replace("%", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _compare_answers(
        self,
        answer1: float,
        answer2: float,
        rtol: float = 1e-3,
        atol: float = 1e-3,
    ) -> bool:
        """Compare two numeric answers with tolerance.

        Uses both relative and absolute tolerance to handle:
        - Small numbers (where absolute difference matters)
        - Large numbers (where relative difference matters)
        - Rounding differences

        Args:
            answer1: First answer.
            answer2: Second answer.
            rtol: Relative tolerance (default: 0.001 = 0.1%).
            atol: Absolute tolerance (default: 0.001).

        Returns:
            True if answers are equal within tolerance.
        """
        # Check for exact equality first
        if answer1 == answer2:
            return True

        # Use relative and absolute tolerance
        abs_diff = abs(answer1 - answer2)
        rel_diff = abs_diff / max(abs(answer1), abs(answer2), 1e-10)

        return abs_diff <= atol or rel_diff <= rtol

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for GSM8K task.

        GSM8K doesn't use pre-built images - builds minimal environments.

        Args:
            task: GSM8K task dictionary.

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get GSM8K prompt template.

        Returns:
            Prompt template for solving math problems.
        """
        return (
            "Solve the following grade-school math problem:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Show your reasoning step-by-step (chain-of-thought)\n"
            "- Break down complex problems into smaller steps\n"
            "- Clearly state your final numeric answer\n"
            "- Use the format 'The answer is: <number>' for your final answer\n"
            "- You can use Python for calculations if needed"
        )
