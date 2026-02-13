"""Sampling strategies for benchmark task selection.

Provides random and stratified sampling with seed control for reproducible
benchmark evaluations. Supports sequential (default), random, and stratified
sampling strategies.
"""

import random
from collections import defaultdict
from enum import Enum
from typing import Any


class SamplingStrategy(Enum):
    """Sampling strategy for selecting benchmark tasks.

    Attributes:
        SEQUENTIAL: Take the first N tasks (default behavior, backward compatible).
        RANDOM: Randomly sample N tasks with optional seed for reproducibility.
        STRATIFIED: Group tasks by a field, then sample proportionally from each group.
    """

    SEQUENTIAL = "sequential"
    RANDOM = "random"
    STRATIFIED = "stratified"


def sample_tasks(
    tasks: list[dict[str, Any]],
    sample_size: int | None = None,
    strategy: SamplingStrategy = SamplingStrategy.SEQUENTIAL,
    seed: int | None = None,
    stratify_field: str | None = None,
) -> list[dict[str, Any]]:
    """Sample tasks from a list using the specified strategy.

    Args:
        tasks: Full list of task dictionaries to sample from.
        sample_size: Number of tasks to select. None returns all tasks.
        strategy: Sampling strategy to use.
        seed: Random seed for reproducibility (used by RANDOM and STRATIFIED).
        stratify_field: Field name to group by for STRATIFIED sampling.
            Required when strategy is STRATIFIED.

    Returns:
        List of sampled task dictionaries.

    Raises:
        ValueError: If strategy is STRATIFIED but stratify_field is not provided.
        ValueError: If strategy is STRATIFIED but stratify_field is not found in any task.
    """
    if not tasks:
        return []

    if sample_size is None or sample_size >= len(tasks):
        return list(tasks)

    if sample_size <= 0:
        return []

    if strategy == SamplingStrategy.SEQUENTIAL:
        return _sample_sequential(tasks, sample_size)
    elif strategy == SamplingStrategy.RANDOM:
        return _sample_random(tasks, sample_size, seed)
    elif strategy == SamplingStrategy.STRATIFIED:
        return _sample_stratified(tasks, sample_size, seed, stratify_field)
    else:
        raise ValueError(f"Unknown sampling strategy: {strategy}")


def _sample_sequential(
    tasks: list[dict[str, Any]],
    sample_size: int,
) -> list[dict[str, Any]]:
    """Take the first N tasks sequentially.

    This matches the existing behavior where tasks[:sample_size] is used.

    Args:
        tasks: Full list of tasks.
        sample_size: Number of tasks to select.

    Returns:
        First sample_size tasks from the list.
    """
    return tasks[:sample_size]


def _sample_random(
    tasks: list[dict[str, Any]],
    sample_size: int,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Randomly sample N tasks with optional seed for reproducibility.

    Args:
        tasks: Full list of tasks.
        sample_size: Number of tasks to select.
        seed: Random seed for reproducibility.

    Returns:
        Randomly selected tasks.
    """
    rng = random.Random(seed)  # noqa: S311 -- not used for cryptographic purposes; deterministic sampling
    return rng.sample(tasks, sample_size)


def _sample_stratified(
    tasks: list[dict[str, Any]],
    sample_size: int,
    seed: int | None = None,
    stratify_field: str | None = None,
) -> list[dict[str, Any]]:
    """Sample proportionally from groups defined by stratify_field.

    Groups tasks by the value of stratify_field, then samples from each group
    proportionally to its size in the original dataset. Uses round-robin allocation
    for any remainder to ensure exact sample_size is met.

    Args:
        tasks: Full list of tasks.
        sample_size: Total number of tasks to select across all groups.
        seed: Random seed for reproducibility.
        stratify_field: Field name to group tasks by.

    Returns:
        Stratified sample of tasks.

    Raises:
        ValueError: If stratify_field is None or not found in any task.
    """
    if not stratify_field:
        raise ValueError("stratify_field is required when using STRATIFIED sampling strategy")

    # Group tasks by the stratify_field value
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        key = str(task.get(stratify_field, "_unknown_"))
        groups[key] = groups.get(key, [])
        groups[key].append(task)

    # Check that at least one task had the stratify_field
    if len(groups) == 1 and "_unknown_" in groups:
        raise ValueError(
            f"stratify_field '{stratify_field}' not found in any task. "
            f"Available fields: {list(tasks[0].keys()) if tasks else []}"
        )

    total_tasks = len(tasks)
    rng = random.Random(seed)  # noqa: S311 -- not used for cryptographic purposes; deterministic sampling

    # Sort group keys for deterministic ordering
    sorted_keys = sorted(groups.keys())

    # Calculate proportional allocation for each group
    allocations: dict[str, int] = {}
    allocated = 0
    for key in sorted_keys:
        group_size = len(groups[key])
        # Proportional allocation (floor)
        proportion = group_size / total_tasks
        count = int(sample_size * proportion)
        allocations[key] = count
        allocated += count

    # Distribute remainder using round-robin over groups sorted by fractional part
    remainder = sample_size - allocated
    if remainder > 0:
        # Sort groups by their fractional allocation (descending) for fair distribution
        fractional_parts = []
        for key in sorted_keys:
            group_size = len(groups[key])
            proportion = group_size / total_tasks
            exact = sample_size * proportion
            fractional = exact - int(exact)
            fractional_parts.append((fractional, key))

        fractional_parts.sort(key=lambda x: x[0], reverse=True)

        for i in range(remainder):
            _, key = fractional_parts[i % len(fractional_parts)]
            allocations[key] += 1

    # Sample from each group
    result: list[dict[str, Any]] = []
    for key in sorted_keys:
        group = groups[key]
        count = min(allocations[key], len(group))
        if count > 0:
            sampled = rng.sample(group, count)
            result.extend(sampled)

    return result
