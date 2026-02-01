"""Tests for InfrastructureProvider abstract base class."""

import pytest

from mcpbr.infrastructure.base import InfrastructureProvider


class ConcreteProvider(InfrastructureProvider):
    """Concrete implementation for testing abstract methods."""

    async def setup(self) -> None:
        """Test implementation."""
        pass

    async def run_evaluation(self, config, run_mcp: bool, run_baseline: bool):
        """Test implementation."""
        pass

    async def collect_artifacts(self, output_dir):
        """Test implementation."""
        pass

    async def cleanup(self, force: bool = False) -> None:
        """Test implementation."""
        pass

    async def health_check(self):
        """Test implementation."""
        pass


class IncompleteProvider(InfrastructureProvider):
    """Provider missing some abstract methods."""

    async def setup(self) -> None:
        """Test implementation."""
        pass


class TestInfrastructureProvider:
    """Test InfrastructureProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """Test that abstract class cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            InfrastructureProvider()

    def test_concrete_implementation_can_be_instantiated(self) -> None:
        """Test that concrete implementation can be instantiated."""
        provider = ConcreteProvider()
        assert isinstance(provider, InfrastructureProvider)

    def test_incomplete_implementation_raises_error(self) -> None:
        """Test that incomplete implementation cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteProvider()

    def test_has_setup_method(self) -> None:
        """Test that setup method is defined."""
        provider = ConcreteProvider()
        assert hasattr(provider, "setup")
        assert callable(provider.setup)

    def test_has_run_evaluation_method(self) -> None:
        """Test that run_evaluation method is defined."""
        provider = ConcreteProvider()
        assert hasattr(provider, "run_evaluation")
        assert callable(provider.run_evaluation)

    def test_has_collect_artifacts_method(self) -> None:
        """Test that collect_artifacts method is defined."""
        provider = ConcreteProvider()
        assert hasattr(provider, "collect_artifacts")
        assert callable(provider.collect_artifacts)

    def test_has_cleanup_method(self) -> None:
        """Test that cleanup method is defined."""
        provider = ConcreteProvider()
        assert hasattr(provider, "cleanup")
        assert callable(provider.cleanup)

    def test_has_health_check_method(self) -> None:
        """Test that health_check method is defined."""
        provider = ConcreteProvider()
        assert hasattr(provider, "health_check")
        assert callable(provider.health_check)

    @pytest.mark.asyncio
    async def test_all_methods_are_async(self) -> None:
        """Test that all abstract methods are async."""
        import inspect

        provider = ConcreteProvider()

        assert inspect.iscoroutinefunction(provider.setup)
        assert inspect.iscoroutinefunction(provider.run_evaluation)
        assert inspect.iscoroutinefunction(provider.collect_artifacts)
        assert inspect.iscoroutinefunction(provider.cleanup)
        assert inspect.iscoroutinefunction(provider.health_check)
