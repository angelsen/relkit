"""Core data models for relkit."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Import WorkspaceContext as Context for backward compatibility
from .workspace import WorkspaceContext as Context

# Export for other modules
__all__ = ["Output", "Context"]


@dataclass
class Output:
    """Structured output from commands for consistent display and testing."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    details: Optional[List[Dict[str, Any]]] = None
    next_steps: Optional[List[str]] = None
