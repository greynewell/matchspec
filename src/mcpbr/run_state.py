"""Run state persistence for Azure evaluation runs.

Stores VM details so monitoring commands (status, logs, ssh, stop) can
operate on running evaluations.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    """Persistent state for an evaluation run on Azure."""

    vm_name: str
    vm_ip: str
    resource_group: str
    location: str
    ssh_key_path: str
    config_path: str
    started_at: str
    status: str = "running"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        """Save state to a JSON file.

        Args:
            path: File path to write state to.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "RunState | None":
        """Load state from a JSON file.

        Args:
            path: File path to read state from.

        Returns:
            RunState instance or None if file doesn't exist.
        """
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
