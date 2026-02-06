"""Tests for plugin registry."""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcpbr.plugin_registry import (
    PluginEntry,
    Registry,
    RegistryClient,
    RegistryError,
    generate_registry_entry,
)


class TestPluginEntry:
    """Tests for PluginEntry dataclass."""

    def test_from_dict(self) -> None:
        """Test creating PluginEntry from dict."""
        data = {
            "name": "test-plugin",
            "description": "A test plugin",
            "version": "1.0.0",
            "homepage": "https://example.com",
            "tags": ["test"],
        }
        entry = PluginEntry.from_dict(data)
        assert entry.name == "test-plugin"
        assert entry.description == "A test plugin"
        assert entry.version == "1.0.0"
        assert entry.tags == ["test"]

    def test_from_dict_defaults(self) -> None:
        """Test PluginEntry defaults for missing fields."""
        entry = PluginEntry.from_dict({})
        assert entry.name == ""
        assert entry.benchmark_type == "custom"
        assert entry.tags == []

    def test_to_dict(self) -> None:
        """Test converting to dict."""
        entry = PluginEntry(
            name="test",
            description="desc",
            version="1.0",
            homepage="https://example.com",
        )
        d = entry.to_dict()
        assert d["name"] == "test"
        assert "tags" in d

    def test_roundtrip(self) -> None:
        """Test dict roundtrip."""
        original = {
            "name": "test",
            "description": "desc",
            "version": "1.0",
            "homepage": "https://example.com",
            "tags": ["a", "b"],
        }
        entry = PluginEntry.from_dict(original)
        result = entry.to_dict()
        assert result["name"] == original["name"]
        assert result["tags"] == original["tags"]


class TestRegistry:
    """Tests for Registry class."""

    def _sample_registry(self) -> Registry:
        data = {
            "version": "1",
            "plugins": [
                {
                    "name": "mcpbr",
                    "description": "MCP Benchmark Runner",
                    "version": "0.10.0",
                    "homepage": "https://github.com/greynewell/mcpbr",
                    "tags": ["mcp", "benchmark"],
                },
                {
                    "name": "eval-harness",
                    "description": "General evaluation harness",
                    "version": "2.0.0",
                    "homepage": "https://example.com",
                    "tags": ["evaluation", "harness"],
                },
            ],
        }
        return Registry.from_dict(data)

    def test_from_dict(self) -> None:
        """Test creating registry from dict."""
        reg = self._sample_registry()
        assert reg.version == "1"
        assert len(reg.plugins) == 2

    def test_to_dict(self) -> None:
        """Test converting registry to dict."""
        reg = self._sample_registry()
        d = reg.to_dict()
        assert d["version"] == "1"
        assert len(d["plugins"]) == 2

    def test_search_by_name(self) -> None:
        """Test searching by name."""
        reg = self._sample_registry()
        results = reg.search("mcpbr")
        assert len(results) == 1
        assert results[0].name == "mcpbr"

    def test_search_by_description(self) -> None:
        """Test searching by description."""
        reg = self._sample_registry()
        results = reg.search("evaluation")
        assert len(results) == 1
        assert results[0].name == "eval-harness"

    def test_search_by_tag(self) -> None:
        """Test searching by tag."""
        reg = self._sample_registry()
        results = reg.search("benchmark")
        assert len(results) == 1

    def test_search_case_insensitive(self) -> None:
        """Test case-insensitive search."""
        reg = self._sample_registry()
        results = reg.search("MCP")
        assert len(results) == 1

    def test_search_no_results(self) -> None:
        """Test search with no matches."""
        reg = self._sample_registry()
        results = reg.search("nonexistent")
        assert len(results) == 0

    def test_get_by_name(self) -> None:
        """Test getting plugin by exact name."""
        reg = self._sample_registry()
        plugin = reg.get_by_name("mcpbr")
        assert plugin is not None
        assert plugin.name == "mcpbr"

    def test_get_by_name_not_found(self) -> None:
        """Test getting non-existent plugin."""
        reg = self._sample_registry()
        assert reg.get_by_name("missing") is None

    def test_empty_registry(self) -> None:
        """Test empty registry."""
        reg = Registry.from_dict({})
        assert len(reg.plugins) == 0
        assert reg.search("anything") == []


class TestRegistryClient:
    """Tests for RegistryClient."""

    @patch("mcpbr.plugin_registry.urllib.request.urlopen")
    def test_fetch_success(self, mock_urlopen: MagicMock) -> None:
        """Test successful registry fetch."""
        registry_data = {
            "version": "1",
            "plugins": [{"name": "test", "description": "d", "version": "1.0", "homepage": "h"}],
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(registry_data).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client = RegistryClient(registry_url="https://example.com/registry.json")
        registry = client.fetch()
        assert len(registry.plugins) == 1

    @patch("mcpbr.plugin_registry.urllib.request.urlopen")
    def test_fetch_failure(self, mock_urlopen: MagicMock) -> None:
        """Test registry fetch failure."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        client = RegistryClient()
        with pytest.raises(RegistryError, match="Failed to fetch"):
            client.fetch()

    @patch("mcpbr.plugin_registry.urllib.request.urlopen")
    def test_search_fetches_if_no_cache(self, mock_urlopen: MagicMock) -> None:
        """Test that search triggers fetch if not cached."""
        registry_data = {"version": "1", "plugins": []}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(registry_data).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client = RegistryClient()
        results = client.search("test")
        assert results == []
        mock_urlopen.assert_called_once()

    @patch("mcpbr.plugin_registry.urllib.request.urlopen")
    def test_list_all(self, mock_urlopen: MagicMock) -> None:
        """Test listing all plugins."""
        registry_data = {
            "version": "1",
            "plugins": [
                {"name": "a", "description": "", "version": "1", "homepage": ""},
                {"name": "b", "description": "", "version": "1", "homepage": ""},
            ],
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(registry_data).encode("utf-8")
        mock_urlopen.return_value = mock_response

        client = RegistryClient()
        plugins = client.list_all()
        assert len(plugins) == 2


class TestGenerateRegistryEntry:
    """Tests for generate_registry_entry."""

    def test_generates_valid_entry(self) -> None:
        """Test entry generation."""
        entry = generate_registry_entry()
        assert entry["name"] == "mcpbr"
        assert "version" in entry
        assert "homepage" in entry
        assert isinstance(entry["supported_benchmarks"], list)
        assert len(entry["supported_benchmarks"]) > 0

    def test_entry_has_required_fields(self) -> None:
        """Test all required fields are present."""
        entry = generate_registry_entry()
        required_fields = ["name", "description", "version", "homepage", "tags"]
        for field in required_fields:
            assert field in entry, f"Missing field: {field}"
