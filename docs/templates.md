---
faq:
  - q: "What are MCP server configuration templates?"
    a: "Templates are pre-configured settings for popular MCP servers that make it easy to get started without manually writing YAML configuration files."
  - q: "How do I list available templates?"
    a: "Run 'mcpbr config list' to see all available templates with their descriptions and requirements."
  - q: "How do I use a template?"
    a: "Use 'mcpbr config apply <template-id>' to create a configuration file from a template, or use 'mcpbr init -i' for interactive selection."
  - q: "Can I contribute my own templates?"
    a: "Yes! Create a YAML template file following the template format and submit a pull request to add it to the built-in templates."
---

# Configuration Templates

Configuration templates provide pre-configured settings for popular MCP servers, making it easy to get started with mcpbr without writing YAML configuration files from scratch.

## Using Templates

### List Available Templates

View all available templates:

```bash
mcpbr config list
```

This displays a table showing:

- **ID**: Template identifier used to apply the template
- **Name**: Human-readable name
- **Package**: NPM or Python package name
- **Requires API Key**: Whether an API key is needed
- **Description**: What the MCP server does

### Apply a Template

Create a configuration file from a template:

```bash
# Apply filesystem template (default output: mcpbr.yaml)
mcpbr config apply filesystem

# Specify custom output path
mcpbr config apply brave-search -o brave.yaml

# Overwrite existing config
mcpbr config apply github --force
```

### Interactive Template Selection

Use the interactive wizard when running `init`:

```bash
mcpbr init -i
```

This shows all available templates and lets you choose one interactively.

### Use Template Directly with Init

Apply a template while creating initial configuration:

```bash
# Use template during init
mcpbr init -t filesystem

# Custom output path with template
mcpbr init -t postgres -o postgres-config.yaml
```

## Available Templates

### Filesystem Server

**ID**: `filesystem`
**Package**: `@modelcontextprotocol/server-filesystem`
**API Key Required**: No

Provides file system access tools for reading, writing, and managing files and directories within the task workspace.

**Use Cases**:
- Reading and analyzing code files
- Writing patches and modifications
- File system navigation and search

**Example**:
```bash
mcpbr config apply filesystem
```

### Brave Search

**ID**: `brave-search`
**Package**: `@modelcontextprotocol/server-brave-search`
**API Key Required**: Yes (`BRAVE_API_KEY`)

Web search capabilities using the Brave Search API for finding information online.

**Use Cases**:
- Looking up documentation
- Finding error solutions
- Researching technical concepts

**Setup**:
1. Get API key from [Brave Search API](https://brave.com/search/api/)
2. Set environment variable: `export BRAVE_API_KEY="your-key"`
3. Apply template: `mcpbr config apply brave-search`

### PostgreSQL Database

**ID**: `postgres`
**Package**: `@modelcontextprotocol/server-postgres`
**API Key Required**: No (requires connection string)

Query and manage PostgreSQL databases with SQL execution and schema introspection.

**Use Cases**:
- Database schema analysis
- SQL query generation
- Database migrations

**Setup**:
1. Set connection string: `export POSTGRES_CONNECTION_STRING="postgresql://user:pass@localhost:5432/db"`
2. Apply template: `mcpbr config apply postgres`

### SQLite Database

**ID**: `sqlite`
**Package**: `@modelcontextprotocol/server-sqlite`
**API Key Required**: No

Query and manage SQLite databases with SQL execution and schema introspection.

**Use Cases**:
- Local database analysis
- Testing database queries
- Lightweight data storage

**Example**:
```bash
mcpbr config apply sqlite
```

### GitHub

**ID**: `github`
**Package**: `@modelcontextprotocol/server-github`
**API Key Required**: Yes (`GITHUB_PERSONAL_ACCESS_TOKEN`)

Interact with GitHub repositories, issues, pull requests, and other GitHub resources.

**Use Cases**:
- Creating issues and PRs
- Repository analysis
- GitHub API interactions

**Setup**:
1. Create token at [GitHub Settings](https://github.com/settings/tokens)
2. Set environment variable: `export GITHUB_PERSONAL_ACCESS_TOKEN="your-token"`
3. Apply template: `mcpbr config apply github`

### Google Maps

**ID**: `google-maps`
**Package**: `@modelcontextprotocol/server-google-maps`
**API Key Required**: Yes (`GOOGLE_MAPS_API_KEY`)

Access Google Maps APIs for geocoding, places, directions, and other location services.

**Use Cases**:
- Location-based features
- Geocoding and reverse geocoding
- Route planning

**Setup**:
1. Get API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Set environment variable: `export GOOGLE_MAPS_API_KEY="your-key"`
3. Apply template: `mcpbr config apply google-maps`

### Slack

**ID**: `slack`
**Package**: `@modelcontextprotocol/server-slack`
**API Key Required**: Yes (`SLACK_BOT_TOKEN`)

Send messages, manage channels, and interact with Slack workspaces.

**Use Cases**:
- Sending notifications
- Channel management
- Slack automation

**Setup**:
1. Create Slack app at [Slack API](https://api.slack.com/apps)
2. Get bot token and set: `export SLACK_BOT_TOKEN="xoxb-your-token"`
3. Apply template: `mcpbr config apply slack`

## Template Format

Templates are YAML files with two main sections:

1. **Metadata**: Information about the template
2. **Configuration**: The actual mcpbr configuration

### Example Template Structure

```yaml
# Template Metadata
id: my-server
name: My MCP Server
description: Description of what this server does
package: "@org/my-mcp-server"
requires_api_key: true
env_vars:
  - MY_API_KEY

# Configuration
config:
  mcp_server:
    name: my-server
    command: npx
    args:
      - "-y"
      - "@org/my-mcp-server"
    env:
      MY_API_KEY: "${MY_API_KEY}"

  provider: anthropic
  agent_harness: claude-code
  model: sonnet
  benchmark: swe-bench
  sample_size: 10
  timeout_seconds: 300
  max_concurrent: 4
  max_iterations: 10
```

### Metadata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for the template |
| `name` | Yes | Human-readable name |
| `description` | Yes | What the MCP server does |
| `package` | No | NPM or Python package name |
| `requires_api_key` | No | Whether an API key is needed (default: false) |
| `env_vars` | No | List of required environment variables |

### Configuration Section

The `config` section contains a complete mcpbr configuration. See the [Configuration Guide](configuration.md) for details on all available options.

## Contributing Templates

We welcome community-contributed templates for popular MCP servers!

### Creating a Template

1. Create a new YAML file in `src/mcpbr/data/templates/`
2. Follow the template format above
3. Validate your template:
   ```bash
   uv run pytest tests/test_templates.py -k "test_builtin_templates_valid"
   ```

### Submission Guidelines

When submitting a template:

1. **Use clear IDs**: Use lowercase with hyphens (e.g., `my-server`)
2. **Provide good descriptions**: Explain what the server does clearly
3. **Document requirements**: List all required environment variables
4. **Test thoroughly**: Ensure the template works end-to-end
5. **Add examples**: Include use cases in the description

### Template Checklist

- [ ] Template has unique ID
- [ ] Name and description are clear
- [ ] Package name is specified (if applicable)
- [ ] Environment variables are documented
- [ ] Configuration is valid and complete
- [ ] Template is added to built-in templates list
- [ ] Documentation is updated
- [ ] Tests pass

### Example Pull Request

```markdown
Title: Add template for XYZ MCP server

Description:
This PR adds a configuration template for the XYZ MCP server, which provides
[description of functionality].

The template includes:
- Pre-configured command and arguments
- Environment variable setup for API authentication
- Sensible defaults for evaluation parameters

Checklist:
- [x] Template file created
- [x] Documentation updated
- [x] Tests pass
- [x] Example usage tested
```

## Template Validation

Templates are automatically validated to ensure:

- Required metadata fields are present
- Configuration has `mcp_server` section
- MCP server config includes `command` and `args`
- Environment variables are properly referenced
- No conflicting IDs with existing templates

Run validation:

```bash
uv run pytest tests/test_templates.py
```

## Best Practices

### 1. Use Descriptive IDs

Good:
- `filesystem`
- `brave-search`
- `postgres`

Bad:
- `fs`
- `search`
- `db`

### 2. Document Environment Variables

Always list required environment variables in the metadata:

```yaml
requires_api_key: true
env_vars:
  - API_KEY
  - OPTIONAL_CONFIG_VAR
```

### 3. Use ${VAR} Syntax

Reference environment variables using `${VAR}` syntax:

```yaml
env:
  API_KEY: "${API_KEY}"
```

### 4. Provide Reasonable Defaults

Set sensible defaults for evaluation parameters:

```yaml
sample_size: 10          # Small enough for testing
timeout_seconds: 300     # 5 minutes
max_concurrent: 4        # Moderate parallelism
max_iterations: 10       # Reasonable iteration limit
```

### 5. Include {workdir} Placeholder

Use `{workdir}` for workspace paths:

```yaml
args:
  - "-y"
  - "my-server"
  - "{workdir}"  # Will be replaced at runtime
```

## Troubleshooting

### Template Not Found

If a template doesn't appear in the list:

1. Check the template file is in `src/mcpbr/data/templates/`
2. Verify the YAML is valid: `cat template.yaml | python -m yaml`
3. Ensure the template has required metadata fields
4. Reinstall the package: `uv pip install -e .`

### Environment Variable Not Expanded

If `${VAR}` isn't being replaced:

1. Check the variable is set: `echo $VAR`
2. Verify it's in the `env` section of `mcp_server`
3. Ensure you're using `${VAR}` not `$VAR`

### Template Validation Fails

Run the validator to see specific errors:

```python
from mcpbr.templates import get_template, validate_template

template = get_template("my-template")
errors = validate_template(template)
print(errors)
```

## Next Steps

- [Configuration Guide](configuration.md) - Full configuration reference
- [CLI Reference](cli.md) - Command-line options
- [Contributing Guide](contributing.md) - How to contribute to mcpbr
