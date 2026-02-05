"""Multi-language support for code generation benchmarks.

This module provides:
- Language enum defining supported programming languages.
- LanguageConfig dataclass with per-language Docker, run, compile, and test settings.
- detect_language() to identify the language from a filename or code snippet.
- get_language_config() to retrieve configuration for a given language.
- get_supported_languages() to list all supported language names.
- CrossLanguageMetrics for comparing benchmark performance across languages.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Language(Enum):
    """Supported programming languages for code generation benchmarks."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"


@dataclass
class LanguageConfig:
    """Configuration for running and testing code in a specific language.

    Attributes:
        name: Human-readable language name.
        language: The Language enum member.
        file_extension: File extension including the dot (e.g., ".py").
        docker_image: Docker image used to run code in this language.
        run_command: Command template to run a file. Use {file} as placeholder.
        test_framework: Name of the default test framework for this language.
        compile_command: Optional command template to compile. None for interpreted languages.
    """

    name: str
    language: Language
    file_extension: str
    docker_image: str
    run_command: str
    test_framework: str
    compile_command: str | None = None


LANGUAGE_CONFIGS: dict[Language, LanguageConfig] = {
    Language.PYTHON: LanguageConfig(
        name="Python",
        language=Language.PYTHON,
        file_extension=".py",
        docker_image="python:3.11-slim",
        run_command="python {file}",
        test_framework="pytest",
    ),
    Language.JAVASCRIPT: LanguageConfig(
        name="JavaScript",
        language=Language.JAVASCRIPT,
        file_extension=".js",
        docker_image="node:20-slim",
        run_command="node {file}",
        test_framework="jest",
    ),
    Language.TYPESCRIPT: LanguageConfig(
        name="TypeScript",
        language=Language.TYPESCRIPT,
        file_extension=".ts",
        docker_image="node:20-slim",
        run_command="npx ts-node {file}",
        test_framework="jest",
        compile_command="npx tsc {file}",
    ),
    Language.JAVA: LanguageConfig(
        name="Java",
        language=Language.JAVA,
        file_extension=".java",
        docker_image="eclipse-temurin:17-jdk-jammy",
        run_command="java {file}",
        test_framework="junit",
        compile_command="javac {file}",
    ),
    Language.GO: LanguageConfig(
        name="Go",
        language=Language.GO,
        file_extension=".go",
        docker_image="golang:1.21-alpine",
        run_command="go run {file}",
        test_framework="go test",
        compile_command="go build {file}",
    ),
}

# Map file extensions to languages for filename-based detection.
_EXTENSION_MAP: dict[str, Language] = {
    config.file_extension: lang for lang, config in LANGUAGE_CONFIGS.items()
}

# Ordered list of (pattern, language) tuples for code content detection.
# More specific patterns come first to avoid false positives.
_CODE_PATTERNS: list[tuple[re.Pattern[str], Language]] = [
    # Go: package declaration is highly distinctive
    (re.compile(r"^package\s+\w+", re.MULTILINE), Language.GO),
    (re.compile(r"\bfunc\s+\w+\s*\("), Language.GO),
    # Java: class declaration with access modifier
    (re.compile(r"\bpublic\s+class\s+\w+"), Language.JAVA),
    (re.compile(r"\bpublic\s+static\s+void\s+main"), Language.JAVA),
    # TypeScript: type annotations on const/let/var, or interface keyword
    (re.compile(r"\b(?:const|let|var)\s+\w+\s*:\s*\w+"), Language.TYPESCRIPT),
    (re.compile(r"\binterface\s+\w+\s*\{"), Language.TYPESCRIPT),
    # JavaScript: const/let/var without type annotations, require(), console.log
    (re.compile(r"\brequire\s*\(\s*['\"]"), Language.JAVASCRIPT),
    (re.compile(r"\bconsole\.log\s*\("), Language.JAVASCRIPT),
    (re.compile(r"\b(?:const|let|var)\s+\w+\s*="), Language.JAVASCRIPT),
    # Python: def/class with colon, import, print()
    (re.compile(r"^def\s+\w+\s*\(.*\)\s*:", re.MULTILINE), Language.PYTHON),
    (re.compile(r"^import\s+\w+", re.MULTILINE), Language.PYTHON),
    (re.compile(r"\bprint\s*\("), Language.PYTHON),
]


def detect_language(code: str | None = None, filename: str | None = None) -> Language | None:
    """Detect the programming language from a filename or code snippet.

    Filename-based detection takes priority over code content analysis.

    Args:
        code: Source code string to analyze.
        filename: Filename (with or without path) to check extension.

    Returns:
        The detected Language, or None if detection fails.
    """
    # Try filename-based detection first (higher confidence).
    if filename:
        _, ext = os.path.splitext(filename)
        if ext in _EXTENSION_MAP:
            return _EXTENSION_MAP[ext]

    # Fall back to code content analysis.
    if code:
        for pattern, language in _CODE_PATTERNS:
            if pattern.search(code):
                return language

    return None


def get_language_config(language: Language) -> LanguageConfig:
    """Get the configuration for a given language.

    Args:
        language: A Language enum member.

    Returns:
        The LanguageConfig for the specified language.
    """
    return LANGUAGE_CONFIGS[language]


def get_supported_languages() -> list[str]:
    """Return a list of all supported language name strings.

    Returns:
        List of language value strings (e.g., ["python", "javascript", ...]).
    """
    return [lang.value for lang in Language]


@dataclass
class CrossLanguageMetrics:
    """Aggregated benchmark metrics across multiple programming languages.

    Attributes:
        language_scores: Mapping of language name to its pass rate (resolved ratio).
        best_language: The language with the highest pass rate.
        worst_language: The language with the lowest pass rate.
        average_score: The mean pass rate across all languages.
    """

    language_scores: dict[str, float]
    best_language: str
    worst_language: str
    average_score: float

    @classmethod
    def from_results(cls, results: dict[str, list[dict[str, Any]]]) -> CrossLanguageMetrics:
        """Compute cross-language metrics from per-language result lists.

        Each result dict is expected to have a ``"resolved"`` boolean key.
        The pass rate for a language is the fraction of results where
        ``resolved`` is ``True``.

        Args:
            results: Mapping of language name to list of result dicts.

        Returns:
            A CrossLanguageMetrics instance with computed scores.

        Raises:
            ValueError: If results is empty or any language has an empty result list.
        """
        if not results:
            raise ValueError("results must not be empty")

        language_scores: dict[str, float] = {}
        for lang_name, lang_results in results.items():
            if not lang_results:
                raise ValueError(f"Result list for language '{lang_name}' must not be empty")
            resolved_count = sum(1 for r in lang_results if r.get("resolved", False))
            language_scores[lang_name] = resolved_count / len(lang_results)

        best_language = max(language_scores, key=language_scores.get)  # type: ignore[arg-type]
        worst_language = min(language_scores, key=language_scores.get)  # type: ignore[arg-type]
        average_score = sum(language_scores.values()) / len(language_scores)

        return cls(
            language_scores=language_scores,
            best_language=best_language,
            worst_language=worst_language,
            average_score=average_score,
        )
