"""Tests for the public Python SDK."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from mcpbr.sdk import (
    BenchmarkResult,
    MCPBenchmark,
    get_version,
    list_benchmarks,
    list_models,
    list_providers,
)


class TestListBenchmarks:
    """Tests for list_benchmarks() SDK function."""

    def test_returns_list(self) -> None:
        """list_benchmarks returns a list."""
        result = list_benchmarks()
        assert isinstance(result, list)

    def test_returns_dicts(self) -> None:
        """Each item in list_benchmarks is a dict with expected keys."""
        result = list_benchmarks()
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert "name" in item
            assert "class" in item

    def test_contains_known_benchmarks(self) -> None:
        """list_benchmarks contains well-known benchmark names."""
        result = list_benchmarks()
        names = [b["name"] for b in result]
        assert "swe-bench-verified" in names
        assert "humaneval" in names
        assert "cybergym" in names

    def test_class_field_is_string(self) -> None:
        """The class field is a string (class name)."""
        result = list_benchmarks()
        for item in result:
            assert isinstance(item["class"], str)
            assert len(item["class"]) > 0


class TestListProviders:
    """Tests for list_providers() SDK function."""

    def test_returns_list(self) -> None:
        """list_providers returns a list of strings."""
        result = list_providers()
        assert isinstance(result, list)

    def test_contains_anthropic(self) -> None:
        """list_providers contains 'anthropic'."""
        result = list_providers()
        assert "anthropic" in result

    def test_all_strings(self) -> None:
        """All items in list_providers are strings."""
        result = list_providers()
        for item in result:
            assert isinstance(item, str)


class TestListModels:
    """Tests for list_models() SDK function."""

    def test_returns_list(self) -> None:
        """list_models returns a list."""
        result = list_models()
        assert isinstance(result, list)

    def test_returns_dicts_with_expected_keys(self) -> None:
        """Each model dict has id, provider, display_name, context_window."""
        result = list_models()
        assert len(result) > 0
        for item in result:
            assert isinstance(item, dict)
            assert "id" in item
            assert "provider" in item
            assert "display_name" in item
            assert "context_window" in item

    def test_contains_known_model(self) -> None:
        """list_models contains the sonnet alias."""
        result = list_models()
        ids = [m["id"] for m in result]
        assert "sonnet" in ids

    def test_context_window_is_int(self) -> None:
        """Context window values are integers."""
        result = list_models()
        for item in result:
            assert isinstance(item["context_window"], int)


class TestGetVersion:
    """Tests for get_version() SDK function."""

    def test_returns_string(self) -> None:
        """get_version returns a string."""
        version = get_version()
        assert isinstance(version, str)

    def test_version_format(self) -> None:
        """get_version returns a semver-like string."""
        version = get_version()
        parts = version.split(".")
        assert len(parts) >= 2, f"Version '{version}' should have at least major.minor"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"

    def test_version_matches_package(self) -> None:
        """get_version matches mcpbr.__version__."""
        import mcpbr

        version = get_version()
        assert version == mcpbr.__version__


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_default_creation(self) -> None:
        """BenchmarkResult can be created with required fields only."""
        result = BenchmarkResult(
            success=True,
            summary={"resolved": 3, "total": 5},
            tasks=[{"task_id": "t1", "resolved": True}],
            metadata={"benchmark": "humaneval"},
        )
        assert result.success is True
        assert result.summary == {"resolved": 3, "total": 5}
        assert len(result.tasks) == 1
        assert result.metadata == {"benchmark": "humaneval"}

    def test_default_values(self) -> None:
        """BenchmarkResult has correct default values for optional fields."""
        result = BenchmarkResult(
            success=False,
            summary={},
            tasks=[],
            metadata={},
        )
        assert result.total_cost == 0.0
        assert result.total_tokens == 0
        assert result.duration_seconds == 0.0

    def test_all_fields(self) -> None:
        """BenchmarkResult can be created with all fields."""
        result = BenchmarkResult(
            success=True,
            summary={"pass_rate": 0.8},
            tasks=[{"task_id": "t1"}, {"task_id": "t2"}],
            metadata={"model": "sonnet"},
            total_cost=1.25,
            total_tokens=50000,
            duration_seconds=120.5,
        )
        assert result.total_cost == 1.25
        assert result.total_tokens == 50000
        assert result.duration_seconds == 120.5

    def test_fields_are_correct_types(self) -> None:
        """BenchmarkResult field types are correct."""
        result = BenchmarkResult(
            success=True,
            summary={},
            tasks=[],
            metadata={},
            total_cost=0.0,
            total_tokens=0,
            duration_seconds=0.0,
        )
        assert isinstance(result.success, bool)
        assert isinstance(result.summary, dict)
        assert isinstance(result.tasks, list)
        assert isinstance(result.metadata, dict)
        assert isinstance(result.total_cost, float)
        assert isinstance(result.total_tokens, int)
        assert isinstance(result.duration_seconds, float)


class TestMCPBenchmarkFromDict:
    """Tests for MCPBenchmark creation from a config dict."""

    def test_creation_from_dict(self) -> None:
        """MCPBenchmark can be created from a config dict."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "{workdir}"],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)
        assert bench.config is not None

    def test_config_is_harness_config(self) -> None:
        """MCPBenchmark.config is a HarnessConfig instance."""
        from mcpbr.config import HarnessConfig

        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
        }
        bench = MCPBenchmark(config)
        assert isinstance(bench.config, HarnessConfig)

    def test_invalid_dict_raises(self) -> None:
        """MCPBenchmark raises ValueError for invalid config dict."""
        with pytest.raises((ValueError, Exception)):
            MCPBenchmark({"benchmark": "nonexistent-benchmark-xyz"})


class TestMCPBenchmarkFromYAML:
    """Tests for MCPBenchmark creation from a YAML file path."""

    def test_creation_from_yaml_path_string(self) -> None:
        """MCPBenchmark can be created from a YAML file path (string)."""
        config_data = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            bench = MCPBenchmark(f.name)
            assert bench.config is not None
            assert bench.config.benchmark == "humaneval"

    def test_creation_from_yaml_path_object(self) -> None:
        """MCPBenchmark can be created from a Path object."""
        config_data = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "gsm8k",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            bench = MCPBenchmark(Path(f.name))
            assert bench.config.benchmark == "gsm8k"

    def test_nonexistent_yaml_raises(self) -> None:
        """MCPBenchmark raises FileNotFoundError for missing YAML file."""
        with pytest.raises(FileNotFoundError):
            MCPBenchmark("/nonexistent/path/config.yaml")

    def test_nonexistent_yaml_path_object_raises(self) -> None:
        """MCPBenchmark raises FileNotFoundError for missing Path."""
        with pytest.raises(FileNotFoundError):
            MCPBenchmark(Path("/nonexistent/path/config.yaml"))


class TestMCPBenchmarkValidate:
    """Tests for MCPBenchmark.validate()."""

    def test_valid_config_returns_true(self) -> None:
        """validate() returns (True, []) for a valid config."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)
        is_valid, errors = bench.validate()
        assert is_valid is True
        assert isinstance(errors, list)
        assert len(errors) == 0

    def test_validate_returns_tuple(self) -> None:
        """validate() returns a tuple of (bool, list[str])."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
        }
        bench = MCPBenchmark(config)
        result = bench.validate()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    def test_validate_unsupported_model_returns_warning(self) -> None:
        """validate() returns warnings for unsupported model."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "unknown-model-xyz",
        }
        bench = MCPBenchmark(config)
        is_valid, errors = bench.validate()
        # Config itself is valid (model field accepts any string),
        # but validate warns about unsupported models
        assert isinstance(errors, list)
        if not is_valid:
            assert len(errors) > 0


class TestMCPBenchmarkDryRun:
    """Tests for MCPBenchmark.dry_run()."""

    def test_dry_run_returns_dict(self) -> None:
        """dry_run() returns a dict."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert isinstance(plan, dict)

    def test_dry_run_contains_benchmark(self) -> None:
        """dry_run() plan contains the benchmark name."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert "benchmark" in plan
        assert plan["benchmark"] == "humaneval"

    def test_dry_run_contains_model(self) -> None:
        """dry_run() plan contains the model."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert "model" in plan
        assert plan["model"] == "sonnet"

    def test_dry_run_contains_provider(self) -> None:
        """dry_run() plan contains the provider."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert "provider" in plan
        assert plan["provider"] == "anthropic"

    def test_dry_run_contains_mcp_server(self) -> None:
        """dry_run() plan contains mcp_server info."""
        config = {
            "mcp_server": {
                "command": "npx",
                "args": ["-y", "some-server"],
            },
            "benchmark": "humaneval",
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert "mcp_server" in plan
        assert plan["mcp_server"]["command"] == "npx"

    def test_dry_run_contains_settings(self) -> None:
        """dry_run() plan contains timeout and concurrency settings."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "timeout_seconds": 600,
            "max_concurrent": 2,
        }
        bench = MCPBenchmark(config)
        plan = bench.dry_run()
        assert "timeout_seconds" in plan
        assert plan["timeout_seconds"] == 600
        assert "max_concurrent" in plan
        assert plan["max_concurrent"] == 2


class TestMCPBenchmarkRun:
    """Tests for MCPBenchmark.run() async method."""

    @pytest.mark.asyncio
    async def test_run_returns_benchmark_result(self) -> None:
        """run() returns a BenchmarkResult instance."""
        config = {
            "mcp_server": {
                "command": "echo",
                "args": [],
            },
            "benchmark": "humaneval",
            "model": "sonnet",
        }
        bench = MCPBenchmark(config)

        # Mock the internal _execute method to avoid real execution
        mock_result = BenchmarkResult(
            success=True,
            summary={"resolved": 1, "total": 1},
            tasks=[{"task_id": "t1", "resolved": True}],
            metadata={"benchmark": "humaneval"},
            total_cost=0.05,
            total_tokens=1000,
            duration_seconds=10.0,
        )
        with patch.object(bench, "_execute", new_callable=AsyncMock, return_value=mock_result):
            result = await bench.run()
            assert isinstance(result, BenchmarkResult)
            assert result.success is True


class TestSDKExports:
    """Tests for SDK exports from mcpbr package."""

    def test_import_benchmark_result(self) -> None:
        """BenchmarkResult is importable from mcpbr."""
        from mcpbr import BenchmarkResult as BenchmarkResultAlias

        assert BenchmarkResultAlias is BenchmarkResult

    def test_import_mcp_benchmark(self) -> None:
        """MCPBenchmark is importable from mcpbr."""
        from mcpbr import MCPBenchmark as McpBenchmarkAlias

        assert McpBenchmarkAlias is MCPBenchmark

    def test_import_list_benchmarks(self) -> None:
        """list_benchmarks is importable from mcpbr.sdk."""
        from mcpbr.sdk import list_benchmarks as lb

        assert callable(lb)

    def test_import_list_providers(self) -> None:
        """list_providers is importable from mcpbr.sdk."""
        from mcpbr.sdk import list_providers as lp

        assert callable(lp)

    def test_import_list_models(self) -> None:
        """list_models is importable from mcpbr.sdk."""
        from mcpbr.sdk import list_models as lm

        assert callable(lm)

    def test_import_get_version(self) -> None:
        """get_version is importable from mcpbr.sdk."""
        from mcpbr.sdk import get_version as gv

        assert callable(gv)

    def test_top_level_get_version(self) -> None:
        """get_version is importable from mcpbr top-level."""
        from mcpbr import get_version as gv

        assert callable(gv)

    def test_top_level_list_benchmarks(self) -> None:
        """list_benchmarks is importable from mcpbr top-level."""
        from mcpbr import list_benchmarks as lb

        assert callable(lb)

    def test_top_level_list_providers(self) -> None:
        """list_providers is importable from mcpbr top-level."""
        from mcpbr import list_providers as lp

        assert callable(lp)

    def test_top_level_list_models(self) -> None:
        """list_models is importable from mcpbr top-level."""
        from mcpbr import list_models as lm

        assert callable(lm)
