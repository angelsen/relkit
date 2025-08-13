"""Changelog management commands."""

from typing import Optional
from pathlib import Path
from datetime import date
from ..decorators import command
from ..models import Output, Context
from ..utils import get_workspace_packages


CHANGELOG_TEMPLATE = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
<!-- Example: - New API endpoint for user authentication -->
<!-- Example: - Support for Python 3.12 -->

### Changed
<!-- Example: - Improved error messages for validation failures -->
<!-- Example: - Updated dependencies to latest versions -->

### Fixed
<!-- Example: - Memory leak in worker process -->
<!-- Example: - Incorrect handling of UTF-8 file names -->

### Removed
<!-- Example: - Deprecated legacy API endpoints -->
<!-- Example: - Support for Python 3.7 -->

<!-- 
When you run 'relkit bump', the [Unreleased] section will automatically 
become the new version section. Make sure to add your changes above!
-->
"""


@command("init-changelog", "Create CHANGELOG.md with Unreleased section")
def init_changelog(ctx: Context, package: Optional[str] = None) -> Output:
    """Initialize a new CHANGELOG.md file for the project or specific package."""

    # Determine target location
    if ctx.has_workspace and package:
        try:
            target_pkg = ctx.require_package(package)
            changelog_path = target_pkg.changelog_path
            location_desc = f"package '{target_pkg.name}'"
        except ValueError as e:
            return Output(success=False, message=str(e))
    elif ctx.has_workspace and not package:
        # In workspace mode without package, show available packages
        available = get_workspace_packages(ctx)
        return Output(
            success=False,
            message="Workspace requires --package for init-changelog",
            details=[
                {
                    "type": "text",
                    "content": f"Available packages: {', '.join(available)}",
                }
            ],
            next_steps=[
                "Specify a package: relkit init-changelog --package <name>",
                "Or initialize for root: relkit init-changelog --package _root",
            ],
        )
    else:
        # Single package project
        changelog_path = ctx.root / "CHANGELOG.md"
        location_desc = "project root"

    if changelog_path.exists():
        return Output(
            success=False,
            message=f"CHANGELOG.md already exists in {location_desc}",
            next_steps=["Edit CHANGELOG.md manually or delete it first"],
        )

    # Ensure parent directory exists (for workspace packages)
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    changelog_path.write_text(CHANGELOG_TEMPLATE)

    return Output(
        success=True,
        message=f"Created CHANGELOG.md in {location_desc}",
        data={"path": str(changelog_path)},
        details=[
            {
                "type": "text",
                "content": f"Location: {changelog_path.relative_to(ctx.root)}",
            }
        ],
    )


def update_changelog_version(path: Path, version: str) -> bool:
    """
    Helper to move [Unreleased] → [version] - date.

    Returns True if successful, False otherwise.
    """
    if not path.exists():
        return False

    content = path.read_text()

    # Check if [Unreleased] section exists
    if "## [Unreleased]" not in content:
        return False

    # Replace [Unreleased] with [version] - date
    today = date.today().strftime("%Y-%m-%d")
    new_section = f"## [{version}] - {today}"

    # Replace the section and add new [Unreleased] above it
    updated_content = content.replace(
        "## [Unreleased]",
        f"## [Unreleased]\n\n### Added\n\n### Changed\n\n### Fixed\n\n### Removed\n\n{new_section}",
    )

    path.write_text(updated_content)
    return True
