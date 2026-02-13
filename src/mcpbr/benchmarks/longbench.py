"""LongBench benchmark implementation for long-context understanding."""

import re
import string
from collections import Counter
from typing import Any

from datasets import load_dataset

from ..docker_env import DockerEnvironmentManager, TaskEnvironment
from .base import BenchmarkTask

# Mapping of LongBench subsets to their high-level categories
SUBSET_TO_CATEGORY: dict[str, str] = {
    # Single-Document QA
    "narrativeqa": "single_doc_qa",
    "qasper": "single_doc_qa",
    "multifieldqa_en": "single_doc_qa",
    "multifieldqa_zh": "single_doc_qa",
    # Multi-Document QA
    "hotpotqa": "multi_doc_qa",
    "2wikimqa": "multi_doc_qa",
    "musique": "multi_doc_qa",
    "dureader": "multi_doc_qa",
    # Summarization
    "gov_report": "summarization",
    "qmsum": "summarization",
    "multi_news": "summarization",
    "vcsum": "summarization",
    "samsum": "summarization",
    # Few-Shot Learning
    "triviaqa": "few_shot",
    "trec": "few_shot",
    "lsht": "few_shot",
    # Synthetic Tasks
    "passage_count": "synthetic",
    "passage_retrieval_en": "synthetic",
    "passage_retrieval_zh": "synthetic",
    # Code Completion
    "lcc": "code",
    "repobench-p": "code",
}

# Subsets that use F1 scoring
F1_SUBSETS = {
    "narrativeqa",
    "qasper",
    "multifieldqa_en",
    "multifieldqa_zh",
    "hotpotqa",
    "2wikimqa",
    "musique",
    "triviaqa",
}

# Subsets that use ROUGE-L scoring
ROUGE_SUBSETS = {
    "dureader",
    "gov_report",
    "qmsum",
    "multi_news",
    "vcsum",
    "samsum",
}

# Subsets that use classification accuracy
ACCURACY_SUBSETS = {
    "trec",
    "lsht",
    "passage_count",
    "passage_retrieval_en",
    "passage_retrieval_zh",
}

# Subsets that use edit similarity
EDIT_SIM_SUBSETS = {
    "lcc",
    "repobench-p",
}

# All available subsets
ALL_SUBSETS = list(SUBSET_TO_CATEGORY.keys())


class LongBenchBenchmark:
    """LongBench benchmark implementation.

    LongBench is a bilingual, multitask benchmark for long context understanding.
    It covers 6 categories across 21 tasks with contexts ranging from thousands
    to tens of thousands of tokens:

    - Single-Document QA: narrativeqa, qasper, multifieldqa_en, multifieldqa_zh
    - Multi-Document QA: hotpotqa, 2wikimqa, musique, dureader
    - Summarization: gov_report, qmsum, multi_news, vcsum, samsum
    - Few-Shot Learning: triviaqa, trec, lsht
    - Synthetic Tasks: passage_count, passage_retrieval_en, passage_retrieval_zh
    - Code Completion: lcc, repobench-p

    Evaluation uses task-appropriate metrics: F1 for QA, ROUGE-L for summarization,
    accuracy for classification, and edit similarity for code tasks.
    """

    name = "longbench"

    def __init__(
        self,
        dataset: str = "THUDM/LongBench",
        subset: str = "hotpotqa",
    ):
        """Initialize LongBench benchmark.

        Args:
            dataset: HuggingFace dataset identifier.
            subset: Dataset subset/config name (e.g., 'hotpotqa', 'narrativeqa').
        """
        self.dataset = dataset
        self.subset = subset

    def load_tasks(
        self,
        sample_size: int | None = None,
        task_ids: list[str] | None = None,
        level: int | None = None,
        filter_difficulty: list[str] | None = None,
        filter_category: list[str] | None = None,
        filter_tags: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Load tasks from LongBench dataset.

        Args:
            sample_size: Maximum number of tasks to load (None for all).
            task_ids: Specific task IDs to load (None for all).
            level: Unused for LongBench.
            filter_difficulty: Unused for LongBench.
            filter_category: Filter by task category. Valid categories:
                single_doc_qa, multi_doc_qa, summarization, few_shot,
                synthetic, code. When specified, loads tasks from all
                subsets matching the given categories.
            filter_tags: Unused for LongBench.

        Returns:
            List of LongBench task dictionaries.
        """
        _ = level
        _ = filter_difficulty
        _ = filter_tags

        # Determine which subsets to load based on filter_category
        subsets_to_load = self._resolve_subsets(filter_category)

        all_tasks: list[dict[str, Any]] = []
        for subset_name in subsets_to_load:
            try:
                ds = load_dataset(self.dataset, subset_name, split="test")
                for idx, item in enumerate(ds):
                    task = dict(item)
                    task["_subset"] = subset_name
                    task["_original_index"] = idx
                    all_tasks.append(task)
            except Exception:  # noqa: S112 -- intentionally skip unavailable dataset subsets and continue loading others
                # Skip subsets that fail to load (e.g., unavailable configs)
                continue

        # Filter by task_ids if specified
        if task_ids:
            task_id_set = set(task_ids)
            all_tasks = [
                t
                for t in all_tasks
                if f"longbench_{t['_subset']}_{t['_original_index']}" in task_id_set
            ]

        # Apply sample size limit
        if sample_size is not None and len(all_tasks) > sample_size:
            all_tasks = all_tasks[:sample_size]

        # Augment tasks with instance_id and problem_statement
        augmented_tasks = []
        for task in all_tasks:
            augmented = dict(task)
            subset_name = task["_subset"]
            orig_idx = task["_original_index"]
            augmented["instance_id"] = f"longbench_{subset_name}_{orig_idx}"
            augmented["problem_statement"] = self._generate_problem_statement(augmented)
            augmented["ground_truth_answers"] = task.get("answers", [])
            augmented["task_category"] = SUBSET_TO_CATEGORY.get(subset_name, "unknown")
            augmented_tasks.append(augmented)

        return augmented_tasks

    def _resolve_subsets(self, filter_category: list[str] | None) -> list[str]:
        """Resolve which subsets to load based on category filter.

        Args:
            filter_category: List of category names to include.

        Returns:
            List of subset names to load.
        """
        if not filter_category:
            # If no category filter, use the configured subset
            return [self.subset]

        category_set = {c.lower() for c in filter_category}
        resolved = []
        for subset_name, category in SUBSET_TO_CATEGORY.items():
            if category in category_set:
                resolved.append(subset_name)

        return resolved if resolved else [self.subset]

    def normalize_task(self, task: dict[str, Any]) -> BenchmarkTask:
        """Convert LongBench task to normalized format.

        Args:
            task: LongBench task dictionary.

        Returns:
            Normalized BenchmarkTask.

        Raises:
            ValueError: If required fields are missing.
        """
        instance_id = task.get("instance_id")
        if not instance_id:
            msg = f"Task missing required 'instance_id' field: {list(task.keys())}"
            raise ValueError(msg)

        input_text = task.get("input", "")
        if not input_text and not task.get("context", ""):
            msg = f"Task missing required 'input' or 'context' field: {list(task.keys())}"
            raise ValueError(msg)

        problem_statement = self._generate_problem_statement(task)
        subset_name = task.get("_subset", self.subset)

        return BenchmarkTask(
            task_id=instance_id,
            problem_statement=problem_statement,
            repo="longbench/context",
            commit="HEAD",
            metadata={
                "input": input_text,
                "context_length": task.get("length", 0),
                "dataset": task.get("dataset", subset_name),
                "language": task.get("language", "en"),
                "answers": task.get("answers", []),
                "all_classes": task.get("all_classes"),
                "subset": subset_name,
                "category": SUBSET_TO_CATEGORY.get(subset_name, "unknown"),
            },
        )

    def _generate_problem_statement(self, task: dict[str, Any]) -> str:
        """Generate problem statement from task.

        Includes the full long context in the problem statement so agents
        must process and understand it.

        Args:
            task: LongBench task dictionary.

        Returns:
            Problem statement for the agent.
        """
        input_text = task.get("input", "No input provided")
        context = task.get("context", "")
        subset_name = task.get("_subset", task.get("dataset", self.subset))
        category = SUBSET_TO_CATEGORY.get(subset_name, "unknown")

        # Build category-specific instructions
        if category in ("single_doc_qa", "multi_doc_qa"):
            task_instruction = (
                "Read the following document(s) carefully and answer the question "
                "based on the information provided."
            )
        elif category == "summarization":
            task_instruction = (
                "Read the following document(s) carefully and provide a concise summary "
                "capturing the key points."
            )
        elif category == "few_shot":
            task_instruction = (
                "Study the provided examples carefully and answer the question "
                "following the same pattern."
            )
        elif category == "synthetic":
            task_instruction = (
                "Analyze the provided passages carefully and answer the question precisely."
            )
        elif category == "code":
            task_instruction = "Read the provided code context and complete the code as requested."
        else:
            task_instruction = "Read the following context carefully and respond to the request."

        parts = [task_instruction, ""]

        if context:
            parts.append("--- CONTEXT ---")
            parts.append(context)
            parts.append("--- END CONTEXT ---")
            parts.append("")

        parts.append(f"Question/Task: {input_text}")

        return "\n".join(parts)

    async def create_environment(
        self,
        task: dict[str, Any],
        docker_manager: DockerEnvironmentManager,
    ) -> TaskEnvironment:
        """Create environment for LongBench task.

        LongBench doesn't require repository setup - creates minimal environment.

        Args:
            task: LongBench task dictionary.
            docker_manager: Docker environment manager.

        Returns:
            TaskEnvironment for the task.
        """
        instance_id = task.get("instance_id", "longbench_unknown")
        temp_task = {
            "instance_id": instance_id,
            "repo": "longbench/context",
            "base_commit": "HEAD",
        }
        return await docker_manager.create_environment(temp_task)

    async def evaluate(
        self,
        _env: TaskEnvironment,
        task: dict[str, Any],
        solution: str,
    ) -> dict[str, Any]:
        """Evaluate a solution for LongBench task.

        Uses the appropriate metric based on the task subset:
        - F1 score for QA tasks
        - ROUGE-L for summarization tasks
        - Accuracy for classification tasks
        - Edit similarity for code tasks

        Args:
            _env: Task environment (unused; evaluation is offline).
            task: LongBench task dictionary.
            solution: Solution to evaluate (agent's response).

        Returns:
            Dictionary with evaluation results including 'resolved' boolean.
        """
        answers = task.get("ground_truth_answers", task.get("answers", []))
        if not answers:
            return {"resolved": False, "error": "No ground truth answers available"}

        subset_name = task.get("_subset", task.get("dataset", self.subset))
        all_classes = task.get("all_classes")

        if subset_name in F1_SUBSETS:
            score = self._compute_f1_max(solution, answers)
            metric = "f1"
        elif subset_name in ROUGE_SUBSETS:
            score = self._compute_rouge_l_max(solution, answers)
            metric = "rouge_l"
        elif subset_name in ACCURACY_SUBSETS:
            score = self._compute_classification_accuracy(solution, answers, all_classes)
            metric = "accuracy"
        elif subset_name in EDIT_SIM_SUBSETS:
            score = self._compute_edit_similarity_max(solution, answers)
            metric = "edit_similarity"
        else:
            # Default to F1 for unknown subsets
            score = self._compute_f1_max(solution, answers)
            metric = "f1"

        # Threshold: score >= 0.5 is considered resolved for F1/ROUGE
        # For accuracy, exact match (1.0) is required
        if metric == "accuracy":
            resolved = score >= 1.0
        else:
            resolved = score >= 0.5

        return {
            "resolved": resolved,
            "score": score,
            "metric": metric,
            "subset": subset_name,
            "category": SUBSET_TO_CATEGORY.get(subset_name, "unknown"),
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize text for scoring by lowercasing, removing punctuation and articles.

        Args:
            text: Raw text.

        Returns:
            Normalized text.
        """
        text = text.lower().strip()
        # Remove articles
        text = re.sub(r"\b(a|an|the)\b", " ", text)
        # Remove punctuation
        text = text.translate(str.maketrans("", "", string.punctuation))
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _compute_f1(self, prediction: str, reference: str) -> float:
        """Compute token-level F1 score between prediction and reference.

        Args:
            prediction: Predicted answer text.
            reference: Reference answer text.

        Returns:
            F1 score between 0.0 and 1.0.
        """
        pred_tokens = self._normalize_text(prediction).split()
        ref_tokens = self._normalize_text(reference).split()

        if not pred_tokens or not ref_tokens:
            return 1.0 if pred_tokens == ref_tokens else 0.0

        common = Counter(pred_tokens) & Counter(ref_tokens)
        num_common = sum(common.values())

        if num_common == 0:
            return 0.0

        precision = num_common / len(pred_tokens)
        recall = num_common / len(ref_tokens)

        return 2 * precision * recall / (precision + recall)

    def _compute_f1_max(self, prediction: str, references: list[str]) -> float:
        """Compute maximum F1 score across all reference answers.

        Args:
            prediction: Predicted answer text.
            references: List of reference answer texts.

        Returns:
            Maximum F1 score.
        """
        if not references:
            return 0.0
        return max(self._compute_f1(prediction, ref) for ref in references)

    def _compute_rouge_l(self, prediction: str, reference: str) -> float:
        """Compute ROUGE-L (Longest Common Subsequence) F-measure.

        Args:
            prediction: Predicted text.
            reference: Reference text.

        Returns:
            ROUGE-L F-measure between 0.0 and 1.0.
        """
        pred_tokens = self._normalize_text(prediction).split()
        ref_tokens = self._normalize_text(reference).split()

        if not pred_tokens or not ref_tokens:
            return 1.0 if pred_tokens == ref_tokens else 0.0

        lcs_length = self._lcs_length(pred_tokens, ref_tokens)

        if lcs_length == 0:
            return 0.0

        precision = lcs_length / len(pred_tokens)
        recall = lcs_length / len(ref_tokens)

        return 2 * precision * recall / (precision + recall)

    def _lcs_length(self, seq1: list[str], seq2: list[str]) -> int:
        """Compute length of longest common subsequence.

        Args:
            seq1: First sequence.
            seq2: Second sequence.

        Returns:
            Length of the LCS.
        """
        m, n = len(seq1), len(seq2)
        # Use space-optimized DP with two rows
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i - 1] == seq2[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev, curr = curr, [0] * (n + 1)

        return prev[n]

    def _compute_rouge_l_max(self, prediction: str, references: list[str]) -> float:
        """Compute maximum ROUGE-L score across all reference answers.

        Args:
            prediction: Predicted text.
            references: List of reference texts.

        Returns:
            Maximum ROUGE-L score.
        """
        if not references:
            return 0.0
        return max(self._compute_rouge_l(prediction, ref) for ref in references)

    def _compute_classification_accuracy(
        self,
        prediction: str,
        references: list[str],
        all_classes: list[str] | None = None,
    ) -> float:
        """Compute classification accuracy.

        For classification tasks, checks if the predicted class matches
        any of the reference answers.

        Args:
            prediction: Predicted class/answer.
            references: List of correct answers.
            all_classes: All possible class labels (unused but available).

        Returns:
            1.0 if correct, 0.0 otherwise.
        """
        _ = all_classes
        pred_normalized = self._normalize_text(prediction)
        for ref in references:
            ref_normalized = self._normalize_text(ref)
            if ref_normalized == pred_normalized or ref_normalized in pred_normalized:
                return 1.0
        return 0.0

    def _compute_edit_similarity(self, prediction: str, reference: str) -> float:
        """Compute edit similarity between prediction and reference.

        Edit similarity = 1 - (edit_distance / max_length).

        Args:
            prediction: Predicted code.
            reference: Reference code.

        Returns:
            Edit similarity between 0.0 and 1.0.
        """
        if not prediction and not reference:
            return 1.0
        if not prediction or not reference:
            return 0.0

        m, n = len(prediction), len(reference)

        # Levenshtein distance using space-optimized DP
        prev = list(range(n + 1))
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                if prediction[i - 1] == reference[j - 1]:
                    curr[j] = prev[j - 1]
                else:
                    curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
            prev, curr = curr, [0] * (n + 1)

        edit_distance = prev[n]
        max_length = max(m, n)
        return 1.0 - (edit_distance / max_length)

    def _compute_edit_similarity_max(self, prediction: str, references: list[str]) -> float:
        """Compute maximum edit similarity across all reference answers.

        Args:
            prediction: Predicted code.
            references: List of reference code snippets.

        Returns:
            Maximum edit similarity score.
        """
        if not references:
            return 0.0
        return max(self._compute_edit_similarity(prediction, ref) for ref in references)

    def get_prebuilt_image(self, _task: dict[str, Any]) -> str | None:
        """Get pre-built Docker image name for LongBench task.

        LongBench doesn't use pre-built images.

        Args:
            _task: LongBench task dictionary (unused).

        Returns:
            None (no pre-built images available).
        """
        return None

    def get_prompt_template(self) -> str:
        """Get LongBench prompt template.

        Returns:
            Prompt template for long-context understanding tasks.
        """
        return (
            "You are given a long-context understanding task.\n\n"
            "{problem_statement}\n\n"
            "IMPORTANT INSTRUCTIONS:\n"
            "- Read the entire context carefully before answering\n"
            "- Base your answer solely on the information provided in the context\n"
            "- Be concise and precise in your answer\n"
            "- For QA tasks, provide a direct answer to the question\n"
            "- For summarization tasks, capture the key points concisely\n"
            "- For code tasks, complete the code following the existing patterns"
        )

    def get_default_sandbox_level(self) -> str | None:
        return None
