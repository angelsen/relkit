"""Git wrapper with minimal interference and safety features."""

import re
import sys
from typing import Tuple, Optional
from ..decorators import command
from ..models import Output, Context
from ..safety import (
    generate_token,
    verify_token,
    generate_content_token,
    verify_content_token,
)
from ..utils import run_git
import os


def strip_claude_signatures(message: str) -> str:
    """Remove Claude-related signatures from commit messages."""
    patterns = [
        r".*[Gg]enerated.*[Cc]laude.*[Cc]ode.*",
        r".*[Cc]o-[Aa]uthored.*[Cc]laude.*anthropic.*",
        r".*claude\.ai/code.*",
        r".*[Cc]laude.*",
    ]

    for pattern in patterns:
        message = re.sub(pattern, "", message, flags=re.MULTILINE)

    # Clean up extra newlines
    message = re.sub(r"\n\s*\n\s*\n", "\n\n", message)
    return message.strip()


def validate_conventional_commit(message: str) -> Tuple[bool, Optional[str]]:
    """Validate conventional commit format.

    Returns: (is_valid, error_message)
    """
    lines = message.split("\n")
    header = lines[0].strip()  # Strip leading/trailing whitespace

    # Check header format: type(scope): description
    pattern = r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\([^)]+\))?(!)?:\s+(.+)"
    match = re.match(pattern, header)

    if not match:
        # Check for common mistakes
        if ":" not in header:
            return False, "Missing colon separator. Use: type: description"

        first_word = header.split(":")[0].split("(")[0].lower()
        wrong_types = {
            "feature": "feat",
            "bugfix": "fix",
            "bug": "fix",
            "documentation": "docs",
            "doc": "docs",
            "refactoring": "refactor",
            "tests": "test",
        }
        if first_word in wrong_types:
            return False, f"Use '{wrong_types[first_word]}' instead of '{first_word}'"

        return False, "Invalid format. Use: type(scope): description"

    _, _, breaking, description = match.groups()

    # Basic quality checks
    if len(description) < 10:
        return False, "Description too short (minimum 10 characters)"

    # Check for breaking changes footer
    if breaking and "BREAKING CHANGE:" not in message:
        return False, "Breaking changes (!) need BREAKING CHANGE: footer"

    return True, None


def get_staged_tree_hash(ctx: Context) -> str:
    """Get the git tree hash of staged changes."""
    result = run_git(["write-tree"], cwd=ctx.root)
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


@command("git", "", accepts_any_args=True)
def git_wrapper(ctx: Context, *git_args) -> Output:
    """
    Minimal git wrapper that only intervenes for safety.

    Only handles:
    - commit: validate format, require review
    - tag: block creation (use relkit bump)
    - push --force: require confirmation
    - log/diff/status: generate review tokens (TTY only)

    Everything else passes through unchanged.
    """
    args = list(git_args)

    if not args:
        args = ["--help"]

    # --- SAFETY INTERVENTIONS ---

    # Block direct tag creation (but allow listing and deletion)
    if args[0] == "tag" and len(args) > 1:
        if not any(flag in args for flag in ["-l", "--list", "-d", "--delete"]):
            return Output(
                success=False,
                message="Direct tag creation blocked",
                details=[
                    {"type": "text", "content": "Use: relkit bump <major|minor|patch>"},
                    {
                        "type": "text",
                        "content": "This ensures version, changelog, and tag stay in sync",
                    },
                ],
            )

    # Handle commit with validation
    if args[0] == "commit":
        # Check for staged changes
        tree_hash = get_staged_tree_hash(ctx)
        if not tree_hash:
            return Output(
                success=False,
                message="Nothing staged to commit",
                next_steps=["Stage changes: git add <files>"],
            )

        # Check review token
        token = os.getenv("REVIEW_CHANGES")
        if not token or not verify_content_token(
            ctx.name, "review_staged", tree_hash, token
        ):
            return Output(
                success=False,
                message="Review staged changes first",
                next_steps=[
                    "Review: git diff --staged",
                    "Then commit with the generated REVIEW_CHANGES token",
                ],
            )

        # Validate and clean commit message
        if "-m" in args:
            msg_idx = args.index("-m") + 1
            if msg_idx < len(args):
                original = args[msg_idx]
                cleaned = strip_claude_signatures(original)

                valid, error = validate_conventional_commit(cleaned)
                if not valid:
                    return Output(
                        success=False,
                        message=error or "Invalid commit message format",
                        next_steps=["Example: git commit -m 'feat: add new feature'"],
                    )

                args[msg_idx] = cleaned

    # Handle force push confirmation
    elif args[0] == "push" and ("--force" in args or "-f" in args):
        token = os.getenv("CONFIRM_FORCE_PUSH")
        if not token or not verify_token("force-push", "git", token):
            new_token = generate_token("force-push", "git", 60)
            return Output(
                success=False,
                message="Force push requires confirmation",
                next_steps=[f"CONFIRM_FORCE_PUSH={new_token} relkit git push --force"],
            )

    # --- TOKEN GENERATION (for review commands only) ---

    # These commands might generate tokens
    if args[0] in ["log", "diff", "status", "show"]:
        proc = run_git(args, cwd=ctx.root, capture_output=True)

        # Display git output as-is
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)

        # Generate tokens when there's content to review
        if proc.returncode == 0 and proc.stdout.strip():
            token_desc = None

            if args[0] == "log":
                token = generate_token(ctx.name, "review_commits", ttl=600)
                token_desc = f"REVIEW_COMMITS={token}"

            elif args[0] == "diff" and ("--staged" in args or "--cached" in args):
                tree_hash = get_staged_tree_hash(ctx)
                if tree_hash:
                    token = generate_content_token(
                        ctx.name, "review_staged", tree_hash, ttl=600
                    )
                    token_desc = f"REVIEW_CHANGES={token}"

            elif args[0] == "status":
                # Only generate token if there are changes
                if "nothing to commit" not in proc.stdout:
                    token = generate_token(ctx.name, "review_status", ttl=600)
                    token_desc = f"REVIEW_STATUS={token}"

            # Print token to stderr (user controls visibility with 2>/dev/null if needed)
            if token_desc:
                print(f"\n{token_desc}", file=sys.stderr)

        return Output(success=(proc.returncode == 0), message="")

    # --- DEFAULT: PASSTHROUGH ---

    # Everything else passes through unchanged
    proc = run_git(args, cwd=ctx.root, capture_output=False)
    return Output(success=(proc.returncode == 0), message="")
