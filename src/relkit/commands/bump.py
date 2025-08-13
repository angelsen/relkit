"""Version bumping commands."""

from typing import Optional, Literal
import re
from ..decorators import command
from ..models import Output, Context
from .changelog import update_changelog_version
from ..utils import run_git
from ..safety import requires_active_decision, requires_review
from ..checks.bump import (
    check_git_clean_for_bump,
    check_changelog_has_unreleased,
    check_major_bump_justification,
)
from ..checks.hooks import check_hooks_initialized


BumpType = Literal["major", "minor", "patch"]


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse semantic version string into components."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version_string(version: str, bump_type: BumpType) -> str:
    """Bump version string according to type."""
    major, minor, patch = parse_version(version)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def get_recent_commits(ctx: Context, limit: int = 10) -> list[str]:
    """Get recent commit messages."""
    if ctx.last_tag:
        args = ["log", f"{ctx.last_tag}..HEAD", "--oneline", "-n", str(limit)]
    else:
        args = ["log", "--oneline", "-n", str(limit)]

    result = run_git(args, cwd=ctx.root)

    if result.returncode != 0:
        return []

    return [line for line in result.stdout.strip().split("\n") if line]


@command("bump", "Bump version and update changelog")
@requires_review(
    "commits", ["relkit git log", "relkit git log --oneline -20"], ttl=600
)  # Review what changed
@requires_active_decision(
    "bump",
    checks=[
        check_git_clean_for_bump,
        check_changelog_has_unreleased,
        check_major_bump_justification,
    ],
)
def bump(
    ctx: Context, bump_type: BumpType = "patch", package: Optional[str] = None
) -> Output:
    """Bump project version and update changelog."""
    # Check hooks are initialized first
    hooks_check = check_hooks_initialized(ctx)
    if not hooks_check.success:
        return hooks_check

    # Validate bump type
    if bump_type not in ("major", "minor", "patch"):
        return Output(
            success=False,
            message=f"Invalid bump type: {bump_type}",
            details=[{"type": "text", "content": "Valid types: major, minor, patch"}],
        )

    # Get current version and calculate new version
    current = ctx.version
    new_version = bump_version_string(current, bump_type)

    # Get recent commits for display
    commits = get_recent_commits(ctx)
    commit_count = ctx.commits_since_tag

    # Update pyproject.toml
    pyproject_path = ctx.root / "pyproject.toml"
    content = pyproject_path.read_text()
    updated_content = re.sub(
        r'version = "[^"]+"', f'version = "{new_version}"', content, count=1
    )
    pyproject_path.write_text(updated_content)

    # Update changelog
    changelog_path = ctx.root / "CHANGELOG.md"
    changelog_updated = False
    if changelog_path.exists():
        changelog_updated = update_changelog_version(changelog_path, new_version)

    # Prepare output with structured data
    details = [
        {"type": "version_change", "old": current, "new": new_version},
        {
            "type": "text",
            "content": f"Commits since {ctx.last_tag or 'start'}: {commit_count}",
        },
    ]

    if commits:
        details.append({"type": "spacer"})
        details.append({"type": "text", "content": "Recent commits:"})
        for commit in commits[:5]:  # Show max 5 commits
            details.append({"type": "text", "content": f"  {commit}"})

    if changelog_updated:
        details.append({"type": "spacer"})
        details.append({"type": "text", "content": "Updated CHANGELOG.md"})

    return Output(
        success=True,
        message=f"Bumped version to {new_version}",
        data={
            "old": current,
            "new": new_version,
            "bump_type": bump_type,
            "commits": commit_count,
        },
        details=details,
        next_steps=[
            "Review changes with: git diff",
            "Commit with: git commit -am 'chore: bump version to " + new_version + "'",
            "Tag with: relkit tag",
        ],
    )
