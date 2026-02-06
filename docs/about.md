---
description: "About mcpbr: the story behind the open-source MCP server benchmark runner, why it was built, who maintains it, and where the project is headed."
faq:
  - q: "Who created mcpbr?"
    a: "mcpbr was created by Grey Newell, a software engineer who identified a critical gap in how MCP servers were being evaluated. Read the full origin story at https://greynewell.com/blog/why-i-built-mcpbr/"
  - q: "Why was mcpbr created?"
    a: "Existing coding benchmarks measured language model capabilities but not whether MCP servers actually improved agent performance. mcpbr was built to fill that gap with controlled, reproducible experiments."
  - q: "Is mcpbr open source?"
    a: "Yes, mcpbr is fully open-source under the MIT license. It is available on GitHub at https://github.com/greynewell/mcpbr and published to PyPI, npm, Homebrew, and Conda."
  - q: "How can I contribute to mcpbr?"
    a: "mcpbr welcomes contributions of all kinds. Check out the contributing guide, good first issues, and the project roadmap on GitHub."
---

# About mcpbr

mcpbr (Model Context Protocol Benchmark Runner) is an open-source framework for evaluating whether MCP servers actually improve AI agent performance. It provides controlled, reproducible benchmarking across 30+ benchmarks so developers can stop guessing and start measuring.

## The Origin Story

mcpbr was created by [Grey Newell](https://greynewell.com) after identifying a critical gap in the MCP ecosystem: **no tool existed to measure whether an MCP server actually made an AI agent better at its job.**

Existing coding benchmarks like SWE-bench measured raw language model capabilities. MCP server developers relied on anecdotal evidence and demo videos. There was no way to answer the fundamental question: *does adding this MCP server to an agent improve its performance on real tasks?*

mcpbr was built to answer that question with hard data.

!!! quote "From the creator"
    "No available tool allowed users to easily measure the performance improvement of introducing their MCP server to an agent."

    --- [Grey Newell, "Why I Built mcpbr"](https://greynewell.com/blog/why-i-built-mcpbr/)

Read the full origin story: **[Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)**

## The Problem mcpbr Solves

Before mcpbr, MCP server evaluation looked like this:

- **Manual testing** --- run a few prompts, eyeball the results, declare it "works"
- **Demo-driven development** --- show a polished demo, hope it generalizes
- **Vibes-based benchmarking** --- "it feels faster" with no quantitative evidence

This approach fails for several reasons:

1. **LLMs are non-deterministic** --- the same prompt can produce different results each time
2. **Cherry-picked examples mislead** --- a server that shines on 3 tasks may fail on 300
3. **No baseline comparison** --- without measuring the agent *without* the MCP server, you can't attribute improvement to the server itself
4. **Environment differences** --- different machines, dependencies, and configurations make results unreproducible

mcpbr solves all of these by running **controlled experiments**: same model, same tasks, same Docker environment --- the only variable is the MCP server.

## How mcpbr Works

The core evaluation loop is straightforward:

1. **Load benchmark tasks** from datasets like SWE-bench (real GitHub issues)
2. **Create isolated Docker environments** with pre-built images containing the repository and all dependencies
3. **Run the MCP agent** --- Claude Code with your MCP server registered, working inside the container
4. **Run the baseline agent** --- the same Claude Code instance without MCP tools
5. **Evaluate both** --- apply patches, run test suites, record pass/fail
6. **Compare** --- calculate resolution rates and report the improvement (or regression)

This produces a clear, quantitative answer: your MCP server improved agent performance by X% on Y benchmark.

For a deeper technical walkthrough, see the [Architecture](architecture.md) page.

## A Key Insight: Test Like APIs, Not Plugins

One of the foundational principles behind mcpbr's design came from an important realization during development:

> **MCP servers should be tested like APIs, not like plugins.**

Plugins just need to load and not crash. APIs have defined contracts --- expected inputs, outputs, error handling, and performance characteristics. MCP servers sit squarely in API territory because:

- **Agents respond non-deterministically to failures** --- they may loop, hallucinate, or silently ignore broken tools
- **Success requires measuring multiple dimensions** --- adoption rates (does the agent use the tools?), failure rates (do the tools work reliably?), and token efficiency (does the server reduce overall cost?)
- **Edge cases matter** --- a server that works 90% of the time but fails unpredictably on the other 10% can make an agent *worse* overall

This insight drove mcpbr's design toward comprehensive, statistical evaluation rather than simple pass/fail testing. Read more about this philosophy on the [Testing Philosophy](philosophy.md) page.

Learn more: **[Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)**

## Project Vision

mcpbr aims to be the **standard for MCP server benchmarking** --- the tool that every MCP server developer reaches for when they need to prove their server works.

### Current Capabilities

- **30+ benchmarks** across software engineering, code generation, math reasoning, security, tool use, and more
- **Multi-provider support** for Anthropic, OpenAI, Google Gemini, and Alibaba Qwen
- **Multiple agent harnesses** including Claude Code, OpenAI Codex, OpenCode, and Gemini
- **Infrastructure flexibility** with local Docker and Azure VM execution
- **Regression detection** with CI/CD integration, threshold-based alerts, and multi-channel notifications
- **Side-by-side comparison** mode for A/B testing two MCP servers directly
- **Comprehensive analytics** including statistical significance testing, trend analysis, and leaderboards

### Roadmap

The project's roadmap includes:

- **Multi-agent evaluation** --- testing MCP servers across different agent architectures simultaneously
- **Adversarial testing** --- probing MCP servers with edge cases and failure scenarios
- **Kubernetes scaling** --- running large-scale evaluations across clusters
- **MCP Gym** --- a reinforcement learning environment for training agents with MCP tools

See the full [v1.0 Roadmap](https://github.com/users/greynewell/projects/2) for 200+ planned features.

## Community

mcpbr is built by a growing community of contributors. The project demonstrates how AI agents themselves can accelerate open-source development --- many contributions come from AI-assisted workflows.

### Get Involved

- **[Good First Issues](https://github.com/greynewell/mcpbr/labels/good%20first%20issue)** --- perfect for newcomers
- **[Help Wanted](https://github.com/greynewell/mcpbr/labels/help%20wanted)** --- features that need contributors
- **[Contributing Guide](contributing.md)** --- how to set up and submit PRs
- **[GitHub Discussions](https://github.com/greynewell/mcpbr/discussions)** --- questions and ideas

### Links

| Resource | Link |
|----------|------|
| GitHub | [github.com/greynewell/mcpbr](https://github.com/greynewell/mcpbr) |
| PyPI | [pypi.org/project/mcpbr](https://pypi.org/project/mcpbr/) |
| npm | [npmjs.com/package/mcpbr-cli](https://www.npmjs.com/package/mcpbr-cli) |
| Documentation | [mcpbr.org](https://mcpbr.org/) |
| Blog Post | [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/) |
| Creator | [greynewell.com](https://greynewell.com) |
| Roadmap | [Project Board](https://github.com/users/greynewell/projects/2) |
| License | [MIT](https://github.com/greynewell/mcpbr/blob/main/LICENSE) |

---

Built by [Grey Newell](https://greynewell.com) | [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/)
