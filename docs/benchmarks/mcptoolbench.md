---
description: "MCPToolBench++ evaluates AI agents on MCP tool discovery, selection, invocation, and result interpretation across 45+ categories with accuracy-threshold-based evaluation."
benchmark_howto:
  name: "MCPToolBench++"
  description: "Evaluates AI agents' ability to effectively use MCP tools across four dimensions: discovery, selection, invocation, and result interpretation, with 45+ task categories."
  benchmark_id: "mcptoolbench"
faq:
  - q: "What does MCPToolBench++ evaluate?"
    a: "MCPToolBench++ evaluates four key MCP tool-use capabilities: tool discovery (understanding available tools), tool selection (choosing the right tool), tool invocation (calling tools with correct parameters), and result interpretation (using tool outputs correctly)."
  - q: "How is MCPToolBench++ different from ToolBench?"
    a: "MCPToolBench++ is specifically designed for MCP (Model Context Protocol) tool use, testing the full lifecycle of MCP tool interaction. ToolBench evaluates general API tool use. MCPToolBench++ uses MCP-specific tool schemas, categories, and evaluation metrics."
  - q: "What accuracy thresholds determine a passing score?"
    a: "A task is considered resolved when tool selection accuracy is 0.8 or higher (80% of correct tools selected) AND parameter accuracy is 0.7 or higher (70% of parameters correct), AND the agent does not make more than 1.5x the expected number of tool calls."
  - q: "What are single vs. multi-step tasks?"
    a: "Single-step tasks require one tool call (mapped to 'easy' difficulty). Multi-step tasks require a sequence of tool calls where later calls may depend on earlier results (mapped to 'hard' or 'medium' difficulty). Multi-step tasks are significantly more challenging."
  - q: "How should I structure the agent's output for best results?"
    a: "The evaluation extracts tool calls from the agent's response. JSON-formatted output works best: a list of objects with 'name' and 'parameters' fields. If JSON parsing fails, the evaluator falls back to text pattern matching, which is less reliable."
---

# MCPToolBench++

## Overview

| Property | Value |
|----------|-------|
| **Benchmark ID** | `mcptoolbench` |
| **Dataset** | [MCPToolBench/MCPToolBenchPP](https://huggingface.co/datasets/MCPToolBench/MCPToolBenchPP) |
| **Tasks** | Varies (45+ categories) |
| **Evaluation** | Tool selection accuracy (>=0.8), parameter accuracy (>=0.7), call count limit (<=1.5x) |
| **Output Type** | Tool call accuracy metrics |
| **Timeout** | 180-300s recommended |
| **Pre-built Images** | No |
| **Difficulty Levels** | easy (single-step), hard/medium (multi-step) |

!!! tip "Quick Start"
    ```bash
    mcpbr run -c config.yaml --benchmark mcptoolbench -n 20
    ```

## Overview

MCPToolBench++ is a benchmark specifically designed to evaluate how well AI agents use MCP (Model Context Protocol) tools. It tests the complete tool-use lifecycle across four key dimensions:

1. **Tool Discovery**: Understanding what MCP tools are available and their capabilities
2. **Tool Selection**: Choosing the appropriate tool(s) for a given task
3. **Tool Invocation**: Calling tools with correct parameters matching their schemas
4. **Result Interpretation**: Understanding and correctly using tool outputs

The benchmark covers 45+ categories spanning diverse tool-use scenarios:

- **Browser**: Web browsing and page interaction
- **Finance**: Financial data retrieval and calculations
- **Code Analysis**: Source code inspection and manipulation
- **Database**: Query and data management operations
- **File Management**: File system operations
- **Communication**: Email, messaging, and notification tools
- **Weather**: Weather data retrieval
- **Search**: Information retrieval and search operations
- And many more

Each task provides a query, a set of available MCP tools with their schemas, and a ground truth sequence of tool calls that correctly completes the task.

## What It Measures

MCPToolBench++ evaluates MCP-specific tool use capabilities:

- **Tool schema comprehension**: Understanding tool definitions, parameter types, required vs. optional fields, and return value formats
- **Tool selection accuracy**: Identifying the correct tool(s) from a set of available options based on the task description
- **Parameter precision**: Providing the exact parameter names and values expected by the tool schema
- **Sequential reasoning**: For multi-step tasks, determining the correct order of tool calls and passing results between them
- **Efficiency**: Completing tasks without excessive exploratory or redundant tool calls

MCPToolBench++ does **not** test:

- The actual execution of tool calls (evaluation is based on the call structure, not results)
- Code generation or debugging
- Free-form reasoning or knowledge retrieval
- Tasks that require tools not listed in the task's available tool set

## Task Structure

Each MCPToolBench++ task contains the following fields:

| Field | Description |
|-------|-------------|
| **uuid** | Unique task identifier |
| **query** | The natural language task description |
| **category** | Task category (e.g., "browser", "finance", "code_analysis") |
| **call_type** | Task complexity -- "single" (one tool call) or "multi" (multiple sequential calls) |
| **tools** | List of available tool names |
| **mcp_tools_dict** | Full MCP tool definitions including schemas and descriptions |
| **function_call_label** | Ground truth sequence of tool calls with parameters |

The agent receives the query, task metadata, and available tools, then must select and invoke the correct tools with proper parameters.

### Example Task (Single-Step)

```text
Category: finance
Task Type: single-step tool call
Available Tools: get_stock_price, get_exchange_rate, calculate_tax

Task:
What is the current stock price of Apple Inc. (AAPL)?

Expected Tool Call:
  - name: get_stock_price
    parameters:
      symbol: "AAPL"
```

### Example Task (Multi-Step)

```text
Category: finance
Task Type: multi-step tool call
Available Tools: get_stock_price, get_exchange_rate, calculate_tax

Task:
Get the current stock price of AAPL in USD, then convert it to EUR.

Expected Tool Calls:
  1. name: get_stock_price
     parameters: { symbol: "AAPL" }
  2. name: get_exchange_rate
     parameters: { from: "USD", to: "EUR" }
```

## Configuration

### Basic Configuration

=== "CLI"

    ```bash
    # Run MCPToolBench++ with default settings
    mcpbr run -c config.yaml --benchmark mcptoolbench

    # Run a small sample
    mcpbr run -c config.yaml --benchmark mcptoolbench -n 20

    # Filter by difficulty (single vs multi-step)
    mcpbr run -c config.yaml --benchmark mcptoolbench --filter-difficulty easy
    mcpbr run -c config.yaml --benchmark mcptoolbench --filter-difficulty hard

    # Filter by category
    mcpbr run -c config.yaml --benchmark mcptoolbench --filter-category browser
    mcpbr run -c config.yaml --benchmark mcptoolbench --filter-category finance

    # Combine filters
    mcpbr run -c config.yaml --benchmark mcptoolbench \
      --filter-difficulty easy --filter-category browser

    # Run with verbose output and save results
    mcpbr run -c config.yaml --benchmark mcptoolbench -n 50 -v -o results.json
    ```

=== "YAML"

    ```yaml
    benchmark: "mcptoolbench"
    sample_size: 10
    timeout_seconds: 300

    mcp_server:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

    model: "sonnet"

    # Optional: filter by difficulty and category
    filter_difficulty:
      - "easy"    # single-step tasks
    filter_category:
      - "browser"
      - "finance"
    ```

### Advanced Options

#### Difficulty Filtering

MCPToolBench++ maps difficulty labels to the `call_type` field:

| Filter Value | Maps To | Description |
|--------------|---------|-------------|
| `easy` or `single` | `single` | Single tool call tasks |
| `hard`, `multi`, or `medium` | `multi` | Multi-step tool call sequences |

#### Category Filtering

Filter by any of the 45+ task categories. Category matching is case-insensitive. Common categories include:

| Category | Description |
|----------|-------------|
| `browser` | Web browsing tasks |
| `finance` | Financial operations |
| `code_analysis` | Code inspection and analysis |
| `database` | Database operations |
| `file` | File management |
| `weather` | Weather data |
| `search` | Information retrieval |
| `communication` | Messaging and notification |

#### Configuration for Multi-Step Evaluation

```yaml
benchmark: "mcptoolbench"
sample_size: 20
timeout_seconds: 300
max_iterations: 20

filter_difficulty:
  - "hard"     # Multi-step tasks only

model: "sonnet"

agent_prompt: |
  {problem_statement}

  Output your tool calls as a JSON array. Each element should have:
  - "name": the tool name
  - "parameters": an object with parameter key-value pairs

  Example:
  [{"name": "tool_name", "parameters": {"param1": "value1"}}]
```

#### Configuration for Category-Specific Testing

```yaml
benchmark: "mcptoolbench"
sample_size: 30
timeout_seconds: 180

filter_category:
  - "finance"
  - "search"
  - "weather"

model: "sonnet"
```

## Evaluation Methodology

MCPToolBench++ evaluation compares the agent's tool calls against the ground truth using three metrics:

### 1. Tool Selection Accuracy

Measures how many of the expected tools the agent correctly selected:

```
tool_selection_accuracy = correct_tools / total_expected_tools
```

A tool is considered correctly selected if the agent made at least one call to a tool with the same name as an expected tool. Each expected tool is counted at most once.

### 2. Parameter Accuracy

Measures how correctly the agent filled in tool parameters:

```
parameter_accuracy = correct_parameters / total_expected_parameters
```

For each correctly selected tool, the agent's parameters are compared against the ground truth. A parameter is correct if both the name and value match exactly.

### 3. Sequence Match

A boolean indicating whether the agent called the exact same tools in the exact same order as the ground truth.

### Overall Resolution

A task is **resolved** when all three conditions are met:

```
resolved = (tool_selection_accuracy >= 0.8)
       AND (parameter_accuracy >= 0.7)
       AND (agent_call_count <= expected_call_count * 1.5)
```

The thresholds allow for minor variations:

- **0.8 tool selection**: Allows missing up to 20% of expected tools (e.g., 4 out of 5 correct)
- **0.7 parameter accuracy**: Allows up to 30% parameter errors (e.g., minor formatting differences)
- **1.5x call limit**: Allows some extra exploratory tool calls but prevents excessive flailing

### Tool Call Extraction

The evaluation attempts to extract tool calls from the agent's response in two ways:

1. **JSON parsing**: If the response is valid JSON (a list of tool calls or an object with a `tool_calls` key), the calls are extracted directly.
2. **Text parsing**: If JSON parsing fails, the evaluation falls back to pattern matching in the response text.

## Interpreting Results

### Key Metrics

| Metric | Description |
|--------|-------------|
| **Resolve rate** | Percentage of tasks meeting all three thresholds |
| **Tool selection accuracy (avg)** | Average percentage of correct tools selected across tasks |
| **Parameter accuracy (avg)** | Average percentage of correct parameters across tasks |
| **Sequence match rate** | Percentage of tasks with exact tool call order match |
| **Per-category accuracy** | Resolve rate broken down by task category |
| **Per-difficulty accuracy** | Resolve rate for single-step vs. multi-step tasks |

### What Good Results Look Like

| Task Type | Score Range | Assessment |
|-----------|-------------|------------|
| **Single-step (easy)** | 70-90%+ | Good -- agent reliably selects and invokes individual tools |
| **Single-step (easy)** | 50-70% | Adequate -- basic tool use works but parameter accuracy needs improvement |
| **Multi-step (hard)** | 50-70%+ | Good -- agent handles sequential tool orchestration |
| **Multi-step (hard)** | 30-50% | Adequate -- struggles with tool sequencing or result passing |
| **Multi-step (hard)** | Below 30% | Needs investigation -- check structured output format and tool schema access |

!!! note "Metric Independence"
    A high tool selection accuracy with low parameter accuracy indicates the agent understands which tools to use but struggles with exact parameter formatting. Conversely, low tool selection with high parameter accuracy (for selected tools) suggests the agent is good at invocation but poor at choosing the right tool. Track these metrics independently for targeted improvement.

### Common Failure Patterns

| Pattern | Cause | Solution |
|---------|-------|----------|
| No tool calls extracted | Agent describes actions in natural language instead of structured output | Configure prompt to request JSON-formatted tool calls |
| High tool selection, low parameter accuracy | Parameter name mismatches (e.g., "stock_symbol" vs "symbol") | Review MCP tool schemas; ensure agent has access to full tool definitions |
| Excessive tool calls | Agent retries with different parameters or explores alternatives | Instruct agent to be deliberate; the 1.5x limit prevents excessive flailing |
| Wrong tool order in multi-step | Agent calls tools in incorrect sequence | Provide clear instructions about sequential dependencies |
| Category-specific failures | Agent lacks domain knowledge for certain categories | Filter to categories relevant to your MCP server; investigate per-category metrics |

## Example Output

### Successful Evaluation

```json
{
  "resolved": true,
  "tool_selection_accuracy": 1.0,
  "parameter_accuracy": 0.85,
  "sequence_match": true,
  "details": "Tool selection: 100.0%, Parameter accuracy: 85.0%, Sequence match: True"
}
```

### Failed Evaluation (Low Tool Selection)

```json
{
  "resolved": false,
  "tool_selection_accuracy": 0.5,
  "parameter_accuracy": 0.9,
  "sequence_match": false,
  "details": "Tool selection: 50.0%, Parameter accuracy: 90.0%, Sequence match: False"
}
```

### Failed Evaluation (No Tool Calls Extracted)

```json
{
  "resolved": false,
  "tool_selection_accuracy": 0.0,
  "parameter_accuracy": 0.0,
  "sequence_match": false,
  "details": "Agent made no tool calls"
}
```

### Failed Evaluation (No Ground Truth)

```json
{
  "resolved": false,
  "error": "No ground truth function calls provided for evaluation"
}
```

## Best Practices

### Recommended Workflow

1. **Start with single-step tasks** (`--filter-difficulty easy`) to establish baseline tool selection and invocation capability
2. **Test category-by-category** to identify which tool types your MCP server handles well
3. **Progress to multi-step tasks** once single-step accuracy exceeds 70%
4. **Track all three metrics** (tool selection, parameter accuracy, sequence match) separately for targeted optimization
5. **Test with your actual MCP server** -- MCPToolBench++ is most valuable when evaluating your real tool configuration

### Performance Tips

- **Use structured output prompts**: MCPToolBench++ evaluation depends on extracting tool calls from the agent's response. JSON-formatted output is most reliable.
- **Provide tool schemas**: Ensure your agent has access to the full MCP tool definitions. The `mcp_tools_dict` field in each task contains the complete schemas.
- **Increase timeout for multi-step tasks**: Multi-step tasks require sequential tool calls and result interpretation. Use at least 300 seconds.
- **Monitor all three metrics**: Track tool selection accuracy, parameter accuracy, and sequence match separately. Each reveals different aspects of tool-use capability.

### Cost Optimization

- **MCPToolBench++ is moderately priced**: Tasks are shorter than code generation benchmarks but involve tool schema processing
- **Single-step tasks are cheapest**: One tool call per task means fewer tokens and faster completion
- **Use `sonnet` for all difficulty levels**: Tool use tasks depend more on structured output capability than deep reasoning
- **Filter by category** for focused evaluation rather than running all 45+ categories
- **Start with 20 tasks per category** for statistically meaningful results without excessive cost
- **JSON output prompts reduce cost**: Structured prompts lead to more concise, parseable responses

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Agent does not produce structured tool calls | Agent describes tool calls in natural language | Configure prompt to request JSON output with `name` and `parameters` fields |
| Tool selection is high but parameter accuracy is low | Parameter name mismatches or incorrect value types | Review MCP tool schemas to ensure parameter names and types match exactly |
| Extra tool calls cause resolution failure | Agent exceeds 1.5x expected call count | Instruct agent to be deliberate; avoid exploratory calls |
| Category filter returns no results | Category name does not match dataset | Inspect available categories (see category listing below) |
| Low sequence match despite high individual metrics | Correct tools called in wrong order | For multi-step tasks, instruct agent to consider dependencies between calls |

To inspect available categories:

```bash
uv run python -c "
from datasets import load_dataset
ds = load_dataset('MCPToolBench/MCPToolBenchPP', split='train')
cats = sorted(set(item['category'] for item in ds))
for cat in cats:
    print(cat)
"
```

## Comparison with Similar Benchmarks

| Aspect | MCPToolBench++ | ToolBench | GAIA | AgentBench | WebArena |
|--------|----------------|-----------|------|------------|----------|
| **Goal** | MCP tool use | API tool use | General assistant | Multi-environment agent | Web browsing tasks |
| **Tool Type** | MCP tool schemas | REST API endpoints | Any available tools | Environment-specific | Browser actions |
| **Evaluation** | Accuracy thresholds | Tool call comparison | Exact match (answer) | String matching | Reference matching |
| **Metrics** | Selection + params + sequence | Tool call match | Answer correctness | Task completion | Action accuracy |
| **Task Types** | Single + multi-step | Single + multi-step | Varied (QA) | Varied (multi-env) | Web interaction |
| **Categories** | 45+ | Varies | 3 levels | Multiple environments | Web domains |
| **MCP-Specific** | Yes | No | No | No | No |
| **Typical Timeout** | 180-300s | 120-300s | 180-600s | 120-300s | 120-300s |
| **Best For** | MCP server evaluation | General API tool testing | Overall assistant quality | Broad agent capability | Web automation |

!!! tip "When to Use MCPToolBench++"
    Use MCPToolBench++ when you need to evaluate an MCP server's **tool use pipeline** specifically. It is the only benchmark designed around the MCP tool lifecycle (discovery, selection, invocation, interpretation). For general assistant capability, use GAIA. For code-focused evaluation, use SWE-bench or HumanEval. For real-world API testing, use ToolBench.

## References

- [MCPToolBench++ Dataset on HuggingFace](https://huggingface.co/datasets/MCPToolBench/MCPToolBenchPP)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [ToolBench](toolbench.md) -- general API tool use benchmark
- [GAIA](gaia.md) -- general AI assistant benchmark with tool use
- [AgentBench](agentbench.md) -- multi-environment agent benchmark
- [Benchmarks Overview](index.md)
- [MCP Integration Guide](../mcp-integration.md)
- [Configuration Reference](../configuration.md)
- [CLI Reference](../cli.md)
