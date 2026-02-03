"""Evaluation logic for applying patches and running tests."""

import ast
import json
from dataclasses import dataclass
from typing import Any

from .docker_env import TaskEnvironment


@dataclass
class TestResults:
    """Results from running tests."""

    passed: int
    total: int
    details: list[dict[str, Any]]


@dataclass
class EvaluationResult:
    """Complete evaluation result for a task."""

    resolved: bool
    patch_applied: bool
    fail_to_pass: TestResults | None = None
    pass_to_pass: TestResults | None = None
    error: str | None = None


def parse_test_list(test_str: str) -> list[str]:
    """Parse test list from SWE-bench format (JSON string or Python literal).

    Always returns a list of strings, converting non-string elements as needed.
    Handles malformed data gracefully by filtering out invalid entries.
    """
    if not test_str:
        return []

    test_str = test_str.strip()

    # Try JSON parsing first
    try:
        parsed = json.loads(test_str)
        if isinstance(parsed, list):
            # Convert all elements to strings and filter out invalid entries
            return [str(item) for item in parsed if item is not None and str(item).strip()]
        return []
    except json.JSONDecodeError:
        pass

    # Try Python literal_eval
    try:
        result = ast.literal_eval(test_str)
        if isinstance(result, list):
            # Convert all elements to strings and filter out invalid entries
            return [str(item) for item in result if item is not None and str(item).strip()]
        return []
    except (ValueError, SyntaxError):
        pass

    # Fallback: manual parsing for unquoted strings
    if test_str.startswith("[") and test_str.endswith("]"):
        inner = test_str[1:-1]
        tests = []
        for part in inner.split(","):
            part = part.strip().strip("'\"")
            if part:
                tests.append(part)
        return tests

    return []


async def apply_patch(
    env: TaskEnvironment,
    patch: str,
    workdir: str | None = None,
) -> tuple[bool, str]:
    """Apply a patch to the repository.

    Args:
        env: Docker environment.
        patch: Unified diff patch content.
        workdir: Working directory for git operations. Defaults to env.workdir.

    Returns:
        Tuple of (success, error_message).
    """
    if not patch.strip():
        return False, "Empty patch"

    workdir = workdir or env.workdir

    # Reset repository to clean state before applying patch
    # The agent modified files directly, so we need to restore HEAD state
    await env.exec_command("git reset --hard HEAD", timeout=30, workdir=workdir)
    await env.exec_command("git clean -fd", timeout=30, workdir=workdir)

    await env.write_file("fix.patch", patch, workdir=workdir)

    exit_code, stdout, stderr = await env.exec_command(
        "git apply --check fix.patch",
        timeout=30,
        workdir=workdir,
    )

    if exit_code != 0:
        exit_code2, stdout2, stderr2 = await env.exec_command(
            "git apply --check -3 fix.patch",
            timeout=30,
            workdir=workdir,
        )
        if exit_code2 != 0:
            return False, f"Patch does not apply: {stderr or stderr2}"
        exit_code, stdout, stderr = await env.exec_command(
            "git apply -3 fix.patch",
            timeout=30,
            workdir=workdir,
        )
    else:
        exit_code, stdout, stderr = await env.exec_command(
            "git apply fix.patch",
            timeout=30,
            workdir=workdir,
        )

    if exit_code != 0:
        return False, f"Failed to apply patch: {stderr}"

    return True, ""


async def run_tests(
    env: TaskEnvironment,
    tests: list[str],
    timeout: int = 120,
    uses_prebuilt: bool = False,
    workdir: str | None = None,
    repo: str | None = None,
) -> TestResults:
    """Run a list of tests and return results.

    Args:
        env: Docker environment.
        tests: List of test identifiers.
        timeout: Timeout per test in seconds.
        uses_prebuilt: Whether a pre-built SWE-bench image is being used.
        workdir: Working directory to run tests from. Defaults to env.workdir.
        repo: Repository identifier for looking up the correct test runner.

    Returns:
        TestResults with pass/fail counts.
    """
    if not tests:
        return TestResults(passed=0, total=0, details=[])

    results = []
    passed = 0

    for test in tests:
        test_cmd = _build_test_command(test, uses_prebuilt, repo=repo)

        try:
            exit_code, stdout, stderr = await env.exec_command(
                test_cmd,
                timeout=timeout,
                workdir=workdir,
            )

            test_passed = exit_code == 0
            if test_passed:
                passed += 1

            results.append(
                {
                    "test": test,
                    "passed": test_passed,
                    "exit_code": exit_code,
                    "output": stdout[:1000] if stdout else "",
                    "error": stderr[:1000] if stderr else "",
                }
            )

        except TimeoutError:
            results.append(
                {
                    "test": test,
                    "passed": False,
                    "exit_code": -1,
                    "output": "",
                    "error": "Test timed out",
                }
            )

    return TestResults(
        passed=passed,
        total=len(tests),
        details=results,
    )


def _build_test_command(test: str, uses_prebuilt: bool = False, repo: str | None = None) -> str:
    """Build a test command for the given test identifier.

    Args:
        test: Test identifier in various formats:
            - pytest: "tests/test_file.py::test_func" or "tests/test_file.py"
            - Django: "test_method (module.TestClass)" or "module.tests.TestClass.test_method"
        uses_prebuilt: If True, activate the testbed conda environment first.
        repo: Repository identifier (e.g., "sympy/sympy") for looking up
            the correct test runner from upstream SWE-bench specs.

    Returns:
        Shell command string to run the test.
    """
    import re

    from .swebench_test_specs import get_repo_test_command

    # Pre-built SWE-bench images use a conda environment called 'testbed'
    if uses_prebuilt:
        activate = "source /opt/miniconda3/etc/profile.d/conda.sh && conda activate testbed && "
    else:
        activate = ""

    # Check upstream SWE-bench test command mapping for non-pytest runners
    if repo:
        upstream_cmd = get_repo_test_command(repo)
        if upstream_cmd and "runtests.py" not in upstream_cmd and "pytest" not in upstream_cmd:
            # Non-pytest, non-Django project (e.g., sympy uses bin/test)
            return f"{activate}{upstream_cmd} {test}"

    # Detect Django test format: "test_method (module.TestClass)"
    if "(" in test and ")" in test and "." in test:
        # Extract module path from parentheses
        match = re.search(r"\(([^)]+)\)", test)
        if match:
            module_path = match.group(1)  # e.g., "test_utils.tests.OverrideSettingsTests"
            # Extract first 2 parts for Django test module
            parts = module_path.split(".")
            if len(parts) >= 2:
                test_module = ".".join(parts[:2])  # e.g., "test_utils.tests"
                return f"{activate}cd /testbed/tests && ./runtests.py {test_module}"

    # Detect Django test format: dot-separated, no ::, not a file path
    is_django_test = (
        "." in test and "::" not in test and not test.endswith(".py") and not test.startswith("/")
    )

    if is_django_test:
        # Django format: test_utils.tests.TestClass.test_method
        # Run with Django test runner
        test_module = ".".join(test.split(".")[:2])  # Extract test_utils.tests
        return f"{activate}cd /testbed/tests && ./runtests.py {test_module}"
    elif "::" in test:
        return f"{activate}python -m pytest {test} -xvs 2>&1"
    elif test.endswith(".py"):
        return f"{activate}python -m pytest {test} -xvs 2>&1"
    else:
        return f"{activate}python -m pytest -k '{test}' -xvs 2>&1"


async def _apply_test_patch(
    env: TaskEnvironment,
    test_patch: str,
    workdir: str | None = None,
) -> tuple[bool, str]:
    """Apply the test patch from SWE-bench to add required test cases.

    Args:
        env: Docker environment.
        test_patch: Test patch from SWE-bench dataset.
        workdir: Working directory for git operations.

    Returns:
        Tuple of (success, error_message).
    """
    if not test_patch or not test_patch.strip():
        return True, ""

    workdir = workdir or env.workdir

    await env.write_file("test.patch", test_patch, workdir=workdir)

    exit_code, stdout, stderr = await env.exec_command(
        "git apply --check test.patch",
        timeout=30,
        workdir=workdir,
    )

    if exit_code != 0:
        exit_code, stdout, stderr = await env.exec_command(
            "git apply --check -3 test.patch",
            timeout=30,
            workdir=workdir,
        )
        if exit_code != 0:
            return True, ""
        exit_code, stdout, stderr = await env.exec_command(
            "git apply -3 test.patch",
            timeout=30,
            workdir=workdir,
        )
    else:
        exit_code, stdout, stderr = await env.exec_command(
            "git apply test.patch",
            timeout=30,
            workdir=workdir,
        )

    if exit_code != 0:
        return True, ""

    return True, ""


async def evaluate_patch(
    env: TaskEnvironment,
    task: dict[str, Any],
    patch: str,
    test_timeout: int = 120,
) -> EvaluationResult:
    """Evaluate a patch against a SWE-bench task.

    Args:
        env: Docker environment.
        task: SWE-bench task dictionary.
        patch: Unified diff patch to evaluate.
        test_timeout: Timeout for each test.

    Returns:
        EvaluationResult with full evaluation details.
    """
    # For pre-built images, apply patch and run tests in /testbed
    # because that's where the editable install points to
    eval_workdir = "/testbed" if env.uses_prebuilt else None

    applied, error = await apply_patch(env, patch, workdir=eval_workdir)
    if not applied:
        return EvaluationResult(
            resolved=False,
            patch_applied=False,
            error=error,
        )

    # Apply test patch from SWE-bench to add required test cases
    # (pre-built images may not have the tests added by the fix PR)
    test_patch = task.get("test_patch", "")
    if test_patch:
        await _apply_test_patch(env, test_patch, workdir=eval_workdir)

    fail_to_pass_tests = parse_test_list(task.get("FAIL_TO_PASS", "[]"))
    pass_to_pass_tests = parse_test_list(task.get("PASS_TO_PASS", "[]"))

    # Skip dependency installation for pre-built images (already done)
    if not env.uses_prebuilt:
        await _install_dependencies(env)

    repo = task.get("repo")

    fail_to_pass_results = await run_tests(
        env,
        fail_to_pass_tests,
        timeout=test_timeout,
        uses_prebuilt=env.uses_prebuilt,
        workdir=eval_workdir,
        repo=repo,
    )

    pass_to_pass_results = await run_tests(
        env,
        pass_to_pass_tests[:10],
        timeout=test_timeout,
        uses_prebuilt=env.uses_prebuilt,
        workdir=eval_workdir,
        repo=repo,
    )

    resolved = (
        fail_to_pass_results.passed == fail_to_pass_results.total
        and fail_to_pass_results.total > 0
        and pass_to_pass_results.passed == pass_to_pass_results.total
    )

    return EvaluationResult(
        resolved=resolved,
        patch_applied=True,
        fail_to_pass=fail_to_pass_results,
        pass_to_pass=pass_to_pass_results,
    )


async def _install_dependencies(env: TaskEnvironment) -> None:
    """Attempt to install project dependencies."""
    exit_code, _, _ = await env.exec_command("ls setup.py", timeout=5)
    if exit_code == 0:
        await env.exec_command(
            "pip install -e . -q 2>/dev/null || true",
            timeout=120,
        )
        return

    exit_code, _, _ = await env.exec_command("ls pyproject.toml", timeout=5)
    if exit_code == 0:
        await env.exec_command(
            "pip install -e . -q 2>/dev/null || true",
            timeout=120,
        )
        return

    exit_code, _, _ = await env.exec_command("ls requirements.txt", timeout=5)
    if exit_code == 0:
        await env.exec_command(
            "pip install -r requirements.txt -q 2>/dev/null || true",
            timeout=120,
        )
