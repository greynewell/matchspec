---
description: "GSM8K evaluates mathematical reasoning on 1,319 grade-school math word problems, testing chain-of-thought reasoning and numeric answer extraction with tolerance-based comparison."
benchmark_howto:
  name: "GSM8K"
  description: "Evaluate MCP server-assisted mathematical reasoning on grade-school math word problems from OpenAI's GSM8K dataset."
  benchmark_id: "gsm8k"
faq:
  - q: "What is GSM8K and what does it test?"
    a: "GSM8K (Grade School Math 8K) is a dataset of 8,500 linguistically diverse grade-school math word problems created by OpenAI. The test split contains 1,319 problems requiring 2-8 steps of arithmetic and basic reasoning. mcpbr uses it to evaluate mathematical reasoning and chain-of-thought capabilities."
  - q: "How does mcpbr extract and compare numeric answers?"
    a: "mcpbr supports multiple answer formats: GSM8K format (#### 42), LaTeX boxed (\\boxed{42}), sentence format ('The answer is 42'), dollar amounts ($1,234.56), and numbers with commas (1,234). Answers are compared with both relative tolerance (0.1%) and absolute tolerance (0.001)."
  - q: "Can the agent use Python for calculations in GSM8K?"
    a: "Yes. The Docker environment includes Python 3 with numpy, scipy, and sympy pre-installed. The agent can write and execute Python scripts for complex arithmetic, which is encouraged for multi-step calculations."
  - q: "How does GSM8K compare to the MATH benchmark?"
    a: "GSM8K tests grade-school level math (arithmetic, basic algebra, word problems). The MATH benchmark tests competition-level mathematics (AMC, AIME). GSM8K has 1,319 problems and most models score 70-95%. MATH has 12,500 problems at much higher difficulty with typical scores of 30-70%."
  - q: "Why might a correct answer be marked wrong?"
    a: "Common causes: format mismatch (agent says '18 dollars' but ground truth is '18'), unit confusion, or the agent not clearly stating the final answer. Using 'The answer is: [number]' format in the prompt helps ensure reliable extraction."
---

# GSM8K

## Overview

| Property | Value |
|----------|-------|
| **Benchmark ID** | `gsm8k` |
| **Dataset** | [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k) |
| **Tasks** | 1,319 test problems |
| **Evaluation** | Numeric answer extraction with tolerance (rtol=0.001, atol=0.001) |
| **Output Type** | Numeric answer |
| **Timeout** | 60-180s recommended |
| **Pre-built Images** | No |
| **Difficulty Levels** | None (uniform -- all grade-school level) |

!!! tip "Quick Start"
    ```bash
    mcpbr run -c config.yaml --benchmark gsm8k -n 20
    ```

## Overview

[GSM8K (Grade School Math 8K)](https://github.com/openai/grade-school-math) is a dataset of 8,500 linguistically diverse grade-school math word problems created by OpenAI. The test split used by mcpbr contains 1,319 problems that each require 2 to 8 steps of mathematical reasoning to solve. Problems involve arithmetic, basic algebra, and real-world reasoning about quantities such as money, time, distances, and rates.

GSM8K is one of the most widely used benchmarks for evaluating chain-of-thought reasoning in language models. Rather than testing code generation, it tests whether the model can break down word problems into logical steps and arrive at the correct numeric answer.

In mcpbr, GSM8K evaluates how effectively an MCP server assists the language model in mathematical reasoning tasks. The environment provides Python with math libraries (numpy, scipy, sympy) so the agent can optionally use computation tools for verification.

## What It Measures

GSM8K evaluates core mathematical reasoning capabilities:

- **Chain-of-thought reasoning**: Breaking a multi-step word problem into sequential logical operations
- **Arithmetic accuracy**: Performing addition, subtraction, multiplication, and division correctly across multiple steps
- **Word problem comprehension**: Extracting the relevant quantities, relationships, and constraints from natural language
- **Unit awareness**: Correctly handling quantities involving money, time, distance, rates, and percentages
- **Multi-step planning**: Determining the correct sequence of operations to reach the final answer (2-8 steps per problem)
- **Error propagation management**: Maintaining accuracy across multiple computation steps

GSM8K does **not** test:

- Advanced mathematics (calculus, linear algebra, abstract algebra)
- Competition-level problem solving (see MATH benchmark)
- Formal proof construction
- Symbolic computation
- Multi-modal reasoning (no diagrams or figures)

## Task Structure

Each GSM8K task contains the following fields:

| Field | Description |
|-------|-------------|
| **question** | A natural language math word problem |
| **answer** | Chain-of-thought solution ending with the numeric answer in `#### N` format |

**Example task:**

```text
Question: Janet's ducks lay 16 eggs per day. She eats three for breakfast
every morning and bakes muffins for her friends every day with four. She sells
every duck egg at the farmers' market daily for $2. How much in dollars does
she make every day at the farmers' market?

Answer: Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 duck eggs a day.
She makes 9 * 2 = <<9*2=18>>$18 every day at the farmer's market.
#### 18
```

Instance IDs are generated in the format `gsm8k_{index}` where the index corresponds to the position in the test split (e.g., `gsm8k_0`, `gsm8k_1`).

### Problem Characteristics

GSM8K problems share common characteristics:

- **2-8 reasoning steps**: Each problem requires multiple arithmetic operations
- **Real-world contexts**: Money, time, distance, rates, quantities, and everyday scenarios
- **Integer and decimal answers**: Most answers are integers, but some involve decimals (dollar amounts, rates)
- **No external knowledge required**: All information needed is contained in the problem statement
- **No diagrams or figures**: Pure text-based problems

## Configuration

### Basic Configuration

=== "CLI"

    ```bash
    # Run GSM8K with default settings
    mcpbr run -c config.yaml --benchmark gsm8k

    # Run a small sample for quick testing
    mcpbr run -c config.yaml --benchmark gsm8k -n 20

    # Run specific tasks by index
    mcpbr run -c config.yaml --benchmark gsm8k -t 0 -t 1 -t 2

    # Run with verbose output and save results
    mcpbr run -c config.yaml --benchmark gsm8k -n 50 -v -o results.json

    # Save both JSON results and Markdown report
    mcpbr run -c config.yaml --benchmark gsm8k -n 100 -o results.json -r report.md
    ```

=== "YAML Configuration"

    ```yaml
    benchmark: "gsm8k"
    sample_size: 10
    timeout_seconds: 180
    max_iterations: 15

    mcp_server:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

    model: "sonnet"
    ```

### Advanced Options

GSM8K does not support difficulty or category filtering since all 1,319 problems are at the same grade-school level. You can select specific tasks by index:

```bash
# Run specific tasks for targeted testing
mcpbr run -c config.yaml --benchmark gsm8k -t 0 -t 100 -t 500 -t 1000
```

Configuration with custom chain-of-thought prompt:

```yaml
benchmark: "gsm8k"
sample_size: 50
timeout_seconds: 180
max_iterations: 15

mcp_server:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"]

model: "sonnet"

# Custom prompt encouraging chain-of-thought
agent_prompt: |
  Solve this math problem step-by-step:

  {problem_statement}

  Show your work clearly. Use Python if needed for calculations.
  End with: "The answer is: [number]"
```

Configuration for high-throughput evaluation:

```yaml
benchmark: "gsm8k"
sample_size: 1319       # All test problems
timeout_seconds: 120
max_iterations: 10
max_concurrent: 8        # Lightweight environments support high concurrency

model: "sonnet"
```

## Evaluation Methodology

GSM8K evaluation focuses on extracting and comparing numeric answers rather than executing code:

1. **Ground truth extraction**: The expected numeric answer is extracted from the task's `answer` field, which uses the GSM8K `#### N` format.

2. **Agent answer extraction**: The evaluator attempts to extract a numeric answer from the agent's response using multiple pattern-matching strategies, tried in this order:

    | Priority | Pattern | Example |
    |----------|---------|---------|
    | 1 | GSM8K format: `#### N` | `#### 42` |
    | 2 | LaTeX boxed: `\boxed{N}` | `\boxed{42}` |
    | 3 | Sentence format | `The answer is 42` or `Final answer: 42` |
    | 4 | Dollar amounts | `$1,234.56` |
    | 5 | Last number in text (fallback) | Any numeric value |

    Numbers with commas (e.g., `1,234`), dollar signs, and percentage symbols are automatically cleaned during parsing.

3. **Comparison**: The extracted numeric values are compared using both relative and absolute tolerance:
    - **Relative tolerance (rtol)**: 0.001 (0.1%) -- handles large numbers where small absolute differences are acceptable
    - **Absolute tolerance (atol)**: 0.001 -- handles small numbers and rounding differences
    - A match is declared if the absolute difference is within `atol` OR the relative difference is within `rtol`

4. **Verdict**: The task is marked as **resolved** if the agent's extracted answer matches the ground truth within tolerance.

## Interpreting Results

### Key Metrics

| Metric | Description |
|--------|-------------|
| **Resolve rate** | Percentage of problems where the agent's answer matched the ground truth |
| **Extraction failure rate** | Percentage of problems where no numeric answer could be extracted from the agent's response |
| **Ground truth parse failures** | Percentage of problems where the ground truth answer could not be parsed (should be 0%) |

### What Good Results Look Like

| Score Range | Assessment |
|-------------|------------|
| **90-100%** | Excellent -- state-of-the-art mathematical reasoning with effective tool assistance |
| **80-90%** | Good -- strong reasoning with occasional arithmetic or multi-step errors |
| **70-80%** | Adequate -- basic math reasoning works but struggles with longer chains |
| **60-70%** | Below expected -- check prompt, answer format, or model capability |
| **Below 60%** | Needs investigation -- likely configuration issues, answer extraction problems, or model limitations |

!!! note "Context: Industry Benchmarks"
    Most modern language models achieve 70-95% on GSM8K. Top models (GPT-4, Claude, etc.) score 90%+ without MCP assistance. An effective MCP server integration should maintain these scores. Significant drops suggest the MCP server interaction is interfering with the model's reasoning rather than helping.

### Common Failure Patterns

| Pattern | Cause | Solution |
|---------|-------|----------|
| Correct reasoning, wrong final number | Arithmetic error in one step that propagates | Encourage the agent to use Python for calculations |
| No answer extracted | Agent provides reasoning but no clear final answer | Add explicit format instruction: "End with: The answer is: [number]" |
| Answer is close but not within tolerance | Rounding differences or unit mismatch | Check if agent answers in different units (cents vs. dollars) |
| Agent produces code instead of answer | Agent writes a script but does not state the result | Instruct agent to always state the final numeric answer explicitly |
| Last-number fallback extracts wrong value | Agent mentions numbers in reasoning that are not the final answer | Use a structured answer format like `#### N` to avoid ambiguity |

## Example Output

**Successful resolution:**

```json
{
  "resolved": true,
  "agent_answer": 18.0,
  "ground_truth_answer": 18.0,
  "answer_match": true
}
```

**Failed resolution (wrong answer):**

```json
{
  "resolved": false,
  "agent_answer": 16.0,
  "ground_truth_answer": 18.0,
  "answer_match": false
}
```

**Failed resolution (no answer extracted):**

```json
{
  "resolved": false,
  "error": "Could not extract numeric answer from agent's solution",
  "agent_solution": "Janet has 16 eggs. She eats 3 and bakes 4. She sells the rest at $2 each..."
}
```

**Failed resolution (ground truth parse error):**

```json
{
  "resolved": false,
  "error": "Could not parse ground truth answer: [malformed answer string]"
}
```

## Best Practices

### Recommended Workflow

1. **Start with 10-20 problems** to verify answer extraction works correctly with your model and prompt
2. **Check the first results** to confirm the agent clearly states its final numeric answer
3. **Adjust the prompt** if extraction failures are common -- add explicit format instructions
4. **Scale to full benchmark** (1,319 problems) once configuration is validated
5. **Pair with MATH** for a complete picture of mathematical reasoning capability

### Performance Tips

- **Enable chain-of-thought** in the agent prompt for better reasoning. GSM8K was specifically designed to benefit from step-by-step reasoning.
- **Use Python for calculations** -- the environment includes numpy, scipy, and sympy. Encourage the agent to use Python for multi-step arithmetic to reduce calculation errors.
- **Low resource usage** -- GSM8K tasks require minimal Docker environments, so you can run higher concurrency (`max_concurrent: 8` or more).
- **Quick evaluation** -- problems typically solve in under 3 minutes. Set `timeout_seconds: 180` for comfortable margins.
- **Monitor token usage** -- chain-of-thought reasoning increases input/output tokens. Consider using `thinking_budget` in your YAML configuration for extended thinking mode if your model supports it.

### Cost Optimization

- **GSM8K is cost-efficient**: Problems are short (1-3 sentences) and answers are brief numeric values
- **Chain-of-thought increases tokens**: The reasoning steps add to output token count, but the overall cost per problem remains low
- **1,319 tasks is manageable**: Running the full test split is practical and recommended for reliable benchmarking
- **Use `sonnet` for routine evaluation**: GSM8K problems are well within the capability of mid-tier models; reserve `opus` for investigating specific failures
- **High concurrency reduces wall-clock time**: With `max_concurrent: 8`, the full benchmark can complete in under an hour
- **No expensive setup**: Environment creation is fast -- no repository cloning or heavy dependency installation

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Agent does not provide a clear numeric answer | Extensive reasoning without a stated final answer | Add format instruction: "End with: The answer is: [number]" or "#### [number]" |
| Answer is correct but marked as wrong | Unit mismatch (e.g., "18 dollars" vs "18") or unusual formatting | The evaluator strips dollar signs and commas, but unusual formatting may cause issues |
| Environment setup is slow | Python 3 + numpy/scipy/sympy installation takes 1-2 minutes per container | Increase `timeout_seconds` to account for setup time; use high concurrency to amortize |
| Agent produces code instead of answer | Agent writes Python scripts without stating the result | Instruct agent to print or state the final numeric answer explicitly |
| Extraction picks wrong number | Agent mentions intermediate values that get picked up by the last-number fallback | Use structured answer format (`#### N` or `The answer is: N`) to avoid ambiguity |

## Comparison with Similar Benchmarks

| Aspect | GSM8K | MATH | BigBench-Hard | HumanEval |
|--------|-------|------|---------------|-----------|
| **Goal** | Solve math word problems | Solve competition math | Diverse reasoning tasks | Generate Python code |
| **Subject** | Grade-school arithmetic | AMC/AIME competition math | 27 reasoning subtasks | Programming |
| **Task Count** | 1,319 | 12,500 | 27 subtasks | 164 |
| **Difficulty** | Grade-school (uniform) | High school-competition | Hard (selected) | Moderate (uniform) |
| **Answer Type** | Numeric | Numeric (LaTeX) | Varies by subtask | Function code |
| **Evaluation** | Numeric tolerance | LaTeX extraction + match | Exact match | Unit tests |
| **Chain-of-Thought** | Essential | Essential | Beneficial | Not applicable |
| **Pre-built Images** | No | No | No | No |
| **Typical Runtime** | 1-3 min/task | 2-5 min/task | 1-3 min/task | 1-2 min/task |
| **Expected Scores** | 70-95% | 30-70% | Varies | 85-95% |
| **Best For** | Basic math reasoning baseline | Advanced math evaluation | Broad reasoning assessment | Code generation baseline |

!!! tip "When to Use GSM8K"
    Use GSM8K when you need a **quick, reliable measure of mathematical reasoning capability**. It is the standard first benchmark for evaluating chain-of-thought reasoning. For more challenging math evaluation, follow up with the MATH benchmark. For non-math reasoning, consider BigBench-Hard.

## References

- [GSM8K Repository](https://github.com/openai/grade-school-math)
- [GSM8K Paper (Training Verifiers to Solve Math Word Problems)](https://arxiv.org/abs/2110.14168)
- [GSM8K Dataset on HuggingFace](https://huggingface.co/datasets/openai/gsm8k)
- [MATH Benchmark](math.md) -- competition-level mathematics
- [BigBench-Hard](bigbench-hard.md) -- diverse hard reasoning tasks
- [Benchmarks Overview](index.md)
- [Configuration Reference](../configuration.md)
- [CLI Reference](../cli.md)
