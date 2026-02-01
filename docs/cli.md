---
faq:
  - q: "What commands are available in mcpbr?"
    a: "mcpbr provides six commands: run (execute evaluations), init (generate config), models (list supported models), providers (list LLM providers), harnesses (list agent backends), benchmarks (list available benchmarks), and cleanup (remove orphaned Docker resources including containers, volumes, and networks)."
  - q: "How do I run only the MCP agent without the baseline?"
    a: "Use the --mcp-only or -M flag: 'mcpbr run -c config.yaml -M'. This skips the baseline evaluation and only runs the MCP-enabled agent."
  - q: "How do I run a specific SWE-bench task?"
    a: "Use the --task or -t flag with the instance_id: 'mcpbr run -c config.yaml -t astropy__astropy-12907'. You can repeat this flag to run multiple specific tasks."
  - q: "How do I save mcpbr results to a file?"
    a: "Use --output (-o) for JSON results, --output-yaml (-y) for YAML results, and --report (-r) for a Markdown report: 'mcpbr run -c config.yaml -o results.json -y results.yaml -r report.md'."
---

# CLI Reference

mcpbr provides a command-line interface for running evaluations and managing configurations.

## Global Help

```bash
mcpbr --help
mcpbr run --help
mcpbr init --help
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `mcpbr run` | Run benchmark evaluation with configured MCP server |
| `mcpbr init` | Generate an example configuration file |
| `mcpbr config` | Manage configuration templates |
| `mcpbr models` | List supported models for evaluation |
| `mcpbr providers` | List available model providers |
| `mcpbr harnesses` | List available agent harnesses |
| `mcpbr benchmarks` | List available benchmarks (SWE-bench, CyberGym) |
| `mcpbr cleanup` | Remove orphaned mcpbr Docker resources (containers, volumes, networks) |

---

## `mcpbr run`

Run SWE-bench evaluation with the configured MCP server.

### Usage

```bash
mcpbr run -c CONFIG [OPTIONS]
```

### Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--config PATH` | `-c` | Required | Path to YAML configuration file |
| `--model TEXT` | `-m` | String | Override model from config |
| `--provider TEXT` | `-p` | Choice | Override provider from config |
| `--harness TEXT` | | Choice | Override agent harness from config |
| `--benchmark TEXT` | `-b` | Choice | Override benchmark from config (`swe-bench` or `cybergym`) |
| `--level INTEGER` | | Integer | Override CyberGym difficulty level (0-3) |
| `--sample INTEGER` | `-n` | Integer | Override sample size from config |
| `--mcp-only` | `-M` | Flag | Run only MCP evaluation (skip baseline) |
| `--baseline-only` | `-B` | Flag | Run only baseline evaluation (skip MCP) |
| `--no-prebuilt` | | Flag | Disable pre-built SWE-bench images |
| `--output PATH` | `-o` | Path | Path to save JSON results |
| `--report PATH` | `-r` | Path | Path to save Markdown report |
| `--output-yaml PATH` | `-y` | Path | Path to save YAML results |
| `--verbose` | `-v` | Count | Verbose output (`-v` summary, `-vv` detailed) |
| `--log-file PATH` | `-l` | Path | Path to write raw JSON log output (single file) |
| `--log-dir PATH` | | Path | Directory to write per-instance JSON log files |
| `--task TEXT` | `-t` | String | Run specific task(s) by instance_id (repeatable) |
| `--prompt TEXT` | | String | Override agent prompt (use `{problem_statement}` placeholder) |
| `--filter-difficulty TEXT` | | String | Filter benchmarks by difficulty (repeatable) |
| `--filter-category TEXT` | | String | Filter benchmarks by category (repeatable) |
| `--filter-tags TEXT` | | String | Filter benchmarks by tags (repeatable) |
| `--help` | `-h` | Flag | Show help message |

### Examples

#### Basic Evaluation

```bash
# Full evaluation (MCP + baseline)
mcpbr run -c config.yaml

# With verbose output
mcpbr run -c config.yaml -v

# Very verbose (detailed tool calls)
mcpbr run -c config.yaml -vv
```

#### Selective Runs

```bash
# Run only MCP evaluation
mcpbr run -c config.yaml -M

# Run only baseline evaluation
mcpbr run -c config.yaml -B

# Run specific tasks
mcpbr run -c config.yaml -t astropy__astropy-12907 -t django__django-11099
```

#### Override Config Values

```bash
# Override model (use alias or full name)
mcpbr run -c config.yaml -m opus

# Override sample size
mcpbr run -c config.yaml -n 50

# Override benchmark
mcpbr run -c config.yaml --benchmark cybergym

# Run CyberGym with specific level
mcpbr run -c config.yaml --benchmark cybergym --level 3

# Override prompt
mcpbr run -c config.yaml --prompt "Fix this bug: {problem_statement}"
```

#### Filter Benchmarks

```bash
# Filter by difficulty (CyberGym levels or MCPToolBench complexity)
mcpbr run -c config.yaml --filter-difficulty easy --filter-difficulty medium

# Filter by category (MCPToolBench categories or SWE-bench repos)
mcpbr run -c config.yaml --filter-category browser --filter-category finance

# Filter by multiple criteria
mcpbr run -c config.yaml \
  --filter-difficulty hard \
  --filter-category security

# CyberGym with difficulty filtering
mcpbr run -c config.yaml --benchmark cybergym \
  --filter-difficulty 2 --filter-difficulty 3
```

#### Save Results

```bash
# Save JSON results
mcpbr run -c config.yaml -o results.json

# Save YAML results
mcpbr run -c config.yaml -y results.yaml

# Save Markdown report
mcpbr run -c config.yaml -r report.md

# Save all formats
mcpbr run -c config.yaml -o results.json -y results.yaml -r report.md

# Per-instance logs
mcpbr run -c config.yaml -v --log-dir logs/
```

---

## `mcpbr init`

Generate an example configuration file.

### Usage

```bash
mcpbr init [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output PATH` | `-o` | Path | `mcpbr.yaml` | Path to write example config |
| `--template TEXT` | `-t` | String | | Template ID to use (see `mcpbr config list`) |
| `--interactive` | `-i` | Flag | | Interactive template selection wizard |
| `--help` | `-h` | Flag | | Show help message |

### Examples

```bash
# Create default config
mcpbr init

# Use a template
mcpbr init -t filesystem

# Interactive template selection
mcpbr init -i

# Custom filename with template
mcpbr init -t brave-search -o brave.yaml
```

---

## `mcpbr config`

Manage configuration templates for popular MCP servers.

### Subcommands

| Command | Description |
|---------|-------------|
| `mcpbr config list` | List available configuration templates |
| `mcpbr config apply` | Apply a template to create a configuration file |

---

### `mcpbr config list`

List all available MCP server configuration templates.

#### Usage

```bash
mcpbr config list
```

#### Output

```text
                   Available MCP Server Templates
+-------------+------------------+---------------------+----------+-------------+
| ID          | Name             | Package             | API Key  | Description |
+-------------+------------------+---------------------+----------+-------------+
| filesystem  | Filesystem       | @modelcontext...    | No       | File system |
|             | Server           |                     |          | access      |
| brave-      | Brave Search     | @modelcontext...    | Yes      | Web search  |
| search      |                  |                     |          | using Brave |
| github      | GitHub           | @modelcontext...    | Yes      | GitHub API  |
|             |                  |                     |          | integration |
+-------------+------------------+---------------------+----------+-------------+
```

---

### `mcpbr config apply`

Apply a template to create a configuration file.

#### Usage

```bash
mcpbr config apply TEMPLATE_ID [OPTIONS]
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `TEMPLATE_ID` | ID of the template to apply (see `mcpbr config list`) |

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output PATH` | `-o` | Path | `mcpbr.yaml` | Path to write configuration file |
| `--force` | `-f` | Flag | | Overwrite existing configuration file |
| `--help` | `-h` | Flag | | Show help message |

#### Examples

```bash
# Apply filesystem template
mcpbr config apply filesystem

# Custom output path
mcpbr config apply brave-search -o brave.yaml

# Overwrite existing config
mcpbr config apply github --force
```

---

## `mcpbr models`

List supported Anthropic models for evaluation.

### Usage

```bash
mcpbr models
```

### Output

```text
                   Supported Anthropic Models
+----------------------------+------------------------+---------+
| Model ID                   | Display Name           | Context |
+----------------------------+------------------------+---------+
| claude-opus-4-5-20251101   | Claude Opus 4.5        | 200,000 |
| claude-sonnet-4-5-20250929 | Claude Sonnet 4.5      | 200,000 |
| claude-haiku-4-5-20251001  | Claude Haiku 4.5       | 200,000 |
| opus                       | Claude Opus (alias)    | 200,000 |
| sonnet                     | Claude Sonnet (alias)  | 200,000 |
| haiku                      | Claude Haiku (alias)   | 200,000 |
+----------------------------+------------------------+---------+
```

---

## `mcpbr providers`

List available model providers.

### Usage

```bash
mcpbr providers
```

### Output

```text
Available Model Providers

+----------+-------------------+---------------------+
| Provider | Env Variable      | Description         |
+----------+-------------------+---------------------+
| anthropic| ANTHROPIC_API_KEY | Direct Anthropic API|
+----------+-------------------+---------------------+
```

---

## `mcpbr harnesses`

List available agent harnesses.

### Usage

```bash
mcpbr harnesses
```

### Output

```text
Available Agent Harnesses

claude-code (default)
  Shells out to Claude Code CLI with MCP server support
  Requires: claude CLI installed
```

---

## `mcpbr benchmarks`

List available benchmarks with their characteristics.

### Usage

```bash
mcpbr benchmarks
```

### Output

```text
Available Benchmarks

┌────────────┬──────────────────────────────────────────────────────────┬─────────────────────────┐
│ Benchmark  │ Description                                              │ Output Type             │
├────────────┼──────────────────────────────────────────────────────────┼─────────────────────────┤
│ swe-bench  │ Software bug fixes in GitHub repositories                │ Patch (unified diff)    │
│ cybergym   │ Security vulnerability exploitation (PoC generation)     │ Exploit code            │
└────────────┴──────────────────────────────────────────────────────────┴─────────────────────────┘

Use --benchmark flag with 'run' command to select a benchmark
Example: mcpbr run -c config.yaml --benchmark cybergym --level 2
```

See the [Benchmarks guide](benchmarks.md) for detailed information about each benchmark.

---

## `mcpbr cleanup`

Remove orphaned mcpbr Docker resources (containers, volumes, networks) that were not properly cleaned up.

This command helps prevent resource leaks when evaluations fail or are interrupted. By default, it only removes resources older than 24 hours to avoid removing resources from currently running evaluations.

### Usage

```bash
mcpbr cleanup [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--dry-run` | | Flag | False | Show resources that would be removed without removing them |
| `--force` | `-f` | Flag | False | Force removal without confirmation and ignore retention policy |
| `--retention-hours N` | | Integer | 24 | Only remove resources older than N hours |
| `--containers-only` | | Flag | False | Only clean up containers (skip volumes and networks) |
| `--volumes-only` | | Flag | False | Only clean up volumes (skip containers and networks) |
| `--networks-only` | | Flag | False | Only clean up networks (skip containers and volumes) |
| `--help` | `-h` | Flag | | Show help message |

### Behavior

- **Default**: Removes resources older than 24 hours with confirmation prompt
- **--force**: Removes all resources immediately without confirmation
- **--retention-hours**: Customize the age threshold for automatic cleanup
- **--dry-run**: Shows what would be removed without making changes
- **Resource types**: Cleans containers, volumes, and networks by default

### Examples

```bash
# Preview all resources that would be removed (24h+ old)
mcpbr cleanup --dry-run

# Remove resources with confirmation prompt
mcpbr cleanup

# Force remove all resources immediately
mcpbr cleanup -f

# Only remove resources older than 48 hours
mcpbr cleanup --retention-hours 48

# Remove only containers
mcpbr cleanup --containers-only

# Remove only volumes (useful after many failed runs)
mcpbr cleanup --volumes-only

# Preview with custom retention period
mcpbr cleanup --dry-run --retention-hours 12
```

### Resource Tracking

mcpbr tracks Docker resources using labels:

- `mcpbr=true` - Identifies resources created by mcpbr
- `mcpbr.instance` - Links to specific benchmark task
- `mcpbr.session` - Groups resources from same evaluation run
- `mcpbr.timestamp` - Creation time for retention policy

### When to Use Cleanup

Run cleanup when you:

- Have crashed or interrupted evaluations
- See "container already exists" errors
- Want to free up disk space
- Are switching between different evaluation configurations
- Need to ensure a clean slate before running new evaluations

### Safety Features

- **Retention policy**: Prevents accidental removal of running evaluations
- **Confirmation prompt**: Asks before removing resources (unless --force)
- **Dry run**: Preview mode to verify what will be removed
- **Selective cleanup**: Target specific resource types
- **Error reporting**: Shows which resources failed to clean up

### Output Example

```text
Found orphaned mcpbr resources:

  Containers (3):
    - mcpbr-abc123-astropy__astropy-12907
    - mcpbr-def456-django__django-11099
    - mcpbr-ghi789-sympy__sympy-18199

  Volumes (2):
    - mcpbr-volume-abc123
    - mcpbr-volume-def456

  Networks (1):
    - mcpbr-network-abc123

Total: 6 resource(s)

Remove these resources? [Y/n]:
```

---

## Exit Codes

mcpbr uses specific exit codes to indicate different outcomes, making it easier to integrate with scripts and CI/CD pipelines.

| Code | Meaning | When to Use |
|------|---------|-------------|
| 0 | Success | At least one task was resolved successfully |
| 1 | Fatal error | Config invalid, Docker unavailable, API error, crash, or regression threshold exceeded |
| 2 | No resolutions | Evaluation ran but no tasks were resolved (0% success) |
| 3 | Nothing evaluated | All tasks were cached/skipped, none actually ran |
| 130 | Interrupted by user | Evaluation interrupted by Ctrl+C |

### Exit Code Examples

```bash
# Check exit code after evaluation
mcpbr run -c config.yaml
echo $?  # 0 = success, 1 = error, 2 = no resolutions, 3 = all cached

# Use in scripts
if mcpbr run -c config.yaml; then
    echo "Evaluation successful"
else
    exit_code=$?
    case $exit_code in
        1) echo "Fatal error occurred" ;;
        2) echo "No tasks resolved" ;;
        3) echo "All tasks cached, use --reset-state to re-run" ;;
        130) echo "Interrupted by user" ;;
    esac
fi

# CI/CD integration
mcpbr run -c config.yaml
if [ $? -eq 3 ]; then
    echo "Results cached, re-running with --reset-state"
    mcpbr run -c config.yaml --reset-state
fi
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude models |

## Next Steps

- [Configuration](configuration.md) - Full configuration reference
- [Evaluation Results](evaluation-results.md) - Understanding output formats
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
