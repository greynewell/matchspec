# AI Agent Quick Reference Guide

This guide provides quick commands for AI agents (like Claude Code) to perform common tasks.

## Creating a Release

**Workflow:** Release current version → Auto-bump to next patch → Commit to main

### Standard Release (Patch Bump)

For most releases (bug fixes, improvements, new features):

```bash
# Release current version in pyproject.toml
gh workflow run release.yml

# With optional release notes
gh workflow run release.yml -f release_notes="Special thanks to contributors!"
```

The workflow automatically:
- ✅ Tags and releases current version
- ✅ Bumps to next patch version (e.g., 0.4.1 → 0.4.2)
- ✅ Syncs version across all files
- ✅ Commits and pushes to main
- ✅ Triggers PyPI and npm publication

### Minor or Major Version Bumps

For minor (new features) or major (breaking changes) releases, manually update the version **before** triggering the release:

```bash
# For minor version bump (e.g., 0.4.2 → 0.5.0)
# 1. Edit pyproject.toml
sed -i 's/^version = .*/version = "0.5.0"/' pyproject.toml

# 2. Sync and commit
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 0.5.0"
git push origin main

# 3. Trigger release workflow
gh workflow run release.yml
```

**Major version example:** Same process, use `1.0.0` for breaking changes.

## Version Bump Strategy

- **Patch (automatic):** Bug fixes, documentation, dependencies (0.4.1 → 0.4.2)
- **Minor (manual):** New features, enhancements (0.4.x → 0.5.0)
- **Major (manual):** Breaking API changes, removed features (0.x.x → 1.0.0)

## Common Tasks

### Check Current Version
```bash
grep '^version' pyproject.toml
```

### Verify Release Published
```bash
# Check GitHub
gh release view

# Check PyPI
curl -s https://pypi.org/pypi/mcpbr/json | jq -r '.info.version'

# Check npm
npm view @greynewell/mcpbr version
```

### Manual Version Sync (rarely needed)
```bash
# Update pyproject.toml first, then:
python3 scripts/sync_version.py
```

### Fix Version Mismatch
```bash
# If pyproject.toml and package.json are out of sync:
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: sync version to $(grep '^version' pyproject.toml | cut -d'"' -f2)"
git push origin main
```

## Workflow Checklist

When making a release:

- [ ] Ensure PR is merged to main
- [ ] For minor/major bumps: Manually update version in pyproject.toml, sync, commit, push
- [ ] For patch bumps (most common): Version is already set in main
- [ ] Run: `gh workflow run release.yml`
- [ ] Wait ~2 minutes for completion
- [ ] Verify release: `gh release view`
- [ ] Check that version was auto-bumped on main after release
- [ ] Verify PyPI: Check https://pypi.org/project/mcpbr/
- [ ] Verify npm: Check https://www.npmjs.com/package/mcpbr-cli

## What NOT to Do

❌ Don't manually edit version in package.json (sync script handles it)
❌ Don't create releases manually (use the workflow)
❌ Don't skip version syncing
❌ Don't publish to PyPI/npm manually (workflows handle it)
❌ Don't commit without running pre-commit hooks

## Emergency Procedures

### Delete a Bad Release
```bash
# Delete from GitHub
gh release delete v0.3.25 --yes

# Delete tags
git tag -d v0.3.25
git push origin :refs/tags/v0.3.25

# Note: Can't delete from PyPI/npm - must publish new version
```

### Rollback Version
```bash
# Update to previous version in pyproject.toml
sed -i 's/version = "0.3.25"/version = "0.3.24"/' pyproject.toml

# Sync
python3 scripts/sync_version.py

# Commit
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: rollback to 0.3.24"
git push origin main
```

## Full Documentation

For detailed information, see [RELEASE.md](./RELEASE.md)

## Examples

### Standard patch release (most common)
```bash
# PR #290 fixed Docker TypeError and is merged to main
# Version is already set in pyproject.toml (e.g., 0.4.1)
gh workflow run release.yml
# Releases v0.4.1, then auto-bumps main to 0.4.2
```

### Minor version release (new features)
```bash
# Manually bump version first
sed -i 's/^version = "0.4.2"/version = "0.5.0"/' pyproject.toml
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 0.5.0"
git push origin main

# Trigger release
gh workflow run release.yml
# Releases v0.5.0, then auto-bumps main to 0.5.1
```

### Major version release (breaking changes)
```bash
# Redesigned CLI interface - breaking change
gh workflow run release.yml -f version_bump=major
# Creates v1.0.0
```

---

**Remember**: One command releases everything. Don't overthink it! 🚀
