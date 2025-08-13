"""Safety confirmation system with TTL tokens and git validation."""

import os
import hashlib
import time
from functools import wraps
from typing import Callable
from .models import Output, Context
from .utils import run_git

# Salt for token generation - in production, this could be from config
SALT = "relkit-safety-2024-stateless"


def generate_token(package: str, action: str, ttl: int = 300) -> str:
    """
    Generate stateless time-based token.

    Args:
        package: Package name
        action: Action being confirmed (e.g., "publish", "tag")
        ttl: Time to live in seconds

    Returns:
        Token string in format "hash:expiry"
    """
    expiry = int(time.time()) + ttl
    # Include action in hash to prevent cross-command token reuse
    data = f"{package}:{action}:{expiry}:{SALT}"
    token = hashlib.sha256(data.encode()).hexdigest()[:8]
    return f"{token}:{expiry}"


def verify_token(package: str, action: str, token: str) -> bool:
    """
    Verify token by recreating hash.

    Args:
        package: Package name
        action: Action being confirmed
        token: Token string to verify

    Returns:
        True if token is valid and not expired
    """
    try:
        hash_part, expiry_str = token.split(":")
        expiry = int(expiry_str)

        # Check if expired
        if expiry < time.time():
            return False

        # Recreate with same inputs
        data = f"{package}:{action}:{expiry}:{SALT}"
        expected = hashlib.sha256(data.encode()).hexdigest()[:8]
        return hash_part == expected
    except (ValueError, AttributeError):
        return False


def generate_content_token(
    package: str, action_type: str, content: str, ttl: int = 600
) -> str:
    """
    Generate token tied to specific content hash.

    Args:
        package: Package name
        action_type: Base action type (e.g., "review_staged")
        content: The actual content that was reviewed
        ttl: Time to live in seconds

    Returns:
        Token that proves review of specific content
    """
    if not content or not content.strip():
        # Empty content gets special marker
        action = f"{action_type}_empty"
    else:
        # Hash the content for verification
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        action = f"{action_type}_{content_hash}"

    return generate_token(package, action, ttl)


def verify_content_token(
    package: str, action_type: str, content: str, token: str
) -> bool:
    """
    Verify token matches specific content.

    Args:
        package: Package name
        action_type: Base action type
        content: The content to verify against
        token: Token to verify

    Returns:
        True if token is valid for this exact content
    """
    if not content or not content.strip():
        action = f"{action_type}_empty"
    else:
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:8]
        action = f"{action_type}_{content_hash}"

    return verify_token(package, action, token)


def generate_state_token(
    package: str, state_type: str, state_value: str, ttl: int = 600
) -> str:
    """
    Generate token for specific state.

    Args:
        package: Package name
        state_type: Type of state (e.g., "git_status", "test_result")
        state_value: State value (e.g., "clean", "passed", "failed")
        ttl: Time to live in seconds

    Returns:
        Token that proves observation of specific state
    """
    action = f"{state_type}_{state_value}"
    return generate_token(package, action, ttl)


def requires_confirmation(action: str, ttl: int = 300, skip_private: bool = False):
    """
    Decorator for commands requiring safety confirmation.

    Args:
        action: Action name for token generation
        ttl: Time to live for token in seconds
        skip_private: Skip confirmation for private packages

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(ctx: Context, *args, **kwargs) -> Output:
            # Skip for private packages if configured
            if skip_private and action == "publish" and not ctx.is_public:
                return func(ctx, *args, **kwargs)

            # Check for confirmation token
            token_env = f"CONFIRM_{action.upper()}"
            provided = os.getenv(token_env)

            if not provided or not verify_token(ctx.name, action, provided):
                new_token = generate_token(ctx.name, action, ttl)

                # Build details based on action
                details = [
                    {"type": "text", "content": f"Package: {ctx.name} v{ctx.version}"},
                    {
                        "type": "text",
                        "content": f"Token expires in {ttl // 60} minutes",
                    },
                ]

                if action == "publish" and ctx.is_public:
                    details.extend(
                        [
                            {"type": "spacer"},
                            {
                                "type": "text",
                                "content": "This package will be PUBLIC on PyPI",
                            },
                            {
                                "type": "text",
                                "content": "Anyone can pip install this package",
                            },
                        ]
                    )
                elif action == "tag":
                    details.extend(
                        [
                            {"type": "spacer"},
                            {
                                "type": "text",
                                "content": "This will create a git tag that marks this release",
                            },
                            {
                                "type": "text",
                                "content": "Tags are typically permanent in git history",
                            },
                        ]
                    )

                details.append(
                    {"type": "text", "content": "This action cannot be undone"}
                )

                return Output(
                    success=False,
                    message=f"Confirmation required for: {action}",
                    details=details,
                    next_steps=[f"Run: {token_env}={new_token} relkit {action}"],
                )

            # Token is valid, proceed with command
            return func(ctx, *args, **kwargs)

        return wrapper

    return decorator


def requires_review(review_type: str, review_commands: list[str], ttl: int = 600):
    """
    Decorator requiring proof of recent review via specific commands.

    Args:
        review_type: What needs reviewing (e.g., "commits", "changes", "status")
        review_commands: Commands that generate review tokens (e.g., ["git log", "git diff"])
        ttl: How long review is valid (default 10 min)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(ctx: Context, *args, **kwargs) -> Output:
            token_env = f"REVIEW_{review_type.upper()}"
            provided = os.getenv(token_env)

            # Special token type for reviews
            review_action = f"review_{review_type}"

            if not provided or not verify_token(ctx.name, review_action, provided):
                return Output(
                    success=False,
                    message=f"Recent review of {review_type} required",
                    details=[
                        {
                            "type": "text",
                            "content": f"You must review {review_type} before this operation",
                        },
                        {
                            "type": "text",
                            "content": f"Review tokens expire after {ttl // 60} minutes",
                        },
                        {"type": "spacer"},
                        {
                            "type": "text",
                            "content": "This ensures you make informed decisions based on recent information",
                        },
                    ],
                    next_steps=[
                        f"Run one of: {', '.join(review_commands)}",
                        "This will generate a review token",
                        "Then retry this command",
                    ],
                )

            # Review token is valid, proceed with command
            return func(ctx, *args, **kwargs)

        return wrapper

    return decorator


def requires_active_decision(action: str, checks: list[Callable], ttl: int = 300):
    """
    Decorator requiring confirmation when checks indicate non-standard state.
    Unlike requires_confirmation, this only triggers when issues are found.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(ctx: Context, *args, **kwargs) -> Output:
            # Run checks to see if we're in non-standard state
            warnings = []
            for check_func in checks:
                # Handle checks that need additional context
                if callable(check_func):
                    # Check if the check needs kwargs (like bump_type)
                    import inspect

                    sig = inspect.signature(check_func)
                    if len(sig.parameters) > 1:
                        # Pass kwargs if check needs them
                        result = check_func(ctx, **kwargs)
                    else:
                        result = check_func(ctx)

                    if not result.success:
                        warnings.append({"type": "warning", "message": result.message})

            if warnings:
                # Non-standard state detected, require confirmation
                token_env = f"CONFIRM_{action.upper()}"
                provided = os.getenv(token_env)

                if not provided or not verify_token(ctx.name, action, provided):
                    new_token = generate_token(ctx.name, action, ttl)

                    return Output(
                        success=False,
                        message=f"{action.capitalize()} requires confirmation of non-standard state",
                        details=warnings
                        + [
                            {"type": "spacer"},
                            {
                                "type": "text",
                                "content": f"Token expires in {ttl // 60} minutes",
                            },
                        ],
                        next_steps=[
                            "Fix the issues above (recommended)",
                            f"Or confirm you understand: {token_env}={new_token} relkit {action}",
                        ],
                    )

            # Either no warnings or valid token provided
            return func(ctx, *args, **kwargs)

        return wrapper

    return decorator


def requires_clean_git(func: Callable) -> Callable:
    """
    Decorator that blocks operations if git working directory is dirty.
    No bypass, no escape hatch - enforcement only.
    """

    @wraps(func)
    def wrapper(ctx: Context, *args, **kwargs) -> Output:
        # Check git status
        result = run_git(["status", "--porcelain"], cwd=ctx.root)

        if result.returncode != 0:
            return Output(
                success=False,
                message="Cannot proceed: Unable to check git status",
                details=[
                    {"type": "text", "content": "Git status check failed"},
                    {
                        "type": "text",
                        "content": result.stderr.strip()
                        if result.stderr
                        else "Unknown error",
                    },
                ],
            )

        changes = result.stdout.strip()

        if changes:
            lines = changes.split("\n")
            return Output(
                success=False,
                message="BLOCKED: Git working directory must be clean",
                details=[
                    {
                        "type": "text",
                        "content": f"Found {len(lines)} uncommitted change(s):",
                    },
                    {"type": "spacer"},
                ]
                + [{"type": "text", "content": line} for line in lines[:10]]
                + (
                    [{"type": "text", "content": "... and more"}]
                    if len(lines) > 10
                    else []
                ),
                next_steps=[
                    "Commit all changes: git commit -am 'your message'",
                    "Or stash them: git stash",
                    "Then try again",
                ],
            )

        # Git is clean, proceed
        return func(ctx, *args, **kwargs)

    return wrapper


def requires_clean_dist(func: Callable) -> Callable:
    """
    Decorator that blocks operations if dist directory contains files.
    No bypass, no escape hatch - enforcement only.
    """

    @wraps(func)
    def wrapper(ctx: Context, *args, **kwargs) -> Output:
        # Get package parameter from kwargs if it exists
        package = kwargs.get("package")

        # Get the correct dist path
        try:
            dist_path = ctx.get_dist_path(package)
        except ValueError as e:
            return Output(success=False, message=str(e))

        # Check if dist exists and has files
        if dist_path.exists() and dist_path.is_dir():
            files = list(dist_path.glob("*.whl")) + list(dist_path.glob("*.tar.gz"))
            if files:
                # Extract versions to show what's there
                versions = set()
                for f in files:
                    parts = f.name.replace(".tar.gz", "").replace(".whl", "").split("-")
                    if len(parts) >= 2:
                        versions.add(parts[1])

                return Output(
                    success=False,
                    message="BLOCKED: Distribution directory must be clean before building",
                    details=[
                        {
                            "type": "text",
                            "content": f"Found {len(files)} file(s) in {dist_path}:",
                        },
                        {"type": "spacer"},
                    ]
                    + [
                        {"type": "text", "content": f"  • {f.name}"}
                        for f in sorted(files)[:5]  # Show first 5
                    ]
                    + (
                        [
                            {
                                "type": "text",
                                "content": f"  ... and {len(files) - 5} more",
                            }
                        ]
                        if len(files) > 5
                        else []
                    )
                    + [
                        {"type": "spacer"},
                        {
                            "type": "text",
                            "content": "Mixing versions in dist/ can lead to publishing wrong packages",
                        },
                    ],
                    next_steps=[
                        f"Review the files: ls -la {dist_path}",
                        f"Clean the directory: rm -rf {dist_path}/*",
                        "Run build again: relkit build"
                        + (f" --package {package}" if package else ""),
                    ],
                )

        # Dist is clean or doesn't exist, proceed
        return func(ctx, *args, **kwargs)

    return wrapper
