---
faq:
  - q: "What commands are available in mcpbr?"
    a: "mcpbr provides six commands: run (execute evaluations), init (generate config), models (list supported models), providers (list LLM providers), harnesses (list agent backends), and cleanup (remove orphaned Docker containers)."
  - q: "How do I run only the MCP agent without the baseline?"
    a: "Use the --mcp-only or -M flag: 'mcpbr run -c config.yaml -M'. This skips the baseline evaluation and only runs the MCP-enabled agent."
  - q: "How do I run a specific SWE-bench task?"
    a: "Use the --task or -t flag with the instance_id: 'mcpbr run -c config.yaml -t astropy__astropy-12907'. You can repeat this flag to run multiple specific tasks."
  - q: "How do I save mcpbr results to a file?"
    a: "Use --output (-o) for JSON results and --report (-r) for a Markdown report: 'mcpbr run -c config.yaml -o results.json -r report.md'."
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
| `mcpbr models` | List supported models for evaluation |
| `mcpbr providers` | List available model providers |
| `mcpbr harnesses` | List available agent harnesses |
| `mcpbr benchmarks` | List available benchmarks (SWE-bench, CyberGym) |
| `mcpbr cleanup` | Remove orphaned mcpbr Docker containers |

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
| `--verbose` | `-v` | Count | Verbose output (`-v` summary, `-vv` detailed) |
| `--log-file PATH` | `-l` | Path | Path to write raw JSON log output (single file) |
| `--log-dir PATH` | | Path | Directory to write per-instance JSON log files |
| `--task TEXT` | `-t` | String | Run specific task(s) by instance_id (repeatable) |
| `--prompt TEXT` | | String | Override agent prompt (use `{problem_statement}` placeholder) |
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

#### Save Results

```bash
# Save JSON results
mcpbr run -c config.yaml -o results.json

# Save Markdown report
mcpbr run -c config.yaml -r report.md

# Both
mcpbr run -c config.yaml -o results.json -r report.md

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
| `--help` | `-h` | Flag | | Show help message |

### Examples

```bash
# Create default config
mcpbr init

# Custom filename
mcpbr init -o my-config.yaml
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

Remove orphaned mcpbr Docker containers that were not properly cleaned up.

### Usage

```bash
mcpbr cleanup [OPTIONS]
```

### Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--dry-run` | | Flag | Show containers that would be removed without removing them |
| `--force` | `-f` | Flag | Skip confirmation prompt |
| `--help` | `-h` | Flag | Show help message |

### Examples

```bash
# Preview containers to remove
mcpbr cleanup --dry-run

# Remove with confirmation prompt
mcpbr cleanup

# Remove without confirmation
mcpbr cleanup -f
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (configuration, API, etc.) |
| 130 | Interrupted by user (Ctrl+C) |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude models |

## Next Steps

- [Configuration](configuration.md) - Full configuration reference
- [Evaluation Results](evaluation-results.md) - Understanding output formats
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
