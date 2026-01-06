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
