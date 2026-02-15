# matchspec

The MIST stack evaluation framework for testing and evaluating AI outputs — MCP servers, AI agents, RL environments, model training, and more. The cornerstone of evaluation-driven development.

[![Go](https://img.shields.io/badge/Go-1.23+-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/greynewell/matchspec/actions/workflows/ci.yml/badge.svg)](https://github.com/greynewell/matchspec/actions/workflows/ci.yml)

## Overview

matchspec provides a zero-dependency CLI framework and evaluation toolkit for the MIST stack. It's designed to be the standard way to test and benchmark AI system outputs across the full stack:

- **MCP servers** — evaluate tool use accuracy and performance
- **AI agents** — benchmark reasoning and task completion
- **RL environments** — measure reward signal quality
- **Model training** — validate fine-tuning outcomes

## Install

```bash
go get github.com/greynewell/matchspec
```

## Usage

matchspec includes a subcommand framework (`cli` package) for building evaluation tools with no external dependencies:

```go
package main

import (
	"fmt"
	"os"

	"github.com/greynewell/matchspec/cli"
)

func main() {
	app := cli.NewApp("matchspec", "0.1.0")

	eval := &cli.Command{
		Name:  "eval",
		Usage: "Run an evaluation suite",
	}
	eval.AddStringFlag("config", "matchspec.yaml", "Config file path")
	eval.AddIntFlag("samples", 10, "Number of samples")
	eval.Run = func(cmd *cli.Command, args []string) error {
		fmt.Printf("Running eval with config=%s samples=%d\n",
			cmd.GetString("config"), cmd.GetInt("samples"))
		return nil
	}
	app.AddCommand(eval)

	if err := app.Execute(os.Args[1:]); err != nil {
		os.Exit(1)
	}
}
```

### CLI Package

The `cli` package provides:

- **Subcommand routing** with automatic help generation
- **Typed flag definitions** (string, int, int64, float64, bool)
- **Per-command flag sets** with isolated parsing
- **Zero dependencies** — only the Go standard library

```bash
matchspec eval --config my-suite.yaml --samples 50
matchspec version
matchspec --help
```

## Development

```bash
# Run tests
go test ./...

# Run with verbose output
go test ./... -v
```

## License

MIT — see [LICENSE](LICENSE) for details.

---

Built by [Grey Newell](https://greynewell.com) | [matchspec.dev](https://matchspec.dev)
