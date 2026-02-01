# HumanEval Bug Fixes - Complete Summary

## Overview

Fixed two critical bugs preventing HumanEval benchmark from running successfully:
1. **Issue #327**: Git diff not detecting newly created files
2. **Issue #333**: SimpleNamespace AttributeError in evaluation results

## Bug #1: Git Diff Detection (Issue #327)

### Problem
`_get_git_diff()` used `--diff-filter=M` which only captures MODIFIED files, not NEW files. HumanEval creates `solution.py` as a new file, so patches were empty, resulting in "No changes made by Claude Code" errors.

### Root Cause
```python
# Before (broken)
git diff --cached HEAD --diff-filter=M  # Only shows Modified files
```

### Solution
Added fallback pattern matching the Docker implementation:
```python
# Try filtered diff first (for SWE-bench artifacts)
git diff --cached HEAD --diff-filter=M

# If empty, fall back to unfiltered diff (for new files)
if empty:
    git diff --cached HEAD  # Shows all changes including new files
```

### Implementation
- **File**: `src/mcpbr/harnesses.py:205-242`
- **Commit**: `5f9584c`
- **Tests**: `tests/test_git_diff_new_files.py` (4 tests, all passing)

### Test Coverage
1. ✅ `test_detects_new_files_in_git_diff` - NEW files detected
2. ✅ `test_detects_modified_files_in_git_diff` - Modified files still work
3. ✅ `test_git_diff_with_both_new_and_modified` - Mixed scenarios
4. ✅ `test_git_diff_empty_when_nothing_staged` - Empty case

## Bug #2: SimpleNamespace AttributeError (Issue #333)

### Problem
HumanEval's `evaluate()` returns `{"resolved": bool, ...}` but NOT `"patch_applied"`. When converted to SimpleNamespace, accessing missing attributes raised AttributeError.

### Root Cause
```python
# Before (broken)
data["patch_applied"] = eval_result.patch_applied  # AttributeError!
```

### Solution
Use `getattr()` with defaults for optional attributes:
```python
# After (fixed)
data["resolved"] = getattr(eval_result, "resolved", False)
data["patch_applied"] = getattr(eval_result, "patch_applied", True)
```

### Implementation
- **File**: `src/mcpbr/harness.py:139-142`
- **Commit**: `816c82d`
- **Issue**: Created #333 for tracking

## Verification Results

### Test Suite
- **Total tests**: 741 tests (all passing ✅)
- **New tests**: 4 git diff tests (all passing ✅)
- **Coverage**: Git diff detection, modified files, new files, mixed scenarios

### HumanEval Benchmark Results

#### 2-Task Run
- **MCP Agent**: 2/2 (100%) ✅
- **Baseline**: 2/2 (100%) ✅
- **Patches generated**: 4/4 ✅

#### 5-Task Run
- **MCP Agent**: 5/5 (100%) ✅
- **Baseline**: 4/5 (80%, 1 timeout)
- **Error rate**: MCP 0%, Baseline 20%
- **Tool usage**: Write tool (100% coverage)

## Impact

### Before Fixes
- ❌ HumanEval failed with "No changes made by Claude Code"
- ❌ Patches not generated (git diff returned empty)
- ❌ SimpleNamespace AttributeError on evaluation

### After Fixes
- ✅ HumanEval runs successfully
- ✅ Patches generated correctly for new files
- ✅ 100% task completion rate on MCP agent
- ✅ Compatible with all benchmark types

## Files Changed

1. **src/mcpbr/harnesses.py**
   - Added fallback pattern to `_get_git_diff()`
   - Lines 219-242

2. **src/mcpbr/harness.py**
   - Used getattr for optional eval_result attributes
   - Lines 139-142

3. **tests/test_git_diff_new_files.py**
   - New test file with 4 comprehensive tests
   - Covers new files, modified files, mixed scenarios, empty repos

## Commits

1. **5f9584c**: Git diff detection fix (Issue #327)
2. **816c82d**: SimpleNamespace attribute fix (Issue #333)

## Branch

All changes on: `fix/cost-calculation-with-cache-tokens`

## Next Steps

1. ✅ Tests pass
2. ✅ HumanEval works
3. ✅ Issues documented (#327, #333)
4. 🔄 Ready for PR/merge

## Related Issues

- **Issue #327**: Git diff not detecting new files (FIXED)
- **Issue #333**: SimpleNamespace AttributeError (FIXED)

---

**Status**: ✅ COMPLETE - HumanEval fully functional with both bugs fixed
