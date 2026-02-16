# matchspec

Eval framework. Part of the [MIST stack](https://github.com/greynewell/mist-go).

[![Go](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install

```bash
go get github.com/greynewell/matchspec
```

## Define a suite

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

Matchers: `exact`, `contains`, `prefix`, `suffix`.

## Run

```go
runner := matchspec.NewRunner(reg, inferFunc, reporter)
results, err := runner.Run(ctx, protocol.EvalRun{Suite: "math"})
for _, r := range results {
    fmt.Printf("%s/%s: passed=%v score=%.1f\n", r.Suite, r.Task, r.Passed, r.Score)
}
```

## HTTP API

```go
handler := matchspec.NewHandler(runner, reg)
http.HandleFunc("POST /mist", handler.Ingest)
http.HandleFunc("POST /eval", handler.RunDirect)
http.HandleFunc("GET /suites", handler.Suites)
http.HandleFunc("GET /results", handler.Results)
```

## CLI

```bash
matchspec eval --suite math
matchspec serve --addr :8080
```
