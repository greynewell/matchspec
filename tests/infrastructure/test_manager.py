"""Tests for InfrastructureManager factory and lifecycle management."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcpbr.infrastructure.base import InfrastructureProvider
from mcpbr.infrastructure.local import LocalProvider
from mcpbr.infrastructure.manager import (
    InfrastructureHealthCheckError,
    InfrastructureManager,
    UnknownInfrastructureModeError,
)


class TestInfrastructureManager:
    """Test InfrastructureManager factory and lifecycle."""

    def test_create_provider_with_local_mode(self) -> None:
        """Test creating a LocalProvider with mode='local'."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra

        provider = InfrastructureManager.create_provider(mock_config)

        assert isinstance(provider, LocalProvider)
        assert isinstance(provider, InfrastructureProvider)

    def test_create_provider_raises_error_for_unknown_mode(self) -> None:
        """Test that create_provider() raises error for unknown mode."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "unknown_mode"
        mock_config.infrastructure = mock_infra

        with pytest.raises(
            UnknownInfrastructureModeError, match="Unknown infrastructure mode: unknown_mode"
        ):
            InfrastructureManager.create_provider(mock_config)

    def test_create_provider_azure_mode(self) -> None:
        """Test that create_provider() returns AzureProvider for azure mode."""
        from mcpbr.infrastructure.azure import AzureProvider

        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "azure"
        mock_config.infrastructure = mock_infra

        provider = InfrastructureManager.create_provider(mock_config)

        assert isinstance(provider, AzureProvider)

    def test_create_provider_default_mode(self) -> None:
        """Test that create_provider() defaults to local when mode not specified."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra

        provider = InfrastructureManager.create_provider(mock_config)

        assert isinstance(provider, LocalProvider)

    def test_create_provider_backward_compatibility(self) -> None:
        """Test backward compatibility with old infrastructure_mode attribute."""
        mock_config = MagicMock()
        mock_config.infrastructure = None
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra

        provider = InfrastructureManager.create_provider(mock_config)

        assert isinstance(provider, LocalProvider)

    @pytest.mark.asyncio
    async def test_run_with_infrastructure_lifecycle(self) -> None:
        """Test run_with_infrastructure() executes full lifecycle."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra
        mock_config_path = Path("/fake/config.yaml")

        # Track the order of calls
        call_order = []

        # Create a mock provider with tracking
        mock_provider = AsyncMock(spec=InfrastructureProvider)
        mock_provider.health_check.side_effect = lambda **_: (
            call_order.append("health_check"),
            {"healthy": True, "checks": [], "failures": []},
        )[1]
        mock_provider.setup.side_effect = lambda: call_order.append("setup")
        mock_provider.run_evaluation.side_effect = lambda **_: (
            call_order.append("run_evaluation"),
            MagicMock(),
        )[1]
        mock_provider.collect_artifacts.side_effect = lambda _output_dir: (
            call_order.append("collect_artifacts"),
            Path("/fake/artifacts.zip"),
        )[1]
        mock_provider.cleanup.side_effect = lambda **_: call_order.append("cleanup")

        with patch.object(InfrastructureManager, "create_provider", return_value=mock_provider):
            output_dir = Path("/fake/output")
            result = await InfrastructureManager.run_with_infrastructure(
                config=mock_config,
                config_path=mock_config_path,
                output_dir=output_dir,
                run_mcp=True,
                run_baseline=False,
            )

            # Verify lifecycle order
            assert call_order == [
                "health_check",
                "setup",
                "run_evaluation",
                "collect_artifacts",
                "cleanup",
            ]

            # Verify result structure
            assert "results" in result
            assert "artifacts_path" in result

    @pytest.mark.asyncio
    async def test_run_with_infrastructure_passes_parameters(self) -> None:
        """Test that run_with_infrastructure() passes all parameters correctly."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra
        mock_config_path = Path("/fake/config.yaml")

        mock_provider = AsyncMock(spec=InfrastructureProvider)
        mock_provider.health_check.return_value = {
            "healthy": True,
            "checks": [],
            "failures": [],
        }
        mock_provider.run_evaluation.return_value = MagicMock()
        mock_provider.collect_artifacts.return_value = Path("/fake/artifacts.zip")

        with patch.object(InfrastructureManager, "create_provider", return_value=mock_provider):
            output_dir = Path("/fake/output")
            await InfrastructureManager.run_with_infrastructure(
                config=mock_config,
                config_path=mock_config_path,
                output_dir=output_dir,
                run_mcp=True,
                run_baseline=False,
            )

            # Verify health_check was called with config
            mock_provider.health_check.assert_called_once()
            call_kwargs = mock_provider.health_check.call_args.kwargs
            assert call_kwargs["config"] == mock_config
            assert call_kwargs["config_path"] == mock_config_path

            # Verify run_evaluation was called with correct flags
            mock_provider.run_evaluation.assert_called_once()
            eval_kwargs = mock_provider.run_evaluation.call_args.kwargs
            assert eval_kwargs["config"] == mock_config
            assert eval_kwargs["run_mcp"] is True
            assert eval_kwargs["run_baseline"] is False

            # Verify collect_artifacts was called with output_dir
            mock_provider.collect_artifacts.assert_called_once_with(output_dir)

    @pytest.mark.asyncio
    async def test_run_with_infrastructure_cleanup_on_error(self) -> None:
        """Test that cleanup is called even when evaluation fails."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra
        mock_config_path = Path("/fake/config.yaml")

        mock_provider = AsyncMock(spec=InfrastructureProvider)
        mock_provider.health_check.return_value = {
            "healthy": True,
            "checks": [],
            "failures": [],
        }
        mock_provider.run_evaluation.side_effect = RuntimeError("Evaluation failed")

        with patch.object(InfrastructureManager, "create_provider", return_value=mock_provider):
            output_dir = Path("/fake/output")

            with pytest.raises(RuntimeError, match="Evaluation failed"):
                await InfrastructureManager.run_with_infrastructure(
                    config=mock_config,
                    config_path=mock_config_path,
                    output_dir=output_dir,
                    run_mcp=True,
                    run_baseline=True,
                )

            # Verify cleanup was still called
            mock_provider.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_infrastructure_fails_on_unhealthy(self) -> None:
        """Test that run_with_infrastructure() fails if health check fails."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra
        mock_config_path = Path("/fake/config.yaml")

        mock_provider = AsyncMock(spec=InfrastructureProvider)
        mock_provider.health_check.return_value = {
            "healthy": False,
            "checks": [],
            "failures": ["Docker is not running"],
        }

        with patch.object(InfrastructureManager, "create_provider", return_value=mock_provider):
            output_dir = Path("/fake/output")

            with pytest.raises(InfrastructureHealthCheckError, match="Health check failed"):
                await InfrastructureManager.run_with_infrastructure(
                    config=mock_config,
                    config_path=mock_config_path,
                    output_dir=output_dir,
                    run_mcp=True,
                    run_baseline=True,
                )

            # Verify setup was not called
            mock_provider.setup.assert_not_called()
            mock_provider.run_evaluation.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_infrastructure_skips_artifacts_if_no_output_dir(self) -> None:
        """Test that artifact collection is skipped if output_dir is None."""
        mock_config = MagicMock()
        mock_infra = MagicMock()
        mock_infra.mode = "local"
        mock_config.infrastructure = mock_infra
        mock_config_path = Path("/fake/config.yaml")

        mock_provider = AsyncMock(spec=InfrastructureProvider)
        mock_provider.health_check.return_value = {
            "healthy": True,
            "checks": [],
            "failures": [],
        }
        mock_provider.run_evaluation.return_value = MagicMock()

        with patch.object(InfrastructureManager, "create_provider", return_value=mock_provider):
            result = await InfrastructureManager.run_with_infrastructure(
                config=mock_config,
                config_path=mock_config_path,
                output_dir=None,
                run_mcp=True,
                run_baseline=True,
            )

            # Verify collect_artifacts was not called
            mock_provider.collect_artifacts.assert_not_called()

            # Result should not have artifacts_path
            assert result["artifacts_path"] is None
