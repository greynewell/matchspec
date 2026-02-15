package matchspec

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/greynewell/mist-go/protocol"
	"github.com/greynewell/mist-go/tokentrace"
	"github.com/greynewell/mist-go/trace"
)

// InferFunc is a function that performs inference for evaluation.
// It takes a prompt and returns the model's response.
type InferFunc func(ctx context.Context, prompt string) (string, error)

// Runner executes evaluation suites and collects results.
type Runner struct {
	registry *SuiteRegistry
	infer    InferFunc
	reporter *tokentrace.Reporter

	mu      sync.Mutex
	results []protocol.EvalResult
}

// NewRunner creates a runner with the given suite registry and inference function.
func NewRunner(registry *SuiteRegistry, infer InferFunc, reporter *tokentrace.Reporter) *Runner {
	return &Runner{
		registry: registry,
		infer:    infer,
		reporter: reporter,
	}
}

// Run executes all tasks in the named suite and returns the results.
func (r *Runner) Run(ctx context.Context, run protocol.EvalRun) ([]protocol.EvalResult, error) {
	suite, ok := r.registry.Get(run.Suite)
	if !ok {
		return nil, fmt.Errorf("matchspec: unknown suite %q", run.Suite)
	}

	ctx, span := trace.Start(ctx, "matchspec.eval")
	span.SetAttr("suite", run.Suite)

	var results []protocol.EvalResult
	var passed, failed int

	tasks := suite.Tasks
	if len(run.Tasks) > 0 {
		tasks = filterTasks(suite.Tasks, run.Tasks)
	}

	for _, task := range tasks {
		result := r.runTask(ctx, suite.Name, task)
		results = append(results, result)
		if result.Passed {
			passed++
		} else {
			failed++
		}
	}

	span.SetAttr("passed", passed)
	span.SetAttr("failed", failed)
	span.SetAttr("total", len(results))
	if failed > 0 {
		span.End("error")
	} else {
		span.End("ok")
	}
	r.reporter.Report(ctx, span)

	r.mu.Lock()
	r.results = append(r.results, results...)
	r.mu.Unlock()

	return results, nil
}

func (r *Runner) runTask(ctx context.Context, suite string, task Task) protocol.EvalResult {
	ctx, span := trace.Start(ctx, "matchspec.task")
	span.SetAttr("suite", suite)
	span.SetAttr("task", task.Name)

	start := time.Now()
	response, err := r.infer(ctx, task.Prompt)
	duration := time.Since(start)

	if err != nil {
		span.SetAttr("error", err.Error())
		span.End("error")
		r.reporter.Report(ctx, span)
		return protocol.EvalResult{
			Suite:      suite,
			Task:       task.Name,
			Passed:     false,
			Score:      0,
			DurationMS: duration.Milliseconds(),
			Error:      err.Error(),
		}
	}

	passed, score := task.Match(response)
	status := "ok"
	if !passed {
		status = "error"
	}

	span.SetAttr("passed", passed)
	span.SetAttr("score", score)
	span.End(status)
	r.reporter.Report(ctx, span)

	return protocol.EvalResult{
		Suite:      suite,
		Task:       task.Name,
		Passed:     passed,
		Score:      score,
		DurationMS: duration.Milliseconds(),
	}
}

// Results returns all collected evaluation results.
func (r *Runner) Results() []protocol.EvalResult {
	r.mu.Lock()
	defer r.mu.Unlock()
	cp := make([]protocol.EvalResult, len(r.results))
	copy(cp, r.results)
	return cp
}

// ResultsBySuite returns results filtered by suite name.
func (r *Runner) ResultsBySuite(suite string) []protocol.EvalResult {
	r.mu.Lock()
	defer r.mu.Unlock()
	var filtered []protocol.EvalResult
	for _, res := range r.results {
		if res.Suite == suite {
			filtered = append(filtered, res)
		}
	}
	return filtered
}

func filterTasks(all []Task, names []string) []Task {
	nameSet := make(map[string]bool, len(names))
	for _, n := range names {
		nameSet[n] = true
	}
	var filtered []Task
	for _, t := range all {
		if nameSet[t.Name] {
			filtered = append(filtered, t)
		}
	}
	return filtered
}
