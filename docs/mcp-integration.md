---
description: "Guide to integrating and testing MCP servers with mcpbr, including configuration, environment variables, and common server setups."
faq:
  - q: "How do I test my MCP server with mcpbr?"
    a: "Configure your MCP server in mcpbr.yaml by specifying the command, args (using {workdir} for the repository path), and any required environment variables. Then run 'mcpbr run -c mcpbr.yaml' to benchmark it against SWE-bench tasks."
  - q: "What MCP servers work with mcpbr?"
    a: "Any MCP server that exposes tools for file operations, code search, or codebase analysis can be tested. Common examples include the Anthropic filesystem server, custom Python MCP servers, and codebase analysis tools like Supermodel."
  - q: "How does mcpbr register MCP servers with Claude?"
    a: "mcpbr uses the Claude Code CLI's 'claude mcp add' command to register your MCP server before each agent run. Tools from your server appear with the mcp__ prefix (e.g., mcp__read_file)."
  - q: "Why would I use an MCP server instead of Claude's built-in tools?"
    a: "MCP servers can provide specialized tools like semantic code search, codebase indexing, AST analysis, or domain-specific operations that go beyond basic file operations, potentially improving the agent's ability to understand and fix bugs."
---

# MCP Server Integration

This guide explains how to benchmark your MCP (Model Context Protocol) server with mcpbr.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard that allows AI models to access external tools and data sources. MCP servers expose tools that Claude can use during agent runs.

mcpbr was built specifically to solve the problem of measuring whether MCP servers actually improve agent performance. Read [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/) for the full context behind this approach.

## How mcpbr Uses MCP

mcpbr runs two parallel evaluations for each task:

1. **MCP Agent**: Claude Code CLI with your MCP server registered
2. **Baseline Agent**: Claude Code CLI without MCP tools

By comparing resolution rates, you can measure the effectiveness of your MCP server.

## Configuring Your MCP Server

### Basic Configuration

```yaml
mcp_server:
  name: "mcpbr"
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env: {}
```

### Configuration Fields

| Field | Description |
|-------|-------------|
| `name` | Name to register the server as (tools appear as `mcp__{name}__{tool}`) |
| `command` | Executable to run your MCP server |
| `args` | Command arguments (use `{workdir}` for repository path) |
| `env` | Environment variables for the server |

### The `{workdir}` Placeholder

The `{workdir}` placeholder is replaced at runtime with `/workspace` - the path to the task repository inside the Docker container.

## Example Configurations

### Anthropic Filesystem Server

Basic file system access:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
```

This provides tools for reading, writing, and listing files.

### Custom Python MCP Server

```yaml
mcp_server:
  command: "python"
  args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]
  env:
    LOG_LEVEL: "debug"
    CUSTOM_SETTING: "value"
```

### Node.js MCP Server

```yaml
mcp_server:
  command: "node"
  args: ["/path/to/server/index.js", "--root", "{workdir}"]
```

### External API Server

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

## Testing Your Server

### 1. Verify Standalone

Before running mcpbr, test your MCP server independently:

```bash
# For the filesystem server
npx -y @modelcontextprotocol/server-filesystem /tmp/test

# For a custom server
python -m my_mcp_server --workspace /tmp/test
```

### 2. Quick Smoke Test

Run a single task with verbose output:

```bash
mcpbr run -c config.yaml -n 1 -v -M
```

This runs:

- Only 1 task (`-n 1`)
- With verbose output (`-v`)
- MCP agent only (`-M`)

### 3. Check Tool Registration

In verbose output, you'll see tool calls like:

```text
14:23:22 astropy-12907:mcp    > mcp__mcpbr__read_file
14:23:22 astropy-12907:mcp    < File content: ...
```

If your tools aren't appearing, check:

- Server startup logs (stderr)
- Environment variables are set correctly
- The `{workdir}` path is valid

## MCP Tools in Action

When your MCP server is registered, Claude can use its tools alongside built-in tools:

```text
Built-in tools:
  Bash, Glob, Grep, Read, Write, Edit, TodoWrite, Task

MCP tools (with mcp__ prefix):
  mcp__mcpbr__read_file
  mcp__mcpbr__write_file
  mcp__mcpbr__list_directory
  mcp__mcpbr__search_files
  ...
```

## Evaluation Strategy

### Small-Scale Testing

Start with a small sample to verify your server works:

```yaml
sample_size: 5
max_concurrent: 1
timeout_seconds: 180
```

### Full Benchmark

For comprehensive results:

```yaml
sample_size: null  # Full SWE-bench Lite (300 tasks)
max_concurrent: 4
timeout_seconds: 600
max_iterations: 30
```

### Comparing Servers

To compare multiple MCP servers:

1. Create separate config files
2. Run evaluations with different configs
3. Compare JSON results

```bash
mcpbr run -c server-a.yaml -o results-a.json
mcpbr run -c server-b.yaml -o results-b.json
```

## Server Development Tips

### 1. Optimize for Code Search

Tools that help locate relevant code quickly tend to improve performance:

- Semantic search
- Symbol lookup
- Reference finding

### 2. Provide Context

Tools that provide contextual information help Claude understand the codebase:

- File summaries
- Module structure
- Dependency graphs

### 3. Minimize Latency

Each tool call adds time. Consider:

- Caching results
- Batch operations
- Precomputing indexes

### 4. Handle Errors Gracefully

Return informative error messages that help Claude recover:

```python
# Bad
raise Exception("Error")

# Good
raise Exception("File not found: {path}. Did you mean {suggestion}?")
```

## Debugging

### Logs Per Instance

Enable per-instance logs to debug specific tasks:

```bash
mcpbr run -c config.yaml -v --log-dir logs/
```

This creates JSON log files with full tool call traces.

### Check Tool Usage

The results JSON includes tool usage statistics:

```json
{
  "tool_usage": {
    "mcp__mcpbr__read_file": 15,
    "mcp__mcpbr__search_files": 8,
    "Bash": 27,
    "Read": 22
  }
}
```

Low MCP tool usage may indicate:

- Tools not helpful for the task
- Tool discovery issues
- Better built-in alternatives

### Common Issues

#### Server Not Starting

```text
Warning: MCP server add failed (exit 1): ...
```

Check:

- Command exists and is executable
- Environment variables are set
- No syntax errors in server code

#### Tools Not Appearing

If Claude isn't using your MCP tools:

- Verify server registers tools correctly
- Check tool descriptions are clear
- Ensure `{workdir}` is resolved correctly

## Next Steps

- [Testing Philosophy](philosophy.md) - Principles for meaningful MCP server evaluation
- [Evaluation Results](evaluation-results.md) - Understanding output formats
- [Architecture](architecture.md) - How mcpbr works internally
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
