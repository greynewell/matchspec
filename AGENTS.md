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

### 2. Run Type Checking

```bash
# Run mypy on source code
uv run mypy src/mcpbr/
```

**Expected output:** `Success: no issues found`

If any type errors remain, they MUST be fixed before proceeding.

### 3. Run Tests

```bash
# Run all non-integration tests
uv run pytest -m "not integration"

# For integration tests (if applicable)
uv run pytest -m integration
```

**Expected result:** All tests must pass with 0 failures.

### 4. Update CHANGELOG

**MANDATORY:** If your changes are user-visible, update CHANGELOG.md:

```bash
# Edit CHANGELOG.md and add entry under [Unreleased]
# Example:
# ### Fixed
# - Fixed XYZ issue (#123)

# Verify entry is properly formatted
cat CHANGELOG.md | head -30
```

### 5. Verify Changes

- Review all modified files
- Ensure no unintended changes were introduced
- Confirm all new code follows project conventions
- Check that imports are properly organized
- **Verify CHANGELOG.md is updated** (if applicable)

## Code Quality Requirements

### Linting Rules

The project uses Ruff for linting with the following configuration:

- **Line length:** 100 characters (E501 is ignored)
- **Target Python version:** 3.11+
- **Enabled rules:** E (pycodestyle), F (pyflakes), I (isort), N (pep8-naming), W (warnings), B (bugbear), UP (pyupgrade), SIM (simplify), RUF (ruff-specific), C4 (comprehensions), PIE (misc), PT (pytest-style), ASYNC (async bugs), S (security/bandit), T20 (print detection)
- **Type checking:** mypy with Pydantic plugin, strict mode on core modules

### Common Linting Issues to Avoid

1. **Unused imports** - Remove all unused imports
2. **Import sorting** - Imports must be sorted (stdlib → third-party → local)
3. **Undefined names** - All variables and functions must be defined before use
4. **Line too long** - While E501 is ignored, try to keep lines under 100 chars when reasonable
5. **Trailing whitespace** - Remove trailing whitespace from all lines
6. **Mutable default args** (B006) - Don't use `[]` or `{}` as default arguments
7. **Exception chaining** (B904) - Use `raise X from err` inside `except` blocks
8. **Modern Python** (UP) - Use Python 3.11+ patterns (e.g., `X | Y` unions, `match` statements)
9. **Simplifications** (SIM) - Collapse nested `with`/`if` statements, use `contextlib.suppress()`

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

### Changelog Maintenance

**CRITICAL RULE:** The CHANGELOG.md MUST be updated with EVERY user-facing change, AUTOMATICALLY, WITHOUT BEING ASKED.

#### When to Update CHANGELOG

Update CHANGELOG.md for ANY of these changes:
- ✅ New features or functionality
- ✅ Bug fixes
- ✅ Breaking changes
- ✅ Deprecations
- ✅ Security fixes
- ✅ Performance improvements that users will notice
- ✅ Changes to CLI commands or configuration
- ✅ Changes to output formats or APIs
- ❌ Internal refactoring with no user impact
- ❌ Test additions (unless they expose new testing capabilities)
- ❌ Documentation fixes (unless significant new documentation)

#### How to Update CHANGELOG

1. **Add entries to the `[Unreleased]` section** - This is where all in-progress changes go
2. **Use the correct category:**
   - `Added` - New features, capabilities, configuration options
   - `Changed` - Changes to existing functionality
   - `Deprecated` - Features marked for removal
   - `Removed` - Removed features
   - `Fixed` - Bug fixes
   - `Security` - Security-related changes
   - `Infrastructure` - Build, release, or infrastructure changes
   - `Documentation` - Significant documentation additions (not fixes)
3. **Write clear, user-focused descriptions:**
   - Start with what changed, not how
   - Include issue/PR numbers: `(#123)` or `(closes #123)`
   - Use past tense
   - Add sub-bullets for important details
4. **Format consistently:**
   ```markdown
   ## [Unreleased]

   ### Added

   - **Feature Name** (#123): Brief description
     - Additional detail about the feature
     - Another important detail
   ```

#### Example Workflow

```bash
# 1. Make code changes
# ... edit files ...

# 2. Update CHANGELOG.md (REQUIRED - don't skip this!)
# Add entry under [Unreleased] section:
# ### Fixed
# - Fixed bug in git diff detection (#335)
#   - Now detects newly created files correctly
#   - Applied fallback pattern to both Docker and local modes

# 3. Commit both together
git add src/ CHANGELOG.md
git commit -m "fix: Resolve git diff detection for new files (#335)"
```

#### Version Management on Main Branch

**IMPORTANT:** The version in `pyproject.toml` on the main branch is ALWAYS the version for the NEXT release, not the current released version.

- After releasing v0.4.1, main is automatically bumped to v0.4.2
- All changes on main are being prepared for v0.4.2
- When you update CHANGELOG, add entries under `[Unreleased]`
- When a release is published, unreleased changes move to the new version section

#### Release Process and CHANGELOG

The release process works like this:

1. **Development Phase:**
   - Changes accumulate under `[Unreleased]` section
   - Version in `pyproject.toml` reflects the upcoming release (e.g., 0.4.3)

2. **Release Phase:**
   - Maintainer manually publishes release in GitHub UI (e.g., v0.4.3)
   - Post-release workflow automatically bumps version to next patch (e.g., 0.4.4)
   - Maintainer moves `[Unreleased]` changes to `## [0.4.3] - YYYY-MM-DD` section
   - Adds version link at bottom: `[0.4.3]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.3`

3. **Post-Release:**
   - `[Unreleased]` section is now empty, ready for next changes
   - Version on main is 0.4.4
   - Next changes go under `[Unreleased]` for eventual 0.4.4 release

**CRITICAL:** Always add your changes to `[Unreleased]`. The maintainer will move them to the versioned section during release.

#### Before Creating a PR

Checklist for CHANGELOG:
- [ ] All user-visible changes are documented under `[Unreleased]`
- [ ] Entries are in the correct category (Added/Fixed/Changed/etc.)
- [ ] Descriptions are clear and user-focused
- [ ] Issue/PR numbers are included: `(#123)`
- [ ] Format matches existing entries

## Pull Request Guidelines

### Before Creating a PR

1. ✅ All linting checks pass (`uvx ruff check src/ tests/`)
2. ✅ Code is formatted (`uvx ruff format src/ tests/`)
3. ✅ Type checking passes (`uv run mypy src/mcpbr/`)
4. ✅ All tests pass (`uv run pytest -m "not integration"`)
5. ✅ **CHANGELOG.md is updated** (for user-visible changes)
6. ✅ Code is documented
7. ✅ README is updated (if applicable)
8. ✅ Changes are committed with descriptive commit messages

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

### Responding to CodeRabbit Reviews

**REQUIRED:** When CodeRabbit posts review comments on your PR, you MUST acknowledge and respond to them.

#### When You Fix a CodeRabbit Comment

If you push a commit that addresses a CodeRabbit comment:

1. **Add a comment to the PR** explaining what you fixed:
   ```markdown
   ✅ **Resolved CodeRabbit comment about XYZ (commit abc1234)**

   Fixed the issue by:
   - Specific change 1
   - Specific change 2

   The corrected code now [explanation of fix].
   ```

2. **Reference the specific comment** if there are multiple:
   ```markdown
   ✅ **Resolved: CLI override documentation issue**

   Fixed in commit 8185e60:
   - Removed incorrect `--thinking-budget` CLI override examples
   - Added warning that thinking_budget is YAML-only
   - Documented correct way to disable (omit field or set to null)
   ```

3. **Be specific** - Don't just say "fixed", explain what you changed

#### When You Disagree with CodeRabbit

If you believe a CodeRabbit suggestion is incorrect or not applicable:

1. **Explain your reasoning** in a comment:
   ```markdown
   ❌ **CodeRabbit suggestion not applicable**

   The suggestion to [X] doesn't apply here because:
   - Reason 1
   - Reason 2

   The current implementation is correct as-is.
   ```

2. **Ask for maintainer input** if uncertain:
   ```markdown
   ❓ **Need guidance on CodeRabbit suggestion**

   CodeRabbit suggests [X], but I'm not sure if this is the right approach.
   Current approach: [Y]
   CodeRabbit approach: [X]

   @maintainer - Which approach should I take?
   ```

#### Why This Matters

- Shows you're responsive to code review feedback
- Helps maintainers track which issues are resolved
- Creates a clear audit trail of what changed and why
- Prevents CodeRabbit comments from being ignored or forgotten
- Makes PR review faster (maintainers don't have to re-check everything)

## Common Pitfalls for Agents

### ❌ DON'T: Skip Linting

```bash
# Bad: Committing without checking linting
git commit -m "feat: add new feature"
git push
```

### ✅ DO: Check Linting First

```bash
# Good: Check linting and types before commit
uvx ruff check --fix src/ tests/
uvx ruff format src/ tests/
uv run mypy src/mcpbr/
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

# 3. Update CHANGELOG.md (REQUIRED for user-visible changes)
# Add entry under [Unreleased] section:
# ### Added
# - **New Feature**: Description of feature (#123)
#   - Additional details

# 4. Check linting and format
uvx ruff check --fix src/ tests/
uvx ruff format src/ tests/
uvx ruff check src/ tests/  # Verify all fixed

# 5. Run type checking
uv run mypy src/mcpbr/

# 6. Run tests
uv run pytest -m "not integration"

# 7. Commit changes (include CHANGELOG.md)
git add src/ tests/ CHANGELOG.md
git commit -m "feat: add my new feature"

# 8. Push and create PR
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
3. **Type Check** - `mypy src/mcpbr/`
4. **Build Check** - Package builds successfully
5. **Test (Python 3.11)** - All tests pass on Python 3.11
6. **Test (Python 3.12)** - All tests pass on Python 3.12

You can view check results on any PR:
```bash
gh pr checks <PR_NUMBER>
```

## Summary

**Remember:** The most important rule is to run linting, formatting, type checking, and tests BEFORE committing. This ensures high code quality and prevents CI/CD failures.

**Pre-commit command:**
```bash
uvx ruff check --fix src/ tests/ && uvx ruff format src/ tests/ && uv run mypy src/mcpbr/ && uv run pytest -m "not integration"
```

Happy coding! 🚀
