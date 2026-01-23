# Supermodel MCP Server

[![npm](https://img.shields.io/npm/v/@supermodeltools/mcp-server)](https://www.npmjs.com/package/@supermodeltools/mcp-server)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io)
[![CI](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/supermodeltools/mcp/actions/workflows/ci.yml)

MCP server that provides deep codebase analysis to AI agents via the [Supermodel API](https://docs.supermodeltools.com). Enables Claude to understand code structure, dependencies, and relationships by generating comprehensive graphs from any repository. Use this to help AI agents explore unfamiliar code, plan refactorings, assess change impact, and understand system architecture.

## Install

### Quick Setup (Recommended)

Run the setup script to configure the recommended timeout settings:

```bash
curl -sSL https://raw.githubusercontent.com/supermodeltools/mcp/main/setup.sh | bash
```

<details>
<summary>Prefer to inspect before running? (Click to expand)</summary>

Download, review, then execute:

```bash
# Download the script
curl -sSL https://raw.githubusercontent.com/supermodeltools/mcp/main/setup.sh -o setup.sh

# Review the contents
cat setup.sh

# Make executable and run
chmod +x setup.sh
./setup.sh
```

Or clone the entire repo:

```bash
git clone https://github.com/supermodeltools/mcp.git
cd mcp
./setup.sh
```

</details>

This will configure `MCP_TOOL_TIMEOUT=900000` for optimal performance with large codebases.

### Manual Install

```bash
npm install -g @supermodeltools/mcp-server
```

Or run directly:

```bash
npx @supermodeltools/mcp-server
```

## ⚠️ Important: Configure Timeout for Large Codebase Analysis

The `explore_codebase` tool can take **5-15 minutes** to analyze large repositories. Most MCP clients have a default timeout of 60-120 seconds, which will cause the operation to fail prematurely.

**Quick Setup:**

Add this to your shell profile to set a 15-minute timeout:

```bash
export MCP_TOOL_TIMEOUT=900000
```

**Installation by Client:**

<details>
<summary><strong>Claude Code CLI</strong></summary>

Add to your shell profile (`~/.zshrc` for macOS or `~/.bashrc` for Linux):

```bash
export MCP_TOOL_TIMEOUT=900000
```

Then reload your shell:

```bash
source ~/.zshrc  # or ~/.bashrc
```

Verify it's set:

```bash
echo $MCP_TOOL_TIMEOUT
```

</details>

**Note:** Timeout configuration via `MCP_TOOL_TIMEOUT` is only supported in Claude Code CLI. For more details, see the [official Claude Code documentation](https://code.claude.com/docs/en/settings.md).

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

### Claude Code CLI

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

## Health Checks

This MCP server implements the [MCP ping utility](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping) for connection health monitoring. The ping mechanism allows clients to verify that the server is responsive and the connection remains alive.

### How It Works

- **Request**: Client sends a `ping` JSON-RPC request with no parameters
- **Response**: Server responds promptly with an empty result object `{}`
- **Automatic**: Handled automatically by the MCP SDK - no additional configuration needed

### Use Cases

- **Pre-flight checks**: Verify server is accessible before starting work
- **Connection monitoring**: Detect stale connections during long-running sessions
- **Periodic health checks**: Confirm server remains responsive

### Example

```json
// Request
{
  "jsonrpc": "2.0",
  "id": "123",
  "method": "ping"
}

// Response
{
  "jsonrpc": "2.0",
  "id": "123",
  "result": {}
}
```

If the server doesn't respond within a reasonable timeout (typically 5-10 seconds), the connection should be considered stale.

For more details, see the [MCP specification for ping/health checks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping).

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

## Tool Performance & Timeout Requirements

The `explore_codebase` tool analyzes your entire repository to build a comprehensive code graph. Analysis time scales with repository size and complexity.

| Tool | Typical Duration | Recommended Timeout | Repository Size |
|------|------------------|---------------------|--------------------|
| `explore_codebase` | 2-5 min | 600000ms (10 min) | Small (<1k files) |
| `explore_codebase` | 5-10 min | 900000ms (15 min) | Medium (1k-10k files) |
| `explore_codebase` | 10-15 min | 1200000ms (20 min) | Large (10k+ files) |

**Default recommendation**: The server uses a 15-minute timeout (`900000ms`) by default, which works well for most medium-sized repositories.

**Caching behavior**: The first run analyzes your codebase and caches the results. Subsequent queries on the same repository are typically much faster (seconds instead of minutes) as they use the cached graph.

**Setting custom timeouts**: If you need to adjust the timeout for larger repositories, you can set the `SUPERMODEL_TIMEOUT_MS` environment variable:

```json
{
  "mcpServers": {
    "supermodel": {
      "command": "npx",
      "args": ["-y", "@supermodeltools/mcp-server"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key",
        "SUPERMODEL_TIMEOUT_MS": "1200000"
      }
    }
  }
}
```

## Troubleshooting

### Timeout Errors

#### "Request timeout"

**Cause:** The analysis is taking longer than your MCP client's timeout allows (varies by client—Claude Code CLI defaults to ~2 minutes, Claude Desktop enforces 5 minutes). Large repositories or complex codebases may require more time to analyze.

**Solutions:**

1. **Analyze a subdirectory instead** - Target specific parts of your codebase:
   ```bash
   # Instead of analyzing the entire repo
   explore_codebase(directory="/path/to/repo")

   # Analyze just the core module
   explore_codebase(directory="/path/to/repo/src/core")
   ```

2. **Increase your MCP client timeout** - For Claude Code CLI, set the `MCP_TOOL_TIMEOUT` environment variable:

   ```bash
   # Set timeout to 15 minutes (900000ms) for large codebase analysis
   export MCP_TOOL_TIMEOUT=900000
   ```

   Then reload your shell or start a new terminal session. This timeout applies to all MCP tool executions.

   **Note:** Timeout configuration is currently only supported in Claude Code CLI.

3. **Verify `.gitignore` excludes build artifacts** - Ensure your repository excludes:
   - `node_modules/`, `vendor/`, `venv/`
   - `dist/`, `build/`, `out/`
   - `.next/`, `.nuxt/`, `.cache/`

   The MCP server automatically excludes these patterns when zipping, but `.gitignore` prevents them from being in your working directory in the first place—both improve performance and reduce analysis size.

#### "Analysis interrupted mid-way"

**Cause:** Network interruption or the MCP server process was terminated before completion.

**Solutions:**

1. **Check MCP server logs** - Logs location varies by client:

   > **Note:** Log filenames match your MCP server name from the config. If you named it differently (e.g., `my-server`), look for `mcp-server-my-server.log` instead of `mcp-server-supermodel.log`.

   **Claude Desktop (macOS):**
   ```bash
   tail -f ~/Library/Logs/Claude/mcp-server-supermodel.log
   ```

   **Claude Desktop (Windows):**
   ```powershell
   Get-Content "$env:APPDATA\Claude\Logs\mcp-server-supermodel.log" -Wait
   ```

   **Claude Desktop (Linux):**
   ```bash
   tail -f ~/.config/Claude/logs/mcp-server-supermodel.log
   ```

   **Cursor:**
   ```bash
   # Check the Cursor logs directory
   tail -f ~/Library/Application\ Support/Cursor/logs/mcp-server-supermodel.log
   ```

   **Claude Code:**
   ```bash
   # Logs are shown in the terminal when running with verbose mode
   claude --verbose
   ```

2. **Retry the analysis** - Temporary network issues often resolve on retry

3. **Check your internet connection** - The analysis requires a stable connection to the Supermodel API

4. **Verify the API is accessible:**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" https://api.supermodeltools.com/health
   ```

#### "ERROR Request failed. Check the MCP server logs"

**Multiple possible causes:**

##### 1. Missing or invalid API key

Check if your API key is set:
```bash
echo $SUPERMODEL_API_KEY
```

Verify it's valid at [Supermodel Dashboard](https://dashboard.supermodeltools.com).

**Solution:**
```bash
# Set in your shell profile (~/.zshrc or ~/.bashrc)
export SUPERMODEL_API_KEY="your-api-key"
source ~/.zshrc

# Or update your MCP client config with the correct key
```

##### 2. API service outage or rate limiting

Check the error details in logs (see log locations above).

**Solution:**
- Visit [Supermodel Status](https://status.supermodeltools.com) for service status
- If rate limited, wait a few minutes before retrying
- Consider upgrading your API plan if hitting rate limits frequently

##### 3. Repository too large

The API has size limits for analysis. Check the [Supermodel documentation](https://docs.supermodeltools.com) for current limits.

**Solution:**
```bash
# Check your repo size
du -sh /path/to/repo

# If too large, analyze subdirectories instead
explore_codebase(directory="/path/to/repo/src")
```

##### 4. Network or firewall issues

Corporate firewalls may block outbound requests to the Supermodel API.

**Solution:**
- Test connectivity: `curl https://api.supermodeltools.com/health`
- Check firewall rules allow HTTPS to `api.supermodeltools.com`
- Contact your IT department if behind a corporate proxy

### Debug Logging

Debug logs go to stderr and include:

- `[DEBUG] Server configuration:` - Startup config
- `[DEBUG] Auto-zipping directory:` - Starting zip creation
- `[DEBUG] Auto-zip complete:` - Zip stats (file count, size)
- `[DEBUG] Making API request` - Request details
- `[ERROR] API call failed:` - Error details with HTTP status

To enable verbose logging, set the `DEBUG` environment variable:

```bash
# In your MCP config
{
  "mcpServers": {
    "supermodel": {
      "command": "npx",
      "args": ["-y", "@supermodeltools/mcp-server"],
      "env": {
        "SUPERMODEL_API_KEY": "your-api-key",
        "DEBUG": "supermodel:*"
      }
    }
  }
}
```

### Common Issues

- **401 Unauthorized:** Check `SUPERMODEL_API_KEY` is set correctly
- **ZIP too large:** Directory contains too many files/dependencies. Ensure `.gitignore` is configured properly
- **Permission denied:** Check read permissions on the directory
- **Insufficient disk space:** Free up space in your system's temp directory
- **Directory does not exist:** Verify the path is correct and absolute
- **ENOTFOUND or connection errors:** Check your internet connection and firewall settings

## Benchmarking

Benchmark this MCP server using [mcpbr](https://github.com/caspianmoon/mcpbr-benchmark-caching) with the provided [`mcpbr-config.yaml`](./mcpbr-config.yaml) configuration.

## Links

- [API Documentation](https://docs.supermodeltools.com)
- [Supermodel SDK](https://www.npmjs.com/package/@supermodeltools/sdk)
