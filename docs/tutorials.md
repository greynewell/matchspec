---
description: Interactive step-by-step tutorials for learning mcpbr from beginner to advanced.
---

# Tutorials

Learn mcpbr through interactive, hands-on tutorials that guide you step by step.

## Available Tutorials

| Tutorial | Difficulty | Time | Description |
|----------|-----------|------|-------------|
| **Getting Started** | Beginner | ~10 min | Install mcpbr, create your first config, and run a benchmark |
| **Configuration** | Intermediate | ~15 min | Master YAML configuration, environment variables, and validation |
| **Benchmarks** | Intermediate | ~15 min | Explore benchmark selection, filtering, and custom benchmarks |
| **Analytics** | Advanced | ~20 min | Use the analytics engine for trends, comparisons, and reports |

## Using the Tutorial CLI

### List tutorials

```bash
mcpbr tutorial list
```

### Start a tutorial

```bash
mcpbr tutorial start getting-started
```

### Check your progress

```bash
mcpbr tutorial progress
```

### Reset and start over

```bash
mcpbr tutorial reset getting-started
```

## Tutorial Workflow

Each tutorial consists of multiple steps. For each step you'll:

1. **Read** the instruction and explanation
2. **Do** the action (run a command, create a file, etc.)
3. **Validate** — the tutorial checks your work automatically
4. **Continue** to the next step

!!! tip "Hints"
    Stuck on a step? Type `hint` when prompted to get a helpful nudge.

!!! info "Progress is saved"
    Your progress is saved automatically in `~/.mcpbr_state/tutorials/`. You can quit and resume any tutorial later with `mcpbr tutorial start <id>`.

## What You'll Learn

### Getting Started (Beginner)

- Installing mcpbr with pip or npm
- Creating a minimal configuration file
- Running your first benchmark evaluation
- Understanding the results output

### Configuration (Intermediate)

- YAML configuration structure and fields
- Environment variable substitution (`${VAR}`)
- Configuration validation with `mcpbr config validate`
- Advanced options: timeouts, concurrency, resource limits

### Benchmarks (Intermediate)

- Choosing the right benchmark for your use case
- Filtering tasks by difficulty, category, and tags
- Running multiple benchmarks in sequence
- Interpreting benchmark-specific metrics

### Analytics (Advanced)

- Storing results in the analytics database
- Generating trend reports and detecting regressions
- Comparing models and MCP servers side-by-side
- Creating HTML, Markdown, and PDF reports
