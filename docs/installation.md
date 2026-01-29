---
faq:
  - q: "What are the prerequisites for running mcpbr?"
    a: "You need Python 3.11+, Docker running, an ANTHROPIC_API_KEY environment variable, the Claude Code CLI installed, and network access for pulling Docker images and API calls."
  - q: "How do I install mcpbr?"
    a: "Install from PyPI with 'pip install mcpbr', or install from source by cloning the repository and running 'pip install -e .' in the project directory."
  - q: "Does mcpbr work on Apple Silicon Macs?"
    a: "Yes, mcpbr works on Apple Silicon. The harness automatically uses x86_64 Docker images via emulation, which may be slower than native ARM64 images but ensures compatibility with all SWE-bench tasks."
  - q: "How do I install the Claude Code CLI?"
    a: "Install the Claude Code CLI globally with npm: 'npm install -g @anthropic-ai/claude-code'. Verify installation with 'which claude'."
---

# Installation

```bash
pip install mcpbr && mcpbr init && mcpbr run -c mcpbr.yaml -n 1 -v
```

That's it. For the full setup guide, read on.

## Prerequisites

Before installing mcpbr, ensure you have the following:

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required for mcpbr |
| Docker | Latest | Must be running |
| Claude Code CLI | Latest | The `claude` command |
| Network access | - | For Docker images and API calls |

### API Key

You'll need an Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

!!! tip "Get an API key"
    Sign up at [console.anthropic.com](https://console.anthropic.com/) to get your API key.

### Claude Code CLI

Install the Claude Code CLI globally:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify the installation:

```bash
which claude  # Should return the path to the CLI
```

### Docker

Ensure Docker is installed and running:

```bash
docker info
```

If Docker isn't running, start it from your system's application launcher or:

=== "macOS"
    ```bash
    open -a Docker
    ```

=== "Linux"
    ```bash
    sudo systemctl start docker
    ```

=== "Windows"
    Start Docker Desktop from the Start menu.

## Installation Methods

### From PyPI (Recommended)

```bash
pip install mcpbr
```

### From npm

[![npm package](https://img.shields.io/npm/v/mcpbr-cli.svg)](https://www.npmjs.com/package/mcpbr-cli)

mcpbr is also available as an npm package for easy integration with Node.js workflows:

```bash
# Run with npx (no installation)
npx mcpbr-cli run -c config.yaml

# Or install globally
npm install -g mcpbr-cli
mcpbr run -c config.yaml
```

!!! info "Package Details"
    **Package name**: [`mcpbr-cli`](https://www.npmjs.com/package/mcpbr-cli)

    The npm package is a wrapper that requires Python 3.11+ and the mcpbr Python package to be installed separately:
    ```bash
    pip install mcpbr
    npm install -g mcpbr-cli
    ```

### From Source

```bash
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr
pip install -e .
```

### With uv

```bash
uv pip install mcpbr
```

Or from source:

```bash
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr
uv pip install -e .
```

## Verify Installation

After installation, verify everything is working:

```bash
# Check mcpbr is installed
mcpbr --version

# List supported models
mcpbr models

# Generate a test config
mcpbr init -o test-config.yaml
```

## Supported Models

mcpbr supports the following Claude models:

| Model | ID | Context Window |
|-------|-----|----------------|
| Claude Opus 4.5 | `opus` or `claude-opus-4-5-20251101` | 200,000 |
| Claude Sonnet 4.5 | `sonnet` or `claude-sonnet-4-5-20250929` | 200,000 |
| Claude Haiku 4.5 | `haiku` or `claude-haiku-4-5-20251001` | 200,000 |
| Claude Opus 4 | `claude-opus-4-20250514` | 200,000 |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | 200,000 |
| Claude Haiku 4 | `claude-haiku-4-20250514` | 200,000 |
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` | 200,000 |

Run `mcpbr models` to see the full list.

## Apple Silicon Notes

On ARM64 Macs (M1/M2/M3), x86_64 Docker images run via emulation. This is:

- **Slower** than native ARM64 images
- **Required** for compatibility with all SWE-bench tasks
- **Automatic** - no configuration needed

If you experience issues, ensure Rosetta 2 is installed:

```bash
softwareupdate --install-rosetta
```

## Development Installation

For contributing to mcpbr:

```bash
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr
pip install -e ".[dev]"
```

This installs additional development dependencies:

- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `ruff` - Linting and formatting

See [Contributing](contributing.md) for more details.

## Next Steps

After installation, you have two options to get started:

**Option 1: Use Example Configurations (Fastest)**

Jump straight in with our ready-to-use examples:

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-api-key"

# Run your first evaluation
mcpbr run -c examples/quick-start/getting-started.yaml -v
```

Explore **25+ example configurations** in the [`examples/`](https://github.com/greynewell/mcpbr/tree/main/examples) directory covering benchmarks, MCP servers, and common scenarios. See the [Examples README](https://github.com/greynewell/mcpbr/tree/main/examples/README.md) for the complete guide.

**Option 2: Generate Custom Configuration**

Create your own configuration:

```bash
mcpbr init
# Edit mcpbr.yaml
mcpbr run -c mcpbr.yaml -v
```

**Continue Learning:**

- [Quick Start](index.md) - Run your first evaluation
- [Configuration](configuration.md) - Configure your MCP server
- [Examples](https://github.com/greynewell/mcpbr/tree/main/examples) - Browse example configurations
- [CLI Reference](cli.md) - Explore all commands
