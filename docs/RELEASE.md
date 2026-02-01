# Release Process

This document explains how to create releases for mcpbr, both manually and via automation.

## Table of Contents

- [Automated Release (Recommended)](#automated-release-recommended)
- [Manual Release](#manual-release)
- [For AI Agents](#for-ai-agents)
- [Version Management](#version-management)
- [What Happens on Release](#what-happens-on-release)
- [Troubleshooting](#troubleshooting)

## Release Process (Recommended)

### Workflow Overview

mcpbr uses GitHub's release drafter and automatic version bumping:

1. **Release Drafter** automatically creates draft releases from merged PRs
2. You **manually publish the release** in the GitHub UI
3. **Post-release workflow** automatically bumps the version on main

### Step-by-Step

#### 1. Review the Draft Release

As you merge PRs to main, Release Drafter automatically:
- Creates/updates a draft release
- Categorizes changes (features, fixes, breaking changes)
- Generates release notes from PR titles and labels

Navigate to [Releases](../../releases) to see the current draft.

#### 2. Prepare the Version (if needed)

For **patch releases** (bug fixes, minor improvements):
- No preparation needed! The current version in `pyproject.toml` is already correct.

For **minor releases** (new features) or **major releases** (breaking changes):
- Manually update the version in `pyproject.toml` before publishing:

```bash
# For minor bump (0.4.1 → 0.5.0)
sed -i 's/^version = "0.4.1"/version = "0.5.0"/' pyproject.toml
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 0.5.0"
git push origin main

# For major bump (0.5.0 → 1.0.0)
# Same process, update to "1.0.0"
```

#### 3. Publish the Release

In the [Releases](../../releases) page:
1. Click "Edit" on the draft release
2. Set the tag to match the version in `pyproject.toml` (e.g., `v0.4.1`)
3. Review the auto-generated release notes
4. Add any additional context or breaking change warnings
5. Click "Publish release"

#### 4. Automatic Version Bump

After you publish the release, the **Post-Release Version Bump** workflow automatically:
- ✅ Bumps to next patch version (e.g., `0.4.1` → `0.4.2`)
- ✅ Syncs version across all files
- ✅ Commits and pushes to main
- ✅ Triggers PyPI and npm publication

**Main branch is now ready for the next release!**

### Version Bump Strategy

- **Patch (automatic after release):** Bug fixes, minor improvements (0.4.1 → 0.4.2)
- **Minor (manual before release):** New features, enhancements (0.4.2 → 0.5.0)
- **Major (manual before release):** Breaking changes (0.5.0 → 1.0.0)

## Manual Release

If you need to create a release manually, follow the same pattern as the automated workflow:

### 1. Tag and release the current version

```bash
# Get current version from pyproject.toml
CURRENT_VERSION=$(python -c "import tomllib; f=open('pyproject.toml','rb'); data=tomllib.load(f); print(data['project']['version'])")

# Create and push tag
git tag -a "v${CURRENT_VERSION}" -m "Release v${CURRENT_VERSION}"
git push origin "v${CURRENT_VERSION}"

# Create GitHub release
gh release create "v${CURRENT_VERSION}" \
  --title "v${CURRENT_VERSION}" \
  --generate-notes \
  --latest
```

### 2. Bump to next version

After the release is published, bump to the next patch version:

```bash
# Calculate next version (assuming CURRENT_VERSION is set from above)
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
NEXT_VERSION="${major}.${minor}.$((patch + 1))"

# Update pyproject.toml
sed -i "s/^version = \".*\"/version = \"$NEXT_VERSION\"/" pyproject.toml

# Sync versions across all files
python3 scripts/sync_version.py

# Commit and push
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to ${NEXT_VERSION}"
git push origin main
```

This keeps the repository ready for the next release.
  --notes "Release notes here" \
  --latest

# Or use the GitHub UI at:
# https://github.com/greynewell/mcpbr/releases/new
```

## For AI Agents

**AI agents should use the automated workflow whenever possible.** Here's the recommended workflow:

### Quick Release Workflow

```bash
# 1. Trigger the release workflow (choose patch/minor/major)
gh workflow run release.yml -f version_bump=patch

# 2. Wait for the workflow to complete (~2 minutes)
sleep 120

# 3. Verify the release was created
gh release view --json tagName,publishedAt,assets

# 4. Confirm publication to PyPI and npm
# PyPI: https://pypi.org/project/mcpbr/
# npm: https://www.npmjs.com/package/@greynewell/mcpbr
```

### Determining Version Bump Type

Choose the bump type based on the changes:

- **patch**: Bug fixes, documentation updates, dependency updates
  - Example: Fix Docker TypeError (#290)
  - Example: Update README with new examples

- **minor**: New features, enhancements (backward compatible)
  - Example: Add new benchmark support
  - Example: Add CSV export functionality

- **major**: Breaking changes, API changes
  - Example: Redesign CLI interface
  - Example: Remove deprecated features

### Checking Current Version

```bash
# From pyproject.toml
grep '^version' pyproject.toml

# From git tags
git describe --tags --abbrev=0

# From latest release
gh release view --json tagName -q '.tagName'
```

## Version Management

### Version Sync Script

The `scripts/sync_version.py` script ensures all package files have the same version:

- **Source of truth**: `pyproject.toml`
- **Synced files**:
  - `package.json` (npm CLI package)
  - `.claude-plugin/plugin.json`
  - `.claude-plugin/package.json` (Claude plugin)
  - `.claude-plugin/marketplace.json`

### Pre-commit Hook

The version sync runs automatically on commit via `.pre-commit-config.yaml`:

```yaml
- id: sync-version
  name: Sync version across project files
  entry: python3 scripts/sync_version.py
  language: system
  pass_filenames: false
  files: pyproject.toml
  stages: [pre-commit]
```

## What Happens on Release

When a release is published (tag pushed or GitHub release created):

### 1. PyPI Publication (`publish.yml`)
- Builds Python package
- Publishes to https://pypi.org/project/mcpbr/

### 2. npm Publication (`publish-npm.yml`)
Publishes **4 packages**:
- `@greynewell/mcpbr` - Scoped CLI package
- `mcpbr-cli` - Unscoped CLI package
- `@greynewell/mcpbr-claude-plugin` - Scoped Claude plugin
- `mcpbr-claude-plugin` - Unscoped Claude plugin

### 3. Release Drafter
- Automatically generates release notes based on merged PRs
- Groups changes by type (features, fixes, docs, etc.)
- Credits contributors

## GitHub Actions Limitation

**Important**: When the release workflow creates a release using `GITHUB_TOKEN`, it doesn't automatically trigger the PyPI and npm publish workflows. This is a GitHub Actions security feature to prevent recursive workflow triggers.

**Workaround**: After running the release workflow, manually trigger the publish workflows:

```bash
# After release workflow completes
gh workflow run publish.yml -f tag=v0.3.25
gh workflow run publish-npm.yml -f tag=v0.3.25
```

**Alternative**: Use a Personal Access Token (PAT) in the release workflow instead of `GITHUB_TOKEN` (not implemented yet, but possible future enhancement).

## Troubleshooting

### Version Mismatch Error

If you see "version does not match release tag" during npm publish:

```bash
# Sync versions
python3 scripts/sync_version.py

# Verify all versions match
grep '"version"' package.json .claude-plugin/package.json
grep '^version' pyproject.toml
```

### Failed PyPI Upload

If PyPI upload fails:
1. Check if the version already exists on PyPI
2. Bump to the next version
3. Delete the failed release and tag
4. Retry with new version

```bash
# Delete failed release
gh release delete v0.3.25 --yes

# Delete tag locally and remotely
git tag -d v0.3.25
git push origin :refs/tags/v0.3.25

# Bump version and retry
```

### Failed npm Upload

If npm upload fails:
1. Check npm token is valid
2. Verify package names are available
3. Check package.json structure

```bash
# Test npm package locally
cd /tmp
npm pack /path/to/mcpbr
tar -tzf greynewell-mcpbr-*.tgz
```

### Release Draft Not Found

The automated workflow looks for a draft release created by Release Drafter. If none exists:
- The workflow will create a release with basic notes
- You can add custom notes via the `release_notes` input

### Git Push Permission Denied

If the workflow fails to push:
- Ensure `GITHUB_TOKEN` has `contents: write` permission
- Check branch protection rules allow the bot to push

## Best Practices

1. **Always use semantic versioning**: MAJOR.MINOR.PATCH
2. **Use automated workflow** to avoid manual errors
3. **Test releases** on TestPyPI/npm dry-run first (if critical)
4. **Update CHANGELOG.md** if maintained separately
5. **Verify publications** after release completes
6. **Never delete published releases** unless absolutely necessary

## Examples

### Example 1: Bug Fix Release

```bash
# PR #290 fixed a Docker TypeError - this is a patch
gh workflow run release.yml -f version_bump=patch
# Result: 0.3.24 → 0.3.25
```

### Example 2: New Feature Release

```bash
# Added SWE-Bench Lite support - this is a minor feature
gh workflow run release.yml -f version_bump=minor
# Result: 0.3.24 → 0.4.0
```

### Example 3: Breaking Change Release

```bash
# Redesigned CLI interface - breaking change
gh workflow run release.yml \
  -f version_bump=major \
  -f release_notes="⚠️ Breaking: CLI commands have been reorganized. See migration guide."
# Result: 0.3.24 → 1.0.0
```

## Quick Reference

| Task | Command |
|------|---------|
| Check current version | `grep '^version' pyproject.toml` |
| Sync versions | `python3 scripts/sync_version.py` |
| Patch release | `gh workflow run release.yml -f version_bump=patch` |
| Minor release | `gh workflow run release.yml -f version_bump=minor` |
| Major release | `gh workflow run release.yml -f version_bump=major` |
| View latest release | `gh release view` |
| List all releases | `gh release list` |
| Delete release | `gh release delete v0.3.25 --yes` |

---

**For questions or issues, please open an issue on GitHub.**
