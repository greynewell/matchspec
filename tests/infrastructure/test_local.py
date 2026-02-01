"""Tests for LocalProvider implementation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZipFile

import pytest

from mcpbr.infrastructure.base import InfrastructureProvider
from mcpbr.infrastructure.local import LocalProvider


class TestLocalProvider:
    """Test LocalProvider implementation."""

    def test_extends_infrastructure_provider(self) -> None:
        """Test that LocalProvider extends InfrastructureProvider."""
        provider = LocalProvider()
        assert isinstance(provider, InfrastructureProvider)

    @pytest.mark.asyncio
    async def test_setup_is_noop(self) -> None:
        """Test that setup() is a no-op (already on local machine)."""
        provider = LocalProvider()
        # Should not raise and should return None
        result = await provider.setup()
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_is_noop(self) -> None:
        """Test that cleanup() is a no-op for local provider."""
        provider = LocalProvider()
        # Should not raise and should return None
        result = await provider.cleanup()
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_with_force_flag(self) -> None:
        """Test that cleanup() handles force flag (even though it's a no-op)."""
        provider = LocalProvider()
        # Should not raise with force=True
        result = await provider.cleanup(force=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_run_evaluation_delegates_to_harness(self) -> None:
        """Test that run_evaluation() delegates to harness.run_evaluation()."""
        provider = LocalProvider()

        # Mock the harness.run_evaluation function
        mock_config = MagicMock()
        mock_results = MagicMock()

        with patch("mcpbr.infrastructure.local.run_evaluation", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_results

            result = await provider.run_evaluation(
                config=mock_config, run_mcp=True, run_baseline=True
            )

            # Verify it was called correctly
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["config"] == mock_config
            assert call_kwargs["run_mcp"] is True
            assert call_kwargs["run_baseline"] is True
            assert result == mock_results

    @pytest.mark.asyncio
    async def test_run_evaluation_passes_all_parameters(self) -> None:
        """Test that run_evaluation() passes all parameters to harness."""
        provider = LocalProvider()

        mock_config = MagicMock()

        with patch("mcpbr.infrastructure.local.run_evaluation", new_callable=AsyncMock) as mock_run:
            await provider.run_evaluation(config=mock_config, run_mcp=False, run_baseline=True)

            # Verify parameters
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["run_mcp"] is False
            assert call_kwargs["run_baseline"] is True

    @pytest.mark.asyncio
    async def test_collect_artifacts_creates_zip(self, tmp_path: Path) -> None:
        """Test that collect_artifacts() creates a ZIP archive from output directory."""
        provider = LocalProvider()

        # Create a test output directory with some files
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "results.json").write_text('{"test": "data"}')
        (output_dir / "logs").mkdir()
        (output_dir / "logs" / "test.log").write_text("log content")

        # Collect artifacts
        zip_path = await provider.collect_artifacts(output_dir)

        # Verify ZIP was created
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert "artifacts" in zip_path.name

        # Verify ZIP contents
        with ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "results.json" in names
            assert "logs/test.log" in names

            # Verify content is preserved
            assert zf.read("results.json").decode() == '{"test": "data"}'
            assert zf.read("logs/test.log").decode() == "log content"

    @pytest.mark.asyncio
    async def test_collect_artifacts_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test that collect_artifacts() handles empty output directory."""
        provider = LocalProvider()

        output_dir = tmp_path / "empty_output"
        output_dir.mkdir()

        # Should still create a ZIP, just empty
        zip_path = await provider.collect_artifacts(output_dir)

        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zf:
            assert len(zf.namelist()) == 0

    @pytest.mark.asyncio
    async def test_collect_artifacts_handles_nested_directories(self, tmp_path: Path) -> None:
        """Test that collect_artifacts() handles nested directory structures."""
        provider = LocalProvider()

        output_dir = tmp_path / "nested_output"
        output_dir.mkdir()
        (output_dir / "level1").mkdir()
        (output_dir / "level1" / "level2").mkdir()
        (output_dir / "level1" / "level2" / "deep.txt").write_text("nested content")

        zip_path = await provider.collect_artifacts(output_dir)

        with ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "level1/level2/deep.txt" in names

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_preflight(self) -> None:
        """Test that health_check() delegates to preflight.run_comprehensive_preflight()."""
        provider = LocalProvider()

        mock_config = MagicMock()
        mock_config_path = Path("/fake/config.yaml")
        mock_checks = [MagicMock(name="Docker", status="✓", details="OK", critical=True)]
        mock_failures = []

        with patch("mcpbr.infrastructure.local.run_comprehensive_preflight") as mock_preflight:
            mock_preflight.return_value = (mock_checks, mock_failures)

            result = await provider.health_check(config=mock_config, config_path=mock_config_path)

            # Verify preflight was called
            mock_preflight.assert_called_once_with(mock_config, mock_config_path)

            # Verify result format
            assert "checks" in result
            assert "failures" in result
            assert "healthy" in result
            assert result["checks"] == mock_checks
            assert result["failures"] == mock_failures
            assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_check_reports_unhealthy_on_failures(self) -> None:
        """Test that health_check() reports unhealthy when there are failures."""
        provider = LocalProvider()

        mock_config = MagicMock()
        mock_config_path = Path("/fake/config.yaml")
        mock_checks = [MagicMock(name="Docker", status="✗", details="Not running", critical=True)]
        mock_failures = ["Docker is not running"]

        with patch("mcpbr.infrastructure.local.run_comprehensive_preflight") as mock_preflight:
            mock_preflight.return_value = (mock_checks, mock_failures)

            result = await provider.health_check(config=mock_config, config_path=mock_config_path)

            assert result["healthy"] is False
            assert len(result["failures"]) > 0

    @pytest.mark.asyncio
    async def test_all_methods_complete_without_error(self) -> None:
        """Integration test: verify all methods can be called in sequence."""
        provider = LocalProvider()

        # Setup
        await provider.setup()

        # Health check (with mocked preflight)
        mock_config = MagicMock()
        mock_config_path = Path("/fake/config.yaml")
        with patch("mcpbr.infrastructure.local.run_comprehensive_preflight") as mock_preflight:
            mock_preflight.return_value = ([], [])
            health = await provider.health_check(config=mock_config, config_path=mock_config_path)
            assert "healthy" in health

        # Cleanup
        await provider.cleanup()

        # All methods completed successfully
        assert True
