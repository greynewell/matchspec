// Package matchspec implements the MatchSpec evaluation framework for the
// MIST stack. It runs benchmark suites against LLM outputs, compares results
// to baselines, and reports trace spans to TokenTrace.
package matchspec

import (
	"fmt"
	"strings"
)

// Suite defines an evaluation benchmark suite.
type Suite struct {
	Name  string `json:"name"`
	Tasks []Task `json:"tasks"`
}

// Task is a single evaluation task within a suite.
type Task struct {
	Name     string `json:"name"`
	Prompt   string `json:"prompt"`
	Expected string `json:"expected"`

	// Matcher determines how Expected is compared to the response.
	// "exact", "contains", "prefix", "suffix"
	Matcher string `json:"matcher"`
}

// Match evaluates whether a response satisfies this task's expected output.
func (t *Task) Match(response string) (bool, float64) {
	switch t.Matcher {
	case "exact":
		if response == t.Expected {
			return true, 1.0
		}
		return false, 0.0
	case "contains":
		if strings.Contains(response, t.Expected) {
			return true, 1.0
		}
		return false, 0.0
	case "prefix":
		if strings.HasPrefix(response, t.Expected) {
			return true, 1.0
		}
		return false, 0.0
	case "suffix":
		if strings.HasSuffix(response, t.Expected) {
			return true, 1.0
		}
		return false, 0.0
	default:
		// Default to contains match.
		if strings.Contains(response, t.Expected) {
			return true, 1.0
		}
		return false, 0.0
	}
}

// Validate checks that the suite is well-formed.
func (s *Suite) Validate() error {
	if s.Name == "" {
		return fmt.Errorf("matchspec: suite name is required")
	}
	if len(s.Tasks) == 0 {
		return fmt.Errorf("matchspec: suite %q has no tasks", s.Name)
	}
	for i, t := range s.Tasks {
		if t.Name == "" {
			return fmt.Errorf("matchspec: suite %q task[%d] has no name", s.Name, i)
		}
		if t.Prompt == "" {
			return fmt.Errorf("matchspec: suite %q task %q has no prompt", s.Name, t.Name)
		}
	}
	return nil
}

// SuiteRegistry holds named evaluation suites.
type SuiteRegistry struct {
	suites map[string]*Suite
}

// NewSuiteRegistry creates an empty suite registry.
func NewSuiteRegistry() *SuiteRegistry {
	return &SuiteRegistry{suites: make(map[string]*Suite)}
}

// Register adds a suite to the registry.
func (r *SuiteRegistry) Register(s *Suite) error {
	if err := s.Validate(); err != nil {
		return err
	}
	r.suites[s.Name] = s
	return nil
}

// Get returns a suite by name.
func (r *SuiteRegistry) Get(name string) (*Suite, bool) {
	s, ok := r.suites[name]
	return s, ok
}

// Names returns all registered suite names.
func (r *SuiteRegistry) Names() []string {
	names := make([]string, 0, len(r.suites))
	for name := range r.suites {
		names = append(names, name)
	}
	return names
}
