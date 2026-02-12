# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MCP native tool blocking** (#450): New `disallowed_native_tools` and `system_prompt_append`
  fields in `mcp_server` config. When set, `--disallowedTools` strips specified native tools
  (e.g., Read, Grep, Glob) from the API tool definitions, forcing the agent to use MCP
  equivalents. `--append-system-prompt` can guide the agent toward MCP tools. Essential for
  meaningful MCP vs native tool benchmarking.
- **Claude Code version pinning** (#453): New `claude_code_version` config field lets you pin a
  specific Claude Code version inside Docker containers (e.g., `claude_code_version: "2.1.37"`).
  Useful for version comparison experiments. Older versions that lack `--max-turns` support
  (pre-2.1.x) are automatically detected and the flag is omitted.
- **Eval started notifications** (#413): Notifications are now sent when an evaluation begins,
  including benchmark name, model, task count, concurrency, and infrastructure mode
- **Infrastructure lifecycle notifications** (#414): `infra_provisioned` and `infra_teardown`
  events notify when cloud VMs are provisioned (with SSH command) and torn down
- **Progress notifications** (#415): Periodic progress updates during long-running evaluations,
  configurable via `notify_progress_interval` (every N tasks) and
  `notify_progress_time_minutes` (every N minutes). Includes completed/total counts, elapsed
  time, ETA, and running cost
- **Failure notifications** (#416): Immediate notification when an evaluation fails with error
  details, completed task count, and last successful task ID

### Security

- **Sandbox seccomp default-deny allowlist** (#417): Strict sandbox mode now uses a seccomp
  allowlist (default-deny) instead of a blocklist, preventing bypass via unlisted syscalls
- **Shell injection prevention in infrastructure providers** (#421, #422): `python_version`
  and env key names are now validated with strict regex before interpolation into shell commands
  in AWS and GCP providers. SSH firewall rules raise `RuntimeError` instead of falling back to
  `0.0.0.0/0` when IP detection fails.
- **Audit HMAC chain tamper protection** (#419): Audit log entries now use a secret HMAC key
  and chain on recomputed checksums, making the tamper-evident chain resistant to forgery
- **API authentication, CORS headers, and limit validation** (#420): REST API now supports
  bearer token authentication, sends security headers (`X-Content-Type-Options: nosniff`),
  warns when binding to `0.0.0.0`, and validates the `?limit=` query parameter
- **Plugin registry SSRF prevention** (#428): Registry URL scheme is now validated (must be
  `https://`) and response body size is limited to prevent SSRF and resource exhaustion
- **Prompt scanner multi-match fix** (#423): Prompt security scanner now checks all regex
  matches per pattern instead of stopping at the first match, preventing evasion by placing
  benign content before malicious payloads
- **Cloudflare Worker auth enforcement** (#426): Worker deployments now require authentication
  by default. A secure token is auto-generated if none is provided in the config.
- **Safer K8s DinD defaults** (#426): Docker-in-Docker sidecar uses rootless Docker image
  (`docker:27-dind-rootless`) instead of `--privileged` by default. Privileged mode can be
  explicitly enabled via `dind_privileged: true`.
- **Sandbox strict mode validation** (#427): `validate_sandbox()` now raises `ValueError` in
  strict mode when container settings don't match the security profile, instead of only logging warnings

### Changed

- **Default disk size increased to 1 TB** (#434): `disk_gb` default changed from 250 to 1000
  across AWS, GCP, and Azure providers to accommodate swe-bench-verified evaluations

### Fixed

- **MCP log directory permission error** (#451): Claude CLI running as non-root `mcpbr` user
  could fail with `EACCES` when creating MCP log directories under `~/.cache/`. The home
  directory and `.cache` subdirectory are now explicitly created and owned by the `mcpbr` user
  during container setup
- **K8s async context crash** (#424): Replaced `run_until_complete` with `await` in K8s
  provider async methods, fixing crashes when called from an existing event loop
- **SQLite UPSERT timestamp preservation** (#425): Changed `INSERT OR REPLACE` to
  `INSERT ... ON CONFLICT DO UPDATE` so `created_at` timestamps are preserved on re-runs
- **Infrastructure resource leak fixes** (#430): SFTP connections in AWS/GCP now close in
  `finally` blocks; Kubernetes `setup()` cleans up partial ConfigMaps/Secrets on failure
- **PII pattern coverage** (#431): Added abbreviated IPv6, SSN without dashes, Amex credit
  cards, and international phone number detection to the privacy module
- **Distributed coordinator reliability** (#432): Added per-worker timeouts via
  `asyncio.wait_for()`, config isolation with `copy.deepcopy()`, `asyncio.Lock` for shared
  state safety, and `DistributedExecutionError` with fail-fast error propagation
- **Cloud storage error handling** (#429): Added retry logic with exponential backoff,
  `CloudStorageError` for timeout/auth errors, partial file cleanup on failed downloads,
  and CLI-not-found handling for GCS/Azure
- **network_allowlist warning** (#418): Logs a warning when `network_allowlist` is configured
  but not yet enforced at runtime, instead of silently ignoring the setting

## [0.12.0] - 2026-02-07

### Added

- **Docker sandbox enhancements** (#381): Extended sandbox security profiles with new isolation features
  - User namespace remapping (`userns_mode`) for container user isolation
  - I/O rate limits (`device_read_bps`, `device_write_bps`) for disk throughput control
  - Network allowlist (`network_allowlist`) for fine-grained network access control
  - Sandbox validation (`validate_sandbox()`) to verify container settings match the profile
  - Per-benchmark sandbox defaults: CyberGym and Adversarial benchmarks default to strict mode
  - Audit logging for sandbox events (`SANDBOX_APPLIED`, `SANDBOX_VALIDATED`)
  - Strict profile now enables user namespace remapping by default
- **Prompt security scanning** (#108): Detect prompt injection attacks in benchmark tasks
  - 10 built-in detection patterns: instruction override, identity injection, system prompt leak,
    jailbreak prefixes (DAN/STAN/DUDE/AIM), role-play injection, base64 injection, unicode
    obfuscation, shell injection, reverse shell, and delimiter injection
  - Configurable scan levels: `full` (all patterns) or `minimal` (HIGH/CRITICAL only)
  - Three action modes: `audit` (log only), `warn` (log warnings), `block` (skip task)
  - Custom pattern support via YAML configuration
  - Allowlist patterns to suppress false positives
  - Audit logging for scan findings (`SECURITY_SCAN_FINDING`, `SECURITY_SCAN_BLOCKED`)
  - New `prompt_security` configuration section in YAML

### Fixed

- **Misleading 'no changes detected' error** (#409): When an agent wrote changes that were
  later reverted, the error field incorrectly reported "no changes detected." Now reports
  "working tree is clean - changes were likely reverted" with tool call counts, and suppresses
  the error entirely when a patch was generated and evaluated.

### Documentation

- **About page**: New docs/about.md page with the mcpbr origin story, project vision, community
  links, and prominent links to the [Why I Built mcpbr](https://greynewell.com/blog/why-i-built-mcpbr/) blog post
- **Testing Philosophy page**: New docs/philosophy.md page expanding on the principle that
  "MCP servers should be tested like APIs, not like plugins" with detailed evaluation design guidance
- **Blog post integration**: Added links to the origin story blog post across README, docs homepage,
  FAQ, architecture, MCP integration, best practices, and contributing pages
- **Navigation update**: Added About section to mkdocs.yml with About and Testing Philosophy pages

### Fixed

- **Retry empty workspace after Docker copy** (#405): Under high concurrency, the Docker
  filesystem copy from `/testbed` to `/workspace` can silently produce an empty workspace.
  Now retries with a sync and, if necessary, a full re-copy before raising an error.
- **setup_command runs as mcpbr user in Docker** (#386): setup_command now executes as the
  mcpbr user instead of root, preventing EACCES permission errors when the agent accesses
  files created during setup (e.g., npm cache)
- **Workspace verification after copy** (#387): Added filesystem sync and file-count check
  after copying the repo to /workspace, raising an early error if the workspace is empty
- **setup_command failures are always visible** (#388): Non-zero exit codes from
  setup_command now always print a warning, not just in `--verbose` mode
- **Azure health check timeout** (#375): Increased Azure quota health check timeout from
  60s to 120s (configurable) and made quota check non-fatal with warnings instead of errors
- **CLI task filters not forwarded** (#367): Task IDs specified via `-t` CLI flags are now
  correctly forwarded to remote infrastructure providers during evaluation

### Added

- **Sandbox execution environment** (#109): Configurable Docker security profiles for
  benchmark evaluation containers
  - Three security levels: permissive, standard (default), and strict
  - Seccomp profile generation with syscall allow/deny lists
  - Network, filesystem, and capability controls per security level
  - YAML config integration via `sandbox` section
- **Database backend** (#86): SQLite storage backend for persistent evaluation results
  - Async `SQLiteStorage` with automatic schema creation (runs + task_results tables)
  - Store, query, list, and delete evaluation runs
  - Task-level result storage with JSON serialization
  - `StorageBackend` abstract base class for future backends
- **Cloud storage support** (#87): Upload results and artifacts to cloud object storage
  - `S3Storage` for AWS S3 with presigned URL generation
  - `GCSStorage` for Google Cloud Storage
  - `AzureBlobStorage` for Azure Blob Storage with SAS URL generation
  - `create_cloud_storage()` factory for provider selection
  - CLI tool-based implementation (no SDK dependencies)
- **AWS EC2 infrastructure provider** (#352): Run evaluations on AWS EC2 instances
  - Automatic instance provisioning with configurable instance types and AMIs
  - SSH connectivity via paramiko with key management
  - Remote Docker/Python/Node.js dependency installation
  - Health checks for AWS CLI, authentication, and instance type availability
  - Full lifecycle: setup, evaluation, artifact collection, cleanup
- **GCP Compute Engine infrastructure provider** (#353): Run evaluations on GCP VMs
  - Instance provisioning via `gcloud compute` CLI
  - SSH connectivity with GCP-managed keys
  - Health checks for gcloud CLI, authentication, project, and zone configuration
  - Configurable machine types, disk sizes, and network settings
- **Kubernetes infrastructure provider** (#355): Run evaluations as Kubernetes Jobs
  - Job manifest generation with configurable resource requests/limits
  - ConfigMap and Secret creation for benchmark configuration
  - Pod log streaming and artifact collection
  - Health checks for kubectl, cluster access, namespace, and resource quotas
  - Automatic cleanup of Jobs, ConfigMaps, and Secrets
- **Cloudflare Workers infrastructure provider** (#354): Hybrid Worker-based evaluation
  - Wrangler CLI integration for Worker deployment
  - KV namespace management for result storage
  - Worker script generation with benchmark compatibility checks
  - Health checks for wrangler CLI, authentication, and Node.js
  - Supports custom and HumanEval benchmarks via Worker execution
- **Distributed execution coordinator** (#116): Coordinate running evaluations across multiple
  workers/machines with automatic task partitioning and result merging
  - `TaskPartitioner` with even round-robin and difficulty-balanced (LPT) partitioning strategies
  - `WorkerResult` dataclass for per-worker execution results with timing and error tracking
  - `DistributedCoordinator` that partitions tasks, launches workers concurrently via
    `asyncio.gather`, and merges results into a unified `EvaluationResults` object
  - Supports all infrastructure providers: local, AWS, GCP, Kubernetes, Azure
- **Multi-benchmark runner** (#359): Run multiple benchmarks in a single invocation with parallel
  execution and aggregated results
  - `MultiBenchmarkRunner` with asyncio semaphore-based concurrency control
  - `BenchmarkRun`, `BenchmarkResult`, and `MultiBenchmarkResults` dataclasses for configuration
    and result aggregation
  - `partition_tasks` utility for sharding task lists across runners
  - Summary property with aggregate pass rate, task counts, and duration
- **REST API server** (#83): HTTP API for querying evaluation results and server status
  - `GET /api/v1/health` — server health check
  - `GET /api/v1/runs` — list all evaluation runs
  - `GET /api/v1/runs/{id}` — get a specific run with results
  - `GET /api/v1/runs/{id}/tasks` — get task-level results for a run
  - `DELETE /api/v1/runs/{id}` — delete an evaluation run
  - `GET /api/v1/stats` — aggregate statistics across all runs
  - Built on Python `http.server` (no external dependencies)
  - `mcpbr serve` CLI command for starting the API server
- **Cross-platform compatibility** (#161): Windows support utilities and path normalization
  - Platform detection helpers (`is_windows`, `is_macos`, `is_linux`)
  - Platform-aware directory paths for data, cache, config, and temp
  - Windows Docker path normalization (e.g., `C:\Users\...` → `/c/Users/...`)
  - Shell detection (PowerShell/cmd fallback on Windows, bash on Unix)
  - Docker socket path abstraction (Unix socket vs Windows named pipe)
- **VS Code extension scaffold** (#163): Extension for running benchmarks from VS Code
  - Sidebar views for benchmark results and configuration
  - Commands: run benchmark, stop, select config, view results, open dashboard
  - `BenchmarkRunner` class spawning mcpbr CLI as child process
  - Tree data providers for results and config display
  - Configuration settings for Python path and API host
- **Plugin registry** (#267): Discover and register MCP server benchmark plugins
  - `PluginEntry` and `Registry` dataclasses with search by name, description, and tags
  - `RegistryClient` with HTTP fetch, caching, search, and list operations
  - `generate_registry_entry()` for mcpbr self-registration
  - JSON-based registry format hosted on GitHub
- **Rate limiting for API calls** (#196): Intelligent rate limiting to prevent API quota exhaustion
  - Token bucket algorithm with configurable requests-per-minute (`rate_limit_rpm`)
  - Three backoff strategies: fixed, exponential, and adaptive (with jitter)
  - Retry-After header parsing for automatic 429 recovery
  - Real-time metrics tracking (throttled requests, total wait time, error counts)
  - Configurable safety margin to stay within provider limits
- **Benchmark reproducibility** (#136): Ensure evaluations are reproducible across runs
  - Global random seed control (`global_seed`) for deterministic evaluation ordering
  - Environment snapshot capture (Python version, platform, installed packages)
  - Deterministic mode with `PYTHONHASHSEED` control
  - SHA256 checksums for reproducibility report verification
  - JSON-serializable reproducibility reports for sharing and auditing
- **Privacy controls** (#120): PII detection, redaction, and data governance
  - Three redaction levels: none, basic (emails/keys/IPs), strict (all PII patterns)
  - 7 built-in PII patterns (email, API key, IPv4/IPv6, credit card, SSN, phone)
  - Custom regex pattern support for organization-specific redaction
  - Recursive dict redaction for nested result structures
  - Task ID anonymization via SHA256 hashing
  - Data retention policies with configurable expiry
  - Field exclusion to strip sensitive result fields before saving
- **Audit logging** (#118): Tamper-proof audit trail for compliance and security
  - 13 auditable event types covering config, benchmark, task, result, and data lifecycle
  - HMAC-SHA256 hash chain for tamper detection and integrity verification
  - JSON and CSV export formats for compliance reporting
  - Configurable event filtering (log all or specific event types)
  - Append-only JSONL file logging with automatic directory creation
  - Standalone `verify_integrity()` to detect log tampering
- **Interactive tutorial system** (#198, #157): CLI-based tutorials for learning mcpbr
  - `mcpbr tutorial list` — browse available tutorials with difficulty levels
  - `mcpbr tutorial start <id>` — step-by-step walkthrough with validation
  - `mcpbr tutorial progress` — track completion across all tutorials
  - `mcpbr tutorial reset <id>` — restart a tutorial from scratch
  - 4 built-in tutorials: Getting Started, Configuration, Benchmarks, Analytics
  - Progress persistence in `~/.mcpbr_state/tutorials/`
- **Comprehensive API reference documentation** (#202, #156): Auto-generated docs from source
  - SDK, Configuration, Benchmarks, Analytics, and Reports API pages
  - mkdocstrings integration for live source rendering
- **Enhanced benchmark guides** (#203): 6 benchmark docs expanded to comprehensive guides
  - HumanEval, GSM8K, GAIA, CyberGym, TerminalBench, MCPToolBench++ — each with evaluation methodology, configuration examples, best practices, and troubleshooting
- **Plugin development guide** (#160): Complete guide for extending mcpbr
  - Custom benchmark creation with Benchmark protocol walkthrough
  - Custom provider and custom metrics implementation
  - Testing guidelines and publishing instructions
- **Best practices guide enhancements** (#159): 6 new sections added
  - Security, Performance Optimization, CI/CD Integration, Troubleshooting, Cost Management, Analytics Best Practices
  - 6 new FAQ entries covering common workflows
- **Custom domain** (#379): Documentation site now served at https://mcpbr.org/
  - GitHub Pages CNAME configuration
  - All documentation URLs updated to mcpbr.org

## [0.7.0] - 2026-02-06

### Added

- **Analytics package** (#178, #179, #183, #61, #63, #57, #60, #180, #181, #182, #184, #185, #187, #226, #227): Comprehensive analytics and insights engine
  - **Historical results database** (#178): SQLite-backed `ResultsDatabase` for storing, querying, and tracking evaluation runs over time
  - **Performance regression detection** (#179): `RegressionDetector` with statistical significance testing for score, cost, latency, and token regressions
  - **Multi-model comparison** (#183): `ComparisonEngine` with Pareto frontier analysis, winner analysis, and pairwise statistical significance testing
  - **Statistical significance testing** (#61, #63): Chi-squared test, bootstrap confidence intervals, Cohen's d effect size, Mann-Whitney U, and permutation tests — all implemented with stdlib only (no numpy/scipy)
  - **Trend analysis** (#57, #60): Time-series trend detection with linear regression, moving averages, and direction classification
  - **A/B testing framework** (#180): `ABTest` class for controlled experiment analysis with resolution rate comparison
  - **Leaderboard generation** (#181): Ranked leaderboards with ASCII table and Markdown output, sortable by any metric
  - **Custom metrics registry** (#182): `MetricsRegistry` with 5 built-in metrics and extensible custom metric registration
  - **Benchmark difficulty estimation** (#184): Task difficulty scoring based on resolution rates, cost, and iterations
  - **Correlation analysis** (#185): Pearson and Spearman correlation with automatic metric pair analysis
  - **Anomaly detection** (#187): Z-score, IQR, and MAD methods for detecting outlier tasks across cost, tokens, runtime, and iterations
  - **Error pattern analysis** (#227): `ErrorPatternAnalyzer` with Jaccard similarity clustering, temporal pattern detection, and actionable recommendations
  - **Cross-benchmark comparison** (#226): Side-by-side comparison with task-level overlap analysis and unique-win identification
- **Interactive HTML reports** (#39, #55): `HTMLReportGenerator` with Chart.js charts, dark mode toggle, sortable task tables, and responsive layout
- **Enhanced Markdown reports** (#42): `EnhancedMarkdownGenerator` with shields.io badges, mermaid pie/bar charts, collapsible sections, and analysis tables
- **PDF reports** (#56): `PDFReportGenerator` with CSS @media print styles, page numbers, custom branding, and optional weasyprint PDF export
- **Comparison reports** (#53, #59): `mcpbr compare` CLI command for multi-run comparison with statistical significance, winner analysis, and Pareto frontier
- **CLI report output flags**: `--output-html`, `--output-markdown`, `--output-pdf` options on the `mcpbr run` command for generating reports alongside evaluation
- **CLI analytics subcommands**: `mcpbr analytics store`, `mcpbr analytics trends`, `mcpbr analytics leaderboard`, `mcpbr analytics regression` for database-backed analytics workflows
- **310 new tests** for analytics modules, report generators, and CLI commands

## [0.6.0] - 2026-02-05

### Added

- **Graceful degradation** (#70): Fault-tolerant task execution with failure isolation, classification (transient/permanent/unknown), configurable `continue_on_error` and `max_failures` policies, execution checkpointing for crash recovery, and partial report generation
  - New config fields: `continue_on_error`, `max_failures`, `checkpoint_interval`, `resume_from_checkpoint`
- **Multi-provider support** (#229): Added OpenAI, Google Gemini, and Alibaba Qwen as model providers alongside Anthropic
  - `OpenAIProvider` for GPT-4o, GPT-4 Turbo, and GPT-4o Mini models
  - `GeminiProvider` for Gemini 2.0 Flash, Gemini 1.5 Pro, and Gemini 1.5 Flash models
  - `QwenProvider` for Qwen Plus, Qwen Turbo, and Qwen Max models via DashScope API
  - New optional dependencies: `openai`, `gemini`, `all-providers` extras
  - Pricing data for all 9 new models
  - Model registry entries with context window and tool support metadata
- **Multi-language support** (#230): Cross-language benchmark execution for Python, JavaScript, TypeScript, Java, and Go
  - Per-language Docker images, run/compile commands, and test framework configs
  - Automatic language detection from filenames and code patterns
  - Cross-language metrics aggregation
- **Structured logging** (#231): JSON and human-readable log formatters with contextual metadata
  - File rotation, configurable log levels via `MCPBR_LOG_LEVEL` env var
  - `LogContext` context manager for injecting task/benchmark fields into log records
- **Public Python SDK** (#232): Programmatic API for configuring and running benchmarks
  - `MCPBenchmark` class with config from dict, YAML, or `HarnessConfig`
  - `list_benchmarks()`, `list_providers()`, `list_models()`, `get_version()` helpers
  - Exported in top-level `mcpbr` package for `from mcpbr import MCPBenchmark`
- **Platform distribution files**: Docker, Conda, Homebrew, GitHub Actions, and CI templates
  - `Dockerfile.app` multi-stage build for container deployment
  - `docker/docker-compose.yml` for multi-container orchestration
  - `conda/meta.yaml` recipe for Conda packaging
  - `action/action.yml` GitHub Action with basic and matrix examples
  - `ci-templates/` for GitLab CI and CircleCI integration

## [0.5.5] - 2026-02-06

### Fixed

- **Retry empty workspace after Docker copy** (#405): Under high concurrency, the Docker
  filesystem copy from `/testbed` to `/workspace` can silently produce an empty workspace.
  Now retries with a sync and, if necessary, a full re-copy before raising an error.

## [0.5.0] - 2026-02-05

### Added

- **Real-time web dashboard** (#58): Live monitoring of benchmark evaluations via `DashboardServer` with FastAPI + WebSocket, task progress, resolution rate, ETA, and pause/resume/cancel controls
- **Interactive configuration wizard** (#74): Step-by-step CLI wizard for creating config files with presets (filesystem, web-search, database), model/benchmark selection, and MCP server setup
- **Dry-run mode** (#84): Preview evaluation plan without executing — shows tasks, estimated cost/time, validates config, checks Docker and MCP server availability
- **Task prioritization and scheduling** (#92): Intelligent task ordering with speed-first, cost-first, coverage-first, and custom scoring strategies
- **Color and formatting options** (#105): Configurable output themes (default, minimal, plain) with NO_COLOR convention support and MCPBR_THEME env var
- **Docker image pre-warming** (#128): Pre-pull Docker images in parallel before evaluation starts with progress reporting and cache detection
- **Result streaming to external storage** (#131): Stream results as tasks complete to local JSONL files, S3-compatible storage, or webhooks with buffering and retry
- **Memory-efficient large dataset handling** (#134): Streaming and chunked loading of large HuggingFace datasets with memory monitoring and automatic chunk-size adaptation
- **Task batching with smart scheduling** (#137): Group similar tasks by repo/image/category to minimize Docker container restarts with adaptive batch sizing
- **Resource limit configuration** (#139): Configure CPU, memory, disk, PID, and network limits for Docker containers with monitoring and violation reporting
- **Configuration migration tool** (#195): Detect and migrate old config formats (V1→V4) with dry-run preview, backup, and chained migration steps
- **Docker image caching optimization** (#228): LRU cache management with size limits, usage tracking, eviction, warmup recommendations, and dangling image cleanup

### Fixed

- **Zero-cost metrics on evaluation timeout** (#374): Agent metrics (cost, tokens, iterations) were discarded when `benchmark.evaluate()` timed out after the agent had already completed successfully. Now preserves agent results when available.
- **Process hang after evaluation completes** (#374): `asyncio.run()` blocked indefinitely during cleanup because Docker SDK urllib3 background threads kept the default executor alive. Now force-shuts down the executor with `wait=False`.

## [0.4.16] - 2026-02-05

### Added

- **Custom benchmark support via YAML** (#29, #47): Users can define custom benchmarks without writing Python code using YAML definition files with configurable evaluation types (exact_match, numeric, regex, script)
- **Custom metrics framework** (#64): Define and compute custom evaluation metrics beyond standard accuracy/pass rates, with composite metrics support and a built-in metric registry
- **Failure analysis module** (#67): Categorize and analyze evaluation failures with pattern extraction, failure reports, and actionable recommendations
- **Random and stratified sampling** (#142): Add sampling strategies (sequential, random, stratified) with seed control for reproducible benchmark task selection
- **Dataset versioning** (#138): Pin and track HuggingFace dataset versions for reproducible benchmark runs with manifest save/load support
- **Latency and performance metrics** (#129): Track task latency, time-to-first-tool-call, throughput, and percentile statistics (p50/p95/p99)
- **GPU support for Docker containers** (#121): Detect NVIDIA GPUs and configure Docker containers with GPU access for ML benchmarks
- **Few-shot learning support** (#127): Variable shot counts with selection strategies (random, similar, diverse) and learning curve analysis
- **MMMU multi-modal benchmark** (#123): Massive Multi-discipline Multimodal Understanding benchmark for image understanding tasks
- **LongBench long-context benchmark** (#125): Long-context benchmark with F1, ROUGE-L, classification accuracy, and edit similarity metrics across 21 subsets
- **Adversarial testing benchmark** (#126): Safety and robustness benchmark using HarmBench with refusal detection across jailbreak, hallucination, bias, and robustness categories
- **MCPToolBench++ integration tests** (#232): Comprehensive test suite for the MCPToolBench++ benchmark implementation
- **21 new benchmark implementations** (#6, #7, #18, #19, #20, #22, #24, #25, #26, #27, #28, #33, #34, #35, #37, #38, #40, #45, #46, #49): Initial stub implementations for all planned benchmarks

### Fixed

- **Repository-aware test commands for non-pytest projects** (#365): Use upstream SWE-bench test command specs for sympy (`bin/test`), sphinx (`tox`), and other non-pytest repos instead of defaulting to `python -m pytest`
- **Flaky Azure and trial mode tests**: Fixed tests that depended on local `~/.ssh/mcpbr_azure` state and updated assertions for multi-step dependency installation
- **SEO improvements** for documentation site
  - Added robots.txt with sitemap reference
  - Added Open Graph and Twitter Card meta tags on all pages
  - Added per-page meta descriptions from frontmatter across all doc pages
  - Updated site description to reflect all 25+ benchmarks (was SWE-bench only)
  - Fixed SoftwareApplication schema version (was 0.1.0, now 0.4.5)
  - Updated SoftwareApplication schema description to cover full benchmark suite

### Documentation

- **Comprehensive benchmark documentation** with individual tutorial pages for all 25+ benchmarks
  - Each benchmark has a dedicated page with overview, task structure, CLI/YAML usage, evaluation methodology, examples, troubleshooting, and best practices
  - Benchmarks organized by category: Software Engineering, Code Generation, Math & Reasoning, Knowledge & QA, Tool Use & Agents, ML Research, Code Understanding, Security
  - New benchmarks overview page with master comparison table and category navigation
  - HowTo JSON-LD structured data for SEO on benchmark pages
  - Updated README with complete benchmark category table
  - Fixed internal links across FAQ, configuration, CLI, and best practices docs
  - **Code generation**: MBPP, APPS, CodeContests, BigCodeBench, LeetCode, CoderEval
  - **Math/reasoning**: MATH, BigBench-Hard
  - **Knowledge/QA**: TruthfulQA, HellaSwag, ARC
  - **Agent/interactive**: GAIA, AgentBench, WebArena, TerminalBench, MLAgentBench, InterCode
  - **Tool-use**: ToolBench
  - **Code editing**: Aider Polyglot
  - **Repository understanding**: RepoQA
  - All benchmarks implement the full `Benchmark` protocol with `load_tasks`, `normalize_task`, `create_environment`, `evaluate`, `get_prebuilt_image`, and `get_prompt_template`

## [0.4.4] - 2026-02-01

### Added

- **Azure Infrastructure Provider** (#351, #356): Run evaluations on Azure VMs instead of local Docker
  - Automatic VM provisioning with configurable CPU, memory, and disk
  - SSH connectivity with key management
  - Remote dependency installation (Docker, Python, mcpbr)
  - Configuration transfer and environment variable export
  - Test task validation before full evaluation
  - Artifact collection with ZIP archiving
  - Auto-cleanup with configurable preservation on error
  - Comprehensive health checks (Azure CLI, authentication, quotas)
  - Abstract `InfrastructureProvider` base class for future providers
  - `InfrastructureManager` factory with full lifecycle orchestration
  - Custom exceptions (`UnknownInfrastructureModeError`, `InfrastructureHealthCheckError`)
  - New config fields: `infrastructure.mode` (`local`/`azure`), `infrastructure.azure.*`
  - Full backward compatibility when `infrastructure` field is omitted

### Fixed

- **Django test runner support** (#93): Detect Django test format and use `./tests/runtests.py` instead of pytest
  - Django tasks in SWE-bench previously had 0% success rate due to wrong test runner
  - Detects both parenthesized format (`test_method (module.tests.TestClass)`) and dot-separated format (`module.tests.TestClass.test_method`)

## [0.4.3] - 2026-02-01

### Added

- **Side-by-Side MCP Server Comparison** (#350): A/B test two MCP servers in a single evaluation run
  - New `comparison_mode` flag enables dual-server evaluation
  - Configure servers with `mcp_server_a` and `mcp_server_b` fields
  - Results show side-by-side comparison with delta metrics and improvement percentages
  - Per-task comparison showing which server won each task
  - Unique wins analysis (tasks where only one server succeeded)
  - Full backward compatibility with single-server mode
  - Comprehensive documentation in `docs/comparison-mode.md`
- **GSM8K Benchmark** (#306): Math reasoning evaluation support
  - Evaluate LLM math reasoning on Grade School Math 8K dataset
  - 1,319 test problems covering arithmetic, algebra, and multi-step reasoning
  - Automatic answer extraction from multiple formats (GSM8K, LaTeX, natural language)
  - Configurable tolerance for numeric comparison
  - Chain-of-thought prompting support
  - Comprehensive documentation in `docs/benchmarks.md`

### Fixed

- **Docker Environment Robustness** (#337, #339, #342, #341): Multiple improvements to Docker-based evaluation
  - Git installation: Automatically install git in containers that don't have it (#337)
  - Fallback images: Handle missing pre-built images gracefully with build-from-scratch fallback (#339)
  - Retry logic: Retry Docker operations on transient failures with exponential backoff (#342)
  - Cleanup: Ensure temp files are cleaned up on all exit paths (#341)
- **Error Handling** (#343, #344): Improved error messages and resilience
  - Parse errors: Better handling of malformed JSON responses from agents (#343)
  - Error messages: More detailed error context including log paths and suggestions (#344)
- **Health Check Tests**: Fixed 3 failing tests by using `sys.executable` instead of `python` command
  - Issue: `python` command doesn't exist on many modern systems (only `python3`)
  - Tests now use the actual Python interpreter being used by pytest
- **Comparison Mode Integration**: Fixed state tracker and preflight checks for comparison mode
  - State tracker now computes correct config hash when using mcp_server_a/b
  - Preflight checks now validate both servers in comparison mode
  - Fixes AttributeError when running side-by-side evaluations
- **GSM8K Configuration**: Added gsm8k to VALID_BENCHMARKS list
  - Benchmark validation now accepts gsm8k as a valid benchmark option
  - Updated field description to include gsm8k and humaneval
- **GSM8K Compatibility**: Added filter parameters to GSM8K load_tasks signature
  - Added filter_difficulty, filter_category, filter_tags for compatibility
  - Parameters unused for GSM8K but needed for benchmark interface consistency
  - Fixes TypeError when running GSM8K evaluations

### Infrastructure

- Refactored release workflow to auto-bump version after GitHub UI release
  - Removed automated release creation workflow (releases now created manually in GitHub UI)
  - Restored Release Drafter for auto-generating draft releases from PRs
  - Added post-release workflow that automatically bumps patch version on main after release publish

## [0.4.2] - 2026-01-29

### Documentation

- Added npm package links throughout documentation and README
- Added thinking_budget configuration documentation with examples and validation notes
- Fixed incorrect CLI override documentation (thinking_budget is YAML-only, no CLI flag exists)
- Added npm badge and installation section to docs

## [0.4.1] - 2026-01-29

### Added

- **HumanEval Benchmark** (#304): Code generation benchmark support
  - Evaluate LLM code generation capabilities on HumanEval dataset
  - Test function implementations against unit test suites
  - Automatic solution extraction and evaluation
- **Extended Thinking Mode** (#332): Support for Claude's extended thinking
  - `thinking_budget` configuration option (1024-31999 tokens)
  - Enables deeper reasoning for complex tasks
  - Validation with clear error messages for invalid values
  - Environment variable injection for both Docker and local execution
- **Performance Profiling** (#331): Comprehensive profiling infrastructure
  - Track tool call latencies with percentiles (p50, p95, p99)
  - Memory usage monitoring (peak and average RSS/VMS)
  - Infrastructure overhead measurement (Docker, MCP startup)
  - Automated insights generation from profiling data
  - Enable with `--profile` flag or `enable_profiling` config
- **Benchmark Filtering** (#305): Filter tasks by difficulty, category, and tags
  - `filter_difficulty` - Filter by task difficulty level
  - `filter_category` - Filter by task category
  - `filter_tags` - Filter by custom tags (all must match)
  - CLI flags: `--filter-difficulty`, `--filter-category`, `--filter-tags`
- **Runtime Tracking** (#326): Track task execution duration
  - Records total runtime for each task evaluation
  - Helps identify performance bottlenecks
  - Included in profiling reports

### Fixed

- **HumanEval Git Detection** (#335): Fixed git diff not detecting newly created files
  - Added fallback to unfiltered git diff when filtered diff is empty
  - Resolves issue where `solution.py` wasn't detected in HumanEval tasks
  - Applied same pattern to both Docker and local execution paths
- **Cost Calculation** (#330): Use total_cost_usd from API to include cache tokens
  - Accurate cost tracking including prompt caching discounts
  - Prevents underreporting of actual API costs

## [0.4.0] - 2026-01-28

### Added

- **MCP Server Log Capture** (#287): Comprehensive logging for MCP server debugging
  - Automatic capture of MCP server stdout/stderr to `~/.mcpbr_state/logs/{instance_id}_mcp.log`
  - MCP log path included in all error messages for easy access
  - Real-time log writing during task execution for troubleshooting
  - Proper cleanup in finally block to ensure logs are always saved
- **Separate MCP Registration Phase** (#285): Better error visibility for MCP initialization
  - MCP server registration now separate from Claude CLI execution with its own 60s timeout
  - Detailed logging showing exact MCP registration command and arguments
  - Clear success/failure messages for MCP server startup
  - Early detection of MCP server initialization issues
- **MCP Timeout Configuration** (#286): Configurable timeouts for MCP servers
  - `startup_timeout_ms` field for MCP server startup (default: 60 seconds)
  - `tool_timeout_ms` field for long-running MCP tool calls (default: 15 minutes)
  - Environment variables passed to Claude CLI for timeout configuration
  - Documented recommended timeouts for different server types
- **Integration Tests** (#286): Comprehensive test coverage for MCP logging features
  - Tests for log file creation and cleanup
  - Tests for error message formatting with log paths
  - Tests for stdout/stderr capture in error messages
  - Tests for timeout handling and temp file cleanup

### Changed

- **Improved Error Messages** (#285, #286): Much more detailed MCP-related error reporting
  - Registration failures now show exact command, exit code, and stderr
  - MCP stdout included in error messages for better diagnostics
  - Timeouts distinguish between init timeout vs execution timeout
  - 0-iteration failures include hint to check MCP server logs
  - All MCP errors include log file path for debugging
- **Better Resource Cleanup** (#286): Temp files cleaned up on all exit paths
  - API keys in env files cleaned up before early returns
  - Cleanup happens on registration failure, timeout, and normal exit
  - Cleanup errors logged when verbose mode enabled
- **Documentation** (#286): Added comprehensive MCP debugging section
  - MCP server log location and access instructions
  - MCP tool timeout configuration examples
  - Recommended timeout values by server type
  - Registration failure troubleshooting steps
  - Examples of new error message formats
  - `startup_timeout_ms` and `tool_timeout_ms` configuration examples

### Security

- **Shell Injection Prevention** (#286): All MCP commands properly escaped
  - All MCP command arguments now quoted with `shlex.quote()`
  - Environment variable values safely escaped
  - Handles spaces and special characters correctly in paths
  - Path traversal prevention in MCP log filenames

### Fixed

- **Resource Leaks** (#286): Fixed temp file leaks on MCP registration failure
  - Temp files containing `ANTHROPIC_API_KEY` now cleaned up before early returns
  - Fixed cleanup bypass in registration failure and timeout paths
- **Unused Variables** (#286): Fixed RUF059 lint warnings
  - `mcp_stdout` now used in error messages instead of discarded

## [0.3.29] - 2026-01-26

### Added

- **XML Output Format** (#301): Convert results to XML format with `mcpbr export xml` (closes #13)
  - XML export for results data
  - Easy integration with XML-based tools
- **One-Liner Install** (#302): Simplified installation with auto-init
  - `curl -sSL https://raw.githubusercontent.com/greynewell/mcpbr/main/install.sh | bash`
  - Automatically installs and runs quick test
  - Improved onboarding experience

### Documentation

- Expanded Claude Code plugin installation options with multiple methods (#275)

## [0.3.28] - 2026-01-26

### Added

- **Default Logging** (#295): Detailed execution logs enabled by default
  - Logs automatically saved to `output_dir/logs/` to prevent data loss
  - Critical for expensive evaluation runs ($50+)
  - Add `--disable-logs` or `disable_logs: true` to opt-out
- **Consolidated Output Directory** (#296): All outputs in single timestamped directory
  - Default: `.mcpbr_run_YYYYMMDD_HHMMSS/`
  - Contains: config.yaml, evaluation_state.json, logs/, README.txt
  - Easy archiving: `tar -czf results.tar.gz .mcpbr_run_*`
  - Customizable with `--output-dir` flag or `output_dir` config option

### Fixed

- Fixed timeout statistics calculation bug

## [0.3.27] - 2026-01-24

### Fixed

- **TypeError in Log Formatter** (#294): Fixed Read tool offset/limit parameter handling
  - Changed defaults from empty string to None
  - Added proper type conversion before arithmetic operations
  - Resolves intermittent failures affecting ~5-7% of SWE-bench tasks
  - Added comprehensive regression tests

## [0.3.26] - 2026-01-23

### Added

- **MCP Observability** (#292): Enhanced logging and error reporting for MCP servers
  - Better visibility into MCP server behavior
  - Improved error messages for debugging
- **MCP Pre-Flight Health Checks** (#293): Validate MCP server before evaluation
  - Early detection of MCP server issues
  - Prevent wasted evaluation time on misconfigured servers

## [0.3.25] - 2026-01-23

### Infrastructure

- Testing automated release workflow

## [0.3.24] - 2026-01-23

### Added

- **Automated Release Workflow**: One-command releases via GitHub Actions
  - Command: `gh workflow run release.yml -f version_bump=patch`
  - Automatic version syncing across all package files
  - Integrated with PyPI and npm publication
  - New [Release Guide](docs/RELEASE.md) and [AI Agent Guide](docs/AI_AGENT_GUIDE.md)

### Fixed

- **Docker TypeError** (#290): Convert instance_id to string in Docker labels
  - Prevents TypeError when instance_id is not a string
  - Improves Docker label handling robustness

### Documentation

- Added release documentation links to README

## [0.3.23] - 2026-01-23

### Added

- **Comprehensive MCP Initialization Logging** (#286): Better error handling and logging
  - Detailed logging for MCP server initialization
  - Enhanced error messages for troubleshooting
  - Improved timeout handling

### Infrastructure

- Fixed version sync across all package files

## [0.3.22] - 2026-01-22

### Fixed

- npm package now correctly includes README.md (removed NPM.md experiment)
  - Previous attempt to use separate NPM.md did not work
  - Package now displays main README on npm registry

## [0.3.21] - 2026-01-22

### Changed

- **npm Package Documentation**: Attempted to use NPM.md for npm-specific docs
  - Configured npm package to display NPM.md on registry
  - Added npm installation instructions to README quick-start
  - Added dedicated npm installation section before pip instructions

## [0.3.20] - 2026-01-22

### Infrastructure

- **npm Publishing**: Updated unscoped CLI package name to `mcpbr-cli`
  - Unscoped CLI package is now `mcpbr-cli` (command is still `mcpbr`)
  - Scoped package remains `@greynewell/mcpbr`
  - Plugin packages remain `mcpbr-claude-plugin` (unscoped) and `@greynewell/mcpbr-claude-plugin` (scoped)
  - Updated documentation to reflect new package names
  - All packages provide the same CLI command: `mcpbr`

## [0.3.19] - 2026-01-22

### Changed

- **Documentation**: Updated all documentation to prefer unscoped npm package names
  - Primary installation method now uses `mcpbr-cli` instead of `@greynewell/mcpbr`
  - Plugin installation now uses `mcpbr-claude-plugin` instead of `@greynewell/mcpbr-claude-plugin`
  - Scoped versions still available and mentioned as alternatives
  - Updated NPM.md, .claude-plugin/README.md with new package references

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
  - **Scoped packages**:
    - `@greynewell/mcpbr` - CLI wrapper for cross-platform installation
    - `@greynewell/mcpbr-claude-plugin` - Claude Code plugin package
  - **Unscoped packages** (same content, easier names):
    - `mcpbr` - CLI wrapper for cross-platform installation
    - `mcpbr-claude-plugin` - Claude Code plugin package
  - Automated publishing workflow on GitHub releases
  - Cross-publishes to both scoped and unscoped names for maximum discoverability

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
  - New [Benchmarks Guide](https://mcpbr.org/benchmarks/) page
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

[0.12.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.12.0
[0.5.5]: https://github.com/greynewell/mcpbr/releases/tag/v0.5.5
[0.4.4]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.4
[0.4.3]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.3
[0.4.2]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.2
[0.4.1]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.1
[0.4.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.0
[0.3.29]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.29
[0.3.28]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.28
[0.3.27]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.27
[0.3.26]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.26
[0.3.25]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.25
[0.3.24]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.24
[0.3.23]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.23
[0.3.22]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.22
[0.3.21]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.21
[0.3.20]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.20
[0.3.19]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.19
[0.3.18]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.18
[0.3.17]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.17
[0.3.16]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.16
[0.3.15]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.15
[0.3.14]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.14
[0.3.13]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.13
[0.3.12]: https://github.com/greynewell/mcpbr/releases/tag/v0.3.12
[0.7.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.7.0
[0.6.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.6.0
[0.5.0]: https://github.com/greynewell/mcpbr/releases/tag/v0.5.0
[0.4.16]: https://github.com/greynewell/mcpbr/releases/tag/v0.4.16
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
