"""Bump-specific validation checks."""

from ..models import Output, Context
from ..utils import run_git


def check_git_clean_for_bump(ctx: Context, **kwargs) -> Output:
    """Soft check for git status - warns but doesn't block."""
    result = run_git(["status", "--porcelain"], cwd=ctx.root)
    if result.returncode == 0 and result.stdout.strip():
        lines = result.stdout.strip().split("\n")
        return Output(
            success=False, message=f"Git has uncommitted changes ({len(lines)} files)"
        )
    return Output(success=True, message="Git is clean")


def check_changelog_has_unreleased(ctx: Context, **kwargs) -> Output:
    """Check if [Unreleased] section has content."""
    changelog_path = ctx.root / "CHANGELOG.md"
    if not changelog_path.exists():
        return Output(success=False, message="No CHANGELOG.md found")

    content = changelog_path.read_text()

    # Find [Unreleased] section
    unreleased_idx = content.find("## [Unreleased]")
    if unreleased_idx == -1:
        return Output(success=False, message="No [Unreleased] section in changelog")

    # Check if it has content
    next_section = content.find("\n## [", unreleased_idx + 1)
    if next_section == -1:
        next_section = len(content)

    section_content = content[unreleased_idx:next_section]
    meaningful_lines = [
        line.strip()
        for line in section_content.split("\n")
        if line.strip()
        and not line.strip().startswith("###")
        and not line.strip().startswith("<!--")
        and not line.strip() == "## [Unreleased]"
    ]

    if not meaningful_lines:
        return Output(success=False, message="Changelog [Unreleased] section is empty")

    return Output(success=True, message="Changelog has unreleased content")


def check_major_bump_justification(
    ctx: Context, bump_type: str = "patch", **kwargs
) -> Output:
    """Check if major bump is justified."""
    # Get bump_type from kwargs if not passed directly
    if "bump_type" in kwargs:
        bump_type = kwargs["bump_type"]

    if bump_type != "major":
        return Output(success=True, message="Not a major bump")

    return Output(success=False, message="Major version bump (breaking change)")
