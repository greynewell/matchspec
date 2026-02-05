# CircleCI Orb for mcpbr

Run MCP server benchmarks in your CircleCI pipeline.

## Quick Start

```yaml
version: 2.1

orbs:
  mcpbr: greynewell/mcpbr@1.0

workflows:
  benchmark:
    jobs:
      - mcpbr/benchmark:
          config: benchmarks/config.yaml
```

## Commands

| Command | Description |
|---|---|
| `install` | Install mcpbr (with optional version) |
| `run-benchmark` | Run benchmarks with a config file |
| `smoke-test` | Quick verification that mcpbr works |

## Jobs

| Job | Description |
|---|---|
| `benchmark` | Full benchmark run with install + execute |
| `smoke-test` | Quick smoke test |

## Parameters

### `install`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `version` | string | `latest` | mcpbr version to install |

### `run-benchmark`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `config` | string | (required) | Path to config YAML |
| `output-dir` | string | `results` | Results directory |
| `extra-args` | string | `""` | Additional CLI args |

## Environment Variables

Set these in your CircleCI project settings:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
