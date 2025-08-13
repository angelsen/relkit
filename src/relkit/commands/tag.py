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

    tag_name = f"v{ctx.version}"

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
