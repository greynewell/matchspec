# Agent Guidelines for mcpbr Development

This document provides guidelines for AI agents (e.g., Claude Code agents) working on the mcpbr project. Following these guidelines ensures consistent, high-quality contributions.

## Table of Contents

1. [Virtual Environment Setup](#virtual-environment-setup) **← START HERE**
2. [Pre-Commit Checklist](#pre-commit-checklist)
3. [Code Quality Requirements](#code-quality-requirements)
4. [Testing Requirements](#testing-requirements)
5. [Documentation Requirements](#documentation-requirements)
6. [Pull Request Guidelines](#pull-request-guidelines)

## Virtual Environment Setup

**⚠️ CRITICAL: ALWAYS USE A VIRTUAL ENVIRONMENT**

macOS uses system Python protection (PEP 668) which prevents installing packages globally. **DO NOT** use `--break-system-packages` or try to install packages system-wide. Instead, ALWAYS use a virtual environment or `uv`/`uvx`.

### Option 1: Using uv (Recommended)

The project uses `uv` for dependency management. Use `uvx` for running commands and `uv run` for scripts:

```bash
# Run commands without installation
uvx ruff check src/ tests/
uvx ruff format src/ tests/

# Run Python scripts/tests
uv run pytest -m "not integration"

# Install project in development mode (if needed)
uv pip install -e ".[dev]"
```

**This is the preferred approach** as it's already configured in the project.

### Option 2: Traditional Virtual Environment

If you need a traditional venv:

```bash
# Create virtual environment (one time)
python3 -m venv .venv

# Activate it (REQUIRED for every terminal session)
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Now you can use pip and run commands normally
pip install pre-commit
pytest -m "not integration"

# Deactivate when done
deactivate
```

### Option 3: Using pipx for Global Tools

For global tools like `pre-commit`, use `pipx`:

```bash
# Install pipx (one time)
brew install pipx

# Install global tools
pipx install pre-commit
pipx install pytest
```

### Checking Active Environment

Before running Python commands, verify your environment:

```bash
# Check if in a virtual environment
echo $VIRTUAL_ENV

# Should show path like: /Users/you/Projects/mcpbr/.venv

# Check Python location
which python3
# Should NOT be: /usr/bin/python3 (system Python)
# Should be: .venv/bin/python3 (venv) or managed by uv
```

### Common Errors and Solutions

**Error: `externally-managed-environment`**
```bash
# ❌ DON'T: Try to install globally
pip install something

# ✅ DO: Use uv or venv
uvx something  # for CLI tools
uv run python script.py  # for scripts
# OR activate venv first
source .venv/bin/activate && pip install something
```

**Error: `command not found: pytest`**
```bash
# ❌ DON'T: Install globally
pip install pytest

# ✅ DO: Use uv run or activate venv
uv run pytest  # preferred
# OR
source .venv/bin/activate && pytest
```

### Project Setup Workflow

When starting work on this project:

```bash
# 1. Clone the repository
git clone https://github.com/greynewell/mcpbr.git
cd mcpbr

# 2. Choose your environment approach:

# Option A: Using uv (recommended)
# No setup needed! Just use `uvx` and `uv run` commands

# Option B: Using venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Install pre-commit hooks (one time)
pipx install pre-commit  # if not already installed
pre-commit install

# 4. Verify setup
uv run pytest --version  # Should work
uvx ruff --version  # Should work
```

### Remember

- **NEVER** install Python packages system-wide on macOS
- **ALWAYS** use `uv run` / `uvx` OR activate venv first
- **CHECK** your environment with `echo $VIRTUAL_ENV` when debugging
- The project is configured to use `uv` - prefer `uvx` and `uv run` commands

## Pre-Commit Checklist

**MANDATORY:** Before committing code or creating a pull request, agents MUST complete ALL of the following steps:

### 1. Run Linting

```bash
# Check for linting issues
uvx ruff check src/ tests/

# Auto-fix fixable issues
uvx ruff check --fix src/ tests/

# Format code
uvx ruff format src/ tests/

# Verify all issues are resolved
uvx ruff check src/ tests/
```

**Expected output:** `All checks passed!`

If any linting errors remain, they MUST be fixed manually before proceeding.

**Quick one-liner:**
```bash
uvx ruff check --fix src/ tests/ && uvx ruff format src/ tests/ && uvx ruff check src/ tests/
```

### 2. Run Tests

```bash
# Run all non-integration tests
uv run pytest -m "not integration"

# For integration tests (if applicable)
uv run pytest -m integration
```

**Expected result:** All tests must pass with 0 failures.

### 3. Verify Changes

- Review all modified files
- Ensure no unintended changes were introduced
- Confirm all new code follows project conventions
- Check that imports are properly organized

## Code Quality Requirements

### Linting Rules

The project uses Ruff for linting with the following configuration:

- **Line length:** 100 characters (E501 is ignored)
- **Target Python version:** 3.11+
- **Enabled rules:** E (pycodestyle errors), F (pyflakes), I (isort), N (pep8-naming), W (pycodestyle warnings)

### Common Linting Issues to Avoid

1. **Unused imports** - Remove all unused imports
2. **Import sorting** - Imports must be sorted (stdlib → third-party → local)
3. **Undefined names** - All variables and functions must be defined before use
4. **Line too long** - While E501 is ignored, try to keep lines under 100 chars when reasonable
5. **Trailing whitespace** - Remove trailing whitespace from all lines

### Code Style

- Use type hints for function signatures
- Use descriptive variable names
- Follow PEP 8 naming conventions:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- Add docstrings for public functions and classes

## Testing Requirements

### Test Coverage

- **New features** must have comprehensive test coverage
- **Bug fixes** should include regression tests
- Aim for at least 80% code coverage on new code

### Test Organization

- Place tests in `tests/` directory
- Mirror source file structure (e.g., `src/mcpbr/foo.py` → `tests/test_foo.py`)
- Use pytest fixtures for common setup
- Mark integration tests with `@pytest.mark.integration`

### Test Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Use descriptive names that explain what is being tested

### Running Tests

```bash
# Run all non-integration tests
uv run pytest -m "not integration"

# Run specific test file
uv run pytest tests/test_foo.py

# Run with coverage
uv run pytest --cov=src/mcpbr --cov-report=html

# Run integration tests (requires setup)
uv run pytest -m integration
```

## Documentation Requirements

### Code Documentation

- Add docstrings to all public functions, classes, and modules
- Use Google-style docstrings
- Include type hints in function signatures

Example:
```python
def calculate_cost(tokens_in: int, tokens_out: int, model: str) -> float:
    """Calculate the cost of an API call.

    Args:
        tokens_in: Number of input tokens
        tokens_out: Number of output tokens
        model: Model identifier (e.g., 'claude-sonnet-4-5-20250929')

    Returns:
        Total cost in USD

    Raises:
        ValueError: If model is not supported
    """
    ...
```

### README Updates

If your changes affect:
- CLI commands
- Configuration format
- Features or capabilities
- Installation or setup

Then you MUST update the README.md accordingly.

### Changelog

For significant changes, add an entry to CHANGELOG.md following the Keep a Changelog format.

## Pull Request Guidelines

### Before Creating a PR

1. ✅ All linting checks pass (`uvx ruff check src/ tests/`)
2. ✅ Code is formatted (`uvx ruff format src/ tests/`)
3. ✅ All tests pass (`uv run pytest -m "not integration"`)
4. ✅ Code is documented
5. ✅ README is updated (if applicable)
6. ✅ Changes are committed with descriptive commit messages

### PR Title Format

Use conventional commit format:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Examples:
- `feat: add YAML export for results`
- `fix: resolve linting issues`
- `docs: update installation instructions`

### PR Description

Include:
1. **Summary** - What does this PR do?
2. **Changes** - Detailed list of changes
3. **Testing** - How was this tested?
4. **Related Issues** - Link to issues using `fixes #123` or `closes #123`

### Linking Issues

Use GitHub keywords in PR description to auto-close issues:
- `fixes #123`
- `closes #123`
- `resolves #123`

## Common Pitfalls for Agents

### ❌ DON'T: Skip Linting

```bash
# Bad: Committing without checking linting
git commit -m "feat: add new feature"
git push
```

### ✅ DO: Check Linting First

```bash
# Good: Check linting before commit
uvx ruff check --fix src/ tests/
uvx ruff format src/ tests/
uv run pytest -m "not integration"
git commit -m "feat: add new feature"
git push
```

### ❌ DON'T: Create PRs with Failing Tests

Always verify tests pass locally before pushing.

### ✅ DO: Run Full Test Suite

```bash
# Run tests before creating PR
uv run pytest -m "not integration"
# Verify all tests pass, then push
```

### ❌ DON'T: Ignore Import Order

Ruff will fail if imports are not properly sorted.

### ✅ DO: Let Ruff Fix Import Order

```bash
# Ruff will automatically fix import sorting
uvx ruff check --fix src/ tests/
```

## Workflow Example

Here's a complete workflow for implementing a feature:

```bash
# 1. Create a branch
git checkout -b feature/my-new-feature

# 2. Implement the feature
# ... edit files ...

# 3. Check linting and format
uvx ruff check --fix src/ tests/
uvx ruff format src/ tests/
uvx ruff check src/ tests/  # Verify all fixed

# 4. Run tests
uv run pytest -m "not integration"

# 5. Commit changes
git add .
git commit -m "feat: add my new feature"

# 6. Push and create PR
git push -u origin feature/my-new-feature
gh pr create --title "feat: add my new feature" --body "Implements #123"
```

## Questions?

If you encounter issues or have questions:
- Check existing issues: https://github.com/greynewell/mcpbr/issues
- Review CI/CD logs for failed checks
- Consult the main README.md for setup instructions

## CI/CD Pipeline

The project uses GitHub Actions for CI/CD. All PRs must pass:

1. **Lint Check** - `uvx ruff check src/ tests/`
2. **Format Check** - `uvx ruff format --check src/ tests/`
3. **Build Check** - Package builds successfully
4. **Test (Python 3.11)** - All tests pass on Python 3.11
5. **Test (Python 3.12)** - All tests pass on Python 3.12

You can view check results on any PR:
```bash
gh pr checks <PR_NUMBER>
```

## Summary

**Remember:** The most important rule is to run linting, formatting, and tests BEFORE committing. This ensures high code quality and prevents CI/CD failures.

**Pre-commit command:**
```bash
uvx ruff check --fix src/ tests/ && uvx ruff format src/ tests/ && uv run pytest -m "not integration"
```

Happy coding! 🚀
