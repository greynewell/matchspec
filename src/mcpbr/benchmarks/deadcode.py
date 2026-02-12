"""Dead code detection benchmark implementation."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask

# Corpus repository configuration
CORPUS_REPO = "git@github.com:supermodeltools/dead-code-benchmark-corpus.git"
CORPUS_HTTPS = "https://github.com/supermodeltools/dead-code-benchmark-corpus.git"
DEFAULT_CORPUS_CACHE = Path.home() / ".cache" / "mcpbr" / "dead-code-benchmark-corpus"

# Placeholder content for the report file - agent will modify this
REPORT_PLACEHOLDER = """{
  "dead_code": [],
  "analysis_complete": false
}
"""


def _clone_or_update_corpus(corpus_path: Path | None = None) -> Path:
    """Clone or update the dead-code-benchmark-corpus repository.

    Args:
        corpus_path: Optional path to use. If None, uses DEFAULT_CORPUS_CACHE.

    Returns:
        Path to the corpus directory.
    """
    corpus_dir = corpus_path or DEFAULT_CORPUS_CACHE
    corpus_dir.parent.mkdir(parents=True, exist_ok=True)

    if corpus_dir.exists() and (corpus_dir / ".git").exists():
        # Update existing repo
        subprocess.run(
            ["git", "pull", "--quiet"],
            cwd=corpus_dir,
            capture_output=True,
            check=False,
        )
    else:
        # Clone fresh
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)

        # Try SSH first, fall back to HTTPS
        result = subprocess.run(
            ["git", "clone", "--quiet", CORPUS_REPO, str(corpus_dir)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "clone", "--quiet", CORPUS_HTTPS, str(corpus_dir)],
                capture_output=True,
                check=True,
            )

    return corpus_dir


def _load_corpus_task(
    corpus_dir: Path, task_name: str = "typescript-express-app"
) -> dict[str, Any]:
    """Load a task from the corpus.

    Args:
        corpus_dir: Path to the corpus directory.
        task_name: Name of the task (directory name).

    Returns:
        Task dictionary with repo_content, dead_code, alive_code.
    """
    # Load ground truth
    ground_truth_path = corpus_dir / ".benchmark" / f"{task_name}.json"
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth not found: {ground_truth_path}")

    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    # Load all source files
    task_dir = corpus_dir / task_name
    src_dir = task_dir / "src"

    repo_content: dict[str, str] = {}
    repo_content["REPORT.json"] = REPORT_PLACEHOLDER

    # Walk all TypeScript files
    for ts_file in src_dir.rglob("*.ts"):
        rel_path = ts_file.relative_to(task_dir)
        repo_content[str(rel_path)] = ts_file.read_text()

    # Include package.json and tsconfig if they exist
    for config_file in ["package.json", "tsconfig.json"]:
        config_path = task_dir / config_file
        if config_path.exists():
            repo_content[config_file] = config_path.read_text()

    # Load pre-generated dead code analysis separately (only for MCP agent)
    mcp_only_content: dict[str, str] = {}
    analysis_path = task_dir / ".supermodel" / "dead-code-analysis.json"
    if analysis_path.exists():
        mcp_only_content[".supermodel/dead-code-analysis.json"] = analysis_path.read_text()

    return {
        "instance_id": ground_truth["metadata"]["task_id"],
        "language": ground_truth["metadata"]["language"],
        "difficulty": ground_truth["metadata"].get("difficulty", "hard"),
        "repo_content": repo_content,
        "mcp_only_content": mcp_only_content,  # Only written for MCP agent
        "dead_code": ground_truth["dead_code"],
        "alive_code": ground_truth["alive_code"],
        "metadata": ground_truth["metadata"],
    }


class DeadCodeBenchmark:
    """Dead code detection benchmark."""

    name = "dead-code"

    def __init__(self, dataset: str | Path = "", corpus_path: str | Path | None = None):
        """Initialize the benchmark.

        Args:
            dataset: Path to a JSON dataset file (legacy, optional).
            corpus_path: Path to cached corpus directory. If None, uses default cache.
        """
        self.dataset = dataset
        self.corpus_path = Path(corpus_path) if corpus_path else None
        self._tasks: list[dict[str, Any]] | None = None
        self._corpus_dir: Path | None = None

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        _level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        _ = filter_tags
        tasks = self._load_raw_tasks()

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t["instance_id"] in task_id_set]

        if filter_difficulty:
            difficulty_set = set(filter_difficulty)
            tasks = [t for t in tasks if t.get("difficulty", "medium") in difficulty_set]

        if filter_category:
            category_set = set(filter_category)
            tasks = [t for t in tasks if t.get("language", "python") in category_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        # Add problem_statement to each task (required by harness)
        for task in tasks:
            task["problem_statement"] = self._generate_problem_statement(task)

        return tasks

    def _load_raw_tasks(self) -> list[dict[str, Any]]:
        if self._tasks is not None:
            return self._tasks

        # First check for explicit dataset file
        dataset_path = Path(self.dataset) if self.dataset else None
        if dataset_path and dataset_path.exists():
            with open(dataset_path) as f:
                self._tasks = json.load(f)
            return self._tasks

        # Load from corpus repository
        try:
            self._corpus_dir = _clone_or_update_corpus(self.corpus_path)
            task = _load_corpus_task(self._corpus_dir, "typescript-express-app")
            self._tasks = [task]
        except Exception as e:
            # Fall back to error message if corpus unavailable
            raise RuntimeError(
                f"Failed to load dead code corpus: {e}\n"
                "Ensure you have access to the supermodeltools/dead-code-benchmark-corpus repository."
            ) from e

        return self._tasks

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        instance_id = task.get("instance_id", "unknown")
        problem_statement = self._generate_problem_statement(task)

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo="local/dead-code-detection",
            commit="HEAD",
            metadata={
                "language": task.get("language", "unknown"),
                "difficulty": task.get("difficulty", "medium"),
                "dead_code": task.get("dead_code", []),
                "alive_code": task.get("alive_code", []),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        instance_id = task.get("instance_id", "unknown")
        language = task.get("language", "unknown")
        metadata = task.get("metadata", {})
        total_files = metadata.get("total_files", len(task.get("repo_content", {})))
        dead_count = metadata.get("dead_functions", len(task.get("dead_code", [])))

        # List files (excluding config files for cleaner output)
        files = [
            f
            for f in task.get("repo_content", {}).keys()
            if f not in ("REPORT.json", "package.json", "tsconfig.json")
            and not f.startswith(".supermodel/")
        ]

        return f"""Find all dead code in this {language} codebase.

Task: {instance_id}
Total files: {total_files}
Approximate dead functions: {dead_count}

Source files to analyze:
{chr(10).join(f"  - {f}" for f in sorted(files)[:20])}
{f"  ... and {len(files) - 20} more files" if len(files) > 20 else ""}

INSTRUCTIONS:
1. Read all source files in the workspace
2. Identify entry points (exported functions, route handlers, main modules)
3. Trace the call graph to find which functions are actually reachable
4. Find functions/classes/variables that are NEVER called or referenced

CRITICAL: Update the existing REPORT.json file with your findings.
Format: a JSON object with "dead_code" array containing objects with file, name, line, and type fields.
Set "analysis_complete" to true when done.

Rules:
- Exported functions that are used by routes ARE alive (they are entry points)
- Functions called transitively from entry points are NOT dead
- Functions that are only referenced in comments/strings ARE dead
- Only mark truly unreachable code as dead
"""

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
        is_mcp: bool = False,
    ) -> TaskEnvironment:
        instance_id = task.get("instance_id", "unknown")
        repo_content = task.get("repo_content", {})
        mcp_only_content = task.get("mcp_only_content", {})

        await docker_manager._ensure_fallback_image()
        image_name = docker_manager.FALLBACK_IMAGE

        temp_dir = tempfile.TemporaryDirectory(prefix=f"mcpbr_{instance_id}_")
        docker_manager._temp_dirs.append(temp_dir)
        host_workdir = temp_dir.name

        # Write all files including REPORT.json
        for file_path, content in repo_content.items():
            full_path = Path(host_workdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        # Write MCP-only files (e.g., pre-computed analysis) only for MCP agent
        if is_mcp:
            for file_path, content in mcp_only_content.items():
                full_path = Path(host_workdir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

        container_name = f"mcpbr-{docker_manager._session_id}-{instance_id}"
        container_workdir = "/workspace"

        container = docker_manager.client.containers.run(
            image_name,
            command="tail -f /dev/null",
            name=container_name,
            detach=True,
            network_mode="bridge",
            volumes={host_workdir: {"bind": "/workspace", "mode": "rw"}},
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

        # Init git so modifications are tracked
        subprocess.run(["git", "init"], cwd=host_workdir, capture_output=True, check=False)
        subprocess.run(
            ["git", "config", "user.email", "mcpbr@test.com"],
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
        subprocess.run(["git", "add", "-A"], cwd=host_workdir, capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )

        return env

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate by reading REPORT.json from the workspace."""
        expected_dead = task.get("dead_code", [])
        expected_alive = task.get("alive_code", [])

        # Read REPORT.json from host (faster than docker exec)
        report_path = Path(env.host_workdir) / "REPORT.json"

        agent_findings: list[dict[str, Any]] = []

        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)
                agent_findings = report.get("dead_code", [])
            except (json.JSONDecodeError, IOError):
                # Try parsing from the solution/patch string
                agent_findings = self._extract_findings_from_text(solution)
        else:
            agent_findings = self._extract_findings_from_text(solution)

        # Calculate metrics
        found_set = {(f.get("file", ""), f.get("name", "")) for f in agent_findings}
        dead_set = {(d.get("file", ""), d.get("name", "")) for d in expected_dead}
        alive_set = {(a.get("file", ""), a.get("name", "")) for a in expected_alive}

        tp = len(found_set & dead_set)
        fp = len(found_set & alive_set)
        fn = len(dead_set - found_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        resolved = precision >= 0.8 and recall >= 0.8

        # Log results for visibility
        print(f"\n{'=' * 50}")
        print(f"DEAD CODE EVALUATION - {env.instance_id}")
        print(f"  Found: {len(agent_findings)} items")
        print(f"  Expected: {len(expected_dead)} dead functions")
        print(f"  True Positives: {tp}")
        print(f"  False Positives: {fp}")
        print(f"  False Negatives: {fn}")
        print(f"  Precision: {precision * 100:.1f}%")
        print(f"  Recall: {recall * 100:.1f}%")
        print(f"  F1 Score: {f1 * 100:.1f}%")
        print(f"{'=' * 50}\n")

        return {
            "resolved": resolved,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "found": len(agent_findings),
            "expected": len(expected_dead),
        }

    def _extract_findings_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract findings from text/patch content."""
        findings = []

        # Look for JSON with dead_code array
        try:
            # Find JSON object in text
            start = text.find('"dead_code"')
            if start != -1:
                # Find the array start
                arr_start = text.find("[", start)
                if arr_start != -1:
                    # Find matching bracket
                    depth = 0
                    for i, c in enumerate(text[arr_start:], arr_start):
                        if c == "[":
                            depth += 1
                        elif c == "]":
                            depth -= 1
                            if depth == 0:
                                arr_text = text[arr_start : i + 1]
                                findings = json.loads(arr_text)
                                break
        except (json.JSONDecodeError, ValueError):
            pass

        return findings

    def get_prebuilt_image(self, task: dict[str, Any]) -> str | None:
        return None

    def get_prompt_template(self) -> str:
        return (
            "Analyze the codebase and identify all dead code.\n\n"
            "{problem_statement}\n\n"
            "Update REPORT.json with your findings."
        )
