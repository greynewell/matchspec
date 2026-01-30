# Dead Code Detection Benchmark

A benchmark for evaluating AI agents' ability to identify unused code in software projects.

## Overview

This benchmark tests whether agents can accurately find "dead code" - functions, classes, and variables that are defined but never called or used. It compares two approaches:

1. **Baseline (grep/search)**: Agent uses file reading and text search to find definitions and usages
2. **Supermodel MCP (call graph)**: Agent uses the Supermodel API to generate call graphs for precise analysis

## Hypothesis

From [supermodeltools/mcp#85](https://github.com/supermodeltools/mcp/issues/85):

> An agent using call graphs and dependency graphs will find dead code more accurately and efficiently than an agent using grep/search alone.

## Running the Benchmark

### Prerequisites

```bash
# Install mcpbr
pip install -e ".[dev]"

# Set environment variables
export ANTHROPIC_API_KEY=your-key
export SUPERMODEL_API_KEY=your-supermodel-key
export SUPERMODEL_BASE_URL=https://staging.api.supermodeltools.com  # for staging
```

### Run Baseline (grep approach)

```bash
mcpbr run --config config/deadcode-baseline.yaml -n 3 -v
```

### Run with Supermodel (call graph approach)

```bash
mcpbr run --config config/deadcode-supermodel.yaml -n 3 -v
```

## Benchmark Tasks

The benchmark includes 3 synthetic tasks with known ground truth:

| Task ID | Language | Difficulty | Dead Code | Alive Code |
|---------|----------|------------|-----------|------------|
| dead-code-001 | TypeScript | easy | 3 functions | 3 functions |
| dead-code-002 | Python | medium | 2 functions + 1 class | 3 functions |
| dead-code-003 | JavaScript | hard | 5 functions | 4 functions |

### Task Structure

Each task includes:
- Source files with intentional dead code
- A `REPORT.json` file for the agent to update with findings
- Ground truth annotations for evaluation

### Evaluation Metrics

- **Precision**: % of reported dead code that is actually dead
- **Recall**: % of actual dead code that was found
- **F1 Score**: Harmonic mean of precision and recall
- **Resolved**: True if precision ≥ 80% AND recall ≥ 80%

## Pre-Generated Call Graphs

Each benchmark task includes a pre-generated call graph at `.supermodel/graph.json`. This implements the concept from [supermodeltools/mcp#82](https://github.com/supermodeltools/mcp/issues/82) - providing local graph data to avoid burning agent iterations on API calls.

The graph structure includes:
- **nodes**: All functions/classes with metadata (file, name, line, type, exported)
- **edges**: Call relationships between nodes
- **entry_points**: Exported functions and module entry points

The agent can read this file directly to determine which nodes have no incoming edges (potential dead code) vs which are reachable from entry points (alive code).

## Results

### With Pre-Generated Call Graphs (2026-01-30)

| Task | Call Graph Approach | Baseline (grep) |
|------|---------------------|-----------------|
| dead-code-001 (TS) | ✅ PASS (12 iter) | ✅ PASS (11 iter) |
| dead-code-002 (Python) | ✅ PASS (13 iter) | ✅ PASS (9 iter) |
| dead-code-003 (JS) | ✅ PASS (12 iter) | ✅ PASS (10 iter) |

**Summary:**
- Both approaches achieved 100% pass rate on synthetic tasks
- Call graph approach: avg 12.3 iterations, $0.16/task
- Baseline approach: avg 10.0 iterations, $0.15/task

On simple synthetic tasks, both approaches work equally well. The call graph approach provides more value on larger, complex codebases where:
1. Grep-based search produces false positives/negatives
2. Call chains involve indirect dependencies
3. Dynamic dispatch makes static analysis difficult

### Tool Usage

Call graph agent read `.supermodel/graph.json` directly, eliminating the need for API calls during the benchmark.

## Configuration Files

### deadcode-baseline.yaml

Uses `@modelcontextprotocol/server-filesystem` MCP for file operations. Agent must use grep/search to find dead code.

### deadcode-supermodel.yaml

Uses `@supermodeltools/mcp-server` MCP for call graph analysis. Agent can query the Supermodel API for precise call relationships.

## Extending the Benchmark

### Adding New Tasks

Edit `src/mcpbr/benchmarks/deadcode.py` and add to `_generate_synthetic_tasks()`:

```python
{
    "instance_id": "dead-code-004",
    "language": "rust",
    "difficulty": "hard",
    "repo_content": {
        "REPORT.json": REPORT_PLACEHOLDER,
        "src/main.rs": "...",
    },
    "dead_code": [
        {"file": "src/main.rs", "name": "unused_fn", "line": 10, "type": "function"},
    ],
    "alive_code": [
        {"file": "src/main.rs", "name": "main", "line": 1, "type": "function"},
    ],
}
```

### Using Real Repositories

Create a JSON dataset file:

```json
[
  {
    "instance_id": "real-repo-001",
    "language": "python",
    "repo_url": "https://github.com/example/repo",
    "commit": "abc123",
    "dead_code": [...],
    "alive_code": [...]
  }
]
```

Then reference it in the config:

```yaml
benchmark: "dead-code"
dataset: "/path/to/dataset.json"
```

## Future Work

1. **Larger codebases**: Test on real-world repos where grep would produce false positives
2. **Indirect dependencies**: Cases where call chains are complex
3. **Dynamic dispatch**: Languages with runtime polymorphism
4. **Cross-module analysis**: Dead code across package boundaries

## References

- [supermodeltools/mcp#85](https://github.com/supermodeltools/mcp/issues/85) - Benchmark proposal issue
- [supermodeltools/mcp#82](https://github.com/supermodeltools/mcp/issues/82) - Local graph.json feature proposal
- [Supermodel API Documentation](https://docs.supermodeltools.com)
- [mcpbr Documentation](https://github.com/greynewell/mcpbr)
