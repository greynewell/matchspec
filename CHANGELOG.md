# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-17

### Added

- **CyberGym Benchmark Support**: Added support for [CyberGym](https://cybergym.cs.berkeley.edu/) security vulnerability benchmark
  - Agents generate Proof-of-Concept (PoC) exploits for real CVEs
  - 4 difficulty levels (0-3) controlling context provided to agent
  - Evaluation by crash detection with AddressSanitizer
  - Automatic C/C++ build environment setup with sanitizers
- **Benchmark Abstraction Layer**: New flexible architecture for multiple benchmarks
  - Protocol-based `Benchmark` interface with standardized methods
  - Easy to add new benchmarks by implementing the protocol
  - `BenchmarkTask` and `EvaluationSpec` for normalized task representation
- **Benchmark Registry**: Factory pattern for creating benchmark instances
  - `create_benchmark()` function for dynamic benchmark selection
  - `list_benchmarks()` to see available benchmarks
- **New CLI Commands**:
  - `mcpbr benchmarks` - List available benchmarks with descriptions
- **New CLI Options**:
  - `--benchmark` / `-b` - Select benchmark (swe-bench or cybergym)
  - `--level` - Set CyberGym difficulty level (0-3)
- **Configuration Fields**:
  - `benchmark`: Select which benchmark to run (default: "swe-bench")
  - `cybergym_level`: Set CyberGym difficulty (default: 1)
  - `dataset`: Now optional, benchmark provides default
- **Benchmark-Specific Agent Prompts**: Different prompts for bug fixing vs exploit generation
- **Comprehensive Documentation**:
  - New [Benchmarks Guide](https://greynewell.github.io/mcpbr/benchmarks/) page
  - Updated README with CyberGym information
  - Updated configuration and CLI documentation
  - Architecture documentation updated for benchmark abstraction
- **Test Coverage**: 20 new tests for benchmark implementations and protocol compliance

### Changed

- Refactored SWE-bench logic into `benchmarks/swebench.py` (no behavior change)
- Harness orchestrator now uses benchmark abstraction instead of direct dataset loading
- Agent prompts are now provided by benchmarks (can still be overridden in config)
- Dataset field in config is now optional (benchmarks provide defaults)
- Updated example configurations to include benchmark options

### Backward Compatibility

- **Fully backward compatible** - all existing SWE-bench workflows continue to work unchanged
- Default benchmark is still SWE-bench
- All existing configuration files work without modification

## [0.1.0] - 2026-01-17

### Added

- Initial release of mcpbr (Model Context Protocol Benchmark Runner)
- Support for multiple LLM providers:
  - OpenRouter (multi-provider gateway)
  - OpenAI (direct API)
  - Anthropic (direct API)
  - Google AI / Gemini (direct API)
- Agent harness implementations:
  - Claude Code CLI with MCP server support
  - OpenAI Codex CLI
  - OpenCode CLI
  - Gemini CLI
- Docker-based task isolation for SWE-bench evaluation
- Baseline agent for comparison (no tools)
- JSON and Markdown report generation
- Configurable evaluation parameters via YAML
- CLI commands: `run`, `init`, `models`, `harnesses`, `providers`
- Real-time streaming output when using `--verbose` flag with Claude Code harness
- Tool usage tracking: counts tool calls by name and includes breakdown in results JSON
- Each streamed output line is prefixed with task instance ID for parallel worker disambiguation
- **In-container agent execution**: The Claude Code CLI now runs inside the Docker container where all dependencies are installed. This ensures Python imports work correctly (e.g., `from astropy import ...`) and the agent can verify fixes by running tests.
- Pre-built SWE-bench Docker images from Epoch AI's registry (`ghcr.io/epoch-research/swe-bench.eval`) are now used when available, providing:
  - Repository at the correct commit with all dependencies pre-installed
  - Consistent, reproducible evaluation environments
  - x86_64 images with automatic emulation on ARM64 (Apple Silicon) Macs
- Timestamped log filenames to prevent overwrites: `{instance_id}_{run_type}_{YYYYMMDD_HHMMSS}.json`
- `--no-prebuilt` CLI flag to disable pre-built images and build from scratch
- Network access for containers to enable API calls from within Docker

[0.2.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.2.0
[0.1.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.1.0
