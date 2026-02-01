# Comprehensive Statistics

MCPBR now provides detailed statistics beyond basic success rates to help you understand and optimize your MCP server performance.

## What's Included

The enhanced statistics provide insights across multiple dimensions:

### 1. Token Usage Statistics
- **Total tokens** (input/output) across all tasks
- **Per-task averages** and ranges (min/max)
- **Detailed breakdown** for both MCP and baseline runs
- Helps you understand: API usage patterns, cost drivers, and efficiency

### 2. Cost Breakdown
- **Total cost** for the evaluation run
- **Average cost per task** and per resolved task
- **Min/max costs** to identify outliers
- **Cost-effectiveness metrics** comparing MCP vs baseline

### 3. Tool Usage Statistics (MCP Only)
- **Total tool calls** with success/failure rates
- **Per-tool breakdown** showing reliability
- **Most used** and **most failed** tools
- **Unique tools used** and average calls per task
- Helps you understand: Which tools are essential, which need improvement

### 4. Error Analysis
- **Total errors** and error rates
- **Categorization** (timeout, network, docker, MCP, etc.)
- **Most common errors** with sample instances
- **Timeout tracking** separately from other errors
- Helps you understand: Common failure modes, infrastructure issues

### 5. Iteration Statistics
- **Average iterations** per task
- **Distribution** showing iteration patterns
- **Min/max iterations** to find edge cases
- Helps you understand: Task complexity, convergence patterns

## Viewing Statistics

### Console Output

When you run an evaluation, comprehensive statistics are automatically displayed:

```bash
mcpbr run config.yaml
```

You'll see Rich-formatted tables showing:

```
Token Usage Statistics
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric          ┃ MCP Agent  ┃ Baseline ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Total Input     │ 45,230     │ 38,120   │
│ Total Output    │ 123,450    │ 98,340   │
│ Avg Input/Task  │ 4,523      │ 3,812    │
│ Avg Output/Task │ 12,345     │ 9,834    │
└─────────────────┴────────────┴──────────┘

Iteration Statistics
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric             ┃ MCP Agent  ┃ Baseline ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Total Iterations   │ 87         │ 56       │
│ Avg Iterations/Task│ 8.7        │ 5.6      │
│ Max Iterations     │ 15         │ 10       │
└────────────────────┴────────────┴──────────┘

MCP Tool Usage Statistics
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Metric           ┃ Value       ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Total Calls      │ 1,247       │
│ Successful Calls │ 1,198       │
│ Failed Calls     │ 49          │
│ Failure Rate     │ 3.9%        │
│ Unique Tools Used│ 12          │
└──────────────────┴─────────────┘

Top 10 Most Used Tools:
┏━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Tool       ┃ Calls ┃ Success Rate ┃
┡━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━┩
│ Read       │ 456   │ 99.3%        │
│ Bash       │ 312   │ 95.2%        │
│ Write      │ 234   │ 98.7%        │
└────────────┴───────┴──────────────┘

Error Analysis
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric       ┃ MCP Agent  ┃ Baseline ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Total Errors │ 2          │ 3        │
│ Error Rate   │ 20.0%      │ 30.0%    │
│ Timeout Count│ 1          │ 2        │
└──────────────┴────────────┴──────────┘
```

### JSON Output

All statistics are included in JSON results:

```bash
mcpbr run config.yaml --format json -o results.json
```

```json
{
  "summary": {
    "comprehensive_stats": {
      "mcp_tokens": {
        "total_input": 45230,
        "total_output": 123450,
        "avg_input_per_task": 4523.0,
        "avg_output_per_task": 12345.0,
        "max_input_per_task": 8920,
        "min_input_per_task": 2340,
        "per_task": {
          "task-1": {
            "input": 4523,
            "output": 12345,
            "total": 16868
          }
        }
      },
      "mcp_costs": {
        "total_cost": 0.5234,
        "avg_cost_per_task": 0.0523,
        "max_cost_per_task": 0.0892,
        "min_cost_per_task": 0.0234,
        "cost_per_resolved": 0.0654,
        "per_task": {
          "task-1": 0.0523
        }
      },
      "mcp_tools": {
        "total_calls": 1247,
        "total_successes": 1198,
        "total_failures": 49,
        "failure_rate": 0.0393,
        "unique_tools_used": 12,
        "avg_calls_per_task": 124.7,
        "per_tool": {
          "Read": {
            "total": 456,
            "succeeded": 453,
            "failed": 3,
            "failure_rate": 0.0066
          }
        },
        "most_used_tools": {
          "Read": 456,
          "Bash": 312
        },
        "most_failed_tools": {
          "Docker": 20,
          "MCP_Tool": 15
        }
      },
      "mcp_errors": {
        "total_errors": 2,
        "error_rate": 0.2,
        "timeout_count": 1,
        "timeout_rate": 0.1,
        "error_categories": {
          "timeout": 1,
          "docker": 1
        },
        "most_common_errors": {
          "Timeout exceeded": 1,
          "Docker container failed": 1
        },
        "sample_errors": [
          {
            "instance_id": "task-5",
            "error": "Timeout exceeded",
            "category": "timeout"
          }
        ]
      },
      "mcp_iterations": {
        "total_iterations": 87,
        "avg_iterations": 8.7,
        "max_iterations": 15,
        "min_iterations": 3,
        "distribution": {
          "3": 1,
          "5": 2,
          "8": 4,
          "15": 1
        },
        "per_task": {
          "task-1": 8
        }
      }
    }
  }
}
```

### Markdown Report

Statistics are also included in the Markdown report:

```bash
mcpbr run config.yaml --format markdown -o report.md
```

The report includes:
- Summary tables comparing MCP vs Baseline
- Detailed token usage breakdown
- Cost analysis with per-task details
- Tool usage statistics with failure analysis
- Error analysis with categorization
- Iteration distribution charts

## Interpreting the Statistics

### Token Usage
- **High input tokens**: May indicate verbose prompts or large context
- **High output tokens**: Could suggest the model is being too verbose
- **Wide variance**: Tasks have different complexity levels
- **Action**: Consider optimizing prompts for high-token outliers

### Tool Usage
- **High failure rate (>10%)**: Infrastructure or MCP server issues
- **Unused tools**: May indicate poor tool discoverability
- **Tool concentration**: Most tasks use a few core tools
- **Action**: Focus on improving reliability of most-used tools

### Errors
- **High timeout rate**: Tasks too complex or timeout too short
- **Network errors**: Infrastructure reliability issues
- **Docker errors**: Environment setup problems
- **MCP errors**: Server-specific issues
- **Action**: Address most common error categories first

### Iterations
- **High average iterations**: Tasks require multiple attempts
- **Wide distribution**: Some tasks are much harder than others
- **Max iterations hit**: May need to increase iteration limit
- **Action**: Analyze high-iteration tasks for common patterns

## Use Cases

### 1. Debugging MCP Server Issues
```bash
# Look at tool failure rates
mcpbr run config.yaml | grep "Failed Calls"

# Check error categories
mcpbr run config.yaml --format json -o results.json
cat results.json | jq '.summary.comprehensive_stats.mcp_errors.error_categories'
```

### 2. Cost Optimization
```bash
# Find expensive tasks
cat results.json | jq '.summary.comprehensive_stats.mcp_costs.per_task | to_entries | sort_by(.value) | reverse | .[0:5]'

# Compare MCP vs baseline costs
cat results.json | jq '{
  mcp: .summary.comprehensive_stats.mcp_costs.total_cost,
  baseline: .summary.comprehensive_stats.baseline_costs.total_cost,
  difference: (.summary.comprehensive_stats.mcp_costs.total_cost - .summary.comprehensive_stats.baseline_costs.total_cost)
}'
```

### 3. Performance Analysis
```bash
# Check iteration patterns
cat results.json | jq '.summary.comprehensive_stats.mcp_iterations.distribution'

# Find high-iteration outliers
cat results.json | jq '.summary.comprehensive_stats.mcp_iterations.per_task | to_entries | sort_by(.value) | reverse | .[0:5]'
```

### 4. Tool Reliability Monitoring
```bash
# List tools with high failure rates
cat results.json | jq '.summary.comprehensive_stats.mcp_tools.per_tool | to_entries | map(select(.value.failure_rate > 0.1)) | sort_by(.value.failure_rate) | reverse'

# Track improvement over time
for file in results-*.json; do
  echo "$file: $(jq '.summary.comprehensive_stats.mcp_tools.failure_rate' $file)"
done
```

## API Usage

If you're using MCPBR programmatically, you can access statistics directly:

```python
from mcpbr.harness import run_evaluation
from mcpbr.statistics import calculate_comprehensive_statistics

# Run evaluation
results = await run_evaluation(config)

# Statistics are automatically included
stats_dict = results.summary["comprehensive_stats"]

# Or calculate manually from results
from mcpbr.statistics import ComprehensiveStatistics
stats = ComprehensiveStatistics(**stats_dict)

# Access specific metrics
print(f"MCP tool failure rate: {stats.mcp_tools.failure_rate:.1%}")
print(f"Average iterations: {stats.mcp_iterations.avg_iterations:.1f}")
print(f"Total cost: ${stats.mcp_costs.total_cost:.4f}")

# Export to dict for custom processing
stats_dict = stats.to_dict()
```

## Best Practices

1. **Regular Monitoring**: Track statistics across runs to identify trends
2. **Set Baselines**: Establish expected ranges for key metrics
3. **Alert on Anomalies**: High failure rates or costs should trigger investigation
4. **Iterate on Tools**: Use statistics to prioritize tool improvements
5. **Cost Budgets**: Monitor costs against budgets using cost statistics
6. **Error Analysis**: Categorize and track error patterns over time

## See Also

- [Configuration Guide](configuration.md)
- [MCP Integration](mcp-integration.md)
- [Best Practices](best-practices.md)
