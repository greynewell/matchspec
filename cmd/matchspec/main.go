package main

import (
	"fmt"
	"os"

	"github.com/greynewell/mist-go/cli"
)

func main() {
	app := cli.NewApp("matchspec", "0.1.0")

	eval := &cli.Command{
		Name:  "eval",
		Usage: "Run an evaluation suite",
	}
	eval.AddStringFlag("suite", "", "Suite name to evaluate")
	eval.AddStringFlag("config", "matchspec.yaml", "Config file path")
	eval.AddIntFlag("samples", 0, "Limit number of samples (0 = all)")
	eval.Run = func(cmd *cli.Command, args []string) error {
		suite := cmd.GetString("suite")
		if suite == "" {
			return fmt.Errorf("--suite is required")
		}
		fmt.Printf("Running suite %q with config=%s\n", suite, cmd.GetString("config"))
		return nil
	}
	app.AddCommand(eval)

	serve := &cli.Command{
		Name:  "serve",
		Usage: "Start the matchspec HTTP server",
	}
	serve.AddStringFlag("addr", ":8080", "Listen address")
	serve.Run = func(cmd *cli.Command, args []string) error {
		fmt.Printf("matchspec server listening on %s\n", cmd.GetString("addr"))
		return nil
	}
	app.AddCommand(serve)

	if err := app.Execute(os.Args[1:]); err != nil {
		os.Exit(1)
	}
}
