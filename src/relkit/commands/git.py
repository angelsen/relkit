"""Git wrapper with safety features and style enforcement."""

import re
import sys
from typing import List, Tuple
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


def validate_conventional_commit(message: str) -> Tuple[bool, str, List[str]]:
    """Validate conventional commit format with detailed feedback.

    Returns: (is_valid, error_message, warnings)
    """
    lines = message.split("\n")
    header = lines[0]
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    warnings = []

    # Check header format: type(scope): description
    pattern = r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\([^)]+\))?(!)?:\s+(.+)"
    match = re.match(pattern, header)

    if not match:
        # Provide specific feedback on what's wrong
        if ":" not in header:
            return (
                False,
                (
                    "Missing colon separator\n"
                    "\n"
                    "Valid types:\n"
                    "  feat     - New feature\n"
                    "  fix      - Bug fix\n"
                    "  docs     - Documentation only\n"
                    "  style    - Formatting (no code change)\n"
                    "  refactor - Code restructuring\n"
                    "  test     - Adding tests\n"
                    "  chore    - Maintenance\n"
                    "  perf     - Performance improvement\n"
                    "  ci       - CI/CD changes\n"
                    "  build    - Build system\n"
                    "  revert   - Revert previous commit\n"
                    "\n"
                    "Examples:\n"
                    "  feat: add user authentication\n"
                    "  fix(api): handle null responses\n"
                    "  docs: update README with examples"
                ),
                [],
            )

        # Check if they used wrong type
        wrong_types = {
            "feature": "feat",
            "bugfix": "fix",
            "bug": "fix",
            "documentation": "docs",
            "doc": "docs",
            "refactoring": "refactor",
            "tests": "test",
            "testing": "test",
            "misc": "chore",
            "maintenance": "chore",
        }

        first_word = header.split(":")[0].split("(")[0].lower()
        if first_word in wrong_types:
            return (
                False,
                f"Use '{wrong_types[first_word]}' instead of '{first_word}'",
                [],
            )

        return (
            False,
            (
                "Invalid format. Use: type(scope): description\n"
                "\n"
                "Examples:\n"
                "  feat: add new feature\n"
                "  fix(auth): resolve login issue\n"
                "  docs: update API documentation"
            ),
            [],
        )

    type_part, scope, breaking, description = match.groups()

    # Check description quality
    if len(description) < 10:
        return (
            False,
            (
                f"Description too short: '{description}'\n"
                "Minimum 10 characters. Be descriptive!\n"
                "\n"
                "Bad:  feat: add stuff\n"
                "Good: feat: add user authentication system"
            ),
            [],
        )

    # Check for sentence case (warning only)
    if description[0].isupper():
        warnings.append("Use lowercase: 'add feature' not 'Add feature'")

    # Check for ending punctuation (warning only)
    if description[-1] in ".!?":
        warnings.append("Omit ending punctuation in header")

    # Validate body format if present
    if body.strip():
        # Check for bullet points
        if re.search(r"^[*\-+]\s+", body.strip(), re.MULTILINE):
            bullets = re.findall(r"^[*\-+]\s+(.+)$", body.strip(), re.MULTILINE)
            for bullet in bullets:
                if len(bullet.strip()) < 5:
                    return (
                        False,
                        (
                            "Bullet points must be descriptive\n"
                            "\n"
                            "Bad:\n"
                            "  - fix\n"
                            "  - update\n"
                            "\n"
                            "Good:\n"
                            "  - Fix memory leak in worker process\n"
                            "  - Update error handling for API calls"
                        ),
                        [],
                    )

    # Check for breaking changes
    if breaking or "BREAKING" in message.upper():
        if "BREAKING CHANGE:" not in message:
            return (
                False,
                (
                    "Breaking changes need footer:\n"
                    "\n"
                    "feat!: change API response format\n"
                    "\n"
                    "BREAKING CHANGE: Response now returns array instead of object"
                ),
                [],
            )

    # Warnings only (don't block)
    if re.search(r"\b(WIP|TODO|FIXME|XXX)\b", message, re.IGNORECASE):
        warnings.append("Contains WIP/TODO/FIXME markers")

    if type_part == "fix" and not re.search(r"#\d+|[A-Z]+-\d+", message):
        warnings.append("Fix commits should reference issue (e.g., #123, JIRA-456)")

    return True, "", warnings


def get_staged_tree_hash(ctx: Context) -> str:
    """Get the git tree hash of staged changes."""
    result = run_git(["write-tree"], cwd=ctx.root)
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def check_commit_review_requirement(ctx: Context) -> Output:
    """Check if commit requires review of exact staged changes."""
    token_env = "REVIEW_CHANGES"
    provided = os.getenv(token_env)

    # Get tree hash of staged content
    tree_hash = get_staged_tree_hash(ctx)

    if not tree_hash:
        return Output(
            success=False,
            message="Nothing staged to commit",
            details=[{"type": "text", "content": "No changes are staged for commit"}],
            next_steps=[
                "Stage changes: git add <files>",
                "Or stage all: git add .",
            ],
        )

    # Check for review token matching exact staged tree
    if not provided or not verify_content_token(
        ctx.name, "review_staged", tree_hash, provided
    ):
        # Check what type of changes exist
        status_result = run_git(["status", "--porcelain"], cwd=ctx.root)
        has_unstaged = False
        if status_result.returncode == 0:
            lines = (
                status_result.stdout.strip().split("\n")
                if status_result.stdout.strip()
                else []
            )
            has_unstaged = any(len(line) > 1 and line[1] in "MD" for line in lines)

        next_steps = [
            "Review your staged changes: git diff --staged",
            "This will generate a review token like: REVIEW_CHANGES=abc123:timestamp",
            "Then commit with: REVIEW_CHANGES=abc123:timestamp git commit -m 'your message'",
        ]
        if has_unstaged:
            next_steps.append(
                "Note: You also have unstaged changes not included in commit"
            )

        return Output(
            success=False,
            message="Must review staged changes before committing",
            details=[
                {
                    "type": "text",
                    "content": "Review token must match current staged content",
                },
                {
                    "type": "text",
                    "content": "If you stage more files, you'll need to review again",
                },
                {"type": "spacer"},
                {
                    "type": "text",
                    "content": "This ensures you commit exactly what you reviewed",
                },
            ],
            next_steps=next_steps,
        )

    return Output(success=True, message="Review token valid")


def enhance_commit_args(args: List[str]) -> Tuple[List[str], Output]:
    """Enhance commit command arguments."""
    # Find -m flag and its message
    if "-m" in args:
        msg_idx = args.index("-m") + 1
        if msg_idx < len(args):
            original_msg = args[msg_idx]

            # Strip Claude signatures
            clean_msg = strip_claude_signatures(original_msg)

            # Validate conventional commit
            valid, error, warnings = validate_conventional_commit(clean_msg)
            if not valid:
                return args, Output(
                    success=False,
                    message="Invalid commit message format",
                    details=[{"type": "text", "content": error}],
                    next_steps=[
                        "Use conventional commit format",
                        "Example: git commit -m 'feat: add new feature'",
                    ],
                )

            args[msg_idx] = clean_msg

            # If valid but has warnings, include them in details
            if warnings:
                # Still proceed, but show warnings
                warning_dicts = [{"type": "warning", "message": w} for w in warnings]
                return args, Output(success=True, message="", details=warning_dicts)

    return args, Output(success=True, message="")


def check_force_push(args: List[str]) -> Output:
    """Check if force push requires confirmation."""
    if "push" in args and ("--force" in args or "-f" in args):
        token = os.getenv("CONFIRM_FORCE_PUSH")

        if not token or not verify_token("force-push", "git", token):
            new_token = generate_token("force-push", "git", 60)
            return Output(
                success=False,
                message="Force push requires confirmation",
                details=[
                    {"type": "text", "content": "This will rewrite remote history"},
                    {"type": "text", "content": "Token expires in 1 minute"},
                ],
                next_steps=[f"CONFIRM_FORCE_PUSH={new_token} relkit git push --force"],
            )

    return Output(success=True, message="")


def check_main_branch_push(args: List[str]) -> Output:
    """Warn about pushing directly to main/master."""
    if "push" in args:
        # Get current branch
        result = run_git(["branch", "--show-current"])

        branch = result.stdout.strip()
        if branch in ["main", "master"]:
            # Return warning in Output, don't print
            return Output(
                success=True,
                message="",
                details=[
                    {
                        "type": "text",
                        "content": "Warning: Pushing directly to main branch",
                    }
                ],
            )

    return Output(success=True, message="")


@command("git", "", accepts_any_args=True)
def git_wrapper(ctx: Context, *git_args) -> Output:
    """
    Git wrapper that enforces conventions and adds safety.

    Features:
    - Strips Claude signatures automatically
    - Enforces conventional commit format
    - Requires confirmation for force push
    - Warns about main branch operations
    """
    args = list(git_args)

    if not args:
        # Show git help if no args
        args = ["--help"]

    # Store any warnings to display later
    warnings = []

    # Block direct git tag creation - but allow deletion and listing
    if args[0] == "tag" and len(args) > 1:
        # Allow listing tags (git tag -l) and deletion (git tag -d)
        if (
            "-l" not in args
            and "--list" not in args
            and "-d" not in args
            and "--delete" not in args
        ):
            return Output(
                success=False,
                message="BLOCKED: Direct git tag creation not allowed",
                details=[
                    {
                        "type": "text",
                        "content": "This project enforces release workflow",
                    },
                    {
                        "type": "text",
                        "content": "Tags are created automatically by relkit bump",
                    },
                ],
                next_steps=[
                    "Use: relkit bump <major|minor|patch>",
                    "This creates version, changelog, commit, and tag atomically",
                ],
            )

    # Apply enhancements based on git command
    if args[0] == "commit":
        # Check review requirement first
        review_result = check_commit_review_requirement(ctx)
        if not review_result.success:
            return review_result

        args, result = enhance_commit_args(args)
        if not result.success:
            return result
        # Collect warnings
        if result.details:
            warnings.extend(result.details)

    elif args[0] == "push":
        # Check force push
        result = check_force_push(args)
        if not result.success:
            return result

        # Warn about main branch
        result = check_main_branch_push(args)
        if not result.success:
            return result

    # Execute real git - need to let it output directly for interactive commands
    # But also capture for token generation
    if args[0] in ["log", "diff", "status", "show"]:
        # For review commands, capture output to check content
        proc = run_git(
            args,
            cwd=ctx.root,
            capture_output=True,
        )
        # Display git output
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)
    else:
        # For other commands, let git output directly
        proc = run_git(
            args,
            cwd=ctx.root,
            capture_output=False,
        )

    # Generate review tokens for informational commands
    token_details = []
    if proc.returncode == 0 and args[0] in ["log", "diff", "status", "show"]:
        if args[0] == "log":
            if proc.stdout.strip():
                # Generate commits review token
                review_token = generate_token(ctx.name, "review_commits", ttl=600)
                token_details.extend(
                    [
                        "",
                        f"Review token generated: REVIEW_COMMITS={review_token}",
                        "Valid for 10 minutes for operations requiring commit review",
                    ]
                )

        elif args[0] == "diff":
            # Check if this is staged diff or regular diff
            is_staged = "--staged" in args or "--cached" in args

            if proc.stdout.strip():
                # Generate content-based token for non-empty diff
                if is_staged:
                    # For staged changes, generate token tied to tree hash
                    tree_hash = get_staged_tree_hash(ctx)
                    if tree_hash:
                        review_token = generate_content_token(
                            ctx.name, "review_staged", tree_hash, ttl=600
                        )
                        token_details.extend(
                            [
                                "",
                                f"Review token generated: REVIEW_CHANGES={review_token}",
                                "Valid for committing THESE EXACT staged changes",
                            ]
                        )
                else:
                    # For unstaged changes, generate regular token
                    review_token = generate_token(ctx.name, "review_unstaged", ttl=600)
                    token_details.extend(
                        [
                            "",
                            f"Review token generated: REVIEW_CHANGES={review_token}",
                            "Valid for reviewing unstaged changes",
                        ]
                    )
            else:
                # No content to review - provide guidance
                if is_staged:
                    token_details.extend(
                        [
                            "",
                            "No staged changes to review",
                            "Stage changes with: git add <files>",
                        ]
                    )
                else:
                    # Check if there are staged changes they should review instead
                    status_result = run_git(["status", "--porcelain"], cwd=ctx.root)
                    if status_result.returncode == 0 and status_result.stdout:
                        lines = status_result.stdout.strip().split("\n")
                        has_staged = any(line and line[0] in "MADRC" for line in lines)
                        if has_staged:
                            token_details.extend(
                                [
                                    "",
                                    "No unstaged changes (all changes are staged)",
                                    "To review staged changes: relkit git diff --staged",
                                ]
                            )

        elif args[0] == "status":
            if proc.stdout.strip():
                # Generate status review token
                review_token = generate_token(ctx.name, "review_status", ttl=600)
                token_details.extend(
                    [
                        "",
                        f"Review token generated: REVIEW_STATUS={review_token}",
                        "Valid for 10 minutes for operations requiring status review",
                    ]
                )

        elif args[0] == "show":
            if proc.stdout.strip():
                # Generate commit details review token
                review_token = generate_token(ctx.name, "review_details", ttl=600)
                token_details.extend(
                    [
                        "",
                        f"Review token generated: REVIEW_DETAILS={review_token}",
                        "Valid for 10 minutes for detailed review operations",
                    ]
                )

    # Combine warnings and token details
    all_details = warnings if warnings else []
    if token_details:
        # Print token info to stderr so it doesn't interfere with piping
        # and is always visible to users
        for detail in token_details:
            if detail:  # Skip empty strings
                print(detail, file=sys.stderr)

    # Return based on git's exit code
    if proc.returncode == 0:
        return Output(
            success=True,
            message="",  # No message needed for successful git operations
            details=all_details if all_details else None,
        )
    else:
        return Output(
            success=False,
            message=f"Git command failed with exit code {proc.returncode}",
            details=all_details if all_details else None,
        )
