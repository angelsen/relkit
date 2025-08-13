"""Status command showing release readiness."""

from typing import Optional, List, Dict, Any
from ..decorators import command
from ..models import Output, Context
from ..checks.git import check_git_clean, check_changelog
from ..checks.quality import check_formatting, check_linting, check_types
from ..checks.hooks import check_hooks_initialized
from ..safety import generate_token


@command("status", "Show project release readiness")
def status(ctx: Context, package: Optional[str] = None) -> Output:
    """Display release readiness status at a glance."""

    # Run all checks
    checks = [
        ("Hooks", check_hooks_initialized(ctx)),
        ("Git", check_git_clean(ctx)),
        ("Changelog", check_changelog(ctx)),
        ("Formatting", check_formatting(ctx)),
        ("Linting", check_linting(ctx)),
        ("Types", check_types(ctx)),
    ]

    # Build status display
    ready_count = sum(1 for _, result in checks if result.success)
    total_count = len(checks)

    details: List[Dict[str, Any]] = [
        {"type": "text", "content": f"Project: {ctx.name} v{ctx.version}"},
        {"type": "text", "content": f"Type: {ctx.type}"},
        {"type": "text", "content": f"Last tag: {ctx.last_tag or 'none'}"},
        {"type": "text", "content": f"Commits since tag: {ctx.commits_since_tag}"},
        {"type": "spacer"},
        {"type": "text", "content": "Release Readiness:"},
    ]

    for name, result in checks:
        status_msg = result.message
        # Shorten some messages for cleaner display
        if "Git working directory is clean" in status_msg:
            status_msg = "Clean"
        elif "Git working directory has" in status_msg:
            # Extract just the key info
            import re

            match = re.search(r"has (\d+ uncommitted change)", status_msg)
            if match:
                status_msg = match.group(1) + "(s)"
        elif "Code formatting is correct" in status_msg:
            status_msg = "Correct"
        elif "No linting issues found" in status_msg:
            status_msg = "No issues"
        elif "Type checking passed" in status_msg:
            status_msg = "Passed"

        # Return structured data instead of formatted strings
        details.append(
            {
                "type": "check",
                "name": name,
                "success": result.success,
                "message": status_msg,
            }
        )

    all_ready = ready_count == total_count

    # Generate review token for release readiness
    review_token = generate_token(ctx.name, "review_readiness", ttl=600)  # 10 min
    details.append({"type": "spacer"})
    details.append(
        {
            "type": "token",
            "success": True,
            "message": f"Review token generated: REVIEW_READINESS={review_token}",
        }
    )
    details.append(
        {
            "type": "text",
            "content": "Valid for 10 minutes for operations requiring readiness review",
        }
    )

    if all_ready:
        return Output(
            success=True,
            message=f"Ready for release ({ready_count}/{total_count} checks passed)",
            details=details,
            next_steps=["Run: relkit release"],
        )
    else:
        next_steps = []
        # Provide targeted guidance
        if any(name == "Formatting" and not result.success for name, result in checks):
            next_steps.append("Run: relkit check format --fix")
        if any(name == "Linting" and not result.success for name, result in checks):
            next_steps.append("Run: relkit check lint --fix")
        if any(name == "Git" and not result.success for name, result in checks):
            next_steps.append("Commit changes: git commit -am 'your message'")
        if any(name == "Changelog" and not result.success for name, result in checks):
            next_steps.append("Update CHANGELOG.md with changes")

        next_steps.append("Then: relkit status")

        return Output(
            success=False,
            message=f"Not ready for release ({ready_count}/{total_count} checks passed)",
            details=details,
            next_steps=next_steps,
        )
