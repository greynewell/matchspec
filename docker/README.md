# Docker Support for mcpbr

Run mcpbr benchmarks in a containerized environment.

## Quick Start

### Build the image

```bash
docker build -f Dockerfile.app -t mcpbr:latest .
```

### Run a benchmark

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -v $(pwd)/configs:/home/mcpbr/configs:ro \
  -v $(pwd)/results:/home/mcpbr/results \
  mcpbr:latest run --config /home/mcpbr/configs/benchmark.yaml
```

### Run with Docker Compose

```bash
cd docker/
export ANTHROPIC_API_KEY=your-key-here
docker compose up mcpbr
```

### Smoke test

```bash
docker run --rm -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" mcpbr:latest smoke-test
```

## Architecture

The `Dockerfile.app` uses a multi-stage build:

1. **Builder stage**: Builds the mcpbr wheel from source
2. **Runtime stage**: Installs only the wheel and runtime dependencies

The image runs as a non-root user (`mcpbr`) for security.

## Volumes

| Mount Point | Purpose |
|---|---|
| `/home/mcpbr/configs` | Benchmark configuration files (read-only) |
| `/home/mcpbr/results` | Benchmark results output |

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | API key for Anthropic models |
| `OPENAI_API_KEY` | API key for OpenAI models |
| `MCPBR_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |
