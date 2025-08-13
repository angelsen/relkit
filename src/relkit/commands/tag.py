"""Git tagging command."""

from typing import Optional
from ..decorators import command
from ..models import Output, Context
from ..safety import requires_confirmation, requires_clean_git, requires_review
from ..utils import run_git


@command("tag", "Create and push git tag for release")
@requires_review("commits", ["relkit git log", "relkit git log --oneline"], ttl=600)
@requires_confirmation("tag", ttl=180)  # 3 min TTL for tags
@requires_clean_git  # BLOCK if git is dirty - no escape
def tag(ctx: Context, package: Optional[str] = None, push: bool = True) -> Output:
    """Create and optionally push a git tag for the current version."""
    # Check for remote first (opinionated: tags should be pushable)
    remote_result = run_git(["remote", "-v"], cwd=ctx.root)
    if not remote_result.stdout.strip():
        return Output(
            success=False,
            message="No git remote configured",
            details=[
                {"type": "text", "content": "Tags require a remote repository"},
                {"type": "text", "content": "This ensures tags can be shared"},
            ],
            next_steps=[
                "Add remote: git remote add origin <url>",
                "Example: git remote add origin git@github.com:user/repo.git",
            ],
        )

    # Check for unpushed commits (opinionated: must push branch before tagging)
    # Try to get upstream branch
    upstream_result = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=ctx.root
    )

    if upstream_result.returncode != 0:
        # No upstream branch set
        return Output(
            success=False,
            message="Branch not pushed to remote",
            details=[
                {"type": "text", "content": "Current branch has no upstream tracking"},
                {
                    "type": "text",
                    "content": "Tags should only be created on pushed commits",
                },
            ],
            next_steps=[
                "Push branch first: git push -u origin <branch>",
                "Example: git push -u origin master",
            ],
        )

    # Check for unpushed commits
    unpushed_result = run_git(["cherry", "-v", "@{u}"], cwd=ctx.root)
    if unpushed_result.stdout.strip():
        commit_count = len(unpushed_result.stdout.strip().split("\n"))
        return Output(
            success=False,
            message=f"Branch has {commit_count} unpushed commit(s)",
            details=[
                {
                    "type": "text",
                    "content": "Tags should only be created on pushed commits",
                },
                {
                    "type": "text",
                    "content": "This ensures tags reference public commits",
                },
            ],
            next_steps=["Push commits first: git push", "Then retry: relkit tag"],
        )

    tag_name = f"v{ctx.version}"

    # Check if version already in CHANGELOG (prevents re-releasing)
    changelog_path = ctx.root / "CHANGELOG.md"
    if changelog_path.exists():
        changelog_content = changelog_path.read_text()
        version_header = f"## [{ctx.version}]"
        if version_header in changelog_content:
            return Output(
                success=False,
                message=f"Version {ctx.version} already released",
                details=[
                    {
                        "type": "text",
                        "content": f"Found in CHANGELOG.md: {version_header}",
                    },
                    {
                        "type": "text",
                        "content": "Cannot tag an already-released version",
                    },
                ],
                next_steps=[
                    "Bump to new version: relkit bump patch",
                    "Or if recovering from reset: relkit bump patch --force",
                ],
            )

    # Check if tag already exists
    check_result = run_git(["tag", "-l", tag_name], cwd=ctx.root)

    if check_result.stdout.strip():
        return Output(
            success=False,
            message=f"Tag {tag_name} already exists",
            next_steps=[
                f"Delete existing tag: git tag -d {tag_name}",
                "Or bump version first: relkit bump <major|minor|patch>",
            ],
        )

    # Create tag
    result = run_git(
        ["tag", "-a", tag_name, "-m", f"Release {ctx.version}"], cwd=ctx.root
    )

    if result.returncode != 0:
        return Output(
            success=False,
            message=f"Failed to create tag {tag_name}",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
        )

    details = [{"type": "text", "content": f"Created tag: {tag_name}"}]
    pushed = False

    # Push tag if requested
    if push:
        push_result = run_git(["push", "origin", tag_name], cwd=ctx.root)

        if push_result.returncode == 0:
            details.append({"type": "text", "content": "Pushed tag to origin"})
            pushed = True
        else:
            details.append(
                {
                    "type": "text",
                    "content": "Failed to push tag (will need manual push)",
                }
            )
            if push_result.stderr:
                details.append({"type": "text", "content": push_result.stderr.strip()})

    return Output(
        success=True,
        message=f"Tagged release {ctx.version}",
        details=details,
        data={"tag": tag_name, "pushed": pushed},
    )
