"""Tests for Azure health check functions."""

import json
from unittest.mock import MagicMock, patch

from mcpbr.config import AzureConfig
from mcpbr.infrastructure.azure_health import (
    check_az_authenticated,
    check_az_cli_installed,
    check_az_subscription,
    check_azure_quotas,
    run_azure_health_checks,
)


class TestCheckAzCliInstalled:
    """Tests for check_az_cli_installed function."""

    @patch("subprocess.run")
    @patch("platform.system")
    def test_az_cli_installed_unix(self, mock_system: MagicMock, mock_run: MagicMock) -> None:
        """Test detecting az CLI on Unix systems."""
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="/usr/local/bin/az\n",
        )

        success, result = check_az_cli_installed()

        assert success is True
        assert result == "/usr/local/bin/az"
        mock_run.assert_called_once()
        assert "which" in mock_run.call_args[0][0]

    @patch("subprocess.run")
    @patch("platform.system")
    def test_az_cli_installed_windows(self, mock_system: MagicMock, mock_run: MagicMock) -> None:
        """Test detecting az CLI on Windows systems."""
        mock_system.return_value = "Windows"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="C:\\Program Files\\az.cmd\n",
        )

        success, result = check_az_cli_installed()

        assert success is True
        assert result == "C:\\Program Files\\az.cmd"
        mock_run.assert_called_once()
        assert "where" in mock_run.call_args[0][0]

    @patch("subprocess.run")
    @patch("platform.system")
    def test_az_cli_not_installed(self, mock_system: MagicMock, mock_run: MagicMock) -> None:
        """Test detecting when az CLI is not installed."""
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        success, result = check_az_cli_installed()

        assert success is False
        assert "not found" in result.lower()

    @patch("subprocess.run")
    @patch("platform.system")
    def test_az_cli_check_exception(self, mock_system: MagicMock, mock_run: MagicMock) -> None:
        """Test handling exceptions when checking az CLI."""
        mock_system.return_value = "Linux"
        mock_run.side_effect = Exception("Command failed")

        success, result = check_az_cli_installed()

        assert success is False
        assert "error" in result.lower()


class TestCheckAzAuthenticated:
    """Tests for check_az_authenticated function."""

    @patch("subprocess.run")
    def test_az_authenticated_success(self, mock_run: MagicMock) -> None:
        """Test successful Azure authentication check."""
        account_data = {
            "id": "12345678-1234-1234-1234-123456789012",
            "name": "Test Subscription",
            "user": {"name": "test@example.com"},
        }
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(account_data),
        )

        success, result = check_az_authenticated()

        assert success is True
        assert "test@example.com" in result
        mock_run.assert_called_once()
        assert "az account show" in " ".join(mock_run.call_args[0][0])

    @patch("subprocess.run")
    def test_az_not_authenticated(self, mock_run: MagicMock) -> None:
        """Test when not authenticated to Azure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Please run 'az login' to setup account.",
        )

        success, result = check_az_authenticated()

        assert success is False
        assert "not logged in" in result.lower()

    @patch("subprocess.run")
    def test_az_authenticated_invalid_json(self, mock_run: MagicMock) -> None:
        """Test handling invalid JSON response."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
        )

        success, result = check_az_authenticated()

        assert success is False
        assert "error" in result.lower()

    @patch("subprocess.run")
    def test_az_authenticated_exception(self, mock_run: MagicMock) -> None:
        """Test handling exceptions during authentication check."""
        mock_run.side_effect = Exception("Network error")

        success, result = check_az_authenticated()

        assert success is False
        assert "error" in result.lower()


class TestCheckAzSubscription:
    """Tests for check_az_subscription function."""

    @patch("subprocess.run")
    def test_subscription_found_specific_id(self, mock_run: MagicMock) -> None:
        """Test finding a specific subscription by ID."""
        subscriptions = [
            {
                "id": "sub-1",
                "name": "Test Subscription 1",
                "state": "Enabled",
            },
            {
                "id": "sub-2",
                "name": "Test Subscription 2",
                "state": "Enabled",
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(subscriptions),
        )

        success, result = check_az_subscription("sub-2")

        assert success is True
        assert "Test Subscription 2" in result
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_subscription_found_default(self, mock_run: MagicMock) -> None:
        """Test finding default subscription when no ID specified."""
        subscriptions = [
            {
                "id": "sub-1",
                "name": "Default Subscription",
                "state": "Enabled",
                "isDefault": True,
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(subscriptions),
        )

        success, result = check_az_subscription(None)

        assert success is True
        assert "Default Subscription" in result

    @patch("subprocess.run")
    def test_subscription_not_found(self, mock_run: MagicMock) -> None:
        """Test when specified subscription is not found."""
        subscriptions = [
            {
                "id": "sub-1",
                "name": "Test Subscription",
                "state": "Enabled",
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(subscriptions),
        )

        success, result = check_az_subscription("nonexistent-sub")

        assert success is False
        assert "not found" in result.lower()

    @patch("subprocess.run")
    def test_subscription_command_fails(self, mock_run: MagicMock) -> None:
        """Test when az subscription list command fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Error listing subscriptions",
        )

        success, result = check_az_subscription(None)

        assert success is False
        assert "error" in result.lower()

    @patch("subprocess.run")
    def test_subscription_no_default(self, mock_run: MagicMock) -> None:
        """Test when no default subscription is set."""
        subscriptions = [
            {
                "id": "sub-1",
                "name": "Subscription 1",
                "state": "Enabled",
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(subscriptions),
        )

        success, result = check_az_subscription(None)

        assert success is False
        assert "no default" in result.lower()


class TestCheckAzureQuotas:
    """Tests for check_azure_quotas function."""

    @patch("subprocess.run")
    def test_vm_size_available(self, mock_run: MagicMock) -> None:
        """Test when requested VM size is available."""
        skus = [
            {
                "name": "Standard_D4s_v3",
                "locations": ["eastus"],
                "restrictions": [],
            },
            {
                "name": "Standard_D8s_v3",
                "locations": ["eastus"],
                "restrictions": [],
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(skus),
        )

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is True
        assert result == ""

    @patch("subprocess.run")
    def test_vm_size_not_available(self, mock_run: MagicMock) -> None:
        """Test when requested VM size is not available."""
        skus = [
            {
                "name": "Standard_D8s_v3",
                "locations": ["eastus"],
                "restrictions": [],
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(skus),
        )

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is False
        assert "not available" in result.lower()

    @patch("subprocess.run")
    def test_vm_size_restricted(self, mock_run: MagicMock) -> None:
        """Test when VM size has restrictions."""
        skus = [
            {
                "name": "Standard_D4s_v3",
                "locations": ["eastus"],
                "restrictions": [
                    {
                        "type": "Location",
                        "reasonCode": "NotAvailableForSubscription",
                    }
                ],
            },
        ]
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(skus),
        )

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is False
        assert "restricted" in result.lower()

    @patch("subprocess.run")
    def test_quota_check_command_fails(self, mock_run: MagicMock) -> None:
        """Test when quota check command fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Error checking quotas",
        )

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is False
        assert "error" in result.lower()

    @patch("subprocess.run")
    def test_quota_check_invalid_json(self, mock_run: MagicMock) -> None:
        """Test handling invalid JSON in quota response."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="invalid json",
        )

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is False
        assert "error" in result.lower()

    @patch("subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock) -> None:
        """Test that custom timeout is passed to subprocess."""
        skus = [{"name": "Standard_D4s_v3", "locations": ["eastus"], "restrictions": []}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(skus))

        check_azure_quotas("eastus", "Standard_D4s_v3", timeout=180)

        assert mock_run.call_args.kwargs.get("timeout") == 180

    @patch("subprocess.run")
    def test_default_timeout_is_120(self, mock_run: MagicMock) -> None:
        """Test that default timeout is 120 seconds."""
        skus = [{"name": "Standard_D4s_v3", "locations": ["eastus"], "restrictions": []}]
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(skus))

        check_azure_quotas("eastus", "Standard_D4s_v3")

        assert mock_run.call_args.kwargs.get("timeout") == 120

    @patch("subprocess.run")
    def test_timeout_returns_error(self, mock_run: MagicMock) -> None:
        """Test that subprocess timeout is handled gracefully."""
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="az", timeout=120)

        success, result = check_azure_quotas("eastus", "Standard_D4s_v3")

        assert success is False
        assert "error" in result.lower()


class TestRunAzureHealthChecks:
    """Tests for run_azure_health_checks function."""

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_all_checks_pass(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test when all health checks pass."""
        mock_cli.return_value = (True, "/usr/local/bin/az")
        mock_auth.return_value = (True, "test@example.com")
        mock_sub.return_value = (True, "Test Subscription")
        mock_quotas.return_value = (True, "")

        config = AzureConfig(
            resource_group="test-rg",
            location="eastus",
            vm_size="Standard_D4s_v3",
        )

        result = run_azure_health_checks(config)

        assert result["az_cli"] is True
        assert result["authenticated"] is True
        assert result["subscription"] is True
        assert result["quotas"] is True
        assert len(result["errors"]) == 0

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_cli_not_installed(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test when az CLI is not installed."""
        mock_cli.return_value = (False, "az command not found")
        mock_auth.return_value = (False, "Cannot check without CLI")
        mock_sub.return_value = (False, "Cannot check without CLI")
        mock_quotas.return_value = (False, "Cannot check without CLI")

        config = AzureConfig(resource_group="test-rg")

        result = run_azure_health_checks(config)

        assert result["az_cli"] is False
        assert result["authenticated"] is False
        assert result["subscription"] is False
        assert result["quotas"] is False
        assert len(result["errors"]) > 0
        assert any("az command not found" in error for error in result["errors"])

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_not_authenticated(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test when not authenticated to Azure."""
        mock_cli.return_value = (True, "/usr/local/bin/az")
        mock_auth.return_value = (False, "Not logged in")
        mock_sub.return_value = (False, "Cannot check without auth")
        mock_quotas.return_value = (False, "Cannot check without auth")

        config = AzureConfig(resource_group="test-rg")

        result = run_azure_health_checks(config)

        assert result["az_cli"] is True
        assert result["authenticated"] is False
        assert len(result["errors"]) > 0
        assert any("Not logged in" in error for error in result["errors"])

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_quota_check_fails_produces_warning_not_error(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test when quota check fails it produces a warning, not a hard error."""
        mock_cli.return_value = (True, "/usr/local/bin/az")
        mock_auth.return_value = (True, "test@example.com")
        mock_sub.return_value = (True, "Test Subscription")
        mock_quotas.return_value = (False, "VM size not available")

        config = AzureConfig(
            resource_group="test-rg",
            vm_size="Standard_D4s_v3",
        )

        result = run_azure_health_checks(config)

        assert result["az_cli"] is True
        assert result["authenticated"] is True
        assert result["subscription"] is True
        assert result["quotas"] is False
        # Quota failures are warnings, not errors — evaluation should still proceed
        assert len(result["errors"]) == 0
        assert len(result.get("warnings", [])) > 0
        assert any("VM size not available" in w for w in result["warnings"])

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_quota_check_uses_config_timeout(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test that quota check passes the configured timeout."""
        mock_cli.return_value = (True, "/usr/local/bin/az")
        mock_auth.return_value = (True, "test@example.com")
        mock_sub.return_value = (True, "Test Subscription")
        mock_quotas.return_value = (True, "")

        config = AzureConfig(
            resource_group="test-rg",
            vm_size="Standard_D4s_v3",
            quota_check_timeout=180,
        )

        run_azure_health_checks(config)

        mock_quotas.assert_called_once_with(config.location, "Standard_D4s_v3", None, timeout=180)

    @patch("mcpbr.infrastructure.azure_health.check_azure_quotas")
    @patch("mcpbr.infrastructure.azure_health.check_az_subscription")
    @patch("mcpbr.infrastructure.azure_health.check_az_authenticated")
    @patch("mcpbr.infrastructure.azure_health.check_az_cli_installed")
    def test_skip_quota_check_when_no_vm_size(
        self,
        mock_cli: MagicMock,
        mock_auth: MagicMock,
        mock_sub: MagicMock,
        mock_quotas: MagicMock,
    ) -> None:
        """Test that quota check is skipped when no vm_size specified."""
        mock_cli.return_value = (True, "/usr/local/bin/az")
        mock_auth.return_value = (True, "test@example.com")
        mock_sub.return_value = (True, "Test Subscription")

        config = AzureConfig(resource_group="test-rg", vm_size=None)

        result = run_azure_health_checks(config)

        assert result["az_cli"] is True
        assert result["authenticated"] is True
        assert result["subscription"] is True
        assert result["quotas"] is True  # Should be True when skipped
        assert len(result["errors"]) == 0
        mock_quotas.assert_not_called()
