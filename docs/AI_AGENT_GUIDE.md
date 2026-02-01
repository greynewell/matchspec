# AI Agent Quick Reference Guide

This guide provides quick commands for AI agents (like Claude Code) to perform common tasks.

## Creating a Release

**Workflow:** Publish release in GitHub UI → Auto-bump version on main

### Standard Release (Patch - Most Common)

For patch releases (bug fixes, minor improvements):

1. **Check the draft release** - Release Drafter auto-creates it from merged PRs:
   ```bash
   gh release list
   ```

2. **Publish the release in GitHub UI**:
   - Go to https://github.com/greynewell/mcpbr/releases
   - Edit the draft release
   - Set tag to match current version (e.g., `v0.4.1`)
   - Review notes and publish

3. **Automatic version bump** - The post-release workflow automatically:
   - Bumps to next patch (0.4.1 → 0.4.2)
   - Commits to main
   - Main is ready for next release!

### Minor or Major Version Bumps

For minor (new features) or major (breaking changes) releases, update the version **before** publishing:

```bash
# For minor version bump (e.g., 0.4.2 → 0.5.0)
sed -i 's/^version = "0.4.2"/version = "0.5.0"/' pyproject.toml
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 0.5.0"
git push origin main

# Then publish release v0.5.0 in GitHub UI
# Post-release workflow will auto-bump to 0.5.1
```

**Major version example:** Same process, use `1.0.0` for breaking changes.

## Version Bump Strategy

- **Patch (auto after release):** Bug fixes, docs, deps (0.4.1 → 0.4.2)
- **Minor (manual before release):** New features (0.4.2 → 0.5.0)
- **Major (manual before release):** Breaking changes (0.5.0 → 1.0.0)

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
- [ ] Check draft release: `gh release list`
- [ ] Publish release in GitHub UI (set correct tag version)
- [ ] Wait ~2 minutes for post-release workflow to auto-bump version
- [ ] Verify version was bumped on main: `grep '^version' pyproject.toml`
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
# PRs merged to main, draft release exists
# Version is already set in pyproject.toml (e.g., 0.4.1)

# 1. Check draft
gh release list

# 2. Publish in GitHub UI with tag v0.4.1
# 3. Post-release workflow auto-bumps to 0.4.2 on main
```

### Minor version release (new features)
```bash
# Manually bump version first
sed -i 's/^version = "0.4.2"/version = "0.5.0"/' pyproject.toml
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 0.5.0"
git push origin main

# Publish release v0.5.0 in GitHub UI
# Post-release workflow auto-bumps to 0.5.1
```

### Major version release (breaking changes)
```bash
# Redesigned CLI interface - breaking change
sed -i 's/^version = "0.5.1"/version = "1.0.0"/' pyproject.toml
python3 scripts/sync_version.py
git add pyproject.toml package.json .claude-plugin/
git commit -m "chore: Bump version to 1.0.0"
git push origin main

# Publish release v1.0.0 in GitHub UI
# Post-release workflow auto-bumps to 1.0.1
gh workflow run release.yml -f version_bump=major
# Creates v1.0.0
```

---

**Remember**: One command releases everything. Don't overthink it! 🚀
