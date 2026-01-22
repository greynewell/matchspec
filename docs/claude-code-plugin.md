# Claude Code Plugin

The mcpbr Claude Code plugin makes Claude an expert at running benchmarks correctly. When you work with mcpbr in Claude Code, the plugin automatically provides specialized knowledge about commands, configuration, and best practices.

## Overview

The plugin consists of two components:

1. **Plugin manifest** (`.claude-plugin/plugin.json`) - Registers mcpbr with Claude Code
2. **Skills directory** (`skills/`) - Contains specialized instruction sets for specific tasks

When Claude Code detects the plugin in a repository, it automatically:

- Validates prerequisites before running commands
- Generates correct configuration files with required placeholders
- Uses appropriate CLI flags and options
- Provides helpful troubleshooting when issues occur
- Follows best practices without being explicitly instructed

## Installation

The plugin is bundled with mcpbr and activated automatically when you work in a cloned repository.

### Option 1: Clone the Repository (Recommended)

```bash
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr
```

That's it! Claude Code will automatically detect the `.claude-plugin/plugin.json` manifest and load all skills.

### Option 2: Install as a Standalone Plugin

If you want to use the plugin without cloning the full repository:

1. Copy the plugin files to your project:
   ```bash
   mkdir -p .claude-plugin
   cp /path/to/mcpbr/.claude-plugin/plugin.json .claude-plugin/
   cp -r /path/to/mcpbr/skills ./skills
   ```

2. Claude Code will detect the plugin next time you open the project.

### Option 3: Manual Installation (Advanced)

For custom setups, you can manually configure the plugin:

1. Create a `.claude-plugin` directory in your project root
2. Create `plugin.json` with the following structure:
   ```json
   {
     "name": "mcpbr",
     "version": "0.3.17",
     "description": "Expert benchmark runner for MCP servers using mcpbr",
     "schema_version": "1.0"
   }
   ```
3. Create a `skills/` directory with skill subdirectories (see [How It Works](#how-it-works) for details)

## Skills Reference

The plugin includes three specialized skills for common mcpbr tasks:

### 1. mcpbr-eval (run-benchmark)

Expert at running evaluations with proper validation.

**Purpose:** Execute benchmark evaluations with mcpbr while validating all prerequisites and avoiding common mistakes.

**Key Features:**

- Checks Docker is running before starting
- Verifies API keys are set
- Validates configuration files exist and are correct
- Supports all benchmarks (SWE-bench, CyberGym, MCPToolBench++)
- Provides actionable troubleshooting for errors

**When to Use:** Anytime you want to run a benchmark evaluation.

**Example Prompts:**

```text
"Run the SWE-bench benchmark with 10 tasks"
"Evaluate my MCP server on CyberGym level 2"
"Run a quick test with 1 task"
```

**What the Skill Does:**

1. Verifies Docker is running with `docker ps`
2. Checks for `ANTHROPIC_API_KEY` environment variable
3. Ensures config file exists (runs `mcpbr init` if needed)
4. Validates config has required `{workdir}` placeholder
5. Constructs correct `mcpbr run` command with appropriate flags
6. Monitors execution and provides troubleshooting if errors occur

**Common Validations:**

- Docker daemon is running
- API key is set in environment
- Config file exists and is valid YAML
- MCP server command is available (`npx`, `uvx`, `python`, etc.)
- `{workdir}` placeholder is present in server args
- Model and dataset names are valid

### 2. mcpbr-config (generate-config)

Generates valid mcpbr configuration files.

**Purpose:** Create correct YAML configuration files for MCP server benchmarking with all required fields and placeholders.

**Key Features:**

- Ensures critical `{workdir}` placeholder is included
- Validates MCP server commands exist
- Provides templates for common MCP servers
- Supports all benchmark types
- Prevents common configuration mistakes

**When to Use:** When creating or modifying mcpbr configuration files.

**Example Prompts:**

```text
"Generate a config for my Python MCP server"
"Create a config using the filesystem server"
"Help me configure my custom MCP server"
```

**What the Skill Does:**

1. Asks about your MCP server (command, args, env vars)
2. Selects appropriate template (npx, uvx, python, etc.)
3. Ensures `{workdir}` placeholder is in args array
4. Validates YAML syntax is correct
5. Saves config to `mcpbr.yaml` or specified path
6. Optionally tests config with a single task

**Configuration Templates:**

The skill provides pre-built templates for:

- Anthropic filesystem server (`@modelcontextprotocol/server-filesystem`)
- Python MCP servers via uvx
- Custom Node.js servers via npx
- Direct Python execution
- Servers requiring environment variables

**Critical Requirements:**

- `{workdir}` placeholder MUST be in `args` array
- Command must be an executable available in PATH
- YAML indentation must use spaces (not tabs)
- Environment variable references need quotes

### 3. benchmark-swe-lite (swe-bench-lite)

Quick-start command for SWE-bench Lite evaluation.

**Purpose:** Streamlined way to run SWE-bench Lite with sensible defaults for quick testing and demonstrations.

**Key Features:**

- Pre-configured for 5-task evaluation
- Includes default output files (results.json, report.md)
- Provides runtime and cost estimates
- Perfect for testing and demos

**When to Use:** For quick validation or demonstrations of mcpbr functionality.

**Example Prompts:**

```text
"Run a quick SWE-bench Lite test"
"Show me how mcpbr works"
"Do a fast evaluation"
```

**What the Skill Does:**

1. Checks prerequisites (Docker, API key, config)
2. Runs `mcpbr run` with 5 tasks from SWE-bench Lite
3. Saves results to `results.json` and `report.md`
4. Uses verbose output for visibility
5. Provides expected runtime/cost estimates

**Default Command:**

```bash
mcpbr run -c mcpbr.yaml --dataset SWE-bench/SWE-bench_Lite -n 5 -v -o results.json -r report.md
```

**Expected Performance:**

- **Runtime:** 15-30 minutes (depends on task complexity)
- **Cost:** $2-5 (depends on task complexity and model)

**Customization Options:**

- Change sample size: `-n 1` (quick test) or `-n 10` (more thorough)
- MCP-only evaluation: Add `-M` flag
- Very verbose output: Use `-vv` instead of `-v`
- Specific tasks: Use `-t <instance_id>` flag

## How It Works

### Plugin Architecture

```text
.claude-plugin/
└── plugin.json          # Manifest that registers the plugin

skills/
├── mcpbr-eval/
│   └── SKILL.md         # Instructions for running evaluations
├── mcpbr-config/
│   └── SKILL.md         # Instructions for config generation
└── benchmark-swe-lite/
    └── SKILL.md         # Quick-start instructions
```

### Skill File Format

Each skill is defined by a `SKILL.md` file with the following structure:

```markdown
---
name: skill-name
description: Brief description of what this skill does
---

# Instructions
[Main skill content with detailed instructions]

## Critical Constraints
[Non-negotiable requirements that MUST be followed]

## Common Pitfalls
[Mistakes to avoid]

## Examples
[Usage examples and code snippets]

## Troubleshooting
[Common issues and solutions]
```

### How Claude Uses Skills

When you ask Claude to perform a task in a repository with the plugin:

1. **Detection:** Claude Code detects `.claude-plugin/plugin.json`
2. **Loading:** All skills in `skills/` are loaded into Claude's context
3. **Selection:** Claude identifies which skill(s) are relevant to your request
4. **Execution:** Claude follows the skill's instructions and constraints
5. **Validation:** Critical requirements are checked before and during execution
6. **Troubleshooting:** If errors occur, skill provides actionable feedback

### Example Flow

**Without Plugin:**

```text
User: "Run the benchmark"
Claude: *tries `mcpbr run` without config, fails*
Claude: *forgets to check Docker, fails*
Claude: *uses wrong flags, gets errors*
```

**With Plugin:**

```text
User: "Run the benchmark"
Claude: *checks Docker with `docker ps`*
Claude: *verifies config exists*
Claude: *validates `{workdir}` placeholder*
Claude: *constructs correct command*
Claude: *evaluation succeeds*
```

## Troubleshooting

### Plugin Not Detected

**Symptom:** Claude doesn't seem to know about mcpbr commands or best practices.

**Solutions:**

1. Verify `.claude-plugin/plugin.json` exists:
   ```bash
   ls -la .claude-plugin/plugin.json
   ```

2. Check plugin.json is valid JSON:
   ```bash
   cat .claude-plugin/plugin.json | python -m json.tool
   ```

3. Ensure skills directory exists:
   ```bash
   ls -la skills/
   ```

4. Restart Claude Code or reload the workspace

### Skills Not Working

**Symptom:** Claude makes mistakes that the skills should prevent.

**Solutions:**

1. Verify skill files exist:
   ```bash
   ls -la skills/*/SKILL.md
   ```

2. Check skill files have valid frontmatter:
   ```bash
   head -5 skills/mcpbr-eval/SKILL.md
   ```

3. Ensure frontmatter has `name` and `description` fields

4. Verify no syntax errors in skill content

### Version Mismatch

**Symptom:** Plugin version doesn't match mcpbr version.

**Solutions:**

1. Check versions:
   ```bash
   # Plugin version
   cat .claude-plugin/plugin.json | grep version

   # mcpbr version
   mcpbr --version
   ```

2. Sync versions automatically:
   ```bash
   make sync-version
   ```

3. Manually update plugin.json version to match pyproject.toml

### Custom Skills Not Loading

**Symptom:** New custom skills aren't recognized by Claude.

**Solutions:**

1. Verify skill directory structure:
   ```text
   skills/
   └── my-skill/
       └── SKILL.md
   ```

2. Check SKILL.md has valid frontmatter with `name` and `description`

3. Ensure no YAML syntax errors in frontmatter

4. Restart Claude Code after adding new skills

## FAQ

### How do I create custom skills?

1. Create a new directory in `skills/`:
   ```bash
   mkdir skills/my-skill
   ```

2. Create `SKILL.md` with frontmatter:
   ```markdown
   ---
   name: my-skill
   description: Brief description
   ---

   # Instructions
   [Your skill content]
   ```

3. Add tests in `tests/test_claude_plugin.py`

4. Run tests to validate:
   ```bash
   pytest tests/test_claude_plugin.py -v
   ```

### Can I use the plugin with other projects?

Yes! The plugin is designed for mcpbr but you can adapt the pattern:

1. Copy `.claude-plugin/plugin.json` to your project
2. Update the `name`, `version`, and `description` fields
3. Create custom skills in `skills/` directory
4. Each skill teaches Claude about your project's specific commands and workflows

### How do I update the plugin?

When pulling new mcpbr updates:

```bash
git pull origin main
```

The plugin files are versioned with the repository, so updates are automatic.

For standalone installations, manually copy the updated files:

```bash
cp -r /path/to/mcpbr/.claude-plugin .
cp -r /path/to/mcpbr/skills .
```

### Does the plugin work offline?

The plugin files work offline, but mcpbr itself requires:

- Network access for Docker image pulls
- API access to Anthropic's servers

The plugin instructions are embedded in the repository and don't require external resources.

### How do I disable the plugin?

To temporarily disable:

```bash
# Rename the plugin directory
mv .claude-plugin .claude-plugin.disabled
```

To re-enable:

```bash
mv .claude-plugin.disabled .claude-plugin
```

### Can I contribute new skills?

Yes! Contributions are welcome. To add a new skill:

1. Create the skill directory and SKILL.md file
2. Add comprehensive tests in `tests/test_claude_plugin.py`
3. Update `skills/README.md` to document the new skill
4. Run pre-commit hooks: `pre-commit run --all-files`
5. Submit a pull request

See the [contributing guide](contributing.md) for detailed guidelines.

### What's the difference between skills and documentation?

**Documentation** (like this page) is for human readers to understand how things work.

**Skills** are instruction sets that Claude Code reads and follows when performing tasks. They include:

- Specific validation steps
- Common pitfalls to avoid
- Exact command formats
- Troubleshooting procedures

Think of skills as "executable documentation" that guides Claude's actions.

### How do I test if the plugin is working?

Ask Claude to perform a task that requires domain knowledge:

```text
"Run a benchmark evaluation with 1 task"
```

If the plugin is working, Claude should:

1. Check Docker is running
2. Verify API key is set
3. Ensure config exists
4. Construct a valid command
5. Execute without errors

If Claude skips these steps or makes mistakes, the plugin may not be loaded.

### Are there performance implications?

The plugin files are small (a few KB total) and have minimal impact on performance:

- **Load time:** Negligible (files are read once on workspace load)
- **Memory:** Skills are loaded into Claude's context but don't significantly impact token usage
- **Execution:** Skills improve efficiency by preventing errors and reducing back-and-forth

### How is version sync maintained?

The plugin version in `.claude-plugin/plugin.json` is automatically synced with `pyproject.toml`:

1. **Pre-commit hook:** Runs `sync_version.py` before each commit
2. **Make target:** `make sync-version` syncs versions manually
3. **CI checks:** GitHub Actions verify versions match
4. **Build process:** `make build` automatically syncs versions

This ensures the plugin version always matches the mcpbr package version.

## Version Management

### Automatic Version Sync

The plugin version is kept in sync with mcpbr through automated processes:

```bash
# Manual sync
make sync-version

# Automatic sync during build
make build

# CI verification
pytest tests/test_claude_plugin.py::TestPluginManifest::test_plugin_version_matches_pyproject
```

### Version Sync Script

Location: `scripts/sync_version.py`

The script:

1. Reads version from `pyproject.toml`
2. Updates `.claude-plugin/plugin.json`
3. Exits with error if sync fails (for CI)

### Pre-commit Hook

The `.pre-commit-config.yaml` includes a hook that automatically syncs versions:

```yaml
- repo: local
  hooks:
    - id: sync-version
      name: Sync plugin version
      entry: python scripts/sync_version.py
      language: system
      pass_filenames: false
```

## Testing

The plugin includes comprehensive tests to ensure quality:

### Run All Plugin Tests

```bash
pytest tests/test_claude_plugin.py -v
```

### Test Categories

1. **Manifest Tests:** Validate `plugin.json` structure and content
2. **Skill Tests:** Ensure skills have proper format and required content
3. **Version Tests:** Verify version sync script and automation
4. **Documentation Tests:** Check README mentions all skills
5. **Integration Tests:** Validate pre-commit hooks and Makefile targets

### Example Test Output

```text
tests/test_claude_plugin.py::TestPluginManifest::test_plugin_json_exists PASSED
tests/test_claude_plugin.py::TestPluginManifest::test_plugin_json_valid PASSED
tests/test_claude_plugin.py::TestPluginManifest::test_plugin_version_matches_pyproject PASSED
tests/test_claude_plugin.py::TestSkills::test_mcpbr_eval_mentions_docker PASSED
tests/test_claude_plugin.py::TestSkills::test_mcpbr_config_mentions_workdir PASSED
```

### Adding Tests for Custom Skills

When creating a custom skill, add tests to verify:

1. Skill directory and SKILL.md exist
2. Frontmatter is valid and complete
3. Critical keywords are present (Docker, {workdir}, etc.)
4. Instructions section exists
5. Examples are included

Example test:

```python
def test_my_skill_mentions_critical_concept(skills_dir: Path) -> None:
    """Test that my-skill mentions critical concept."""
    skill_path = skills_dir / "my-skill" / "SKILL.md"
    content = skill_path.read_text()

    assert "critical_concept" in content, "my-skill should mention critical_concept"
```

## Related Resources

- **[Skills README](https://github.com/greynewell/mcpbr/blob/main/skills/README.md)** - Detailed skill development guide
- **[Plugin Tests](https://github.com/greynewell/mcpbr/blob/main/tests/test_claude_plugin.py)** - Test suite for validation
- **[Contributing Guide](contributing.md)** - How to contribute skills
- **[CLI Reference](cli.md)** - Complete mcpbr command documentation
- **[Configuration Guide](configuration.md)** - Config file reference

## Support

If you encounter issues with the plugin:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review [FAQ](#faq) for common questions
3. Run plugin tests: `pytest tests/test_claude_plugin.py -v`
4. Open an issue on [GitHub](https://github.com/greynewell/mcpbr/issues)
5. Join discussions in the repository

When reporting issues, include:

- Claude Code version
- mcpbr version
- Plugin version (from `.claude-plugin/plugin.json`)
- Error messages or unexpected behavior
- Steps to reproduce
