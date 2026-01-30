"""Dead code detection benchmark implementation."""

import json
import tempfile
from pathlib import Path
from typing import Any

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask

# Placeholder content for the report file - agent will modify this
REPORT_PLACEHOLDER = """{
  "dead_code": [],
  "analysis_complete": false
}
"""

# Pre-generated call graphs for each task (implements issue #82 concept)
# These provide instant context injection without API calls
CALL_GRAPH_001 = """{
  "metadata": {
    "generated_at": "2025-01-30T12:00:00Z",
    "language": "typescript",
    "task_id": "dead-code-001"
  },
  "nodes": [
    {"id": "src/index.ts::<module>", "file": "src/index.ts", "name": "<module>", "type": "module", "line": 1, "exported": true},
    {"id": "src/utils.ts::usedFunction", "file": "src/utils.ts", "name": "usedFunction", "type": "function", "line": 1, "exported": true},
    {"id": "src/utils.ts::helperFunction", "file": "src/utils.ts", "name": "helperFunction", "type": "function", "line": 6, "exported": false},
    {"id": "src/utils.ts::neverCalled", "file": "src/utils.ts", "name": "neverCalled", "type": "function", "line": 10, "exported": false},
    {"id": "src/utils.ts::alsoNeverCalled", "file": "src/utils.ts", "name": "alsoNeverCalled", "type": "function", "line": 14, "exported": false},
    {"id": "src/utils.ts::unusedArrow", "file": "src/utils.ts", "name": "unusedArrow", "type": "variable", "line": 18, "exported": false},
    {"id": "src/utils.ts::anotherUsedFunction", "file": "src/utils.ts", "name": "anotherUsedFunction", "type": "function", "line": 22, "exported": true}
  ],
  "edges": [
    {"from": "src/index.ts::<module>", "to": "src/utils.ts::usedFunction", "type": "call"},
    {"from": "src/index.ts::<module>", "to": "src/utils.ts::anotherUsedFunction", "type": "call"},
    {"from": "src/utils.ts::usedFunction", "to": "src/utils.ts::helperFunction", "type": "call"},
    {"from": "src/utils.ts::anotherUsedFunction", "to": "src/utils.ts::usedFunction", "type": "call"}
  ],
  "entry_points": ["src/index.ts::<module>", "src/utils.ts::usedFunction", "src/utils.ts::anotherUsedFunction"]
}
"""

CALL_GRAPH_002 = """{
  "metadata": {
    "generated_at": "2025-01-30T12:00:00Z",
    "language": "python",
    "task_id": "dead-code-002"
  },
  "nodes": [
    {"id": "app/main.py::<module>", "file": "app/main.py", "name": "<module>", "type": "module", "line": 1, "exported": true},
    {"id": "app/main.py::main", "file": "app/main.py", "name": "main", "type": "function", "line": 3, "exported": false},
    {"id": "app/utils.py::process_data", "file": "app/utils.py", "name": "process_data", "type": "function", "line": 1, "exported": true},
    {"id": "app/utils.py::validate_input", "file": "app/utils.py", "name": "validate_input", "type": "function", "line": 5, "exported": true},
    {"id": "app/utils.py::format_output", "file": "app/utils.py", "name": "format_output", "type": "function", "line": 11, "exported": false},
    {"id": "app/utils.py::deprecated_processor", "file": "app/utils.py", "name": "deprecated_processor", "type": "function", "line": 15, "exported": false},
    {"id": "app/utils.py::legacy_validator", "file": "app/utils.py", "name": "legacy_validator", "type": "function", "line": 19, "exported": false},
    {"id": "app/utils.py::UnusedClass", "file": "app/utils.py", "name": "UnusedClass", "type": "class", "line": 23, "exported": false}
  ],
  "edges": [
    {"from": "app/main.py::<module>", "to": "app/main.py::main", "type": "call"},
    {"from": "app/main.py::main", "to": "app/utils.py::validate_input", "type": "call"},
    {"from": "app/main.py::main", "to": "app/utils.py::process_data", "type": "call"},
    {"from": "app/utils.py::process_data", "to": "app/utils.py::format_output", "type": "call"}
  ],
  "entry_points": ["app/main.py::<module>", "app/utils.py::process_data", "app/utils.py::validate_input"]
}
"""

CALL_GRAPH_003 = """{
  "metadata": {
    "generated_at": "2025-01-30T12:00:00Z",
    "language": "javascript",
    "task_id": "dead-code-003"
  },
  "nodes": [
    {"id": "src/api/routes.js::<module>", "file": "src/api/routes.js", "name": "<module>", "type": "module", "line": 1, "exported": true},
    {"id": "src/api/handlers.js::handleUser", "file": "src/api/handlers.js", "name": "handleUser", "type": "function", "line": 3, "exported": true},
    {"id": "src/api/handlers.js::handleAuth", "file": "src/api/handlers.js", "name": "handleAuth", "type": "function", "line": 9, "exported": true},
    {"id": "src/api/handlers.js::handleLegacyEndpoint", "file": "src/api/handlers.js", "name": "handleLegacyEndpoint", "type": "function", "line": 12, "exported": false},
    {"id": "src/api/handlers.js::handleDeprecatedAuth", "file": "src/api/handlers.js", "name": "handleDeprecatedAuth", "type": "function", "line": 16, "exported": false},
    {"id": "src/utils/helpers.js::validateToken", "file": "src/utils/helpers.js", "name": "validateToken", "type": "function", "line": 1, "exported": true},
    {"id": "src/utils/helpers.js::formatResponse", "file": "src/utils/helpers.js", "name": "formatResponse", "type": "function", "line": 5, "exported": true},
    {"id": "src/utils/helpers.js::logRequest", "file": "src/utils/helpers.js", "name": "logRequest", "type": "function", "line": 9, "exported": false},
    {"id": "src/utils/helpers.js::formatLegacyResponse", "file": "src/utils/helpers.js", "name": "formatLegacyResponse", "type": "function", "line": 13, "exported": false},
    {"id": "src/utils/helpers.js::generateId", "file": "src/utils/helpers.js", "name": "generateId", "type": "function", "line": 17, "exported": false}
  ],
  "edges": [
    {"from": "src/api/routes.js::<module>", "to": "src/api/handlers.js::handleUser", "type": "reference"},
    {"from": "src/api/routes.js::<module>", "to": "src/api/handlers.js::handleAuth", "type": "reference"},
    {"from": "src/api/handlers.js::handleUser", "to": "src/utils/helpers.js::validateToken", "type": "call"},
    {"from": "src/api/handlers.js::handleUser", "to": "src/utils/helpers.js::formatResponse", "type": "call"}
  ],
  "entry_points": ["src/api/routes.js::<module>", "src/api/handlers.js::handleUser", "src/api/handlers.js::handleAuth", "src/utils/helpers.js::validateToken", "src/utils/helpers.js::formatResponse"]
}
"""


class DeadCodeBenchmark:
    """Dead code detection benchmark."""

    name = "dead-code"

    def __init__(self, dataset: str | Path = ""):
        self.dataset = dataset
        self._tasks: list[dict[str, Any]] | None = None

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

        dataset_path = Path(self.dataset) if self.dataset else None

        if dataset_path and dataset_path.exists():
            with open(dataset_path) as f:
                self._tasks = json.load(f)
        else:
            self._tasks = self._generate_synthetic_tasks()

        return self._tasks

    def _generate_synthetic_tasks(self) -> list[dict[str, Any]]:
        """Generate synthetic dead code detection tasks."""
        return [
            {
                "instance_id": "dead-code-001",
                "language": "typescript",
                "difficulty": "easy",
                "repo_content": {
                    "REPORT.json": REPORT_PLACEHOLDER,
                    ".supermodel/graph.json": CALL_GRAPH_001,
                    "src/utils.ts": """export function usedFunction() {
  console.log("I am used");
  helperFunction();
}

function helperFunction() {
  console.log("I am a helper");
}

function neverCalled() {
  console.log("Nobody calls me");
}

function alsoNeverCalled(x: number) {
  return x * 2;
}

const unusedArrow = () => {
  console.log("I am unused");
};

export function anotherUsedFunction() {
  usedFunction();
}
""",
                    "src/index.ts": """import { usedFunction, anotherUsedFunction } from "./utils";

usedFunction();
anotherUsedFunction();
""",
                },
                "dead_code": [
                    {"file": "src/utils.ts", "name": "neverCalled", "line": 10, "type": "function"},
                    {
                        "file": "src/utils.ts",
                        "name": "alsoNeverCalled",
                        "line": 14,
                        "type": "function",
                    },
                    {"file": "src/utils.ts", "name": "unusedArrow", "line": 18, "type": "variable"},
                ],
                "alive_code": [
                    {"file": "src/utils.ts", "name": "usedFunction", "line": 1, "type": "function"},
                    {
                        "file": "src/utils.ts",
                        "name": "helperFunction",
                        "line": 6,
                        "type": "function",
                    },
                    {
                        "file": "src/utils.ts",
                        "name": "anotherUsedFunction",
                        "line": 22,
                        "type": "function",
                    },
                ],
            },
            {
                "instance_id": "dead-code-002",
                "language": "python",
                "difficulty": "medium",
                "repo_content": {
                    "REPORT.json": REPORT_PLACEHOLDER,
                    ".supermodel/graph.json": CALL_GRAPH_002,
                    "app/main.py": """from app.utils import process_data, validate_input

def main():
    data = validate_input({"key": "value"})
    result = process_data(data)
    print(result)

if __name__ == "__main__":
    main()
""",
                    "app/utils.py": '''def process_data(data: dict) -> str:
    """Process the input data."""
    return format_output(data)

def validate_input(data: dict) -> dict:
    """Validate input data."""
    if not isinstance(data, dict):
        raise ValueError("Expected dict")
    return data

def format_output(data: dict) -> str:
    """Format data for output."""
    return str(data)

def deprecated_processor(data):
    """Old processor - no longer used."""
    return data

def legacy_validator(data):
    """Legacy validation - replaced by validate_input."""
    return bool(data)

class UnusedClass:
    """This class is never instantiated."""
    def __init__(self):
        self.value = 0

    def compute(self):
        return self.value * 2
''',
                    "app/__init__.py": "",
                },
                "dead_code": [
                    {
                        "file": "app/utils.py",
                        "name": "deprecated_processor",
                        "line": 15,
                        "type": "function",
                    },
                    {
                        "file": "app/utils.py",
                        "name": "legacy_validator",
                        "line": 19,
                        "type": "function",
                    },
                    {"file": "app/utils.py", "name": "UnusedClass", "line": 23, "type": "class"},
                ],
                "alive_code": [
                    {"file": "app/utils.py", "name": "process_data", "line": 1, "type": "function"},
                    {
                        "file": "app/utils.py",
                        "name": "validate_input",
                        "line": 5,
                        "type": "function",
                    },
                    {
                        "file": "app/utils.py",
                        "name": "format_output",
                        "line": 11,
                        "type": "function",
                    },
                ],
            },
            {
                "instance_id": "dead-code-003",
                "language": "javascript",
                "difficulty": "hard",
                "repo_content": {
                    "REPORT.json": REPORT_PLACEHOLDER,
                    ".supermodel/graph.json": CALL_GRAPH_003,
                    "src/api/routes.js": """const { handleUser, handleAuth } = require('./handlers');

module.exports = {
  routes: [
    { path: '/user', handler: handleUser },
    { path: '/auth', handler: handleAuth },
  ]
};
""",
                    "src/api/handlers.js": """const { validateToken, formatResponse } = require('../utils/helpers');

function handleUser(req, res) {
  const valid = validateToken(req.headers.token);
  if (!valid) return res.status(401).send('Unauthorized');
  return res.json(formatResponse({ user: 'data' }));
}

function handleAuth(req, res) {
  return res.json({ authenticated: true });
}

function handleLegacyEndpoint(req, res) {
  return res.json({ legacy: true });
}

function handleDeprecatedAuth(req, res) {
  console.log('Deprecated');
  return res.status(410).send('Gone');
}

module.exports = { handleUser, handleAuth };
""",
                    "src/utils/helpers.js": """function validateToken(token) {
  return token && token.length > 0;
}

function formatResponse(data) {
  return { success: true, data };
}

function logRequest(req) {
  console.log(req.url);
}

function formatLegacyResponse(data) {
  return { result: data };
}

function generateId() {
  return Math.random().toString(36);
}

module.exports = { validateToken, formatResponse };
""",
                },
                "dead_code": [
                    {
                        "file": "src/api/handlers.js",
                        "name": "handleLegacyEndpoint",
                        "line": 12,
                        "type": "function",
                    },
                    {
                        "file": "src/api/handlers.js",
                        "name": "handleDeprecatedAuth",
                        "line": 16,
                        "type": "function",
                    },
                    {
                        "file": "src/utils/helpers.js",
                        "name": "logRequest",
                        "line": 9,
                        "type": "function",
                    },
                    {
                        "file": "src/utils/helpers.js",
                        "name": "formatLegacyResponse",
                        "line": 13,
                        "type": "function",
                    },
                    {
                        "file": "src/utils/helpers.js",
                        "name": "generateId",
                        "line": 17,
                        "type": "function",
                    },
                ],
                "alive_code": [
                    {
                        "file": "src/api/handlers.js",
                        "name": "handleUser",
                        "line": 3,
                        "type": "function",
                    },
                    {
                        "file": "src/api/handlers.js",
                        "name": "handleAuth",
                        "line": 9,
                        "type": "function",
                    },
                    {
                        "file": "src/utils/helpers.js",
                        "name": "validateToken",
                        "line": 1,
                        "type": "function",
                    },
                    {
                        "file": "src/utils/helpers.js",
                        "name": "formatResponse",
                        "line": 5,
                        "type": "function",
                    },
                ],
            },
        ]

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
        files = [f for f in task.get("repo_content", {}).keys() if f != "REPORT.json"]

        return f"""Find all dead code in this {language} codebase.

Task: {instance_id}
Files to analyze: {", ".join(files)}

INSTRUCTIONS:
1. Read all source files in the workspace
2. Identify entry points (exported functions, main modules)
3. Trace which functions are actually called
4. Find functions/classes that are NEVER called

CRITICAL: Update the existing REPORT.json file with your findings.
Format: a JSON object with "dead_code" array containing objects with file, name, line, and type fields.
Set "analysis_complete" to true when done.

Rules:
- Exported functions are NOT dead (they are entry points)
- Functions called by live code are NOT dead
- Only mark truly unreachable code as dead
"""

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        import subprocess

        instance_id = task.get("instance_id", "unknown")
        repo_content = task.get("repo_content", {})

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
