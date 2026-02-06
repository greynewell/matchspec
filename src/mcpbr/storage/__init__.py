"""Storage backends for benchmark results."""

from .base import StorageBackend
from .sqlite_backend import SQLiteBackend

__all__ = ["StorageBackend", "SQLiteBackend"]
