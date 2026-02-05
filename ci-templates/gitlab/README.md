# GitLab CI Template for mcpbr

Run MCP server benchmarks in your GitLab CI/CD pipeline.

## Quick Start

Add this to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/greynewell/mcpbr/main/ci-templates/gitlab/.gitlab-ci-mcpbr.yml'

variables:
  MCPBR_CONFIG: "benchmarks/my-config.yaml"
  ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
```

## Configuration Variables

| Variable | Description | Default |
|---|---|---|
| `MCPBR_VERSION` | Version of mcpbr to install | `latest` |
| `MCPBR_PYTHON_VERSION` | Python version | `3.11` |
| `MCPBR_CONFIG` | Path to config file | `benchmarks/config.yaml` |
| `MCPBR_OUTPUT_DIR` | Results directory | `results` |
| `MCPBR_LOG_LEVEL` | Log level | `INFO` |

## Jobs

| Job | Stage | Description |
|---|---|---|
| `mcpbr_install` | setup | Verify mcpbr installation |
| `mcpbr_benchmark` | benchmark | Run the benchmark suite |
| `mcpbr_smoke_test` | benchmark | Run a quick smoke test |
| `mcpbr_report` | report | Display results summary |

## Secrets

Store API keys as GitLab CI/CD variables (Settings > CI/CD > Variables):

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

Mark them as **masked** and **protected**.
