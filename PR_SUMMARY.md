# PR Summary: Enhance Run Output with Comprehensive Statistics

Implements issue #9 by adding comprehensive statistics beyond basic success rates to help users understand and optimize their MCP servers.

## Changes Made

### New Files

1. **`src/mcpbr/statistics.py`** - Core statistics module
   - `ComprehensiveStatistics` dataclass with 9 sub-statistics types
   - Token usage statistics (total, averages, per-task breakdown)
   - Cost breakdown (total, per-task, per-resolved, min/max)
   - Tool usage statistics (calls, failures, per-tool breakdown, rankings)
   - Error analysis (categorization, common errors, samples)
   - Iteration statistics (averages, distribution, per-task)
   - Helper functions for error categorization and statistics calculation

2. **`tests/test_statistics.py`** - Comprehensive unit tests (35 test cases)
   - Error categorization tests (9 categories)
   - Token statistics tests (4 test cases)
   - Cost statistics tests (3 test cases)
   - Tool statistics tests (4 test cases)
   - Error statistics tests (4 test cases)
   - Iteration statistics tests (3 test cases)
   - Integration tests (3 test cases)
   - Edge case tests (5 test cases)

3. **`tests/test_statistics_integration.py`** - End-to-end integration tests (3 test cases)
   - JSON output integration
   - Markdown output integration
   - Empty results handling

4. **`docs/comprehensive-statistics.md`** - User documentation
   - Overview of all statistics
   - Console output examples
   - JSON export examples
   - Markdown report examples
   - Interpretation guide
   - Use cases and best practices

### Modified Files

1. **`src/mcpbr/harness.py`**
   - Integrated comprehensive statistics calculation
   - Added statistics to evaluation results summary
   - No breaking changes to existing functionality

2. **`src/mcpbr/reporting.py`**
   - Added `print_comprehensive_statistics()` function for Rich console output
   - Updated `print_summary()` to include comprehensive statistics
   - Extended `save_markdown_report()` with detailed statistics sections
   - Fixed optional dataset field in markdown report
   - Added automatic deserialization of statistics from dict to dataclass

## Statistics Provided

### 1. Token Usage Statistics
- Total input/output tokens across all tasks
- Average tokens per task
- Min/max tokens per task
- Per-task breakdown
- Comparison between MCP and baseline

### 2. Cost Breakdown
- Total cost for evaluation run
- Average cost per task
- Cost per resolved task
- Min/max costs (identify outliers)
- Per-task cost tracking
- Comparison between MCP and baseline

### 3. Tool Usage Statistics (MCP Only)
- Total tool calls with success/failure rates
- Per-tool breakdown with reliability metrics
- Top 10 most used tools
- Top 10 most failed tools
- Unique tools used count
- Average calls per task

### 4. Error Analysis
- Total errors and error rate
- Error categorization (timeout, network, docker, MCP, permission, etc.)
- Most common errors with counts
- Sample errors with context
- Timeout tracking separately
- Comparison between MCP and baseline

### 5. Iteration Statistics
- Total iterations across all tasks
- Average iterations per task
- Min/max iterations
- Iteration distribution histogram
- Per-task iteration tracking
- Comparison between MCP and baseline

## Output Formats

### Console Output
Beautiful Rich-formatted tables showing:
- Token usage comparison table
- Iteration statistics table
- Tool usage summary table
- Top tools by usage/failure
- Error analysis table
- Error category breakdowns

### JSON Output
All statistics included in `summary.comprehensive_stats`:
```json
{
  "summary": {
    "comprehensive_stats": {
      "mcp_tokens": { ... },
      "baseline_tokens": { ... },
      "mcp_costs": { ... },
      "baseline_costs": { ... },
      "mcp_tools": { ... },
      "mcp_errors": { ... },
      "baseline_errors": { ... },
      "mcp_iterations": { ... },
      "baseline_iterations": { ... }
    }
  }
}
```

### Markdown Report
Comprehensive markdown sections with:
- Token usage tables
- Cost breakdown tables
- Iteration statistics and distribution
- Tool usage tables with success rates
- Error analysis with categorization
- Sample errors with context

## Test Coverage

- **35 unit tests** in `test_statistics.py`
  - 100% coverage of statistics calculation functions
  - All error categories tested
  - Edge cases covered (empty results, missing fields, etc.)

- **3 integration tests** in `test_statistics_integration.py`
  - End-to-end JSON export
  - End-to-end Markdown export
  - Empty results handling

- **All existing tests pass** (65 related tests, 588 total non-async tests)

## Backwards Compatibility

- ✅ No breaking changes to existing APIs
- ✅ All existing tests pass
- ✅ Statistics are additive - old reports still work
- ✅ Graceful handling of missing fields
- ✅ Works with empty results

## Performance Impact

- Minimal - statistics are calculated once after evaluation
- O(n) complexity where n = number of tasks
- Lazy calculation - only computed when needed
- No impact on evaluation runtime

## Usage Examples

### Viewing in Console
```bash
mcpbr run config.yaml
```
Automatically displays comprehensive statistics in formatted tables.

### JSON Export
```bash
mcpbr run config.yaml --format json -o results.json
cat results.json | jq '.summary.comprehensive_stats'
```

### Markdown Report
```bash
mcpbr run config.yaml --format markdown -o report.md
```

### Programmatic Access
```python
from mcpbr.harness import run_evaluation
from mcpbr.statistics import ComprehensiveStatistics

results = await run_evaluation(config)
stats_dict = results.summary["comprehensive_stats"]

# Access specific metrics
print(f"Tool failure rate: {stats_dict['mcp_tools']['failure_rate']:.1%}")
print(f"Average iterations: {stats_dict['mcp_iterations']['avg_iterations']:.1f}")
```

## Benefits

1. **Better Debugging** - Error categorization and tool failure analysis
2. **Cost Optimization** - Detailed cost breakdown per task and per tool
3. **Performance Insights** - Iteration patterns and token usage analysis
4. **Tool Improvement** - Identify which tools need reliability improvements
5. **Infrastructure Monitoring** - Track timeouts, network issues, docker problems
6. **Actionable Data** - All statistics designed to drive specific improvements

## Documentation

- New comprehensive documentation in `docs/comprehensive-statistics.md`
- Includes interpretation guide
- Use cases and best practices
- Example queries for analysis

## Related Issues

Closes #9
