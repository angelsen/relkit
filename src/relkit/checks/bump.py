"""Bump-specific validation checks."""

import os
from ..models import Output, Context
from ..utils import run_git
from ..safety import generate_token, verify_token


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
    """Check if [Unreleased] section has meaningful content."""
    changelog_path = ctx.root / "CHANGELOG.md"
    if not changelog_path.exists():
        return Output(success=False, message="No CHANGELOG.md found")

    content = changelog_path.read_text()

    # Find [Unreleased] section
    unreleased_idx = content.find("## [Unreleased]")
    if unreleased_idx == -1:
        return Output(success=False, message="No [Unreleased] section in changelog")

    # Find the next section boundary
    next_section = content.find("\n## [", unreleased_idx + 1)
    if next_section == -1:
        next_section = len(content)

    section_content = content[unreleased_idx:next_section]
    
    # Parse subsections and check for actual content
    has_content = False
    
    for line in section_content.split("\n"):
        stripped = line.strip()
        
        # Skip empty lines and the main header
        if not stripped or stripped == "## [Unreleased]":
            continue
            
        # Skip comments
        if stripped.startswith("<!--") or stripped.endswith("-->"):
            continue
            
        # Check for subsection headers (### Added, ### Changed, etc.)
        if stripped.startswith("###"):
            # Skip subsection headers - we only care about content
            continue
            
        # If we get here, it's actual content (bullet point, text, etc.)
        if stripped.startswith("-") or stripped.startswith("*") or stripped.startswith("+"):
            has_content = True
            break
        # Also consider any other non-empty line as content
        elif len(stripped) > 0:
            has_content = True
            break

    if not has_content:
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


def check_commits_vs_changelog(ctx: Context, **kwargs) -> Output:
    """Enforce changelog entries for commits since last tag."""
    # Check for force override token
    token_env = "FORCE_EMPTY_CHANGELOG"
    provided = os.getenv(token_env)
    
    if provided and verify_token(ctx.name, "force_empty_changelog", provided):
        # User has explicitly overridden the check
        return Output(success=True, message="Changelog check overridden")
    
    # Get commit information
    commit_count = ctx.commits_since_tag
    last_tag = ctx.last_tag or "start of project"
    
    # Case 1: No commits since last tag - why are we bumping?
    if commit_count == 0:
        new_token = generate_token(ctx.name, "force_empty_changelog", ttl=300)
        return Output(
            success=False,
            message="No commits since last tag - nothing to release",
            details=[
                {"type": "text", "content": f"Last tag: {last_tag}"},
                {"type": "text", "content": "No changes have been made since the last release"},
                {"type": "spacer"},
                {"type": "text", "content": "If you need to bump anyway (e.g., rebuild):"},
                {"type": "text", "content": "Token expires in 5 minutes"},
            ],
            next_steps=[
                "Make changes before creating a new release",
                f"Or force bump: {token_env}={new_token} relkit bump",
            ],
        )
    
    # Case 2: Have commits - check changelog
    # First check if changelog exists and has [Unreleased] section
    changelog_result = check_changelog_has_unreleased(ctx, **kwargs)
    
    if not changelog_result.success:
        # Changelog is empty or missing - get commit list to show user
        if last_tag:
            result = run_git(
                ["log", f"{last_tag}..HEAD", "--oneline", "--no-merges"],
                cwd=ctx.root
            )
        else:
            result = run_git(
                ["log", "--oneline", "--no-merges", "-n", "20"],
                cwd=ctx.root
            )
        
        commits = []
        if result.returncode == 0 and result.stdout.strip():
            commits = result.stdout.strip().split("\n")
        
        # Build details showing the commits
        details = [
            {"type": "text", "content": f"Found {commit_count} commit(s) since {last_tag}"},
            {"type": "text", "content": "But [Unreleased] section in CHANGELOG.md is empty"},
            {"type": "spacer"},
            {"type": "text", "content": "Recent commits that need documentation:"},
        ]
        
        # Show up to 10 commits
        for commit in commits[:10]:
            details.append({"type": "text", "content": f"  {commit}"})
        
        if len(commits) > 10:
            details.append({"type": "text", "content": f"  ... and {len(commits) - 10} more"})
        
        details.extend([
            {"type": "spacer"},
            {"type": "text", "content": "Every release must document what changed"},
            {"type": "text", "content": "Add entries under ## [Unreleased] in CHANGELOG.md"},
        ])
        
        # Generate override token for edge cases
        new_token = generate_token(ctx.name, "force_empty_changelog", ttl=300)
        details.append({"type": "spacer"})
        details.append({"type": "text", "content": "To force bump without changelog (not recommended):"})
        details.append({"type": "text", "content": f"{token_env}={new_token} relkit bump"})
        details.append({"type": "text", "content": "Token expires in 5 minutes"})
        
        return Output(
            success=False,
            message=f"Found {commit_count} commit(s) but changelog is empty",
            details=details,
            next_steps=[
                "Add entries to CHANGELOG.md under ## [Unreleased]",
                "Document what changed in this release",
                f"Or force: {token_env}={new_token} relkit bump",
            ],
        )
    
    # All good - have commits and changelog
    return Output(success=True, message="Commits and changelog are in sync")
