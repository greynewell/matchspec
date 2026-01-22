# @greynewell/mcpbr

> npm wrapper for the mcpbr CLI tool

[![npm version](https://badge.fury.io/js/%40greynewell%2Fmcpbr.svg)](https://www.npmjs.com/package/@greynewell/mcpbr)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This npm package provides convenient access to the [mcpbr](https://github.com/greynewell/mcpbr) command-line tool for Node.js and JavaScript developers.

## What is mcpbr?

**Model Context Protocol Benchmark Runner** - Benchmark your MCP server against real GitHub issues. Get hard numbers comparing tool-assisted vs. baseline agent performance.

## Installation

### Prerequisites

- **Python 3.11+** (the mcpbr CLI is implemented in Python)
- **mcpbr Python package** (`pip install mcpbr`)

### Install via npm

```bash
# Run directly with npx (no installation)
npx @greynewell/mcpbr run -c config.yaml

# Or install globally
npm install -g @greynewell/mcpbr

# Then use anywhere
mcpbr run -c config.yaml
```

### Install Python dependencies

The npm package is a wrapper that requires the Python implementation:

```bash
# Install mcpbr Python package
pip install mcpbr

# Verify installation
mcpbr --version
```

## Usage

All `mcpbr` commands are available through the npm wrapper:

```bash
# Initialize configuration
npx @greynewell/mcpbr init

# Run benchmark evaluation
npx @greynewell/mcpbr run -c config.yaml

# List available models
npx @greynewell/mcpbr models

# List available benchmarks
npx @greynewell/mcpbr benchmarks

# Run with verbose output
npx @greynewell/mcpbr run -c config.yaml -v

# Run specific tasks
npx @greynewell/mcpbr run -c config.yaml -t astropy__astropy-12907
```

## Quick Start

```bash
# 1. Install Python dependencies
pip install mcpbr

# 2. Set API key
export ANTHROPIC_API_KEY="your-api-key"

# 3. Run benchmark
npx @greynewell/mcpbr init
npx @greynewell/mcpbr run -c mcpbr.yaml -n 5 -v
```

## Why use the npm package?

- **Familiar workflow** for Node.js/JavaScript developers
- **No need to remember** pip vs npm for different tools
- **Consistent versioning** with other npm packages
- **Easy integration** into Node.js projects and scripts
- **npx support** for one-off commands without installation

## Documentation

For full documentation, visit: https://greynewell.github.io/mcpbr/

- [Installation Guide](https://greynewell.github.io/mcpbr/installation/)
- [Configuration Reference](https://greynewell.github.io/mcpbr/configuration/)
- [CLI Reference](https://greynewell.github.io/mcpbr/cli/)
- [Benchmarks Guide](https://greynewell.github.io/mcpbr/benchmarks/)

## Troubleshooting

### Error: Python 3.11 or later required

Install Python 3.11+:

```bash
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# Windows
# Download from https://www.python.org/downloads/
```

### Error: mcpbr Python package not found

Install the Python package:

```bash
pip install mcpbr
# or
pip3 install mcpbr
```

### Error: command not found: mcpbr

If you installed globally, ensure npm global bin directory is in your PATH:

```bash
npm config get prefix
# Add <prefix>/bin to your PATH
```

## Development

This package is part of the mcpbr project:

```bash
# Clone the repository
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr/cli

# Install dependencies
npm install

# Test the wrapper
npm test
```

## Related Packages

- [`mcpbr`](https://pypi.org/project/mcpbr/) - Python package (core implementation)
- [`@greynewell/mcpbr-claude-plugin`](https://www.npmjs.com/package/@greynewell/mcpbr-claude-plugin) - Claude Code plugin

## License

MIT - see [LICENSE](../LICENSE) for details.

## Contributing

Contributions welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Support

- **Documentation**: https://greynewell.github.io/mcpbr/
- **Issues**: https://github.com/greynewell/mcpbr/issues
- **Discussions**: https://github.com/greynewell/mcpbr/discussions
