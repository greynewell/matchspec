"""Custom benchmark implementation loaded from YAML definition files."""

import base64
import re
from pathlib import Path
from typing import Any

import yaml
from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask

# Required fields in a custom benchmark YAML definition
REQUIRED_YAML_FIELDS = ("name", "dataset", "evaluation_type")

# Supported evaluation types
VALID_EVALUATION_TYPES = ("exact_match", "numeric", "regex", "script")


class CustomBenchmark:
    """Custom benchmark loaded from a YAML definition file.

    Allows users to define benchmarks via YAML without writing Python code.
    Supports HuggingFace datasets or local data, with configurable field mapping
    and multiple evaluation strategies (exact_match, numeric, regex, script).

    Example YAML definition:

        name: my-benchmark
        dataset: my-org/my-dataset
        split: test
        task_id_field: id
        problem_statement_field: question
        answer_field: answer
        evaluation_type: exact_match
    """

    def __init__(self, definition_path: str | Path | None = None, **kwargs: Any):
        """Initialize custom benchmark from a YAML definition file or kwargs.

        Args:
            definition_path: Path to the YAML benchmark definition file.
            **kwargs: Override or provide definition fields directly.
                Useful for programmatic construction or testing.

        Raises:
            FileNotFoundError: If the definition file does not exist.
            ValueError: If required fields are missing or evaluation_type is invalid.
        """
        definition: dict[str, Any] = {}

        if definition_path is not None:
            path = Path(definition_path)
            if not path.exists():
                msg = f"Custom benchmark definition not found: {path}"
                raise FileNotFoundError(msg)

            with open(path) as f:
                definition = yaml.safe_load(f) or {}

        # Merge kwargs on top of file-loaded definition
        definition.update(kwargs)

        self._validate_definition(definition)

        # Core identity
        self.name: str = definition["name"]
        self.dataset: str = definition["dataset"]
        self.subset: str | None = definition.get("subset")
        self.split: str = definition.get("split", "test")

        # Field mapping
        self.task_id_field: str = definition.get("task_id_field", "id")
        self.problem_statement_field: str = definition.get("problem_statement_field", "question")
        self.answer_field: str = definition.get("answer_field", "answer")

        # Evaluation configuration
        self.evaluation_type: str = definition["evaluation_type"]
        self.evaluation_script: str | None = definition.get("evaluation_script")
        self.regex_pattern: str | None = definition.get("regex_pattern")

        # Prompt template
        self.prompt_template: str | None = definition.get("prompt_template")

        # Docker / environment configuration
        self.docker_image: str | None = definition.get("docker_image")
        self.setup_commands: list[str] = definition.get("setup_commands", [])

        # Numeric comparison tolerances
        self.numeric_rtol: float = definition.get("numeric_rtol", 1e-3)
        self.numeric_atol: float = definition.get("numeric_atol", 1e-3)

    @staticmethod
    def _validate_definition(definition: dict[str, Any]) -> None:
        """Validate a custom benchmark definition dictionary.

        Args:
            definition: The parsed YAML definition.

        Raises:
            ValueError: If required fields are missing or values are invalid.
        """
        missing = [f for f in REQUIRED_YAML_FIELDS if f not in definition]
        if missing:
            msg = f"Custom benchmark definition missing required fields: {', '.join(missing)}"
            raise ValueError(msg)

        eval_type = definition.get("evaluation_type")
        if eval_type not in VALID_EVALUATION_TYPES:
            msg = (
                f"Invalid evaluation_type: {eval_type}. "
                f"Must be one of: {', '.join(VALID_EVALUATION_TYPES)}"
            )
            raise ValueError(msg)

        if eval_type == "script" and not definition.get("evaluation_script"):
            msg = "evaluation_script is required when evaluation_type is 'script'"
            raise ValueError(msg)

        if eval_type == "regex" and not definition.get("regex_pattern"):
            msg = "regex_pattern is required when evaluation_type is 'regex'"
            raise ValueError(msg)

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from the configured dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for custom benchmarks.
            filter_difficulty: Unused for custom benchmarks.
            filter_category: Unused for custom benchmarks.
            filter_tags: Unused for custom benchmarks.

        Returns:
            List of task dictionaries augmented with instance_id and problem_statement.
        """
        if self.subset:
            dataset = load_dataset(self.dataset, self.subset, split=self.split)
        else:
            dataset = load_dataset(self.dataset, split=self.split)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = []
            original_indices = []
            for idx, item in enumerate(dataset):
                item_id = str(item.get(self.task_id_field, idx))
                if item_id in task_id_set:
                    tasks.append(item)
                    original_indices.append(idx)
        else:
            tasks = list(dataset)
            original_indices = list(range(len(tasks)))

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]
            original_indices = original_indices[:sample_size]

        augmented_tasks = []
        for idx, task in enumerate(tasks):
            augmented = dict(task)
            # Build instance_id from the task_id_field or index
            raw_id = task.get(self.task_id_field, original_indices[idx])
            augmented["instance_id"] = f"{self.name}_{raw_id}"
            # Build problem_statement from the configured field
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            # Store ground truth answer
            augmented["ground_truth_answer"] = task.get(self.answer_field, "")
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert task to normalized BenchmarkTask.

        Args:
            task: Task dictionary (augmented from load_tasks).

        Returns:
            Normalized BenchmarkTask.

        Raises:
            ValueError: If required fields are missing.
        """
        instance_id = task.get("instance_id")
        if not instance_id:
            msg = f"Task missing required 'instance_id' field: {task.keys()}"
            raise ValueError(msg)

        problem_field_value = task.get(self.problem_statement_field, "")
        if not problem_field_value and not task.get("problem_statement"):
            msg = (
                f"Task missing required '{self.problem_statement_field}' field: {list(task.keys())}"
            )
            raise ValueError(msg)

        problem_statement = task.get("problem_statement") or self._generate_problem_statement(task)

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo=f"{self.name}/custom",
            commit="HEAD",
            metadata={
                "benchmark_name": self.name,
                "evaluation_type": self.evaluation_type,
                "ground_truth_answer": task.get("ground_truth_answer", ""),
                "raw_answer": task.get(self.answer_field, ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task fields.

        If a prompt_template is configured, uses it with field substitution.
        Otherwise, returns the raw problem_statement_field value.

        Args:
            task: Task dictionary.

        Returns:
            Problem statement string.
        """
        raw_statement = task.get(self.problem_statement_field, "No problem statement provided")

        if self.prompt_template:
            try:
                return self.prompt_template.format(
                    problem_statement=raw_statement,
                    **{k: v for k, v in task.items() if isinstance(v, (str, int, float, bool))},
                )
            except KeyError:
                # Fall back to raw statement if template substitution fails
                return str(raw_statement)

        return str(raw_statement)

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create an isolated environment for the task.

        Args:
            task: Task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", f"{self.name}_unknown")

        temp_task = {
            "instance_id": instance_id,
            "repo": f"{self.name}/custom",
            "base_commit": "HEAD",
        }

        env = await docker_manager.create_environment(temp_task)

        # Run setup commands if configured
        if self.setup_commands:
            await self._run_setup_commands(env)

        return env

    async def _run_setup_commands(self, env: TaskEnvironment) -> None:
        """Run configured setup commands in the environment.

        Args:
            env: Task environment.
        """
        for cmd in self.setup_commands:
            _exit_code, _stdout, _stderr = await env.exec_command(
                cmd,
                timeout=300,
            )
            # Continue even if individual setup commands fail

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for the task.

        Dispatches to the appropriate evaluation method based on evaluation_type.

        Args:
            env: Task environment.
            task: Task dictionary.
            solution: Solution to evaluate.

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        ground_truth = task.get("ground_truth_answer", task.get(self.answer_field, ""))

        if not ground_truth:
            return {
                "resolved": False,
                "error": "No ground truth answer available for evaluation",
            }

        if self.evaluation_type == "exact_match":
            return self._evaluate_exact_match(solution, str(ground_truth))
        elif self.evaluation_type == "numeric":
            return self._evaluate_numeric(solution, str(ground_truth))
        elif self.evaluation_type == "regex":
            return self._evaluate_regex(solution, str(ground_truth))
        elif self.evaluation_type == "script":
            return await self._evaluate_script(env, task, solution, str(ground_truth))
        else:
            return {
                "resolved": False,
                "error": f"Unknown evaluation_type: {self.evaluation_type}",
            }

    def _evaluate_exact_match(self, solution: str, ground_truth: str) -> dict[str, Any]:
        """Evaluate using exact string match (case-insensitive, stripped).

        Args:
            solution: Agent's solution.
            ground_truth: Expected answer.

        Returns:
            Evaluation result dictionary.
        """
        normalized_solution = self._normalize_text(solution)
        normalized_truth = self._normalize_text(ground_truth)

        # Check if the ground truth appears in the solution
        resolved = normalized_truth in normalized_solution

        return {
            "resolved": resolved,
            "agent_answer": solution[:500],
            "ground_truth_answer": ground_truth,
            "match_type": "exact_match",
        }

    def _evaluate_numeric(self, solution: str, ground_truth: str) -> dict[str, Any]:
        """Evaluate by comparing numeric values with tolerance.

        Args:
            solution: Agent's solution.
            ground_truth: Expected numeric answer.

        Returns:
            Evaluation result dictionary.
        """
        agent_num = self._extract_number(solution)
        truth_num = self._extract_number(ground_truth)

        if truth_num is None:
            return {
                "resolved": False,
                "error": f"Could not parse ground truth as number: {ground_truth}",
            }

        if agent_num is None:
            return {
                "resolved": False,
                "error": "Could not extract numeric answer from solution",
                "agent_solution": solution[:500],
            }

        resolved = self._compare_numbers(agent_num, truth_num)

        return {
            "resolved": resolved,
            "agent_answer": agent_num,
            "ground_truth_answer": truth_num,
            "match_type": "numeric",
        }

    def _evaluate_regex(self, solution: str, ground_truth: str) -> dict[str, Any]:
        """Evaluate using regex pattern matching.

        The regex_pattern is applied to the solution. If it has a capture group,
        the captured text is compared to the ground truth. Otherwise, the match
        itself is used.

        Args:
            solution: Agent's solution.
            ground_truth: Expected answer.

        Returns:
            Evaluation result dictionary.
        """
        if not self.regex_pattern:
            return {
                "resolved": False,
                "error": "No regex_pattern configured for regex evaluation",
            }

        try:
            match = re.search(self.regex_pattern, solution, re.IGNORECASE | re.DOTALL)
        except re.error as e:
            return {
                "resolved": False,
                "error": f"Invalid regex pattern: {e}",
            }

        if not match:
            return {
                "resolved": False,
                "error": "Regex pattern did not match solution",
                "agent_solution": solution[:500],
            }

        # Use first capture group if available, otherwise use full match
        extracted = match.group(1) if match.lastindex else match.group(0)
        normalized_extracted = self._normalize_text(extracted)
        normalized_truth = self._normalize_text(ground_truth)

        resolved = normalized_extracted == normalized_truth

        return {
            "resolved": resolved,
            "agent_answer": extracted,
            "ground_truth_answer": ground_truth,
            "match_type": "regex",
        }

    async def _evaluate_script(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
        ground_truth: str,
    ) -> dict[str, Any]:
        """Evaluate by running a custom script in the Docker environment.

        The script receives the solution and ground truth as arguments.
        Exit code 0 means the solution is correct.

        Args:
            env: Task environment.
            task: Task dictionary.
            solution: Agent's solution.
            ground_truth: Expected answer.

        Returns:
            Evaluation result dictionary.
        """
        if not self.evaluation_script:
            return {
                "resolved": False,
                "error": "No evaluation_script configured for script evaluation",
            }

        # Write solution and ground truth using base64 to avoid shell injection
        solution_b64 = base64.b64encode(solution.encode()).decode()
        truth_b64 = base64.b64encode(ground_truth.encode()).decode()

        setup_cmd = (
            f"echo '{solution_b64}' | base64 -d > /tmp/solution.txt && "
            f"echo '{truth_b64}' | base64 -d > /tmp/ground_truth.txt"
        )
        await env.exec_command(setup_cmd, timeout=30)

        # Run the evaluation script
        exit_code, stdout, stderr = await env.exec_command(
            self.evaluation_script,
            timeout=300,
        )

        resolved = exit_code == 0

        return {
            "resolved": resolved,
            "agent_answer": solution[:500],
            "ground_truth_answer": ground_truth,
            "match_type": "script",
            "script_exit_code": exit_code,
            "script_stdout": stdout[:1000] if stdout else "",
            "script_stderr": stderr[:1000] if stderr else "",
        }

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for the task.

        Returns the configured docker_image if set, otherwise None.

        Args:
            task: Task dictionary.

        Returns:
            Docker image name or None.
        """
        return self.docker_image

    def get_prompt_template(self) -> str:
        """Get the benchmark prompt template.

        Returns the configured prompt_template or a sensible default.

        Returns:
            Prompt template string with {problem_statement} placeholder.
        """
        if self.prompt_template:
            return self.prompt_template

        return (
            f"Solve the following {self.name} benchmark task:\n\n"
            "{problem_statement}\n\n"
            "Provide your answer clearly."
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for comparison by lowercasing, stripping, collapsing whitespace.

        Args:
            text: Input text.

        Returns:
            Normalized text.
        """
        return " ".join(text.lower().strip().split())

    @staticmethod
    def _extract_number(text: str) -> float | None:
        """Extract the last numeric value from text.

        Handles commas, dollar signs, percentages, and negative numbers.

        Args:
            text: Text potentially containing a number.

        Returns:
            Extracted float or None.
        """
        if not text:
            return None

        # Try #### format first (GSM8K-style)
        match = re.search(r"####\s*([+-]?[\d,]+(?:\.\d+)?)", text)
        if match:
            return CustomBenchmark._parse_number(match.group(1))

        # Try "the answer is X" pattern
        match = re.search(
            r"(?:the\s+)?(?:final\s+)?answer\s*(?:is|:)\s*\$?([+-]?[\d,]+(?:\.\d+)?)",
            text,
            re.IGNORECASE,
        )
        if match:
            return CustomBenchmark._parse_number(match.group(1))

        # Fallback: last number in the text
        numbers = re.findall(r"([+-]?[\d,]+(?:\.\d+)?)", text)
        if numbers:
            return CustomBenchmark._parse_number(numbers[-1])

        return None

    @staticmethod
    def _parse_number(num_str: str) -> float | None:
        """Parse a number string to float.

        Args:
            num_str: String representation of number.

        Returns:
            Float value or None if parsing fails.
        """
        try:
            cleaned = num_str.replace(",", "").replace("$", "").replace("%", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def _compare_numbers(
        self,
        answer1: float,
        answer2: float,
    ) -> bool:
        """Compare two numeric answers with configurable tolerance.

        Args:
            answer1: First answer.
            answer2: Second answer.

        Returns:
            True if answers are equal within tolerance.
        """
        if answer1 == answer2:
            return True

        abs_diff = abs(answer1 - answer2)
        rel_diff = abs_diff / max(abs(answer1), abs(answer2), 1e-10)

        return abs_diff <= self.numeric_atol or rel_diff <= self.numeric_rtol
