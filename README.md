# Supermodel MCP Server (OpenAPI Edition)

A standalone Model Context Protocol (MCP) server for the Supermodel API, built using the `@supermodeltools/sdk`. This server allows AI agents (like Cursor, Claude Desktop, etc.) to interact directly with Supermodel's graph generation capabilities.

## Features

- **Standalone Package:** No workspace dependencies on the main repo.
- **OpenAPI SDK:** Uses the official `@supermodeltools/sdk`.
- **Graph Generation:** Exposes the `create_supermodel_graph_graphs` tool to generate Supermodel Intermediate Representation (SIR) from code repositories.
- **Smart Filtering:** Supports `jq` filtering to reduce context usage for large responses.

## Installation

1.  **Build the project:**

    ```bash
    cd packages/mcp-server-openapi
    npm install
    npm run build
    ```

## Configuration

The server requires API credentials to be provided via environment variables.

| Variable | Description |
| :--- | :--- |
| `SUPERMODEL_API_KEY` | Your Supermodel API Key. |
| `SUPERMODEL_BEARER_TOKEN` | Bearer token (alternative to API Key). |
| `SUPERMODEL_BASE_URL` | (Optional) Override the API base URL. Defaults to `https://api.supermodel.io`. |

## Usage with MCP Clients

### Cursor / VS Code

Add the following configuration to your `config.json` (usually found in `~/.cursor/mcp.json` or similar):

```json
{
  "mcpServers": {
    "supermodel-openapi": {
      "command": "node",
      "args": ["/absolute/path/to/packages/mcp-server-openapi/dist/index.js"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "supermodel-openapi": {
      "command": "node",
      "args": ["/absolute/path/to/packages/mcp-server-openapi/dist/index.js"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Available Tools

### `create_supermodel_graph_graphs`

Uploads a zipped repository snapshot to generate the Supermodel Intermediate Representation (SIR).

**Arguments:**
- `file` (string, required): Path to the ZIP file containing the code.
- `Idempotency-Key` (string, required): Unique key for the request to ensure idempotency.
- `jq_filter` (string, optional): A `jq` filter string to extract specific parts of the response (highly recommended to save context).

**Example Usage (by AI):**
> "Generate a supermodel graph for the code in `/tmp/my-repo.zip`."

## Development

```bash
# Install dependencies
npm install

# Watch mode for development
npm run build -- --watch
```

