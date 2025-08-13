"""Core data models for relkit."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import tomllib
from .utils import run_git


@dataclass
class Output:
    """Structured output from commands for consistent display and testing."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    details: Optional[List[Dict[str, Any]]] = None
    next_steps: Optional[List[str]] = None


@dataclass
class Context:
    """Project context encapsulating all state."""

    type: str  # 'single', 'workspace', 'hybrid'
    name: str
    version: str
    packages: List[str] = field(default_factory=list)
    package_types: Dict[str, str] = field(
        default_factory=dict
    )  # package -> 'tool'|'library'
    root: Path = field(default_factory=Path.cwd)

    @classmethod
    def from_pyproject(cls, path: Optional[Path] = None) -> "Context":
        """Load context from pyproject.toml."""
        if path is None:
            path = Path.cwd()

        pyproject_path = path / "pyproject.toml"
        if not pyproject_path.exists():
            pyproject_path = path.parent / "pyproject.toml"
            if not pyproject_path.exists():
                raise FileNotFoundError("No pyproject.toml found")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})
        tool_uv = data.get("tool", {}).get("uv", {})

        # Determine project type
        if "workspace" in tool_uv:
            project_type = "workspace"
            workspace = tool_uv["workspace"]
            packages = workspace.get("members", [])
        elif tool_uv.get("package") is False:
            project_type = "single"
            packages = []
        else:
            project_type = "hybrid"
            packages = []

        return cls(
            type=project_type,
            name=project.get("name", path.name),
            version=project.get("version", "0.0.0"),
            packages=packages,
            root=pyproject_path.parent,
        )

    @property
    def is_workspace(self) -> bool:
        """Check if this is a workspace project."""
        return self.type in ("workspace", "hybrid")

    @property
    def is_single(self) -> bool:
        """Check if this is a single package project."""
        return self.type == "single"

    @property
    def last_tag(self) -> Optional[str]:
        """Get the most recent git tag."""
        result = run_git(["describe", "--tags", "--abbrev=0"], cwd=self.root)
        return result.stdout.strip() if result.returncode == 0 else None

    @property
    def commits_since_tag(self) -> int:
        """Count commits since last tag (or ALL commits if no tags)."""
        if self.last_tag:
            result = run_git(
                ["rev-list", f"{self.last_tag}..HEAD", "--count"], cwd=self.root
            )
        else:
            # First release - count all commits
            result = run_git(["rev-list", "HEAD", "--count"], cwd=self.root)
        return int(result.stdout.strip()) if result.returncode == 0 else 0

    @property
    def is_public(self) -> bool:
        """Check if package is intended for public release."""
        # Read pyproject.toml
        pyproject_path = self.root / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        classifiers = data.get("project", {}).get("classifiers", [])

        # Check for explicit private classifier
        if "Private :: Do Not Upload" in classifiers:
            return False

        # Check for OSI approved license (indicates public intent)
        for classifier in classifiers:
            if "License :: OSI Approved" in classifier:
                return True

        # Default to private for safety
        return False
