package cli

import (
	"bytes"
	"strings"
	"testing"
)

func TestNewAppHasVersionCommand(t *testing.T) {
	app := NewApp("test", "1.0.0")
	if _, ok := app.commands["version"]; !ok {
		t.Error("expected built-in version command")
	}
}

func TestAddCommand(t *testing.T) {
	app := NewApp("test", "1.0.0")
	app.AddCommand(&Command{
		Name:  "greet",
		Usage: "Say hello",
		Run:   func(_ *Command, _ []string) error { return nil },
	})

	if _, ok := app.commands["greet"]; !ok {
		t.Error("expected greet command")
	}
}

func TestExecuteUnknownCommand(t *testing.T) {
	app := NewApp("test", "1.0.0")
	app.out = &bytes.Buffer{}

	err := app.Execute([]string{"nope"})
	if err == nil {
		t.Fatal("expected error for unknown command")
	}
	if !strings.Contains(err.Error(), "unknown command") {
		t.Errorf("expected 'unknown command' in error, got %q", err)
	}
}

func TestExecuteNoArgs(t *testing.T) {
	app := NewApp("test", "1.0.0")
	app.out = &bytes.Buffer{}

	err := app.Execute(nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestExecuteHelp(t *testing.T) {
	app := NewApp("test", "1.0.0")
	var buf bytes.Buffer
	app.out = &buf

	for _, arg := range []string{"help", "-h", "--help"} {
		buf.Reset()
		err := app.Execute([]string{arg})
		if err != nil {
			t.Fatalf("Execute(%q): %v", arg, err)
		}
		if !strings.Contains(buf.String(), "Commands:") {
			t.Errorf("help for %q should contain 'Commands:'", arg)
		}
	}
}

func TestExecuteRunsCommand(t *testing.T) {
	app := NewApp("test", "1.0.0")
	var ran bool

	app.AddCommand(&Command{
		Name:  "run",
		Usage: "Run something",
		Run: func(_ *Command, _ []string) error {
			ran = true
			return nil
		},
	})

	err := app.Execute([]string{"run"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ran {
		t.Error("expected command to run")
	}
}

func TestExecutePassesArgs(t *testing.T) {
	app := NewApp("test", "1.0.0")
	var got []string

	app.AddCommand(&Command{
		Name:  "echo",
		Usage: "Echo args",
		Run: func(_ *Command, args []string) error {
			got = args
			return nil
		},
	})

	err := app.Execute([]string{"echo", "hello", "world"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 || got[0] != "hello" || got[1] != "world" {
		t.Errorf("got args %v, want [hello world]", got)
	}
}

func TestAddCommandCreatesDefaultFlagSet(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "noflag",
		Usage: "No flags",
		Run:   func(_ *Command, _ []string) error { return nil },
	}
	app.AddCommand(cmd)

	if cmd.Flags == nil {
		t.Error("expected default FlagSet to be created")
	}
}

// Flag definition and access tests

func TestAddStringFlag(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "serve",
		Usage: "Start server",
	}
	cmd.AddStringFlag("addr", ":8080", "Listen address")
	cmd.AddStringFlag("config", "", "Config path")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetString("addr") != ":9090" {
			t.Errorf("addr = %s, want :9090", cmd.GetString("addr"))
		}
		if cmd.GetString("config") != "/etc/app.toml" {
			t.Errorf("config = %s, want /etc/app.toml", cmd.GetString("config"))
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"serve", "-addr", ":9090", "-config", "/etc/app.toml"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddIntFlag(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "serve",
		Usage: "Start server",
	}
	cmd.AddIntFlag("workers", 4, "Number of workers")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetInt("workers") != 8 {
			t.Errorf("workers = %d, want 8", cmd.GetInt("workers"))
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"serve", "-workers", "8"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddInt64Flag(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "run",
		Usage: "Run",
	}
	cmd.AddInt64Flag("max-bytes", 1024, "Max bytes")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetInt64("max-bytes") != 2048 {
			t.Errorf("max-bytes = %d, want 2048", cmd.GetInt64("max-bytes"))
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"run", "-max-bytes", "2048"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddFloat64Flag(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "run",
		Usage: "Run",
	}
	cmd.AddFloat64Flag("rate", 1.0, "Rate limit")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetFloat64("rate") != 0.5 {
			t.Errorf("rate = %f, want 0.5", cmd.GetFloat64("rate"))
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"run", "-rate", "0.5"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddBoolFlag(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "run",
		Usage: "Run",
	}
	cmd.AddBoolFlag("verbose", false, "Verbose output")
	cmd.Run = func(cmd *Command, args []string) error {
		if !cmd.GetBool("verbose") {
			t.Error("verbose should be true")
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"run", "-verbose"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestFlagDefaults(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "run",
		Usage: "Run",
	}
	cmd.AddStringFlag("name", "default-name", "Name")
	cmd.AddIntFlag("port", 8080, "Port")
	cmd.AddFloat64Flag("rate", 1.5, "Rate")
	cmd.AddBoolFlag("debug", false, "Debug")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetString("name") != "default-name" {
			t.Errorf("name = %s, want default-name", cmd.GetString("name"))
		}
		if cmd.GetInt("port") != 8080 {
			t.Errorf("port = %d, want 8080", cmd.GetInt("port"))
		}
		if cmd.GetFloat64("rate") != 1.5 {
			t.Errorf("rate = %f, want 1.5", cmd.GetFloat64("rate"))
		}
		if cmd.GetBool("debug") {
			t.Error("debug should be false by default")
		}
		return nil
	}
	app.AddCommand(cmd)

	// Execute without any flags — should use defaults.
	err := app.Execute([]string{"run"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestGetUndefinedFlag(t *testing.T) {
	cmd := &Command{
		Name: "test",
		Run:  func(_ *Command, _ []string) error { return nil },
	}
	cmd.initFlags()

	if cmd.GetString("nope") != "" {
		t.Error("undefined string flag should return empty")
	}
	if cmd.GetInt("nope") != 0 {
		t.Error("undefined int flag should return 0")
	}
	if cmd.GetInt64("nope") != 0 {
		t.Error("undefined int64 flag should return 0")
	}
	if cmd.GetFloat64("nope") != 0 {
		t.Error("undefined float64 flag should return 0")
	}
	if cmd.GetBool("nope") {
		t.Error("undefined bool flag should return false")
	}
}

func TestHasFlag(t *testing.T) {
	cmd := &Command{Name: "test"}
	cmd.AddStringFlag("addr", "", "Address")

	if !cmd.HasFlag("addr") {
		t.Error("should have addr flag")
	}
	if cmd.HasFlag("nope") {
		t.Error("should not have nope flag")
	}
}

func TestFlagsWithPositionalArgs(t *testing.T) {
	app := NewApp("test", "1.0.0")
	cmd := &Command{
		Name:  "run",
		Usage: "Run",
	}
	cmd.AddStringFlag("format", "json", "Output format")
	cmd.Run = func(cmd *Command, args []string) error {
		if cmd.GetString("format") != "table" {
			t.Errorf("format = %s, want table", cmd.GetString("format"))
		}
		if len(args) != 2 || args[0] != "file1" || args[1] != "file2" {
			t.Errorf("args = %v, want [file1 file2]", args)
		}
		return nil
	}
	app.AddCommand(cmd)

	err := app.Execute([]string{"run", "-format", "table", "file1", "file2"})
	if err != nil {
		t.Fatal(err)
	}
}

// Per-command help tests

func TestCommandHelp(t *testing.T) {
	app := NewApp("myapp", "1.0.0")
	var buf bytes.Buffer
	app.out = &buf

	cmd := &Command{
		Name:  "serve",
		Usage: "Start the server",
	}
	cmd.AddStringFlag("addr", ":8080", "Listen address")
	cmd.AddIntFlag("workers", 4, "Number of workers")
	cmd.Run = func(_ *Command, _ []string) error { return nil }
	app.AddCommand(cmd)

	// Parse --help triggers the Usage function which writes to app.out.
	app.Execute([]string{"serve", "--help"})

	help := buf.String()
	if !strings.Contains(help, "myapp serve") {
		t.Errorf("help should contain 'myapp serve', got:\n%s", help)
	}
	if !strings.Contains(help, "Start the server") {
		t.Errorf("help should contain usage text, got:\n%s", help)
	}
	if !strings.Contains(help, "-addr") {
		t.Errorf("help should list -addr flag, got:\n%s", help)
	}
	if !strings.Contains(help, "-workers") {
		t.Errorf("help should list -workers flag, got:\n%s", help)
	}
}

func TestAppHelpShowsHint(t *testing.T) {
	app := NewApp("myapp", "1.0.0")
	var buf bytes.Buffer
	app.out = &buf

	app.AddCommand(&Command{
		Name:  "serve",
		Usage: "Start the server",
		Run:   func(_ *Command, _ []string) error { return nil },
	})

	app.Execute([]string{"--help"})

	help := buf.String()
	if !strings.Contains(help, "--help") {
		t.Errorf("app help should mention per-command --help, got:\n%s", help)
	}
}

func TestMultipleCommandsWithFlags(t *testing.T) {
	app := NewApp("test", "1.0.0")

	serve := &Command{Name: "serve", Usage: "Start server"}
	serve.AddStringFlag("addr", ":8080", "Listen address")
	serve.Run = func(cmd *Command, args []string) error {
		if cmd.GetString("addr") != ":9090" {
			t.Errorf("serve addr = %s, want :9090", cmd.GetString("addr"))
		}
		return nil
	}

	query := &Command{Name: "query", Usage: "Query data"}
	query.AddStringFlag("url", "http://localhost:8080", "Server URL")
	query.AddStringFlag("format", "json", "Output format")
	query.Run = func(cmd *Command, args []string) error {
		if cmd.GetString("format") != "table" {
			t.Errorf("query format = %s, want table", cmd.GetString("format"))
		}
		return nil
	}

	app.AddCommand(serve)
	app.AddCommand(query)

	// Each command's flags are isolated.
	if err := app.Execute([]string{"serve", "-addr", ":9090"}); err != nil {
		t.Fatal(err)
	}
	if err := app.Execute([]string{"query", "-format", "table"}); err != nil {
		t.Fatal(err)
	}
}

func TestCommandInitFlagsIdempotent(t *testing.T) {
	cmd := &Command{Name: "test"}
	cmd.initFlags()
	fs := cmd.Flags
	cmd.initFlags()
	if cmd.Flags != fs {
		t.Error("initFlags should not replace existing FlagSet")
	}
}
