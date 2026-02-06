"""Infrastructure manager for creating and managing providers."""

from pathlib import Path
from typing import Any

from rich.console import Console

from .base import InfrastructureProvider
from .local import LocalProvider


class UnknownInfrastructureModeError(ValueError):
    """Raised when an unknown infrastructure mode is specified."""

    def __init__(self, mode: str) -> None:
        super().__init__(f"Unknown infrastructure mode: {mode}")


class InfrastructureHealthCheckError(RuntimeError):
    """Raised when infrastructure health checks fail."""

    def __init__(self, failures: list[str]) -> None:
        super().__init__(f"Health check failed: {', '.join(failures)}")


class InfrastructureManager:
    """Factory and lifecycle manager for infrastructure providers.

    This class provides factory methods for creating infrastructure providers
    and orchestrating the full evaluation lifecycle (health check, setup,
    evaluation, artifact collection, cleanup).
    """

    @staticmethod
    def create_provider(config: Any) -> InfrastructureProvider:
        """Create an infrastructure provider based on configuration.

        Args:
            config: Harness configuration object with infrastructure attribute.

        Returns:
            Infrastructure provider instance.

        Raises:
            UnknownInfrastructureModeError: If infrastructure mode is unknown.
        """
        # Get infrastructure config (with backward compatibility)
        infra_config = getattr(config, "infrastructure", None)
        if infra_config is None:
            # Backward compatibility: check for old infrastructure_mode attribute
            mode = getattr(config, "infrastructure_mode", "local")
        else:
            mode = infra_config.mode

        if mode == "local":
            return LocalProvider()
        elif mode == "azure":
            from .azure import AzureProvider

            return AzureProvider(config)
        elif mode == "aws":
            from .aws import AWSProvider

            return AWSProvider(config)
        elif mode == "gcp":
            from .gcp import GCPProvider

            return GCPProvider(config)
        elif mode == "kubernetes":
            from .k8s import KubernetesProvider

            return KubernetesProvider(config)
        elif mode == "cloudflare":
            from .cloudflare import CloudflareProvider

            return CloudflareProvider(config)
        else:
            raise UnknownInfrastructureModeError(mode)

    @staticmethod
    async def run_with_infrastructure(
        config: Any,
        config_path: Path,
        output_dir: Path | None,
        run_mcp: bool,
        run_baseline: bool,
    ) -> dict[str, Any]:
        """Run evaluation with full infrastructure lifecycle management.

        This method orchestrates the complete evaluation workflow:
        1. Health check - validate environment is ready
        2. Setup - provision infrastructure
        3. Run evaluation - execute the evaluation
        4. Collect artifacts - package outputs into ZIP
        5. Cleanup - tear down infrastructure

        The cleanup step is guaranteed to run even if evaluation fails.

        Args:
            config: Harness configuration object.
            config_path: Path to configuration file.
            output_dir: Directory for evaluation outputs (None to skip artifacts).
            run_mcp: Whether to run MCP evaluation.
            run_baseline: Whether to run baseline evaluation.

        Returns:
            Dictionary with evaluation results and artifacts path:
                - results: EvaluationResults object
                - artifacts_path: Path to ZIP archive (or None if no output_dir)

        Raises:
            InfrastructureHealthCheckError: If health check fails.
            Exception: If evaluation or other steps fail.
        """
        # Create provider
        provider = InfrastructureManager.create_provider(config)

        try:
            # 1. Health check
            health_result = await provider.health_check(config=config, config_path=config_path)
            # Support both key formats: "healthy"/"failures" and "errors" (Azure)
            is_healthy = health_result.get("healthy")
            if is_healthy is None:
                # Azure format: healthy if no errors
                errors = health_result.get("errors", [])
                is_healthy = len(errors) == 0
            if not is_healthy:
                failures = health_result.get("failures") or health_result.get("errors", [])
                raise InfrastructureHealthCheckError(failures)

            # Display non-fatal warnings (e.g., quota check timeouts)
            warnings = health_result.get("warnings", [])
            if warnings:
                console = Console()
                for warning in warnings:
                    console.print(f"[yellow]⚠ Health check warning: {warning}[/yellow]")

            # 2. Setup infrastructure
            await provider.setup()

            # 3. Run evaluation
            results = await provider.run_evaluation(
                config=config, run_mcp=run_mcp, run_baseline=run_baseline
            )

            # 4. Collect artifacts (if output_dir provided)
            artifacts_path = None
            if output_dir is not None:
                artifacts_path = await provider.collect_artifacts(output_dir)

            return {
                "results": results,
                "artifacts_path": artifacts_path,
            }

        finally:
            # 5. Cleanup (always runs, even on error)
            await provider.cleanup()
