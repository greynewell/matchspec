"""Tests for multi-language support module."""

import pytest

from mcpbr.languages import (
    LANGUAGE_CONFIGS,
    CrossLanguageMetrics,
    Language,
    LanguageConfig,
    detect_language,
    get_language_config,
    get_supported_languages,
)

# ===================================================================
# Language Enum
# ===================================================================


class TestLanguageEnum:
    """Tests for the Language enum."""

    def test_python_value(self) -> None:
        """Test Python enum value."""
        assert Language.PYTHON.value == "python"

    def test_javascript_value(self) -> None:
        """Test JavaScript enum value."""
        assert Language.JAVASCRIPT.value == "javascript"

    def test_typescript_value(self) -> None:
        """Test TypeScript enum value."""
        assert Language.TYPESCRIPT.value == "typescript"

    def test_java_value(self) -> None:
        """Test Java enum value."""
        assert Language.JAVA.value == "java"

    def test_go_value(self) -> None:
        """Test Go enum value."""
        assert Language.GO.value == "go"

    def test_all_languages_present(self) -> None:
        """Test that all expected languages are defined."""
        expected = {"python", "javascript", "typescript", "java", "go"}
        actual = {lang.value for lang in Language}
        assert actual == expected

    def test_language_from_value(self) -> None:
        """Test creating Language from string value."""
        assert Language("python") is Language.PYTHON
        assert Language("javascript") is Language.JAVASCRIPT
        assert Language("typescript") is Language.TYPESCRIPT
        assert Language("java") is Language.JAVA
        assert Language("go") is Language.GO

    def test_invalid_language_value_raises(self) -> None:
        """Test that invalid value raises ValueError."""
        with pytest.raises(ValueError):
            Language("rust")


# ===================================================================
# LanguageConfig
# ===================================================================


class TestLanguageConfig:
    """Tests for the LanguageConfig dataclass."""

    def test_python_config(self) -> None:
        """Test Python language configuration."""
        config = LANGUAGE_CONFIGS[Language.PYTHON]
        assert config.name == "Python"
        assert config.language is Language.PYTHON
        assert config.file_extension == ".py"
        assert config.docker_image == "python:3.11-slim"
        assert config.run_command == "python {file}"
        assert config.test_framework == "pytest"
        assert config.compile_command is None

    def test_javascript_config(self) -> None:
        """Test JavaScript language configuration."""
        config = LANGUAGE_CONFIGS[Language.JAVASCRIPT]
        assert config.name == "JavaScript"
        assert config.language is Language.JAVASCRIPT
        assert config.file_extension == ".js"
        assert config.docker_image == "node:20-slim"
        assert config.run_command == "node {file}"
        assert config.test_framework == "jest"
        assert config.compile_command is None

    def test_typescript_config(self) -> None:
        """Test TypeScript language configuration."""
        config = LANGUAGE_CONFIGS[Language.TYPESCRIPT]
        assert config.name == "TypeScript"
        assert config.language is Language.TYPESCRIPT
        assert config.file_extension == ".ts"
        assert config.docker_image == "node:20-slim"
        assert config.run_command == "npx ts-node {file}"
        assert config.test_framework == "jest"
        assert config.compile_command == "npx tsc {file}"

    def test_java_config(self) -> None:
        """Test Java language configuration."""
        config = LANGUAGE_CONFIGS[Language.JAVA]
        assert config.name == "Java"
        assert config.language is Language.JAVA
        assert config.file_extension == ".java"
        assert config.docker_image == "eclipse-temurin:17-jdk-jammy"
        assert config.run_command == "java {file}"
        assert config.test_framework == "junit"
        assert config.compile_command == "javac {file}"

    def test_go_config(self) -> None:
        """Test Go language configuration."""
        config = LANGUAGE_CONFIGS[Language.GO]
        assert config.name == "Go"
        assert config.language is Language.GO
        assert config.file_extension == ".go"
        assert config.docker_image == "golang:1.21-alpine"
        assert config.run_command == "go run {file}"
        assert config.test_framework == "go test"
        assert config.compile_command == "go build {file}"

    def test_all_languages_have_configs(self) -> None:
        """Test that every Language enum member has a config entry."""
        for lang in Language:
            assert lang in LANGUAGE_CONFIGS, f"Missing config for {lang}"

    def test_config_run_command_has_placeholder(self) -> None:
        """Test that all run commands contain {file} placeholder."""
        for lang, config in LANGUAGE_CONFIGS.items():
            assert "{file}" in config.run_command, (
                f"Run command for {lang} missing {{file}} placeholder"
            )

    def test_compiled_languages_have_compile_command(self) -> None:
        """Test that TypeScript, Java, and Go have compile commands."""
        compiled = [Language.TYPESCRIPT, Language.JAVA, Language.GO]
        for lang in compiled:
            config = LANGUAGE_CONFIGS[lang]
            assert config.compile_command is not None, f"{lang} should have a compile command"

    def test_interpreted_languages_no_compile_command(self) -> None:
        """Test that Python and JavaScript have no compile command."""
        interpreted = [Language.PYTHON, Language.JAVASCRIPT]
        for lang in interpreted:
            config = LANGUAGE_CONFIGS[lang]
            assert config.compile_command is None, f"{lang} should not have a compile command"


# ===================================================================
# detect_language
# ===================================================================


class TestDetectLanguage:
    """Tests for the detect_language function."""

    # --- Detection by filename ---

    def test_detect_python_from_filename(self) -> None:
        """Test detecting Python from .py extension."""
        assert detect_language(filename="solution.py") is Language.PYTHON

    def test_detect_javascript_from_filename(self) -> None:
        """Test detecting JavaScript from .js extension."""
        assert detect_language(filename="app.js") is Language.JAVASCRIPT

    def test_detect_typescript_from_filename(self) -> None:
        """Test detecting TypeScript from .ts extension."""
        assert detect_language(filename="app.ts") is Language.TYPESCRIPT

    def test_detect_java_from_filename(self) -> None:
        """Test detecting Java from .java extension."""
        assert detect_language(filename="Main.java") is Language.JAVA

    def test_detect_go_from_filename(self) -> None:
        """Test detecting Go from .go extension."""
        assert detect_language(filename="main.go") is Language.GO

    def test_detect_from_filename_with_path(self) -> None:
        """Test detecting language from filename with directory path."""
        assert detect_language(filename="/path/to/file.py") is Language.PYTHON
        assert detect_language(filename="src/utils/helper.js") is Language.JAVASCRIPT

    def test_detect_unknown_extension(self) -> None:
        """Test that unknown file extension returns None."""
        assert detect_language(filename="file.rs") is None
        assert detect_language(filename="file.cpp") is None
        assert detect_language(filename="file.rb") is None

    def test_detect_no_extension(self) -> None:
        """Test that filename without extension returns None."""
        assert detect_language(filename="Makefile") is None
        assert detect_language(filename="README") is None

    # --- Detection by code content ---

    def test_detect_python_from_code(self) -> None:
        """Test detecting Python from code content."""
        code = "def hello():\n    print('Hello, World!')\n"
        assert detect_language(code=code) is Language.PYTHON

    def test_detect_python_from_import(self) -> None:
        """Test detecting Python from import statement."""
        code = "import os\nimport sys\n"
        assert detect_language(code=code) is Language.PYTHON

    def test_detect_javascript_from_code(self) -> None:
        """Test detecting JavaScript from code content."""
        code = "const x = 42;\nconsole.log(x);\n"
        assert detect_language(code=code) is Language.JAVASCRIPT

    def test_detect_javascript_from_require(self) -> None:
        """Test detecting JavaScript from require statement."""
        code = "const fs = require('fs');\n"
        assert detect_language(code=code) is Language.JAVASCRIPT

    def test_detect_typescript_from_code(self) -> None:
        """Test detecting TypeScript from code with type annotations."""
        code = "const x: number = 42;\ninterface Foo { bar: string; }\n"
        assert detect_language(code=code) is Language.TYPESCRIPT

    def test_detect_java_from_code(self) -> None:
        """Test detecting Java from code content."""
        code = "public class Main {\n    public static void main(String[] args) {}\n}\n"
        assert detect_language(code=code) is Language.JAVA

    def test_detect_go_from_code(self) -> None:
        """Test detecting Go from code content."""
        code = 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello")\n}\n'
        assert detect_language(code=code) is Language.GO

    def test_detect_unknown_code(self) -> None:
        """Test that unrecognizable code returns None."""
        code = "x = 1 + 2"
        assert detect_language(code=code) is None

    # --- Edge cases ---

    def test_detect_no_arguments_returns_none(self) -> None:
        """Test that calling with no arguments returns None."""
        assert detect_language() is None

    def test_detect_filename_takes_priority(self) -> None:
        """Test that filename detection takes priority over code content."""
        # Java code with .py filename should detect as Python
        java_code = "public class Main { public static void main(String[] args) {} }"
        assert detect_language(code=java_code, filename="main.py") is Language.PYTHON

    def test_detect_empty_code_returns_none(self) -> None:
        """Test that empty code string returns None."""
        assert detect_language(code="") is None

    def test_detect_empty_filename_returns_none(self) -> None:
        """Test that empty filename string returns None."""
        assert detect_language(filename="") is None


# ===================================================================
# get_language_config
# ===================================================================


class TestGetLanguageConfig:
    """Tests for the get_language_config function."""

    def test_get_python_config(self) -> None:
        """Test getting Python configuration."""
        config = get_language_config(Language.PYTHON)
        assert isinstance(config, LanguageConfig)
        assert config.language is Language.PYTHON
        assert config.name == "Python"

    def test_get_javascript_config(self) -> None:
        """Test getting JavaScript configuration."""
        config = get_language_config(Language.JAVASCRIPT)
        assert isinstance(config, LanguageConfig)
        assert config.language is Language.JAVASCRIPT

    def test_get_typescript_config(self) -> None:
        """Test getting TypeScript configuration."""
        config = get_language_config(Language.TYPESCRIPT)
        assert isinstance(config, LanguageConfig)
        assert config.language is Language.TYPESCRIPT

    def test_get_java_config(self) -> None:
        """Test getting Java configuration."""
        config = get_language_config(Language.JAVA)
        assert isinstance(config, LanguageConfig)
        assert config.language is Language.JAVA

    def test_get_go_config(self) -> None:
        """Test getting Go configuration."""
        config = get_language_config(Language.GO)
        assert isinstance(config, LanguageConfig)
        assert config.language is Language.GO

    def test_all_configs_returned_correctly(self) -> None:
        """Test that get_language_config matches LANGUAGE_CONFIGS dict."""
        for lang in Language:
            assert get_language_config(lang) is LANGUAGE_CONFIGS[lang]


# ===================================================================
# get_supported_languages
# ===================================================================


class TestGetSupportedLanguages:
    """Tests for the get_supported_languages function."""

    def test_returns_list(self) -> None:
        """Test that function returns a list."""
        result = get_supported_languages()
        assert isinstance(result, list)

    def test_contains_all_languages(self) -> None:
        """Test that all languages are in the returned list."""
        result = get_supported_languages()
        expected = {"python", "javascript", "typescript", "java", "go"}
        assert set(result) == expected

    def test_returns_string_values(self) -> None:
        """Test that returned values are strings, not enum members."""
        result = get_supported_languages()
        for item in result:
            assert isinstance(item, str)

    def test_length_matches_enum(self) -> None:
        """Test that length matches number of Language enum members."""
        result = get_supported_languages()
        assert len(result) == len(Language)


# ===================================================================
# CrossLanguageMetrics
# ===================================================================


SAMPLE_RESULTS: dict[str, list[dict]] = {
    "python": [
        {"resolved": True, "score": 0.9},
        {"resolved": True, "score": 0.8},
        {"resolved": False, "score": 0.3},
    ],
    "javascript": [
        {"resolved": True, "score": 0.7},
        {"resolved": False, "score": 0.4},
        {"resolved": False, "score": 0.2},
    ],
    "go": [
        {"resolved": True, "score": 1.0},
        {"resolved": True, "score": 0.95},
        {"resolved": True, "score": 0.85},
    ],
}


class TestCrossLanguageMetrics:
    """Tests for the CrossLanguageMetrics dataclass."""

    def test_from_results_creates_instance(self) -> None:
        """Test that from_results returns a CrossLanguageMetrics instance."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        assert isinstance(metrics, CrossLanguageMetrics)

    def test_language_scores_computed(self) -> None:
        """Test that language_scores contains entries for all languages."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        assert "python" in metrics.language_scores
        assert "javascript" in metrics.language_scores
        assert "go" in metrics.language_scores

    def test_language_scores_are_pass_rates(self) -> None:
        """Test that language scores are computed as pass rates (resolved ratio)."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        # Python: 2/3 resolved
        assert metrics.language_scores["python"] == pytest.approx(2 / 3)
        # JavaScript: 1/3 resolved
        assert metrics.language_scores["javascript"] == pytest.approx(1 / 3)
        # Go: 3/3 resolved
        assert metrics.language_scores["go"] == pytest.approx(1.0)

    def test_best_language(self) -> None:
        """Test that best_language identifies the highest scoring language."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        assert metrics.best_language == "go"

    def test_worst_language(self) -> None:
        """Test that worst_language identifies the lowest scoring language."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        assert metrics.worst_language == "javascript"

    def test_average_score(self) -> None:
        """Test that average_score is the mean of all language scores."""
        metrics = CrossLanguageMetrics.from_results(SAMPLE_RESULTS)
        expected_avg = (2 / 3 + 1 / 3 + 1.0) / 3
        assert metrics.average_score == pytest.approx(expected_avg)

    def test_single_language_results(self) -> None:
        """Test with results for only one language."""
        single = {"python": [{"resolved": True}, {"resolved": False}]}
        metrics = CrossLanguageMetrics.from_results(single)
        assert metrics.best_language == "python"
        assert metrics.worst_language == "python"
        assert metrics.average_score == pytest.approx(0.5)
        assert metrics.language_scores["python"] == pytest.approx(0.5)

    def test_all_resolved_results(self) -> None:
        """Test with all results resolved."""
        all_pass = {
            "python": [{"resolved": True}],
            "java": [{"resolved": True}],
        }
        metrics = CrossLanguageMetrics.from_results(all_pass)
        assert metrics.average_score == pytest.approx(1.0)
        assert metrics.language_scores["python"] == pytest.approx(1.0)
        assert metrics.language_scores["java"] == pytest.approx(1.0)

    def test_no_resolved_results(self) -> None:
        """Test with no results resolved."""
        no_pass = {
            "python": [{"resolved": False}],
            "java": [{"resolved": False}],
        }
        metrics = CrossLanguageMetrics.from_results(no_pass)
        assert metrics.average_score == pytest.approx(0.0)

    def test_empty_results_raises(self) -> None:
        """Test that empty results dict raises ValueError."""
        with pytest.raises(ValueError):
            CrossLanguageMetrics.from_results({})

    def test_empty_language_results_raises(self) -> None:
        """Test that a language with empty result list raises ValueError."""
        with pytest.raises(ValueError):
            CrossLanguageMetrics.from_results({"python": []})

    def test_from_results_two_languages_tied(self) -> None:
        """Test behavior when two languages have the same score."""
        tied = {
            "python": [{"resolved": True}, {"resolved": False}],
            "java": [{"resolved": True}, {"resolved": False}],
        }
        metrics = CrossLanguageMetrics.from_results(tied)
        assert metrics.language_scores["python"] == pytest.approx(0.5)
        assert metrics.language_scores["java"] == pytest.approx(0.5)
        assert metrics.average_score == pytest.approx(0.5)
        # Both are tied; best/worst should be one of them
        assert metrics.best_language in ("python", "java")
        assert metrics.worst_language in ("python", "java")
