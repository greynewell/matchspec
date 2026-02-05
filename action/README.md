# mcpbr GitHub Action

A composite GitHub Action to run MCP server benchmarks in your CI/CD pipeline.

## Usage

```yaml
- uses: greynewell/mcpbr@main
  with:
    config: benchmarks/config.yaml
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

| Input | Description | Required | Default |
|---|---|---|---|
| `config` | Path to benchmark configuration YAML | Yes | - |
| `version` | mcpbr version to install | No | `latest` |
| `python-version` | Python version to use | No | `3.11` |
| `output-dir` | Directory for results | No | `results` |
| `extra-args` | Additional CLI arguments | No | `""` |
| `anthropic-api-key` | Anthropic API key | No | - |
| `openai-api-key` | OpenAI API key | No | - |

## Outputs

| Output | Description |
|---|---|
| `results-path` | Path to the results directory |
| `exit-code` | Exit code from the benchmark run |

## Examples

See the [examples](examples/) directory for:

- [basic.yml](examples/basic.yml) - Simple benchmark run on push
- [matrix.yml](examples/matrix.yml) - Matrix builds across benchmarks and Python versions

## Security

Always use GitHub Secrets for API keys. Never hardcode them in workflow files.

```yaml
anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```
