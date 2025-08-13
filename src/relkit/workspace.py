"""Workspace and package management for relkit."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import tomllib


@dataclass
class Package:
    """A single package that can be released."""

    name: str
    version: str
    path: Path
    is_root: bool = False  # True if this is the root package

    @property
    def changelog_path(self) -> Path:
        """Get changelog path for this package."""
        return self.path / "CHANGELOG.md"

    @property
    def pyproject_path(self) -> Path:
        """Get pyproject.toml path for this package."""
        return self.path / "pyproject.toml"

    @property
    def dist_path(self) -> Path:
        """Get dist directory path for this package."""
        return self.path / "dist"

    @property
    def tag_name(self) -> str:
        """Get tag name for this package version."""
        # Root/single packages use v1.0.0, workspace member packages use name-v1.0.0
        if self.is_root:
            return f"v{self.version}"
        return f"{self.name}-v{self.version}"

    @property
    def import_name(self) -> str:
        """Get the Python import name (package name with underscores)."""
        return self.name.replace("-", "_")

    def get_last_tag(self) -> Optional[str]:
        """Get the last tag for this specific package."""
        from .utils import run_git

        # For workspace member packages, look for tags with package prefix
        if not self.is_root:
            pattern = f"{self.name}-v*"
            result = run_git(
                ["tag", "-l", pattern, "--sort=-version:refname"], cwd=self.path.parent
            )
            if result.returncode == 0 and result.stdout.strip():
                tags = result.stdout.strip().split("\n")
                return tags[0] if tags else None
        else:
            # For root/single package, look for plain version tags
            result = run_git(["describe", "--tags", "--abbrev=0"], cwd=self.path)
            if result.returncode == 0:
                tag = result.stdout.strip()
                # Only return if it's a version tag (not a package tag)
                if tag.startswith("v") and "-v" not in tag:
                    return tag
        return None


@dataclass
class WorkspaceContext:
    """Context that understands workspaces but keeps it simple."""

    root: Path
    has_workspace: bool
    packages: Dict[str, Package]  # name -> Package

    @classmethod
    def from_path(cls, path: Optional[Path] = None) -> "WorkspaceContext":
        """Load context, discover packages if workspace."""
        if path is None:
            path = Path.cwd()

        # Find root pyproject.toml
        root_pyproject = cls._find_root_pyproject(path)
        if not root_pyproject:
            raise FileNotFoundError("No pyproject.toml found")

        with open(root_pyproject, "rb") as f:
            data = tomllib.load(f)

        root_path = root_pyproject.parent
        has_workspace = "workspace" in data.get("tool", {}).get("uv", {})
        packages = {}

        # Always add root if it has [project]
        if "project" in data:
            project = data["project"]
            root_name = project.get("name", root_path.name)
            packages[root_name] = Package(
                name=root_name,
                version=project.get("version", "0.0.0"),
                path=root_path,
                is_root=True,  # Mark as root package
            )
            # Also add _root alias for convenience
            packages["_root"] = packages[root_name]

        # Add workspace members if they exist
        if has_workspace:
            workspace_config = data["tool"]["uv"]["workspace"]
            members = workspace_config.get("members", [])

            for pattern in members:
                # Handle both literal paths and glob patterns
                if "*" in pattern:
                    member_paths = list(root_path.glob(pattern))
                else:
                    member_path = root_path / pattern
                    member_paths = [member_path] if member_path.exists() else []

                for pkg_path in member_paths:
                    pkg_pyproject = pkg_path / "pyproject.toml"
                    if pkg_pyproject.exists():
                        with open(pkg_pyproject, "rb") as f:
                            pkg_data = tomllib.load(f)

                        if "project" in pkg_data:
                            pkg_project = pkg_data["project"]
                            pkg_name = pkg_project.get("name", pkg_path.name)
                            packages[pkg_name] = Package(
                                name=pkg_name,
                                version=pkg_project.get("version", "0.0.0"),
                                path=pkg_path,
                            )

        return cls(root=root_path, has_workspace=has_workspace, packages=packages)

    @staticmethod
    def _find_root_pyproject(start_path: Path) -> Optional[Path]:
        """Find the root pyproject.toml (with workspace or single package)."""
        current = start_path
        if not current.is_dir():
            current = current.parent

        while current != current.parent:
            pyproject = current / "pyproject.toml"
            if pyproject.exists():
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                # This is a root if it has workspace config or if no parent has pyproject
                if "workspace" in data.get("tool", {}).get("uv", {}):
                    return pyproject
                # Check if parent has pyproject.toml
                parent_pyproject = current.parent / "pyproject.toml"
                if not parent_pyproject.exists():
                    return pyproject
            current = current.parent

        # Check the root directory
        if (Path("/") / "pyproject.toml").exists():
            return Path("/") / "pyproject.toml"

        return None

    @property
    def is_single(self) -> bool:
        """Check if this is a single package project."""
        # Single package = only one real package (may have _root alias)
        real_packages = [p for p in self.packages.keys() if p != "_root"]
        return len(real_packages) == 1 and not self.has_workspace

    def get_package(self, name: Optional[str] = None) -> Optional[Package]:
        """Get a package by name, with smart defaults."""
        if not name:
            # If single package, return it
            if self.is_single:
                return list(self.packages.values())[0]
            return None

        # Direct lookup
        if name in self.packages:
            return self.packages[name]

        # Check if asking for root with the actual name
        if "_root" in self.packages and self.packages["_root"].name == name:
            return self.packages["_root"]

        return None

    def require_package(self, name: Optional[str] = None) -> Package:
        """Get a package or raise an error with helpful message."""

        pkg = self.get_package(name)
        if pkg:
            return pkg

        if self.is_single:
            # Should not happen, but be defensive
            raise ValueError("Single package project has no packages")

        if not name:
            # Workspace but no package specified
            available = [p for p in self.packages.keys() if p != "_root"]
            raise ValueError(
                f"Workspace requires --package. Available: {', '.join(available)}"
            )
        else:
            # Package not found
            available = [p for p in self.packages.keys() if p != "_root"]
            raise ValueError(
                f"Package '{name}' not found. Available: {', '.join(available)}"
            )

    @property
    def is_public(self) -> bool:
        """Check if root package is public (for backward compat)."""
        # Only check root package
        root_pkg = self.packages.get("_root")
        if not root_pkg:
            return False

        with open(root_pkg.pyproject_path, "rb") as f:
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

    # Compatibility properties for gradual migration
    @property
    def name(self) -> str:
        """Get root package name for backward compat."""
        root = self.packages.get("_root")
        return root.name if root else "unknown"

    @property
    def version(self) -> str:
        """Get root package version for backward compat."""
        root = self.packages.get("_root")
        return root.version if root else "0.0.0"

    @property
    def type(self) -> str:
        """Get project type for backward compat."""
        if self.has_workspace:
            if "_root" in self.packages:
                return "hybrid"
            return "workspace"
        return "single"

    @property
    def last_tag(self) -> Optional[str]:
        """Get last tag for root package (backward compat)."""
        root = self.packages.get("_root")
        return root.get_last_tag() if root else None

    @property
    def commits_since_tag(self) -> int:
        """Count commits since last tag (backward compat)."""
        from .utils import run_git

        last_tag = self.last_tag
        if last_tag:
            result = run_git(
                ["rev-list", f"{last_tag}..HEAD", "--count"], cwd=self.root
            )
        else:
            result = run_git(["rev-list", "HEAD", "--count"], cwd=self.root)
        return int(result.stdout.strip()) if result.returncode == 0 else 0

    @property
    def is_workspace(self) -> bool:
        """Check if this has workspace config."""
        return self.has_workspace

    def get_dist_path(self, package: Optional[str] = None) -> Path:
        """Get the dist directory path for a package or root."""
        if self.has_workspace and package:
            pkg = self.require_package(package)
            return pkg.dist_path
        return self.root / "dist"

    def get_package_context(self, package: Optional[str] = None):
        """
        Get package-specific context (package object, paths, version).
        Returns a tuple of (Package, changelog_path, version, tag_name).
        """
        if self.has_workspace and package:
            pkg = self.require_package(package)
            return pkg, pkg.changelog_path, pkg.version, pkg.tag_name
        else:
            # For single packages or root
            pkg = self.get_package()
            if pkg:
                return pkg, pkg.changelog_path, pkg.version, pkg.tag_name
            # Fallback for backward compat
            return None, self.root / "CHANGELOG.md", self.version, f"v{self.version}"
