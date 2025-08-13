"""Version bumping commands."""

from typing import Optional, Literal
import re
import time
import hashlib
from ..decorators import command
from ..models import Output, Context
from .changelog import update_changelog_version
from ..utils import run_git, run_uv, require_package_for_workspace, parse_version
from ..safety import requires_active_decision, requires_review, requires_clean_git
from ..checks.changelog import check_commits_documented, check_major_bump_justification
from ..checks.hooks import check_hooks_initialized


BumpType = Literal["major", "minor", "patch"]


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
        check_commits_documented,
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

    # Check if workspace requires package
    error = require_package_for_workspace(ctx, package, "bump")
    if error:
        return error

    # Get target package
    try:
        target_pkg = ctx.require_package(package)
    except ValueError as e:
        return Output(success=False, message=str(e))

    # Get current version and calculate new version
    current = target_pkg.version
    new_version = bump_version_string(current, bump_type)

    # Get recent commits for display (package-specific if possible)
    last_tag = target_pkg.get_last_tag()
    if last_tag:
        result = run_git(["rev-list", f"{last_tag}..HEAD", "--count"], cwd=ctx.root)
        commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0
    else:
        result = run_git(["rev-list", "HEAD", "--count"], cwd=ctx.root)
        commit_count = int(result.stdout.strip()) if result.returncode == 0 else 0

    commits = get_recent_commits(ctx)  # Still use general commits for display

    # Update pyproject.toml for the target package
    pyproject_path = target_pkg.pyproject_path
    content = pyproject_path.read_text()
    updated_content = re.sub(
        r'version = "[^"]+"', f'version = "{new_version}"', content, count=1
    )
    pyproject_path.write_text(updated_content)

    # Update changelog for the target package
    changelog_path = target_pkg.changelog_path
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

    # Commit the changes with package prefix if not root
    if target_pkg.name != "_root" and ctx.has_workspace:
        commit_message = f"chore({target_pkg.name}): bump version to {new_version}"
    else:
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

    # Generate HOOK_OVERRIDE to bypass pre-commit hook
    # This is secure because:
    # 1. User already reviewed commits (REVIEW_COMMITS token)
    # 2. User already confirmed bump (via @requires_review decorator)
    # 3. Bump is the ONLY authorized way to change versions
    timestamp = int(time.time())
    window = timestamp // 60
    hook_override = hashlib.sha256(str(window).encode()).hexdigest()[:8]

    # Run git commit with HOOK_OVERRIDE in environment
    commit_result = run_git(
        ["commit", "-m", commit_message],
        cwd=ctx.root,
        env={"HOOK_OVERRIDE": hook_override},
    )

    if commit_result.returncode != 0:
        return Output(
            success=False,
            message="Failed to commit changes",
            details=[{"type": "text", "content": commit_result.stderr.strip()}]
            if commit_result.stderr
            else None,
        )

    # Phase 2: Sync lockfile and amend commit if needed
    # This ensures the lockfile reflects the new version
    # Use --all-extras to ensure complete dependency resolution for type checking
    sync_args = ["sync", "--all-extras"]
    if package and ctx.has_workspace:
        sync_args.extend(["--package", package])
    sync_result = run_uv(sync_args, cwd=ctx.root)
    if sync_result.returncode == 0:
        # Check if lockfile changed
        status_result = run_git(["status", "--porcelain", "uv.lock"], cwd=ctx.root)
        if status_result.stdout.strip():
            # Lockfile changed, amend it into the commit
            add_lock_result = run_git(["add", "uv.lock"], cwd=ctx.root)
            if add_lock_result.returncode == 0:
                amend_result = run_git(
                    ["commit", "--amend", "--no-edit"],
                    cwd=ctx.root,
                    env={"HOOK_OVERRIDE": hook_override},  # Use same override for amend
                )
                if amend_result.returncode == 0:
                    print("  ✓ Updated and included lockfile")

    # Create tag with package-specific naming
    tag_name = target_pkg.tag_name.replace(target_pkg.version, new_version)
    tag_message = (
        f"Release {target_pkg.name} {new_version}"
        if ctx.has_workspace
        else f"Release {new_version}"
    )
    tag_result = run_git(["tag", "-a", tag_name, "-m", tag_message], cwd=ctx.root)
    if tag_result.returncode != 0:
        # Rollback commit if tag fails
        run_git(["reset", "--hard", "HEAD~1"], cwd=ctx.root)
        details = [{"type": "text", "content": "Rolled back commit due to tag failure"}]
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
            "content": f"Package: {target_pkg.name}",
        }
        if ctx.has_workspace
        else None,
        {
            "type": "text",
            "content": f"Commits since {last_tag or 'start'}: {commit_count}",
        },
    ]

    if commits:
        details.append({"type": "spacer"})
        details.append({"type": "text", "content": "Recent commits:"})
        for commit in commits[:5]:  # Show max 5 commits
            details.append({"type": "text", "content": f"  {commit}"})

    details.append({"type": "spacer"})
    # Filter out None entries
    details = [d for d in details if d is not None]

    details.append(
        {
            "type": "text",
            "content": f"✓ Updated {target_pkg.name} version to {new_version}"
            if ctx.has_workspace
            else f"✓ Updated version to {new_version}",
        }
    )
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
                {
                    "type": "text",
                    "content": f"  Commit push: {push_commit_result.stderr.strip() if push_commit_result.stderr else 'failed'}",
                }
            )
        if push_tag_result.returncode != 0:
            details.append(
                {
                    "type": "text",
                    "content": f"  Tag push: {push_tag_result.stderr.strip() if push_tag_result.stderr else 'failed'}",
                }
            )

    return Output(
        success=True,
        message=f"Released {target_pkg.name} version {new_version}"
        if ctx.has_workspace
        else f"Released version {new_version}",
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
