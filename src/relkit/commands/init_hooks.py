"""Initialize git hooks to enforce relkit workflows."""

from ..decorators import command
from ..models import Output, Context
from ..checks.hooks import get_hook_with_hash, get_hook_hash, check_hooks_initialized


@command("init-hooks", "Initialize git hooks for version management")
def init_hooks(ctx: Context) -> Output:
    """Initialize git hooks that enforce relkit workflows."""
    git_dir = ctx.root / ".git"

    if not git_dir.exists():
        return Output(
            success=False,
            message="Not a git repository",
            details=[{"type": "text", "content": "No .git directory found"}],
            next_steps=["Initialize git: git init"],
        )

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    precommit_path = hooks_dir / "pre-commit"

    # Check current state
    check_result = check_hooks_initialized(ctx)

    # If already up to date
    if check_result.success:
        return Output(
            success=True,
            message="Git hooks already initialized and up to date",
            details=check_result.details,
        )

    # If exists but not ours
    if (
        precommit_path.exists()
        and "relkit pre-commit hook" not in precommit_path.read_text()
    ):
        return check_result  # Return the error about existing hook

    # Install or update the hook
    hook_content = get_hook_with_hash()
    precommit_path.write_text(hook_content)
    precommit_path.chmod(0o755)

    return Output(
        success=True,
        message="Git hooks initialized successfully",
        details=[
            {"type": "text", "content": f"Hook hash: {get_hook_hash()}"},
            {"type": "spacer"},
            {"type": "text", "content": "Enforcement active:"},
            {"type": "text", "content": "  - Direct version edits blocked"},
            {
                "type": "text",
                "content": "  - Must use: relkit bump <major|minor|patch>",
            },
        ],
    )
