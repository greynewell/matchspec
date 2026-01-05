# Supermodel MCP Server

[![npm](https://img.shields.io/npm/v/@supermodeltools/mcp-server)](https://www.npmjs.com/package/@supermodeltools/mcp-server)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io)
[![CI](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml)

MCP server that exposes [Supermodel API](https://docs.supermodeltools.com) graph generation to AI agents. Generates dependency graphs, call graphs, domain models, and full Supermodel IR from code repositories.

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

```bash
claude mcp add supermodel -- npx -y @supermodeltools/mcp-server
```

## Tools

### `create_supermodel_graph_graphs`

Generates Supermodel IR from a zipped repository.

| Argument | Type | Description |
|----------|------|-------------|
| `file` | string | Path to repository ZIP file |
| `Idempotency-Key` | string | Unique request key for caching |
| `jq_filter` | string | Optional jq filter to reduce response size |

**Prepare your repo:**

```bash
git archive -o /tmp/repo.zip HEAD
```

**Example prompt:**
> Generate a supermodel graph for `/tmp/repo.zip`

## Troubleshooting

Debug logs go to stderr:

- `[DEBUG] Server configuration:` - Startup config
- `[DEBUG] Making API request` - Request details
- `[ERROR] API call failed:` - Error details with HTTP status

**Common issues:**
- 401: Check `SUPERMODEL_API_KEY` is set
- ZIP too large: Exclude node_modules/dist (use `git archive`)

## Links

- [API Documentation](https://docs.supermodeltools.com)
- [Supermodel SDK](https://www.npmjs.com/package/@supermodeltools/sdk)
