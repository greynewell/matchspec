---
faq:
  - q: "How do I configure mcpbr to use my MCP server?"
    a: "Configure the mcp_server section in your YAML config file with the command to start your server, args (using {workdir} as placeholder for the task repository path), and any required environment variables."
  - q: "What configuration parameters are available in mcpbr?"
    a: "Key parameters include mcp_server (command, args, env), provider (anthropic), model, benchmark, sample_size, timeout_seconds, max_concurrent, and max_iterations."
  - q: "How do I use environment variables in mcpbr config?"
    a: "Reference environment variables in the env section using ${VAR_NAME} syntax, e.g., SUPERMODEL_API_KEY: '${SUPERMODEL_API_KEY}'. The variable will be expanded from your shell environment at runtime."
  - q: "What is the {workdir} placeholder in mcpbr?"
    a: "The {workdir} placeholder is replaced at runtime with the path to the task repository inside the Docker container. Use it in your MCP server args to point to the workspace."
---

# Configuration

mcpbr uses YAML configuration files to define your MCP server settings and evaluation parameters.

## Getting Started with Examples

!!! tip "New to mcpbr?"
    The fastest way to get started is with our **[example configurations](https://github.com/greynewell/mcpbr/tree/main/examples)**. We provide 25+ ready-to-use configs for common scenarios:

    - **Quick Start**: Getting started, testing servers, comparing models
    - **Benchmarks**: SWE-bench Lite/Full, CyberGym basic/advanced
    - **MCP Servers**: Filesystem, GitHub, Brave Search, databases, custom servers
    - **Scenarios**: Cost-optimized, performance-optimized, CI/CD, regression detection

    ```bash
    # Run an example config directly
    mcpbr run -c examples/quick-start/getting-started.yaml -v

    # Or copy and customize
    cp examples/scenarios/balanced.yaml my-config.yaml
    vim my-config.yaml
    mcpbr run -c my-config.yaml
    ```

    See the **[Examples README](https://github.com/greynewell/mcpbr/tree/main/examples/README.md)** for the complete guide.

## Generating a Config File

### Using Templates (Recommended)

mcpbr includes pre-configured templates for popular MCP servers. This is the easiest way to get started:

```bash
# List available templates
mcpbr config list

# Apply a template
mcpbr config apply filesystem

# Or use the interactive wizard
mcpbr init -i
```

Available templates include:

- **filesystem** - File system access (no API key required)
- **brave-search** - Web search using Brave Search API
- **postgres** - PostgreSQL database access
- **sqlite** - SQLite database access
- **github** - GitHub API integration
- **google-maps** - Google Maps APIs
- **slack** - Slack workspace integration

### Manual Configuration

Create a basic starter configuration:

```bash
mcpbr init
```

This creates `mcpbr.yaml` with sensible defaults.

## Configuration Reference

### Full Example

```yaml
# MCP Server Configuration
mcp_server:
  name: "mcpbr"  # Name for the MCP server (appears in tool names)
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env: {}

# Provider and Harness
provider: "anthropic"
agent_harness: "claude-code"

# Custom Agent Prompt (optional)
agent_prompt: |
  Fix the following bug in this repository:

  {problem_statement}

  Make the minimal changes necessary to fix the issue.
  Focus on the root cause, not symptoms.

# Model Configuration (use alias or full name)
model: "sonnet"  # or "claude-sonnet-4-5-20250929"

# Benchmark Selection
benchmark: "swe-bench-lite"  # 300 tasks for quick testing
sample_size: 10  # null for full benchmark

# Execution Parameters
timeout_seconds: 300
max_concurrent: 4
max_iterations: 10

# Docker Configuration
use_prebuilt_images: true
```

### MCP Server Section

The `mcp_server` section defines how to start your MCP server:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Name to register the MCP server as (default: `mcpbr`) |
| `command` | string | Executable to run (e.g., `npx`, `uvx`, `python`) |
| `args` | list | Command arguments. Use `{workdir}` as placeholder |
| `env` | dict | Additional environment variables |

#### The `{workdir}` Placeholder

The `{workdir}` placeholder is replaced at runtime with the path to the task repository inside the Docker container (typically `/workspace`). This allows your MCP server to access the codebase.

#### Environment Variables

mcpbr supports environment variable substitution throughout your configuration file for secure credential management and flexible deployments.

**Basic Syntax:**

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    # Required variable - error if not set
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"

    # Optional variable with default value
    LOG_LEVEL: "${LOG_LEVEL:-info}"

    # Works in any string field
    DATABASE_URL: "${DB_URL}"
```

**Using .env Files:**

mcpbr automatically loads environment variables from a `.env` file in the current directory:

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-...
SUPERMODEL_API_KEY=sm-...
LOG_LEVEL=debug
```

Then in your config:

```yaml
mcp_server:
  env:
    API_KEY: "${ANTHROPIC_API_KEY}"  # Loaded from .env
```

**Variable Precedence:**

1. Shell environment variables (highest priority)
2. .env file
3. Default values in config (`${VAR:-default}`)

**Security Warnings:**

mcpbr will warn you if it detects hardcoded secrets:

```yaml
# ⚠️ Warning: hardcoded API key detected
mcp_server:
  env:
    API_KEY: "sk-ant-hardcoded-key"  # Bad!

# ✅ Good: using environment variable
mcp_server:
  env:
    API_KEY: "${ANTHROPIC_API_KEY}"  # Good!
```

**Advanced Features:**

- **Multiple substitutions**: `"prefix_${VAR1}_middle_${VAR2}_suffix"`
- **Nested structures**: Works in dicts, lists, and nested configs
- **Non-string values**: Numbers and booleans pass through unchanged
- **Model selection**: `model: "${MODEL:-sonnet}"`
- **Sample size**: `sample_size: ${SAMPLE_SIZE:-10}`

See [`examples/env-vars-example.yaml`](https://github.com/greynewell/mcpbr/tree/main/examples/env-vars-example.yaml) for a complete example.

### Provider and Harness

| Field | Values | Description |
|-------|--------|-------------|
| `provider` | `anthropic` | LLM provider (currently only Anthropic is supported) |
| `agent_harness` | `claude-code` | Agent backend (currently only Claude Code CLI is supported) |

### Custom Agent Prompt

Customize the prompt sent to the agent:

```yaml
agent_prompt: |
  Fix the following bug in this repository:

  {problem_statement}

  Make the minimal changes necessary to fix the issue.
  Focus on the root cause, not symptoms.
```

Use `{problem_statement}` as a placeholder for the SWE-bench issue text.

!!! tip "CLI Override"
    Override the prompt at runtime with `--prompt`:
    ```bash
    mcpbr run -c config.yaml --prompt "Fix this: {problem_statement}"
    ```

### Model Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `model` | `sonnet` | Model alias or full Anthropic model ID |

You can use either aliases (`sonnet`, `opus`, `haiku`) or full model names (`claude-sonnet-4-5-20250929`).
Aliases automatically resolve to the latest model version.

See [Installation](installation.md#supported-models) for the full list of supported models.

### Benchmark Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `benchmark` | `swe-bench` | Benchmark to run (`swe-bench` or `cybergym`) |
| `cybergym_level` | `1` | CyberGym difficulty level (0-3, only used for CyberGym) |

!!! info "Benchmark Selection"
    - **SWE-bench**: Bug fixing in Python repositories, evaluated with test suites
    - **CyberGym**: Security exploit generation in C/C++ projects, evaluated by crash detection

    See the [Benchmarks guide](benchmarks.md) for detailed information.

!!! tip "CLI Override"
    Override the benchmark at runtime:
    ```bash
    # Run CyberGym instead of SWE-bench
    mcpbr run -c config.yaml --benchmark cybergym --level 2
    ```

### Benchmark Selection

| Field | Default | Description |
|-------|---------|-------------|
| `benchmark` | `"swe-bench-verified"` | Benchmark to run |
| `sample_size` | `null` | Number of tasks (`null` = full dataset) |

Available benchmarks:

- **swe-bench-verified**: Manually validated test cases, accurate benchmarking (default)
- **swe-bench-lite**: 300 curated tasks, quick testing
- **swe-bench-full**: 2,294 tasks, comprehensive evaluation
- **cybergym**: Security exploits at various difficulty levels
- **mcptoolbench**: MCP tool usage evaluation

Example:
```yaml
benchmark: "swe-bench-verified"  # Use high-quality validated tasks
sample_size: 50                   # Run 50 tasks
```

### Filtering Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `filter_difficulty` | `null` | Filter tasks by difficulty (list of strings) |
| `filter_category` | `null` | Filter tasks by category (list of strings) |
| `filter_tags` | `null` | Filter tasks by tags (list of strings, requires all to match) |

Filter benchmarks to select specific subsets of tasks:

```yaml
# Filter by difficulty (CyberGym: 0-3, MCPToolBench: single/multi)
filter_difficulty:
  - "easy"
  - "medium"

# Filter by category (MCPToolBench: browser, finance, etc.)
filter_category:
  - "browser"
  - "web"

# Filter by tags (requires custom dataset with tags)
filter_tags:
  - "security"
  - "critical"
```

**Benchmark-specific filtering:**

- **SWE-bench**:
  - `filter_category`: Filter by repository name (e.g., "django", "scikit-learn")
  - `filter_difficulty` and `filter_tags`: Not supported in base dataset

- **CyberGym**:
  - `filter_difficulty`: Numeric levels (0-3) or names (easy, medium, hard, expert)
  - `filter_category`: Filter by project language (c++, python) or source (arvo, libfuzzer)
  - `filter_tags`: Not supported in base dataset

- **MCPToolBench++**:
  - `filter_difficulty`: Task complexity (easy/single, hard/multi)
  - `filter_category`: Task categories (browser, finance, web, etc.)
  - `filter_tags`: Not supported in base dataset

!!! tip "CLI Override"
    Apply filters at runtime:
    ```bash
    # Filter by difficulty
    mcpbr run -c config.yaml --filter-difficulty easy --filter-difficulty medium

    # Filter by category
    mcpbr run -c config.yaml --filter-category browser --filter-category finance

    # Combine multiple filters
    mcpbr run -c config.yaml \
      --filter-difficulty hard \
      --filter-category security
    ```

!!! note "Filter Behavior"
    - Filters are applied after task_ids selection but before sample_size
    - Multiple values within a filter are OR'ed (task matches ANY value)
    - Multiple different filters are AND'ed (task must match ALL filter types)
    - Empty filter lists are treated as no filter (all tasks pass)

### Execution Parameters

| Field | Default | Description |
|-------|---------|-------------|
| `timeout_seconds` | `300` | Timeout per task in seconds |
| `max_concurrent` | `4` | Maximum parallel task evaluations |
| `max_iterations` | `10` | Maximum agent iterations (turns) per task |
| `thinking_budget` | `null` | Extended thinking token budget (1024-31999) |

#### Extended Thinking Mode

The `thinking_budget` field enables Claude's extended thinking mode, allowing the model to reason through complex problems before responding. When enabled, Claude can use up to the specified token budget for internal reasoning (thinking tokens), separate from the response tokens.

**Configuration:**

```yaml
# Enable extended thinking with 10,000 token budget
thinking_budget: 10000
```

**Valid Range:**
- Minimum: 1024 tokens (Claude API requirement)
- Maximum: 31999 tokens (Claude Code default cap)
- Default: `null` (disabled)

**When to Use:**

Extended thinking is particularly useful for:
- Complex debugging tasks requiring deep analysis
- Multi-step reasoning problems
- Tasks where the model needs to explore multiple solution paths
- Situations where upfront planning improves solution quality

**Cost Considerations:**

Thinking tokens are billed at a lower rate than regular input/output tokens. The exact pricing depends on your model tier. Extended thinking increases cost but may improve success rates on complex tasks, potentially reducing the number of attempts needed.

**Example Configurations:**

```yaml
# Conservative thinking budget for simpler tasks
thinking_budget: 5000

# Moderate thinking budget for balanced performance
thinking_budget: 10000

# Maximum thinking budget for very complex tasks
thinking_budget: 31999

# Disabled (default) - omit the field or set to null
thinking_budget: null
```

!!! warning "Configuration Only"
    **Important**: `thinking_budget` can only be configured in the YAML file. There is no CLI override option for this parameter.

    To disable thinking mode, omit the `thinking_budget` field entirely or explicitly set it to `null`:
    ```yaml
    # Thinking mode disabled (these are equivalent)
    thinking_budget: null
    # or simply omit the field
    ```

!!! note "Validation"
    mcpbr validates thinking_budget at configuration load time. Invalid values (< 1024 or > 31999) will produce a clear error message before evaluation starts.

### Docker Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `use_prebuilt_images` | `true` | Use pre-built SWE-bench Docker images when available |

### Partial Results Configuration

| Field | Default | Description |
|-------|---------|-------------|
| `save_partial_results` | `true` | Enable automatic saving of intermediate results |
| `partial_results_interval` | `60` | Interval in seconds between automatic saves |

Partial results allow you to recover from interruptions and prevent data loss during long-running evaluations:

- Results are automatically saved at regular intervals
- Graceful shutdown handling on SIGINT/SIGTERM
- Resume capability from saved state
- Metadata tracking for completion status

!!! tip "CLI Control"
    Control partial results from the command line:
    ```bash
    # Specify custom save location
    mcpbr run -c config.yaml --partial-results results.partial.json

    # Disable partial results
    mcpbr run -c config.yaml --no-partial-results

    # Resume from previous run
    mcpbr run -c config.yaml --resume --partial-results results.partial.json

    # Adjust save interval
    mcpbr run -c config.yaml --partial-interval 120
    ```

### Budget Control

| Field | Default | Description |
|-------|---------|-------------|
| `budget` | `null` | Maximum budget in USD (halts evaluation when reached) |

Set a budget limit to prevent runaway costs:

```yaml
budget: 10.0  # Stop after spending $10
```

!!! warning "Budget Limit"
    When the budget is exceeded, the evaluation will halt gracefully and save all completed results. This is useful for cost-controlled experiments.

## Example Configurations

### Anthropic Filesystem Server

Basic file system access:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
```

### Custom Python MCP Server

```yaml
mcp_server:
  command: "python"
  args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]
  env:
    LOG_LEVEL: "debug"
```

### Supermodel Codebase Analysis

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

### Fast Iteration (Development)

Small sample size with single concurrency for debugging:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "haiku"  # Faster, cheaper
sample_size: 3
max_concurrent: 1
timeout_seconds: 180
max_iterations: 5
```

### Full Benchmark Run

Comprehensive evaluation with maximum parallelism:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"
sample_size: null  # Full dataset
max_concurrent: 8
timeout_seconds: 600
max_iterations: 30
```

## Configuration Validation

mcpbr validates your configuration on startup:

- `provider` must be one of: `anthropic`
- `agent_harness` must be one of: `claude-code`
- `max_concurrent` must be at least 1
- `timeout_seconds` must be at least 30

Invalid configurations will produce clear error messages.

## Next Steps

- [CLI Reference](cli.md) - Command options that override config values
- [MCP Integration](mcp-integration.md) - Tips for testing your MCP server
- [Evaluation Results](evaluation-results.md) - Understanding output formats
