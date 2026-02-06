---
description: "GAIA evaluates general AI assistant capabilities including multi-step reasoning, web browsing, tool use, and multi-modality on real-world questions with unambiguous answers."
benchmark_howto:
  name: "GAIA"
  description: "Tests real-world AI assistant capabilities with questions requiring reasoning, multi-modality, web browsing, and tool use across three difficulty levels."
  benchmark_id: "gaia"
faq:
  - q: "What makes GAIA different from other benchmarks?"
    a: "GAIA tests real-world assistant capabilities that require combining multiple skills: reasoning, multi-modality, web browsing, and tool use. Unlike academic benchmarks, GAIA questions are designed to be easy for humans but hard for AI, with unambiguous, fact-based answers."
  - q: "How are GAIA difficulty levels structured?"
    a: "Level 1 questions require basic reasoning or a single tool. Level 2 questions need multi-step reasoning or combining multiple tools. Level 3 questions demand complex planning, multi-hop reasoning, and sophisticated tool orchestration."
  - q: "How does GAIA evaluation work?"
    a: "GAIA uses exact match evaluation. The model's answer is normalized (lowercased, stripped) and compared against the ground truth. The answer matches if the normalized ground truth equals or is a substring of the normalized response."
  - q: "Why are GAIA scores typically low?"
    a: "GAIA is intentionally designed to be challenging for AI. Questions often require combining web search, computation, file processing, and multi-step reasoning. Even state-of-the-art systems score below 75% on Level 1. Low absolute scores are expected."
  - q: "What tools does the agent need for GAIA?"
    a: "GAIA tasks benefit from web browsing, file access, calculator/code execution, and search tools. An MCP server providing these capabilities will significantly improve scores compared to a model with no tool access."
---

# GAIA

## Overview

| Property | Value |
|----------|-------|
| **Benchmark ID** | `gaia` |
| **Dataset** | [gaia-benchmark/GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA) |
| **Tasks** | ~460 validation questions |
| **Evaluation** | Exact match on final answer (case-insensitive, substring matching) |
| **Output Type** | Free-form text answer |
| **Timeout** | 180-600s recommended |
| **Pre-built Images** | No |
| **Difficulty Levels** | 1, 2, 3 (increasing complexity) |

!!! tip "Quick Start"
    ```bash
    mcpbr run -c config.yaml --benchmark gaia -n 10
    ```

## Overview

GAIA (General AI Assistants) is a benchmark designed to evaluate AI systems on real-world questions that require fundamental assistant capabilities. Unlike many academic benchmarks that test narrow skills, GAIA questions are intentionally designed to be:

- **Easy for humans**: A human with access to standard tools (web browser, calculator, etc.) can answer most questions in minutes
- **Hard for AI**: Questions require combining multiple capabilities that current AI systems struggle to integrate

GAIA covers a broad range of tasks including:

- **Factual reasoning**: Questions that require multi-step logical deduction
- **Multi-modality**: Tasks involving images, audio, or documents
- **Web browsing**: Questions requiring information retrieval from the internet
- **Tool use**: Tasks that need calculator, code execution, or API access
- **File handling**: Questions that involve processing attached files

Each question has an unambiguous, fact-based answer that can be verified without subjective judgment.

## What It Measures

GAIA evaluates the fundamental capabilities of a general AI assistant:

- **Information retrieval**: Finding specific facts from the web, databases, or attached files
- **Multi-step reasoning**: Chaining multiple logical steps to arrive at a conclusion
- **Tool orchestration**: Selecting and combining the right tools (web search, calculator, code execution) for each sub-task
- **Multi-modal understanding**: Processing and reasoning about images, PDFs, spreadsheets, and other file formats
- **Precise answer generation**: Producing concise, factually correct answers in the expected format
- **Planning and decomposition**: Breaking complex questions into manageable sub-problems

GAIA does **not** test:

- Creative writing or open-ended generation
- Code generation or software engineering
- Long-form document synthesis
- Conversational ability or personality

### Difficulty Levels

GAIA organizes questions into three difficulty levels:

| Level | Description | Typical Skills Required | Expected Score Range |
|-------|-------------|------------------------|---------------------|
| **Level 1** | Simple questions | Single tool use, basic reasoning, direct factual lookup | 40-75% |
| **Level 2** | Moderate questions | Multi-step reasoning, combining 2-3 tools, information synthesis | 20-50% |
| **Level 3** | Complex questions | Multi-hop reasoning, complex planning, sophisticated tool orchestration | 5-25% |

## Task Structure

Each GAIA task contains the following fields:

| Field | Description |
|-------|-------------|
| **Question** | The question to answer (may reference attached files) |
| **Level** | Difficulty level (1, 2, or 3) |
| **Final answer** | The ground truth answer for evaluation |
| **task_id** | Unique identifier for the task |
| **Annotator Metadata** | Additional context from human annotators (steps required, tools needed) |

The agent receives the question with its difficulty level and must provide a concise, factual answer.

### Example Task (Level 1)

```text
Difficulty Level: 1

Question: What is the population of the capital city of the country where
the 2024 Summer Olympics were held? Give your answer to the nearest million.

Expected Answer: 2 million
```

### Example Task (Level 3)

```text
Difficulty Level: 3

Question: Download the CSV file at [URL]. Calculate the median value in the
'revenue' column for entries where the 'region' field is 'North America',
then convert this value to EUR using the exchange rate on January 15, 2024.
Round to the nearest hundred.

Expected Answer: 45200
```

## Configuration

### Basic Configuration

=== "CLI"

    ```bash
    # Run GAIA with default settings
    mcpbr run -c config.yaml --benchmark gaia

    # Run a small sample
    mcpbr run -c config.yaml --benchmark gaia -n 10

    # Filter by difficulty level using the level parameter
    mcpbr run -c config.yaml --benchmark gaia --level 1

    # Filter by difficulty using filter-difficulty
    mcpbr run -c config.yaml --benchmark gaia --filter-difficulty 1

    # Run only Level 3 (hardest) questions
    mcpbr run -c config.yaml --benchmark gaia --filter-difficulty 3

    # Run with extended timeout for complex tasks
    mcpbr run -c config.yaml --benchmark gaia -n 10 -v -o results.json
    ```

=== "YAML"

    ```yaml
    benchmark: "gaia"
    sample_size: 10
    timeout_seconds: 300

    mcp_server:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

    model: "sonnet"

    # Optional: filter by difficulty level
    filter_difficulty:
      - "1"
      - "2"
    ```

### Advanced Options

#### Level Filtering

GAIA supports two methods for filtering by difficulty:

1. **`--level` flag**: Directly sets the difficulty level (1, 2, or 3). This is applied first during task loading.

2. **`--filter-difficulty` flag**: Accepts difficulty level strings. Applied after level filtering, providing additional refinement.

Both methods are case-sensitive on the numeric value. Valid values are `1`, `2`, and `3`.

#### Configuration for Level-Specific Evaluation

```yaml
# Level 1 only -- fast baseline
benchmark: "gaia"
sample_size: 20
timeout_seconds: 180
filter_difficulty:
  - "1"

model: "sonnet"
```

```yaml
# Level 3 only -- hardest tasks, extended timeout
benchmark: "gaia"
sample_size: 10
timeout_seconds: 600
max_iterations: 30
filter_difficulty:
  - "3"

model: "opus"
```

#### Configuration with Rich Tool Access

```yaml
# GAIA with web search and filesystem tools
benchmark: "gaia"
sample_size: 15
timeout_seconds: 300

mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

# Additional MCP servers for broader tool coverage
# (configure based on your available servers)

model: "sonnet"

agent_prompt: |
  {problem_statement}

  Provide your final answer as concisely as possible. Match the expected format exactly.
  If the answer is a number, provide just the number. If it is a name, provide just the name.
```

## Evaluation Methodology

GAIA uses exact match evaluation with normalization:

1. **Answer normalization**: Both the ground truth and the model's response are stripped of leading/trailing whitespace and lowercased.

2. **Exact match check**: The normalized ground truth is compared to the normalized response. A match occurs if:
   - The ground truth exactly equals the response, OR
   - The ground truth is a substring of the response

3. **Result determination**: The task is resolved if and only if the normalized ground truth matches or is contained within the normalized response.

### Scoring Details

```
resolved = (gt_normalized == solution_normalized) OR (gt_normalized in solution_normalized)
```

Where:
- `gt_normalized`: Ground truth answer, stripped and lowercased
- `solution_normalized`: Model's response, stripped and lowercased

### Answer Format

GAIA expects concise, factual answers. The substring matching allows for some flexibility:

- `"Paris"` matches ground truth `"paris"` (exact match after normalization)
- `"The answer is 42"` matches ground truth `"42"` (substring match)
- `"Based on my research, the population is approximately 2 million"` matches ground truth `"2 million"` (substring match)

However, overly verbose responses risk matching unintended substrings. Keep answers concise.

## Interpreting Results

### Key Metrics

| Metric | Description |
|--------|-------------|
| **Overall resolve rate** | Percentage of all questions answered correctly |
| **Per-level resolve rate** | Accuracy broken down by difficulty level (1, 2, 3) |
| **Level progression** | How steeply accuracy drops from Level 1 to Level 3 |

### What Good Results Look Like

| Level | Score Range | Assessment |
|-------|-------------|------------|
| **Level 1** | 50-75%+ | Good -- agent handles simple factual lookups and single-tool tasks |
| **Level 1** | 30-50% | Adequate -- basic capability present but tool integration needs work |
| **Level 2** | 30-50% | Good -- effective multi-step reasoning and tool combination |
| **Level 2** | 15-30% | Adequate -- struggles with some multi-step tasks |
| **Level 3** | 15-25%+ | Excellent -- sophisticated planning and tool orchestration |
| **Level 3** | 5-15% | Expected -- Level 3 is extremely challenging for current systems |

!!! note "Context: Human vs. AI Performance"
    The GAIA paper reports human accuracy above 90% across all levels using standard tools (web browser, calculator). The large gap between human and AI performance is by design -- GAIA measures the integration capabilities that humans take for granted but AI systems find difficult.

### Common Failure Patterns

| Pattern | Cause | Solution |
|---------|-------|----------|
| Correct reasoning, wrong format | Answer is "42.0" but ground truth is "42" | Instruct the model to provide concise, precise answers matching expected format |
| Near-miss on factual questions | Model retrieves outdated or slightly wrong information | Ensure web browsing tools are available and working |
| Verbose answer with wrong substring | Long response contains unintended substring match | Instruct the model to keep final answers brief |
| Timeout on Level 3 | Multi-step reasoning exceeds time limit | Increase `timeout_seconds` to 600 for Level 3 tasks |
| Cannot access referenced files | Task references external URLs or attached files | Ensure MCP server provides file access and web browsing capabilities |

## Example Output

### Successful Evaluation

```json
{
  "resolved": true,
  "agent_answer": "The population of Paris is approximately 2 million.",
  "ground_truth": "2 million"
}
```

### Failed Evaluation (Wrong Answer)

```json
{
  "resolved": false,
  "agent_answer": "The population is about 11 million in the metropolitan area.",
  "ground_truth": "2 million"
}
```

### Failed Evaluation (No Ground Truth)

```json
{
  "resolved": false,
  "error": "No ground truth answer available"
}
```

## Best Practices

### Recommended Workflow

1. **Start with Level 1**: Begin evaluation with Level 1 questions to establish a baseline and verify configuration
2. **Evaluate each level separately**: Track accuracy per level for a nuanced view of capabilities
3. **Add tool access incrementally**: Test with minimal tools first, then add web search, computation tools to measure their impact
4. **Compare with human baseline**: Use the GAIA paper's human accuracy numbers to contextualize results

### Performance Tips

- **Use generous timeouts**: Set `timeout_seconds` to at least 300 for Level 2 and 600 for Level 3
- **Provide tool access**: GAIA is designed to test tool use. MCP servers with web browsing, file access, and computation tools produce the best results
- **Keep answers concise**: The exact-match evaluation penalizes verbose responses. Instruct the model to provide only the final answer without extensive explanation
- **Monitor the agent_answer field**: The evaluation truncates stored agent answers to 500 characters. For debugging, use verbose output to see full responses

### Cost Optimization

- **Level 1 is cheapest**: Fewer reasoning steps and tool calls required per task
- **Level 3 is most expensive**: Multi-hop reasoning, multiple tool calls, and extended thinking increase token usage significantly
- **Start with 10-20 tasks per level**: This provides a statistically meaningful sample without excessive cost
- **Use `sonnet` for Level 1-2**: Simpler tasks work well with faster, cheaper models
- **Reserve `opus` for Level 3**: Complex planning tasks benefit from the strongest reasoning capability
- **Filter by level** to avoid running expensive Level 3 tasks during initial configuration testing

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Model gives correct reasoning but wrong answer format | GAIA expects answers in a specific format | Add format instructions to prompt: "If the answer is a number, provide just the number." |
| Timeout issues on Level 3 questions | Complex multi-step tasks exceed time limit | Increase `timeout_seconds` to 600; consider `max_iterations: 30` |
| Model cannot access referenced files or URLs | MCP server lacks web/file tools | Configure MCP server with web browsing and file access capabilities |
| Low scores on Level 1 questions | Basic tool integration issues | Verify web browsing tools work, timeout is at least 180s, and prompt requests concise answers |
| Score inconsistency between runs | GAIA tasks may depend on external web content that changes | Re-run failed tasks individually; some tasks may be inherently brittle due to web dependencies |

## Comparison with Similar Benchmarks

| Aspect | GAIA | MCPToolBench++ | AgentBench | ToolBench |
|--------|------|----------------|------------|-----------|
| **Goal** | Answer real-world questions | Use MCP tools correctly | Complete agent tasks | Use API tools |
| **Skills Tested** | Reasoning + tools + multi-modal | Tool selection + invocation | Multi-environment interaction | API tool use |
| **Answer Type** | Free-form factual answer | Structured tool calls | Task-specific output | Tool call sequences |
| **Evaluation** | Exact match (substring) | Accuracy thresholds | String matching | Tool call comparison |
| **Difficulty Levels** | 3 (1-3) | 2 (single/multi) | Varies by environment | Varies |
| **Tool Requirements** | Web, file, calculation | MCP tool schemas | Environment-specific | API access |
| **Typical Timeout** | 180-600s | 180-300s | 120-300s | 120-300s |
| **Best For** | General assistant capability | MCP-specific tool use | Broad agent evaluation | API tool selection |

!!! tip "When to Use GAIA"
    Use GAIA when you want to evaluate an MCP server's effectiveness as a **general-purpose assistant**. GAIA tests the combination of reasoning, tool use, and information retrieval that defines a practical AI assistant. For MCP-specific tool use metrics, use MCPToolBench++. For code-focused evaluation, use SWE-bench or HumanEval.

## References

- [GAIA Paper (arXiv)](https://arxiv.org/abs/2311.12983)
- [GAIA Dataset on HuggingFace](https://huggingface.co/datasets/gaia-benchmark/GAIA)
- [GAIA Leaderboard](https://huggingface.co/spaces/gaia-benchmark/leaderboard)
- [MCPToolBench++](mcptoolbench.md) -- MCP-specific tool use benchmark
- [AgentBench](agentbench.md) -- multi-environment agent benchmark
- [ToolBench](toolbench.md) -- real-world API tool use benchmark
- [Benchmarks Overview](index.md)
- [Configuration Reference](../configuration.md)
- [CLI Reference](../cli.md)
