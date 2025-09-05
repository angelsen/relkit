"""Core data models for relkit."""

from dataclasses import dataclass
from typing import List, Dict, Any

# Import WorkspaceContext as Context for backward compatibility
from .workspace import WorkspaceContext as Context

# Export for other modules
__all__ = ["Output", "Context"]


@dataclass
class Output:
    """Structured output from commands for consistent display and testing."""

    success: bool
    message: str
    data: Dict[str, Any] | None = None
    details: List[Dict[str, Any]] | None = None
    next_steps: List[str] | None = None
