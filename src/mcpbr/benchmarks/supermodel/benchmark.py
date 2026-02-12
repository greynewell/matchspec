"""SupermodelBenchmark -- PR-based analysis benchmark for mcpbr.

Supports multiple analysis types (dead-code, impact, test-coverage, circular-deps)
via endpoint plugins. Uses GitHub PRs for ground truth extraction and the Supermodel
API for pre-computed analysis in the enhanced (MCP) condition.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ...docker_env import DockerEnvironmentManager, TaskEnvironment
from ..base import BenchmarkTask
from .api_client import call_supermodel_api
from .endpoints import get_endpoint
from .evaluation import compute_prf1
from .git_utils import clone_repo_at_commit, get_pre_merge_commit, zip_repo

logger = logging.getLogger("mcpbr.supermodel")

REPORT_PLACEHOLDER = """{
  "dead_code": [],
  "analysis_complete": false
}
"""

DEFAULT_GT_DIR = Path.home() / ".cache" / "mcpbr" / "supermodel_ground_truth"


class SupermodelBenchmark:
    """Supermodel analysis benchmark with PR-based ground truth.

    Implements the mcpbr Benchmark protocol. Each task is a GitHub PR
    where the ground truth is extracted from the diff.
    """

    name = "supermodel"

    def __init__(
        self,
        analysis_type: str = "dead-code",
        tasks: list[dict[str, Any]] | None = None,
        supermodel_api_base: str = "https://staging.api.supermodeltools.com",
        supermodel_api_key: str | None = None,
        resolved_threshold: float = 0.8,
        ground_truth_dir: str | Path | None = None,
        **kwargs: Any,
    ):
        """Initialize the Supermodel benchmark.

        Args:
            analysis_type: Analysis endpoint to use (dead-code, impact, test-coverage,
                          circular-deps).
            tasks: List of task config dicts from YAML.
            supermodel_api_base: Base URL for Supermodel API.
            supermodel_api_key: API key (or set SUPERMODEL_API_KEY env var).
            resolved_threshold: P & R threshold to consider a task 'resolved'.
            ground_truth_dir: Directory to cache ground truth JSON files.
            **kwargs: Additional keyword arguments (ignored for forward compat).
        """
        self.analysis_type = analysis_type
        self._tasks_config = tasks or []
        self.api_base = supermodel_api_base
        self.api_key = supermodel_api_key or os.environ.get("SUPERMODEL_API_KEY")
        self.resolved_threshold = resolved_threshold
        self.gt_dir = Path(ground_truth_dir) if ground_truth_dir else DEFAULT_GT_DIR
        self.gt_dir.mkdir(parents=True, exist_ok=True)

        self._endpoint = get_endpoint(analysis_type)
        self._loaded_tasks: list[dict[str, Any]] | None = None
        self._work_dir = Path(tempfile.mkdtemp(prefix="mcpbr_supermodel_"))

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        _level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from config and extract ground truth from PR diffs.

        Ground truth is cached in gt_dir to avoid repeated GitHub API calls.
        """
        _ = _level, filter_tags

        tasks = []
        for task_cfg in self._tasks_config:
            task_id = task_cfg["id"]
            repo = task_cfg["repo"]
            pr_number = task_cfg["pr_number"]
            merge_commit = task_cfg["merge_commit"]
            language = task_cfg.get("language", "typescript")
            scope_prefix = task_cfg.get("scope_prefix")
            description = task_cfg.get("description", "")

            # Load or extract ground truth
            gt = self._load_ground_truth(task_id, repo, pr_number, language, scope_prefix)

            if not gt:
                logger.warning(f"No ground truth for {task_id}, skipping")
                continue

            task = {
                "instance_id": task_id,
                "repo": repo,
                "pr_number": pr_number,
                "merge_commit": merge_commit,
                "language": language,
                "scope_prefix": scope_prefix,
                "description": description,
                "ground_truth": gt,
                "problem_statement": self._generate_baseline_problem_statement(task_cfg),
                "problem_statement_enhanced": self._generate_enhanced_problem_statement(task_cfg),
                "problem_statement_baseline": self._generate_baseline_problem_statement(task_cfg),
            }
            tasks.append(task)

        if task_ids:
            task_id_set = set(task_ids)
            tasks = [t for t in tasks if t["instance_id"] in task_id_set]

        if filter_difficulty:
            difficulty_set = set(filter_difficulty)
            tasks = [t for t in tasks if t.get("difficulty", "hard") in difficulty_set]

        if filter_category:
            category_set = set(filter_category)
            tasks = [t for t in tasks if t.get("language", "typescript") in category_set]

        if sample_size and len(tasks) > sample_size:
            tasks = tasks[:sample_size]

        self._loaded_tasks = tasks
        return tasks

    def _load_ground_truth(
        self,
        task_id: str,
        repo: str,
        pr_number: int,
        language: str,
        scope_prefix: str | None,
    ) -> list[dict]:
        """Load cached ground truth or extract from PR diff."""
        ep_name = self._endpoint.name
        gt_path = self.gt_dir / f"{ep_name}_{task_id}.json"

        if gt_path.exists():
            with open(gt_path) as f:
                gt = json.load(f)
            logger.info(f"Loaded cached GT: {len(gt)} items from {gt_path}")
            return gt

        logger.info(f"Extracting ground truth for {task_id} from PR diff...")
        gt = self._endpoint.extract_ground_truth(repo, pr_number, language, scope_prefix)

        with open(gt_path, "w") as f:
            json.dump(gt, f, indent=2)
        logger.info(f"Extracted {len(gt)} ground truth items -> {gt_path}")

        return gt

    def _generate_enhanced_problem_statement(self, task_cfg: dict) -> str:
        """Generate problem statement for the enhanced (graph-assisted) condition.

        The agent gets a pre-computed analysis JSON from a call graph analyzer.
        The analyzer has already done reachability analysis -- these ARE dead code.
        The agent should do light validation and filter obvious false positives.
        """
        language = task_cfg.get("language", "typescript")
        analysis_file = self._endpoint.analysis_filename

        return f"""You are a code analyst. Find all dead code in this {language} codebase.

A call graph analyzer has already analyzed this codebase and identified dead code
candidates. The results are in `{analysis_file}`.

The analyzer uses full call graph reachability -- it traces which functions are
actually called from entry points, not just whether a name appears in the code.
This means its candidates ARE unreachable code, even if the name appears elsewhere
(e.g., in __all__ exports, self-recursive calls, or atexit registrations that
reference unused state).

IMPORTANT DISTINCTIONS:
- A function listed in __all__ but never actually imported/called = DEAD
- Two functions that only call each other but nothing calls either = DEAD cluster
- A cleanup function registered with atexit but whose state is never populated = DEAD
- A constant that is only referenced in its own module's dead functions = DEAD

YOUR JOB:
1. Read `{analysis_file}` to get the candidate list.
2. For each candidate, do a quick sanity check -- only REMOVE a candidate if you
   find clear evidence it is genuinely live (e.g., it IS an entry point called by
   a framework, or it is imported and called in a main execution path).
3. Err on the side of KEEPING candidates. The analyzer's call graph is more
   reliable than a simple grep. If you're unsure, keep it.
4. Write your filtered findings to REPORT.json.

REPORT.json format:
{{
  "dead_code": [
    {{"file": "path/to/file.py", "name": "unused_func", "type": "function", "reason": "unreachable from entry points"}},
    ...
  ],
  "analysis_complete": true
}}

Type should be one of: function, class, method, const."""

    def _generate_baseline_problem_statement(self, task_cfg: dict) -> str:
        """Generate problem statement for the baseline (manual analysis) condition.

        The agent must find dead code by reading and searching the codebase directly.
        """
        language = task_cfg.get("language", "typescript")

        return f"""You are a code analyst. Find all dead code in this {language} codebase.

Dead code = functions, classes, methods, and constants that are defined but never
used in any meaningful execution path. This includes:
- Functions/methods defined but never called from any entry point
- Constants defined but never read by any live code
- Functions that only call each other (dead clusters) with no external caller
- Functions in __all__ that are never actually imported by other modules
- Cleanup/utility functions whose associated state is never populated

YOUR JOB:
1. List all source files (exclude test files from the dead code search -- tests
   are consumers, not definitions to check).
2. Read each non-test source file and identify all function, class, and constant
   definitions.
3. For each definition, trace whether it is reachable from an actual entry point
   (main functions, module-level code that runs on import, framework callbacks).
   A function that is only referenced by its own definition or by other dead
   functions is still dead.
4. Write your findings to REPORT.json.

REPORT.json format:
{{
  "dead_code": [
    {{"file": "path/to/file.py", "name": "unused_func", "type": "function", "reason": "no callers from entry points"}},
    ...
  ],
  "analysis_complete": true
}}

Type should be one of: function, class, method, const.
When in doubt about whether something is dead, INCLUDE it -- false positives
are better than false negatives for this analysis."""

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        instance_id = task.get("instance_id", "unknown")
        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=task.get("problem_statement", ""),
            repo=task.get("repo", "unknown"),
            commit=task.get("merge_commit", "HEAD"),
            metadata={
                "language": task.get("language", "typescript"),
                "analysis_type": self.analysis_type,
                "ground_truth_count": len(task.get("ground_truth", [])),
            },
        )

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
        is_mcp: bool = False,
    ) -> TaskEnvironment:
        """Create an isolated environment for the task.

        For baseline: clone repo at pre-merge commit, write REPORT.json placeholder.
        For MCP (enhanced): also call Supermodel API and place analysis JSON.
        """
        # Swap problem_statement based on condition so the agent gets the right prompt
        if is_mcp:
            task["problem_statement"] = task.get(
                "problem_statement_enhanced", task["problem_statement"]
            )
        else:
            task["problem_statement"] = task.get(
                "problem_statement_baseline", task["problem_statement"]
            )

        instance_id = task["instance_id"]
        repo = task["repo"]
        merge_commit = task["merge_commit"]
        scope_prefix = task.get("scope_prefix")

        # Get pre-merge commit
        pre_merge = get_pre_merge_commit(repo, merge_commit)
        logger.info(f"Pre-merge commit for {instance_id}: {pre_merge[:8]}")

        # Clone repo
        repo_dir = self._work_dir / f"repo-{instance_id}"
        if not repo_dir.exists():
            await clone_repo_at_commit(repo, pre_merge, str(repo_dir))

        # Create Docker environment
        await docker_manager._ensure_fallback_image()
        image_name = docker_manager.FALLBACK_IMAGE

        temp_dir = tempfile.TemporaryDirectory(prefix=f"mcpbr_{instance_id}_")
        docker_manager._temp_dirs.append(temp_dir)
        host_workdir = temp_dir.name

        # Copy repo to workdir (scoped if needed)
        if scope_prefix:
            src_path = repo_dir / scope_prefix
            dest_path = Path(host_workdir) / scope_prefix
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dest_path))
            else:
                shutil.copytree(str(repo_dir), host_workdir, dirs_exist_ok=True)
        else:
            shutil.copytree(str(repo_dir), host_workdir, dirs_exist_ok=True)

        # Write REPORT.json placeholder
        report_path = Path(host_workdir) / "REPORT.json"
        report_path.write_text(REPORT_PLACEHOLDER)

        # For MCP (enhanced) condition: call Supermodel API and place analysis JSON
        if is_mcp:
            try:
                analysis_json = await self._get_analysis(repo_dir, instance_id, scope_prefix)
                analysis_path = Path(host_workdir) / self._endpoint.analysis_filename
                analysis_path.write_text(json.dumps(analysis_json, indent=2))
                logger.info(f"Placed analysis at {analysis_path}")
            except Exception as e:
                logger.error(f"Failed to get Supermodel analysis for {instance_id}: {e}")

        # Start Docker container
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

        # Init git so the harness can track modifications
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
        subprocess.run(
            ["git", "add", "-A"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=host_workdir,
            capture_output=True,
            check=False,
        )

        return env

    async def _get_analysis(
        self,
        repo_dir: Path,
        task_id: str,
        scope_prefix: str | None,
    ) -> dict:
        """Call Supermodel API and return parsed/filtered analysis."""
        zip_path = str(self._work_dir / f"{task_id}.zip")
        await zip_repo(str(repo_dir), zip_path, scope_prefix)

        raw_response = await call_supermodel_api(
            endpoint_path=self._endpoint.api_path,
            zip_path=zip_path,
            api_base=self.api_base,
            api_key=self.api_key,
        )

        return self._endpoint.parse_api_response(raw_response)

    async def evaluate(
        self,
        env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate by reading REPORT.json from the workspace and computing P/R/F1."""
        ground_truth = task.get("ground_truth", [])
        key_fields = self._endpoint.key_fields

        # Read REPORT.json from host
        report_path = Path(env.host_workdir) / "REPORT.json"
        agent_findings: list[dict[str, Any]] = []

        if report_path.exists():
            try:
                with open(report_path) as f:
                    report = json.load(f)
                agent_findings = report.get("dead_code", [])
            except (json.JSONDecodeError, OSError):
                agent_findings = self._extract_findings_from_text(solution)
        else:
            agent_findings = self._extract_findings_from_text(solution)

        # Compute P/R/F1
        metrics = compute_prf1(agent_findings, ground_truth, key_fields)

        precision = metrics["precision"]
        recall = metrics["recall"]
        resolved = precision >= self.resolved_threshold and recall >= self.resolved_threshold

        # Log results
        print(f"\n{'=' * 50}")
        print(f"SUPERMODEL EVALUATION - {env.instance_id} ({self.analysis_type})")
        print(f"  Found: {metrics['found']} items")
        print(f"  Expected: {metrics['expected']} items")
        print(f"  True Positives: {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")
        print(f"  Precision: {precision * 100:.1f}%")
        print(f"  Recall: {recall * 100:.1f}%")
        print(f"  F1 Score: {metrics['f1_score'] * 100:.1f}%")
        print(f"  Resolved: {resolved}")
        print(f"{'=' * 50}\n")

        return {
            "resolved": resolved,
            **metrics,
        }

    def _extract_findings_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract findings from text/patch content as fallback."""
        findings: list[dict[str, Any]] = []
        try:
            start = text.find('"dead_code"')
            if start != -1:
                arr_start = text.find("[", start)
                if arr_start != -1:
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
        return "{problem_statement}"
