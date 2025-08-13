"""Git-related checks."""

from ..models import Output, Context
from ..utils import run_git


def check_git_clean(ctx: Context, **kwargs) -> Output:
    """Check if git working directory is clean."""
    result = run_git(["status", "--porcelain"], cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message="Failed to check git status",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
        )

    changes = result.stdout.strip()

    if changes:
        lines = changes.split("\n")
        return Output(
            success=False,
            message=f"Git working directory has {len(lines)} uncommitted change(s)",
            details=[
                {"type": "text", "content": line} for line in lines[:10]
            ],  # Show first 10 changes
            next_steps=[
                "Review changes: git status",
                "Commit changes: git commit -am 'Your message'",
                "Or stash: git stash",
            ],
        )

    return Output(success=True, message="Git working directory is clean")


def check_changelog(ctx: Context, **kwargs) -> Output:
    """STRICTLY enforce changelog has entry for current version."""
    changelog_path = ctx.root / "CHANGELOG.md"

    if not changelog_path.exists():
        return Output(
            success=False,
            message="BLOCKED: No CHANGELOG.md found",
            details=[
                {
                    "type": "text",
                    "content": "This project requires a changelog for releases",
                }
            ],
            next_steps=["Run: relkit init-changelog"],
        )

    content = changelog_path.read_text()
    version_pattern = f"[{ctx.version}]"

    # Check if current version is in changelog
    if version_pattern not in content:
        return Output(
            success=False,
            message=f"BLOCKED: No changelog entry for version {ctx.version}",
            details=[
                {
                    "type": "text",
                    "content": "Every release MUST have a changelog entry",
                },
                {
                    "type": "text",
                    "content": "The changelog documents what changed for users",
                },
            ],
            next_steps=[
                "Add your changes to CHANGELOG.md under [Unreleased]",
                "Then run: relkit bump <major|minor|patch>",
                "This will move [Unreleased] items to the new version",
            ],
        )

    # Check that the version section has actual content
    version_idx = content.index(version_pattern)
    next_section_idx = content.find("\n## [", version_idx + 1)
    if next_section_idx == -1:
        next_section_idx = len(content)

    version_content = content[version_idx:next_section_idx].strip()

    # Remove the header line and check if anything remains
    lines = version_content.split("\n")[1:]  # Skip the ## [version] line
    meaningful_lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("###")
    ]

    if not meaningful_lines:
        return Output(
            success=False,
            message=f"BLOCKED: Changelog entry for {ctx.version} is empty",
            details=[
                {
                    "type": "text",
                    "content": "Version section exists but has no content",
                },
                {"type": "text", "content": "Users need to know what changed"},
            ],
            next_steps=[
                "Add meaningful entries to the changelog",
                "Document what was added, changed, fixed, or removed",
            ],
        )

    return Output(
        success=True, message=f"Changelog has entry for version {ctx.version}"
    )
