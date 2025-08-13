"""Status command showing release readiness."""

from typing import Optional, List, Dict, Any
from ..decorators import command
from ..models import Output, Context
from ..checks.git import check_clean_working_tree
from ..checks.changelog import check_version_entry, check_relkit_compatibility
from ..utils import run_git, resolve_package
from ..checks.quality import check_formatting, check_linting, check_types
from ..checks.hooks import check_hooks_initialized
from ..safety import generate_token


@command("status", "Show project release readiness")
def status(ctx: Context, package: Optional[str] = None) -> Output:
    """Display release readiness status at a glance."""

    # Handle workspace overview if no package specified
    if ctx.has_workspace and not package:
        details = [
            {"type": "text", "content": f"Workspace: {ctx.root.name}"},
            {
                "type": "text",
                "content": f"Packages ({len([p for p in ctx.packages if p != '_root'])}):",
            },
        ]
        for name, pkg in ctx.packages.items():
            if name != "_root":
                details.append(
                    {"type": "text", "content": f"  - {name} v{pkg.version}"}
                )

        return Output(
            success=True,
            message="Workspace overview",
            details=details,
            next_steps=[
                "Check specific package: relkit status --package <name>",
                "Bump package version: relkit bump patch --package <name>",
            ],
        )

    # Get target package
    target_pkg, error = resolve_package(ctx, package)
    if error:
        return error

    # Run all checks - pass package to checks that need it
    # Check changelog compatibility first
    changelog_compat = check_relkit_compatibility(ctx, package=package)
    if not changelog_compat.success:
        changelog_check = changelog_compat
    else:
        changelog_check = check_version_entry(ctx, package=package)

    checks = [
        ("Hooks", check_hooks_initialized(ctx)),
        ("Git", check_clean_working_tree(ctx)),
        ("Changelog", changelog_check),
        ("Formatting", check_formatting(ctx)),
        ("Linting", check_linting(ctx)),
        ("Types", check_types(ctx)),
    ]

    # Build status display
    ready_count = sum(1 for _, result in checks if result.success)
    total_count = len(checks)

    # Get package-specific tag info
    last_tag = target_pkg.get_last_tag() if target_pkg else None
    if last_tag:
        result = run_git(["rev-list", f"{last_tag}..HEAD", "--count"], cwd=ctx.root)
        commits_since = int(result.stdout.strip()) if result.returncode == 0 else 0
    else:
        result = run_git(["rev-list", "HEAD", "--count"], cwd=ctx.root)
        commits_since = int(result.stdout.strip()) if result.returncode == 0 else 0

    pkg_label = "Package" if ctx.has_workspace else "Project"
    details: List[Dict[str, Any]] = [
        {
            "type": "text",
            "content": f"{pkg_label}: {target_pkg.name} v{target_pkg.version}",
        },
        {"type": "text", "content": f"Type: {ctx.type}"},
        {"type": "text", "content": f"Last tag: {last_tag or 'none'}"},
        {"type": "text", "content": f"Commits since tag: {commits_since}"},
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
