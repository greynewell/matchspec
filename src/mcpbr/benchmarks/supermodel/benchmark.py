"""SupermodelBenchmark -- PR-based analysis benchmark for mcpbr.

Supports multiple analysis types (dead-code, impact, test-coverage, circular-deps)
via endpoint plugins. Uses GitHub PRs for ground truth extraction and the Supermodel
API for pre-computed analysis in the enhanced (MCP) condition.
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
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
    evaluate_without_patch = True  # Uses REPORT.json, not git diff

    def __init__(
        self,
        analysis_type: str = "dead-code",
        tasks: list[dict[str, Any]] | None = None,
        supermodel_api_base: str = "https://staging.api.supermodeltools.com",
        supermodel_api_key: str | None = None,
        resolved_threshold: float = 0.8,
        ground_truth_dir: str | Path | None = None,
        supermodel_api_timeout: int = 900,
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
            supermodel_api_timeout: Max seconds to wait for Supermodel API (default 900).
            **kwargs: Additional keyword arguments (ignored for forward compat).
        """
        self.analysis_type = analysis_type
        self._tasks_config = tasks or []
        self.api_base = supermodel_api_base
        self.api_key = supermodel_api_key or os.environ.get("SUPERMODEL_API_KEY")
        self.api_timeout = supermodel_api_timeout
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
            repo = task_cfg.get("repo", "")
            language = task_cfg.get("language", "typescript")
            scope_prefix = task_cfg.get("scope_prefix")
            description = task_cfg.get("description", "")

            # Corpus mode: ground_truth_file points to a pre-existing GT JSON
            gt_file = task_cfg.get("ground_truth_file")
            if gt_file:
                gt_path = Path(gt_file).expanduser()
                if gt_path.exists():
                    with open(gt_path) as f:
                        gt = json.load(f)
                    logger.info(f"Loaded corpus GT: {len(gt)} items from {gt_path}")
                else:
                    logger.warning(f"GT file not found: {gt_path}, skipping {task_id}")
                    continue
            else:
                # PR mode: extract from diff
                pr_number = task_cfg["pr_number"]
                gt = self._load_ground_truth(task_id, repo, pr_number, language, scope_prefix)

            if not gt:
                logger.warning(f"No ground truth for {task_id}, skipping")
                continue

            task = {
                "instance_id": task_id,
                "repo": repo,
                "pr_number": task_cfg.get("pr_number"),
                "merge_commit": task_cfg.get("merge_commit", task_cfg.get("commit", "HEAD")),
                "commit": task_cfg.get("commit"),
                "clone_url": task_cfg.get("clone_url"),
                "language": language,
                "scope_prefix": scope_prefix,
                "description": description,
                "ground_truth": gt,
                "problem_statement": self._generate_baseline_problem_statement(task_cfg),
                "problem_statement_enhanced": self._generate_enhanced_problem_statement(task_cfg),
                "problem_statement_baseline": self._generate_baseline_problem_statement(task_cfg),
                "zip_exclude": task_cfg.get("zip_exclude", []),
                "cached_analysis": task_cfg.get("cached_analysis"),
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
        Its job is to faithfully transcribe ALL candidates into REPORT.json.
        """
        language = task_cfg.get("language", "typescript")
        analysis_file = self._endpoint.analysis_filename

        ext = ".ts" if language == "typescript" else ".py"

        return f"""You are a code analyst. Find all dead code in this {language} codebase.

A call graph analyzer has already analyzed this codebase and identified dead code
candidates. The results are in `{analysis_file}`.

The analyzer uses full call graph reachability -- it traces which functions are
actually called from entry points, not just whether a name appears in the code.
This means its candidates ARE unreachable code. Trust the analyzer.

IMPORTANT: Use the MCP filesystem tools (read_text_file, write_file) for ALL file
I/O in this task. Do NOT use the built-in Read/Write tools.

YOUR ONLY JOB:

1. Read `{analysis_file}` using the filesystem read_text_file tool.
2. Extract the deadCodeCandidates array.
3. Write REPORT.json using the filesystem write_file tool with EVERY candidate.
   Do NOT filter, validate, or remove any candidates. Include ALL of them.

REPORT.json format:
{{
  "dead_code": [
    {{"file": "path/to/file{ext}", "name": "unusedFunc", "type": "function", "reason": "unreachable from entry points"}},
    ...
  ],
  "analysis_complete": true
}}

Type should be one of: function, class, method, const.

CRITICAL RULES:
- Include EVERY candidate from the analysis file. Do NOT skip any.
- Do NOT investigate or validate candidates by reading source files.
- Do NOT filter candidates based on your own judgment.
- Your ONLY job is to faithfully transcribe candidates into REPORT.json.
- Once REPORT.json is written, you are DONE. Stop immediately."""

    def _generate_baseline_problem_statement(self, task_cfg: dict) -> str:
        """Generate problem statement for the baseline (manual analysis) condition.

        The agent must find dead code by reading and searching the codebase directly.
        """
        language = task_cfg.get("language", "typescript")

        ext = ".ts" if language == "typescript" else ".py"
        if language == "python":
            lang_hints = """- Functions in __all__ that are never actually imported by other modules
- Cleanup/utility functions whose associated state is never populated"""
        else:
            lang_hints = """- Exported functions/classes that are never imported by any other module
- Middleware or handlers that are defined but never registered with the router
- Methods on classes where the class itself is never instantiated from live code"""

        return f"""You are a code analyst. Find all dead code in this {language} codebase.

IMPORTANT: Use the MCP filesystem tools (read_text_file, write_file) for ALL file
I/O in this task. Do NOT use the built-in Read/Write tools.

Dead code = functions, classes, methods, and constants that are defined but never
used in any meaningful execution path. This includes:
- Functions/methods defined but never called from any entry point
- Constants defined but never read by any live code
- Functions that only call each other (dead clusters) with no external caller
{lang_hints}

YOUR JOB:
1. List all source files (exclude test files from the dead code search -- tests
   are consumers, not definitions to check).
2. Read each non-test source file and identify all function, class, and constant
   definitions.
3. For each definition, trace whether it is reachable from an actual entry point
   (main functions, module-level code that runs on import, framework callbacks).
   A function that is only referenced by its own definition or by other dead
   functions is still dead.
4. Write your findings to REPORT.json using the filesystem write_file tool.

REPORT.json format:
{{
  "dead_code": [
    {{"file": "path/to/file{ext}", "name": "unusedFunc", "type": "function", "reason": "no callers from entry points"}},
    ...
  ],
  "analysis_complete": true
}}

Type should be one of: function, class, method, const, interface, variable.
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
        repo = task.get("repo", "")
        scope_prefix = task.get("scope_prefix")

        # Clone repo - corpus mode (clone_url + commit) or PR mode (repo + merge_commit)
        repo_dir = self._work_dir / f"repo-{instance_id}"
        if not repo_dir.exists():
            clone_url = task.get("clone_url")
            if clone_url:
                # Corpus mode: clone directly at specified commit
                commit = task.get("commit", "HEAD")
                logger.info(f"Corpus mode: cloning {clone_url} at {commit[:8]}")
                await clone_repo_at_commit(clone_url, commit, str(repo_dir))
            else:
                # PR mode: get pre-merge commit from merge commit
                merge_commit = task["merge_commit"]
                pre_merge = get_pre_merge_commit(repo, merge_commit)
                logger.info(f"Pre-merge commit for {instance_id}: {pre_merge[:8]}")
                await clone_repo_at_commit(repo, pre_merge, str(repo_dir))

        # Create Docker environment
        await docker_manager._ensure_fallback_image()
        image_name = docker_manager.FALLBACK_IMAGE

        temp_dir = tempfile.TemporaryDirectory(prefix=f"mcpbr_{instance_id}_")
        docker_manager._temp_dirs.append(temp_dir)
        host_workdir = temp_dir.name

        # Copy repo to workdir (scoped if needed)
        is_corpus = task.get("clone_url") is not None
        if scope_prefix:
            src_path = repo_dir / scope_prefix
            if src_path.is_dir():
                if is_corpus:
                    # Corpus mode: scoped content goes to workdir root so GT paths match
                    shutil.copytree(str(src_path), host_workdir, dirs_exist_ok=True)
                else:
                    # PR mode: preserve directory structure for PR-relative paths
                    dest_path = Path(host_workdir) / scope_prefix
                    shutil.copytree(str(src_path), str(dest_path))
            else:
                shutil.copytree(str(repo_dir), host_workdir, dirs_exist_ok=True)
        else:
            shutil.copytree(str(repo_dir), host_workdir, dirs_exist_ok=True)

        # Write REPORT.json placeholder
        report_path = Path(host_workdir) / "REPORT.json"
        report_path.write_text(REPORT_PLACEHOLDER)

        # For MCP (enhanced) condition: place analysis JSON in workdir
        # Priority: 1) cached_analysis file from task config, 2) Supermodel API call
        if is_mcp:
            try:
                cached_path = task.get("cached_analysis")
                if cached_path and Path(cached_path).exists():
                    with open(cached_path) as f:
                        analysis_json = json.load(f)
                    print(
                        f"  Using cached analysis: {cached_path}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    exclude_patterns = task.get("zip_exclude", [])
                    analysis_json = await self._get_analysis(
                        repo_dir,
                        instance_id,
                        scope_prefix,
                        exclude_patterns,
                        strip_prefix=is_corpus,
                    )

                # Slim down the analysis for agent consumption:
                # Strip verbose fields (code snippets, descriptions) — agent
                # only needs file/name/type. With just these fields, even 1000+
                # candidates stay under 100KB which is well within read limits.
                keep_fields = {"file", "name", "type", "reason", "confidence"}
                for key in ("deadCodeCandidates", "candidates", "items"):
                    if key in analysis_json:
                        items = analysis_json[key]
                        items = [
                            {k: v for k, v in item.items() if k in keep_fields} for item in items
                        ]
                        analysis_json[key] = items

                # Strip top-level keys the agent doesn't need.
                # Keep only metadata + the candidate list; drop aliveCode,
                # entryPoints, sourceCode, ast, rawGraph, etc.
                candidate_key = None
                for k in ("deadCodeCandidates", "candidates", "items"):
                    if k in analysis_json:
                        candidate_key = k
                        break
                keep_top_keys = {"metadata", candidate_key} if candidate_key else {"metadata"}
                for drop_key in list(analysis_json.keys()):
                    if drop_key not in keep_top_keys:
                        analysis_json.pop(drop_key)

                analysis_path = Path(host_workdir) / self._endpoint.analysis_filename
                analysis_path.write_text(json.dumps(analysis_json, indent=2))
                logger.info(f"Placed analysis at {analysis_path}")
            except Exception as e:
                logger.error(f"Failed to get Supermodel analysis for {instance_id}: {e}")
                print(
                    f"\n*** SUPERMODEL ANALYSIS FAILED for {instance_id} ***\n"
                    f"{traceback.format_exc()}",
                    file=sys.stderr,
                    flush=True,
                )

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
        exclude_patterns: list[str] | None = None,
        strip_prefix: bool = True,
    ) -> dict:
        """Call Supermodel API and return parsed/filtered analysis.

        Results are cached in gt_dir/{task_id}_analysis.json keyed by zip hash
        so subsequent runs skip the API call.
        """
        zip_path = str(self._work_dir / f"{task_id}.zip")
        await zip_repo(str(repo_dir), zip_path, scope_prefix, exclude_patterns)

        # Check cache
        with open(zip_path, "rb") as f:
            zip_hash = hashlib.sha256(f.read()).hexdigest()[:12]
        cache_path = self.gt_dir / f"{task_id}_analysis_{zip_hash}.json"
        if cache_path.exists():
            logger.info(f"Using cached analysis: {cache_path}")
            with open(cache_path) as f:
                return json.load(f)

        raw_response = await call_supermodel_api(
            endpoint_path=self._endpoint.api_path,
            zip_path=zip_path,
            api_base=self.api_base,
            api_key=self.api_key,
            max_poll_time=self.api_timeout,
        )

        result = self._endpoint.parse_api_response(raw_response)

        # Strip scope_prefix from file paths so they match the workdir layout.
        # Only in corpus mode (strip_prefix=True): workdir content is at root.
        # In PR mode (strip_prefix=False): scope_prefix dir is preserved in workdir.
        if scope_prefix and strip_prefix:
            prefix = scope_prefix.rstrip("/") + "/"
            for key in ("deadCodeCandidates", "candidates", "items"):
                if key in result:
                    for item in result[key]:
                        fp = item.get("file", "")
                        if fp.startswith(prefix):
                            item["file"] = fp[len(prefix) :]

        # Cache the result for future runs
        cache_path.write_text(json.dumps(result, indent=2))
        logger.info(f"Cached analysis at {cache_path}")

        return result

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
