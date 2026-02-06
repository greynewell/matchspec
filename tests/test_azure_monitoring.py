"""Tests for Azure monitoring — RunState, status, logs, ssh, stop commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcpbr.run_state import RunState


class TestRunState:
    """RunState persistence and serialization."""

    def test_serializes_to_json(self):
        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )
        data = state.to_dict()
        assert data["vm_name"] == "mcpbr-eval-12345"
        assert data["vm_ip"] == "10.0.0.1"
        assert data["resource_group"] == "mcpbr-rg"

    def test_deserializes_from_json(self):
        data = {
            "vm_name": "mcpbr-eval-12345",
            "vm_ip": "10.0.0.1",
            "resource_group": "mcpbr-rg",
            "location": "eastus",
            "ssh_key_path": "/home/user/.ssh/mcpbr_azure",
            "config_path": "/home/user/config.yaml",
            "started_at": "2025-01-01T00:00:00Z",
        }
        state = RunState.from_dict(data)
        assert state.vm_name == "mcpbr-eval-12345"
        assert state.vm_ip == "10.0.0.1"

    def test_saves_to_disk(self):
        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "run_state.json"
            state.save(path)
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["vm_name"] == "mcpbr-eval-12345"

    def test_loads_from_disk(self):
        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "run_state.json"
            state.save(path)
            loaded = RunState.load(path)
            assert loaded.vm_name == state.vm_name
            assert loaded.vm_ip == state.vm_ip
            assert loaded.resource_group == state.resource_group

    def test_load_nonexistent_returns_none(self):
        result = RunState.load(Path("/nonexistent/run_state.json"))
        assert result is None

    def test_load_corrupt_json_returns_none(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json{{{")
        result = RunState.load(path)
        assert result is None


class TestAzureMonitoring:
    """Azure provider monitoring methods."""

    @patch("subprocess.run")
    def test_get_status_calls_az_vm_show(self, mock_run):
        from mcpbr.infrastructure.azure import AzureProvider

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"powerState": "VM running"}',
        )

        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )

        result = AzureProvider.get_run_status(state)
        assert result["powerState"] == "VM running"

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "az" in cmd
        assert "vm" in cmd
        assert "show" in cmd

    def test_get_ssh_command(self):
        from mcpbr.infrastructure.azure import AzureProvider

        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )

        ssh_cmd = AzureProvider.get_ssh_command(state)
        assert "ssh" in ssh_cmd
        assert "10.0.0.1" in ssh_cmd
        assert "mcpbr_azure" in ssh_cmd

    @patch("subprocess.run")
    def test_stop_calls_az_vm_deallocate(self, mock_run):
        from mcpbr.infrastructure.azure import AzureProvider

        mock_run.return_value = MagicMock(returncode=0, stdout="")

        state = RunState(
            vm_name="mcpbr-eval-12345",
            vm_ip="10.0.0.1",
            resource_group="mcpbr-rg",
            location="eastus",
            ssh_key_path="/home/user/.ssh/mcpbr_azure",
            config_path="/home/user/config.yaml",
            started_at="2025-01-01T00:00:00Z",
        )

        AzureProvider.stop_run(state)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "az" in cmd
        assert "vm" in cmd
        assert "deallocate" in cmd
