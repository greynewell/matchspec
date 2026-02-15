package matchspec

import (
	"encoding/json"
	"net/http"

	"github.com/greynewell/mist-go/protocol"
)

// Handler provides HTTP handlers for the MatchSpec API.
type Handler struct {
	runner   *Runner
	registry *SuiteRegistry
}

// NewHandler creates a handler wired to the given runner.
func NewHandler(runner *Runner, registry *SuiteRegistry) *Handler {
	return &Handler{runner: runner, registry: registry}
}

// Ingest handles POST /mist — accepts MIST protocol messages containing
// evaluation runs and returns results.
func (h *Handler) Ingest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var msg protocol.Message
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		http.Error(w, "invalid message: "+err.Error(), http.StatusBadRequest)
		return
	}

	if msg.Type != protocol.TypeEvalRun {
		http.Error(w, "expected type eval.run, got "+msg.Type, http.StatusBadRequest)
		return
	}

	var run protocol.EvalRun
	if err := msg.Decode(&run); err != nil {
		http.Error(w, "invalid run payload: "+err.Error(), http.StatusBadRequest)
		return
	}

	results, err := h.runner.Run(r.Context(), run)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

// RunDirect handles POST /eval — accepts a direct EvalRun JSON body.
func (h *Handler) RunDirect(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var run protocol.EvalRun
	if err := json.NewDecoder(r.Body).Decode(&run); err != nil {
		http.Error(w, "invalid request: "+err.Error(), http.StatusBadRequest)
		return
	}

	results, err := h.runner.Run(r.Context(), run)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

// SuitesResponse is the JSON body for GET /suites.
type SuitesResponse struct {
	Suites []SuiteInfo `json:"suites"`
}

// SuiteInfo describes a registered suite.
type SuiteInfo struct {
	Name      string `json:"name"`
	TaskCount int    `json:"task_count"`
}

// Suites handles GET /suites — lists all registered suites.
func (h *Handler) Suites(w http.ResponseWriter, r *http.Request) {
	var resp SuitesResponse
	for _, name := range h.registry.Names() {
		if s, ok := h.registry.Get(name); ok {
			resp.Suites = append(resp.Suites, SuiteInfo{
				Name:      s.Name,
				TaskCount: len(s.Tasks),
			})
		}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// Results handles GET /results — returns all collected results.
func (h *Handler) Results(w http.ResponseWriter, r *http.Request) {
	suite := r.URL.Query().Get("suite")
	var results []protocol.EvalResult
	if suite != "" {
		results = h.runner.ResultsBySuite(suite)
	} else {
		results = h.runner.Results()
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}
