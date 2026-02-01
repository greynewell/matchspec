# Performance Profiling

mcpbr includes comprehensive performance profiling infrastructure to help you understand and optimize MCP server performance characteristics.

## Overview

The profiling system tracks:

- **Tool call latencies** with percentile breakdown (p50, p95, p99)
- **Memory usage** (peak and average RSS/VMS)
- **Infrastructure overhead** (Docker container and MCP server startup times)
- **Tool discovery speed** (time to first tool use)
- **Tool switching overhead** (time between different tool calls)
- **Automated insights** from profiling data

## Enabling Profiling

### Via CLI Flag

Enable profiling for a single run:

```bash
mcpbr run -c config.yaml --profile
```

### Via Configuration File

Enable profiling persistently in your config:

```yaml
# config.yaml
enable_profiling: true

mcp_server:
  command: npx
  args:
    - "-y"
    - "@modelcontextprotocol/server-filesystem"
    - "{workdir}"

model: claude-sonnet-4.5-20250929
benchmark: swe-bench-verified
sample_size: 10
```

## Profiling Output

When profiling is enabled, detailed performance metrics are included in the output JSON:

```json
{
  "tasks": [
    {
      "instance_id": "astropy__astropy-12907",
      "mcp": {
        "resolved": true,
        "runtime_seconds": 142.3,
        "tokens": {"input": 45000, "output": 12000},
        "cost": 1.23,
        "profiling": {
          "task_duration_seconds": 140.5,
          "tool_call_latencies": {
            "Read": {
              "count": 15,
              "avg_seconds": 0.8,
              "min_seconds": 0.2,
              "max_seconds": 2.1,
              "p50_seconds": 0.7,
              "p95_seconds": 1.5,
              "p99_seconds": 2.0,
              "total_seconds": 12.0
            },
            "Bash": {
              "count": 8,
              "avg_seconds": 2.3,
              "p50_seconds": 2.1,
              "p95_seconds": 5.1,
              "p99_seconds": 8.7
            }
          },
          "memory_profile": {
            "peak_rss_mb": 512.3,
            "avg_rss_mb": 387.5,
            "peak_vms_mb": 1024.0,
            "avg_vms_mb": 890.2,
            "sample_count": 5
          },
          "docker_startup_seconds": 2.1,
          "docker_teardown_seconds": 0.5,
          "mcp_server_startup_seconds": 1.8,
          "time_to_first_tool_seconds": 8.3,
          "tool_switching_overhead_seconds": 0.3,
          "total_tool_calls": 23,
          "successful_tool_calls": 22,
          "failed_tool_calls": 1
        }
      }
    }
  ]
}
```

## Understanding Metrics

### Tool Call Latencies

Latency metrics show how long each tool takes to execute:

- **count**: Total number of calls to this tool
- **avg_seconds**: Average execution time
- **p50/p95/p99**: Percentile values (50th, 95th, 99th percentile)
- **min/max**: Fastest and slowest calls
- **total_seconds**: Cumulative time spent in this tool

**Interpretation:**
- High p95/p99 compared to avg indicates occasional slow calls
- Consistent high latency suggests optimization opportunities
- Compare MCP vs baseline to understand MCP overhead

### Memory Profile

Memory metrics track resource usage during task execution:

- **peak_rss_mb**: Maximum Resident Set Size (actual memory used)
- **avg_rss_mb**: Average RSS throughout execution
- **peak_vms_mb**: Maximum Virtual Memory Size (allocated memory)
- **avg_vms_mb**: Average VMS throughout execution
- **sample_count**: Number of memory samples taken

**Interpretation:**
- High peak memory (>1GB) may cause issues on resource-constrained systems
- Large gap between avg and peak suggests bursty memory usage
- Compare MCP vs baseline to understand MCP memory overhead

### Infrastructure Overhead

Timing for setup and teardown operations:

- **docker_startup_seconds**: Time to create and start Docker container
- **docker_teardown_seconds**: Time to stop and remove container
- **mcp_server_startup_seconds**: Time to initialize MCP connection

**Interpretation:**
- Docker startup >5s may indicate image pulling or slow system
- MCP startup >2s suggests connection/initialization issues
- These are one-time costs per task

### Tool Discovery Metrics

Metrics about how quickly tools are discovered and used:

- **time_to_first_tool_seconds**: Time from task start to first tool call
- **tool_switching_overhead_seconds**: Average time between tool calls

**Interpretation:**
- Fast tool discovery (<5s) indicates good prompt and tool design
- Slow discovery (>15s) suggests the agent is taking time to understand available tools
- Low switching overhead indicates efficient tool use

## Automated Insights

The profiler automatically generates insights from the data:

```json
{
  "insights": [
    "Bash is the slowest tool (avg: 2.3s, p95: 5.1s)",
    "Docker startup adds 2.1s overhead per task",
    "MCP server initialization takes 1.8s",
    "Fast tool discovery: first tool use in 8.3s"
  ]
}
```

Common insights:
- **Slow tools**: Identifies tools with high latency
- **Infrastructure overhead**: Flags excessive Docker/MCP startup times
- **Tool discovery**: Highlights fast or slow tool adoption
- **High failure rate**: Warns about tools with frequent failures
- **Memory usage**: Alerts on high memory consumption

## Performance Optimization

### Reducing Tool Latency

If tool calls are slow:

1. **For Read operations**:
   - Use glob patterns to limit file reads
   - Read specific files instead of directory listings
   - Cache frequently accessed files

2. **For Bash commands**:
   - Optimize shell commands (avoid unnecessary pipes)
   - Use native tools instead of complex shell scripts
   - Run commands inside Docker when possible

3. **For Grep/search operations**:
   - Use specific patterns instead of broad searches
   - Limit search scope with file patterns

### Reducing Infrastructure Overhead

If Docker or MCP startup is slow:

1. **Docker startup**:
   - Use pre-built images (`use_prebuilt_images: true`)
   - Ensure Docker has sufficient resources allocated
   - Consider using local builds if pulling is slow

2. **MCP server startup**:
   - Check MCP server initialization code
   - Ensure network connectivity for remote servers
   - Monitor MCP server logs for issues

### Improving Tool Discovery

If time-to-first-tool is high:

1. **Prompt optimization**:
   - Make problem statements clearer
   - Provide explicit hints about available tools
   - Include examples of tool usage

2. **Tool design**:
   - Ensure tool names are descriptive
   - Provide clear tool descriptions
   - Group related tools logically

## Comparing MCP vs Baseline

Profiling both MCP and baseline runs allows comparison:

```python
# In your analysis script
import json

with open("results.json") as f:
    data = json.load(f)

for task in data["tasks"]:
    mcp_prof = task.get("mcp", {}).get("profiling", {})
    base_prof = task.get("baseline", {}).get("profiling", {})

    if mcp_prof and base_prof:
        mcp_time = mcp_prof.get("task_duration_seconds", 0)
        base_time = base_prof.get("task_duration_seconds", 0)
        overhead = mcp_time - base_time

        print(f"{task['instance_id']}: MCP overhead = {overhead:.1f}s")
```

## Performance Regression Detection

Use profiling data to detect performance regressions:

```bash
# Run baseline profiling
mcpbr run -c config.yaml --profile -o baseline.json

# Make changes to your MCP server
# ...

# Run new profiling with regression detection
mcpbr run -c config.yaml --profile -o new.json \
  --baseline-results baseline.json \
  --regression-threshold 0.0
```

The `--baseline-results` flag compares the new run against the baseline, and `--regression-threshold` sets the acceptable regression rate (0.0 = fail on any regression).

## API: Using the Profiler Programmatically

For custom integrations:

```python
from mcpbr.profiler import PerformanceProfiler
from datetime import datetime, timezone

# Initialize profiler
profiler = PerformanceProfiler(enable_memory_profiling=True)

# Start task timing
profiler.start_task()

# Record tool calls
start = datetime.now(timezone.utc)
# ... perform operation ...
end = datetime.now(timezone.utc)
profiler.record_tool_call(
    tool_name="Read",
    start_time=start,
    end_time=end,
    success=True,
    parameters={"file_path": "/test.py"},
    result_size_bytes=1024
)

# Sample memory periodically
profiler.sample_memory()

# Record infrastructure timing
profiler.record_docker_startup(2.5)
profiler.record_mcp_startup(1.8)

# End task and generate report
profiler.end_task()
report = profiler.generate_report()

# Get automated insights
insights = profiler.get_insights()
print("Insights:", insights)
```

## Best Practices

1. **Always profile both MCP and baseline** to understand MCP-specific overhead
2. **Run multiple samples** (at least 3-5 tasks) for reliable percentile data
3. **Profile in production-like conditions** (same hardware, network, etc.)
4. **Monitor trends over time** to catch performance regressions early
5. **Use insights as starting points** for optimization efforts
6. **Document performance requirements** and use profiling to verify them

## Troubleshooting

### Profiling Not Working

If profiling data is missing:

1. Check that `--profile` flag is used or `enable_profiling: true` in config
2. Verify psutil is installed: `pip install psutil`
3. Check logs for profiling errors

### Unexpected Memory Values

If memory usage seems wrong:

1. Memory is sampled periodically, not continuously
2. Includes Docker and all subprocess memory
3. Compare to system monitors for validation

### Percentile Calculation Issues

For small sample sizes (<10 tool calls):

- Percentiles may not be meaningful
- Focus on avg and max values instead
- Increase sample size for reliable percentiles

## Performance Goals

Recommended targets for good performance:

- **Tool call latency**: p95 < 3s for most tools
- **Docker startup**: < 5s with pre-built images
- **MCP server startup**: < 2s
- **Time to first tool**: < 10s
- **Tool failure rate**: < 5%
- **Peak memory**: < 2GB per task

These are guidelines; actual requirements depend on your use case.
