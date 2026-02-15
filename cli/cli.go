// Package cli provides a zero-dependency subcommand framework shared
// across all MIST stack tools.
//
// Each command gets its own flag set. Define flags on the command, then
// access parsed values in the Run handler:
//
//	cmd := &cli.Command{
//	    Name:  "serve",
//	    Usage: "Start the server",
//	}
//	cmd.AddStringFlag("addr", ":8080", "Listen address")
//	cmd.AddIntFlag("workers", 4, "Number of workers")
//	cmd.Run = func(cmd *cli.Command, args []string) error {
//	    addr := cmd.GetString("addr")
//	    workers := cmd.GetInt("workers")
//	    // ...
//	}
//	app.AddCommand(cmd)
package cli

import (
	"flag"
	"fmt"
	"io"
	"os"
	"sort"
	"text/tabwriter"
)

// App is the top-level CLI application.
type App struct {
	Name     string
	Version  string
	commands map[string]*Command
	order    []string // insertion order for help display
	out      io.Writer
}

// Command is a single CLI subcommand with its own flag set.
type Command struct {
	Name  string
	Usage string
	Flags *flag.FlagSet
	Run   func(cmd *Command, args []string) error

	// Set by App when the command is registered, for help output.
	appName string
}

// NewApp creates an application with the built-in version command.
func NewApp(name, version string) *App {
	a := &App{
		Name:     name,
		Version:  version,
		commands: make(map[string]*Command),
		out:      os.Stderr,
	}
	a.AddCommand(&Command{
		Name:  "version",
		Usage: "Print the version and exit",
		Run: func(_ *Command, _ []string) error {
			fmt.Fprintf(os.Stdout, "%s %s\n", a.Name, a.Version)
			return nil
		},
	})
	return a
}

// AddCommand registers a subcommand.
func (a *App) AddCommand(c *Command) {
	c.initFlags()
	c.appName = a.Name

	// Set custom usage function for per-command help.
	c.Flags.Usage = func() {
		c.printHelp(a.out)
	}

	if _, exists := a.commands[c.Name]; !exists {
		a.order = append(a.order, c.Name)
	}
	a.commands[c.Name] = c
}

// Execute parses the argument list and runs the matching subcommand.
func (a *App) Execute(args []string) error {
	if len(args) == 0 {
		a.printUsage()
		return nil
	}

	name := args[0]
	if name == "-h" || name == "--help" || name == "help" {
		a.printUsage()
		return nil
	}

	cmd, ok := a.commands[name]
	if !ok {
		fmt.Fprintf(a.out, "unknown command: %s\n\n", name)
		a.printUsage()
		return fmt.Errorf("unknown command: %s", name)
	}

	if err := cmd.Flags.Parse(args[1:]); err != nil {
		return err
	}

	return cmd.Run(cmd, cmd.Flags.Args())
}

// --- Flag definition helpers ---

// AddStringFlag defines a string flag on this command.
func (c *Command) AddStringFlag(name, value, usage string) {
	c.initFlags()
	c.Flags.String(name, value, usage)
}

// AddIntFlag defines an integer flag on this command.
func (c *Command) AddIntFlag(name string, value int, usage string) {
	c.initFlags()
	c.Flags.Int(name, value, usage)
}

// AddInt64Flag defines an int64 flag on this command.
func (c *Command) AddInt64Flag(name string, value int64, usage string) {
	c.initFlags()
	c.Flags.Int64(name, value, usage)
}

// AddFloat64Flag defines a float64 flag on this command.
func (c *Command) AddFloat64Flag(name string, value float64, usage string) {
	c.initFlags()
	c.Flags.Float64(name, value, usage)
}

// AddBoolFlag defines a boolean flag on this command.
func (c *Command) AddBoolFlag(name string, value bool, usage string) {
	c.initFlags()
	c.Flags.Bool(name, value, usage)
}

// --- Flag value accessors (call after Parse) ---

// GetString returns the parsed string flag value.
func (c *Command) GetString(name string) string {
	f := c.Flags.Lookup(name)
	if f == nil {
		return ""
	}
	return f.Value.String()
}

// GetInt returns the parsed integer flag value.
func (c *Command) GetInt(name string) int {
	f := c.Flags.Lookup(name)
	if f == nil {
		return 0
	}
	if getter, ok := f.Value.(flag.Getter); ok {
		if v, ok := getter.Get().(int); ok {
			return v
		}
	}
	return 0
}

// GetInt64 returns the parsed int64 flag value.
func (c *Command) GetInt64(name string) int64 {
	f := c.Flags.Lookup(name)
	if f == nil {
		return 0
	}
	if getter, ok := f.Value.(flag.Getter); ok {
		if v, ok := getter.Get().(int64); ok {
			return v
		}
	}
	return 0
}

// GetFloat64 returns the parsed float64 flag value.
func (c *Command) GetFloat64(name string) float64 {
	f := c.Flags.Lookup(name)
	if f == nil {
		return 0
	}
	if getter, ok := f.Value.(flag.Getter); ok {
		if v, ok := getter.Get().(float64); ok {
			return v
		}
	}
	return 0
}

// GetBool returns the parsed boolean flag value.
func (c *Command) GetBool(name string) bool {
	f := c.Flags.Lookup(name)
	if f == nil {
		return false
	}
	if getter, ok := f.Value.(flag.Getter); ok {
		if v, ok := getter.Get().(bool); ok {
			return v
		}
	}
	return false
}

// HasFlag reports whether a flag with the given name is defined.
func (c *Command) HasFlag(name string) bool {
	return c.Flags.Lookup(name) != nil
}

// --- Help output ---

func (c *Command) printHelp(w io.Writer) {
	if c.appName != "" {
		fmt.Fprintf(w, "Usage: %s %s [flags]\n", c.appName, c.Name)
	} else {
		fmt.Fprintf(w, "Usage: %s [flags]\n", c.Name)
	}
	if c.Usage != "" {
		fmt.Fprintf(w, "\n%s\n", c.Usage)
	}

	// Count defined flags.
	hasFlags := false
	c.Flags.VisitAll(func(_ *flag.Flag) { hasFlags = true })

	if hasFlags {
		fmt.Fprintf(w, "\nFlags:\n")
		c.Flags.SetOutput(w)
		c.Flags.PrintDefaults()
	}
}

func (c *Command) initFlags() {
	if c.Flags == nil {
		c.Flags = flag.NewFlagSet(c.Name, flag.ContinueOnError)
	}
}

func (a *App) printUsage() {
	w := tabwriter.NewWriter(a.out, 0, 0, 2, ' ', 0)
	fmt.Fprintf(w, "Usage: %s <command> [flags]\n\n", a.Name)
	fmt.Fprintln(w, "Commands:")

	names := make([]string, len(a.order))
	copy(names, a.order)
	sort.Strings(names)

	for _, name := range names {
		fmt.Fprintf(w, "  %s\t%s\n", name, a.commands[name].Usage)
	}
	fmt.Fprintf(w, "\nRun '%s <command> --help' for command-specific flags.\n", a.Name)
	w.Flush()
}
