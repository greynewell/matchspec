"""Plugin registry client for discovering and registering MCP server benchmarks.

Provides functionality to:
- Search for available benchmark plugins from a registry
- Register mcpbr as a benchmark tool
- Discover MCP servers that have benchmark suites

The registry uses a simple JSON-based format that can be hosted
on any static file server or GitHub repository.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default registry URL (can be overridden via config)
DEFAULT_REGISTRY_URL = "https://raw.githubusercontent.com/greynewell/mcpbr/main/registry.json"


@dataclass
class PluginEntry:
    """A single plugin entry in the registry."""

    name: str
    description: str
    version: str
    homepage: str
    benchmark_type: str = "custom"
    tags: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    supported_benchmarks: list[str] = field(default_factory=list)
    author: str = ""
    license: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginEntry":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", ""),
            homepage=data.get("homepage", ""),
            benchmark_type=data.get("benchmark_type", "custom"),
            tags=data.get("tags", []),
            config_schema=data.get("config_schema", {}),
            supported_benchmarks=data.get("supported_benchmarks", []),
            author=data.get("author", ""),
            license=data.get("license", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "homepage": self.homepage,
            "benchmark_type": self.benchmark_type,
            "tags": self.tags,
            "config_schema": self.config_schema,
            "supported_benchmarks": self.supported_benchmarks,
            "author": self.author,
            "license": self.license,
        }


@dataclass
class Registry:
    """Plugin registry containing available benchmark plugins."""

    version: str = "1"
    plugins: list[PluginEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Registry":
        """Create from dictionary."""
        plugins = [PluginEntry.from_dict(p) for p in data.get("plugins", [])]
        return cls(version=data.get("version", "1"), plugins=plugins)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "plugins": [p.to_dict() for p in self.plugins],
        }

    def search(self, query: str) -> list[PluginEntry]:
        """Search plugins by name, description, or tags.

        Args:
            query: Search term.

        Returns:
            Matching plugins.
        """
        query_lower = query.lower()
        results = []
        for plugin in self.plugins:
            if (
                query_lower in plugin.name.lower()
                or query_lower in plugin.description.lower()
                or any(query_lower in tag.lower() for tag in plugin.tags)
            ):
                results.append(plugin)
        return results

    def get_by_name(self, name: str) -> PluginEntry | None:
        """Get a plugin by exact name.

        Args:
            name: Plugin name.

        Returns:
            Plugin entry or None if not found.
        """
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None


class RegistryClient:
    """Client for interacting with the plugin registry."""

    def __init__(self, registry_url: str = DEFAULT_REGISTRY_URL, timeout: int = 30) -> None:
        """Initialize registry client.

        Args:
            registry_url: URL of the registry JSON file.
            timeout: HTTP request timeout in seconds.
        """
        self.registry_url = registry_url
        self.timeout = timeout
        self._cache: Registry | None = None

    def fetch(self) -> Registry:
        """Fetch the registry from the remote URL.

        Returns:
            Registry object.

        Raises:
            RegistryError: If the fetch fails.
        """
        try:
            req = urllib.request.Request(
                self.registry_url,
                headers={"Accept": "application/json", "User-Agent": "mcpbr"},
            )
            response = urllib.request.urlopen(req, timeout=self.timeout)
            data = json.loads(response.read().decode("utf-8"))
            self._cache = Registry.from_dict(data)
            return self._cache
        except urllib.error.URLError as e:
            raise RegistryError(f"Failed to fetch registry: {e}") from e
        except json.JSONDecodeError as e:
            raise RegistryError(f"Invalid registry format: {e}") from e

    def search(self, query: str) -> list[PluginEntry]:
        """Search for plugins in the registry.

        Args:
            query: Search query.

        Returns:
            List of matching plugins.
        """
        registry = self._cache or self.fetch()
        return registry.search(query)

    def list_all(self) -> list[PluginEntry]:
        """List all plugins in the registry.

        Returns:
            List of all plugins.
        """
        registry = self._cache or self.fetch()
        return registry.plugins


class RegistryError(RuntimeError):
    """Raised when a registry operation fails."""

    pass


def generate_registry_entry() -> dict[str, Any]:
    """Generate a registry entry for mcpbr itself.

    Returns:
        Dictionary suitable for inclusion in a plugin registry.
    """
    from mcpbr import __version__

    return {
        "name": "mcpbr",
        "description": "MCP Benchmark Runner - evaluate MCP servers against standard benchmarks",
        "version": __version__,
        "homepage": "https://github.com/greynewell/mcpbr",
        "benchmark_type": "multi",
        "tags": [
            "mcp",
            "benchmark",
            "evaluation",
            "swe-bench",
            "humaneval",
            "testing",
        ],
        "supported_benchmarks": [
            "swe-bench-lite",
            "swe-bench-full",
            "swe-bench-verified",
            "humaneval",
            "mbpp",
            "gsm8k",
            "custom",
        ],
        "author": "Grey Newell",
        "license": "MIT",
    }
