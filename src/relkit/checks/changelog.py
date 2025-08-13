"""Changelog validation checks."""

import os
from typing import Optional
from ..models import Output, Context
from ..utils import run_git
from ..safety import generate_token, verify_token


def check_changelog_exists(ctx: Context, **kwargs) -> Output:
    """Check if CHANGELOG.md exists."""
    changelog_path = ctx.root / "CHANGELOG.md"
    
    if not changelog_path.exists():
        return Output(
            success=False,
            message="No CHANGELOG.md found",
            details=[
                {"type": "text", "content": "This project requires a changelog for releases"}
            ],
            next_steps=["Run: relkit init-changelog"],
        )
    
    return Output(success=True, message="CHANGELOG.md exists")


def check_unreleased_content(ctx: Context, **kwargs) -> Output:
    """Check if [Unreleased] section has meaningful content."""
    changelog_path = ctx.root / "CHANGELOG.md"
    
    if not changelog_path.exists():
        return check_changelog_exists(ctx, **kwargs)
    
    content = changelog_path.read_text()
    
    # Find [Unreleased] section
    unreleased_idx = content.find("## [Unreleased]")
    if unreleased_idx == -1:
        return Output(
            success=False, 
            message="No [Unreleased] section in changelog",
            next_steps=["Add ## [Unreleased] section to CHANGELOG.md"],
        )
    
    # Find the next section boundary
    next_section = content.find("\n## [", unreleased_idx + 1)
    if next_section == -1:
        next_section = len(content)
    
    section_content = content[unreleased_idx:next_section]
    
    # Parse and check for actual content
    has_content = False
    
    for line in section_content.split("\n"):
        stripped = line.strip()
        
        # Skip empty lines, headers, and comments
        if (not stripped or 
            stripped == "## [Unreleased]" or
            stripped.startswith("###") or
            stripped.startswith("<!--") or 
            stripped.endswith("-->")):
            continue
        
        # Check for actual content (bullet points or text)
        if (stripped.startswith("-") or 
            stripped.startswith("*") or 
            stripped.startswith("+") or
            len(stripped) > 0):
            has_content = True
            break
    
    if not has_content:
        return Output(
            success=False, 
            message="Changelog [Unreleased] section is empty",
            next_steps=[
                "Add entries to CHANGELOG.md under ## [Unreleased]",
                "Document what was added, changed, fixed, or removed",
            ],
        )
    
    return Output(success=True, message="Changelog has unreleased content")


def check_version_entry(ctx: Context, version: Optional[str] = None, **kwargs) -> Output:
    """Check if a specific version has a changelog entry with content."""
    if version is None:
        version = ctx.version
    
    changelog_path = ctx.root / "CHANGELOG.md"
    
    if not changelog_path.exists():
        return check_changelog_exists(ctx, **kwargs)
    
    content = changelog_path.read_text()
    version_pattern = f"[{version}]"
    
    # Check if version is in changelog
    if version_pattern not in content:
        return Output(
            success=False,
            message=f"No changelog entry for version {version}",
            details=[
                {"type": "text", "content": "Every release must have a changelog entry"},
                {"type": "text", "content": "The changelog documents what changed for users"},
            ],
            next_steps=[
                "Add your changes to CHANGELOG.md under [Unreleased]",
                "Then run: relkit bump <major|minor|patch>",
            ],
        )
    
    # Check that the version section has actual content
    version_idx = content.index(version_pattern)
    next_section_idx = content.find("\n## [", version_idx + 1)
    if next_section_idx == -1:
        next_section_idx = len(content)
    
    version_content = content[version_idx:next_section_idx].strip()
    
    # Check for meaningful content
    has_content = False
    for line in version_content.split("\n")[1:]:  # Skip the header line
        stripped = line.strip()
        if (stripped and 
            not stripped.startswith("###") and
            not stripped.startswith("<!--") and
            not stripped.endswith("-->")):
            has_content = True
            break
    
    if not has_content:
        return Output(
            success=False,
            message=f"Changelog entry for {version} is empty",
            details=[
                {"type": "text", "content": "Version section exists but has no content"},
                {"type": "text", "content": "Users need to know what changed"},
            ],
            next_steps=[
                "Add meaningful entries to the changelog",
                "Document what was added, changed, fixed, or removed",
            ],
        )
    
    return Output(success=True, message=f"Changelog has entry for version {version}")


def check_commits_documented(ctx: Context, **kwargs) -> Output:
    """Check if commits since last tag are documented in changelog."""
    # Check for force override token
    token_env = "FORCE_EMPTY_CHANGELOG"
    provided = os.getenv(token_env)
    
    if provided and verify_token(ctx.name, "force_empty_changelog", provided):
        return Output(success=True, message="Changelog check overridden")
    
    # Get commit information
    commit_count = ctx.commits_since_tag
    last_tag = ctx.last_tag or "start of project"
    
    # Case 1: No commits since last tag
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
    changelog_result = check_unreleased_content(ctx, **kwargs)
    
    if not changelog_result.success:
        # Get commit list to show user
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