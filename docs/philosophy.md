---
description: "mcpbr's testing philosophy: why MCP servers should be tested like APIs not plugins, how to design meaningful evaluations, and principles for reliable benchmarking."
faq:
  - q: "How should MCP servers be tested?"
    a: "MCP servers should be tested like APIs, not like plugins. This means measuring defined contracts (inputs, outputs, error handling), testing across diverse tasks, and using statistical methods to determine if performance improvements are real."
  - q: "What makes a good MCP server benchmark?"
    a: "A good benchmark uses real-world tasks (not toy examples), runs controlled experiments with a baseline comparison, uses isolated environments for reproducibility, and produces quantitative metrics rather than qualitative impressions."
  - q: "Why is baseline comparison important for MCP server testing?"
    a: "Without a baseline, you cannot attribute performance to the MCP server. The agent might solve the task using built-in tools alone. Only by comparing with-server vs without-server results can you measure the actual contribution of your MCP tools."
  - q: "How many benchmark tasks do I need for statistically valid results?"
    a: "At minimum 25 tasks for directional signals, 50+ for reasonable confidence in moderate effects, and 100+ for detecting small improvements. Single-digit sample sizes are useful only for smoke testing."
---

# Testing Philosophy

This page describes the principles and philosophy behind mcpbr's approach to MCP server evaluation. These ideas emerged from building mcpbr and are shared here to help the broader MCP ecosystem develop better testing practices.

For the full backstory on how these principles were discovered, read **[Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)**.

## The Core Principle: Test Like APIs, Not Like Plugins

The most important insight behind mcpbr is this:

> **MCP servers should be tested like APIs, not like plugins.**

This distinction matters more than it might seem at first glance.

### What Plugin Testing Looks Like

Plugin testing asks simple questions:

- Does it load without crashing?
- Does it expose the expected functions?
- Does it return data in the expected format?

This is necessary but nowhere near sufficient for MCP servers.

### What API Testing Looks Like

API testing asks harder, more important questions:

- **Does it fulfill its contract?** --- Given valid input, does it return correct output?
- **How does it handle failures?** --- What happens when the input is malformed, the resource doesn't exist, or the operation times out?
- **What is its performance profile?** --- Latency, throughput, resource consumption?
- **Does it degrade gracefully?** --- Under load, under unusual conditions, at scale?

### Why MCP Servers Need API-Level Testing

MCP servers operate in a fundamentally different context than traditional plugins. They are consumed by **non-deterministic AI agents** that respond unpredictably to tool behavior:

| Scenario | Plugin Consumer (deterministic code) | MCP Consumer (AI agent) |
|----------|--------------------------------------|------------------------|
| Tool returns an error | Code handles the error predictably | Agent may retry, switch strategies, hallucinate a result, or give up entirely |
| Tool is slow | Code waits or times out predictably | Agent may abandon the tool, call it repeatedly, or waste tokens on alternative approaches |
| Tool returns partial data | Code processes what it gets | Agent may misinterpret partial results as complete, leading to incorrect solutions |
| Tool is unavailable | Code falls back to alternative | Agent may not discover the tool at all, negating the server's entire value |

Because agents respond non-deterministically, testing MCP servers requires **statistical evaluation across many tasks**, not just functional verification.

## Principles of Meaningful Evaluation

### 1. Always Compare Against a Baseline

The most common mistake in MCP server evaluation is measuring only the server-assisted agent. Without a baseline, you have no way to attribute performance to the server itself.

```
Good:  MCP agent solves 32% → Baseline solves 20% → Server adds +60% improvement
Bad:   MCP agent solves 32% → Is that good? Who knows?
```

mcpbr runs both evaluations automatically: the same model, same tasks, same environment, same parameters. The only variable is the presence of your MCP server. This is the foundation of a controlled experiment.

### 2. Use Real Tasks, Not Toy Examples

Demonstrations with carefully chosen examples are misleading. A server that excels at reading a single file may fail when navigating a complex repository with hundreds of files and nested dependencies.

mcpbr uses established benchmarks with real-world tasks:

- **SWE-bench** --- actual GitHub issues from major open-source projects (Django, Astropy, Scikit-learn)
- **CyberGym** --- real security vulnerabilities requiring exploit generation
- **MCPToolBench++** --- diverse tool-use scenarios across 45+ categories
- **HumanEval, MBPP** --- algorithmic code generation problems
- **GSM8K, MATH** --- mathematical reasoning tasks

These tasks were not designed with any particular MCP server in mind. They are unbiased, diverse, and representative of real work.

### 3. Reproducibility Is Non-Negotiable

If an evaluation cannot be reproduced, its results are meaningless. mcpbr enforces reproducibility through:

- **Docker containers** --- identical environment for every task run, with pre-built images containing pinned dependencies
- **Version-locked benchmarks** --- tasks pulled from specific dataset versions on HuggingFace
- **Deterministic configuration** --- YAML configs that fully specify the evaluation parameters
- **Seed control** --- optional global random seeds for reproducible task sampling

When you share mcpbr results, anyone can re-run the exact same evaluation and verify your numbers.

### 4. Measure Multiple Dimensions

Resolution rate alone does not tell the full story. A comprehensive evaluation should measure:

| Dimension | What It Tells You | How mcpbr Measures It |
|-----------|-------------------|-----------------------|
| **Resolution rate** | Does the server help solve more tasks? | Pass/fail on benchmark test suites |
| **Tool adoption** | Does the agent actually use your tools? | `tool_usage` statistics in results JSON |
| **Token efficiency** | Does the server reduce overall cost? | Input/output token counts per task |
| **Latency profile** | Does the server slow things down? | Profiling data (with `--profile` flag) |
| **Failure modes** | When things go wrong, how do they fail? | Per-instance logs and error analysis |
| **Regression stability** | Is performance consistent over time? | Regression detection against baseline results |

A server that improves resolution rate by 20% but doubles token usage might not be a net positive for production workloads.

### 5. Statistical Rigor Over Anecdotes

Small sample sizes produce noisy results. A single evaluation with 5 tasks might show Server A beating Server B by 20%, but running the same comparison with 50 tasks could reverse the result.

**Guidelines for sample sizes:**

| Sample Size | Confidence Level | Appropriate Use |
|------------|-----------------|-----------------|
| 1-5 tasks | Very low | Smoke testing and setup verification only |
| 10-25 tasks | Low to moderate | Directional signal, catching large effects |
| 25-50 tasks | Moderate | Reasonable confidence for effects > 10% |
| 50-100 tasks | Good | Detect moderate improvements (5-10%) |
| 100+ tasks | High | Detect small but meaningful improvements |

When in doubt, run more tasks. The cost of a larger sample is always less than the cost of a wrong conclusion.

### 6. Control Your Variables

A valid comparison requires controlling every variable except the one you are testing:

- **Same model** --- model capability differences will dominate MCP server differences
- **Same tasks** --- use `--task` flags to ensure identical task sets between runs
- **Same parameters** --- `timeout_seconds`, `max_iterations`, `max_concurrent` must match
- **Same benchmark** --- never compare SWE-bench results with CyberGym results
- **Same environment** --- use the same machine or infrastructure mode

mcpbr's comparison mode handles this automatically by running both configurations against the same tasks in the same evaluation.

## Common Evaluation Pitfalls

### The Demo Trap

**Problem:** Showing a polished demo where the MCP server helps solve a specific task.

**Why it fails:** The task was chosen because it works. You have no idea if the server helps on the other 299 tasks in the benchmark.

**Solution:** Run a statistically meaningful sample with random task selection.

### The Missing Baseline

**Problem:** Reporting that your MCP server achieved a 35% resolution rate on SWE-bench.

**Why it fails:** Without knowing the baseline rate, 35% could be worse than the agent without your server. Claude with built-in tools might achieve 38% on its own.

**Solution:** Always run both MCP and baseline evaluations. mcpbr does this by default.

### The Apples-to-Oranges Comparison

**Problem:** Comparing your MCP server results against published benchmarks from other papers.

**Why it fails:** Different models, different task samples, different timeouts, different evaluation methods. The numbers are not comparable.

**Solution:** Generate your own baseline on the exact same setup. Use mcpbr's comparison mode.

### The Overfitting Trap

**Problem:** Tuning your MCP server configuration until it performs well on a specific set of 10 tasks.

**Why it fails:** The server may be overfitting to those specific tasks. Performance on new tasks may be worse.

**Solution:** Use a held-out test set. Develop on one set of tasks, evaluate on a completely different set.

### The Single-Run Conclusion

**Problem:** Running one evaluation and drawing permanent conclusions.

**Why it fails:** Both agents are non-deterministic. A single run captures one sample from a distribution of possible outcomes.

**Solution:** Run multiple evaluations and look at the distribution of results. If the improvement is consistent across runs, it is more likely real.

## Designing Your Evaluation Strategy

### For MCP Server Developers

If you are building an MCP server and want to prove it works:

1. **Start with smoke tests** (n=1-5) to verify basic functionality
2. **Scale to validation** (n=10-25) to check if tools are being adopted
3. **Run a proper evaluation** (n=50+) to measure improvement with confidence
4. **Track regressions** by saving results and using `--baseline-results` in CI

See the [Best Practices Guide](best-practices.md) for a complete iterative workflow.

### For MCP Server Evaluators

If you are evaluating MCP servers for adoption:

1. **Define your criteria** --- resolution rate, cost, latency, tool coverage
2. **Select a representative benchmark** --- match the benchmark to your use case
3. **Run controlled comparisons** --- same tasks, same model, same parameters
4. **Use comparison mode** for direct head-to-head evaluation
5. **Report confidence intervals**, not just point estimates

### For Researchers

If you are publishing research involving MCP server evaluation:

1. **Document your full configuration** --- share the YAML config file
2. **Report sample sizes and confidence intervals**
3. **Use established benchmarks** rather than custom task sets when possible
4. **Make results reproducible** --- pin dataset versions, model versions, and mcpbr version
5. **Run multiple trials** and report variance

## Further Reading

- **[Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)** --- the origin story and initial insights
- **[Architecture](architecture.md)** --- how mcpbr implements these principles
- **[Best Practices](best-practices.md)** --- practical application of these ideas
- **[Benchmarks Guide](benchmarks/index.md)** --- choosing the right benchmark for your evaluation
- **[Evaluation Results](evaluation-results.md)** --- interpreting what the numbers mean

---

Built by [Grey Newell](https://greynewell.com) | [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)
