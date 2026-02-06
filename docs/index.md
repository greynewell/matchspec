---
description: "mcpbr is an open-source benchmark runner for evaluating AI agents and MCP servers across 25+ benchmarks including SWE-bench, HumanEval, GSM8K, CyberGym, and more."
faq:
  - q: "What is mcpbr?"
    a: "mcpbr (Model Context Protocol Benchmark Runner) is an open-source tool for evaluating AI agents and MCP servers across 25+ benchmarks including SWE-bench, HumanEval, GSM8K, CyberGym, MCPToolBench++, and more. It provides quantitative comparison between tool-assisted and baseline agent performance."
  - q: "What models does mcpbr support?"
    a: "mcpbr supports Claude models from Anthropic including Claude Opus 4.5, Claude Sonnet 4.5, and Claude Haiku 4.5. Run 'mcpbr models' to see the full list."
  - q: "How do I get started with mcpbr?"
    a: "Install mcpbr with 'pip install mcpbr', set your ANTHROPIC_API_KEY, run 'mcpbr init' to create a config file, then run 'mcpbr run -c mcpbr.yaml' to start an evaluation."
---

# mcpbr

```bash
pip install mcpbr && mcpbr init && mcpbr run -c mcpbr.yaml -n 1 -v
```

Benchmark your MCP server against real GitHub issues. One command, hard numbers.

---

<p align="center">
  <img src="assets/mcpbr-logo.jpg" alt="MCPBR Logo" width="400">
</p>

**Model Context Protocol Benchmark Runner**

[![PyPI version](https://badge.fury.io/py/mcpbr.svg)](https://pypi.org/project/mcpbr/)
[![npm version](https://badge.fury.io/js/mcpbr-cli.svg)](https://www.npmjs.com/package/mcpbr-cli)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/greynewell/mcpbr/actions/workflows/ci.yml/badge.svg)](https://github.com/greynewell/mcpbr/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Stop guessing if your MCP server actually helps. Get hard numbers comparing tool-assisted vs. baseline agent performance on real GitHub issues.

<p align="center">
  <img src="assets/mcpbr-demo.gif" alt="mcpbr in action" width="700">
</p>

## What You Get

Real metrics showing whether your MCP server improves agent performance on SWE-bench tasks. No vibes, just data.

```text
Evaluation Results

                 Summary
+-----------------+-----------+----------+
| Metric          | MCP Agent | Baseline |
+-----------------+-----------+----------+
| Resolved        | 8/25      | 5/25     |
| Resolution Rate | 32.0%     | 20.0%    |
+-----------------+-----------+----------+

Improvement: +60.0%
```

## Why mcpbr?

MCP servers promise to make LLMs better at coding tasks. But how do you *prove* it?

mcpbr runs controlled experiments: same model, same tasks, same environment - the only variable is your MCP server. You get:

- **Apples-to-apples comparison** against a baseline agent
- **Real GitHub issues** from SWE-bench (not toy examples)
- **Reproducible results** via Docker containers with pinned dependencies

!!! info "Origin Story"
    Learn why mcpbr was built and the key insight that "MCP servers should be tested like APIs, not like plugins" in the blog post: **[Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)**

## Quick Start

### Option 1: Use Example Configurations (Fastest)

Get started in seconds with our ready-to-use examples:

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-api-key"

# Run your first evaluation
mcpbr run -c examples/quick-start/getting-started.yaml -v
```

This runs 5 SWE-bench tasks with the filesystem server. Expected runtime: 15-30 minutes, cost: $2-5.

!!! tip "Explore 25+ Example Configurations"
    Browse the [`examples/`](https://github.com/greynewell/mcpbr/tree/main/examples) directory for:

    - **Quick Start**: Getting started, testing servers, comparing models
    - **Benchmarks**: SWE-bench Lite/Full, CyberGym basic/advanced
    - **MCP Servers**: Filesystem, GitHub, Brave Search, databases, custom servers
    - **Scenarios**: Cost-optimized, performance-optimized, CI/CD, regression detection

    See the [Examples README](https://github.com/greynewell/mcpbr/tree/main/examples/README.md) for the complete guide.

### Option 2: Generate Custom Configuration

#### 1. Set your API key

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

#### 2. Generate a configuration file

```bash
mcpbr init
```

#### 3. Edit the configuration

Point it to your MCP server:

```yaml
mcp_server:
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env: {}

provider: "anthropic"
agent_harness: "claude-code"
model: "sonnet"
dataset: "SWE-bench/SWE-bench_Lite"
sample_size: 10
timeout_seconds: 300
max_concurrent: 4
```

#### 4. Run the evaluation

```bash
mcpbr run --config mcpbr.yaml
```

## How It Works

mcpbr runs two parallel evaluations for each SWE-bench task:

1. **MCP Agent**: LLM with access to tools from your MCP server
2. **Baseline Agent**: Same LLM without MCP tools

By comparing resolution rates, you can measure the effectiveness of your MCP server for code exploration and bug fixing.

```
Host Machine
+-----------------------------------------------------------+
|                    mcpbr Harness (Python)                 |
|  - Loads SWE-bench tasks from HuggingFace                 |
|  - Pulls pre-built Docker images                          |
|  - Orchestrates agent runs                                |
|  - Collects results and generates reports                 |
+----------------------------+------------------------------+
                             | docker exec
+----------------------------v------------------------------+
|              Docker Container (per task)                  |
|  - Repository at correct commit                           |
|  - All dependencies pre-installed                         |
|  - Claude Code CLI runs inside container                  |
|  - Generates patches and runs tests                       |
+-----------------------------------------------------------+
```

## Next Steps

- [About mcpbr](about.md) - The project story, philosophy, and vision
- [Testing Philosophy](philosophy.md) - Why MCP servers should be tested like APIs, not plugins
- [Examples](https://github.com/greynewell/mcpbr/tree/main/examples) - Browse 25+ example configurations
- [FAQ](FAQ.md) - Frequently asked questions
- [Best Practices](best-practices.md) - Guide to effective mcpbr usage
- [Installation](installation.md) - Prerequisites and installation options
- [Configuration](configuration.md) - Full configuration reference
- [CLI Reference](cli.md) - All available commands and options
- [MCP Integration](mcp-integration.md) - How to test your MCP server
- [Benchmarks](benchmarks/index.md) - Available benchmarks and how to use them
- [Evaluation Results](evaluation-results.md) - Understanding output formats
- [Troubleshooting](troubleshooting.md) - Common issues and solutions


---

Built by [Grey Newell](https://greynewell.com) | [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)
