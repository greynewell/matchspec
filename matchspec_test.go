package matchspec

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/greynewell/mist-go/protocol"
	"github.com/greynewell/mist-go/tokentrace"
)

// --- Task matching tests ---

func TestTaskMatchExact(t *testing.T) {
	task := Task{Name: "t1", Prompt: "p", Expected: "hello", Matcher: "exact"}
	passed, score := task.Match("hello")
	if !passed || score != 1.0 {
		t.Errorf("exact match failed: passed=%v, score=%f", passed, score)
	}
	passed, _ = task.Match("hello world")
	if passed {
		t.Error("exact match should fail on partial")
	}
}

func TestTaskMatchContains(t *testing.T) {
	task := Task{Name: "t1", Prompt: "p", Expected: "world", Matcher: "contains"}
	passed, _ := task.Match("hello world")
	if !passed {
		t.Error("contains match should succeed")
	}
	passed, _ = task.Match("hello")
	if passed {
		t.Error("contains match should fail")
	}
}

func TestTaskMatchPrefix(t *testing.T) {
	task := Task{Name: "t1", Prompt: "p", Expected: "hello", Matcher: "prefix"}
	passed, _ := task.Match("hello world")
	if !passed {
		t.Error("prefix match should succeed")
	}
	passed, _ = task.Match("world hello")
	if passed {
		t.Error("prefix match should fail")
	}
}

func TestTaskMatchSuffix(t *testing.T) {
	task := Task{Name: "t1", Prompt: "p", Expected: "world", Matcher: "suffix"}
	passed, _ := task.Match("hello world")
	if !passed {
		t.Error("suffix match should succeed")
	}
	passed, _ = task.Match("world hello")
	if passed {
		t.Error("suffix match should fail")
	}
}

func TestTaskMatchDefault(t *testing.T) {
	task := Task{Name: "t1", Prompt: "p", Expected: "42"}
	passed, _ := task.Match("the answer is 42")
	if !passed {
		t.Error("default matcher (contains) should succeed")
	}
}

// --- Suite tests ---

func TestSuiteValidation(t *testing.T) {
	tests := []struct {
		name    string
		suite   Suite
		wantErr bool
	}{
		{"valid", Suite{Name: "math", Tasks: []Task{{Name: "add", Prompt: "1+1"}}}, false},
		{"no name", Suite{Tasks: []Task{{Name: "t", Prompt: "p"}}}, true},
		{"no tasks", Suite{Name: "empty"}, true},
		{"task no name", Suite{Name: "s", Tasks: []Task{{Prompt: "p"}}}, true},
		{"task no prompt", Suite{Name: "s", Tasks: []Task{{Name: "t"}}}, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.suite.Validate()
			if (err != nil) != tt.wantErr {
				t.Errorf("Validate() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// --- Registry tests ---

func TestSuiteRegistryRegisterAndGet(t *testing.T) {
	reg := NewSuiteRegistry()
	err := reg.Register(&Suite{
		Name:  "math",
		Tasks: []Task{{Name: "add", Prompt: "1+1", Expected: "2"}},
	})
	if err != nil {
		t.Fatal(err)
	}

	s, ok := reg.Get("math")
	if !ok {
		t.Fatal("expected to find math suite")
	}
	if len(s.Tasks) != 1 {
		t.Errorf("expected 1 task, got %d", len(s.Tasks))
	}
}

func TestSuiteRegistryNames(t *testing.T) {
	reg := NewSuiteRegistry()
	reg.Register(&Suite{Name: "a", Tasks: []Task{{Name: "t", Prompt: "p"}}})
	reg.Register(&Suite{Name: "b", Tasks: []Task{{Name: "t", Prompt: "p"}}})

	if len(reg.Names()) != 2 {
		t.Errorf("Names = %d, want 2", len(reg.Names()))
	}
}

func TestSuiteRegistryRejectInvalid(t *testing.T) {
	reg := NewSuiteRegistry()
	err := reg.Register(&Suite{Name: ""})
	if err == nil {
		t.Error("expected error for invalid suite")
	}
}

// --- Runner tests ---

func echoInfer(_ context.Context, prompt string) (string, error) {
	return "echo: " + prompt, nil
}

func failInfer(_ context.Context, prompt string) (string, error) {
	return "", fmt.Errorf("inference failed")
}

func testRunner(infer InferFunc) *Runner {
	reg := NewSuiteRegistry()
	reg.Register(&Suite{
		Name: "math",
		Tasks: []Task{
			{Name: "add", Prompt: "1+1", Expected: "echo: 1+1", Matcher: "exact"},
			{Name: "mul", Prompt: "2*3", Expected: "echo: 2*3", Matcher: "exact"},
		},
	})
	reg.Register(&Suite{
		Name: "contains",
		Tasks: []Task{
			{Name: "has-echo", Prompt: "test", Expected: "echo", Matcher: "contains"},
		},
	})

	reporter := tokentrace.NewReporter("matchspec", "")
	return NewRunner(reg, infer, reporter)
}

func TestRunnerRunAllPass(t *testing.T) {
	runner := testRunner(echoInfer)
	results, err := runner.Run(context.Background(), protocol.EvalRun{Suite: "math"})
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	for _, r := range results {
		if !r.Passed {
			t.Errorf("task %s should pass", r.Task)
		}
		if r.Score != 1.0 {
			t.Errorf("task %s score = %f, want 1.0", r.Task, r.Score)
		}
	}
}

func TestRunnerRunFilterTasks(t *testing.T) {
	runner := testRunner(echoInfer)
	results, err := runner.Run(context.Background(), protocol.EvalRun{
		Suite: "math",
		Tasks: []string{"add"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	if results[0].Task != "add" {
		t.Errorf("task = %s, want add", results[0].Task)
	}
}

func TestRunnerRunUnknownSuite(t *testing.T) {
	runner := testRunner(echoInfer)
	_, err := runner.Run(context.Background(), protocol.EvalRun{Suite: "nonexistent"})
	if err == nil {
		t.Error("expected error for unknown suite")
	}
}

func TestRunnerRunInferError(t *testing.T) {
	runner := testRunner(failInfer)
	results, err := runner.Run(context.Background(), protocol.EvalRun{Suite: "math"})
	if err != nil {
		t.Fatal(err)
	}
	for _, r := range results {
		if r.Passed {
			t.Errorf("task %s should fail on inference error", r.Task)
		}
		if r.Error == "" {
			t.Errorf("task %s should have error message", r.Task)
		}
	}
}

func TestRunnerResults(t *testing.T) {
	runner := testRunner(echoInfer)
	runner.Run(context.Background(), protocol.EvalRun{Suite: "math"})
	runner.Run(context.Background(), protocol.EvalRun{Suite: "contains"})

	all := runner.Results()
	if len(all) != 3 {
		t.Errorf("total results = %d, want 3", len(all))
	}

	bySuite := runner.ResultsBySuite("math")
	if len(bySuite) != 2 {
		t.Errorf("math results = %d, want 2", len(bySuite))
	}
}

// --- Handler tests ---

func testRunnerAndRegistry() (*Runner, *SuiteRegistry) {
	reg := NewSuiteRegistry()
	reg.Register(&Suite{
		Name: "math",
		Tasks: []Task{
			{Name: "add", Prompt: "1+1", Expected: "echo: 1+1", Matcher: "exact"},
		},
	})
	reporter := tokentrace.NewReporter("matchspec", "")
	runner := NewRunner(reg, echoInfer, reporter)
	return runner, reg
}

func TestHandlerIngestSuccess(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	msg, _ := protocol.New("test", protocol.TypeEvalRun, protocol.EvalRun{Suite: "math"})
	body, _ := msg.Marshal()

	req := httptest.NewRequest("POST", "/mist", bytes.NewReader(body))
	w := httptest.NewRecorder()
	h.Ingest(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200, body: %s", w.Code, w.Body.String())
	}

	var results []protocol.EvalResult
	if err := json.Unmarshal(w.Body.Bytes(), &results); err != nil {
		t.Fatal(err)
	}
	if len(results) != 1 || !results[0].Passed {
		t.Error("expected 1 passing result")
	}
}

func TestHandlerIngestWrongType(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	msg, _ := protocol.New("test", protocol.TypeHealthPing, protocol.HealthPing{From: "test"})
	body, _ := msg.Marshal()

	req := httptest.NewRequest("POST", "/mist", bytes.NewReader(body))
	w := httptest.NewRecorder()
	h.Ingest(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want 400", w.Code)
	}
}

func TestHandlerRunDirect(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	body, _ := json.Marshal(protocol.EvalRun{Suite: "math"})
	req := httptest.NewRequest("POST", "/eval", bytes.NewReader(body))
	w := httptest.NewRecorder()
	h.RunDirect(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}
}

func TestHandlerSuites(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	req := httptest.NewRequest("GET", "/suites", nil)
	w := httptest.NewRecorder()
	h.Suites(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}

	var resp SuitesResponse
	json.Unmarshal(w.Body.Bytes(), &resp)
	if len(resp.Suites) != 1 || resp.Suites[0].Name != "math" {
		t.Errorf("unexpected suites: %+v", resp.Suites)
	}
}

func TestHandlerResults(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	// Run first to populate results.
	runner.Run(context.Background(), protocol.EvalRun{Suite: "math"})

	req := httptest.NewRequest("GET", "/results", nil)
	w := httptest.NewRecorder()
	h.Results(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", w.Code)
	}

	var results []protocol.EvalResult
	json.Unmarshal(w.Body.Bytes(), &results)
	if len(results) != 1 {
		t.Errorf("expected 1 result, got %d", len(results))
	}
}

func TestHandlerResultsBySuite(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	runner.Run(context.Background(), protocol.EvalRun{Suite: "math"})

	req := httptest.NewRequest("GET", "/results?suite=math", nil)
	w := httptest.NewRecorder()
	h.Results(w, req)

	var results []protocol.EvalResult
	json.Unmarshal(w.Body.Bytes(), &results)
	if len(results) != 1 {
		t.Errorf("expected 1 result for math, got %d", len(results))
	}
}

func TestHandlerMethodNotAllowed(t *testing.T) {
	runner, reg := testRunnerAndRegistry()
	h := NewHandler(runner, reg)

	req := httptest.NewRequest("GET", "/mist", nil)
	w := httptest.NewRecorder()
	h.Ingest(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", w.Code)
	}
}
