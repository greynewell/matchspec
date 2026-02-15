# matchspec

The MIST stack evaluation framework for testing and evaluating AI outputs — MCP servers, AI agents, RL environments, model training, and more. The cornerstone of evaluation-driven development.

[![Go](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

matchspec runs benchmark suites against AI system outputs, compares results to baselines, and reports trace spans to TokenTrace.

- **Suites** define evaluation tasks with expected outputs
- **Matchers** compare responses: exact, contains, prefix, suffix
- **Runner** executes suites against any inference function
- **HTTP handlers** expose the MIST protocol API

## Install

```bash
go get github.com/greynewell/matchspec
```

## Usage

### Define a suite

```go
reg := matchspec.NewSuiteRegistry()
reg.Register(&matchspec.Suite{
    Name: "math",
    Tasks: []matchspec.Task{
        {Name: "add", Prompt: "What is 1+1?", Expected: "2", Matcher: "contains"},
        {Name: "mul", Prompt: "What is 3*4?", Expected: "12", Matcher: "contains"},
    },
})
```

### Run evaluations

```go
runner := matchspec.NewRunner(reg, inferFunc, reporter)
results, err := runner.Run(ctx, protocol.EvalRun{Suite: "math"})
for _, r := range results {
    fmt.Printf("%s/%s: passed=%v score=%.1f\n", r.Suite, r.Task, r.Passed, r.Score)
}
```

### HTTP API

```go
handler := matchspec.NewHandler(runner, reg)
http.HandleFunc("POST /mist", handler.Ingest)       // MIST protocol
http.HandleFunc("POST /eval", handler.RunDirect)     // Direct eval
http.HandleFunc("GET /suites", handler.Suites)       // List suites
http.HandleFunc("GET /results", handler.Results)     // Get results
```

### CLI

```bash
go run ./cmd/matchspec eval --suite math
go run ./cmd/matchspec serve --addr :8080
go run ./cmd/matchspec version
```

## Part of the MIST stack

| Tool | Purpose |
|------|---------|
| **MatchSpec** | Evaluation framework (this repo) |
| **InferMux** | Inference routing across providers |
| **SchemaFlux** | Structured data compiler |
| **TokenTrace** | Token-level observability |

Shared foundation: [mist-go](https://github.com/greynewell/mist-go)

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built by [Grey Newell](https://greynewell.com) | [matchspec.dev](https://matchspec.dev)
