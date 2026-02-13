"""Few-shot learning support for benchmark evaluations.

Provides configurable few-shot example selection with multiple strategies
(random, similar, diverse), prompt formatting, and learning curve analysis
to study how performance changes with varying shot counts.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class FewShotConfig:
    """Configuration for few-shot example selection.

    Attributes:
        num_shots: Number of examples to include (0 for zero-shot).
        selection_strategy: Strategy for selecting examples. One of
            ``"random"``, ``"similar"``, or ``"diverse"``.
        seed: Random seed for reproducibility. ``None`` for non-deterministic.
    """

    num_shots: int = 0
    selection_strategy: str = "random"
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate configuration values after initialisation."""
        if self.num_shots < 0:
            raise ValueError(f"num_shots must be non-negative, got {self.num_shots}")

        valid_strategies = {"random", "similar", "diverse"}
        if self.selection_strategy not in valid_strategies:
            raise ValueError(
                f"selection_strategy must be one of {valid_strategies}, "
                f"got {self.selection_strategy!r}"
            )


def select_examples(
    pool: list[dict[str, Any]],
    query: dict[str, Any],
    config: FewShotConfig,
) -> list[dict[str, Any]]:
    """Select few-shot examples from a pool based on the given configuration.

    Args:
        pool: List of candidate example dictionaries to select from.
        query: The query/task dictionary that examples are being selected for.
            Used by the ``"similar"`` strategy to find related examples.
        config: Few-shot configuration controlling selection behaviour.

    Returns:
        List of selected example dictionaries. Length is
        ``min(config.num_shots, len(pool))``.
    """
    if config.num_shots == 0 or not pool:
        return []

    num = min(config.num_shots, len(pool))

    if config.selection_strategy == "random":
        return _select_random(pool, num, config.seed)
    elif config.selection_strategy == "similar":
        return _select_similar(pool, query, num, config.seed)
    elif config.selection_strategy == "diverse":
        return _select_diverse(pool, num, config.seed)
    else:
        raise ValueError(f"Unknown selection strategy: {config.selection_strategy!r}")


def format_few_shot_prompt(
    examples: list[dict[str, Any]],
    query: dict[str, Any],
    template: str,
) -> str:
    """Format a prompt string with few-shot examples and the target query.

    The *template* string should contain ``{examples}`` and ``{query}``
    placeholders. Each example is formatted as a numbered block using the
    example's string representation.

    Args:
        examples: List of few-shot example dictionaries.
        query: The target query dictionary.
        template: A format string containing ``{examples}`` and ``{query}``
            placeholders.

    Returns:
        The fully formatted prompt string.
    """
    if not examples:
        examples_text = "No examples provided."
    else:
        parts: list[str] = []
        for i, example in enumerate(examples, 1):
            parts.append(f"Example {i}:\n{_format_dict(example)}")
        examples_text = "\n\n".join(parts)

    query_text = _format_dict(query)

    return template.format(examples=examples_text, query=query_text)


def compute_learning_curve(
    results_by_shots: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Analyse how performance changes with the number of few-shot examples.

    For each shot count, computes accuracy (fraction of results where
    ``"resolved"`` is truthy), average cost, and average token usage.

    Args:
        results_by_shots: Mapping from shot count (int) to a list of result
            dictionaries. Each result dict may contain keys such as
            ``"resolved"`` (bool), ``"cost"`` (float), and
            ``"tokens"`` (dict with ``"input"`` and ``"output"``).

    Returns:
        Dictionary with keys:

        - ``"shot_counts"``: sorted list of shot counts.
        - ``"accuracy"``: list of accuracy values corresponding to each shot count.
        - ``"avg_cost"``: list of average cost values.
        - ``"avg_tokens"``: list of average total token counts.
        - ``"num_samples"``: list of sample counts for each shot count.
    """
    if not results_by_shots:
        return {
            "shot_counts": [],
            "accuracy": [],
            "avg_cost": [],
            "avg_tokens": [],
            "num_samples": [],
        }

    sorted_shots = sorted(results_by_shots.keys())
    accuracies: list[float] = []
    avg_costs: list[float] = []
    avg_tokens: list[float] = []
    num_samples: list[int] = []

    for shot_count in sorted_shots:
        results = results_by_shots[shot_count]
        n = len(results)
        num_samples.append(n)

        if n == 0:
            accuracies.append(0.0)
            avg_costs.append(0.0)
            avg_tokens.append(0.0)
            continue

        # Accuracy
        resolved = sum(1 for r in results if r.get("resolved"))
        accuracies.append(resolved / n)

        # Average cost
        total_cost = sum(r.get("cost", 0.0) for r in results)
        avg_costs.append(total_cost / n)

        # Average tokens
        total_tokens = 0
        for r in results:
            tokens = r.get("tokens", {})
            total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
        avg_tokens.append(total_tokens / n)

    return {
        "shot_counts": sorted_shots,
        "accuracy": accuracies,
        "avg_cost": avg_costs,
        "avg_tokens": avg_tokens,
        "num_samples": num_samples,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_dict(d: dict[str, Any]) -> str:
    """Format a dictionary as a human-readable key-value block.

    Args:
        d: Dictionary to format.

    Returns:
        Multi-line string with one ``key: value`` pair per line.
    """
    lines = [f"  {k}: {v}" for k, v in d.items()]
    return "\n".join(lines) if lines else "  (empty)"


def _select_random(
    pool: list[dict[str, Any]],
    num: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    """Randomly select *num* examples from *pool*.

    Args:
        pool: Candidate examples.
        num: Number of examples to select.
        seed: Random seed for reproducibility.

    Returns:
        Randomly selected examples.
    """
    rng = random.Random(seed)  # noqa: S311 -- not used for cryptographic purposes; deterministic sampling
    return rng.sample(pool, num)


def _select_similar(
    pool: list[dict[str, Any]],
    query: dict[str, Any],
    num: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    """Select examples most similar to *query* by shared category/tags.

    Similarity is computed as the number of matching metadata values
    for the keys ``"category"``, ``"tags"``, ``"language"``, and ``"difficulty"``.
    For the ``"tags"`` key the score is the size of the intersection.

    When there are ties in similarity score, a seeded RNG is used to
    shuffle tied candidates for deterministic tie-breaking.

    Args:
        pool: Candidate examples.
        query: The query dictionary to compare against.
        num: Number of examples to select.
        seed: Random seed for reproducibility in tie-breaking.

    Returns:
        Examples sorted by descending similarity, with ties broken
        deterministically when *seed* is provided.
    """
    rng = random.Random(seed)  # noqa: S311 -- not used for cryptographic purposes; deterministic sampling

    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, example in enumerate(pool):
        score = _similarity_score(example, query)
        scored.append((score, idx, example))

    # Group by score and shuffle within each group for deterministic tie-breaking
    # Sort descending by score first
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build groups of tied scores
    groups: list[list[tuple[float, int, dict[str, Any]]]] = []
    current_group: list[tuple[float, int, dict[str, Any]]] = []
    current_score: float | None = None

    for item in scored:
        if current_score is None or item[0] == current_score:
            current_group.append(item)
            current_score = item[0]
        else:
            groups.append(current_group)
            current_group = [item]
            current_score = item[0]
    if current_group:
        groups.append(current_group)

    # Shuffle within each group and flatten
    result: list[dict[str, Any]] = []
    for group in groups:
        rng.shuffle(group)
        for _, _, example in group:
            result.append(example)
            if len(result) == num:
                return result

    return result[:num]


def _similarity_score(example: dict[str, Any], query: dict[str, Any]) -> float:
    """Compute a simple similarity score between an example and a query.

    Checks the following keys:
    - ``"category"``: +1 if equal.
    - ``"language"``: +1 if equal.
    - ``"difficulty"``: +1 if equal.
    - ``"tags"``: +1 for each shared tag (set intersection size).

    Args:
        example: Candidate example dictionary.
        query: Target query dictionary.

    Returns:
        Non-negative similarity score.
    """
    score = 0.0

    for key in ("category", "language", "difficulty"):
        if key in example and key in query and example[key] == query[key]:
            score += 1.0

    example_tags = set(example.get("tags", []))
    query_tags = set(query.get("tags", []))
    score += len(example_tags & query_tags)

    return score


def _select_diverse(
    pool: list[dict[str, Any]],
    num: int,
    seed: int | None,
) -> list[dict[str, Any]]:
    """Select diverse examples covering different categories.

    Groups candidates by their ``"category"`` key (falling back to
    ``"_uncategorized_"``), then round-robins across categories to
    select *num* examples. Within each category, examples are shuffled
    using the provided *seed* for reproducibility.

    Args:
        pool: Candidate examples.
        num: Number of examples to select.
        seed: Random seed for reproducibility.

    Returns:
        Diverse selection of examples from different categories.
    """
    rng = random.Random(seed)  # noqa: S311 -- not used for cryptographic purposes; deterministic sampling

    # Group by category
    categories: dict[str, list[dict[str, Any]]] = {}
    for example in pool:
        cat = example.get("category", "_uncategorized_")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(example)

    # Shuffle within each category for fairness
    for cat_examples in categories.values():
        rng.shuffle(cat_examples)

    # Sort category keys for deterministic ordering
    sorted_cats = sorted(categories.keys())

    # Track current index within each category's shuffled list
    cat_indices: dict[str, int] = dict.fromkeys(sorted_cats, 0)

    result: list[dict[str, Any]] = []
    while len(result) < num:
        added_any = False
        for cat in sorted_cats:
            if len(result) >= num:
                break
            idx = cat_indices[cat]
            if idx < len(categories[cat]):
                result.append(categories[cat][idx])
                cat_indices[cat] = idx + 1
                added_any = True

        # If no category had remaining items, we've exhausted the pool
        if not added_any:
            break

    return result
