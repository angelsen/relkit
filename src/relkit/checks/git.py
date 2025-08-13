"""Git-related checks."""

from ..models import Output, Context
from ..utils import run_git


def check_clean_working_tree(ctx: Context, **kwargs) -> Output:
    """Check if git working directory is clean (no uncommitted changes)."""
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


def check_tag_exists(ctx: Context, tag_name: str, **kwargs) -> Output:
    """Check if a specific git tag exists."""
    result = run_git(["tag", "-l", tag_name], cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message=f"Failed to check for tag {tag_name}",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
        )

    if result.stdout.strip():
        return Output(success=True, message=f"Tag {tag_name} exists")
    else:
        return Output(success=False, message=f"Tag {tag_name} does not exist")


def check_commits_since_tag(ctx: Context, **kwargs) -> Output:
    """Get information about commits since the last tag."""
    commit_count = ctx.commits_since_tag
    last_tag = ctx.last_tag

    if commit_count == 0:
        return Output(
            success=True,
            message="No commits since last tag",
            data={
                "count": 0,
                "last_tag": last_tag,
            },
        )

    # Get commit list
    if last_tag:
        result = run_git(
            ["log", f"{last_tag}..HEAD", "--oneline", "--no-merges"], cwd=ctx.root
        )
    else:
        result = run_git(["log", "--oneline", "--no-merges", "-n", "20"], cwd=ctx.root)

    commits = []
    if result.returncode == 0 and result.stdout.strip():
        commits = result.stdout.strip().split("\n")

    details = [
        {
            "type": "text",
            "content": f"Commits since {last_tag or 'start'}: {commit_count}",
        },
    ]

    if commits:
        details.append({"type": "spacer"})
        details.append({"type": "text", "content": "Recent commits:"})
        for commit in commits[:10]:
            details.append({"type": "text", "content": f"  {commit}"})
        if len(commits) > 10:
            details.append(
                {"type": "text", "content": f"  ... and {len(commits) - 10} more"}
            )

    return Output(
        success=True,
        message=f"{commit_count} commit(s) since {last_tag or 'start'}",
        details=details,
        data={
            "count": commit_count,
            "last_tag": last_tag,
            "commits": commits,
        },
    )


def check_remote_configured(ctx: Context, **kwargs) -> Output:
    """Check if git remote is configured."""
    result = run_git(["remote", "-v"], cwd=ctx.root)

    if result.returncode != 0:
        return Output(
            success=False,
            message="Failed to check git remotes",
            details=[{"type": "text", "content": result.stderr.strip()}]
            if result.stderr
            else None,
        )

    remotes = result.stdout.strip()

    if not remotes:
        return Output(
            success=False,
            message="No git remote configured",
            details=[
                {
                    "type": "text",
                    "content": "A remote repository is required for collaboration",
                },
                {"type": "text", "content": "This allows pushing commits and tags"},
            ],
            next_steps=[
                "Add remote: git remote add origin <url>",
                "Example: git remote add origin git@github.com:user/repo.git",
            ],
        )

    # Parse remotes
    remote_lines = remotes.split("\n")
    remote_names = set()
    for line in remote_lines:
        if line:
            parts = line.split("\t")
            if parts:
                remote_names.add(parts[0])

    return Output(
        success=True,
        message=f"Git remote configured ({', '.join(remote_names)})",
        data={"remotes": list(remote_names)},
    )


def check_branch_pushed(ctx: Context, **kwargs) -> Output:
    """Check if current branch is pushed to remote."""
    # Get current branch
    branch_result = run_git(["branch", "--show-current"], cwd=ctx.root)
    if branch_result.returncode != 0 or not branch_result.stdout.strip():
        return Output(
            success=False,
            message="Failed to determine current branch",
        )

    current_branch = branch_result.stdout.strip()

    # Check if branch has upstream
    upstream_result = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=ctx.root
    )

    if upstream_result.returncode != 0:
        return Output(
            success=False,
            message=f"Branch '{current_branch}' not pushed to remote",
            details=[
                {"type": "text", "content": "Branch has no upstream tracking"},
                {"type": "text", "content": "This is required for collaboration"},
            ],
            next_steps=[
                f"Push branch: git push -u origin {current_branch}",
            ],
        )

    # Check for unpushed commits
    unpushed_result = run_git(["cherry", "-v", "@{u}"], cwd=ctx.root)
    if unpushed_result.returncode == 0 and unpushed_result.stdout.strip():
        commit_count = len(unpushed_result.stdout.strip().split("\n"))
        return Output(
            success=False,
            message=f"Branch has {commit_count} unpushed commit(s)",
            details=[
                {"type": "text", "content": "Local commits not yet on remote"},
                {"type": "text", "content": "Push to share your changes"},
            ],
            next_steps=["Push commits: git push"],
        )

    return Output(
        success=True,
        message=f"Branch '{current_branch}' is pushed to remote",
        data={"branch": current_branch},
    )
