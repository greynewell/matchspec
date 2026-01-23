---
faq:
  - q: "Docker is not running - how do I fix this?"
    a: "Start Docker Desktop on macOS/Windows, or run 'sudo systemctl start docker' on Linux. Verify with 'docker info'."
  - q: "mcpbr says Claude CLI not found - what should I do?"
    a: "Install the Claude Code CLI with 'npm install -g @anthropic-ai/claude-code'. Verify installation with 'which claude'."
  - q: "Why is mcpbr slow on my Apple Silicon Mac?"
    a: "mcpbr uses x86_64 Docker images for compatibility with all SWE-bench tasks, which run via emulation on ARM64 Macs. Install Rosetta 2 with 'softwareupdate --install-rosetta' for best performance."
  - q: "My MCP server is not starting - how do I debug it?"
    a: "Test your MCP server independently first (e.g., 'npx -y @modelcontextprotocol/server-filesystem /tmp/test'). Check that all required environment variables are set and the command is in your PATH."
  - q: "mcpbr timed out on a task - what should I do?"
    a: "Increase timeout_seconds in your config (e.g., 600 for 10 minutes). Complex tasks may need more time, especially on emulated Docker."
  - q: "How do I clean up orphaned Docker resources?"
    a: "Run 'mcpbr cleanup' to find and remove orphaned containers, volumes, and networks. Use '--dry-run' first to preview what would be removed. By default, it only removes resources older than 24 hours."
  - q: "Pre-built Docker image not found - is this a problem?"
    a: "mcpbr will fall back to building from scratch, which is less reliable. You can manually pull images with 'docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.INSTANCE_ID'."
  - q: "API key is not working - how do I check?"
    a: "Ensure ANTHROPIC_API_KEY is exported in your shell: 'echo $ANTHROPIC_API_KEY'. The key should start with 'sk-ant-'."
---

# Troubleshooting

Common issues and solutions for mcpbr.

## Docker Issues

### Docker Not Running

**Symptom**: Error connecting to Docker daemon

**Solution**:

=== "macOS"
    ```bash
    open -a Docker
    # Wait for Docker to start, then verify
    docker info
    ```

=== "Linux"
    ```bash
    sudo systemctl start docker
    docker info
    ```

=== "Windows"
    Start Docker Desktop from the Start menu, then verify:
    ```bash
    docker info
    ```

### Pre-built Image Not Found

**Symptom**: Warning about falling back to building from scratch

**Solution**: This is normal for some tasks. You can manually pull:

```bash
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907
```

Or disable pre-built images to always build from scratch:

```bash
mcpbr run -c config.yaml --no-prebuilt
```

### Orphaned Docker Resources

**Symptom**: Old mcpbr containers, volumes, or networks consuming resources or causing "already exists" errors

**Solution**:

```bash
# Preview what would be removed (resources older than 24 hours)
mcpbr cleanup --dry-run

# Remove orphaned resources with confirmation
mcpbr cleanup

# Force remove all resources immediately
mcpbr cleanup -f

# Remove only specific resource types
mcpbr cleanup --containers-only
mcpbr cleanup --volumes-only
mcpbr cleanup --networks-only

# Customize retention period (e.g., 48 hours)
mcpbr cleanup --retention-hours 48
```

**When to use**: After crashes, interruptions, or when switching evaluation configurations

**Safety features**:
- Default 24-hour retention policy prevents removing active evaluations
- Confirmation prompt before removal (use -f to skip)
- Dry-run mode to preview changes
- Detailed reporting of removed resources

## Performance Issues

### Slow on Apple Silicon

**Symptom**: Tasks take much longer than expected on M1/M2/M3 Macs

**Explanation**: mcpbr uses x86_64 Docker images that run via emulation on ARM64.

**Solutions**:

1. Install Rosetta 2 for better emulation:
   ```bash
   softwareupdate --install-rosetta
   ```

2. Reduce concurrency to avoid resource contention:
   ```yaml
   max_concurrent: 2
   ```

3. Increase timeouts:
   ```yaml
   timeout_seconds: 600
   ```

### Task Timeouts

**Symptom**: Tasks fail with "Timeout" error

**Solutions**:

1. Increase timeout in config:
   ```yaml
   timeout_seconds: 600  # 10 minutes
   ```

2. Reduce max iterations if agent is looping:
   ```yaml
   max_iterations: 20
   ```

3. Use a faster model for testing:
   ```yaml
   model: "haiku"
   ```

## API Issues

### API Key Not Set

**Symptom**: "ANTHROPIC_API_KEY environment variable not set"

**Solution**:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Add to your shell profile (`.bashrc`, `.zshrc`) for persistence.

### API Key Invalid

**Symptom**: Authentication errors from Anthropic API

**Solutions**:

1. Verify the key format (should start with `sk-ant-`):
   ```bash
   echo $ANTHROPIC_API_KEY
   ```

2. Check key permissions in [Anthropic Console](https://console.anthropic.com/)

3. Ensure no extra whitespace:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..." # No spaces
   ```

### Rate Limiting

**Symptom**: API rate limit errors

**Solutions**:

1. Reduce concurrency:
   ```yaml
   max_concurrent: 2
   ```

2. Add delays between tasks (requires code modification)

3. Check your API tier limits in Anthropic Console

## CLI Issues

### Claude CLI Not Found

**Symptom**: "Claude Code CLI (claude) not found in PATH"

**Solution**:

```bash
# Install Claude CLI
npm install -g @anthropic-ai/claude-code

# Verify installation
which claude
```

If installed but not found, check your PATH includes npm global binaries:

```bash
export PATH="$PATH:$(npm config get prefix)/bin"
```

### Command Not Found: mcpbr

**Symptom**: "mcpbr: command not found"

**Solutions**:

1. Ensure mcpbr is installed:
   ```bash
   pip install mcpbr
   ```

2. Check it's in your PATH:
   ```bash
   pip show mcpbr | grep Location
   ```

3. Use the full path or module:
   ```bash
   python -m mcpbr --help
   ```

## MCP Server Issues

### Server Not Starting

**Symptom**: "Warning: MCP server add failed"

**Solutions**:

1. Test the server independently:
   ```bash
   npx -y @modelcontextprotocol/server-filesystem /tmp/test
   ```

2. Check environment variables:
   ```bash
   echo $SUPERMODEL_API_KEY  # If using Supermodel
   ```

3. Verify the command exists:
   ```bash
   which npx  # or python, node, etc.
   ```

### Tools Not Appearing

**Symptom**: MCP tools not being used by the agent

**Possible causes**:

1. Server not registering tools correctly
2. Tool descriptions unclear
3. Built-in tools sufficient for the task

**Debug steps**:

1. Enable verbose logging:
   ```bash
   mcpbr run -c config.yaml -vv --log-dir logs/
   ```

2. Check per-instance logs for tool registration
3. Review tool_usage in results JSON

### MCP Server Logs

**New in v3.0.0**: mcpbr now captures MCP server logs automatically.

**Log Location**: `~/.mcpbr_state/logs/{instance_id}_mcp.log`

**What's captured**:
- MCP server stdout and stderr
- Claude CLI's MCP-related output
- Tool call errors and timeouts

**How to access**:

```bash
# View logs for a specific instance
cat ~/.mcpbr_state/logs/django__django-11905_mcp.log

# View logs for all instances
ls ~/.mcpbr_state/logs/

# Follow logs in real-time during evaluation
tail -f ~/.mcpbr_state/logs/*.log
```

**Error messages now include log paths**:
```text
Error: Task execution timed out after 1200s.
       MCP server 'supermodel' was registered successfully
       but the agent failed to complete within the timeout.
       MCP server logs saved to: ~/.mcpbr_state/logs/django__django-11905_mcp.log
```

### MCP Tool Timeouts

**Symptom**: MCP tool calls timing out or failing with "Request failed"

**Explanation**: Some MCP servers (like Supermodel's codebase analyzer) can take several minutes to respond. Claude CLI has default timeouts that may be too short.

**Solution**: Configure MCP timeouts in your config file:

```yaml
mcp_server:
  name: "supermodel"
  command: "npx"
  args:
    - "-y"
    - "@supermodeltools/mcp-server"
    - "{workdir}"
  startup_timeout_ms: 60000      # 60 seconds for server to start
  tool_timeout_ms: 900000        # 15 minutes for tool calls
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

**Recommended timeouts by server type**:

| Server Type | startup_timeout_ms | tool_timeout_ms | Notes |
|-------------|-------------------|-----------------|-------|
| Fast (filesystem, git) | 10000 (10s) | 30000 (30s) | Local operations |
| Medium (web search) | 30000 (30s) | 120000 (2m) | Network I/O |
| Slow (code analysis) | 60000 (60s) | 900000 (15m) | Complex processing |

**Debug steps if timeouts persist**:

1. Check MCP server logs (see above)
2. Test the tool independently:
   ```bash
   # For Supermodel
   npx -y @supermodeltools/mcp-server /tmp/test
   ```
3. Increase task timeout to allow for multiple retries:
   ```yaml
   timeout_seconds: 1200  # 20 minutes
   ```

### Registration Failures

**Symptom**: "MCP server registration failed" or "MCP server registration timed out"

**New in v3.0.0**: Detailed error messages showing exactly what failed.

**Example errors**:

```text
MCP server registration failed (exit 1):
  npx: command not found
```

```text
MCP server registration timed out after 60s.
  The MCP server may have failed to start or is hanging.
```

**Solutions**:

1. **Command not found**: Ensure the MCP server command is in PATH:
   ```bash
   which npx  # Should return a path
   ```

2. **Slow server startup**: If your server takes >60s to start, this is unusual but you can modify the registration timeout in code (default is 60s)

3. **Environment variables missing**: Check MCP server logs to see what's missing:
   ```bash
   cat ~/.mcpbr_state/logs/{instance_id}_mcp.log
   ```

## Evaluation Issues

### Patch Not Applying

**Symptom**: "Patch does not apply" error

**Explanation**: The agent's changes don't apply cleanly to the original repository state.

**This can happen when**:

- Agent modified files that conflict with test patches
- Agent created files instead of modifying existing ones
- Git state is inconsistent

**Note**: This is often an agent behavior issue, not an mcpbr bug.

### Tests Failing

**Symptom**: Tests fail even though patch applies

**Debug steps**:

1. Check per-instance logs for test output:
   ```bash
   cat logs/instance_id_mcp_*.json | jq '.events[-5:]'
   ```

2. Review the fail_to_pass results in JSON output

3. The agent may have made an incorrect fix

### No Patch Generated

**Symptom**: "No changes made by Claude Code"

**Possible causes**:

1. Agent didn't find a solution
2. Agent made changes then reverted them
3. Max iterations reached without completing

**Solutions**:

1. Increase max_iterations:
   ```yaml
   max_iterations: 30
   ```

2. Review logs to understand agent behavior

## Getting Help

### Gathering Debug Information

When reporting issues, include:

```bash
# Version info
mcpbr --version
python --version
docker --version

# Environment
echo $ANTHROPIC_API_KEY | head -c 10  # First 10 chars only

# Run with verbose logging
mcpbr run -c config.yaml -n 1 -vv --log-dir debug-logs/
```

### Where to Get Help

- [GitHub Issues](https://github.com/greynewell/mcpbr/issues) - Bug reports
- [GitHub Discussions](https://github.com/greynewell/mcpbr/discussions) - Questions

### Common Log Locations

| Log Type | Location |
|----------|----------|
| Per-instance logs | `--log-dir` directory |
| Single log file | `--log-file` path |
| Docker logs | `docker logs <container_id>` |
