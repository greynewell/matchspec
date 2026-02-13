"""Docker image pre-warming for mcpbr benchmark evaluations.

Pre-pulls Docker images needed for a benchmark run before evaluation begins,
so that image pull time does not inflate task-level timing measurements.
Supports parallel pulling, progress reporting, and local cache detection.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import docker.errors
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

import docker

from .docker_env import SWEBENCH_IMAGE_REGISTRY, get_swebench_image_name

logger = logging.getLogger(__name__)

# Default base images used by non-SWE-bench benchmarks
DEFAULT_BASE_IMAGES: dict[str, list[str]] = {
    "humaneval": ["python:3.11-slim"],
    "mbpp": ["python:3.11-slim"],
    "apps": ["python:3.11-slim"],
    "codecontests": ["python:3.11-slim"],
    "bigcodebench": ["python:3.11-slim"],
    "leetcode": ["python:3.11-slim"],
    "codereval": ["python:3.11-slim"],
    "gsm8k": ["python:3.11-slim"],
    "math": ["python:3.11-slim"],
    "truthfulqa": ["python:3.11-slim"],
    "bigbench-hard": ["python:3.11-slim"],
    "hellaswag": ["python:3.11-slim"],
    "arc": ["python:3.11-slim"],
    "repoqa": ["python:3.11-slim"],
    "toolbench": ["python:3.11-slim"],
    "aider-polyglot": ["python:3.11-slim"],
    "terminalbench": ["python:3.11-slim"],
    "gaia": ["python:3.11-slim"],
    "agentbench": ["python:3.11-slim"],
    "webarena": ["python:3.11-slim"],
    "mlagentbench": ["python:3.11-slim"],
    "intercode": ["python:3.11-slim"],
    "mmmu": ["python:3.11-slim"],
    "longbench": ["python:3.11-slim"],
    "adversarial": ["python:3.11-slim"],
    "mcptoolbench": ["python:3.11-slim"],
    "custom": ["python:3.11-slim"],
    "cybergym": ["python:3.11-slim"],
}


@dataclass
class PrewarmResult:
    """Result of a Docker image pre-warming operation.

    Attributes:
        total_images: Total number of images that were requested.
        already_cached: Number of images already available locally.
        newly_pulled: Number of images successfully pulled from registry.
        failed: List of image names that failed to pull.
        pull_time_seconds: Wall-clock time for the entire pre-warm operation.
    """

    total_images: int = 0
    already_cached: int = 0
    newly_pulled: int = 0
    failed: list[str] = field(default_factory=list)
    pull_time_seconds: float = 0.0


def get_required_images(benchmark_name: str, tasks: list[dict[str, Any]]) -> list[str]:
    """Determine which Docker images are needed for a benchmark run.

    For SWE-bench variants, each task maps to a unique per-instance image from
    the Epoch Research registry. For other benchmarks, a common base image
    (typically ``python:3.11-slim``) is used.

    Args:
        benchmark_name: Name of the benchmark (e.g., ``"swe-bench-lite"``).
        tasks: List of task dictionaries loaded from the benchmark.

    Returns:
        Deduplicated list of Docker image names required for the run.
    """
    images: list[str] = []

    is_swebench = benchmark_name.startswith("swe-bench")

    if is_swebench:
        seen: set[str] = set()
        for task in tasks:
            instance_id = task.get("instance_id", "")
            if instance_id and instance_id not in seen:
                seen.add(instance_id)
                images.append(get_swebench_image_name(instance_id))
    else:
        # Use default base images for the benchmark, or fall back to python:3.11-slim
        base_images = DEFAULT_BASE_IMAGES.get(benchmark_name, ["python:3.11-slim"])
        images = list(base_images)

    return images


def check_cached_images(images: list[str]) -> dict[str, bool]:
    """Check which Docker images are already available in the local cache.

    Uses ``docker.from_env()`` to inspect the local image store. Images that
    are present locally are marked ``True``; missing or inaccessible images
    are marked ``False``.

    Args:
        images: List of Docker image names to check.

    Returns:
        Dictionary mapping each image name to a boolean indicating whether
        it is cached locally.
    """
    result: dict[str, bool] = {}
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        logger.warning("Could not connect to Docker daemon for cache check")
        return dict.fromkeys(images, False)

    for image in images:
        try:
            client.images.get(image)
            result[image] = True
        except docker.errors.ImageNotFound:
            result[image] = False
        except docker.errors.APIError:
            result[image] = False

    return result


async def _pull_single_image(
    client: docker.DockerClient,
    image: str,
    semaphore: asyncio.Semaphore,
    on_progress: Callable[[str, str], None] | None = None,
) -> tuple[str, bool]:
    """Pull a single Docker image, respecting the concurrency semaphore.

    Args:
        client: Docker client instance.
        image: Full image name to pull.
        semaphore: Asyncio semaphore to limit parallel pulls.
        on_progress: Optional callback ``(image, status)`` for progress updates.

    Returns:
        Tuple of ``(image_name, success)``.
    """

    async with semaphore:
        if on_progress:
            on_progress(image, "pulling")

        def _do_pull() -> bool:
            try:
                # Determine platform for SWE-bench images
                platform = "linux/amd64" if SWEBENCH_IMAGE_REGISTRY in image else None
                client.images.pull(image, platform=platform)
                return True
            except docker.errors.ImageNotFound:
                logger.warning("Image not found in registry: %s", image)
                return False
            except docker.errors.APIError as exc:
                logger.warning("Failed to pull image %s: %s", image, exc)
                return False

        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, _do_pull)

        if on_progress:
            on_progress(image, "done" if success else "failed")

        return image, success


async def prewarm_images(
    benchmark_name: str,
    tasks: list[dict[str, Any]],
    max_parallel: int = 3,
    on_progress: Callable[[str, str], None] | None = None,
) -> PrewarmResult:
    """Pre-pull all Docker images needed for a benchmark run.

    Checks the local cache first, then pulls missing images in parallel
    (limited by ``max_parallel``). Returns a summary of the operation.

    Args:
        benchmark_name: Name of the benchmark (e.g., ``"swe-bench-verified"``).
        tasks: List of task dictionaries from the benchmark loader.
        max_parallel: Maximum number of concurrent image pulls. Defaults to 3.
        on_progress: Optional callback ``(image_name, status_string)`` invoked
            when an image starts pulling or completes.

    Returns:
        PrewarmResult summarising cached, pulled, and failed images.
    """
    start_time = time.monotonic()

    images = get_required_images(benchmark_name, tasks)
    total = len(images)

    if total == 0:
        return PrewarmResult(pull_time_seconds=time.monotonic() - start_time)

    # Check local cache
    cache_status = check_cached_images(images)
    already_cached = sum(1 for cached in cache_status.values() if cached)
    to_pull = [img for img, cached in cache_status.items() if not cached]

    if not to_pull:
        return PrewarmResult(
            total_images=total,
            already_cached=already_cached,
            newly_pulled=0,
            failed=[],
            pull_time_seconds=time.monotonic() - start_time,
        )

    # Pull missing images in parallel
    try:
        client = docker.from_env()
    except docker.errors.DockerException as exc:
        logger.error("Cannot connect to Docker daemon: %s", exc)
        return PrewarmResult(
            total_images=total,
            already_cached=already_cached,
            newly_pulled=0,
            failed=to_pull,
            pull_time_seconds=time.monotonic() - start_time,
        )

    semaphore = asyncio.Semaphore(max_parallel)

    pull_tasks = [
        _pull_single_image(client, image, semaphore, on_progress=on_progress) for image in to_pull
    ]

    results = await asyncio.gather(*pull_tasks, return_exceptions=True)

    newly_pulled = 0
    failed: list[str] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Unexpected error during image pull: %s", result)
            failed.append(str(result))
        else:
            image_name, success = result
            if success:
                newly_pulled += 1
            else:
                failed.append(image_name)

    return PrewarmResult(
        total_images=total,
        already_cached=already_cached,
        newly_pulled=newly_pulled,
        failed=failed,
        pull_time_seconds=time.monotonic() - start_time,
    )


def format_prewarm_report(result: PrewarmResult) -> None:
    """Print a rich-formatted summary of the pre-warm operation.

    Displays a table with counts of cached, pulled, and failed images,
    plus total elapsed time.

    Args:
        result: PrewarmResult from a completed pre-warm operation.
    """
    console = Console()

    table = Table(title="Docker Image Pre-warm Summary", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", justify="right")

    table.add_row("Total images", str(result.total_images))
    table.add_row("Already cached", str(result.already_cached))
    table.add_row("Newly pulled", str(result.newly_pulled))
    table.add_row("Failed", str(len(result.failed)))
    table.add_row("Pull time", f"{result.pull_time_seconds:.1f}s")

    console.print()
    console.print(table)

    if result.failed:
        console.print()
        console.print("[red bold]Failed to pull the following images:[/red bold]")
        for image in result.failed:
            console.print(f"[red]  - {image}[/red]")

    if result.failed:
        console.print()
        console.print(
            "[yellow]Some images could not be pre-warmed. "
            "Evaluation will attempt to pull them at task time.[/yellow]"
        )
    elif result.newly_pulled > 0:
        console.print()
        console.print("[green bold]All images pre-warmed successfully.[/green bold]")
    elif result.total_images > 0:
        console.print()
        console.print("[green]All images already cached locally.[/green]")
    console.print()


async def prewarm_images_with_progress(
    benchmark_name: str,
    tasks: list[dict[str, Any]],
    max_parallel: int = 3,
) -> PrewarmResult:
    """Pre-pull images with a rich progress bar displayed in the terminal.

    This is a convenience wrapper around :func:`prewarm_images` that
    creates and manages a ``rich.progress.Progress`` bar automatically.

    Args:
        benchmark_name: Name of the benchmark.
        tasks: List of task dictionaries from the benchmark loader.
        max_parallel: Maximum number of concurrent image pulls. Defaults to 3.

    Returns:
        PrewarmResult summarising cached, pulled, and failed images.
    """
    images = get_required_images(benchmark_name, tasks)
    cache_status = check_cached_images(images)
    to_pull = [img for img, cached in cache_status.items() if not cached]

    if not to_pull:
        # Nothing to pull, just compute the result quickly
        return await prewarm_images(benchmark_name, tasks, max_parallel)

    console = Console()
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    task_id = progress.add_task("Pre-warming Docker images", total=len(to_pull))
    completed_count = 0

    def _on_progress(image: str, status: str) -> None:
        nonlocal completed_count
        if status in ("done", "failed"):
            completed_count += 1
            progress.update(task_id, completed=completed_count)
        else:
            # Shorten image name for display
            short_name = image.split("/")[-1][:40]
            progress.update(task_id, description=f"Pulling {short_name}")

    with progress:
        result = await prewarm_images(benchmark_name, tasks, max_parallel, on_progress=_on_progress)

    return result
