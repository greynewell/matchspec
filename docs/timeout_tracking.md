# Timeout Statistics Tracking

## Overview

When a task times out during evaluation, mcpbr now captures and records the work completed before the timeout occurred. This ensures that timeout tasks don't appear as "never started" in evaluation results.

## Problem (Before Fix)

Prior to this fix, when a task timed out:
- `iterations` was recorded as 0
- `tool_calls` was recorded as 0
- `tool_usage` was empty
- No distinction between "agent never started" vs "ran out of time"

This caused:
- Inaccurate statistics excluding all timeout work
- Misleading results showing timeouts as startup failures
- Under-counted costs and token usage
- Incorrect analysis of tool effectiveness

### Example Before Fix

```json
{
  "instance_id": "django__django-11797",
  "mcp_result": {
    "iterations": 0,
    "tool_calls": 0,
    "tool_usage": {},
    "error": "Task execution timed out after 600s..."
  }
}
```

Even though MCP server logs showed the agent made 30 tool calls.

## Solution (After Fix)

The timeout handler now:
1. Captures partial stdout from MCP log files
2. Parses tool usage statistics from the partial output
3. Records iterations, tool_calls, tool_usage, and tool_failures
4. Adds `"status": "timeout"` field to distinguish from other errors

### Example After Fix

```json
{
  "instance_id": "django__django-11797",
  "mcp_result": {
    "iterations": 15,
    "tool_calls": 30,
    "tool_usage": {
      "Grep": 16,
      "Read": 8,
      "mcp__supermodel__explore_codebase": 4,
      "Bash": 1,
      "TodoWrite": 1
    },
    "tool_failures": {},
    "status": "timeout",
    "error": "Task execution timed out after 600s. Agent made 30 tool calls across 15 iterations before timeout.",
    "tokens": {
      "input": 25000,
      "output": 12000
    }
  }
}
```

## Implementation Details

### MCP Log File Recovery

When a timeout occurs in Docker execution (`ClaudeCodeHarness._solve_in_docker`):

1. The MCP server log file is flushed and closed
2. The log file is read back to extract stdout lines
3. Lines prefixed with `[STDOUT]` are parsed for tool usage events
4. The `_parse_tool_usage_from_stream()` function extracts:
   - Total tool calls
   - Tool usage breakdown by tool name
   - Tool failures and error messages
   - Number of iterations (turns)
   - Token usage (input/output)

### Status Field

The `"status": "timeout"` field is added to results when:
- The error message contains "timeout" or "timed out"
- This allows distinguishing between:
  - `"status": "timeout"` - Agent was working but ran out of time
  - No status field - Other types of errors
  - `"resolved": true` - Normal successful completion

### Fallback Behavior

If MCP log parsing fails for any reason:
- The system gracefully falls back to returning zeros
- An error message is logged (in verbose mode)
- The timeout error is still recorded with available information

## Testing

New tests verify:
- Partial stdout parsing from interrupted executions
- Tool usage statistics extraction
- Tool failure tracking in partial streams
- Status field addition for timeout errors
- Graceful handling of malformed JSON
- Empty stdout handling

Run tests:
```bash
pytest tests/test_timeout_tracking.py -v
```

## Impact on Evaluation Results

After this fix:
- Timeout tasks now contribute to tool usage statistics
- Average tool calls per task is more accurate
- Cost calculations include timeout work
- Researchers can distinguish "too slow" from "failed to start"

### Statistics Correction Example

In a 300-task evaluation where 36 tasks timed out:
- **Before**: Missing 1,080 tool calls from statistics
- **After**: All tool calls included, proper averages calculated

## Configuration

No configuration changes required. The fix is automatic and backward-compatible.

Timeout duration is still controlled by:
```yaml
timeout_seconds: 600  # Default timeout per task
```

## Related Issues

- Issue #297: Original bug report
- Issue #295: Enable logging by default
- Issue #296: Consolidate log directories

## Future Enhancements

Potential improvements:
1. Add timeout warning thresholds (warn if many tasks timeout)
2. Include timeout statistics in summary reports
3. Support adjustable timeouts per task or repository
4. Add timeout prediction based on repository size
