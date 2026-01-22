# mcpbr Claude Code Skills

This directory contains specialized skills that make Claude Code an expert at using mcpbr.

## What are Skills?

Skills are instruction sets that teach Claude Code how to perform specific tasks correctly. When Claude works in this repository, it automatically detects these skills and gains domain expertise about mcpbr.

## Available Skills

### 1. `mcpbr-eval` - Run Benchmark

**Purpose:** Expert at running evaluations with proper validation

**Key Features:**
- Validates prerequisites (Docker, API keys, config files)
- Checks for common mistakes before running
- Supports all benchmarks (SWE-bench, CyberGym, MCPToolBench++)
- Provides actionable troubleshooting

**When to use:** Anytime you want to run an evaluation with mcpbr

**Example prompts:**
- "Run the SWE-bench benchmark with 10 tasks"
- "Evaluate my MCP server on CyberGym level 2"
- "Run a quick test with 1 task"

### 2. `mcpbr-config` - Generate Config

**Purpose:** Generates valid mcpbr configuration files

**Key Features:**
- Ensures critical `{workdir}` placeholder is included
- Validates MCP server commands
- Provides templates for common MCP servers
- Supports all benchmark types

**When to use:** When creating or modifying mcpbr configuration files

**Example prompts:**
- "Generate a config for my Python MCP server"
- "Create a config using the filesystem server"
- "Help me configure my custom MCP server"

### 3. `benchmark-swe-lite` - Quick Start

**Purpose:** Streamlined command for SWE-bench Lite evaluation

**Key Features:**
- Pre-configured for 5-task evaluation
- Sensible defaults for quick testing
- Includes runtime/cost estimates
- Perfect for demos and testing

**When to use:** For quick validation or demonstrations

**Example prompts:**
- "Run a quick SWE-bench Lite test"
- "Show me how mcpbr works"
- "Do a fast evaluation"

## How Skills Work

When you clone this repository and work with Claude Code:

1. Claude Code detects the `.claude-plugin/plugin.json` manifest
2. It loads all skills from the `skills/` directory
3. Each skill provides specialized knowledge about mcpbr commands
4. Claude automatically follows best practices without being told

## Skill Structure

Each skill is a directory containing a `SKILL.md` file:

```text
skills/
├── mcpbr-eval/
│   └── SKILL.md          # Instructions for running evaluations
├── mcpbr-config/
│   └── SKILL.md          # Instructions for config generation
└── benchmark-swe-lite/
    └── SKILL.md          # Quick-start instructions
```

Each `SKILL.md` contains:

1. **Frontmatter** - Metadata (name, description)
2. **Instructions** - Main skill content
3. **Examples** - Usage examples
4. **Constraints** - Critical requirements
5. **Troubleshooting** - Common issues and solutions

## Benefits

### Without Skills
```text
User: "Run the benchmark"
Claude: *tries `mcpbr run` without config, fails*
Claude: *forgets to check Docker, fails*
Claude: *uses wrong flags, fails*
```

### With Skills
```text
User: "Run the benchmark"
Claude: *checks Docker is running*
Claude: *verifies config exists*
Claude: *uses correct flags*
Claude: *evaluation succeeds*
```

## Testing

Skills are validated by comprehensive tests in `tests/test_claude_plugin.py`:

- Validates plugin manifest structure
- Checks skill file format and content
- Ensures critical keywords are present (Docker, {workdir}, etc.)
- Verifies documentation mentions all commands

Run skill tests:
```bash
uv run pytest tests/test_claude_plugin.py -v
```

## Adding New Skills

To add a new skill:

1. Create a new directory: `skills/my-skill/`
2. Create `SKILL.md` with frontmatter:
   ```markdown
   ---
   name: my-skill
   description: Brief description of what this skill does
   ---

   # Instructions
   [Your skill content here]
   ```
3. Add tests in `tests/test_claude_plugin.py`
4. Update this README

## Version Management

The plugin version in `.claude-plugin/plugin.json` is automatically synced with `pyproject.toml`:

```bash
# Sync versions manually
make sync-version

# Syncs automatically during
make build
pre-commit hooks
CI/CD checks
```

## Learn More

- **Plugin Manifest**: `.claude-plugin/plugin.json`
- **Tests**: `tests/test_claude_plugin.py`
- **Documentation**: Main README.md, CONTRIBUTING.md
- **Issue**: [#262](https://github.com/greynewell/mcpbr/issues/262)

## Contributing

When modifying skills:

1. Update the relevant `SKILL.md` file
2. Run tests: `uv run pytest tests/test_claude_plugin.py`
3. Run pre-commit: `pre-commit run --all-files`
4. Submit a PR with your changes

Skills should:
- Be clear and concise
- Include examples
- Emphasize critical requirements
- Provide troubleshooting guidance
- Reference actual mcpbr commands

## Questions?

Open an issue or check the main project documentation.
