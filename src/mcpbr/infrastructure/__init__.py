"""Infrastructure provider abstraction layer for mcpbr.

This module provides an abstraction layer for running evaluations on different
infrastructure providers (local, Azure VMs, etc.).
"""

from .base import InfrastructureProvider
from .local import LocalProvider
from .manager import InfrastructureManager

__all__ = ["InfrastructureManager", "InfrastructureProvider", "LocalProvider"]
