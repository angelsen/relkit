"""Detailed check commands for code quality and git status."""

from typing import Literal
from ..decorators import command
from ..models import Output, Context
from ..checks.git import check_clean_working_tree
from ..checks.changelog import check_version_entry, check_relkit_compatibility
from ..checks.quality import check_formatting, check_linting, check_types
from ..utils import run_ruff_format, run_ruff_check


CheckType = Literal["all", "git", "changelog", "format", "lint", "types"]


def run_fixes(ctx: Context, check_type: str) -> Output:
    """Run auto-fixes for the specified check type."""
    fixes_applied = []

    if check_type in ("all", "format"):
        # Run ruff format using utility
        result = run_ruff_format(cwd=ctx.root, check=False)
        if result["success"]:
            fixes_applied.append(
                {"type": "fix", "success": True, "message": "Applied formatting fixes"}
            )

    if check_type in ("all", "lint"):
        # Run ruff check --fix using utility
        result = run_ruff_check(cwd=ctx.root, fix=True)
        if result["success"]:
            fixes_applied.append(
                {
                    "type": "fix",
                    "success": True,
                    "message": "Applied auto-fixable linting fixes",
                }
            )

    if fixes_applied:
        return Output(
            success=True,
            message="Applied automatic fixes",
            details=fixes_applied
            + [
                {"type": "spacer"},
                {"type": "text", "content": "Now running checks..."},
            ],
        )

    return Output(success=True, message="No auto-fixes available for this check type")


@command("check", "Run detailed quality checks")
def check(ctx: Context, check_type: CheckType = "all", fix: bool = False) -> Output:
    """
    Run detailed quality checks with full output.

    Args:
        check_type: Type of check to run (all, git, changelog, format, lint, types)
        fix: Whether to apply auto-fixes before checking

    Returns:
        Detailed output for the requested checks
    """
    if fix:
        # Run fixes first
        fix_result = run_fixes(ctx, check_type)
        if not fix_result.success:
            return fix_result
    # Single check requested
    if check_type == "git":
        return check_clean_working_tree(ctx)
    elif check_type == "changelog":
        # Check compatibility first - fail fast if not relkit-compatible
        compat_result = check_relkit_compatibility(ctx)
        if not compat_result.success:
            return compat_result
        # Only check version entry if compatible
        return check_version_entry(ctx)
    elif check_type == "format":
        return check_formatting(ctx)
    elif check_type == "lint":
        return check_linting(ctx)
    elif check_type == "types":
        return check_types(ctx)

    # Run all checks with detailed output
    results = []

    # Git checks
    git_result = check_clean_working_tree(ctx)
    results.append(("Git status", git_result))

    # Changelog checks - compatibility first, then version entry
    changelog_compat = check_relkit_compatibility(ctx)
    if not changelog_compat.success:
        results.append(("Changelog", changelog_compat))
    else:
        changelog_result = check_version_entry(ctx)
        results.append(("Changelog", changelog_result))

    # Quality checks (run in parallel for speed)
    format_result = check_formatting(ctx)
    results.append(("Formatting", format_result))

    lint_result = check_linting(ctx)
    results.append(("Linting", lint_result))

    type_result = check_types(ctx)
    results.append(("Type checking", type_result))

    # Aggregate results
    all_passed = all(r[1].success for r in results)
    failed_checks = [name for name, result in results if not result.success]

    # Build detailed output
    details = []
    for name, result in results:
        details.append(
            {
                "type": "check",
                "name": name,
                "success": result.success,
                "message": result.message,
                "sub_details": result.details[:5] if result.details else None,
                "overflow": len(result.details) - 5
                if result.details and len(result.details) > 5
                else 0,
            }
        )

    if all_passed:
        return Output(success=True, message="All checks passed", details=details)
    else:
        return Output(
            success=False,
            message=f"{len(failed_checks)} check(s) failed: {', '.join(failed_checks)}",
            details=details,
            next_steps=[
                "Fix the issues above",
                "Run 'relkit check <type>' to focus on specific issues",
            ],
        )
