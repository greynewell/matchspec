# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.18] - 2026-01-22

### Added

- **Plugin Marketplace**: Added `marketplace.json` for Claude Code plugin manager installation (closes #266)
  - Proper marketplace manifest with owner information
  - GitHub source configuration for plugin distribution
  - Automatic installation via Claude Code plugin manager
- **Plugin Documentation**: Comprehensive documentation for the Claude Code plugin (closes #273)
  - Installation guide with multiple methods
  - Complete skills reference for all three skills
  - Architecture explanation and execution flow
  - Troubleshooting section with common issues
  - FAQ covering plugin usage and development
- **Plugin Validation**: Automated validation of plugin manifests in CI
  - Python-based validation script for plugin.json and marketplace.json
  - Checks required fields, structure, and schema compliance
  - Runs on every PR to prevent breaking changes
- **Community Guidelines**: Added Code of Conduct for project contributors
  - Contributor Covenant code of conduct
  - Guidelines for respectful collaboration

### Changed

- **Version Sync**: Enhanced version sync script to include marketplace.json
  - Syncs version across plugin.json, marketplace.json, and package.json files
  - Updates both root and nested plugin versions
  - Ensures consistency across all distribution channels
- **CI/CD**: Updated CI to validate all version files are synced
  - Checks plugin.json, marketplace.json, package.json versions
  - Prevents version drift across npm packages

### Infrastructure

- **npm Publishing**: First official npm package releases
  - `@greynewell/mcpbr` - CLI wrapper for cross-platform installation
  - `@greynewell/mcpbr-claude-plugin` - Claude Code plugin package
  - Automated publishing workflow on GitHub releases
  - Publishes both packages with synchronized versions

## [0.3.17] - 2026-01-22

### Added

- **Claude Code Plugin**: Added specialized Claude Code plugin with custom skills for enhanced MCP server evaluation
  - Custom skills tailored for benchmarking workflows (`benchmark-swe-lite`, `mcpbr-config`, `mcpbr-eval`)
  - Integration with Claude Code CLI for improved agent capabilities
  - Published as npm package `@greynewell/mcpbr-claude-plugin`
- **npm CLI Wrapper**: Added Node.js wrapper (`bin/mcpbr.js`) for cross-platform npm installation
  - Published as `@greynewell/mcpbr` on npm
  - Automatic detection and invocation of Python CLI
  - Supports npx usage: `npx @greynewell/mcpbr`

### Fixed

- Improved pre-commit configuration for consistent linting in CI
- Addressed code quality issues from CodeRabbit review
- Added `__main__.py` to enable `python -m mcpbr` execution
- Fixed `--version` flag handling at CLI group level

## [0.3.16] - 2026-01-22

### Fixed

- MCP Docker context preservation: Use `su` without login flag to preserve project context for MCP servers

## [0.3.15] - 2026-01-21

### Added

- **CSV Export**: New `mcpbr export csv` command to convert results to CSV format (closes #11)
  - Export evaluation results with customizable columns
  - Supports filtering by status (pass/fail/error)
  - Easy integration with spreadsheet tools

## [0.3.14] - 2026-01-21

### Added

- **Streaming Results Support**: Real-time streaming of evaluation results to SSE endpoint (closes #259)
  - Enable with `--stream-to` flag or `stream_to` config option
  - Immediate visibility into evaluation progress
  - Compatible with web dashboards and monitoring tools

## [0.3.13] - 2026-01-21

### Added

- **Incremental Evaluation**: Only re-run failed tasks with `--incremental` flag (closes #258)
  - Automatically resume from previous failed evaluations
  - Skip already passing tasks to save time and cost
  - Useful for iterating on fixes or retrying flaky tests

## [0.3.12] - 2026-01-20

### Added

- **Configuration Validation Schema**: Comprehensive JSON schema validation for config files (closes #98)
  - Validate config files with `mcpbr config validate`
  - Clear error messages for invalid configurations
  - IDE autocompletion support via schema

## [0.3.11] - 2026-01-20

### Added

- **Benchmark Result Caching**: Cache evaluation results to avoid redundant runs (closes #255)
  - Automatic caching of task evaluations
  - Significant speed improvements for repeated runs
  - Cache invalidation based on configuration changes

## [0.3.10] - 2026-01-19

### Added

- **Config Inheritance**: Support for `extends` field in configuration files (closes #106)
  - Reuse common settings across multiple config files
  - Override specific fields while inheriting base configuration
  - Supports relative and absolute paths

## [0.3.9] - 2026-01-19

### Added

- **Smoke Test Mode**: New `--smoke-test` flag to validate setup without full evaluation (closes #253)
  - Quickly verify environment configuration
  - Test single task instance to ensure everything works
  - Useful for CI/CD pipeline validation
- **Incremental Saving**: Automatically save results after each task completion (closes #252)
  - Prevents data loss on crashes or interruptions
  - Resume evaluations from last completed task
  - Intermediate results available during long-running evaluations

## [0.3.8] - 2026-01-18

### Added

- **Environment Variable Support**: Use environment variables in config files with `${VAR}` syntax (closes #251)
  - Reference secrets and dynamic values
  - Example: `api_key: ${ANTHROPIC_API_KEY}`
  - Supports default values: `${VAR:-default}`

### Fixed

- Documentation: Fixed broken links in FAQ

## [0.3.7] - 2026-01-18

### Added

- **Best Practices Guide**: Comprehensive guide for effective MCP server evaluation (closes #199)
  - Configuration optimization tips
  - Performance tuning recommendations
  - Common pitfalls and solutions

## [0.3.6] - 2026-01-17

### Added

- **Example Configurations Repository**: Added collection of example config files (closes #200)
  - Ready-to-use configurations for common scenarios
  - Templates for different providers and harnesses
  - Documented best practices

## [0.3.5] - 2026-01-17

### Added

- **FAQ Documentation**: Comprehensive frequently asked questions section (closes #204)
  - Common issues and solutions
  - Setup troubleshooting
  - Performance optimization tips

## [0.3.3] - 2026-01-17

### Added

- **Docker Cleanup Enhancements**: Comprehensive Docker resource cleanup on errors (closes #194)
  - Automatic cleanup of containers on failure
  - Prevention of resource leaks
  - Improved error handling

## [0.3.2] - 2026-01-17

### Added

- **Tool Coverage Reporting**: Analyze which MCP tools were used during evaluation (closes #225)
  - Track tool usage frequency
  - Identify unused tools
  - Coverage metrics in results JSON

## [0.3.1] - 2026-01-17

### Added

- **MCPToolBench++ Integration**: Support for MCPToolBench++ benchmark (closes #223)
  - Evaluate MCP servers on standardized tool usage tasks
  - Integration with MCPToolBench++ dataset
  - Comprehensive tool evaluation capabilities

## [0.3.0] - 2026-01-17

### Added

- **Regression Detection**: Automated detection of performance regressions (closes #65)
  - Compare results against baseline
  - Configurable regression thresholds
  - Alert notifications for detected regressions
- **YAML Export**: Convert results to YAML format with `mcpbr export yaml` (closes #12)
  - Human-readable output format
  - Easy integration with other tools
- **Enhanced Agent Documentation**: Comprehensive AGENTS.md with guidelines for AI agents

### Changed

- Expanded documentation with comprehensive guidelines
- Updated roadmap with v1.0 milestones

## [0.2.3] - 2026-01-17

### Added

- **v1.0 Roadmap**: Comprehensive roadmap section in README
  - Planned features and improvements
  - Timeline and milestones

### Fixed

- Improved MCP tool error handling and logging (closes #10)
  - Better error messages for tool failures
  - Enhanced debugging capabilities

## [0.2.2] - 2026-01-17

### Changed

- Version bump for release consistency

## [0.2.1] - 2026-01-17

### Fixed

- Prevent dataset configuration override issues
  - Ensure dataset settings are properly applied
  - Fix configuration precedence

### Documentation

- Improved README with one-line install instructions

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

[0.3.18]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.18
[0.3.17]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.17
[0.3.16]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.16
[0.3.15]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.15
[0.3.14]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.14
[0.3.13]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.13
[0.3.12]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.12
[0.3.11]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.11
[0.3.10]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.10
[0.3.9]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.9
[0.3.8]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.8
[0.3.7]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.7
[0.3.6]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.6
[0.3.5]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.5
[0.3.3]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.3
[0.3.2]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.2
[0.3.1]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.1
[0.3.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.0
[0.2.3]: https://github.com/greynewell/mcpbr/releases/tag/v0.2.3
[0.2.2]: https://github.com/greynewell/mcpbr/releases/tag/v0.2.2
[0.2.1]: https://github.com/greynewell/mcpbr/releases/tag/v0.2.1
[0.2.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.2.0
[0.1.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.1.0
