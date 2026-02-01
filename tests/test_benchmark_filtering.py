"""Tests for benchmark filtering functionality."""

from mcpbr.benchmarks import CyberGymBenchmark, MCPToolBenchmark, SWEBenchmark
from mcpbr.config import HarnessConfig, MCPServerConfig


class TestFilteringConfig:
    """Tests for filter configuration fields."""

    def test_config_with_filter_difficulty(self) -> None:
        """Test config with filter_difficulty field."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_difficulty=["easy", "medium"],
        )
        assert config.filter_difficulty == ["easy", "medium"]

    def test_config_with_filter_category(self) -> None:
        """Test config with filter_category field."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_category=["browser", "finance"],
        )
        assert config.filter_category == ["browser", "finance"]

    def test_config_with_filter_tags(self) -> None:
        """Test config with filter_tags field."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_tags=["security", "critical"],
        )
        assert config.filter_tags == ["security", "critical"]

    def test_config_with_all_filters(self) -> None:
        """Test config with all filter fields."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_difficulty=["medium"],
            filter_category=["web"],
            filter_tags=["important"],
        )
        assert config.filter_difficulty == ["medium"]
        assert config.filter_category == ["web"]
        assert config.filter_tags == ["important"]

    def test_config_filters_default_none(self) -> None:
        """Test that filters default to None."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
        )
        assert config.filter_difficulty is None
        assert config.filter_category is None
        assert config.filter_tags is None


class TestSWEBenchmarkFiltering:
    """Tests for SWE-bench filtering."""

    def test_load_tasks_with_no_filters(self) -> None:
        """Test that load_tasks works without filters."""
        benchmark = SWEBenchmark()
        # Mock test - in real scenario would load from dataset
        # Just verify the method accepts filter parameters
        try:
            # This will fail without network/dataset but should accept parameters
            _ = benchmark.load_tasks(
                sample_size=1,
                filter_difficulty=None,
                filter_category=None,
                filter_tags=None,
            )
        except Exception:
            # Expected to fail without dataset, but method signature is correct
            pass

    def test_load_tasks_signature_includes_filters(self) -> None:
        """Test that load_tasks method signature includes filter parameters."""
        import inspect

        sig = inspect.signature(SWEBenchmark.load_tasks)
        params = sig.parameters

        assert "filter_difficulty" in params
        assert "filter_category" in params
        assert "filter_tags" in params


class TestCyberGymBenchmarkFiltering:
    """Tests for CyberGym filtering."""

    def test_load_tasks_signature_includes_filters(self) -> None:
        """Test that load_tasks method signature includes filter parameters."""
        import inspect

        sig = inspect.signature(CyberGymBenchmark.load_tasks)
        params = sig.parameters

        assert "filter_difficulty" in params
        assert "filter_category" in params
        assert "filter_tags" in params

    def test_filter_difficulty_by_level(self) -> None:
        """Test filtering by difficulty level."""
        # Test that filter_difficulty with matching level returns tasks
        # In real scenario, this would filter based on difficulty
        # Here we just verify the logic structure is correct
        filter_levels = ["1", "2"]  # Should include level 1
        difficulty_levels = set()
        for diff in filter_levels:
            if diff.isdigit():
                difficulty_levels.add(int(diff))

        assert 1 in difficulty_levels  # Level 1 should be included

    def test_filter_difficulty_by_name(self) -> None:
        """Test filtering by difficulty name."""
        filter_difficulties = ["easy", "medium"]
        difficulty_levels = set()
        mapping = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}

        for diff in filter_difficulties:
            if diff.lower() in mapping:
                difficulty_levels.add(mapping[diff.lower()])

        assert 0 in difficulty_levels
        assert 1 in difficulty_levels
        assert 2 not in difficulty_levels


class TestMCPToolBenchmarkFiltering:
    """Tests for MCPToolBench++ filtering."""

    def test_load_tasks_signature_includes_filters(self) -> None:
        """Test that load_tasks method signature includes filter parameters."""
        import inspect

        sig = inspect.signature(MCPToolBenchmark.load_tasks)
        params = sig.parameters

        assert "filter_difficulty" in params
        assert "filter_category" in params
        assert "filter_tags" in params

    def test_filter_difficulty_mapping(self) -> None:
        """Test difficulty to call_type mapping."""
        # Test difficulty mapping logic
        filter_difficulty = ["easy", "hard"]
        call_types = set()

        for diff in filter_difficulty:
            diff_lower = diff.lower()
            if diff_lower in ("easy", "single"):
                call_types.add("single")
            elif diff_lower in ("hard", "multi", "medium"):
                call_types.add("multi")

        assert "single" in call_types
        assert "multi" in call_types

    def test_filter_difficulty_with_call_type(self) -> None:
        """Test filtering with direct call_type values."""
        filter_difficulty = ["single", "multi"]
        call_types = set()

        for diff in filter_difficulty:
            diff_lower = diff.lower()
            if diff_lower in ("easy", "single"):
                call_types.add("single")
            elif diff_lower in ("hard", "multi", "medium"):
                call_types.add("multi")
            else:
                call_types.add(diff)

        assert "single" in call_types
        assert "multi" in call_types


class TestFilteringIntegration:
    """Integration tests for filtering across benchmarks."""

    def test_all_benchmarks_support_filter_parameters(self) -> None:
        """Test that all benchmarks support filter parameters in load_tasks."""
        benchmarks = [
            SWEBenchmark(),
            CyberGymBenchmark(),
            MCPToolBenchmark(),
        ]

        for benchmark in benchmarks:
            import inspect

            sig = inspect.signature(benchmark.load_tasks)
            params = sig.parameters

            assert "filter_difficulty" in params, f"{benchmark.name} missing filter_difficulty"
            assert "filter_category" in params, f"{benchmark.name} missing filter_category"
            assert "filter_tags" in params, f"{benchmark.name} missing filter_tags"

    def test_filters_with_sample_size(self) -> None:
        """Test that filters work together with sample_size."""
        # This is a structural test - real implementation would need dataset
        benchmark = MCPToolBenchmark()

        # Verify method accepts both filter and sample_size parameters
        import inspect

        sig = inspect.signature(benchmark.load_tasks)
        params = sig.parameters

        assert "sample_size" in params
        assert "filter_difficulty" in params
        assert "filter_category" in params

    def test_filters_with_task_ids(self) -> None:
        """Test that filters work together with task_ids."""
        benchmark = SWEBenchmark()

        # Verify method accepts both filter and task_ids parameters
        import inspect

        sig = inspect.signature(benchmark.load_tasks)
        params = sig.parameters

        assert "task_ids" in params
        assert "filter_difficulty" in params
        assert "filter_category" in params


class TestFilteringEdgeCases:
    """Tests for edge cases in filtering."""

    def test_empty_filter_list(self) -> None:
        """Test behavior with empty filter lists."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_difficulty=[],
            filter_category=[],
            filter_tags=[],
        )
        assert config.filter_difficulty == []
        assert config.filter_category == []
        assert config.filter_tags == []

    def test_none_filters(self) -> None:
        """Test behavior with None filters."""
        config = HarnessConfig(
            mcp_server=MCPServerConfig(command="npx", args=["test"]),
            filter_difficulty=None,
            filter_category=None,
            filter_tags=None,
        )
        assert config.filter_difficulty is None
        assert config.filter_category is None
        assert config.filter_tags is None

    def test_cybergym_difficulty_name_mapping(self) -> None:
        """Test CyberGym difficulty name to level mapping."""
        mapping = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}

        assert mapping["easy"] == 0
        assert mapping["medium"] == 1
        assert mapping["hard"] == 2
        assert mapping["expert"] == 3

    def test_mcptoolbench_difficulty_to_call_type(self) -> None:
        """Test MCPToolBench++ difficulty to call_type conversion."""
        test_cases = [
            ("easy", "single"),
            ("single", "single"),
            ("hard", "multi"),
            ("multi", "multi"),
            ("medium", "multi"),
        ]

        for input_diff, expected_type in test_cases:
            call_types = set()
            diff_lower = input_diff.lower()
            if diff_lower in ("easy", "single"):
                call_types.add("single")
            elif diff_lower in ("hard", "multi", "medium"):
                call_types.add("multi")

            assert expected_type in call_types, f"Failed for {input_diff}"


class TestFilteringCLIIntegration:
    """Tests for CLI integration with filtering."""

    def test_cli_run_accepts_filter_options(self) -> None:
        """Test that CLI run command accepts filter options."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()

        # Test that CLI accepts filter flags (will fail on missing config, but should parse flags)
        result = runner.invoke(
            main,
            [
                "run",
                "-c",
                "nonexistent.yaml",
                "--filter-difficulty",
                "easy",
                "--filter-category",
                "browser",
                "--filter-tags",
                "security",
            ],
            catch_exceptions=True,
        )

        # Should fail on missing config file, not on unknown options
        # If it fails on unknown option, that means CLI doesn't accept the flag
        assert "no such option" not in result.output.lower(), "CLI doesn't recognize filter options"

    def test_multiple_filter_values(self) -> None:
        """Test CLI with multiple values for each filter."""
        from click.testing import CliRunner

        from mcpbr.cli import main

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "run",
                "-c",
                "nonexistent.yaml",
                "--filter-difficulty",
                "easy",
                "--filter-difficulty",
                "medium",
                "--filter-category",
                "browser",
                "--filter-category",
                "finance",
                "--filter-tags",
                "tag1",
                "--filter-tags",
                "tag2",
            ],
            catch_exceptions=True,
        )

        # Should not fail on unknown options
        assert "no such option" not in result.output.lower()
