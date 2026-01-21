# Frequently Asked Questions (FAQ)

Quick answers to common questions about mcpbr. For detailed information, follow the links to the full documentation.

**New to mcpbr?** Check out the [Best Practices Guide](best-practices.md) for tips on getting the most value from your evaluations.

## Getting Started

### What is mcpbr?

mcpbr (Model Context Protocol Benchmark Runner) is a tool for evaluating MCP servers against real GitHub issues from benchmarks like SWE-bench and CyberGym. It provides quantitative comparison between tool-assisted and baseline agent performance, helping you prove whether your MCP server actually improves AI coding capabilities.

### How do I get started with mcpbr?

1. Install mcpbr: `pip install mcpbr`
2. Set your API key: `export ANTHROPIC_API_KEY="sk-ant-..."`
3. Generate a config: `mcpbr init`
4. Run an evaluation: `mcpbr run -c mcpbr.yaml -n 1 -v`

See the [Installation Guide](installation.md) for detailed setup instructions.

### What are the prerequisites?

- **Python 3.11+** - Required for mcpbr
- **Docker** - Must be running (verify with `docker info`)
- **Claude Code CLI** - Install with `npm install -g @anthropic-ai/claude-code`
- **Anthropic API key** - Get one at [console.anthropic.com](https://console.anthropic.com/)
- **Network access** - For pulling Docker images and API calls

See [Prerequisites](installation.md#prerequisites) for more details.

### Which models does mcpbr support?

mcpbr supports all Claude models from Anthropic:

- **Claude Opus 4.5** - Alias: `opus` or `claude-opus-4-5-20251101`
- **Claude Sonnet 4.5** - Alias: `sonnet` or `claude-sonnet-4-5-20250929` (recommended)
- **Claude Haiku 4.5** - Alias: `haiku` or `claude-haiku-4-5-20251001`

Run `mcpbr models` to see the full list. See [Supported Models](installation.md#supported-models).

### Does mcpbr work on Apple Silicon Macs?

Yes! mcpbr works on M1/M2/M3 Macs using x86_64 Docker images via emulation. This may be slower than native ARM64 but ensures compatibility with all SWE-bench tasks. Install Rosetta 2 for best performance:

```bash
softwareupdate --install-rosetta
```

See [Apple Silicon Notes](installation.md#apple-silicon-notes).

### How do I install the Claude Code CLI?

```bash
npm install -g @anthropic-ai/claude-code
```

Verify the installation:

```bash
which claude  # Should return the path to the CLI
```

See [Claude Code CLI Installation](installation.md#claude-code-cli).

## Installation & Setup

### How do I install mcpbr?

From PyPI (recommended):

```bash
pip install mcpbr
```

From source:

```bash
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr
pip install -e .
```

See [Installation Methods](installation.md#installation-methods).

### How do I verify my installation?

```bash
# Check mcpbr version
mcpbr --version

# List supported models
mcpbr models

# Generate a test config
mcpbr init -o test-config.yaml
```

See [Verify Installation](installation.md#verify-installation).

### How do I set my API key?

Set the `ANTHROPIC_API_KEY` environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Add to your shell profile (`.bashrc`, `.zshrc`) for persistence:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
```

## Configuration

### How do I create a configuration file?

Use the `init` command to generate a starter config:

```bash
mcpbr init  # Creates mcpbr.yaml
```

For specific MCP servers, use templates:

```bash
# List available templates
mcpbr templates

# Use a specific template
mcpbr init -t filesystem

# Interactive template selection
mcpbr init -i
```

See [Configuration Templates](templates.md).

### How do I configure my MCP server?

Edit the `mcp_server` section in your config file:

```yaml
mcp_server:
  command: "npx"
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"
  env: {}
```

- **command**: Executable to run (e.g., `npx`, `python`, `node`)
- **args**: Command arguments. Use `{workdir}` as placeholder for the task repository path
- **env**: Environment variables for the server

See [MCP Server Configuration](configuration.md#mcp-server-section).

### What is the {workdir} placeholder?

`{workdir}` is replaced at runtime with the path to the task repository inside the Docker container (typically `/workspace`). This allows your MCP server to access the codebase.

See [The {workdir} Placeholder](configuration.md#the-workdir-placeholder).

### How do I use environment variables in config?

Reference environment variables using `${VAR_NAME}` syntax:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

The variable will be expanded from your shell environment at runtime.

See [Environment Variables](configuration.md#environment-variables).

### What configuration parameters are available?

Key parameters:

- **mcp_server** - MCP server command, args, and environment
- **provider** - LLM provider (`anthropic`)
- **agent_harness** - Agent backend (`claude-code`)
- **model** - Model alias or full ID (`sonnet`, `opus`, `haiku`)
- **benchmark** - Benchmark to run (`swe-bench` or `cybergym`)
- **dataset** - HuggingFace dataset (optional, benchmark provides default)
- **sample_size** - Number of tasks (null = full dataset)
- **timeout_seconds** - Timeout per task (default: 300)
- **max_concurrent** - Parallel task limit (default: 4)
- **max_iterations** - Max agent turns per task (default: 10)

See [Configuration Reference](configuration.md#configuration-reference).

### How do I customize the agent prompt?

Use the `agent_prompt` field:

```yaml
agent_prompt: |
  Fix the following bug in this repository:

  {problem_statement}

  Make the minimal changes necessary to fix the issue.
```

Use `{problem_statement}` as a placeholder for the task description. You can also override via CLI:

```bash
mcpbr run -c config.yaml --prompt "Fix this: {problem_statement}"
```

See [Custom Agent Prompt](configuration.md#custom-agent-prompt).

## Benchmark Selection

### What benchmarks does mcpbr support?

mcpbr supports two benchmarks:

1. **SWE-bench** - Bug fixing in Python repositories, evaluated with test suites
2. **CyberGym** - Security exploit generation in C/C++ projects, evaluated by crash detection

Run `mcpbr benchmarks` to list available benchmarks.

See [Benchmarks Guide](benchmarks.md).

### How do I choose between SWE-bench and CyberGym?

- **SWE-bench**: Use for testing code exploration, bug fixing, and general software engineering tasks
- **CyberGym**: Use for security research, vulnerability analysis, and exploit generation

```bash
# Run SWE-bench (default)
mcpbr run -c config.yaml

# Run CyberGym
mcpbr run -c config.yaml --benchmark cybergym --level 2
```

See [Comparing Benchmarks](benchmarks.md#comparing-benchmarks).

### What are CyberGym difficulty levels?

CyberGym supports 4 difficulty levels (0-3) that control context given to the agent:

- **Level 0**: Minimal context (project name and bug ID only) - hardest
- **Level 1**: Adds vulnerability type information
- **Level 2**: Includes vulnerability type and description
- **Level 3**: Maximum context with detailed instructions - easiest

```bash
mcpbr run -c config.yaml --benchmark cybergym --level 2
```

See [Difficulty Levels](benchmarks.md#difficulty-levels).

### How many tasks should I run?

Start small, then scale up:

- **Development/Testing**: 1-5 tasks
- **Validation**: 10-25 tasks
- **Comprehensive**: 50-100 tasks or full dataset (null sample_size)

```bash
# Quick test
mcpbr run -c config.yaml -n 1 -v

# Validation run
mcpbr run -c config.yaml -n 25

# Full dataset
mcpbr run -c config.yaml
```

### Can I run specific tasks?

Yes, use the `-t` or `--task` flag:

```bash
mcpbr run -c config.yaml -t astropy__astropy-12907 -t django__django-11099
```

You can specify multiple task IDs.

## Running Evaluations

### How do I run my first evaluation?

```bash
# Generate config
mcpbr init

# Run with 1 task and verbose output
mcpbr run -c mcpbr.yaml -n 1 -v
```

See [Quick Start](index.md#quick-start).

### What do the run flags mean?

Common flags:

- `-c, --config PATH` - Path to YAML configuration file (required)
- `-n, --sample INTEGER` - Number of tasks to run
- `-v, --verbose` - Verbose output (`-vv` for very verbose)
- `-M, --mcp-only` - Run only MCP evaluation (skip baseline)
- `-B, --baseline-only` - Run only baseline evaluation (skip MCP)
- `-o, --output PATH` - Save JSON results
- `-r, --report PATH` - Save Markdown report
- `--log-dir PATH` - Directory for per-instance logs

See [CLI Reference](cli.md#mcpbr-run).

### How long does an evaluation take?

Depends on several factors:

- **Task complexity**: 2-10 minutes per task on average
- **Sample size**: 1 task vs. 300 tasks
- **Timeout setting**: Default 300s (5 min) per task
- **Concurrency**: 4 parallel tasks (default)
- **Platform**: Slower on Apple Silicon (emulation)

Example: 25 tasks with 4 concurrent = ~30-60 minutes total

### How do I speed up evaluations?

1. Increase concurrency:
   ```yaml
   max_concurrent: 8
   ```

2. Use a faster model:
   ```yaml
   model: "haiku"  # Faster than opus/sonnet
   ```

3. Reduce sample size for testing:
   ```bash
   mcpbr run -c config.yaml -n 5
   ```

4. Use pre-built Docker images (enabled by default)

See [Performance Issues](troubleshooting.md#performance-issues).

### Can I run only the MCP agent or baseline?

Yes:

```bash
# Only MCP agent
mcpbr run -c config.yaml -M

# Only baseline agent
mcpbr run -c config.yaml -B
```

This is useful for testing your MCP server without waiting for baseline results.

### How do I pause or resume evaluations?

mcpbr doesn't currently support pause/resume natively, but you can:

1. Use `--task` to run specific tasks
2. Save results with `--output results.json`
3. Run remaining tasks separately
4. Manually combine results

Future versions may include automatic checkpoint/resume.

## MCP Server Setup

### How do I test my MCP server with mcpbr?

1. Configure your server in the config file:
   ```yaml
   mcp_server:
     command: "python"
     args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]
   ```

2. Test standalone first:
   ```bash
   python -m my_mcp_server --workspace /tmp/test
   ```

3. Run a quick mcpbr test:
   ```bash
   mcpbr run -c config.yaml -n 1 -v -M
   ```

See [Testing Your Server](mcp-integration.md#testing-your-server).

### What MCP servers work with mcpbr?

Any MCP server that exposes tools for file operations, code search, or codebase analysis can be tested. Common examples:

- **Anthropic filesystem server** - Basic file operations
- **Custom Python servers** - Domain-specific tools
- **Supermodel** - Codebase analysis and semantic search
- **Custom Node.js servers** - API integrations

See [Example Configurations](mcp-integration.md#example-configurations).

### How does mcpbr register MCP servers?

mcpbr uses the Claude Code CLI's `claude mcp add` command to register your MCP server before each agent run. Tools from your server appear with the `mcp__` prefix (e.g., `mcp__read_file`).

See [How mcpbr Uses MCP](mcp-integration.md#how-mcpbr-uses-mcp).

### Why would I use an MCP server vs. built-in tools?

MCP servers can provide specialized capabilities:

- **Semantic code search** - Beyond simple text grep
- **Codebase indexing** - Fast symbol lookup and references
- **AST analysis** - Parse and analyze code structure
- **Domain-specific operations** - Custom tools for your use case
- **API integrations** - External data sources

These can improve the agent's ability to understand and fix bugs compared to basic file operations.

See [MCP Server Integration](mcp-integration.md).

### My MCP server isn't starting - how do I debug it?

1. Test the server independently:
   ```bash
   npx -y @modelcontextprotocol/server-filesystem /tmp/test
   ```

2. Check environment variables are set:
   ```bash
   echo $SUPERMODEL_API_KEY  # If using an API-based server
   ```

3. Verify the command exists:
   ```bash
   which npx  # or python, node, etc.
   ```

4. Check mcpbr logs with verbose output:
   ```bash
   mcpbr run -c config.yaml -n 1 -vv
   ```

See [Server Not Starting](troubleshooting.md#server-not-starting).

### How do I check if my MCP tools are being used?

1. Run with verbose output:
   ```bash
   mcpbr run -c config.yaml -n 1 -v
   ```

2. Look for tool calls like:
   ```text
   14:23:22 astropy-12907:mcp    > mcp__mcpbr__read_file
   ```

3. Check tool usage in JSON results:
   ```json
   {
     "tool_usage": {
       "mcp__mcpbr__read_file": 15,
       "Bash": 27
     }
   }
   ```

See [Check Tool Usage](mcp-integration.md#check-tool-usage).

## Result Interpretation

### What does "resolved" mean?

A task is **resolved** when:

1. The agent generated a patch/solution
2. The patch applied cleanly to the repository
3. All FAIL_TO_PASS tests pass (tests that should pass after the fix)
4. All PASS_TO_PASS tests pass (regression tests that should remain passing)

For CyberGym: PoC crashes pre-patch AND doesn't crash post-patch.

See [What "Resolved" Means](evaluation-results.md#what-resolved-means).

### How do I interpret the improvement percentage?

The improvement shows how much better the MCP agent performed relative to baseline:

```
improvement = ((mcp_rate - baseline_rate) / baseline_rate) × 100
```

Example: If MCP resolves 32% and baseline resolves 20%:
```
improvement = ((0.32 - 0.20) / 0.20) × 100 = +60%
```

- **Positive**: MCP agent performed better
- **Negative**: Baseline performed better
- **~0%**: Similar performance

See [Improvement Calculation](evaluation-results.md#improvement-calculation).

### What output formats are available?

- **Console** - Real-time progress and summary tables
- **JSON** (`--output`) - Structured data for programmatic analysis
- **YAML** (`--output-yaml`) - Human-readable structured format
- **Markdown** (`--report`) - Report for team reviews
- **JUnit XML** (`--output-junit`) - For CI/CD integration
- **Per-instance logs** (`--log-dir`) - Detailed debugging information

```bash
mcpbr run -c config.yaml -o results.json -y results.yaml -r report.md --log-dir logs/
```

See [Understanding Evaluation Results](evaluation-results.md).

### Where can I find detailed logs?

Use the `--log-dir` flag to save per-instance logs:

```bash
mcpbr run -c config.yaml -v --log-dir logs/
```

This creates timestamped JSON files with full tool call traces for each task:

```
logs/
  astropy__astropy-12907_mcp_20260117_143052.json
  astropy__astropy-12907_baseline_20260117_143156.json
```

See [Per-Instance Logs](evaluation-results.md#per-instance-logs).

### How do I analyze tool usage?

Check the `tool_usage` field in JSON results:

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
- Better built-in alternatives available
- Tool discovery or registration issues

See [Tool Usage Analysis](evaluation-results.md#tool-usage-analysis).

### What if MCP and baseline have similar rates?

If both agents perform similarly:

- MCP tools may not provide additional value for these specific tasks
- Built-in tools may be sufficient
- Review tool usage to see if MCP tools are actually being used
- Consider testing on different tasks or benchmarks

See [Common Patterns](evaluation-results.md#common-patterns).

## Troubleshooting

### Docker is not running - how do I fix this?

Start Docker:

- **macOS**: `open -a Docker`
- **Linux**: `sudo systemctl start docker`
- **Windows**: Start Docker Desktop from Start menu

Verify with:
```bash
docker info
```

See [Docker Not Running](troubleshooting.md#docker-not-running).

### Claude CLI not found - what should I do?

Install the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify installation:

```bash
which claude
```

If installed but not found, add npm globals to PATH:

```bash
export PATH="$PATH:$(npm config get prefix)/bin"
```

See [Claude CLI Not Found](troubleshooting.md#claude-cli-not-found).

### Why is mcpbr slow on my Apple Silicon Mac?

mcpbr uses x86_64 Docker images for compatibility, which run via emulation on ARM64 Macs. This is normal and expected behavior.

To optimize:

1. Install Rosetta 2:
   ```bash
   softwareupdate --install-rosetta
   ```

2. Reduce concurrency:
   ```yaml
   max_concurrent: 2
   ```

3. Increase timeouts:
   ```yaml
   timeout_seconds: 600
   ```

See [Slow on Apple Silicon](troubleshooting.md#slow-on-apple-silicon).

### Tasks are timing out - what should I do?

Increase the timeout in your config:

```yaml
timeout_seconds: 600  # 10 minutes
```

Or reduce iterations if the agent is looping:

```yaml
max_iterations: 20
```

For testing, use a faster model:

```yaml
model: "haiku"
```

See [Task Timeouts](troubleshooting.md#task-timeouts).

### Pre-built Docker image not found - is this a problem?

mcpbr will fall back to building from scratch, which is less reliable but usually works. This warning is informational.

You can:

1. Manually pull the image:
   ```bash
   docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.INSTANCE_ID
   ```

2. Or disable pre-built images:
   ```bash
   mcpbr run -c config.yaml --no-prebuilt
   ```

See [Pre-built Image Not Found](troubleshooting.md#pre-built-image-not-found).

### How do I clean up Docker containers?

Use the cleanup command:

```bash
# Preview what would be removed
mcpbr cleanup --dry-run

# Remove orphaned containers
mcpbr cleanup

# Skip confirmation
mcpbr cleanup -f
```

See [Orphaned Docker Resources](troubleshooting.md#orphaned-docker-resources).

### API key is not working - how do I check?

Verify the key is set correctly:

```bash
echo $ANTHROPIC_API_KEY
```

The key should:
- Start with `sk-ant-`
- Have no extra whitespace
- Be exported in your current shell session

Re-export if needed:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

See [API Key Not Set](troubleshooting.md#api-key-not-set).

## Performance & Optimization

### How do I optimize evaluation performance?

1. **Increase concurrency** (if you have resources):
   ```yaml
   max_concurrent: 8
   ```

2. **Use pre-built images** (enabled by default):
   ```yaml
   use_prebuilt_images: true
   ```

3. **Use faster models for testing**:
   ```yaml
   model: "haiku"
   ```

4. **Reduce sample size during development**:
   ```bash
   mcpbr run -c config.yaml -n 5
   ```

5. **On Apple Silicon**, reduce concurrency to avoid resource contention:
   ```yaml
   max_concurrent: 2
   ```

### What's the difference between models?

- **Opus 4.5** - Most capable, highest cost, slowest
- **Sonnet 4.5** - Balanced performance and cost (recommended)
- **Haiku 4.5** - Fastest and cheapest, good for testing

For production evaluations, use Sonnet or Opus. For development, Haiku is sufficient.

### How do I reduce costs?

1. **Use Haiku for development**:
   ```yaml
   model: "haiku"
   ```

2. **Test with smaller samples**:
   ```bash
   mcpbr run -c config.yaml -n 10
   ```

3. **Reduce max iterations**:
   ```yaml
   max_iterations: 15  # Instead of 30
   ```

4. **Use shorter timeouts**:
   ```yaml
   timeout_seconds: 180  # 3 minutes
   ```

5. **Run only MCP or baseline**:
   ```bash
   mcpbr run -c config.yaml -M  # Skip baseline
   ```

### How much does an evaluation cost?

Costs depend on:
- **Model used** (Haiku < Sonnet < Opus)
- **Number of tasks** (25 vs. 300)
- **Task complexity** (tokens per task)
- **Iterations** (max_iterations setting)

Rough estimates for SWE-bench Lite (300 tasks) with Sonnet:
- Full evaluation: ~$50-150
- 25-task sample: ~$5-15
- Single task: ~$0.20-0.60

Use `--output-yaml` to track token usage and calculate exact costs.

## Docker & Environment

### What Docker images does mcpbr use?

For SWE-bench: Pre-built images from [Epoch AI's registry](https://github.com/orgs/Epoch-Research/packages) when available:

```
ghcr.io/epoch-research/swe-bench.eval.x86_64.INSTANCE_ID
```

For CyberGym: mcpbr builds custom images with compilation tools and sanitizers.

See [Pre-built Docker Images](architecture.md).

### How does mcpbr use Docker?

1. Creates an isolated container per task
2. Sets up the repository at the correct commit
3. Installs dependencies (or uses pre-built image)
4. Runs Claude Code CLI inside the container
5. Evaluates the solution
6. Cleans up the container

The agent runs **inside** the container so Python imports and tests work correctly.

### Can I run mcpbr without Docker?

No, Docker is required for:
- Isolated task environments
- Reproducible evaluations
- Consistent dependencies
- Safe code execution

Make sure Docker is running before starting evaluations.

### How do I see Docker container logs?

While running:

```bash
# List running mcpbr containers
docker ps | grep mcpbr

# View logs
docker logs <container_id>
```

Enable verbose mcpbr output:

```bash
mcpbr run -c config.yaml -vv
```

## Cost & Billing

### How can I estimate costs before running?

Rough cost estimates per task with Sonnet:
- Simple tasks: $0.20-0.40
- Average tasks: $0.40-0.80
- Complex tasks: $0.80-1.50

For a 25-task sample: ~$10-30 total
For full SWE-bench Lite (300 tasks): ~$100-300 total

Start with 1-5 tasks to gauge costs for your specific configuration.

### Does mcpbr track token usage?

Yes, the JSON output includes detailed token usage:

```json
{
  "tokens": {
    "input": 115,
    "output": 6542
  }
}
```

Save results with `--output` to analyze token consumption.

### Can I set a budget or limit?

mcpbr doesn't have built-in budget limits, but you can:

1. Use `sample_size` to limit tasks:
   ```yaml
   sample_size: 25
   ```

2. Use `timeout_seconds` to limit runtime per task:
   ```yaml
   timeout_seconds: 300
   ```

3. Use `max_iterations` to limit agent turns:
   ```yaml
   max_iterations: 15
   ```

Monitor costs through Anthropic Console.

### Are there any free tiers?

mcpbr itself is free and open-source. However, you need:

- **Anthropic API credits** - Check [console.anthropic.com](https://console.anthropic.com/) for current pricing
- **Docker** - Free for personal use

Infrastructure costs are minimal (local Docker execution).

## Advanced Usage

### Can I use mcpbr in CI/CD?

Yes! mcpbr supports CI/CD integration with:

- **JUnit XML output** for test reporting
- **Exit codes** for pass/fail status
- **Regression detection** with thresholds
- **Notifications** via Slack/Discord/Email

```bash
mcpbr run -c config.yaml \
  --output-junit junit.xml \
  --baseline-results baseline.json \
  --regression-threshold 0.1 \
  --slack-webhook https://hooks.slack.com/...
```

See [CI/CD Integration](best-practices.md#cicd-integration-patterns) for more details.

### How do I compare two MCP servers?

1. Create separate configs:
   ```bash
   mcpbr init -o server-a.yaml
   mcpbr init -o server-b.yaml
   ```

2. Run evaluations:
   ```bash
   mcpbr run -c server-a.yaml -o results-a.json
   mcpbr run -c server-b.yaml -o results-b.json
   ```

3. Compare resolution rates:
   ```python
   import json

   with open("results-a.json") as f:
       a = json.load(f)
   with open("results-b.json") as f:
       b = json.load(f)

   print(f"Server A: {a['summary']['mcp']['rate']:.1%}")
   print(f"Server B: {b['summary']['mcp']['rate']:.1%}")
   ```

See [Comparing Servers](mcp-integration.md#comparing-servers).

### How do I track regressions between versions?

Use regression detection:

```bash
# Run baseline with version 1.0
mcpbr run -c config.yaml -o baseline-v1.json

# Later, compare version 2.0
mcpbr run -c config.yaml \
  --baseline-results baseline-v1.json \
  --regression-threshold 0.1
```

This exits with code 1 if regression rate exceeds 10%, perfect for CI/CD.

See [Regression Detection](best-practices.md#regression-testing) for more details.

### Can I customize the task selection?

Yes, several ways:

1. **Use specific tasks**:
   ```bash
   mcpbr run -c config.yaml -t task1 -t task2
   ```

2. **Use sample size**:
   ```yaml
   sample_size: 50  # Random sample of 50 tasks
   ```

3. **Filter by repository** (requires code modification currently)

### How do I contribute to mcpbr?

We welcome contributions! Check out:

- [Good First Issues](https://github.com/greynewell/mcpbr/labels/good%20first%20issue)
- [Help Wanted](https://github.com/greynewell/mcpbr/labels/help%20wanted)
- [Contributing Guide](contributing.md)

Key areas:
- Output formats (CSV, XML)
- Configuration templates
- Documentation improvements
- Bug fixes and performance optimizations

## Additional Resources

### Where can I get help?

- **Documentation**: [greynewell.github.io/mcpbr](https://greynewell.github.io/mcpbr/)
- **GitHub Issues**: [github.com/greynewell/mcpbr/issues](https://github.com/greynewell/mcpbr/issues)
- **GitHub Discussions**: [github.com/greynewell/mcpbr/discussions](https://github.com/greynewell/mcpbr/discussions)

When reporting issues, include:
```bash
mcpbr --version
python --version
docker --version
```

See [Getting Help](troubleshooting.md#getting-help).

### How do I stay updated?

- **Star the repo**: [github.com/greynewell/mcpbr](https://github.com/greynewell/mcpbr)
- **Watch releases**: Get notifications for new versions
- **Follow the roadmap**: [Project Board](https://github.com/greynewell/mcpbr/projects/2)
- **Join discussions**: Share feedback and ideas

### Where can I find examples?

- **Examples**: Check the `examples/` directory for sample configurations
- **Templates**: [Template guide](templates.md#examples)
- **Documentation**: Each guide includes examples
- **Tests**: Check `tests/` directory for code examples

### What's on the roadmap?

Major upcoming features:

- **More benchmarks** - HumanEval, MBPP, GAIA, SWE-bench Verified
- **Better UX** - Real-time dashboard, interactive wizard
- **Platform expansion** - NPM package, GitHub Action, Homebrew
- **MCP testing suite** - Coverage analysis, performance profiling

See the [full roadmap](https://github.com/greynewell/mcpbr/projects/2) for details.

## Quick Reference

### Essential Commands

```bash
# List available commands
mcpbr --help

# Initialize config
mcpbr init
mcpbr init -t filesystem  # Use template
mcpbr init -i             # Interactive

# List options
mcpbr models      # Available models
mcpbr benchmarks  # Available benchmarks
mcpbr templates   # Configuration templates

# Run evaluation
mcpbr run -c config.yaml                # Full run
mcpbr run -c config.yaml -n 5 -v        # 5 tasks, verbose
mcpbr run -c config.yaml -M             # MCP only
mcpbr run -c config.yaml -o results.json # Save results

# Cleanup
mcpbr cleanup --dry-run  # Preview
mcpbr cleanup            # Remove orphaned containers
```

### Common Workflows

**Quick test:**
```bash
mcpbr init -t quick-test
mcpbr run -c mcpbr.yaml -v
```

**Full evaluation:**
```bash
mcpbr init -t production
mcpbr run -c mcpbr.yaml -o results.json -r report.md
```

**Debug MCP server:**
```bash
mcpbr run -c config.yaml -n 1 -vv --log-dir logs/
```

**CI/CD integration:**
```bash
mcpbr run -c config.yaml --output-junit junit.xml --baseline-results baseline.json --regression-threshold 0.1
```

---

**Still have questions?** Check the [full documentation](index.md) or [open an issue](https://github.com/greynewell/mcpbr/issues).
