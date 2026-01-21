# Configuration Templates

mcpbr provides pre-built configuration templates for common MCP server scenarios, making it easy to get started quickly.

## Quick Start

List available templates:

```bash
mcpbr templates
```

Create a config from a template:

```bash
mcpbr init -t filesystem
```

Interactive template selection:

```bash
mcpbr init -i
```

## Available Templates

### File Operations

#### Filesystem Server (Basic)
**Template ID:** `filesystem`

Basic filesystem access with the official Anthropic MCP server. This is the recommended starting point for most users.

```bash
mcpbr init -t filesystem
```

**Features:**
- Official Anthropic filesystem server
- Full read/write access to task workspace
- SWE-bench benchmark
- 10 task sample for quick testing

**Tags:** `filesystem`, `basic`, `official`, `recommended`

#### Filesystem Server (Read-Only)
**Template ID:** `filesystem-readonly`

Read-only filesystem access for safe exploration without modification risks.

```bash
mcpbr init -t filesystem-readonly
```

**Features:**
- Official Anthropic filesystem server
- Read-only mode for safety
- Perfect for analysis tasks
- Same settings as basic template

**Tags:** `filesystem`, `readonly`, `safe`, `official`

### Code Analysis

#### Supermodel Codebase Analysis
**Template ID:** `supermodel`

Advanced codebase analysis with the Supermodel MCP server.

```bash
mcpbr init -t supermodel
```

**Features:**
- Advanced code analysis capabilities
- Requires SUPERMODEL_API_KEY environment variable
- Extended timeout for complex analysis
- Reduced concurrency for API rate limits

**Tags:** `codebase`, `analysis`, `advanced`, `api-key`

**Note:** Set `SUPERMODEL_API_KEY` environment variable before running.

### Security

#### CyberGym Security Testing
**Template ID:** `cybergym-basic`

Security vulnerability testing with CyberGym benchmark at basic difficulty.

```bash
mcpbr init -t cybergym-basic
```

**Features:**
- CyberGym benchmark for PoC generation
- Level 1 difficulty (basic context)
- 5 task sample
- Standard timeout

**Tags:** `security`, `cybergym`, `vulnerability`, `basic`

#### CyberGym Advanced Security
**Template ID:** `cybergym-advanced`

Advanced security testing with maximum context (level 3).

```bash
mcpbr init -t cybergym-advanced
```

**Features:**
- CyberGym benchmark
- Level 3 difficulty (maximum context)
- Extended timeout for complex exploits
- Increased iteration limit

**Tags:** `security`, `cybergym`, `vulnerability`, `advanced`

### Testing

#### Quick Test (Single Task)
**Template ID:** `quick-test`

Fast single-task evaluation for quick testing and development.

```bash
mcpbr init -t quick-test
```

**Features:**
- Single task evaluation
- Single concurrent task
- Standard timeout
- Perfect for development/debugging

**Tags:** `testing`, `quick`, `development`, `single-task`

### Production

#### Production Evaluation
**Template ID:** `production`

Full-scale production evaluation with optimal settings.

```bash
mcpbr init -t production
```

**Features:**
- Full dataset (no sampling)
- Extended timeout (600s)
- High concurrency (8 tasks)
- Maximum iterations (30)
- Pre-built images enabled

**Tags:** `production`, `full-scale`, `performance`

### Custom

#### Custom Python MCP Server
**Template ID:** `custom-python`

Template for custom Python-based MCP servers.

```bash
mcpbr init -t custom-python
```

**Features:**
- Python command with module format
- Debug logging enabled
- Standard evaluation settings
- Ready to customize

**Tags:** `custom`, `python`, `development`

**Note:** Update `args` to point to your Python MCP server module.

#### Custom Node.js MCP Server
**Template ID:** `custom-node`

Template for custom Node.js-based MCP servers.

```bash
mcpbr init -t custom-node
```

**Features:**
- Node.js runtime
- Production environment
- Standard evaluation settings
- Ready to customize

**Tags:** `custom`, `nodejs`, `development`

**Note:** Update `args` to point to your Node.js server file.

## Using Templates

### Basic Usage

Create a config file using a template:

```bash
mcpbr init -t <template-id> -o config.yaml
```

Example:

```bash
mcpbr init -t filesystem -o my-config.yaml
```

### Interactive Mode

Launch interactive mode to select a template and customize values:

```bash
mcpbr init -i
```

This will:
1. Display all templates organized by category
2. Let you select a template
3. Optionally customize key values (sample size, timeout, concurrency)
4. Generate the config file

### Listing Templates

List all available templates:

```bash
mcpbr templates
```

Filter by category:

```bash
mcpbr templates -c Security
```

Filter by tag:

```bash
mcpbr templates --tag quick
```

### Template Customization

After creating a config from a template, you can edit it to:
- Adjust sample sizes
- Change timeout values
- Modify MCP server arguments
- Add custom prompts
- Configure environment variables

Example workflow:

```bash
# Create from template
mcpbr init -t filesystem

# Edit the config
vim mcpbr.yaml

# Run evaluation
mcpbr run -c mcpbr.yaml
```

## Template Categories

### File Operations
Templates for filesystem access and file manipulation.

### Code Analysis
Templates for advanced code analysis and understanding.

### Security
Templates for security testing and vulnerability analysis.

### Testing
Templates optimized for development and testing workflows.

### Production
Templates for production-scale evaluations.

### Custom
Templates for custom MCP server implementations.

## Template Tags

Templates are tagged to help you find the right one:

- `basic` - Simple, beginner-friendly templates
- `advanced` - Complex templates with more features
- `official` - Official Anthropic MCP servers
- `recommended` - Recommended for most users
- `quick` - Fast, minimal templates for testing
- `production` - Production-ready settings
- `custom` - Customizable templates
- `filesystem` - File operation templates
- `security` - Security testing templates
- `cybergym` - CyberGym benchmark templates
- `safe` - Read-only or safe-mode templates
- `readonly` - Read-only filesystem access

## Best Practices

### For Development

Use `quick-test` template for rapid iteration:

```bash
mcpbr init -t quick-test
mcpbr run -c mcpbr.yaml
```

### For Testing MCP Servers

Start with `filesystem` template and customize:

```bash
mcpbr init -t filesystem
# Edit mcpbr.yaml to point to your MCP server
mcpbr run -c mcpbr.yaml -n 5  # Test with 5 tasks first
```

### For Security Research

Use CyberGym templates:

```bash
# Start with basic
mcpbr init -t cybergym-basic
mcpbr run -c mcpbr.yaml

# Progress to advanced
mcpbr init -t cybergym-advanced -o cybergym-adv.yaml
mcpbr run -c cybergym-adv.yaml
```

### For Production Evaluations

Use production template with full dataset:

```bash
mcpbr init -t production
# Review and adjust settings
mcpbr run -c mcpbr.yaml -o results.json -r report.md
```

## Creating Custom Templates

Templates are defined in `src/mcpbr/templates.py`. To add a new template:

1. Define a new `Template` instance in the `TEMPLATES` dictionary
2. Specify all required fields: id, name, description, category, config, tags
3. Ensure the config contains all required fields
4. Add appropriate tags for discoverability

Example:

```python
"my-template": Template(
    id="my-template",
    name="My Custom Template",
    description="Description of what this template does",
    category="Custom",
    config={
        "mcp_server": {
            "command": "npx",
            "args": ["-y", "my-mcp-server", "{workdir}"],
            "env": {},
        },
        "provider": "anthropic",
        "agent_harness": "claude-code",
        "model": DEFAULT_MODEL,
        "benchmark": "swe-bench",
        "sample_size": 10,
        "timeout_seconds": 300,
        "max_concurrent": 4,
        "max_iterations": 10,
    },
    tags=["custom", "my-tag"],
)
```

## FAQ

### Which template should I use?

- **First time user?** Use `filesystem` template
- **Testing your MCP server?** Start with `quick-test`
- **Security research?** Use `cybergym-basic` or `cybergym-advanced`
- **Production evaluation?** Use `production` template
- **Custom server?** Use `custom-python` or `custom-node`

### Can I modify a template-generated config?

Yes! Templates are just starting points. Edit the generated YAML file to customize any settings.

### How do I see what a template contains?

Use `mcpbr init -t <template-id>` to generate a config file and inspect it, or check the template source in `src/mcpbr/templates.py`.

### Can I create my own templates?

Yes! Add them to `src/mcpbr/templates.py` following the existing pattern. Consider submitting a PR to share useful templates with the community.

## Examples

### Quick Test Workflow

```bash
# List templates
mcpbr templates

# Create quick test config
mcpbr init -t quick-test

# Run single task
mcpbr run -c mcpbr.yaml -v

# If successful, scale up
mcpbr init -t filesystem -o full-test.yaml
# Edit sample_size to 25
mcpbr run -c full-test.yaml -o results.json
```

### Security Testing Workflow

```bash
# Create CyberGym config
mcpbr init -t cybergym-basic

# Run evaluation
mcpbr run -c mcpbr.yaml -v --log-dir logs/

# Analyze results
# If good, try advanced level
mcpbr init -t cybergym-advanced -o cybergym-adv.yaml
mcpbr run -c cybergym-adv.yaml -o results-adv.json
```

### Custom Server Workflow

```bash
# Create custom Python template
mcpbr init -t custom-python -o my-server.yaml

# Edit to point to your server
# Update: args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]

# Test with one task
mcpbr run -c my-server.yaml -n 1 -vv

# Scale up gradually
mcpbr run -c my-server.yaml -n 5
mcpbr run -c my-server.yaml -n 25
```

## See Also

- [Configuration Guide](configuration.md) - Detailed config reference
- [CLI Reference](cli.md) - All command options
- [Quick Start](../README.md#quick-start) - Getting started guide
