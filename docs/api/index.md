---
faq:
  - q: "What is the mcpbr Python API?"
    a: "mcpbr provides a full Python SDK for programmatic benchmarking of MCP servers, including configuration management, benchmark execution, analytics, and report generation -- all without requiring the CLI."
  - q: "How do I run mcpbr evaluations programmatically?"
    a: "Use the MCPBenchmark class from the SDK: create an instance with a config dict or YAML path, call validate() to check configuration, dry_run() to preview the execution plan, and run() to execute the benchmark asynchronously."
  - q: "What modules does mcpbr expose for extensibility?"
    a: "mcpbr exposes the SDK (mcpbr.sdk), configuration (mcpbr.config), benchmarks (mcpbr.benchmarks with a Benchmark protocol), analytics (mcpbr.analytics for statistical analysis and historical tracking), and reports (mcpbr.reports for HTML, Markdown, and PDF generation)."
  - q: "Can I define custom benchmarks?"
    a: "Yes. Implement the Benchmark protocol from mcpbr.benchmarks.base, which requires load_tasks(), normalize_task(), create_environment(), evaluate(), get_prebuilt_image(), and get_prompt_template() methods."
---

# API Reference

Comprehensive reference documentation for the mcpbr Python API. Use these modules to programmatically configure, execute, and analyze MCP server benchmarks.

## Quick Start

The fastest way to use mcpbr programmatically is through the SDK module:

```python
from mcpbr import MCPBenchmark, list_benchmarks, list_models, get_version

# Check available benchmarks and models
print(get_version())  # e.g., "0.8.0"
for b in list_benchmarks():
    print(b["name"], b["class"])

# Configure and validate a benchmark
bench = MCPBenchmark({
    "mcp_server": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
    },
    "benchmark": "humaneval",
    "model": "sonnet",
    "sample_size": 10,
})

is_valid, errors = bench.validate()
if is_valid:
    plan = bench.dry_run()
    print(plan)
```

!!! tip "SDK vs Harness"
    The **SDK** (`mcpbr.sdk`) provides a high-level, user-friendly interface for configuration and validation. For full evaluation execution with Docker environments, use the **Harness** (`mcpbr.harness.run_evaluation`) directly.

---

## Core Modules

mcpbr is organized into several focused modules. Click through to each sub-page for detailed API documentation with examples.

| Module | Description | Key Classes / Functions |
|--------|-------------|------------------------|
| [**SDK**](sdk.md) | High-level Python interface | `MCPBenchmark`, `BenchmarkResult`, `list_benchmarks()`, `list_models()` |
| [**Configuration**](configuration.md) | Config models and YAML loading | `HarnessConfig`, `MCPServerConfig`, `AzureConfig`, `load_config()` |
| [**Analytics**](analytics.md) | Statistical analysis and tracking | `ResultsDatabase`, `ComparisonEngine`, `RegressionDetector`, `ABTest` |
| [**Reports**](reports.md) | Report generation in multiple formats | `HTMLReportGenerator`, `EnhancedMarkdownGenerator`, `PDFReportGenerator` |
| [**Benchmarks**](benchmarks.md) | Benchmark protocol and extensions | `Benchmark` protocol, `BenchmarkTask`, `create_benchmark()` |

---

## Architecture Overview

```
mcpbr
 |-- sdk.py                  # Public Python SDK (MCPBenchmark, list_*)
 |-- config.py               # Configuration models (HarnessConfig, MCPServerConfig)
 |-- harness.py              # Evaluation orchestration (run_evaluation)
 |-- models.py               # Model registry (SUPPORTED_MODELS)
 |-- benchmarks/
 |   |-- base.py             # Benchmark protocol and BenchmarkTask
 |   |-- swebench.py         # SWE-bench implementation
 |   |-- humaneval.py        # HumanEval implementation
 |   +-- ...                 # 27+ benchmark implementations
 |-- analytics/
 |   |-- database.py         # SQLite results storage
 |   |-- statistical.py      # Hypothesis testing
 |   |-- comparison.py       # Multi-model comparison
 |   |-- regression_detector.py
 |   |-- ab_testing.py       # A/B testing framework
 |   |-- leaderboard.py      # Rankings generation
 |   |-- metrics.py          # Custom metrics registry
 |   |-- trends.py           # Time-series trends
 |   |-- anomaly.py          # Outlier detection
 |   |-- correlation.py      # Metric correlations
 |   |-- error_analysis.py   # Error clustering
 |   +-- difficulty.py       # Task difficulty scoring
 +-- reports/
     |-- html_report.py      # Interactive HTML reports
     |-- enhanced_markdown.py # GitHub-flavored markdown
     +-- pdf_report.py       # Print-friendly PDF reports
```

---

## Harness API

The harness module orchestrates the full evaluation pipeline, including task loading, Docker environment management, agent execution, and result aggregation.

### run_evaluation

::: mcpbr.harness.run_evaluation
    options:
      show_root_heading: true
      show_source: false

### EvaluationResults

::: mcpbr.harness.EvaluationResults
    options:
      show_root_heading: true
      show_source: false

### TaskResult

::: mcpbr.harness.TaskResult
    options:
      show_root_heading: true
      show_source: false

---

## Models

### ModelInfo

::: mcpbr.models.ModelInfo
    options:
      show_root_heading: true
      show_source: false

### Model Functions

::: mcpbr.models.list_supported_models
    options:
      show_root_heading: true
      show_source: false

::: mcpbr.models.get_model_info
    options:
      show_root_heading: true
      show_source: false

::: mcpbr.models.is_model_supported
    options:
      show_root_heading: true
      show_source: false

::: mcpbr.models.validate_model
    options:
      show_root_heading: true
      show_source: false

---

## Constants

### Default Values

```python
from mcpbr.models import DEFAULT_MODEL
from mcpbr.config import VALID_PROVIDERS, VALID_HARNESSES, VALID_BENCHMARKS

print(DEFAULT_MODEL)       # "sonnet"
print(VALID_PROVIDERS)     # ("anthropic", "openai", "gemini", "qwen")
print(VALID_HARNESSES)     # ("claude-code",)
print(VALID_BENCHMARKS)    # 29 benchmark identifiers
```

### Supported Models

| Model ID | Provider | Display Name | Context Window |
|----------|----------|-------------|----------------|
| `claude-opus-4-5-20251101` | Anthropic | Claude Opus 4.5 | 200,000 |
| `claude-sonnet-4-5-20250929` | Anthropic | Claude Sonnet 4.5 | 200,000 |
| `claude-haiku-4-5-20251001` | Anthropic | Claude Haiku 4.5 | 200,000 |
| `sonnet` | Anthropic | Claude Sonnet (alias) | 200,000 |
| `opus` | Anthropic | Claude Opus (alias) | 200,000 |
| `haiku` | Anthropic | Claude Haiku (alias) | 200,000 |
| `gpt-4o` | OpenAI | GPT-4o | 128,000 |
| `gpt-4-turbo` | OpenAI | GPT-4 Turbo | 128,000 |
| `gpt-4o-mini` | OpenAI | GPT-4o Mini | 128,000 |
| `gemini-2.0-flash` | Google | Gemini 2.0 Flash | 1,048,576 |
| `gemini-1.5-pro` | Google | Gemini 1.5 Pro | 2,097,152 |
| `gemini-1.5-flash` | Google | Gemini 1.5 Flash | 1,048,576 |
| `qwen-plus` | Alibaba | Qwen Plus | 131,072 |
| `qwen-turbo` | Alibaba | Qwen Turbo | 131,072 |
| `qwen-max` | Alibaba | Qwen Max | 131,072 |
