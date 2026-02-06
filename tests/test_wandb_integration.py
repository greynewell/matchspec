"""Tests for W&B integration."""

from unittest.mock import MagicMock, patch

from mcpbr.wandb_integration import log_evaluation


class TestWandbIntegration:
    """W&B logging integration tests."""

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_log_evaluation_calls_wandb_init(self, mock_get_wandb):
        mock_wandb = MagicMock()
        mock_get_wandb.return_value = mock_wandb

        results = {
            "metadata": {
                "config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"},
            },
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
            },
            "tasks": [
                {
                    "instance_id": "task-0",
                    "mcp": {"resolved": True, "cost": 1.25},
                },
            ],
        }

        log_evaluation(results, project="test-project")

        mock_wandb.init.assert_called_once()
        init_kwargs = mock_wandb.init.call_args.kwargs
        assert init_kwargs["project"] == "test-project"

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_config_logged_to_wandb(self, mock_get_wandb):
        mock_wandb = MagicMock()
        mock_get_wandb.return_value = mock_wandb

        results = {
            "metadata": {
                "config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"},
            },
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
            },
            "tasks": [],
        }

        log_evaluation(results, project="test-project")

        init_kwargs = mock_wandb.init.call_args.kwargs
        assert init_kwargs["config"]["benchmark"] == "humaneval"
        assert init_kwargs["config"]["model"] == "claude-sonnet-4-5"

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_summary_logged(self, mock_get_wandb):
        mock_wandb = MagicMock()
        mock_get_wandb.return_value = mock_wandb

        results = {
            "metadata": {
                "config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"},
            },
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
            },
            "tasks": [],
        }

        log_evaluation(results, project="test-project")

        mock_wandb.log.assert_called()
        log_kwargs = mock_wandb.log.call_args[0][0]
        assert log_kwargs["resolution_rate"] == 0.8
        assert log_kwargs["total_cost"] == 12.50

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_per_task_results_logged_as_table(self, mock_get_wandb):
        mock_wandb = MagicMock()
        mock_wandb.Table = MagicMock()
        mock_get_wandb.return_value = mock_wandb

        results = {
            "metadata": {
                "config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"},
            },
            "summary": {
                "mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50},
            },
            "tasks": [
                {"instance_id": "task-0", "mcp": {"resolved": True, "cost": 1.25}},
                {"instance_id": "task-1", "mcp": {"resolved": False, "cost": 0.50}},
            ],
        }

        log_evaluation(results, project="test-project")

        mock_wandb.Table.assert_called_once()
        mock_wandb.finish.assert_called_once()

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_wandb_finish_called(self, mock_get_wandb):
        mock_wandb = MagicMock()
        mock_get_wandb.return_value = mock_wandb

        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {"mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50}},
            "tasks": [],
        }

        log_evaluation(results, project="test-project")
        mock_wandb.finish.assert_called_once()

    @patch("mcpbr.wandb_integration._get_wandb")
    def test_graceful_when_wandb_not_installed(self, mock_get_wandb):
        """Should log a warning, not raise, when wandb is not installed."""
        mock_get_wandb.return_value = None

        results = {
            "metadata": {"config": {"benchmark": "humaneval", "model": "claude-sonnet-4-5"}},
            "summary": {"mcp": {"resolved": 8, "total": 10, "rate": 0.8, "total_cost": 12.50}},
            "tasks": [],
        }

        # Should NOT raise
        log_evaluation(results, project="test-project")
