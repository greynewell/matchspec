"""Local infrastructure provider implementation."""

import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..harness import run_evaluation
from ..preflight import run_comprehensive_preflight
from .base import InfrastructureProvider


class LocalProvider(InfrastructureProvider):
    """Infrastructure provider for running evaluations on the local machine.

    This provider implements the infrastructure abstraction for local execution,
    where evaluations run directly on the current machine without provisioning
    remote resources.
    """

    async def setup(self) -> None:
        """Provision infrastructure and prepare environment.

        For local execution, this is a no-op since we're already on the target machine.

        Returns:
            None
        """
        # No-op: already on local machine

    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on the local infrastructure.

        This delegates to the existing harness.run_evaluation() function
        to execute the evaluation locally.

        Args:
            config: Harness configuration object.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object with all results.

        Raises:
            Exception: If evaluation fails.
        """
        # Delegate to existing harness implementation
        return await run_evaluation(config=config, run_mcp=run_mcp, run_baseline=run_baseline)

    async def collect_artifacts(self, output_dir: Path) -> Path:
        """Collect logs/results/traces into ZIP archive.

        Creates a ZIP archive of all files in the output directory,
        preserving the directory structure.

        Args:
            output_dir: Directory containing evaluation outputs.

        Returns:
            Path to the created ZIP archive.

        Raises:
            Exception: If artifact collection fails.
        """
        # Create ZIP archive with timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        zip_path = output_dir.parent / f"artifacts_{timestamp}.zip"

        # Create ZIP file
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Walk through output directory and add all files
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    # Calculate relative path from output_dir
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)

        return zip_path

    async def cleanup(self, force: bool = False) -> None:
        """Tear down infrastructure.

        For local execution, this is a no-op since there's no infrastructure
        to tear down (Docker cleanup is handled by DockerEnvironmentManager).

        Args:
            force: If True, force cleanup even if evaluation is still running.

        Returns:
            None
        """
        # No-op: no infrastructure to tear down for local execution

    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run pre-flight validation checks.

        Delegates to the existing preflight.run_comprehensive_preflight() function
        to validate that the local environment is ready for evaluation.

        Args:
            **kwargs: Must include 'config' and 'config_path' keys.

        Returns:
            Dictionary with health check results:
                - healthy (bool): Overall health status
                - checks (list): List of individual check results
                - failures (list): List of failure messages

        Raises:
            KeyError: If required kwargs are missing.
        """
        config = kwargs["config"]
        config_path = kwargs["config_path"]

        # Delegate to existing preflight implementation
        checks, failures = run_comprehensive_preflight(config, config_path)

        return {
            "healthy": len(failures) == 0,
            "checks": checks,
            "failures": failures,
        }
