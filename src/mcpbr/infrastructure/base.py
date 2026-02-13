"""Abstract base class for infrastructure providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class InfrastructureProvider(ABC):
    """Abstract base class for infrastructure providers.

    Infrastructure providers handle the setup, execution, and teardown of
    evaluation environments. This abstraction allows evaluations to run
    on different platforms (local, cloud VMs, etc.) with a consistent interface.
    """

    @abstractmethod
    async def setup(self) -> None:
        """Provision infrastructure and prepare environment.

        This method is called before running evaluations to set up any
        necessary infrastructure (e.g., provisioning VMs, installing dependencies).

        Returns:
            None

        Raises:
            Exception: If setup fails.
        """

    @abstractmethod
    async def run_evaluation(self, config: Any, run_mcp: bool, run_baseline: bool) -> Any:
        """Execute evaluation on the infrastructure.

        Args:
            config: Harness configuration object.
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            EvaluationResults object with all results.

        Raises:
            Exception: If evaluation fails.
        """

    @abstractmethod
    async def collect_artifacts(self, output_dir: Path) -> Path | None:
        """Collect logs/results/traces into ZIP archive.

        This method packages evaluation outputs into a single ZIP file
        for easy distribution and archival.

        Args:
            output_dir: Directory containing evaluation outputs.

        Returns:
            Path to the created ZIP archive, or None if no artifacts found.

        Raises:
            Exception: If artifact collection fails.
        """

    @abstractmethod
    async def cleanup(self, force: bool = False) -> None:
        """Tear down infrastructure.

        This method is called after evaluation to clean up any provisioned
        resources (e.g., stopping VMs, removing temporary files).

        Args:
            force: If True, force cleanup even if evaluation is still running.

        Returns:
            None

        Raises:
            Exception: If cleanup fails.
        """

    @abstractmethod
    async def health_check(self, **kwargs: Any) -> dict[str, Any]:
        """Run pre-flight validation checks.

        This method validates that the infrastructure is ready to run
        evaluations (e.g., Docker is running, API keys are set, etc.).

        Args:
            **kwargs: Provider-specific health check parameters.

        Returns:
            Dictionary with health check results:
                - healthy (bool): Overall health status
                - checks (list): List of individual check results
                - failures (list): List of failure messages

        Raises:
            Exception: If health check cannot be performed.
        """
