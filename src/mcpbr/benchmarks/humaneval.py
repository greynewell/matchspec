"""HumanEval benchmark implementation."""

import base64
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask


class HumanEvalBenchmark:
    """HumanEval benchmark implementation.

    HumanEval is a benchmark for evaluating code generation models on Python
    programming problems. Each task requires completing a function given its
    signature and docstring.

    Tasks involve generating function implementations that pass unit tests.
    Evaluation runs the provided test cases against the generated code.
    """

    name = "humaneval"

    def __init__(self, dataset: str = "openai_humaneval"):
        """Initialize HumanEval benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
        """
        self.dataset = dataset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        _level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from HumanEval dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for HumanEval (no difficulty levels).
            filter_difficulty: Unused for HumanEval (no difficulty classification).
            filter_category: Unused for HumanEval (no category classification).
            filter_tags: Unused for HumanEval (no tag system).

        Returns:
            List of HumanEval task dictionaries.
        """
        # Silence unused parameter warnings - required by Benchmark protocol
        _ = filter_difficulty
        _ = filter_category
        _ = filter_tags
        dataset = load_dataset(self.dataset, split="test")

        if task_ids:
            # Use set for O(1) lookup performance
            task_id_set = set(task_ids)
            tasks = []
            for item in dataset:
                if item["task_id"] in task_id_set:
                    tasks.append(item)
        else:
            tasks = list(dataset)

        if sample_size is not None and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        # Augment tasks with instance_id for compatibility with harness
        augmented_tasks = []
        for task in tasks:
            augmented = dict(task)
            # Use task_id as instance_id (e.g., "HumanEval/0")
            # Replace slash with underscore for Docker-safe naming
            augmented["instance_id"] = task["task_id"].replace("/", "_")
            # Generate problem_statement for the harness
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented_tasks.append(augmented)

        return augmented_tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert HumanEval task to normalized format.

        Args:
            task: HumanEval task dictionary.

        Returns:
            Normalized BenchmarkTask.

        Raises:
            ValueError: If task_id is missing from task.
        """
        instance_id = task.get("instance_id")
        if not instance_id:
            task_id = task.get("task_id")
            if not task_id:
                msg = f"Task missing required 'task_id' or 'instance_id' field: {task.keys()}"
                raise ValueError(msg)
            instance_id = task_id.replace("/", "_")

        problem_statement = self._generate_problem_statement(task)

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo="openai/humaneval",
            commit="HEAD",
            metadata={
                "prompt": task.get("prompt", ""),
                "canonical_solution": task.get("canonical_solution", ""),
                "test": task.get("test", ""),
                "entry_point": task.get("entry_point", ""),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Args:
            task: HumanEval task dictionary.

        Returns:
            Problem statement for the agent.
        """
        task_id = task.get("task_id", "unknown")
        prompt = task.get("prompt", "")
        entry_point = task.get("entry_point", "")

        statement = (
            f"Complete the following Python function ({task_id}):\n\n"
            f"```python\n{prompt}\n```\n\n"
            f"INSTRUCTIONS:\n"
            f"- Implement the function '{entry_point}' according to the docstring\n"
            f"- The function signature is already provided\n"
            f"- Write only the function implementation\n"
            f"- Ensure your code passes all test cases\n"
            f"- Do NOT modify the function signature\n"
            f"- Save your implementation to a file named 'solution.py'"
        )

        return statement

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for HumanEval task.

        Creates a lightweight Python environment for code execution.

        Args:
            task: HumanEval task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        import tempfile

        # Get instance_id with fallback to task_id (sanitized)
        instance_id = task.get("instance_id")
        if not instance_id:
            # Fallback to task_id with slash replaced by underscore
            task_id = task.get("task_id", "unknown")
            instance_id = task_id.replace("/", "_")

        # Create a simple Python environment without git repo cloning
        # Use fallback image which is a lightweight Python container
        await docker_manager._ensure_fallback_image()
        image_name = docker_manager.FALLBACK_IMAGE

        # Create temporary directory for this task
        temp_dir = tempfile.TemporaryDirectory(prefix=f"mcpbr_{instance_id}_")
        docker_manager._temp_dirs.append(temp_dir)
        host_workdir = temp_dir.name

        container_name = f"mcpbr-{docker_manager._session_id}-{instance_id}"
        container_workdir = "/workspace"

        # Create container
        container = docker_manager.client.containers.run(
            image_name,
            command="tail -f /dev/null",
            name=container_name,
            detach=True,
            network_mode="bridge",
            volumes={
                host_workdir: {"bind": "/workspace", "mode": "rw"},
            },
            working_dir=container_workdir,
            remove=False,
            labels={
                "mcpbr": "true",
                "session_id": docker_manager._session_id,
                "instance_id": instance_id,
            },
        )

        docker_manager._containers.append(container)

        env = TaskEnvironment(
            container=container,
            workdir=container_workdir,
            host_workdir=host_workdir,
            instance_id=instance_id,
            uses_prebuilt=False,
            claude_cli_installed=False,
        )

        # Ensure Python 3 is available
        await self._setup_python_environment(env)

        # Initialize git repository in HOST workdir for change tracking
        # The harness checks for git changes on the host, so initialize there
        import subprocess

        host_workdir = env.host_workdir
        subprocess.run(["git", "init"], cwd=host_workdir, capture_output=True, check=False)
        subprocess.run(
            ["git", "config", "user.email", "mcpbr@example.com"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "config", "user.name", "MCPBR"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit", "--allow-empty"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )

        return env

    async def _setup_python_environment(self, env: TaskEnvironment) -> None:
        """Setup Python environment with necessary packages.

        Args:
            env: Task environment.

        Raises:
            RuntimeError: If Python installation fails.
        """
        # Check if Python is already available
        exit_code, stdout, stderr = await env.exec_command("python3 --version", timeout=10)
        python_available = exit_code == 0

        # Check if git is available
        exit_code, stdout, stderr = await env.exec_command("git --version", timeout=10)
        git_available = exit_code == 0

        if python_available and git_available:
            # Both already available
            return

        # Install Python and git if not available
        packages = []
        if not python_available:
            packages.extend(["python3", "python3-pip"])
        if not git_available:
            packages.append("git")

        install_cmd = f"apt-get update -qq && apt-get install -y -qq {' '.join(packages)} 2>&1"
        exit_code, stdout, stderr = await env.exec_command(install_cmd, timeout=300)

        # Verify Python installation succeeded
        if not python_available:
            exit_code, stdout, stderr = await env.exec_command("python3 --version", timeout=10)
            if exit_code != 0:
                raise RuntimeError(f"Failed to install Python 3: {stderr}")

        # Verify git installation succeeded
        if not git_available:
            exit_code, stdout, stderr = await env.exec_command("git --version", timeout=10)
            if exit_code != 0:
                raise RuntimeError(f"Failed to install git: {stderr}")

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for HumanEval task.

        Runs the unit tests against the generated code.

        Args:
            env: Task environment.
            task: HumanEval task dictionary.
            solution: Solution code to evaluate (function implementation).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        # Extract test code from task
        test_code = task.get("test", "")
        entry_point = task.get("entry_point", "")

        if not test_code:
            return {
                "resolved": False,
                "error": "No test code provided in task",
            }

        # Try to find the solution file created by the agent
        solution_file = await self._find_solution_file(env)

        if not solution_file:
            # Agent might have included the solution directly in the response
            # Try to extract code from the solution string
            solution_code = self._extract_code_from_solution(solution)
            if not solution_code:
                return {
                    "resolved": False,
                    "error": "No solution file found and could not extract code from solution",
                }

            # Write the solution to a file using base64 to avoid delimiter issues
            solution_file = "solution.py"
            encoded_solution = base64.b64encode(solution_code.encode()).decode()
            exit_code, stdout, stderr = await env.exec_command(
                f"echo '{encoded_solution}' | base64 -d > {solution_file}",
                timeout=10,
            )
            if exit_code != 0:
                return {
                    "resolved": False,
                    "error": f"Failed to write solution file: {stderr}",
                }

        # Read the solution code
        exit_code, solution_content, stderr = await env.exec_command(
            f"cat {solution_file}",
            timeout=10,
        )
        if exit_code != 0:
            return {
                "resolved": False,
                "error": f"Failed to read solution file: {stderr}",
            }

        # Create a test file combining the solution and test code
        test_file_content = f"{solution_content}\n\n{test_code}\n\ncheck({entry_point})\n"

        # Write test file using base64 to avoid delimiter issues
        test_file = "test_solution.py"
        encoded_test = base64.b64encode(test_file_content.encode()).decode()
        exit_code, stdout, stderr = await env.exec_command(
            f"echo '{encoded_test}' | base64 -d > {test_file}",
            timeout=10,
        )
        if exit_code != 0:
            return {
                "resolved": False,
                "error": f"Failed to write test file: {stderr}",
            }

        # Run the test
        exit_code, stdout, stderr = await env.exec_command(
            f"python3 {test_file}",
            timeout=30,
        )

        # Test passes if exit code is 0 and no assertion errors
        passed = exit_code == 0 and "AssertionError" not in stderr

        result = {
            "resolved": passed,
            "exit_code": exit_code,
            "stdout": stdout[:1000] if stdout else "",  # Limit output size
            "stderr": stderr[:1000] if stderr else "",
        }

        if not passed:
            if "AssertionError" in stderr:
                result["error"] = "Test assertions failed"
            else:
                result["error"] = f"Test execution failed with exit code {exit_code}"

        return result

    async def _find_solution_file(self, env: TaskEnvironment) -> str | None:
        """Find the solution file created by the agent.

        Args:
            env: Task environment.

        Returns:
            Path to solution file or None if not found.
        """
        # Common solution filenames
        candidates = [
            "solution.py",
            "answer.py",
            "code.py",
            "implementation.py",
            "main.py",
        ]

        for filename in candidates:
            exit_code, _, _ = await env.exec_command(
                f"test -f {filename}",
                timeout=5,
            )
            if exit_code == 0:
                return filename

        return None

    def _extract_code_from_solution(self, solution: str) -> str | None:
        """Extract Python code from solution string.

        Handles various formats like markdown code blocks, plain text, etc.

        Args:
            solution: Solution string from agent.

        Returns:
            Extracted code or None if no code found.
        """
        # Try to extract from markdown code block
        if "```python" in solution:
            start = solution.find("```python") + len("```python")
            end = solution.find("```", start)
            if end != -1:
                return solution[start:end].strip()

        # Try generic code block
        if "```" in solution:
            start = solution.find("```") + 3
            end = solution.find("```", start)
            if end != -1:
                code = solution[start:end].strip()
                # Check if it looks like Python code
                if "def " in code or "return" in code:
                    return code

        # If solution looks like code directly (contains def keyword)
        if "def " in solution:
            # Try to extract just the function definition, handling nested functions
            lines = solution.split("\n")
            code_lines = []
            in_function = False
            base_indent = None

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def ") and not in_function:
                    # Found the start of the target function
                    in_function = True
                    # Calculate base indentation level (leading spaces)
                    base_indent = len(line) - len(line.lstrip())
                    code_lines.append(line)
                elif in_function:
                    # Inside the function
                    if stripped:  # Non-empty line
                        line_indent = len(line) - len(line.lstrip())
                        # Stop at next top-level (same or less indentation) def/class
                        if line_indent <= base_indent and (
                            stripped.startswith("def ") or stripped.startswith("class ")
                        ):
                            # Reached next top-level definition, stop
                            break
                    code_lines.append(line)

            if code_lines:
                return "\n".join(code_lines)

        return None

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for HumanEval task.

        HumanEval doesn't use pre-built images - uses minimal Python environments.

        Args:
            _task: HumanEval task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get HumanEval prompt template.

        Returns:
            Prompt template for code generation tasks.
        """
        return (
            "Complete the following Python function:\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Implement the function according to its docstring\n"
            "- The function signature is already provided - do NOT change it\n"
            "- Write clean, correct Python code\n"
            "- Ensure your implementation passes all test cases\n"
            "- Save your implementation to a file named 'solution.py'\n"
            "- Include ONLY the function implementation in the file"
        )
