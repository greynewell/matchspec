# Side-by-Side MCP Server Comparison

Compare two MCP servers head-to-head in a single evaluation run to understand which implementation performs better on your benchmark tasks.

## Overview

Comparison mode enables A/B testing of MCP servers by running the same tasks against two different server implementations simultaneously. This is useful for:

- **Evaluating implementation alternatives**: Compare different MCP server architectures
- **Testing optimizations**: Measure the impact of performance improvements
- **Benchmarking tools**: Compare your MCP server against reference implementations
- **Research**: Conduct controlled experiments on MCP server design decisions

## Quick Start

### 1. Create a Comparison Configuration

Create a YAML config file (e.g., `comparison.yaml`):

```yaml
comparison_mode: true

mcp_server_a:
  name: "Task Queries"
  command: node
  args: [build/index.js]
  cwd: /path/to/task-queries-server

mcp_server_b:
  name: "Edge Identity"
  command: node
  args: [build/index.js]
  cwd: /path/to/edge-identity-server

benchmark: swe-bench-lite
sample_size: 10
timeout_seconds: 300
max_iterations: 10
```

### 2. Run the Comparison

```bash
mcpbr run -c comparison.yaml -o results.json
```

### 3. View Results

The output will show:

```text
Side-by-Side MCP Server Comparison

┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric            ┃ Task Queries ┃ Edge Identity┃ Δ (A - B)┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Resolved Tasks    │ 4/10         │ 2/10         │ +2       │
│ Resolution Rate   │ 40.0%        │ 20.0%        │ +100.0%  │
└───────────────────┴──────────────┴──────────────┴──────────┘

Per-Task Results
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Instance ID ┃ Task Queries ┃ Edge Identity┃ Winner       ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ task-1      │ PASS         │ FAIL         │ Task Queries │
│ task-2      │ PASS         │ FAIL         │ Task Queries │
│ task-3      │ PASS         │ PASS         │ Both         │
└─────────────┴──────────────┴──────────────┴──────────────┘

✓ Task Queries unique wins: 2 tasks
  - task-1
  - task-2
```

## Configuration

### Required Fields

When `comparison_mode: true`, you must provide:

- `mcp_server_a`: Configuration for the first MCP server
- `mcp_server_b`: Configuration for the second MCP server

Both servers support the same configuration options as the standard `mcp_server` field:

```yaml
mcp_server_a:
  name: "Server Name"           # Human-readable name (appears in reports)
  command: "npx"                 # Command to start the server
  args: ["-y", "package-name"]   # Command arguments
  env:                           # Environment variables (optional)
    API_KEY: "${API_KEY}"
  cwd: "/path/to/server"         # Working directory (optional)
  startup_timeout_ms: 60000      # Server startup timeout (optional)
  tool_timeout_ms: 900000        # Tool call timeout (optional)
```

### Complete Example

```yaml
# Enable comparison mode
comparison_mode: true

# First MCP server
mcp_server_a:
  name: "Optimized Server"
  command: node
  args: [dist/server.js]
  cwd: /Users/me/projects/optimized-mcp
  env:
    LOG_LEVEL: debug
    CACHE_ENABLED: "true"

# Second MCP server
mcp_server_b:
  name: "Baseline Server"
  command: node
  args: [dist/server.js]
  cwd: /Users/me/projects/baseline-mcp
  env:
    LOG_LEVEL: debug
    CACHE_ENABLED: "false"

# Model and provider (shared by both servers)
provider: anthropic
model: claude-sonnet-4-20250514

# Benchmark settings
benchmark: swe-bench-verified
sample_size: 50
timeout_seconds: 600
max_iterations: 15
```

## Output Format

### JSON Results

The results JSON includes comparison-specific fields:

```json
{
  "metadata": {
    "timestamp": "2026-01-30T10:00:00Z",
    "config": {
      "comparison_mode": true,
      ...
    },
    "mcp_server_a": {
      "name": "Task Queries",
      "command": "node",
      "args": ["build/index.js"]
    },
    "mcp_server_b": {
      "name": "Edge Identity",
      "command": "node",
      "args": ["build/index.js"]
    }
  },
  "summary": {
    "mcp_server_a": {
      "name": "Task Queries",
      "resolved": 4,
      "total": 10,
      "resolution_rate": 0.4,
      "cost": 0.50,
      "tool_calls": 125
    },
    "mcp_server_b": {
      "name": "Edge Identity",
      "resolved": 2,
      "total": 10,
      "resolution_rate": 0.2,
      "cost": 0.45,
      "tool_calls": 98
    },
    "comparison": {
      "a_vs_b_delta": 2,
      "a_vs_b_improvement_pct": 100.0,
      "a_unique_wins": ["task-1", "task-2"],
      "b_unique_wins": [],
      "both_wins": ["task-3"],
      "both_fail": ["task-4", "task-5", ...]
    }
  },
  "tasks": [
    {
      "instance_id": "task-1",
      "mcp_server_a": {
        "resolved": true,
        "patch_generated": true,
        "cost": 0.05,
        ...
      },
      "mcp_server_b": {
        "resolved": false,
        "patch_generated": false,
        "cost": 0.04,
        ...
      }
    },
    ...
  ]
}
```

### Understanding the Metrics

- **Resolution Rate**: Percentage of tasks successfully resolved by each server
- **Δ (A - B)**: Difference in resolved tasks (positive means A is better)
- **Improvement %**: Percentage improvement of A over B
- **Unique Wins**: Tasks where only one server succeeded
- **Both Wins**: Tasks where both servers succeeded
- **Both Fail**: Tasks where both servers failed

## Use Cases

### Comparing MCP Tools

Test which tool implementations work best for your use case:

```yaml
comparison_mode: true

mcp_server_a:
  name: "Filesystem Tools"
  command: npx
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

mcp_server_b:
  name: "Git Tools"
  command: npx
  args: ["-y", "@modelcontextprotocol/server-git", "{workdir}"]

benchmark: swe-bench-lite
sample_size: 20
```

### Performance Optimization

Measure the impact of caching, indexing, or other optimizations:

```yaml
comparison_mode: true

mcp_server_a:
  name: "With Cache"
  command: node
  args: [server.js]
  env:
    ENABLE_CACHE: "true"

mcp_server_b:
  name: "Without Cache"
  command: node
  args: [server.js]
  env:
    ENABLE_CACHE: "false"
```

### Version Comparison

Compare different versions of the same server:

```yaml
comparison_mode: true

mcp_server_a:
  name: "v2.0"
  command: node
  args: [server.js]
  cwd: /path/to/v2.0

mcp_server_b:
  name: "v1.5"
  command: node
  args: [server.js]
  cwd: /path/to/v1.5
```

## Limitations

### Resource Usage

- **2x Execution Time**: Each task runs twice (once per server)
- **2x API Costs**: Both servers make independent API calls
- **2x Compute**: Both servers run sequentially (no parallel execution)

### Budget Tracking

When using `budget` parameter, costs from both servers count toward the limit:

```yaml
comparison_mode: true
budget: 10.00  # Shared budget for both servers
```

### Baseline Evaluation

Comparison mode is compatible with baseline evaluation:

```bash
# Run both servers + baseline
mcpbr run -c comparison.yaml

# Run only comparison (skip baseline)
mcpbr run -c comparison.yaml -M
```

## Best Practices

### 1. Use Meaningful Names

Choose descriptive names that clearly identify what's being compared:

```yaml
mcp_server_a:
  name: "GPT-4 Index"  # Good: specific and clear

mcp_server_b:
  name: "Server B"     # Bad: generic
```

### 2. Start Small

Begin with a small sample size to verify your configuration:

```yaml
comparison_mode: true
sample_size: 5  # Start with 5 tasks
```

Then scale up once you've validated the setup.

### 3. Control Variables

Change only one thing at a time for meaningful comparisons:

```yaml
# Good: Only caching differs
mcp_server_a:
  command: node
  args: [server.js]
  env: {CACHE: "on"}

mcp_server_b:
  command: node
  args: [server.js]
  env: {CACHE: "off"}

# Bad: Multiple differences (harder to interpret)
mcp_server_a:
  command: python
  args: [new_server.py]
  env: {CACHE: "on", LOG_LEVEL: "debug"}

mcp_server_b:
  command: node
  args: [old_server.js]
  env: {CACHE: "off", LOG_LEVEL: "info"}
```

### 4. Run Multiple Trials

For statistical confidence, run multiple evaluations:

```bash
for i in {1..5}; do
  mcpbr run -c comparison.yaml --trial-mode -o trial_${i}.json
done
```

## Backward Compatibility

Comparison mode is fully backward compatible. Existing single-server configurations continue to work:

```yaml
# Old config (still works)
mcp_server:
  command: npx
  args: ["-y", "server"]

# New config (comparison mode)
comparison_mode: true
mcp_server_a:
  command: npx
  args: ["-y", "server-a"]
mcp_server_b:
  command: npx
  args: ["-y", "server-b"]
```

## Troubleshooting

### "requires both mcp_server_a and mcp_server_b"

You enabled `comparison_mode: true` but only provided one server. Both servers are required.

### "use mcp_server_a/b instead of mcp_server"

You enabled comparison mode but also provided the legacy `mcp_server` field. Remove it:

```yaml
comparison_mode: true
# mcp_server: ...  # Remove this
mcp_server_a: ...
mcp_server_b: ...
```

### "mcp_server_a/b only valid in comparison_mode"

You provided comparison servers but didn't enable comparison mode:

```yaml
comparison_mode: true  # Add this
mcp_server_a: ...
mcp_server_b: ...
```

## Examples

See the [examples/comparison/](../examples/comparison/) directory for complete working examples.
