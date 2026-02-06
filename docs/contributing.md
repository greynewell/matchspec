---
description: "Contribute to mcpbr: development setup, coding standards, testing requirements, and pull request guidelines."
faq:
  - q: "How do I contribute to mcpbr?"
    a: "Fork the repository, create a feature branch, make your changes with tests, ensure all tests pass, and submit a pull request. See the contribution guide for detailed steps."
  - q: "How do I set up mcpbr for development?"
    a: "Clone the repository, create a virtual environment, and install with dev dependencies: 'pip install -e \".[dev]\"'. You'll need Python 3.11+, Docker, and an Anthropic API key."
  - q: "How do I add a new MCP provider to mcpbr?"
    a: "Create a class implementing the ModelProvider protocol in providers.py, add it to PROVIDER_REGISTRY, update VALID_PROVIDERS in config.py, add tests, and update documentation."
  - q: "What code style does mcpbr use?"
    a: "mcpbr uses ruff for linting and formatting, with type hints throughout the codebase. Run 'ruff check src/' to lint and 'ruff format src/' to format before submitting PRs."
---

# Contributing

Thank you for your interest in contributing to mcpbr! This guide covers everything you need to get started.

To understand the project's vision and motivation, read [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/) and the [About](about.md) page.

## Ways to Contribute

- **Bug Reports**: Found a bug? [Open an issue](https://github.com/greynewell/mcpbr/issues/new)
- **Feature Requests**: Have an idea? Start a [discussion](https://github.com/greynewell/mcpbr/discussions)
- **Code Contributions**: Submit a pull request
- **Documentation**: Improve docs, fix typos, add examples
- **Testing**: Write tests, report edge cases

## Reporting Bugs

Before creating a bug report, check existing issues to avoid duplicates.

Include:

- Clear, descriptive title
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, Docker version)
- Relevant logs or error messages

## Development Setup

### Prerequisites

- Python 3.11+
- Docker (running)
- An Anthropic API key

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/mcpbr.git
cd mcpbr

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run unit tests only (no Docker or API keys required)
pytest -m "not integration"

# Run all tests (requires Docker and API keys)
pytest

# Run with coverage
pytest --cov=mcpbr
```

## Code Style

mcpbr uses [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

### Before Submitting

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

### Type Hints

All functions should have type hints:

```python
# Good
def process_task(task: dict[str, Any], timeout: int = 300) -> TaskResult:
    ...

# Missing type hints
def process_task(task, timeout=300):
    ...
```

## Pull Request Process

### 1. Fork and Branch

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/mcpbr.git
cd mcpbr

# Create a feature branch
git checkout -b feature/my-feature
```

### 2. Make Changes

- Write clear, focused commits
- Add tests for new functionality
- Update documentation as needed

### 3. Test

```bash
# Run tests
pytest -m "not integration"

# Check linting
ruff check src/ tests/

# Format code
ruff format src/ tests/
```

### 4. Submit

```bash
git push origin feature/my-feature
```

Then open a pull request on GitHub.

### PR Guidelines

- Clear, descriptive title
- Reference related issues
- Describe what changed and why
- Include test results
- Update docs if needed

## Commit Messages

- Use clear, descriptive messages
- Start with a verb in imperative mood (e.g., "Add", "Fix", "Update")
- Keep the first line under 72 characters
- Reference issues when applicable (e.g., "Fix #123")

```bash
# Good
git commit -m "Add timeout parameter to evaluation runner"
git commit -m "Fix container cleanup on SIGTERM"
git commit -m "Update CLI help text for --verbose flag"

# Bad
git commit -m "fixed stuff"
git commit -m "WIP"
```

## Project Structure

```
mcpbr/
├── src/mcpbr/          # Main package
│   ├── cli.py          # CLI commands
│   ├── config.py       # Configuration models
│   ├── harness.py      # Main orchestrator
│   ├── harnesses.py    # Agent implementations
│   ├── providers.py    # LLM provider abstractions
│   ├── docker_env.py   # Docker management
│   ├── evaluation.py   # Patch testing
│   └── ...
├── tests/              # Test suite
├── docs/               # Documentation
└── config/             # Example configurations
```

## Adding New Features

### Adding a New Provider

1. Create a class in `src/mcpbr/providers.py` implementing the `ModelProvider` protocol
2. Add it to `PROVIDER_REGISTRY`
3. Update `VALID_PROVIDERS` in `config.py`
4. Add tests in `tests/test_providers.py`
5. Update documentation

```python
class MyProvider:
    """My custom provider implementation."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
    ) -> ChatResponse:
        ...

# Register in PROVIDER_REGISTRY
PROVIDER_REGISTRY["myprovider"] = MyProvider
```

### Adding a New Agent Harness

1. Create a class in `src/mcpbr/harnesses.py` implementing the `AgentHarness` protocol
2. Add it to `HARNESS_REGISTRY`
3. Update `VALID_HARNESSES` in `config.py`
4. Add tests
5. Update documentation

```python
class MyHarness:
    """My custom agent harness."""

    async def solve(
        self,
        task: dict[str, Any],
        workdir: str,
        timeout: int = 300,
        verbose: bool = False,
        task_id: str | None = None,
        env: TaskEnvironment | None = None,
    ) -> AgentResult:
        ...

# Register in HARNESS_REGISTRY
HARNESS_REGISTRY["myharness"] = MyHarness
```

## Testing Guidelines

### Unit Tests

Test individual components in isolation:

```python
def test_config_validation():
    """Test configuration validation."""
    config = HarnessConfig(
        mcp_server=MCPServerConfig(command="echo", args=["hello"]),
        provider="anthropic",
    )
    assert config.provider == "anthropic"
```

### Integration Tests

Mark tests that require external resources:

```python
import pytest

@pytest.mark.integration
async def test_docker_environment():
    """Test Docker environment creation."""
    manager = DockerEnvironmentManager()
    env = await manager.create_environment(task)
    ...
```

Run integration tests separately:

```bash
pytest -m integration
```

## Documentation

### Building Docs Locally

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Build and serve
mkdocs serve
```

Visit `http://127.0.0.1:8000` to preview.

### Documentation Style

- Clear, concise writing
- Code examples for all features
- FAQ structured data in frontmatter
- Cross-links between related pages

## Questions?

- [Open an issue](https://github.com/greynewell/mcpbr/issues) for bugs or feature requests
- [Start a discussion](https://github.com/greynewell/mcpbr/discussions) for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
