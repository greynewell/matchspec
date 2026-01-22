# Supermodel MCP Server

[![npm](https://img.shields.io/npm/v/@supermodeltools/mcp-server)](https://www.npmjs.com/package/@supermodeltools/mcp-server)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io)
[![CI](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml)

MCP server that provides deep codebase analysis to AI agents via the [Supermodel API](https://docs.supermodeltools.com). Enables Claude to understand code structure, dependencies, and relationships by generating comprehensive graphs from any repository. Use this to help AI agents explore unfamiliar code, plan refactorings, assess change impact, and understand system architecture.

## Install

```bash
npm install -g @supermodeltools/mcp-server
```

Or run directly:

```bash
npx @supermodeltools/mcp-server
```

## Configuration

Get your API key from the [Supermodel Dashboard](https://dashboard.supermodeltools.com).

| Variable | Description |
|----------|-------------|
| `SUPERMODEL_API_KEY` | Your Supermodel API key (required) |
| `SUPERMODEL_BASE_URL` | Override API base URL (optional) |

### Global Setup (Recommended)

Instead of adding your API key to each MCP config file, you can set it globally in your shell profile. This keeps your key in one place and automatically makes it available to all MCP clients.

**For Zsh (macOS default):**

Add to `~/.zshrc`:

```bash
export SUPERMODEL_API_KEY="your-api-key"
```

**For Bash:**

Add to `~/.bashrc` or `~/.bash_profile`:

```bash
export SUPERMODEL_API_KEY="your-api-key"
```

Then reload your shell:

```bash
source ~/.zshrc  # or ~/.bashrc
```

With the API key set globally, you can omit the `env` block from your MCP configs:

```json
{
  "mcpServers": {
    "supermodel": {
      "command": "npx",
      "args": ["-y", "@supermodeltools/mcp-server"]
    }
  }
}
```

### Default Working Directory (Optional)

For automated benchmarking tools (like mcpbr) or batch processing, you can specify a default working directory as a command-line argument. When provided, the `explore_codebase` tool will use this directory automatically if no explicit `directory` parameter is given.

**Command-line usage:**

```bash
npx @supermodeltools/mcp-server /path/to/repository
```

or with Node.js:

```bash
node dist/index.js /path/to/repository
```

**Example with benchmarking tools:**

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server", "{workdir}"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

This allows the agent to call `explore_codebase()` without specifying a directory parameter, automatically using the configured default workdir. You can still override it by explicitly passing a `directory` parameter in individual tool calls.

## Usage

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "supermodel": {
      "command": "npx",
      "args": ["-y", "@supermodeltools/mcp-server"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "supermodel": {
      "command": "npx",
      "args": ["-y", "@supermodeltools/mcp-server"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Claude Code

Add the MCP server with your API key:

```bash
claude mcp add supermodel --env SUPERMODEL_API_KEY=your-api-key -- npx -y @supermodeltools/mcp-server
```

Or if `SUPERMODEL_API_KEY` is already set in your shell environment:

```bash
claude mcp add supermodel -- npx -y @supermodeltools/mcp-server
```

Verify installation:

```bash
claude mcp list
```

## Tools

### `explore_codebase`

Analyzes code structure, dependencies, and relationships across a repository. Use this to understand unfamiliar codebases, plan refactorings, assess change impact, or map system architecture.

**When to use:**
- Exploring new codebases
- Planning refactors or architectural changes
- Understanding dependencies between modules
- Mapping call relationships and code flow
- Assessing the impact of proposed changes

**What you get:**
- Dependency graphs (module/package relationships)
- Call graphs (function-level call hierarchies)
- Domain classifications (architectural patterns)
- AST relationships (structural analysis)
- Summary statistics (languages, complexity, file counts)

**Parameters:**

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `directory` | string | Yes* | Path to repository directory (automatic zipping) |
| `file` | string | Yes* | Path to pre-zipped archive (deprecated) |
| `query` | string | No | Query type (summary, search, list_nodes, etc.) |
| `jq_filter` | string | No | jq filter for custom data extraction |

\* Either `directory` (recommended) or `file` must be provided

**Example prompts:**
- "Analyze the codebase at . to understand its architecture"
- "Before I refactor the authentication module, analyze this repo to show me what depends on it"
- "What's the structure of the codebase in /Users/me/project?"

**Automatic features:**
- Respects `.gitignore` patterns automatically
- Excludes sensitive files (`.env`, `*.pem`, credentials, etc.)
- Skips dependencies (`node_modules`, `venv`, `vendor`)
- Removes build outputs (`dist`, `build`, `out`)
- Cleans up temporary files automatically
- Cross-platform compatible

## Troubleshooting

Debug logs go to stderr:

- `[DEBUG] Server configuration:` - Startup config
- `[DEBUG] Auto-zipping directory:` - Starting zip creation
- `[DEBUG] Auto-zip complete:` - Zip stats (file count, size)
- `[DEBUG] Making API request` - Request details
- `[ERROR] API call failed:` - Error details with HTTP status

**Common issues:**
- 401: Check `SUPERMODEL_API_KEY` is set
- ZIP too large: Directory contains too many files/dependencies. Ensure `.gitignore` is configured properly
- Permission denied: Check read permissions on the directory
- Insufficient disk space: Free up space in your system's temp directory
- Directory does not exist: Verify the path is correct and absolute

## Benchmarking

Benchmark this MCP server using [mcpbr](https://github.com/caspianmoon/mcpbr-benchmark-caching) with the provided [`mcpbr-config.yaml`](./mcpbr-config.yaml) configuration.

## Links

- [API Documentation](https://docs.supermodeltools.com)
- [Supermodel SDK](https://www.npmjs.com/package/@supermodeltools/sdk)
