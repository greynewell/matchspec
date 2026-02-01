"""Azure health check functions."""

import json
import platform
import subprocess
from typing import Any

from ..config import AzureConfig


def check_az_cli_installed() -> tuple[bool, str]:
    """Check if Azure CLI is installed.

    Returns:
        Tuple of (success, result).
        If success: result is the path to az CLI.
        If failure: result is an error message.
    """
    try:
        # Use 'which' on Unix, 'where' on Windows
        command = "where" if platform.system() == "Windows" else "which"
        result = subprocess.run(
            [command, "az"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            az_path = result.stdout.strip()
            return True, az_path
        else:
            return (
                False,
                "Azure CLI (az) not found. Please install it from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli",
            )
    except Exception as e:
        return False, f"Error checking for Azure CLI: {e}"


def check_az_authenticated() -> tuple[bool, str]:
    """Check if authenticated to Azure.

    Returns:
        Tuple of (success, result).
        If success: result is the user account.
        If failure: result is an error message.
    """
    try:
        result = subprocess.run(
            ["az", "account", "show", "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            try:
                account = json.loads(result.stdout)
                user_name = account.get("user", {}).get("name", "unknown")
                return True, f"Authenticated as {user_name}"
            except json.JSONDecodeError:
                return False, "Error parsing Azure account information"
        else:
            return False, "Not logged in to Azure. Please run 'az login' to authenticate."
    except Exception as e:
        return False, f"Error checking Azure authentication: {e}"


def check_az_subscription(subscription_id: str | None) -> tuple[bool, str]:
    """Check if subscription is accessible.

    Args:
        subscription_id: Subscription ID to check. If None, checks for default subscription.

    Returns:
        Tuple of (success, result).
        If success: result is the subscription name.
        If failure: result is an error message.
    """
    try:
        result = subprocess.run(
            ["az", "account", "list", "--output", "json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            try:
                subscriptions = json.loads(result.stdout)

                if subscription_id:
                    # Look for specific subscription
                    for sub in subscriptions:
                        if sub.get("id") == subscription_id:
                            return True, f"Found subscription: {sub.get('name', 'Unknown')}"
                    return False, f"Subscription {subscription_id} not found or not accessible"
                else:
                    # Look for default subscription
                    for sub in subscriptions:
                        if sub.get("isDefault", False):
                            return True, f"Using default subscription: {sub.get('name', 'Unknown')}"
                    return (
                        False,
                        "No default subscription set. Please run 'az account set --subscription <id>'",
                    )
            except json.JSONDecodeError:
                return False, "Error parsing Azure subscription information"
        else:
            return False, f"Error listing Azure subscriptions: {result.stderr}"
    except Exception as e:
        return False, f"Error checking Azure subscription: {e}"


def check_azure_quotas(location: str, vm_size: str) -> tuple[bool, str]:
    """Check if VM size is available in the specified location.

    Args:
        location: Azure region.
        vm_size: Azure VM size (e.g., Standard_D4s_v3).

    Returns:
        Tuple of (success, result).
        If success: result is empty string.
        If failure: result is an error message.
    """
    try:
        result = subprocess.run(
            ["az", "vm", "list-skus", "--location", location, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            try:
                skus = json.loads(result.stdout)

                # Find the requested VM size
                for sku in skus:
                    if sku.get("name") == vm_size:
                        # Check if there are any restrictions
                        restrictions = sku.get("restrictions", [])
                        if restrictions:
                            reasons = [r.get("reasonCode", "Unknown") for r in restrictions]
                            return (
                                False,
                                f"VM size {vm_size} is restricted in {location}: {', '.join(reasons)}",
                            )
                        return True, ""

                # VM size not found in this location
                return False, f"VM size {vm_size} is not available in {location}"
            except json.JSONDecodeError:
                return False, "Error parsing Azure VM SKU information"
        else:
            return False, f"Error checking Azure quotas: {result.stderr}"
    except Exception as e:
        return False, f"Error checking Azure quotas: {e}"


def run_azure_health_checks(config: AzureConfig) -> dict[str, Any]:
    """Run all Azure health checks.

    Args:
        config: Azure configuration.

    Returns:
        Dictionary with check results and any errors.
        {
            "az_cli": bool,
            "authenticated": bool,
            "subscription": bool,
            "quotas": bool,
            "errors": list[str],
        }
    """
    results: dict[str, Any] = {
        "az_cli": False,
        "authenticated": False,
        "subscription": False,
        "quotas": False,
        "errors": [],
    }

    # Check 1: Azure CLI installed
    cli_success, cli_result = check_az_cli_installed()
    results["az_cli"] = cli_success
    if not cli_success:
        results["errors"].append(f"Azure CLI: {cli_result}")
        return results  # Can't proceed without CLI

    # Check 2: Authenticated
    auth_success, auth_result = check_az_authenticated()
    results["authenticated"] = auth_success
    if not auth_success:
        results["errors"].append(f"Authentication: {auth_result}")
        return results  # Can't proceed without auth

    # Check 3: Subscription access
    sub_success, sub_result = check_az_subscription(None)
    results["subscription"] = sub_success
    if not sub_success:
        results["errors"].append(f"Subscription: {sub_result}")
        return results  # Can't proceed without subscription

    # Check 4: VM size/quota (only if vm_size is specified)
    if config.vm_size:
        quota_success, quota_result = check_azure_quotas(config.location, config.vm_size)
        results["quotas"] = quota_success
        if not quota_success:
            results["errors"].append(f"Quotas: {quota_result}")
    else:
        # Skip quota check if no vm_size specified
        results["quotas"] = True

    return results
