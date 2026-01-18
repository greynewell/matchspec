---
faq:
  - q: "How do I interpret mcpbr evaluation results?"
    a: "mcpbr reports resolution rates for MCP and baseline agents, where 'resolved' means the generated patch passes all required tests. The improvement percentage shows how much better the MCP agent performed relative to the baseline."
  - q: "What does 'resolved' mean in mcpbr results?"
    a: "A task is 'resolved' when the agent's patch passes all FAIL_TO_PASS tests (the tests that should pass after the fix) and all PASS_TO_PASS tests (regression tests that should continue passing)."
  - q: "What output formats does mcpbr support?"
    a: "mcpbr supports console output with summary tables, JSON output (--output flag) with full structured data, Markdown reports (--report flag), and per-instance JSON logs (--log-dir flag)."
  - q: "How do I analyze mcpbr results?"
    a: "Use the JSON output for programmatic analysis. Key fields include summary.mcp.rate, summary.baseline.rate, and per-task results with patch_generated, resolved, tokens, iterations, and tool_usage data."
---

# Understanding Evaluation Results

This guide explains how to interpret and analyze mcpbr evaluation results.

## Console Output

When running an evaluation, mcpbr displays real-time progress and a final summary.

### Verbose Mode (`-v`)

```text
mcpbr Evaluation
  Config: config.yaml
  Provider: anthropic
  Model: sonnet
  Agent Harness: claude-code
  Dataset: SWE-bench/SWE-bench_Lite
  Sample size: 10
  Run MCP: True, Run Baseline: True
  Pre-built images: True
  Log dir: my-logs

Loading dataset: SWE-bench/SWE-bench_Lite
Evaluating 10 tasks
Provider: anthropic, Harness: claude-code
14:23:15 [MCP] Starting mcp run for astropy-12907:mcp
14:23:22 astropy-12907:mcp    > TodoWrite
14:23:22 astropy-12907:mcp    < Todos have been modified successfully...
14:23:26 astropy-12907:mcp    > Glob
14:23:26 astropy-12907:mcp    > Grep
14:23:27 astropy-12907:mcp    < $WORKDIR/astropy/modeling/separable.py
14:27:43 astropy-12907:mcp    * done turns=31 tokens=115/6,542
```

Legend:

- `>` Tool call started
- `<` Tool result received
- `*` Run completed

### Summary Table

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

Per-Task Results
+------------------------+------+----------+-------+
| Instance ID            | MCP  | Baseline | Error |
+------------------------+------+----------+-------+
| astropy__astropy-12907 | PASS |   PASS   |       |
| django__django-11099   | PASS |   FAIL   |       |
| sympy__sympy-18087     | FAIL |   FAIL   |       |
+------------------------+------+----------+-------+
```

## What "Resolved" Means

A task is considered **resolved** when:

1. **Patch Generated**: The agent produced a non-empty diff
2. **Patch Applied**: The diff applies cleanly to the repository
3. **FAIL_TO_PASS Tests Pass**: Tests that were failing now pass
4. **PASS_TO_PASS Tests Pass**: Existing tests still pass (no regressions)

## JSON Output

Save structured results with `--output`:

```bash
mcpbr run -c config.yaml -o results.json
```

### Schema

```json
{
  "metadata": {
    "timestamp": "2026-01-17T07:23:39.871437+00:00",
    "config": {
      "model": "sonnet",
      "provider": "anthropic",
      "agent_harness": "claude-code",
      "dataset": "SWE-bench/SWE-bench_Lite",
      "sample_size": 25,
      "timeout_seconds": 600,
      "max_iterations": 30
    },
    "mcp_server": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
    }
  },
  "summary": {
    "mcp": {
      "resolved": 8,
      "total": 25,
      "rate": 0.32
    },
    "baseline": {
      "resolved": 5,
      "total": 25,
      "rate": 0.20
    },
    "improvement": "+60.0%"
  },
  "tasks": [...]
}
```

### Per-Task Results

Each task includes detailed metrics:

```json
{
  "instance_id": "astropy__astropy-12907",
  "mcp": {
    "patch_generated": true,
    "tokens": {
      "input": 115,
      "output": 6542
    },
    "iterations": 30,
    "tool_calls": 72,
    "tool_usage": {
      "TodoWrite": 4,
      "Task": 1,
      "Glob": 4,
      "Grep": 11,
      "Bash": 27,
      "Read": 22,
      "Write": 2,
      "Edit": 1
    },
    "resolved": true,
    "patch_applied": true,
    "fail_to_pass": {
      "passed": 2,
      "total": 2
    },
    "pass_to_pass": {
      "passed": 10,
      "total": 10
    }
  },
  "baseline": {
    "patch_generated": true,
    "tokens": {
      "input": 63,
      "output": 7615
    },
    "iterations": 30,
    "tool_calls": 57,
    "resolved": true,
    "patch_applied": true
  }
}
```

### Key Metrics

| Field | Description |
|-------|-------------|
| `patch_generated` | Whether the agent produced a diff |
| `patch_applied` | Whether the diff applied cleanly |
| `resolved` | Whether all tests pass |
| `tokens.input` | Input tokens consumed |
| `tokens.output` | Output tokens generated |
| `iterations` | Number of agent turns |
| `tool_calls` | Total tool invocations |
| `tool_usage` | Breakdown by tool name |
| `fail_to_pass` | Tests that should now pass |
| `pass_to_pass` | Regression tests |
| `error` | Error message if failed |

## Markdown Report

Generate a human-readable report with `--report`:

```bash
mcpbr run -c config.yaml -r report.md
```

The report includes:

- Summary statistics
- Per-task results table
- Analysis of which tasks each agent solved

## Per-Instance Logs

For detailed debugging, use `--log-dir`:

```bash
mcpbr run -c config.yaml -v --log-dir logs/
```

This creates timestamped JSON files:

```text
logs/
  astropy__astropy-12907_mcp_20260117_143052.json
  astropy__astropy-12907_baseline_20260117_143156.json
  django__django-11099_mcp_20260117_144023.json
  ...
```

### Log File Contents

```json
{
  "instance_id": "astropy__astropy-12907",
  "run_type": "mcp",
  "events": [
    {
      "type": "system",
      "subtype": "init",
      "cwd": "/workspace",
      "tools": ["Task", "Bash", "Glob", "Grep", "Read", "Edit", "Write"],
      "model": "claude-sonnet-4-5-20250929"
    },
    {
      "type": "assistant",
      "message": {
        "content": [
          {"type": "text", "text": "I'll help you fix this bug..."}
        ]
      }
    },
    {
      "type": "assistant",
      "message": {
        "content": [
          {"type": "tool_use", "name": "Grep", "input": {"pattern": "separability"}}
        ]
      }
    },
    {
      "type": "result",
      "num_turns": 31,
      "usage": {"input_tokens": 115, "output_tokens": 6542}
    }
  ]
}
```

## Analyzing Results

### Improvement Calculation

```
improvement = ((mcp_rate - baseline_rate) / baseline_rate) * 100
```

Example: If MCP resolves 32% and baseline resolves 20%:

```
improvement = ((0.32 - 0.20) / 0.20) * 100 = +60%
```

### Comparing Configurations

To compare different MCP servers or settings:

```python
import json

with open("results-server-a.json") as f:
    a = json.load(f)

with open("results-server-b.json") as f:
    b = json.load(f)

print(f"Server A: {a['summary']['mcp']['rate']:.1%}")
print(f"Server B: {b['summary']['mcp']['rate']:.1%}")
```

### Finding Interesting Tasks

Identify tasks where MCP helped but baseline failed:

```python
mcp_only_wins = []
for task in results["tasks"]:
    mcp_resolved = task.get("mcp", {}).get("resolved", False)
    baseline_resolved = task.get("baseline", {}).get("resolved", False)
    if mcp_resolved and not baseline_resolved:
        mcp_only_wins.append(task["instance_id"])

print("MCP solved, baseline failed:", mcp_only_wins)
```

### Tool Usage Analysis

Understand which tools are most used:

```python
from collections import Counter

tool_counts = Counter()
for task in results["tasks"]:
    usage = task.get("mcp", {}).get("tool_usage", {})
    tool_counts.update(usage)

print("Most used tools:", tool_counts.most_common(10))
```

## Common Patterns

### High Resolution Rate

If MCP significantly outperforms baseline:

- Your MCP tools provide valuable functionality
- Consider which specific tools drove the improvement

### Low Resolution Rate (Both)

If neither agent performs well:

- Tasks may be inherently difficult
- Consider increasing `timeout_seconds` and `max_iterations`
- Review per-instance logs for common failure modes

### Similar Rates

If MCP and baseline have similar rates:

- MCP tools may not provide additional value for these tasks
- Built-in tools may be sufficient
- Review tool usage to see if MCP tools are being used

## Next Steps

- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [Architecture](architecture.md) - How evaluation works internally
- [MCP Integration](mcp-integration.md) - Optimize your MCP server
