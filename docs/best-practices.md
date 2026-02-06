---
description: "Best practices for running mcpbr evaluations including cost optimization, sample sizing, MCP server configuration, and result interpretation."
faq:
  - q: "What are the best practices for running mcpbr evaluations?"
    a: "Start with small sample sizes (n=5-10) to validate your setup, use templates for common scenarios, monitor costs by tracking token usage, and save results to compare different configurations. Always test your MCP server standalone before benchmarking."
  - q: "How can I optimize mcpbr evaluation costs?"
    a: "Use faster/cheaper models like Haiku for development, start with small samples, reduce max_iterations for initial testing, use --mcp-only to skip baseline runs during development, and enable verbose logging to catch issues early."
  - q: "What's the recommended workflow for testing a new MCP server?"
    a: "1) Test server standalone, 2) Run quick-test template with n=1, 3) Scale to n=5-10, 4) Analyze tool usage in results, 5) Optimize based on findings, 6) Run full evaluation with n=25-50+."
  - q: "How do I avoid common mcpbr pitfalls?"
    a: "Test Docker setup first, verify API keys are set, use pre-built images when available, set appropriate timeouts for your tasks, start with small samples, and always save results to enable comparisons and regression detection."
  - q: "How should I secure API keys when running mcpbr?"
    a: "Never hardcode API keys in config files. Use environment variables, .env files (gitignored), or secret managers like 1Password CLI, AWS Secrets Manager, or HashiCorp Vault. In CI/CD, store keys as repository secrets."
  - q: "How do I optimize mcpbr performance for large benchmarks?"
    a: "Tune max_concurrent based on available RAM (roughly 1-3 GB per container), use pre-built Docker images, enable result caching with cache_enabled, and use setup_command for MCP server pre-computation. Monitor with docker stats."
  - q: "How do I set up mcpbr in a CI/CD pipeline?"
    a: "Install mcpbr in your CI runner, set ANTHROPIC_API_KEY from secrets, use small sample sizes (n=10) for PRs, enable regression detection with --baseline-results and --regression-threshold, and output JUnit XML for test reporting."
  - q: "How do I set a budget limit for mcpbr evaluations?"
    a: "Set budget: 50.00 in your config YAML to cap spending at $50. Combine with sample_size, max_iterations, and timeout_seconds for layered cost control. Monitor actual costs via token usage in JSON output."
  - q: "How do I make statistically valid comparisons between MCP servers?"
    a: "Use the same task set (--task flags), same model, same benchmark, and same parameters. Sample sizes below 25 have high variance. Check if confidence intervals overlap before concluding one config is better."
---

# Best Practices Guide

This guide helps you get the most value from mcpbr while avoiding common pitfalls. Whether you're testing a new MCP server, optimizing costs, or setting up CI/CD pipelines, these practices will help you work effectively.

## Quick Reference

| Scenario | Recommended Approach |
|----------|---------------------|
| First-time setup | Use `quick-test` template, verify with n=1 |
| MCP server testing | Standalone test → quick-test → scale gradually |
| Cost optimization | Use Haiku model, small samples, --mcp-only flag |
| Production evaluation | Use `production` template, save all outputs |
| CI/CD integration | Use regression detection, JUnit XML, notifications |
| Security testing | Start with cybergym-basic, progress to advanced |
| Debugging failures | Enable -vv, use --log-dir, analyze tool usage |

## Benchmark Selection Guidelines

### Choosing the Right Benchmark

**Use SWE-bench when:**
- Testing code exploration and bug-fixing capabilities
- Evaluating Python-focused MCP servers
- Need proven, standardized benchmarks
- Want fast evaluation with pre-built images

**Use CyberGym when:**
- Testing security analysis capabilities
- Evaluating C/C++ code understanding
- Need vulnerability detection benchmarks
- Want to test different difficulty levels

### SWE-bench Best Practices

**Start Small, Scale Gradually**
```bash
# Step 1: Single task smoke test
mcpbr run -c config.yaml -n 1 -v

# Step 2: Small sample
mcpbr run -c config.yaml -n 5 -o results-5.json

# Step 3: Medium sample
mcpbr run -c config.yaml -n 25 -o results-25.json

# Step 4: Full evaluation (if needed)
mcpbr run -c config.yaml -o results-full.json
```

**Use Pre-built Images**
```yaml
use_prebuilt_images: true  # Much faster and more reliable
```

Pre-built images provide:
- Validated dependency installation
- Consistent evaluation environment
- Faster startup (no package installation)
- Working Python imports inside containers

**Anti-pattern:** Disabling pre-built images without good reason
```bash
# Avoid this unless debugging dependency issues
mcpbr run -c config.yaml --no-prebuilt
```

### CyberGym Best Practices

**Choose Appropriate Difficulty Level**

| Level | Context | Use Case | Typical Success Rate |
|-------|---------|----------|---------------------|
| 0 | Minimal | Test discovery abilities | Low (10-20%) |
| 1 | Type only | Balanced challenge | Medium (20-40%) |
| 2 | Description | Practical testing | Higher (40-60%) |
| 3 | Full context | Maximum guidance | Highest (60-80%) |

**Start with Level 2 for Most Use Cases**
```bash
# Level 2 provides good balance of challenge and success
mcpbr run -c config.yaml --benchmark cybergym --level 2 -n 5
```

**Increase Timeouts for Compilation**
```yaml
benchmark: cybergym
timeout_seconds: 600  # CyberGym needs more time for builds
max_iterations: 15
```

**Anti-pattern:** Using level 3 for all testing
```bash
# Level 3 is too easy for meaningful evaluation
mcpbr run -c config.yaml --benchmark cybergym --level 3  # Not recommended
```

## MCP Server Configuration Best Practices

### Selecting MCP Servers

**Match Server Capabilities to Benchmark Needs**

For **SWE-bench** (bug fixing):
- Filesystem access (read/write)
- Code search capabilities
- Test execution tools
- Git operations

For **CyberGym** (security):
- Code analysis tools
- AST parsing
- Vulnerability pattern detection
- Build system integration

### Configuration Patterns

**Good: Clear, Minimal Configuration**
```yaml
mcp_server:
  name: "mcpbr"
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]
  env: {}
```

**Better: With Environment Variables**
```yaml
mcp_server:
  name: "codebase"
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server"]
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
    LOG_LEVEL: "info"
```

**Anti-pattern: Hardcoded Secrets**
```yaml
mcp_server:
  env:
    API_KEY: "sk-1234..."  # NEVER hardcode secrets!
```

### Testing Your MCP Server

**Step 1: Standalone Verification**
```bash
# Test server starts correctly
npx -y @modelcontextprotocol/server-filesystem /tmp/test

# For custom servers
python -m my_mcp_server --workspace /tmp/test
```

**Step 2: Quick Smoke Test**
```bash
# Single task with MCP only
mcpbr run -c config.yaml -n 1 -v -M
```

**Step 3: Analyze Tool Usage**
```bash
# Check if MCP tools are being used
mcpbr run -c config.yaml -n 5 -o results.json
cat results.json | jq '.tasks[0].mcp.tool_usage'
```

**Step 4: Compare Against Baseline**
```bash
# Full comparison
mcpbr run -c config.yaml -n 10 -o results.json
```

**Red Flags:**
- MCP tools never appear in tool_usage
- Tool usage is always 0 or very low
- Similar results between MCP and baseline
- Server startup warnings in logs

## Performance Optimization Tips

### Docker Resource Management

**Set Appropriate Concurrency**
```yaml
# For most systems
max_concurrent: 4

# For powerful machines (16+ GB RAM, 8+ cores)
max_concurrent: 8

# For limited resources or API rate limits
max_concurrent: 2

# For debugging
max_concurrent: 1
```

**Monitor Resource Usage**
```bash
# Check Docker resource consumption
docker stats

# Check running containers
docker ps | grep mcpbr
```

**Clean Up Orphaned Containers**
```bash
# Preview what will be removed
mcpbr cleanup --dry-run

# Remove orphaned containers
mcpbr cleanup -f
```

### Apple Silicon Optimization

**Expected Performance:**
- Tasks take 2-3x longer than native x86_64
- This is normal due to emulation
- Pre-built images help reduce overhead

**Recommended Settings:**
```yaml
max_concurrent: 2        # Reduce concurrency
timeout_seconds: 600     # Increase timeouts
use_prebuilt_images: true  # Essential for performance
```

**Install Rosetta 2** (if not already installed)
```bash
softwareupdate --install-rosetta
```

### Timeout Tuning

**Default Timeouts by Benchmark**

| Benchmark | Recommended Timeout | Max Iterations |
|-----------|-------------------|----------------|
| SWE-bench | 300-600s | 10-30 |
| CyberGym | 600-900s | 15-30 |

**Adjust Based on Task Complexity**
```yaml
# Simple tasks
timeout_seconds: 300
max_iterations: 10

# Complex tasks or slow hardware
timeout_seconds: 600
max_iterations: 30
```

**Anti-pattern: Extremely Long Timeouts**
```yaml
timeout_seconds: 3600  # 1 hour - probably too long
max_iterations: 100    # Too many iterations
```

### Model Selection

**Development/Testing:**
```yaml
model: "haiku"  # Fast, cheap, good for iteration
```

**Production/Benchmarking:**
```yaml
model: "sonnet"  # Best balance of performance and cost
```

**Maximum Performance:**
```yaml
model: "opus"  # Most capable, highest cost
```

## Cost Management Strategies

### Understanding Costs

**Token Usage Factors:**
- Model choice (Haiku < Sonnet < Opus)
- Number of iterations (more turns = more tokens)
- Task complexity (complex bugs require more exploration)
- Sample size (most obvious cost driver)

**Typical Costs (per task, Sonnet model):**
- Simple task: $0.10-0.30 (5-10K output tokens)
- Medium task: $0.30-0.80 (10-20K output tokens)
- Complex task: $0.80-2.00 (20-50K output tokens)

### Cost Optimization Strategies

**1. Start Small**
```bash
# Test with 1 task first
mcpbr run -c config.yaml -n 1

# Scale to 5 tasks to validate
mcpbr run -c config.yaml -n 5

# Only run full evaluation when confident
mcpbr run -c config.yaml -n 50
```

**2. Use Faster Models for Development**
```yaml
# Development config
model: "haiku"
sample_size: 5
max_iterations: 5
timeout_seconds: 180
```

**3. Skip Baseline During Iteration**
```bash
# Only run MCP agent while developing
mcpbr run -c config.yaml -M -n 5
```

**4. Reduce Iterations**
```yaml
max_iterations: 10  # Instead of 30
```

**5. Monitor Token Usage**
```bash
# Save results and check token consumption
mcpbr run -c config.yaml -n 5 -o results.json

# Analyze token usage
cat results.json | jq '.tasks[] | {id: .instance_id, tokens: .mcp.tokens}'
```

**Anti-pattern: Running Full Evaluations Repeatedly**
```bash
# Bad: Running 300 tasks multiple times during development
mcpbr run -c config.yaml  # Default: full dataset
mcpbr run -c config.yaml  # Oops, again...
# Result: Hundreds of dollars in API costs
```

**Good Pattern: Incremental Testing**
```bash
# Development cycle
mcpbr run -c config.yaml -n 1 -M  # $0.20
mcpbr run -c config.yaml -n 5 -M  # $1-2
mcpbr run -c config.yaml -n 10    # $5-10
# Only when ready:
mcpbr run -c config.yaml -n 50 -o final.json  # $50-100
```

### Cost Tracking

**Track Costs Per Run**
```python
import json

with open("results.json") as f:
    results = json.load(f)

# Calculate approximate costs (Sonnet pricing as of 2026)
INPUT_COST = 3.00 / 1_000_000   # $3 per 1M tokens
OUTPUT_COST = 15.00 / 1_000_000  # $15 per 1M tokens

total_cost = 0
for task in results["tasks"]:
    mcp = task.get("mcp", {})
    tokens = mcp.get("tokens", {})
    input_tokens = tokens.get("input", 0)
    output_tokens = tokens.get("output", 0)

    task_cost = (input_tokens * INPUT_COST) + (output_tokens * OUTPUT_COST)
    total_cost += task_cost

print(f"Total cost: ${total_cost:.2f}")
print(f"Average per task: ${total_cost / len(results['tasks']):.2f}")
```

## Result Interpretation Guidelines

### Understanding Resolution Rates

**What "Resolved" Means:**
1. Patch was generated
2. Patch applied cleanly
3. All FAIL_TO_PASS tests now pass
4. All PASS_TO_PASS tests still pass

**Interpreting Improvement:**
```text
MCP: 32% resolved (8/25)
Baseline: 20% resolved (5/25)
Improvement: +60%
```

This means:
- MCP agent is 60% better than baseline
- Your MCP server helped on 3 additional tasks
- Both agents struggled (absolute rates are low)

### Success Rate Benchmarks

**Typical Resolution Rates (SWE-bench Lite):**

| Configuration | Expected Range | Interpretation |
|--------------|----------------|----------------|
| Baseline (Sonnet) | 15-25% | Normal for single-shot |
| Basic filesystem MCP | 20-30% | Modest improvement |
| Advanced MCP server | 30-45% | Significant value |
| State-of-the-art | 45-60% | Excellent performance |

**Low Rates (Both < 15%):**
- Tasks may be inherently difficult
- Sample may include hard tasks
- Timeouts may be too short
- Model may need more iterations

**High Baseline (> 25%):**
- Sample may include easier tasks
- Good task selection
- Model is performing well

**Low Improvement (< 10%):**
- MCP tools not providing value
- Tools not being used effectively
- Baseline already sufficient

### Analyzing Tool Usage

**Extract Tool Statistics**
```bash
cat results.json | jq '.tasks[0].mcp.tool_usage'
```

**Healthy Tool Distribution:**
```json
{
  "Grep": 15,        // Searching code
  "Read": 20,        // Reading files
  "Bash": 25,        // Running tests
  "Edit": 5,         // Making changes
  "mcp__read": 10    // MCP tools being used
}
```

**Red Flags:**
```json
{
  "TodoWrite": 50,   // Too much planning, not enough action
  "mcp__search": 0   // MCP tools not being used at all
}
```

### Comparing Configurations

**Save Results with Descriptive Names**
```bash
mcpbr run -c filesystem.yaml -o results-filesystem.json
mcpbr run -c supermodel.yaml -o results-supermodel.json
```

**Compare Resolution Rates**
```python
import json

def compare_results(file1, file2):
    with open(file1) as f1, open(file2) as f2:
        r1 = json.load(f1)
        r2 = json.load(f2)

    rate1 = r1["summary"]["mcp"]["rate"]
    rate2 = r2["summary"]["mcp"]["rate"]

    print(f"{file1}: {rate1:.1%}")
    print(f"{file2}: {rate2:.1%}")
    print(f"Difference: {(rate2 - rate1):.1%}")

compare_results("results-filesystem.json", "results-supermodel.json")
```

## Security Considerations

### API Key Management

**Good: Environment Variables**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
mcpbr run -c config.yaml
```

**Better: Shell Profile**
```bash
# Add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Best: Secret Management**
```bash
# Using 1Password CLI
export ANTHROPIC_API_KEY=$(op read "op://vault/mcpbr/api_key")

# Using AWS Secrets Manager
export ANTHROPIC_API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id mcpbr/anthropic-key --query SecretString --output text)
```

**Anti-pattern: Hardcoded in Config**
```yaml
# NEVER do this
env:
  ANTHROPIC_API_KEY: "sk-ant-..."  # Will be committed to git!
```

### Docker Security

**Network Isolation** (when external access not needed)
```yaml
# For most use cases, network access is required for API calls
# But if testing without MCP:
docker_network_mode: "none"
```

**Container Cleanup**
```bash
# Regularly clean up orphaned containers
mcpbr cleanup -f

# Check for running containers
docker ps | grep mcpbr
```

### Data Security

**Sensitive Repositories:**
- mcpbr runs on public datasets (SWE-bench, CyberGym)
- Do NOT use with proprietary code
- Task data is sent to Anthropic API
- Logs may contain code snippets

**Log Management:**
```bash
# Logs contain code and conversations
mcpbr run -c config.yaml --log-dir logs/

# Secure log files
chmod 700 logs/
```

## CI/CD Integration Patterns

### GitHub Actions

**Basic Workflow**
```yaml
name: MCP Benchmark

on:
  pull_request:
    paths:
      - 'mcp-server/**'

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install mcpbr
        run: pip install mcpbr

      - name: Run benchmark
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          mcpbr run -c config.yaml -n 10 -o results.json

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: results.json
```

**With Regression Detection**
```yaml
- name: Download baseline
  run: |
    gh run download --name baseline-results --dir .

- name: Run with regression detection
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    mcpbr run -c config.yaml -n 25 \
      --baseline-results baseline.json \
      --regression-threshold 0.1 \
      --slack-webhook ${{ secrets.SLACK_WEBHOOK }} \
      -o current.json
```

**With JUnit XML**
```yaml
- name: Run benchmark
  run: mcpbr run -c config.yaml --output-junit junit.xml

- name: Publish test results
  uses: EnricoMi/publish-unit-test-result-action@v2
  if: always()
  with:
    files: junit.xml
```

### GitLab CI

```yaml
mcpbr-benchmark:
  image: python:3.11
  services:
    - docker:dind
  variables:
    DOCKER_HOST: tcp://docker:2375
  script:
    - pip install mcpbr
    - mcpbr run -c config.yaml -n 10 --output-junit junit.xml
  artifacts:
    reports:
      junit: junit.xml
    paths:
      - results.json
  only:
    - merge_requests
```

### Cost Control in CI/CD

**Sample Size Limits**
```yaml
# Don't run full benchmarks on every PR
mcpbr run -c config.yaml -n 10  # Small sample for PRs

# Full benchmarks on main branch only
mcpbr run -c config.yaml -n 50  # Larger sample for releases
```

**Conditional Execution**
```yaml
# Only run on MCP server changes
on:
  push:
    paths:
      - 'mcp-server/**'
      - 'config.yaml'
```

## Debugging and Troubleshooting

### Diagnostic Workflow

**Step 1: Verify Prerequisites**
```bash
# Check Docker
docker info

# Check API key
echo $ANTHROPIC_API_KEY | head -c 10

# Check Claude CLI
which claude
```

**Step 2: Test MCP Server Standalone**
```bash
# For filesystem server
npx -y @modelcontextprotocol/server-filesystem /tmp/test

# For custom servers
python -m my_mcp_server --workspace /tmp/test
```

**Step 3: Run Single Task with Verbose Logging**
```bash
mcpbr run -c config.yaml -n 1 -vv --log-dir debug/
```

**Step 4: Analyze Logs**
```bash
# Check system events
cat debug/*.json | jq '.events[] | select(.type == "system")'

# Check tool usage
cat debug/*.json | jq '.events[] | select(.type == "assistant") |
  .message.content[] | select(.type == "tool_use") | .name'
```

### Common Issues and Solutions

**MCP Server Not Starting**
```text
Warning: MCP server add failed (exit 1)
```

Solutions:
1. Test server command directly
2. Check environment variables are set
3. Verify command is in PATH
4. Check server logs for errors

**No Patch Generated**
```text
No changes made by Claude Code
```

Causes:
- Task too complex for iterations limit
- Agent couldn't find solution
- Agent made changes then reverted

Solutions:
```yaml
max_iterations: 30  # Increase from 10
timeout_seconds: 600  # Increase from 300
```

**Timeouts**
```text
Timeout after 300 seconds
```

Solutions:
```yaml
timeout_seconds: 600
max_concurrent: 2  # Reduce load
```

**Tests Failing**
```text
FAIL_TO_PASS: 0/2 passed
```

This means:
- Patch applied successfully
- But didn't fix the bug
- Agent made incorrect changes
- Not an mcpbr issue - agent behavior

### Debug Flags

**Verbose Output Levels**
```bash
# Standard output
mcpbr run -c config.yaml

# Verbose: summary + task progress
mcpbr run -c config.yaml -v

# Very verbose: detailed tool calls
mcpbr run -c config.yaml -vv
```

**Per-Instance Logs**
```bash
# Create detailed JSON logs for each task
mcpbr run -c config.yaml --log-dir logs/

# Logs are timestamped: instance_id_runtype_timestamp.json
ls logs/
# django__django-11099_mcp_20260120_143052.json
# django__django-11099_baseline_20260120_143156.json
```

**Single Log File**
```bash
# All events in one file
mcpbr run -c config.yaml --log-file full.log
```

## Iterative Development Workflow

### Phase 1: Quick Validation

**Goal:** Verify basic functionality

```bash
# 1. Test MCP server starts
npx -y @modelcontextprotocol/server-filesystem /tmp/test

# 2. Run single task
mcpbr init -t quick-test
mcpbr run -c mcpbr.yaml -v

# 3. Check if it worked
# - Did the server start? (check for warnings)
# - Were tools registered? (check verbose output)
# - Was a patch generated?
```

**Success Criteria:**
- No server startup errors
- Task completes without timeout
- Patch generated (even if incorrect)

### Phase 2: Small-Scale Testing

**Goal:** Validate at small scale

```bash
# 1. Run 5 tasks with MCP only
mcpbr run -c config.yaml -n 5 -M -o dev-mcp.json

# 2. Analyze tool usage
cat dev-mcp.json | jq '.tasks[].mcp.tool_usage'

# 3. Check if MCP tools are used
cat dev-mcp.json | jq '.tasks[].mcp.tool_usage |
  to_entries | map(select(.key | startswith("mcp")))'
```

**Success Criteria:**
- MCP tools appear in tool_usage
- At least 1-2 tasks resolved
- No consistent errors

### Phase 3: Baseline Comparison

**Goal:** Measure improvement

```bash
# 1. Run 10 tasks with MCP + baseline
mcpbr run -c config.yaml -n 10 -o comparison.json

# 2. Check improvement
cat comparison.json | jq '.summary'

# 3. Find MCP-only wins
cat comparison.json | jq '.tasks[] |
  select(.mcp.resolved == true and .baseline.resolved == false) |
  .instance_id'
```

**Success Criteria:**
- MCP rate > baseline rate
- At least 1-2 MCP-only wins
- Improvement > 10%

### Phase 4: Optimization

**Goal:** Improve performance based on findings

**Analyze Failures:**
```bash
# Find tasks where MCP failed
cat comparison.json | jq '.tasks[] |
  select(.mcp.resolved == false) |
  {id: .instance_id, error: .mcp.error, iterations: .mcp.iterations}'
```

**Common Optimizations:**
- Increase iterations if hitting limits
- Adjust timeout if tasks timeout
- Modify MCP server configuration
- Update agent prompt

### Phase 5: Production Evaluation

**Goal:** Final comprehensive benchmark

```bash
# 1. Run larger sample
mcpbr run -c config.yaml -n 50 -o production.json -r report.md

# 2. Save for regression detection
cp production.json baseline.json

# 3. Generate all outputs
mcpbr run -c config.yaml -n 50 \
  -o results.json \
  -y results.yaml \
  -r report.md \
  --output-junit junit.xml \
  --log-dir logs/
```

**Success Criteria:**
- Statistically significant sample (n >= 25)
- Results saved for future comparison
- Improvement is consistent
- Documentation completed

## Templates and Configuration

### Using Templates Effectively

**Start with Templates**
```bash
# List all templates
mcpbr templates

# Use appropriate template
mcpbr init -t quick-test      # For testing
mcpbr init -t filesystem      # For development
mcpbr init -t production      # For final evaluation
```

**Customize After Generation**
```bash
# Generate from template
mcpbr init -t filesystem

# Edit to customize
vim mcpbr.yaml

# Test your changes
mcpbr run -c mcpbr.yaml -n 1 -v
```

### Configuration Patterns

**Development Configuration**
```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "haiku"              # Fast and cheap
sample_size: 5              # Small sample
max_concurrent: 1           # Serial execution for debugging
timeout_seconds: 180        # Shorter timeout
max_iterations: 5           # Fewer iterations
use_prebuilt_images: true
```

**Production Configuration**
```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"             # Best balance
sample_size: 50             # Meaningful sample
max_concurrent: 4           # Parallel execution
timeout_seconds: 600        # Generous timeout
max_iterations: 30          # More iterations
use_prebuilt_images: true
```

**CI/CD Configuration**
```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"
sample_size: 10             # Quick feedback
max_concurrent: 2           # Don't overload
timeout_seconds: 300
max_iterations: 15          # Balanced
use_prebuilt_images: true
```

## Examples and Use Cases

### Use Case 1: Testing a New MCP Server

**Scenario:** You've built a custom MCP server with advanced code search

**Workflow:**
```bash
# 1. Create config from template
mcpbr init -t custom-python -o my-server.yaml

# 2. Edit to point to your server
# Update args: ["-m", "my_mcp_server", "--workspace", "{workdir}"]

# 3. Test standalone
python -m my_mcp_server --workspace /tmp/test

# 4. Quick test
mcpbr run -c my-server.yaml -n 1 -v -M

# 5. Small comparison
mcpbr run -c my-server.yaml -n 10 -o results.json

# 6. Analyze tool usage
cat results.json | jq '.tasks[0].mcp.tool_usage'

# 7. Full evaluation if promising
mcpbr run -c my-server.yaml -n 50 -o final.json -r report.md
```

### Use Case 2: Comparing Two MCP Servers

**Scenario:** Evaluating filesystem vs. Supermodel

**Workflow:**
```bash
# 1. Create configurations
mcpbr init -t filesystem -o filesystem.yaml
mcpbr init -t supermodel -o supermodel.yaml

# 2. Set API key for Supermodel
export SUPERMODEL_API_KEY="your-key"

# 3. Run identical samples
mcpbr run -c filesystem.yaml -n 25 -o fs-results.json
mcpbr run -c supermodel.yaml -n 25 -o sm-results.json

# 4. Compare results
python compare.py fs-results.json sm-results.json

# 5. Analyze differences
# Check which tasks each solved
# Compare tool usage patterns
# Analyze token consumption
```

### Use Case 3: Cost-Optimized Development

**Scenario:** Limited budget, need to test iteratively

**Workflow:**
```bash
# Phase 1: Ultra-cheap validation (< $1)
mcpbr init -t quick-test
# Edit: model: "haiku", sample_size: 1, max_iterations: 3
mcpbr run -c mcpbr.yaml -M  # MCP only, ~$0.10

# Phase 2: Small test (< $5)
# Edit: sample_size: 5, max_iterations: 5
mcpbr run -c mcpbr.yaml -M  # ~$2-3

# Phase 3: Baseline comparison (< $20)
# Edit: sample_size: 10, max_iterations: 10
mcpbr run -c mcpbr.yaml -o results.json  # ~$10-15

# Phase 4: Production (budgeted)
# Switch to: model: "sonnet", sample_size: 50
mcpbr run -c mcpbr.yaml -o final.json  # ~$100-150
```

### Use Case 4: CI/CD Integration

**Scenario:** Automated regression testing on PR

**Workflow:**
```yaml
# .github/workflows/mcp-test.yml
name: MCP Regression Test

on:
  pull_request:
    paths: ['mcp-server/**']

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Download baseline
        run: gh run download --name baseline --dir .

      - name: Install mcpbr
        run: pip install mcpbr

      - name: Run regression test
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          mcpbr run -c config.yaml -n 10 \
            --baseline-results baseline.json \
            --regression-threshold 0.1 \
            --slack-webhook ${{ secrets.SLACK_WEBHOOK }} \
            -o current.json \
            --output-junit junit.xml

      - name: Publish results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: junit.xml
```

### Use Case 5: Security Research

**Scenario:** Evaluating vulnerability detection capabilities

**Workflow:**
```bash
# 1. Start with basic level
mcpbr init -t cybergym-basic

# 2. Test single vulnerability
mcpbr run -c mcpbr.yaml -n 1 -v --log-dir logs/

# 3. Check PoC generation
# Look for poc.c, poc.py in logs
cat logs/*.json | jq '.events[] | select(.type == "assistant") |
  .message.content[] | select(.type == "text") | .text' | grep -i poc

# 4. Scale up
mcpbr run -c mcpbr.yaml -n 5 -o level1.json

# 5. Try higher level
mcpbr init -t cybergym-advanced -o level3.yaml
mcpbr run -c level3.yaml -n 5 -o level3.json

# 6. Compare difficulty levels
python compare.py level1.json level3.json
```

## Anti-Patterns to Avoid

### Configuration Anti-Patterns

**Bad: Hardcoded secrets**
```yaml
mcp_server:
  env:
    API_KEY: "sk-1234..."  # Will be committed!
```

**Bad: Unrealistic timeouts**
```yaml
timeout_seconds: 3600  # 1 hour
max_iterations: 100
```

**Bad: Excessive concurrency**
```yaml
max_concurrent: 20  # Will hit rate limits
```

### Workflow Anti-Patterns

**Bad: Running full benchmark during development**
```bash
# Don't do this repeatedly during development
mcpbr run -c config.yaml  # Full dataset every time!
```

**Bad: Not saving results**
```bash
# No way to compare or track progress
mcpbr run -c config.yaml  # Results lost!
```

**Bad: Skipping standalone testing**
```bash
# MCP server fails, wasting API costs
mcpbr run -c broken-config.yaml -n 50
```

### Analysis Anti-Patterns

**Bad: Focusing only on resolution rate**
```python
# Missing important insights
rate = results["summary"]["mcp"]["rate"]
print(f"Rate: {rate}")  # That's it?
```

**Bad: Not checking tool usage**
```python
# MCP tools might not be used at all!
print(f"Resolved: {results['summary']['mcp']['resolved']}")
```

**Bad: Comparing different samples**
```bash
# Results not comparable
mcpbr run -c config-a.yaml -n 10  # Random 10
mcpbr run -c config-b.yaml -n 10  # Different random 10
```

## Quick Start Checklist

**Before First Run:**
- [ ] Docker installed and running
- [ ] ANTHROPIC_API_KEY set
- [ ] Claude CLI installed (`which claude`)
- [ ] mcpbr installed (`mcpbr --version`)

**For New MCP Server:**
- [ ] Test server standalone
- [ ] Create config from template
- [ ] Run single task test (n=1)
- [ ] Check tool registration
- [ ] Verify MCP tools used
- [ ] Scale to 5-10 tasks
- [ ] Save results
- [ ] Compare vs baseline

**For Production Run:**
- [ ] Config validated
- [ ] Sample size determined
- [ ] Timeout appropriate
- [ ] Output paths specified
- [ ] Baseline results saved
- [ ] Budget confirmed
- [ ] Results will be saved

## Security Best Practices

Securing your mcpbr deployment is critical, especially when running evaluations in CI/CD pipelines, shared environments, or with third-party MCP servers.

### API Key Management

!!! danger "Never commit API keys to version control"
    API keys in configuration files or source code are one of the most common security incidents. Use environment variables or secret management tools exclusively.

**Hierarchy of Key Management (from basic to advanced):**

| Method | Security Level | Best For |
|--------|---------------|----------|
| Environment variable | Basic | Local development |
| `.env` file (gitignored) | Better | Team development |
| Shell profile (`~/.zshrc`) | Better | Personal machines |
| Secret manager (1Password, AWS SM) | Best | Production / CI/CD |
| Hardware security module (HSM) | Maximum | Enterprise deployments |

**Using `.env` files with mcpbr:**

mcpbr automatically loads `.env` files from the current directory. Create one but ensure it is never committed:

```bash
# Create .env file
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
echo 'SUPERMODEL_API_KEY=your-key-here' >> .env

# Ensure .env is gitignored
echo '.env' >> .gitignore
```

Then reference variables in your config:

```yaml
mcp_server:
  env:
    SUPERMODEL_API_KEY: "${SUPERMODEL_API_KEY}"
```

**Using secret managers in CI/CD:**

```bash
# AWS Secrets Manager
export ANTHROPIC_API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id mcpbr/anthropic-key --query SecretString --output text)

# 1Password CLI
export ANTHROPIC_API_KEY=$(op read "op://vault/mcpbr/api_key")

# HashiCorp Vault
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/mcpbr)
```

!!! tip "Rotate keys regularly"
    Set a reminder to rotate your API keys on a regular schedule (e.g., every 90 days). If you suspect a key has been exposed, rotate it immediately in the [Anthropic Console](https://console.anthropic.com/).

### Docker Security

mcpbr runs evaluation tasks inside Docker containers, which provides a baseline of isolation. You can harden this further.

**Resource limits to prevent runaway containers:**

```yaml
# In your config, control concurrency to bound resource usage
max_concurrent: 4          # Limit parallel containers
timeout_seconds: 600       # Hard timeout per task
max_iterations: 30         # Cap agent turns
```

**Monitor container activity:**

```bash
# Watch container resource usage in real time
docker stats --filter "name=mcpbr"

# List all mcpbr containers (including stopped)
docker ps -a --filter "name=mcpbr"
```

**Network isolation for non-API workloads:**

```yaml
# If your MCP server does not need network access, isolate it
docker_network_mode: "none"
```

!!! warning "Containers run as root by default"
    Docker containers in mcpbr run as root within the container to ensure dependency installation and test execution work correctly. This is isolated from the host via Docker's namespacing, but avoid mounting sensitive host directories as volumes.

**Volume mount security:**

```yaml
# Only mount what is necessary
volumes:
  "/path/to/cache": "/cache"  # Read-write mount for caching

# NEVER mount these:
# volumes:
#   "/etc": "/host-etc"        # Host system configuration
#   "/var/run/docker.sock": "/var/run/docker.sock"  # Docker socket
#   "~/.ssh": "/root/.ssh"     # SSH keys
```

### MCP Server Sandboxing

!!! warning "Third-party MCP servers execute arbitrary code"
    MCP servers run commands and access files within the Docker container. Only use MCP servers you trust, and review their source code before deploying in production.

**Sandboxing recommendations:**

1. **Review server source code** before first use
2. **Pin server versions** to prevent supply-chain attacks:
   ```yaml
   mcp_server:
     command: "npx"
     args: ["-y", "@modelcontextprotocol/server-filesystem@1.2.3", "{workdir}"]
   ```
3. **Limit environment variables** exposed to the server -- only pass what is required
4. **Use `setup_command`** cautiously -- it runs with full container privileges

### Output Sanitization

**Logs and results may contain sensitive data:**

- Task logs can include code snippets from repositories
- API conversations are recorded in per-instance logs
- Results JSON contains tool call traces

**Secure your outputs:**

```bash
# Restrict log directory permissions
mcpbr run -c config.yaml --log-dir logs/
chmod 700 logs/

# Redact sensitive fields before sharing results
cat results.json | jq 'del(.tasks[].mcp.conversation)' > results-safe.json
```

!!! tip "Audit before sharing"
    Before sharing results files, reports, or logs externally, review them for any API keys, internal paths, or proprietary code that may have been captured during evaluation.

### Secure CI/CD Pipeline Configuration

```yaml
# .github/workflows/benchmark.yml
name: MCP Benchmark (Secure)

on:
  pull_request:
    paths: ['mcp-server/**']

permissions:
  contents: read  # Minimal permissions

jobs:
  benchmark:
    runs-on: ubuntu-latest
    environment: benchmarks  # Use a protected environment
    steps:
      - uses: actions/checkout@v4

      - name: Install mcpbr
        run: pip install mcpbr

      - name: Run benchmark
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          mcpbr run -c config.yaml -n 10 -o results.json

      - name: Upload results (restricted retention)
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: results.json
          retention-days: 30  # Don't keep results forever
```

**CI/CD security checklist:**

- [ ] API keys stored as repository or environment secrets (never in workflow files)
- [ ] Workflow permissions set to minimum required (`contents: read`)
- [ ] Protected environments for production benchmarks
- [ ] Artifact retention policies configured
- [ ] Branch protection rules on main branch
- [ ] Audit logs enabled for secret access

---

## Performance Optimization

Beyond the basic performance tips covered earlier, this section provides advanced optimization strategies for large-scale evaluations.

### Concurrent Task Execution

The `max_concurrent` setting controls how many Docker containers run simultaneously. Tuning this requires balancing CPU, memory, network bandwidth, and API rate limits.

**Recommended settings by machine profile:**

| Machine Profile | RAM | CPU Cores | `max_concurrent` | Notes |
|----------------|-----|-----------|-------------------|-------|
| Laptop (8 GB) | 8 GB | 4 | 1-2 | Memory constrained |
| Workstation (16 GB) | 16 GB | 8 | 3-4 | Good balance |
| Power workstation (32 GB) | 32 GB | 12+ | 4-8 | Check API rate limits |
| Cloud VM (64+ GB) | 64+ GB | 16+ | 8-12 | Monitor network I/O |
| Apple Silicon (16 GB) | 16 GB | 8-10 | 2-3 | Emulation overhead |

```yaml
# Conservative (safe default)
max_concurrent: 4

# Aggressive (high-end hardware with sufficient API quota)
max_concurrent: 8
```

!!! tip "Monitor and adjust"
    Start with `max_concurrent: 4` and monitor with `docker stats`. If you see containers being OOM-killed or Docker becoming unresponsive, reduce concurrency. If CPU and memory utilization are low, increase it.

### Docker Image Caching and Pre-built Images

Docker image pulls and builds are often the largest time cost for first-time runs. Optimize this with caching strategies.

**Always use pre-built images:**

```yaml
use_prebuilt_images: true  # Default and recommended
```

**Pre-pull images before evaluation:**

```bash
# Pre-pull common base images to avoid per-task download delays
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.django__django-11099
docker pull ghcr.io/epoch-research/swe-bench.eval.x86_64.astropy__astropy-12907
```

**Docker build cache optimization:**

```bash
# Ensure Docker build cache is not pruned aggressively
docker system df  # Check disk usage

# Prune only dangling images, keep build cache
docker image prune -f  # Remove dangling only
```

!!! warning "Disk space management"
    SWE-bench pre-built images are large (1-3 GB each). A full evaluation may require 50+ GB of Docker image storage. Monitor disk usage with `docker system df` and clean up between runs with `mcpbr cleanup`.

### Dataset Caching

mcpbr supports result caching to avoid re-running identical evaluations. This is especially valuable during iterative development.

```yaml
# Enable caching
cache_enabled: true
cache_dir: "/path/to/cache"  # Default: ~/.cache/mcpbr
```

**When caching helps most:**

- Re-running after a configuration change that only affects one side (MCP or baseline)
- Iterating on MCP server changes with the same task set
- Resuming after a partial failure

**Persistent volume caching for MCP servers:**

If your MCP server performs expensive pre-computation (like codebase indexing), use the `setup_command` and `volumes` features:

```yaml
mcp_server:
  command: "npx"
  args: ["-y", "@supermodeltools/mcp-server", "{workdir}"]
  setup_command: "npx -y @supermodeltools/mcp-server --index {workdir}"
  setup_timeout_ms: 900000  # 15 minutes for indexing

# Mount a persistent volume for caching across tasks
volumes:
  "/tmp/mcpbr-cache": "/cache"
```

### Memory Management for Large Benchmarks

Full dataset evaluations (300+ tasks) can strain system memory. Use these strategies to stay within bounds.

```yaml
# Reduce concurrency to lower peak memory
max_concurrent: 2

# Use the graceful degradation system to handle failures
continue_on_error: true
max_failures: 10  # Stop if too many tasks fail (likely a systemic issue)

# Enable checkpointing for crash recovery
checkpoint_interval: 1  # Save state after every task
```

**System-level memory monitoring:**

```bash
# Monitor Docker memory usage
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Set Docker Desktop memory limit (macOS/Windows)
# Docker Desktop > Settings > Resources > Memory: 8-12 GB
```

!!! example "Memory budget rule of thumb"
    Each concurrent container uses approximately 1-3 GB of RAM. For a machine with 16 GB total, allocate 8-12 GB to Docker and set `max_concurrent` to 3-4.

### Network Optimization for Remote Evaluations

**Reduce network latency:**

- Use a cloud VM in the same region as the Anthropic API endpoint
- Pre-pull Docker images before starting evaluations
- Use `setup_command` to front-load network-intensive operations

**Azure infrastructure mode for large runs:**

```yaml
infrastructure:
  mode: azure
  azure:
    resource_group: "mcpbr-eval"
    location: "eastus"  # Close to Anthropic API
    cpu_cores: 8
    memory_gb: 32
    disk_gb: 250
    auto_shutdown: true
```

---

## CI/CD Integration

This section provides production-ready CI/CD configurations for automated benchmarking.

### GitHub Actions Example Workflow

**Complete workflow with caching, regression detection, and notifications:**

```yaml
name: MCP Server Benchmark

on:
  pull_request:
    paths: ['mcp-server/**', 'config.yaml']
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday at 6 AM UTC

concurrency:
  group: benchmark-${{ github.ref }}
  cancel-in-progress: true

jobs:
  benchmark:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install mcpbr
        run: pip install mcpbr

      - name: Cache Docker images
        uses: actions/cache@v4
        with:
          path: /tmp/docker-cache
          key: docker-${{ runner.os }}-${{ hashFiles('config.yaml') }}
          restore-keys: docker-${{ runner.os }}-

      - name: Load cached Docker images
        run: |
          if [ -d /tmp/docker-cache ]; then
            for img in /tmp/docker-cache/*.tar; do
              docker load -i "$img" 2>/dev/null || true
            done
          fi

      - name: Download baseline results
        uses: actions/download-artifact@v4
        with:
          name: baseline-results
          path: .
        continue-on-error: true  # OK if no baseline exists yet

      - name: Run benchmark
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          ARGS="-c config.yaml -n 10 -o results.json --output-junit junit.xml"
          if [ -f baseline.json ]; then
            ARGS="$ARGS --baseline-results baseline.json --regression-threshold 0.1"
          fi
          mcpbr run $ARGS

      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: junit.xml

      - name: Upload results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: benchmark-results
          path: |
            results.json
            junit.xml
          retention-days: 90

      - name: Update baseline (main branch only)
        if: github.ref == 'refs/heads/main' && success()
        run: cp results.json baseline.json

      - name: Upload baseline
        if: github.ref == 'refs/heads/main' && success()
        uses: actions/upload-artifact@v4
        with:
          name: baseline-results
          path: baseline.json
          retention-days: 365
```

### GitLab CI Example

```yaml
stages:
  - benchmark
  - report

mcpbr-benchmark:
  stage: benchmark
  image: python:3.11
  services:
    - docker:24.0-dind
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
  before_script:
    - pip install mcpbr
  script:
    - mcpbr run -c config.yaml -n 10 -o results.json --output-junit junit.xml
  artifacts:
    reports:
      junit: junit.xml
    paths:
      - results.json
    expire_in: 90 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - mcp-server/**
        - config.yaml

benchmark-report:
  stage: report
  image: python:3.11
  needs: ["mcpbr-benchmark"]
  script:
    - pip install mcpbr
    - |
      python3 -c "
      import json
      with open('results.json') as f:
          r = json.load(f)
      summary = r.get('summary', {})
      mcp = summary.get('mcp', {})
      print(f'MCP Resolution Rate: {mcp.get(\"rate\", 0):.1%}')
      print(f'Tasks Resolved: {mcp.get(\"resolved\", 0)}/{mcp.get(\"total\", 0)}')
      "
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### Running in CI with Cost Budgets

!!! warning "CI benchmarks incur API costs on every run"
    Without cost controls, a misconfigured CI pipeline can quickly accumulate significant API charges. Always set explicit limits.

**Cost control configuration for CI:**

```yaml
# ci-config.yaml -- optimized for CI cost control
model: "sonnet"
sample_size: 10              # Small sample for PRs
max_concurrent: 2            # Don't overload CI runners
timeout_seconds: 300         # 5-minute hard limit per task
max_iterations: 15           # Cap agent turns
budget: 25.00                # Hard budget cap in USD
use_prebuilt_images: true
continue_on_error: true
max_failures: 3              # Stop early on systemic issues
```

**Conditional execution to avoid unnecessary runs:**

```yaml
# Only run benchmarks when MCP server code changes
on:
  pull_request:
    paths:
      - 'mcp-server/**'
      - 'config.yaml'
      - 'benchmarks/**'
```

**Environment-based sample sizing:**

```yaml
# In your workflow
- name: Set sample size
  run: |
    if [ "${{ github.event_name }}" = "schedule" ]; then
      echo "SAMPLE_SIZE=50" >> $GITHUB_ENV   # Weekly: larger sample
    elif [ "${{ github.ref }}" = "refs/heads/main" ]; then
      echo "SAMPLE_SIZE=25" >> $GITHUB_ENV   # Main: medium sample
    else
      echo "SAMPLE_SIZE=10" >> $GITHUB_ENV   # PRs: small sample
    fi

- name: Run benchmark
  run: mcpbr run -c config.yaml -n $SAMPLE_SIZE -o results.json
```

### Regression Detection in CI Pipelines

Use regression detection to automatically fail builds when MCP server performance degrades.

```bash
# Run with regression detection
mcpbr run -c config.yaml -n 25 \
  --baseline-results baseline.json \
  --regression-threshold 0.1 \
  -o current.json
```

The `--regression-threshold 0.1` flag means the pipeline will fail (exit code 1) if the MCP resolution rate drops by more than 10 percentage points compared to the baseline.

**Recommended thresholds:**

| Context | Threshold | Rationale |
|---------|-----------|-----------|
| PR checks | 0.15 | Tolerant -- small samples have high variance |
| Main branch | 0.10 | Moderate -- catch meaningful regressions |
| Release gate | 0.05 | Strict -- protect production quality |

### Caching Strategies in CI

**Cache Docker images between runs:**

```yaml
- name: Cache Docker images
  uses: actions/cache@v4
  with:
    path: /tmp/docker-cache
    key: docker-${{ hashFiles('config.yaml') }}-${{ github.sha }}
    restore-keys: |
      docker-${{ hashFiles('config.yaml') }}-
      docker-
```

**Cache mcpbr results:**

```yaml
- name: Cache evaluation results
  uses: actions/cache@v4
  with:
    path: ~/.cache/mcpbr
    key: mcpbr-cache-${{ hashFiles('config.yaml') }}
```

**Cache pip dependencies:**

```yaml
- name: Cache pip
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ hashFiles('**/requirements*.txt') }}
```

---

## Troubleshooting Guide

This section provides a quick-reference table for common errors and detailed debugging techniques.

### Common Errors and Solutions

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| `Cannot connect to Docker daemon` | Docker not running | Start Docker Desktop or run `sudo systemctl start docker` |
| `ANTHROPIC_API_KEY not set` | Missing environment variable | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `Timeout after 300 seconds` | Task too complex or slow hardware | Increase `timeout_seconds: 600` and reduce `max_concurrent` |
| `OOM killed` / container exits 137 | Insufficient memory | Reduce `max_concurrent`, increase Docker memory allocation |
| `Connection refused` / `ECONNREFUSED` | Network issue or MCP server crash | Check server logs, verify `docker network ls`, restart Docker |
| `MCP server add failed (exit 1)` | Server command not found or misconfigured | Test server standalone: `npx -y @your/server /tmp/test` |
| `Patch does not apply` | Agent changes conflict with test patches | Agent behavior issue -- increase `max_iterations` or adjust prompt |
| `Rate limit exceeded` | Too many concurrent API calls | Reduce `max_concurrent: 2` and check Anthropic Console quota |
| `No space left on device` | Docker images filling disk | Run `mcpbr cleanup -f` and `docker system prune` |
| `Pre-built image not found` | Image not available for this task | Normal -- mcpbr falls back to building from scratch |
| `Config file not found` | Wrong path to YAML | Verify path: `ls -la config.yaml` |
| `Invalid model` | Unsupported model name | Run `mcpbr models` for valid options |
| `MCP server registration timed out` | Server startup taking too long | Increase `startup_timeout_ms` in MCP server config |
| `Tool execution timed out` | MCP tool call exceeding limit | Increase `tool_timeout_ms` in MCP server config |

### Debugging Techniques

**Verbose mode levels:**

```bash
# Standard output (progress bars, summary)
mcpbr run -c config.yaml

# Verbose: task progress and summary details
mcpbr run -c config.yaml -v

# Very verbose: detailed tool calls and agent interactions
mcpbr run -c config.yaml -vv
```

**Structured JSON logging:**

```bash
# Enable structured logs for machine parsing
MCPBR_LOG_LEVEL=DEBUG mcpbr run -c config.yaml -n 1 --log-dir debug/
```

!!! example "Log analysis workflow"
    ```bash
    # 1. Run a single task with maximum debugging
    mcpbr run -c config.yaml -n 1 -vv --log-dir debug/

    # 2. List generated log files
    ls debug/

    # 3. Extract system events (errors, warnings)
    cat debug/*.json | jq '.events[] | select(.type == "system")'

    # 4. Extract tool usage sequence
    cat debug/*.json | jq '.events[] | select(.type == "assistant") |
      .message.content[] | select(.type == "tool_use") | .name'

    # 5. Check for MCP-specific tool calls
    cat debug/*.json | jq '.events[] | select(.type == "assistant") |
      .message.content[] | select(.type == "tool_use") |
      select(.name | startswith("mcp__"))'
    ```

**Profiling evaluations:**

```yaml
# Enable comprehensive performance profiling
enable_profiling: true
```

This records tool latency, memory usage, and overhead metrics for each task, helping identify bottlenecks.

**Checking MCP server health:**

```bash
# View MCP server logs for a specific instance
cat ~/.mcpbr_state/logs/*_mcp.log

# Follow logs in real time during evaluation
tail -f ~/.mcpbr_state/logs/*.log

# Test server independently
npx -y @modelcontextprotocol/server-filesystem /tmp/test
```

**Checkpoint recovery after crashes:**

If mcpbr crashes mid-evaluation, use checkpoint files to understand what completed:

```bash
# Check for checkpoint files
ls .mcpbr_run_*/checkpoint.json

# View checkpoint state
cat .mcpbr_run_*/checkpoint.json | jq '{
  completed: (.completed | length),
  failed: (.failed | length),
  skipped: (.skipped | length)
}'

# Resume from checkpoint
mcpbr run -c config.yaml --resume-from-checkpoint .mcpbr_run_20260201/checkpoint.json
```

### Getting Help (Troubleshooting)

!!! tip "Before opening an issue"
    Run through this checklist to gather the information needed for a quick resolution:

    1. **Verify prerequisites**: `docker info`, `which claude`, `echo $ANTHROPIC_API_KEY | head -c 10`
    2. **Reproduce with minimal config**: Single task, verbose output
    3. **Collect version info**: `mcpbr --version`, `python --version`, `docker --version`
    4. **Gather logs**: Run with `--log-dir debug/` and include relevant excerpts
    5. **Redact secrets**: Remove API keys, internal paths, proprietary code from logs before sharing

**Where to go:**

- [GitHub Issues](https://github.com/greynewell/mcpbr/issues) -- Bug reports and feature requests
- [GitHub Discussions](https://github.com/greynewell/mcpbr/discussions) -- Questions and community help
- [Documentation](https://mcpbr.org/) -- Full reference guides

---

## Cost Management

This section provides detailed strategies for understanding, estimating, and controlling evaluation costs.

### Budget Configuration and Monitoring

mcpbr supports a hard budget cap that halts evaluation when the estimated spend reaches the limit:

```yaml
# Set a hard budget cap (in USD)
budget: 50.00
```

When the budget is reached, mcpbr will:

1. Complete the currently running tasks
2. Skip remaining tasks
3. Save partial results to the output file
4. Report the budget limit in the summary

!!! tip "Combine budget with sample size for double protection"
    ```yaml
    budget: 25.00        # Hard cost cap
    sample_size: 25      # Task count cap
    max_iterations: 15   # Per-task turn cap
    timeout_seconds: 300 # Per-task time cap
    ```

### Model Cost Comparison Table

Use this table to estimate costs and select the right model for your evaluation stage. Prices are per million tokens (MTok) as of January 2026.

| Model | Provider | Input $/MTok | Output $/MTok | Best For |
|-------|----------|-------------|--------------|----------|
| Claude Haiku 4.5 | Anthropic | $1.00 | $5.00 | Development, iteration, smoke tests |
| Claude Sonnet 4.5 | Anthropic | $3.00 | $15.00 | Production evaluation (recommended) |
| Claude Opus 4.5 | Anthropic | $5.00 | $25.00 | Maximum performance benchmarks |
| GPT-4o | OpenAI | $2.50 | $10.00 | Cross-provider comparison |
| GPT-4o Mini | OpenAI | $0.15 | $0.60 | Ultra-low-cost exploration |
| Gemini 2.0 Flash | Google | $0.10 | $0.40 | Cheapest option for prototyping |
| Gemini 1.5 Pro | Google | $1.25 | $5.00 | Long-context evaluations |
| Qwen Plus | Alibaba | $0.40 | $1.20 | Budget evaluations |
| Qwen Max | Alibaba | $1.20 | $6.00 | Best Qwen performance |

!!! tip "Cost estimation formula"
    ```
    Estimated cost = sample_size x avg_tokens_per_task x (input_rate + output_rate)
    ```
    For Sonnet with typical SWE-bench tasks (~15K input + ~10K output tokens per task):
    ```
    25 tasks x (15K x $3/MTok + 10K x $15/MTok) = 25 x ($0.045 + $0.15) = ~$4.88
    ```
    Actual costs vary based on task complexity and iteration count.

### Cost-Effective Evaluation Strategies

**The incremental evaluation ladder:**

| Phase | Model | Sample | MCP Only? | Est. Cost | Purpose |
|-------|-------|--------|-----------|-----------|---------|
| 1. Smoke test | haiku | 1 | Yes (`-M`) | < $0.10 | Verify setup |
| 2. Quick validation | haiku | 5 | Yes (`-M`) | < $1.00 | Check tool usage |
| 3. Small comparison | sonnet | 10 | No | $5-10 | Compare MCP vs baseline |
| 4. Medium evaluation | sonnet | 25 | No | $10-30 | Statistical significance |
| 5. Full benchmark | sonnet | 50+ | No | $50-150 | Production results |

**Skip baseline during development:**

```bash
# Only run MCP agent while iterating on server config
mcpbr run -c config.yaml -n 5 -M  # Saves ~50% cost
```

**Use Haiku for iteration, Sonnet for final results:**

```yaml
# dev-config.yaml
model: "haiku"
sample_size: 5
max_iterations: 5
```

```yaml
# prod-config.yaml
model: "sonnet"
sample_size: 50
max_iterations: 30
```

### Estimating Costs Before Running

**Quick cost estimate script:**

```python
from mcpbr.pricing import calculate_cost, format_cost

# Estimate for a typical SWE-bench task with Sonnet
# Average: ~15K input tokens, ~10K output tokens per task
tasks = 25
avg_input = 15_000
avg_output = 10_000

# Both MCP and baseline run, so double the task count
total_runs = tasks * 2

per_task_cost = calculate_cost("sonnet", avg_input, avg_output)
total_est = per_task_cost * total_runs if per_task_cost else 0

print(f"Estimated cost per task: {format_cost(per_task_cost)}")
print(f"Estimated total ({tasks} tasks, MCP + baseline): {format_cost(total_est)}")
```

**After a run, calculate actual costs:**

```python
import json
from mcpbr.pricing import calculate_cost, format_cost

with open("results.json") as f:
    results = json.load(f)

total_cost = 0
model = results.get("config", {}).get("model", "sonnet")

for task in results.get("tasks", []):
    for run_type in ["mcp", "baseline"]:
        run = task.get(run_type, {})
        tokens = run.get("tokens", {})
        cost = calculate_cost(
            model,
            tokens.get("input", 0),
            tokens.get("output", 0),
        )
        if cost:
            total_cost += cost

print(f"Total actual cost: {format_cost(total_cost)}")
print(f"Cost per task: {format_cost(total_cost / len(results.get('tasks', [1])))}")
```

---

## Analytics Best Practices

Getting meaningful insights from mcpbr evaluations requires careful experimental design and statistical awareness.

### When to Use the Analytics Database

mcpbr saves results in structured JSON and YAML formats. For teams running frequent evaluations, consider importing results into a database for trend analysis:

- **Single evaluation**: JSON output is sufficient (`-o results.json`)
- **Comparing 2-3 configs**: Side-by-side JSON comparison works well
- **Ongoing regression tracking**: Import results into a database (SQLite, PostgreSQL) for trend queries
- **Team dashboards**: Use YAML/JSON outputs with visualization tools (Grafana, Jupyter)

```bash
# Export multiple formats for different consumers
mcpbr run -c config.yaml -n 25 \
  -o results.json \
  -y results.yaml \
  -r report.md \
  --output-junit junit.xml
```

### Meaningful Comparisons

!!! danger "Comparing results from different task samples is invalid"
    mcpbr randomly samples tasks unless you specify them explicitly. Two runs with `-n 25` may evaluate completely different tasks, making comparison meaningless.

**How to ensure valid comparisons:**

1. **Same tasks**: Use `--task` flags to specify identical task sets:
   ```bash
   mcpbr run -c config-a.yaml -t django__django-11099 -t astropy__astropy-12907 -o a.json
   mcpbr run -c config-b.yaml -t django__django-11099 -t astropy__astropy-12907 -o b.json
   ```

2. **Same benchmark**: Never compare SWE-bench results with CyberGym results

3. **Same model**: Model capability differences will dominate MCP server differences

4. **Same parameters**: Use identical `timeout_seconds`, `max_iterations`, and other settings

**Comparison script:**

```python
import json

def compare(file_a: str, file_b: str) -> None:
    with open(file_a) as f:
        a = json.load(f)
    with open(file_b) as f:
        b = json.load(f)

    a_rate = a["summary"]["mcp"]["rate"]
    b_rate = b["summary"]["mcp"]["rate"]
    a_resolved = set(
        t["instance_id"] for t in a["tasks"]
        if t.get("mcp", {}).get("resolved", False)
    )
    b_resolved = set(
        t["instance_id"] for t in b["tasks"]
        if t.get("mcp", {}).get("resolved", False)
    )

    print(f"Config A: {a_rate:.1%} ({len(a_resolved)} resolved)")
    print(f"Config B: {b_rate:.1%} ({len(b_resolved)} resolved)")
    print(f"Only A solved: {a_resolved - b_resolved}")
    print(f"Only B solved: {b_resolved - a_resolved}")
    print(f"Both solved: {a_resolved & b_resolved}")

compare("results-a.json", "results-b.json")
```

### Interpreting Statistical Significance

Small sample sizes produce noisy results. Before drawing conclusions, consider the variance in your measurements.

**Sample size guidelines:**

| Sample Size | Confidence | Use Case |
|------------|------------|----------|
| 1-5 | Very low | Smoke testing only |
| 10-25 | Low-moderate | Directional signal |
| 25-50 | Moderate | Reasonable confidence for large effects |
| 50-100 | Good | Detect moderate improvements (10%+) |
| 100+ | High | Detect small improvements (5%+) |

!!! warning "A single run with n=10 is not statistically meaningful"
    If Config A resolves 3/10 (30%) and Config B resolves 4/10 (40%), the difference could easily be due to chance. You need larger samples or repeated runs to draw reliable conclusions.

**Practical significance check:**

```python
# Simple binomial confidence interval
import math

def confidence_interval(resolved: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for resolution rate."""
    if total == 0:
        return (0.0, 0.0)
    p = resolved / total
    margin = z * math.sqrt(p * (1 - p) / total)
    return (max(0, p - margin), min(1, p + margin))

# Example: 8 out of 25 resolved
low, high = confidence_interval(8, 25)
print(f"Rate: {8/25:.1%}, 95% CI: [{low:.1%}, {high:.1%}]")
# Rate: 32.0%, 95% CI: [14.7%, 49.3%]
```

If the confidence intervals of two configurations overlap substantially, the difference is likely not statistically significant.

### Regression Detection Thresholds

Choose regression thresholds based on your sample size and tolerance for false alarms:

| Scenario | Threshold | False Alarm Rate | Miss Rate |
|----------|-----------|------------------|-----------|
| PR checks (n=10) | 0.20 | Low | High (misses small regressions) |
| Main branch (n=25) | 0.10 | Moderate | Moderate |
| Release gate (n=50) | 0.05 | Higher | Low (catches most regressions) |

```yaml
# Conservative: only alert on large regressions
--regression-threshold 0.15

# Strict: alert on any meaningful drop
--regression-threshold 0.05
```

!!! tip "Use rolling baselines"
    Update your baseline results periodically (e.g., weekly on the main branch) so that regression detection compares against recent performance rather than a stale snapshot.

### Building Leaderboards

For teams evaluating multiple MCP servers, build a leaderboard from saved results:

```python
import json
import glob

results = []
for path in glob.glob("results-*.json"):
    with open(path) as f:
        data = json.load(f)
    config_name = path.replace("results-", "").replace(".json", "")
    mcp_summary = data.get("summary", {}).get("mcp", {})
    results.append({
        "config": config_name,
        "rate": mcp_summary.get("rate", 0),
        "resolved": mcp_summary.get("resolved", 0),
        "total": mcp_summary.get("total", 0),
    })

# Sort by resolution rate
results.sort(key=lambda x: x["rate"], reverse=True)

print(f"{'Rank':<6}{'Config':<25}{'Rate':<10}{'Resolved':<10}")
print("-" * 51)
for i, r in enumerate(results, 1):
    print(f"{i:<6}{r['config']:<25}{r['rate']:.1%}{'':<4}{r['resolved']}/{r['total']}")
```

**Leaderboard best practices:**

- Always report sample size alongside resolution rate
- Use the same task set across all configurations
- Record the model, parameters, and date for reproducibility
- Track cost-per-resolved-task alongside raw performance
- Re-run periodically as MCP servers and models are updated

---

## Additional Resources

- [Configuration Guide](configuration.md) - Detailed configuration reference
- [Troubleshooting](troubleshooting.md) - Common issues and solutions
- [CLI Reference](cli.md) - All command options
- [Benchmarks Guide](benchmarks/index.md) - Benchmark details
- [Evaluation Results](evaluation-results.md) - Understanding output
- [Templates](templates.md) - Configuration templates
- [MCP Integration](mcp-integration.md) - MCP server testing

## Getting Help

**Before Asking for Help:**
1. Check [troubleshooting guide](troubleshooting.md)
2. Run with `-vv --log-dir debug/`
3. Test MCP server standalone
4. Verify prerequisites

**When Reporting Issues:**
- Include mcpbr version (`mcpbr --version`)
- Include Python version
- Include Docker version
- Include config file (redact secrets!)
- Include relevant logs
- Describe expected vs actual behavior

**Community:**
- [GitHub Issues](https://github.com/greynewell/mcpbr/issues) - Bug reports
- [GitHub Discussions](https://github.com/greynewell/mcpbr/discussions) - Questions
- [Documentation](https://mcpbr.org/) - Comprehensive guides
