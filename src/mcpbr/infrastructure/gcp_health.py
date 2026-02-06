"""GCP health check functions."""

import json
import platform
import subprocess
from typing import Any


def check_gcloud_cli_installed() -> tuple[bool, str]:
    """Check if gcloud CLI is installed.

    Returns:
        Tuple of (success, result).
        If success: result is the path to gcloud CLI.
        If failure: result is an error message.
    """
    try:
        # Use 'which' on Unix, 'where' on Windows
        command = "where" if platform.system() == "Windows" else "which"
        result = subprocess.run(
            [command, "gcloud"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            gcloud_path = result.stdout.strip()
            return True, gcloud_path
        else:
            return (
                False,
                "gcloud CLI not found. Please install it from "
                "https://cloud.google.com/sdk/docs/install",
            )
    except Exception as e:
        return False, f"Error checking for gcloud CLI: {e}"


def check_gcloud_authenticated() -> tuple[bool, str]:
    """Check if authenticated to GCP.

    Returns:
        Tuple of (success, result).
        If success: result is the authenticated account.
        If failure: result is an error message.
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Get the active account for display
            account_result = subprocess.run(
                ["gcloud", "config", "get-value", "account"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            account = account_result.stdout.strip() if account_result.returncode == 0 else "unknown"
            return True, f"Authenticated as {account}"
        else:
            return (
                False,
                "Not authenticated to GCP. Please run 'gcloud auth login' to authenticate.",
            )
    except Exception as e:
        return False, f"Error checking GCP authentication: {e}"


def check_gcloud_project(project_id: str | None) -> tuple[bool, str]:
    """Check if a GCP project is accessible.

    Args:
        project_id: Project ID to check. If None, checks for default project.

    Returns:
        Tuple of (success, result).
        If success: result is the project ID.
        If failure: result is an error message.
    """
    try:
        if project_id:
            # Check specific project
            result = subprocess.run(
                [
                    "gcloud",
                    "projects",
                    "describe",
                    project_id,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                try:
                    project = json.loads(result.stdout)
                    name = project.get("name", project_id)
                    return True, f"Found project: {name} ({project_id})"
                except json.JSONDecodeError:
                    return False, "Error parsing GCP project information"
            else:
                return (
                    False,
                    f"Project {project_id} not found or not accessible: {result.stderr[:200]}",
                )
        else:
            # Check for default project
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                default_project = result.stdout.strip()
                return True, f"Using default project: {default_project}"
            else:
                return (
                    False,
                    "No default project set. Please run "
                    "'gcloud config set project <PROJECT_ID>' or specify project_id in config.",
                )
    except Exception as e:
        return False, f"Error checking GCP project: {e}"


def check_compute_api_enabled(project_id: str | None) -> tuple[bool, str]:
    """Check if the Compute Engine API is enabled.

    Args:
        project_id: Project ID to check. If None, uses the default project.

    Returns:
        Tuple of (success, result).
        If success: result is empty string.
        If failure: result is an error message.
    """
    try:
        cmd = [
            "gcloud",
            "services",
            "list",
            "--enabled",
            "--filter",
            "config.name=compute.googleapis.com",
            "--format",
            "json",
        ]
        if project_id:
            cmd.extend(["--project", project_id])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            try:
                services = json.loads(result.stdout)
                if services:
                    return True, ""
                else:
                    return (
                        False,
                        "Compute Engine API is not enabled. Please run "
                        "'gcloud services enable compute.googleapis.com'",
                    )
            except json.JSONDecodeError:
                return False, "Error parsing GCP services information"
        else:
            return False, f"Error checking Compute Engine API: {result.stderr[:200]}"
    except Exception as e:
        return False, f"Error checking Compute Engine API: {e}"


def run_gcp_health_checks(config: Any) -> dict[str, Any]:
    """Run all GCP health checks.

    Args:
        config: GCP configuration object with project_id attribute.

    Returns:
        Dictionary with check results and any errors.
        {
            "gcloud_cli": bool,
            "authenticated": bool,
            "project": bool,
            "compute_api": bool,
            "errors": list[str],
            "warnings": list[str],
        }
    """
    results: dict[str, Any] = {
        "gcloud_cli": False,
        "authenticated": False,
        "project": False,
        "compute_api": False,
        "errors": [],
        "warnings": [],
    }

    # Check 1: gcloud CLI installed
    cli_success, cli_result = check_gcloud_cli_installed()
    results["gcloud_cli"] = cli_success
    if not cli_success:
        results["errors"].append(f"gcloud CLI: {cli_result}")
        return results  # Can't proceed without CLI

    # Check 2: Authenticated
    auth_success, auth_result = check_gcloud_authenticated()
    results["authenticated"] = auth_success
    if not auth_success:
        results["errors"].append(f"Authentication: {auth_result}")
        return results  # Can't proceed without auth

    # Check 3: Project access
    project_id = getattr(config, "project_id", None)
    project_success, project_result = check_gcloud_project(project_id)
    results["project"] = project_success
    if not project_success:
        results["errors"].append(f"Project: {project_result}")
        return results  # Can't proceed without project

    # Check 4: Compute Engine API enabled
    api_success, api_result = check_compute_api_enabled(project_id)
    results["compute_api"] = api_success
    if not api_success:
        # API not enabled is a warning, not a hard error -- the user may
        # need to enable it but we don't want to block the entire flow
        results["warnings"].append(f"Compute Engine API: {api_result}")

    return results
