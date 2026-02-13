"""Git utilities for cloning repos and creating zip archives."""

import asyncio
import logging
import subprocess

logger = logging.getLogger("mcpbr.supermodel")


async def clone_repo_at_commit(repo: str, commit: str, dest: str) -> None:
    """Clone a repo and checkout a specific commit.

    Args:
        repo: GitHub repo in 'owner/name' format, or a full clone URL.
        commit: Git commit SHA to checkout.
        dest: Destination directory path.
    """
    logger.info(f"Cloning {repo} at {commit[:8]} -> {dest}")

    # Support full URLs (https://, git://, ssh://) or owner/name shorthand
    if repo.startswith(("https://", "http://", "git://", "ssh://", "git@")):
        clone_url = repo
    else:
        clone_url = f"https://github.com/{repo}.git"

    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--quiet",
        "--depth",
        "1",
        clone_url,
        dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"Clone failed: {stderr.decode()}")

    proc = await asyncio.create_subprocess_exec(
        "git",
        "fetch",
        "--quiet",
        "--depth",
        "1",
        "origin",
        commit,
        cwd=dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"Fetch failed: {stderr.decode()}")

    proc = await asyncio.create_subprocess_exec(
        "git",
        "checkout",
        "--quiet",
        commit,
        cwd=dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"Checkout failed: {stderr.decode()}")


def get_pre_merge_commit(repo: str, merge_commit: str) -> str:
    """Get the first parent of a merge commit (pre-merge state).

    Args:
        repo: GitHub repo in 'owner/name' format.
        merge_commit: Merge commit SHA.

    Returns:
        SHA of the first parent commit.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/commits/{merge_commit}", "--jq", ".parents[0].sha"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get parent of {merge_commit}: {result.stderr}")
    return result.stdout.strip()


async def zip_repo(
    repo_dir: str,
    output_zip: str,
    scope_prefix: str | None = None,
    exclude_patterns: list[str] | None = None,
) -> str:
    """Create a zip of the repo for Supermodel API.

    Uses `zip` command with exclude patterns for fine-grained control.

    Args:
        repo_dir: Path to the repository directory.
        output_zip: Path for the output zip file.
        scope_prefix: Optional subdirectory to scope the archive to.
        exclude_patterns: Optional glob patterns to exclude (e.g. ["loc/*", "lib/*"]).

    Returns:
        Path to the created zip file.
    """
    zip_target = scope_prefix if scope_prefix else "."
    base_excludes = [
        "node_modules/*",
        ".git/*",
        "dist/*",
        "build/*",
        "*.pyc",
        "__pycache__/*",
    ]
    # Prepend scope_prefix to exclude patterns so they match archive paths
    prefixed_excludes = []
    for pattern in base_excludes + (exclude_patterns or []):
        if scope_prefix and not pattern.startswith(scope_prefix):
            prefixed_excludes.append(f"{scope_prefix}/{pattern}")
        else:
            prefixed_excludes.append(pattern)

    cmd = ["zip", "-r", "-q", output_zip, zip_target]
    for pattern in prefixed_excludes:
        cmd.extend(["-x", pattern])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=repo_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"zip failed: {stderr.decode()}")
    return output_zip
