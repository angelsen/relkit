"""Version bumping commands."""

from typing import Optional, Literal
import re
from ..decorators import command
from ..models import Output, Context
from .changelog import update_changelog_version
from ..utils import run_git
from ..safety import requires_active_decision, requires_review, requires_clean_git
from ..checks.bump import (
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
@requires_clean_git  # Enforce clean git state - no escape
@requires_active_decision(
    "bump",
    checks=[
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

    # Check for remote (required for atomic operation)
    remote_result = run_git(["remote", "-v"], cwd=ctx.root)
    if not remote_result.stdout.strip():
        return Output(
            success=False,
            message="No git remote configured",
            details=[
                {"type": "text", "content": "Atomic bump requires a remote repository"},
                {"type": "text", "content": "This ensures changes can be shared"},
            ],
            next_steps=[
                "Add remote: git remote add origin <url>",
                "Example: git remote add origin git@github.com:user/repo.git",
            ],
        )

    # Commit the changes
    commit_message = f"chore: bump version to {new_version}"
    add_result = run_git(["add", "-A"], cwd=ctx.root)
    if add_result.returncode != 0:
        return Output(
            success=False,
            message="Failed to stage changes",
            details=[{"type": "text", "content": add_result.stderr.strip()}]
            if add_result.stderr
            else None,
        )

    commit_result = run_git(["commit", "-m", commit_message], cwd=ctx.root)
    if commit_result.returncode != 0:
        return Output(
            success=False,
            message="Failed to commit changes",
            details=[{"type": "text", "content": commit_result.stderr.strip()}]
            if commit_result.stderr
            else None,
        )

    # Create tag
    tag_name = f"v{new_version}"
    tag_result = run_git(
        ["tag", "-a", tag_name, "-m", f"Release {new_version}"], cwd=ctx.root
    )
    if tag_result.returncode != 0:
        # Rollback commit if tag fails
        run_git(["reset", "--hard", "HEAD~1"], cwd=ctx.root)
        details = [
            {"type": "text", "content": "Rolled back commit due to tag failure"}
        ]
        if tag_result.stderr:
            details.append({"type": "text", "content": tag_result.stderr.strip()})
        
        return Output(
            success=False,
            message=f"Failed to create tag {tag_name}",
            details=details,
        )

    # Push commit and tag
    push_commit_result = run_git(["push"], cwd=ctx.root)
    push_tag_result = run_git(["push", "origin", tag_name], cwd=ctx.root)

    push_success = (
        push_commit_result.returncode == 0 and push_tag_result.returncode == 0
    )

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

    details.append({"type": "spacer"})
    details.append({"type": "text", "content": f"✓ Updated version to {new_version}"})
    if changelog_updated:
        details.append({"type": "text", "content": "✓ Updated CHANGELOG.md"})
    details.append({"type": "text", "content": f"✓ Committed: {commit_message}"})
    details.append({"type": "text", "content": f"✓ Tagged: {tag_name}"})

    if push_success:
        details.append({"type": "text", "content": "✓ Pushed commit and tag to origin"})
    else:
        details.append({"type": "spacer"})
        details.append(
            {"type": "text", "content": "⚠ Failed to push (manual push required)"}
        )
        if push_commit_result.returncode != 0:
            details.append(
                {"type": "text", "content": f"  Commit push: {push_commit_result.stderr.strip() if push_commit_result.stderr else 'failed'}"}
            )
        if push_tag_result.returncode != 0:
            details.append(
                {"type": "text", "content": f"  Tag push: {push_tag_result.stderr.strip() if push_tag_result.stderr else 'failed'}"}
            )

    return Output(
        success=True,
        message=f"Released version {new_version}",
        data={
            "old": current,
            "new": new_version,
            "bump_type": bump_type,
            "commits": commit_count,
            "tag": tag_name,
            "pushed": push_success,
        },
        details=details,
        next_steps=[
            "Push manually: git push && git push --tags",
        ]
        if not push_success
        else None,
    )
