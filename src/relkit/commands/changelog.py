"""Changelog management commands."""

from pathlib import Path
from datetime import date
from ..decorators import command
from ..models import Output, Context


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
def init_changelog(ctx: Context) -> Output:
    """Initialize a new CHANGELOG.md file."""
    changelog_path = ctx.root / "CHANGELOG.md"

    if changelog_path.exists():
        return Output(
            success=False,
            message="CHANGELOG.md already exists",
            next_steps=["Edit CHANGELOG.md manually or delete it first"],
        )

    changelog_path.write_text(CHANGELOG_TEMPLATE)

    return Output(
        success=True,
        message="Created CHANGELOG.md with [Unreleased] section",
        data={"path": str(changelog_path)},
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
