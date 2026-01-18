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
  - q: "How do I clean up orphaned Docker containers?"
    a: "Run 'mcpbr cleanup' to find and remove orphaned containers. Use '--dry-run' first to preview what would be removed."
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

### Orphaned Containers

**Symptom**: Old mcpbr containers consuming resources

**Solution**:

```bash
# Preview what would be removed
mcpbr cleanup --dry-run

# Remove orphaned containers
mcpbr cleanup
```

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
