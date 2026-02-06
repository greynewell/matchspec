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


def check_azure_quotas(
    location: str, vm_size: str, zone: str | None = None, timeout: int = 120
) -> tuple[bool, str]:
    """Check if VM size is available in the specified location and zone.

    Args:
        location: Azure region.
        vm_size: Azure VM size (e.g., Standard_D4s_v3).
        zone: Azure availability zone (e.g., "1"). If specified, zone-specific
            restrictions are checked instead of treating all restrictions as blocking.
        timeout: Timeout in seconds for the az vm list-skus command.

    Returns:
        Tuple of (success, result).
        If success: result is empty string.
        If failure: result is an error message.
    """
    try:
        result = subprocess.run(
            [
                "az",
                "vm",
                "list-skus",
                "--location",
                location,
                "--size",
                vm_size,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            try:
                skus = json.loads(result.stdout)

                # Find the requested VM size
                for sku in skus:
                    if sku.get("name") == vm_size:
                        restrictions = sku.get("restrictions", [])
                        if not restrictions:
                            return True, ""

                        # Check each restriction
                        for restriction in restrictions:
                            restriction_type = restriction.get("type", "")
                            reason = restriction.get("reasonCode", "Unknown")

                            if restriction_type == "Zone" and zone:
                                # Zone-specific restriction: only fail if our zone is restricted
                                restricted_zones = restriction.get("restrictionInfo", {}).get(
                                    "zones", []
                                )
                                if zone in restricted_zones:
                                    return (
                                        False,
                                        f"VM size {vm_size} is restricted in {location} zone {zone}: {reason}",
                                    )
                                # Our zone is not in the restricted list — OK
                            else:
                                # Location-wide restriction
                                return (
                                    False,
                                    f"VM size {vm_size} is restricted in {location}: {reason}",
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
            "warnings": list[str],  # Non-fatal issues (e.g., quota check failures)
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
    # Quota check is non-fatal — failures are reported as warnings, not hard errors.
    # This prevents slow `az vm list-skus` calls from blocking the entire evaluation.
    if config.vm_size:
        zone = getattr(config, "zone", None)
        timeout = getattr(config, "quota_check_timeout", 120)
        quota_success, quota_result = check_azure_quotas(
            config.location, config.vm_size, zone, timeout=timeout
        )
        results["quotas"] = quota_success
        if not quota_success:
            results["warnings"] = results.get("warnings", [])
            results["warnings"].append(f"Quotas: {quota_result}")
    else:
        # Skip quota check if no vm_size specified
        results["quotas"] = True

    return results
